"""대본 다듬기 v2.4 — 템플릿 초안 + 사실표(뉴스 헤드라인·지표 실제값)를 Claude(claude -p)에 주고 사람 말투로 다시 쓴다.
새 역할(JJ 2026-09-05): 마감 '배경'을 뉴스 헤드라인에서 찾아 완곡하게 엮고, 다음 관문의 조건부 전망을 붙인다.
검증(장면 단위, 실패 시 템플릿 유지):
  1) 숫자는 초안·헤드라인·사실표에 있는 것만  2) 금지어·단정 표현 없음(checks.forbidden)
  3) 첫 장면은 초안 첫 문장으로 시작하고 80자 이내(10초)  4) 마지막 장면은 브랜드로 시작
  5) 큐워드('국장'/'미국') 유지  6) 길이 초안의 1.25배 이내  7) 배경·원인 문장에는 완곡 표지가 있어야 한다
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime

from _common import DATA, computed_path, load_json, log, save_json
sys.path.insert(0, str(DATA.parent))
from checks import forbidden, jargon  # noqa: E402
from threads_v4 import tail_ok as _banmal_tail  # noqa: E402  (쓰레드 반말 종결 규칙은 threads_v4 한 곳만 본다)

STYLE = """말투 기준(운영자 예문):
"밤낮장, 9월 4일 금요일 국내장 마감입니다. 간밤 나스닥 상승에 이어 국장도 같은 방향으로, 코스피는 1.64% 오른 6,687에 마쳤습니다."
"국장 수급입니다. 개인은 약 3.7조를 순매도했고, 외국인과 기관은 각각 약 5천억과 약 1.7조를 순매수했습니다. 외국인은 6일 만에 순매수로 돌아섰습니다."
"그럼 오늘 국장에서 돈은 어디로 들어와 어디에 머물고 있을까요? 돈은 금융에서 반도체로 옮겨갔습니다. 반도체에는 약 1.4조가 들어왔는데 외국인과 기관이 둘 다 샀고, SK하이닉스·삼성전자·한미반도체로 번졌습니다."
"간밤 주요 일정은 고용보고서였습니다. 8월 비농업 고용은 16만 2천 명 늘었고 실업률은 4.1%였습니다. 고용이 예상보다 훨씬 좋게 나오면서 금리 인상 경계가 되살아난 것이 하락 배경으로 꼽혔습니다. 다음 관문은 11일 CPI입니다. 물가까지 강하게 나오면 금리 부담이 이어질 수 있습니다."
"내일 우리가 체크해야 할 것은 반도체 순매수가 이틀째 이어지는지입니다. 이어지면 그 흐름에 방향을 맞추고, 끊기면 매수 판단은 미루는 편이 안전해 보입니다."
"""

RULES = """규칙(어기면 그 장면은 폐기됨):
- 숫자·날짜·요일·종목명·테마명·기관명은 초안이나 아래 사실표(헤드라인 포함)에 있는 것만 쓴다. 새 숫자·반올림 변경·추정 금지.
- 마감 '배경·원인'은 반드시 사실표의 뉴스 헤드라인에 있는 내용으로만 쓴다. 헤드라인에 없는 원인을 지어내지 말 것. 여러 매체가 공통으로 꼽은 원인을 고른다.
- 원인·전망은 완곡하게: '~로 꼽혔습니다', '~로 풀이됩니다', '~것으로 보입니다', '~수 있습니다'. 단정('확실히', '반드시', '~할 것입니다') 금지.
- 전망은 조건부로만: '다음 관문에서 A가 나오면 B가 이어질 수 있습니다'처럼 예정된 일정에 묶는다. 가격 목표·종목 추천·매수/매도 지시 금지(수급 용어 '순매수/순매도'와 시장 단위의 '매수 판단은 미루는 편' 표현은 허용).
- 영상 장면(s0~s6)은 화자 없음: '저는', '제 생각', '개인적으로' 금지. 진행자 이름 금지. ("threads"만 예외 — 아래 규칙)
- 국장편 첫 장면(s0)은 초안을 글자 그대로 둔다(오늘의 사실 한 문장 → '그 돈은 어디로 갔을까요?' → 날짜·브랜드). 한 글자도 고치지 말 것.
- 미국편 첫 장면(u0)은 초안의 첫 문장을 글자 그대로 유지하고(브랜드, 날짜·요일, '… 마감입니다'), 전체 65자 이내로 끝낸다(10초). 훅 문장은 '원인 한 마디 + 결과' 병치로: "고용 호조에 금리 경계가 살아나며 나스닥은 0.29% 하락 마감했습니다"처럼 '~에 …하며/~속에'. '영향으로', '때문에', '탓에' 같은 단정 인과어는 쓰지 않는다.
- s3 첫머리의 전날 예고 검증 문장("어제 … 보자고 했죠. 오늘 …")은 글자 그대로 유지한다. 이 채널의 핵심 장치다.
- s3의 "그럼 오늘 국장에서 돈은 어디로 갔을까요? {테마}입니다." 두 문장은 그대로 둔다(화면이 이 문장에 맞춰 테마를 크게 띄운다). 종목명 나열 문장("A, B와 C에 몰렸습니다")도 이름을 빼거나 바꾸지 말 것.
- s5의 방향 문장("…눈여겨보는 게 순서입니다", "…확인이 먼저입니다", "…쉬어가는 구간…", "…흐름으로 볼 수 있습니다")과 마지막 동행 문장("…같이 보겠습니다", "…같이 증명해 가겠습니다", "…같이 확인하겠습니다" 등)은 글자 그대로 유지한다. '확률', '승률', '부자', '돈을 벌' 같은 낱말은 어디에도 넣지 않는다.
- 한자(美·中·日 등)는 한글로 쓴다(美 → 미국). 영문 약어(CPI, FOMC, ETF, EWY, S&P500, QQQ)는 자막에 그대로 보여야 하므로 영문 그대로 둔다(씨피아이·이티에프처럼 소리나는 대로 풀어 쓰지 말 것).
- 초안의 용어 풀이 문장("~은 …입니다"처럼 용어를 설명하는 한 문장)은 빼지 말고 뜻 그대로 둔다. 초보자용이다.
- 장중→마감 비교 문장("오후 2시 약 X에서 마감 약 Y")은 이 채널의 핵심 정보다. 두 숫자와 '오후 2시', '마감'을 모두 살려 쓴다. "장 후반 들어 늘었다"처럼 숫자를 빼고 뭉뚱그리지 말 것.
- 시간 표현은 초안 그대로: '간밤'/'지난 금요일 밤'/'전날'/'지난 금요일'을 바꾸지 말 것(월요일 아침편은 금요일 세션이다).
- 고점·저점은 '고점 X, 저점 Y를 거쳐 Z에 마감' 병렬로만. '오간 뒤', '찍고', '올랐다가 밀렸다' 같은 순서 암시 금지(초안에 없으면).
- 초안에 데이터 기반 배경 문장("~한 하루였습니다", "~한 날이었습니다")이 있으면 뉴스 근거 배경 문장으로 '대체'한다. 둘 다 두지 말 것.
- 마지막 장면(s6/u5)은 브랜드 이름으로 시작하고, '매일 … 올라옵니다' 업로드 시각 문장을 글자 그대로 유지한다.
- 전체 목표는 90초다. 초안보다 짧게 쓰는 것은 언제나 환영이다.
- 국장편에는 '국장'이라는 단어가, 미국편에는 '미국'이라는 단어가 장면마다 자연스럽게 들어가 듣기만 해도 어느 편인지 알 수 있게 한다.
- 각 장면은 초안과 같은 내용을 같은 순서로, 사람이 말하듯. 늘리지 말 것(초안 길이의 1.2배 이내). 시각(몇 시 몇 분) 서술 금지.
- 초안의 마지막 '체크' 장면에 있는 어시스트 문장(이어지면/끊기면 …)은 뜻을 바꾸지 말고 자연스럽게만 다듬는다. 종목명을 넣지 말 것.
- 이슈 문장("간밤 애플이 … 공개했는데/공개했지만, … 올랐습니다/내렸습니다")은 제품명·종목명·등락률·순매수 숫자를 그대로 둔다. 내린 날에 한해 사실표 헤드라인에 이유가 있으면 완곡하게 한 문장만 덧붙인다("…이 배경으로 꼽혔습니다"). 헤드라인에 없으면 이유를 지어내지 말 것. '영향으로', '때문에' 금지.
- "threads" 항목은 영상 대본이 아니라 운영자(개인 투자자)가 자기 계정에 올리는 글이다. 초안(threads)은 사실 메모일 뿐이니 그 사실을 바탕으로 **친한 사람에게 오늘 장을 말해 주듯** 다시 쓴다:
  · **반말**(JJ 2026-09-13). '-습니다/-입니다', '-요' 둘 다 금지. '-어/-야/-아/-해'로 끝낸다("팔았어", "회사들이야", "그게 무슨 뜻이야").
    시비조가 아니라 친한 사람에게 설명하는 말투다. 음슴체·축약 종결형("팜", "샀음", "오름", "~인듯")과 채팅 기호(ㅋㅋ ㅎㅎ ㅠㅠ)는 금지.
  · 첫 줄은 읽는 사람이 오늘 이미 본 것(코스피 등락률)을 인정하고 넘어간다("주식 앱 켜면 0.58% 하락이 떠 있어."). 그래서 첫 줄에는 숫자가 들어간다.
  · 둘째 줄은 그 숫자만 보면 놓치는, 숫자가 든 사실 한 줄.
  · 숫자는 글 전체에 최대 5개(억·조·%)만. 초안에 있는 숫자만 쓴다. 초안의 숫자를 다른 표현으로 바꾸지 말 것('33거래일' → '두 달 만에' 같은 환산·어림 금지). 뺄 수는 있어도 바꿀 수는 없다.
  · 가운데는 누가 받았나 / 돈이 어디로 갔나 / 어제 보자고 한 게 이어졌는지 끊겼는지. 질문 한 줄을 가운데 넣어도 된다.
  · 끝에서 두 번째 줄이 '그래서 무슨 뜻'을 맡고, **마지막 한 줄은 읽는 사람에게 던지는 질문**으로 닫는다("너넨 이 돈 누가 받았다고 봐?"). 답글이 달리게.
    읽는 사람의 손익·보유를 전제하는 질문("물렸지?", "얼마나 샀어?")은 금지. 마지막 줄에는 숫자를 넣지 않는다.
  · '내일/월요일에 볼 것'과 채널 고지·영상 링크는 본문이 아니라 첫 답글이 맡는다 — 본문에 넣지 마라.
  · 금융 용어 금지(순매수·순매도·수급·물량·종목·주체·기타법인·자사주·지수·등락·변동성·반등·거래대금·국장 …). 뜻만 쉬운 말로 남긴다.
  · 매수·매도 권유, 종목 추천, 수익·확률·부자 표현, 말줄임표, 해시태그 금지(해시태그는 코드가 붙인다). 이모지는 편당 0~1개.
  · 한 호흡에 한 줄. 문단 사이는 빈 줄. 전체 330~430자.
- 출력은 JSON 객체 하나만: {"s0": "...", "s1": "...", "threads": "...", ...} (키는 초안과 동일). 다른 말 금지.
"""

NUM_RE = re.compile(r"\d[\d,]*\.?\d*")
# 초안에 있으면 다듬은 문장에도 반드시 남아야 하는 구절(예고 검증·방향·동행)
KEEP_PHRASES = ("보자고 했죠", "돈은 아직 여기", "늦지 않다고 한 이유", "눈여겨보는 게 순서", "확인이 먼저", "쉬어가는 구간", "흐름으로 볼 수",
                "같이 보겠습니다", "같이 증명해", "기록에 그대로", "같이 확인하겠습니다", "보는 건 같이", "이 채널의 답", "그 돈은 어디로 갔을까요", "그럼 누가 샀나", "누군가는", "어떤 회사들인지는", "외국인과 기관을 합", "전날 확인하기로 한", "이어진 날도 끊긴 날도")
INTRA_RE = re.compile(r"오후 \d시(?: \d+분)?(?:까지|엔| )[^.]*?(약 [\d,.]+(?:조|천억|억))[^.]*?마감[^.]*?(약 [\d,.]+(?:조|천억|억))")


def _intraday_kept(draft: str, new: str) -> bool:
    m = INTRA_RE.search(draft or "")
    if not m:
        return True
    return all(x in new for x in (m.group(1), m.group(2))) and "오후" in new
CAUSE_WORDS = ("배경", "우려", "경계", "기대", "영향", "탓에", "탓으로", "덕에", "덕분", "때문", "호조", "부진", "안정", "완화", "실망", "서프라이즈")   # 한 글자 표지는 종목명(덕산네오룩스) 오탐


def _nums(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(text or "")}


def _call_claude(prompt: str, timeout: int = 300, model: str = "sonnet") -> str:
    """프롬프트는 stdin으로(Windows 인자 길이·따옴표 문제 회피). 모델은 sonnet(대본 다듬기엔 충분, 비용 1/10)."""
    import time
    cmd = ["claude", "-p", "--output-format", "json", "--max-turns", "2", "--tools", "", "--model", model]
    last = ""
    for attempt in range(3):
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=(sys.platform == "win32"))
        if r.returncode == 0:
            try:
                j = json.loads(r.stdout)
                return j.get("result") or ""
            except json.JSONDecodeError:
                return r.stdout
        last = f"claude -p rc={r.returncode}: {(r.stderr or r.stdout)[-400:]}"
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(last)


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _facts(comp: dict, ed: str) -> str:
    """사실표: 뉴스 헤드라인(시각·매체·제목), 지표 실제값, 지수."""
    lines = []
    items = comp.get("news_items") or []
    if items:
        lines.append("뉴스 헤드라인(마감 뒤 보도, 최신순):")
        for it in items[:16]:
            lines.append(f"  - {it['pub_kst'][5:]} [{it['source']}] {it['title']}")
    else:
        lines.append("뉴스 헤드라인: 없음 → 배경 문장은 초안 그대로 두거나 생략한다.")
    bv = comp.get("bls_values")
    if bv and not bv.get("stale"):
        lines.append(f"지표 실제값({bv['what']}, {bv['period']}): {json.dumps(bv['values'], ensure_ascii=False)}")
    if ed == "us":
        for k, v in (comp.get("idx") or {}).items():
            lines.append(f"지수 {v['name']}: 종가 {v['close']} 고점 {v['high']} 저점 {v['low']} 등락 {v['pct']}%")
        for e in comp.get("events") or []:
            lines.append(f"이벤트: {e['what']} 발표 뒤 30분 {e.get('react30')}% / 이후 마감까지 {e.get('react_close')}%")
    else:
        k = comp.get("kospi") or {}
        lines.append(f"코스피 종가 {k.get('close')} 고점 {k.get('high')} 저점 {k.get('low')} 등락 {k.get('chg_pct')}%")
        ul = comp.get("us_link") or {}
        if ul:
            lines.append(f"간밤 {ul.get('name')} 등락 {ul.get('pct')}%")
    return "\n".join(lines)


def _hedge_ok(text: str) -> bool:
    for s in forbidden._sentences(text):
        if any(w in s for w in CAUSE_WORDS) and not any(h in s for h in forbidden.HEDGES):
            # '…가 있습니다/였습니다'처럼 단순 사실 진술이면 통과, 원인 연결어가 있으면 완곡 표지 필요
            if re.search(r"(에|로|으로|며|면서|자)\s*\S*(하락|상승|올랐|내렸|밀렸|반등|마감)", s):
                return False
    return True


def polish(d: str, ed: str = "kr") -> dict:
    comp = load_json(computed_path(d, ed))
    if not comp:
        raise SystemExit("computed 없음")
    if ed == "kr" and comp.get("format") == "aplus":
        log(d, "polish", "A+ 형식: 대본 틀 그대로 읽음(다듬기 생략)")
        return comp
    scenes = comp["scenes"]
    brand = comp.get("brand") or "밤낮장"
    drafts = {sc["id"]: sc["tts"] for sc in scenes}
    if comp.get("threads_text"):
        drafts["threads"] = comp["threads_text"]
    facts = _facts(comp, ed)
    facts_nums = set()
    for t in list(drafts.values()) + [facts]:
        facts_nums |= _nums(t)
    cue = "국장" if ed == "kr" else "미국"
    prompt = (f"너는 한국 주식 브리핑 채널 '{brand}'의 대본 편집자다. 아래 초안을 자연스러운 한국어 구어체로 다시 쓰고, "
              f"마감 배경은 사실표의 뉴스 헤드라인에서 찾아 완곡하게 엮어라.\n\n{STYLE}\n{RULES}\n"
              f"편집본: {'국내장(저녁)' if ed == 'kr' else '미국장(아침)'}\n\n사실표:\n{facts}\n\n초안(JSON):\n{json.dumps(drafts, ensure_ascii=False, indent=1)}\n")
    log(d, "polish", f"{ed}: claude -p 호출 (초안 {len(drafts)}장면, 헤드라인 {len(comp.get('news_items') or [])}건)")
    try:
        raw = _call_claude(prompt)
    except Exception as e:
        log(d, "polish", f"호출 실패 → 템플릿 유지: {e}")
        return comp
    out = _extract_json(raw)
    if not out:
        log(d, "polish", "JSON 파싱 실패 → 템플릿 유지")
        return comp
    accepted, rejected = 0, []
    first_id, last_id = scenes[0]["id"], scenes[-1]["id"]
    # 스레드 본문(장면 아님) 먼저 처리
    th = (out.get("threads") or "").strip()
    if th:
        lines_th = [x for x in th.splitlines() if x.strip()]
        why = []
        bad_th = forbidden.find_threads(th)
        extra_th = _nums(th) - facts_nums
        if bad_th:
            why.append(f"금지어 {bad_th}")
        if extra_th:
            why.append(f"새 숫자 {sorted(extra_th)[:4]}")
        # 새 형식(2026-09-13): 1줄은 '독자가 이미 본 코스피 숫자', 마지막 줄은 읽는 사람에게 던지는 질문,
        # 본문 전체는 반말이다. 앞선 두 판(첫 줄 숫자 금지 / 마지막 줄 물음표 금지)은 뒤집혔다.
        if not (330 <= len(th) <= 430):
            why.append(f"{len(th)}자 (330~430 밖)")
        if lines_th and not re.search(r"\d", lines_th[0]):
            why.append("첫 줄에 코스피 숫자가 없음")
        if lines_th and not lines_th[-1].rstrip().endswith("?"):
            why.append("마지막 줄이 질문이 아님 — 질문으로 닫는다")
        if lines_th and re.search(r"\d", lines_th[-1]):
            why.append("마지막 줄에 숫자")
        jondae = [x for x in lines_th if not _banmal_tail(x)]
        if jondae:
            why.append(f"반말 종결 아님 {jondae[:2]}")
        if len(re.findall(r"\d[\d,.]*\s?(?:조|억|%)", th)) > 5:
            why.append("숫자 5개 초과")
        if hits := jargon.find(th):
            why.append(f"금융 용어 {hits}")
        if why:
            log(d, "polish", "threads 거절: " + "; ".join(why))
        else:
            comp["threads_text_template"] = comp.get("threads_text")
            comp["threads_text"] = th
    for sc in scenes:
        sid = sc["id"]
        new = (out.get(sid) or "").strip()
        if not new:
            rejected.append((sid, "없음")); continue
        reasons = []
        extra = _nums(new) - facts_nums
        if extra:
            reasons.append(f"새 숫자 {sorted(extra)[:5]}")
        bad = forbidden.find(new)
        if bad:
            reasons.append(f"금지어 {bad}")
        if not _hedge_ok(new):
            reasons.append("원인 문장에 완곡 표지 없음")
        if not _intraday_kept(drafts[sid], new):
            reasons.append("장중→마감 숫자 누락")
        if re.search(r"\d+시\s*\d*분?", new) and sid not in (first_id, last_id) and not re.search(r"\d+시\s*\d*분?", drafts[sid]):
            reasons.append("시각 서술 추가")
        for w in ("오간 뒤", "찍고", "찍은 뒤", "올랐다가", "밀렸다가", "내렸다가"):
            if w in new and w not in drafts[sid]:
                reasons.append(f"순서 암시 '{w}'"); break
        for w in ("간밤", "지난 금요일 밤", "지난 금요일", "전날"):
            if w in drafts[sid] and w not in new and sid not in (first_id, last_id):
                reasons.append(f"시간 표현 '{w}' 누락"); break
        if re.search(r"[一-鿿]", new):
            reasons.append("한자 사용")
        if re.search(r"씨피아이|에프오엠씨|이티에프|에스앤피|이더블유|큐큐큐|피피아이", new):
            reasons.append("약어를 소리나는 대로 풀어 씀")
        norm = lambda x: re.sub(r"[\s,]", "", x)
        if sid == first_id and ed == "kr":
            if norm(new) != norm(drafts[sid]):
                reasons.append("첫 장면은 초안 그대로")
        elif sid == first_id:
            for w in ("나스닥", "샀습니다", "코스피"):
                if w in drafts[sid] and w not in new:
                    reasons.append(f"인트로 핵심 '{w}' 누락"); break
            head = drafts[sid].split("입니다.")[0] + "입니다."
            if not norm(new).startswith(norm(head)):
                reasons.append("첫 문장 불일치")
            if len(new) > 66:
                reasons.append(f"인트로 {len(new)}자 > 66")
        for ph in KEEP_PHRASES:
            if ph in drafts[sid] and ph not in new:
                reasons.append(f"핵심 구절 '{ph}' 누락"); break
        ev = comp.get("event") or {}
        if ev and "간밤 애플이" in drafts[sid]:
            for tok in [t for t in re.split(r"[\s과와·]+", ev.get("spoken") or "") if t]:
                if tok in drafts[sid] and tok not in new:
                    reasons.append(f"이슈 키워드 '{tok}' 누락"); break
        m_rev = re.search(r"갔을까요\? ([^.?!]+?)입니다\.", drafts[sid])
        if m_rev and (m_rev.group(1) + "입니다") not in new:
            reasons.append("테마 공개 문장 누락")
        if sid == last_id and not new.startswith(brand.split(" ")[0]):
            reasons.append("마지막 장면 브랜드 시작 아님")
        if sid == last_id and "매일" in drafts[sid] and ("매일" not in new or "올라" not in new):
            reasons.append("업로드 시각 문장 누락")
        if sid not in (first_id, last_id) and cue not in new and cue in drafts[sid]:
            reasons.append(f"큐워드 '{cue}' 누락")
        limit = len(drafts[sid]) * 1.08 + (40 if sid in ("s1", "u2") else 10)
        if len(new) > limit:
            reasons.append(f"길이 {len(new)} > {int(limit)}")
        if reasons:
            rejected.append((sid, "; ".join(reasons), new[:160])); continue
        sc["tts_template"] = sc["tts"]
        sc["tts"] = new
        if sc.get("sub"):
            sc["sub"] = new
        accepted += 1
    comp["polish"] = {"at": datetime.now().isoformat(timespec="seconds"), "accepted": accepted, "rejected": rejected}
    save_json(computed_path(d, ed), comp)
    log(d, "polish", f"채택 {accepted}/{len(scenes)}" + (f", 거절 {rejected}" if rejected else ""))
    return comp


if __name__ == "__main__":
    polish(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"), sys.argv[2] if len(sys.argv) > 2 else "kr")
