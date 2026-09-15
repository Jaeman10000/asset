"""국장편 v3 'A+ 오늘 누가 샀나' 대본 (2026-09-11 JJ 승인, 형식 토론 메모 기준).

주인공 P = 개인·외국인·기관 중 순매수 절댓값이 가장 큰 주체(동률: 외국인 > 기관 > 개인). 기타법인은 주인공이 아니라 '답'으로 나온다.
장면 순서: s0 훅(주인공 숫자 → 지수 대비 → '그렇다면 누가 샀을까요?') → s2 답(가장 많이 산 쪽 → 나머지 → 오후 2시→마감)
→ s3 '그럼 가장 큰 돈이 빠진 곳은 어디였을까요? {테마}입니다.' → s4 이슈(있는 날만) → s5 '어제 …보자고 했죠' 확인·누적·다음 확인 → s6 끝.
말은 묻고 답하는 사슬로 잇는다(JJ 2026-09-11: 질문으로 궁금증을 만들고 다음 내용으로 자연스럽게, '국장 수급입니다' 같은 꼬리표 금지).
매매 조언 없음. 원인은 말하지 않는다(이 채널의 축은 '왜'가 아니라 '누가'). 다듬기(polish) 없이 이 틀 그대로 읽는다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from narrate import _and, _bat, _won_screen, days_ko, josa, obj, pct, ro, subj, won
import weekend_watch

AFTER_MARKET_NOTICE_UNTIL = "20260918"   # 애프터마켓 안내를 끝에 붙이는 마지막 날(JJ: 이번 주 영상들)


def _ieot(w: str) -> str:
    return w + ('이었습니다.' if _bat(w) else '였습니다.')

NAME_KEY = {"개인": "indiv", "외국인": "foreign", "기관": "inst", "기타법인": "others"}
TAGLINE_V3 = "오늘 국장, 누가 샀나? · 평일 오후 4:30"
HAN_COUNT = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}


def _amt(v: float) -> str:
    """화면용 짧은 금액: 2.5조 / 4,300억 / 9,400억"""
    return won(abs(v)).replace("약 ", "")


def protagonist(inv: dict) -> tuple[str, float]:
    order = ["외국인", "기관", "개인"]
    cands = [(n, inv.get(NAME_KEY[n]) or 0) for n in order]
    return max(cands, key=lambda x: (abs(x[1]), -order.index(x[0])))


def contrast(k: dict, recent: list[dict], p_sold: bool) -> dict:
    """지수 대비 한 문장: 천 단위 선을 지켰다/되찾았다/내줬다, 아니면 등락률."""
    close, prev, low, chg = k.get("close"), k.get("prev_close"), k.get("low"), k.get("chg_pct") or 0.0
    kind, text, short, n_days, line = "pct", "", "", None, None
    if close and prev:
        n_close = int(close // 1000) * 1000
        n_prev = int(prev // 1000) * 1000
        if prev >= n_close and close >= n_close and low is not None and low < n_close:
            kind, line = "held", n_close
            text = f"코스피는 {n_close:,}선을 지켰습니다."
            short = f"{n_close:,}선은 지켰다"
        elif prev < n_close <= close:
            kind, line = "regained", n_close
            hist = [r for r in (recent or []) if r.get("close") is not None]
            hist = sorted(hist, key=lambda r: r["dt"], reverse=True)[1:]
            for i, r in enumerate(hist, start=1):
                if r["close"] >= n_close:
                    n_days = i
                    break
            text = f"코스피는 {n_days}거래일 만에 {n_close:,}선을 되찾았습니다." if n_days else f"코스피는 {n_close:,}선을 되찾았습니다."
            short = f"{n_days}거래일 만에 {n_close:,} 회복" if n_days else f"{n_close:,}선 회복"
        elif close < n_prev <= prev:
            kind, line = "lost", n_prev
            text = f"코스피는 {n_prev:,}선을 내줬습니다."
            short = f"{n_prev:,}선 내줬다"
    if kind == "pct":
        text = f"코스피는 {pct(chg)} {'올랐' if chg > 0 else '내렸'}습니다." if abs(chg) >= 0.05 else "코스피는 거의 제자리였습니다."
        short = f"{abs(chg):.2f}% {'상승' if chg > 0 else '하락'}" if abs(chg) >= 0.05 else "보합"
    idx_down = chg < 0
    opposite = (p_sold and not idx_down) or ((not p_sold) and idx_down)
    if opposite or abs(chg) < 0.5:
        text = "그런데 " + text
    # 훅에서 앞 문장과 이어 붙일 때 쓰는 이음 형태 — "코스피는 7,000선을 내줬고"
    clause = re.sub(r"습니다\.$", "고", text.replace("그런데 ", "", 1))
    return {"kind": kind, "text": text, "clause": clause, "short": short, "line": line, "n_days": n_days, "opposite": opposite}


def _count_ko(n: int) -> str:
    return f"{HAN_COUNT.get(n, str(n))} 번"


WD_KO = "월화수목금토일"


def _was(w: str) -> str:
    """'약 3,500억' → '약 3,500억이었', '약 2.5조' → '약 2.5조였'"""
    return w + ("이었" if _bat(w) else "였")


def _day_word(d: str, other: datetime, past: bool) -> str:
    """d 기준으로 다른 거래일을 부르는 말 — 어제/내일, 아니면 지난 금요일/월요일."""
    base = datetime.strptime(d, "%Y%m%d")
    gap = abs((other - base).days)
    if gap == 1:
        return "어제" if past else "내일"
    return f"지난 {WD_KO[other.weekday()]}요일" if past else f"{WD_KO[other.weekday()]}요일"


def next_trading_day(d: str) -> datetime:
    t = datetime.strptime(d, "%Y%m%d") + timedelta(days=1)
    while t.weekday() >= 5:
        t += timedelta(days=1)
    return t


def callback_v3(cb: dict | None, d: str = "", also: list[str] | None = None, took: bool = False) -> str:
    """'어제 {예고 문장} 보자고 했죠. 결과는 끊겼습니다. 오히려 …' — 전날 영상이 한 약속을 그 문장 그대로 불러온다."""
    if not cb:
        return ""
    chk, ok, t = cb["check"], cb["ok"], cb.get("t")
    kind = chk.get("kind")
    q = (cb.get("q") or "").strip()
    when = "어제"
    if d and cb.get("prev_date"):
        when = _day_word(d, datetime.strptime(cb["prev_date"], "%Y%m%d"), past=True)
    if took:
        # 훅이 이미 약속을 부르고 사실까지 줬다 — 여기서 또 부르면 메아리가 된다. 확인만 짧게 하고 뜻으로 넘어간다.
        n = chk.get("n")
        hit = f"오늘 그 {days_ko(n)}가 채워졌습니다." if (ok and n) else ("오늘도 이어졌습니다." if ok else "오늘은 끊겼습니다.")
        return (f"{_and(list(also))}도 같은 걸 짚었는데, {hit}" if also else hit)
    if also and q.endswith("는지"):
        # 금요일 편과 주말편이 같은 걸 짚었으면 한 문장으로 합친다 — 따로 말하면 목록이 된다
        head = f"{when}에도, {_and(list(also))}에서도 {q} 보자고 했죠."
    elif q.endswith("는지"):
        head = f"{when} {q} 보자고 했죠."
    else:
        head = f"{when} 확인하기로 한 것이 있었죠."
    if kind == "theme_continue":
        if ok:
            return f"{head} 오늘도 {subj(won(t))} 들어오며 이어졌습니다."
        return f"{head} 오늘은 끊겼습니다." if not (t is not None and t < 0) else f"{head} 오늘은 끊기고, 오히려 {subj(won(abs(t)))} 빠졌습니다."
    if kind == "inv_continue":
        word = "순매수" if chk["sign"] > 0 else "순매도"
        opp = "순매도" if chk["sign"] > 0 else "순매수"
        if ok:
            return f"{head} 오늘도 {obj(won(abs(t)))} {word}하며 이어졌습니다."
        return f"{head} 오늘은 끊겼습니다." if not t else f"{head} 오늘은 끊기고, 오히려 {obj(won(abs(t)))} {opp}했습니다."
    if kind == "theme_sell_stop":
        return f"{head} " + (f"순매도는 멈췄습니다." + (f" 오히려 {subj(won(t))} 들어왔습니다." if t and t > 0 else "") if ok else "순매도는 오늘도 이어졌습니다.")
    if kind == "theme_sell_cont":
        return f"{head} " + ("순매도는 오늘도 이어졌습니다." if ok else "순매도는 멈췄습니다.")
    if kind == "kosdaq_break":
        return f"{head} " + ("결과는 끊겼습니다." if ok else "오늘도 이어졌습니다.")
    return ""


def record_line(stats: dict | None) -> str:
    if not stats or not stats.get("n"):
        return ""
    n, k = stats["n"], stats["k"]
    if k == 0:
        return f"지금까지 {_count_ko(n)} 확인했고, {'한 번 끊겼습니다' if n == 1 else _count_ko(n).replace(' 번', ' 번 다') + ' 끊겼습니다'}."
    if k == n:
        return f"지금까지 {_count_ko(n)} 확인했고, {'한 번 이어졌습니다' if n == 1 else _count_ko(n).replace(' 번', ' 번 다') + ' 이어졌습니다'}."
    return f"지금까지 {_count_ko(n)} 확인했고, {_count_ko(k)} 이어졌습니다."


def _active_buybacks(d: str, programs: list[dict]) -> dict:
    iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return {p["code"]: p for p in programs or [] if p.get("from", "") <= iso <= p.get("to", "9999")}


def _others_top(c: dict) -> list[dict]:
    """그날 기타법인 순매수 상위 2종목(억) + 자사주 매입 진행 여부 — 화면용."""
    act = _active_buybacks(c["date"], c.get("buybacks") or [])
    return [{"name": x["name"], "v": x["v"], "buyback": x["code"] in act} for x in (c.get("top_others") or [])[:2] if x.get("v", 0) > 0]


def _said_recently(d: str, needle: str, n: int = 3) -> bool:
    """최근 n편 대사에 이 말이 있었으면 True — 용어 설명을 매일 되풀이하지 않는다(JJ 2026-09-14)."""
    from _common import DATA, load_json
    if not d:
        return False
    cur, seen = datetime.strptime(d, "%Y%m%d"), 0
    for k in range(1, 15):
        c = load_json(DATA / (cur - timedelta(days=k)).strftime("%Y%m%d") / "computed_kr.json")
        if not c:
            continue
        if any(needle in (x.get("tts") or "") for x in c.get("scenes") or []):
            return True
        seen += 1
        if seen >= n:
            break
    return False


def _others_link(c: dict, v0: float, lead: str = "이 가운데", d: str = "") -> list[str]:
    """기타법인이 답인 날: 어느 종목을 샀는지(키움 종목별 합산) → 자사주 매입과 연결(진행 중인 매입이 기사로 확인된 종목만).
    데이터가 없으면 한계 문장. 연결은 '가능성이 큽니다'로만(단정 금지)."""
    top = [x for x in (c.get("top_others") or []) if x.get("v", 0) > 0][:2]
    act = _active_buybacks(c["date"], c.get("buybacks") or [])
    buy = v0 > 0
    if not top:
        if act and buy:
            names = _and([p["name"] for p in act.values()])
            return [f"회사가 자기 주식을 사면 기타법인으로 잡히는데, 지금 {names}가 자사주를 사들이는 중이라 그 몫이 섞였을 수 있습니다."]
        return [f"다만 일반 회사들의 거래를 묶은 숫자라, 어느 회사가 {'샀' if buy else '팔았'}는지는 알 수 없습니다."]
    share = sum(x["v"] for x in top) / abs(v0) if v0 else 0
    if len(top) == 2:
        # 두 종목이 대부분이면 금액 나열 대신 비중 한 마디가 더 빨리 이해된다(숫자 줄이기).
        if share >= 0.8:
            out = [f"{lead} {round(share * 100)}%는 {top[0]['name']}와 {top[1]['name']}였습니다."]
        else:
            out = [f"{lead} {won(top[0]['v'])}{'은' if _bat(won(top[0]['v'])) else '는'} {top[0]['name']}, {won(top[1]['v'])}{'은' if _bat(won(top[1]['v'])) else '는'} {top[1]['name']}였습니다."]
    else:
        out = [f"{lead} {won(top[0]['v'])}{'이' if _bat(won(top[0]['v'])) else '가'} {top[0]['name']}였습니다."]
    inb = [x for x in top if x["code"] in act]
    if buy and inb:
        who = "두 회사 모두" if len(inb) == 2 else f"{inb[0]['name']}{'은' if _bat(inb[0]['name']) else '는'}"
        # 정의 한 줄 + 재정의 한 줄이면 끝난다. 같은 말을 세 문장으로 늘리면 길이 예산만 먹는다.
        if not _said_recently(d, "자사주"):                  # 최근 3편에 자사주 얘기를 했으면 용어 설명은 뺀다(JJ 2026-09-14)
            out.append("회사가 자기 주식을 사면 기타법인으로 잡힙니다.")
        if share >= 0.6 and len(inb) == len(top):
            out.append(f"바깥에서 새 돈이 들어온 게 아니라, {who} 자사주를 사들인 겁니다.")
        else:
            out.append(f"{who} 지금 자사주를 사들이는 중이라, 이 순매수에는 자사주 매입이 섞인 것으로 보입니다.")
    return out


def _record_meaning(stats: dict | None) -> list[str]:
    """누적 기록이 무슨 뜻인지 한 줄(가능성으로만). 두 번 이상 확인했을 때만."""
    if not stats or (stats.get("n") or 0) < 2:
        return []
    n, k = stats["n"], stats["k"]
    kinds = stats.get("kinds") or []
    theme_only = bool(kinds) and all(x == "theme_continue" for x in kinds)
    if k == 0:
        return (["한 테마에 들어온 돈이 오래 머물지 않았다는 뜻입니다. 요즘은 돈이 테마를 옮겨 다니는 장일 수 있습니다."] if theme_only
                else ["돈의 흐름이 오래 이어지지 않았다는 뜻입니다. 요즘은 방향이 자주 바뀌는 장일 수 있습니다."])
    if k == n:
        return ["한번 들어온 돈이 머물고 있다는 뜻입니다. 흐름이 쉽게 바뀌지 않는 장일 수 있습니다."]
    return ["이어진 날과 끊긴 날이 섞여 있어, 아직 한쪽으로 보긴 이릅니다."]



def _mult_ko(x: float) -> str:
    """배수 앵커 — 숫자 하나로 크기를 전하는 가장 싼 방법(SCRIPT_PLAYBOOK 5-4). 2배 미만이면 쓰지 않는다."""
    if x < 1.8:
        return ""
    if x >= 9.5:
        return "열 배 가까이"
    n = round(x)
    return f"{['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉'][n]} 배가"


def _round_won(v: float) -> str:
    """화면 카드의 정확한 숫자와 충돌하지 않게 말로는 경계값으로 — 4,651억 → '5천억이 안 됐습니다'.
    1천억 미만은 경계값이 되레 부풀려 들리므로(300억을 '1천억이 안 됐다'고 하면 속이는 말이다) 금액을 그대로 말한다."""
    if v < 1000 or v >= 10000:
        return f"{_was(won(v))}습니다"
    up = (int(v // 1000) + 1) * 1000
    return f"{up // 1000}천억이 안 됐습니다" if up <= 9000 else f"{_was(won(v))}습니다"


def _why_check(cb: dict | None) -> list[str]:
    """왜 이어지는지를 보는가 + 며칠째부터 흐름으로 보는가. 판단은 시청자가 한다 — 매수·매도 권유는 하지 않는다."""
    if not cb:
        return []
    chk = cb.get("check") or {}
    kind, n = chk.get("kind"), chk.get("n") or 0
    if kind not in ("theme_continue", "inv_continue"):
        return []
    # 업종 약속이면 '그 업종에', 주체 약속이면 '그 주체가' — where 를 만들어 놓고 문장에 안 쓰던 버그(2026-09-14).
    # 외국인이 나흘째 파는지를 확인하면서 "그 업종에 돈이 자리를 잡는지"라고 말하면 회수 장면의 신뢰가 깎인다.
    if kind == "theme_continue":
        why = f"이어지는지 보는 건 그 업종에 돈이 자리를 잡는지 보려는 겁니다."
    else:
        who = chk.get("name") or "그 주체"
        way = "파는" if (chk.get("sign") or -1) < 0 else "사는"
        why = f"이어지는지 보는 건 {who}이 {way} 게 하루 사정인지, 방향을 잡은 건지 가리려는 겁니다."
    # 같은 두 문장을 매일 읽으면 AI 티가 난다(9/14·9/15 가 토씨 하나 빼고 같았다). n 으로 세 벌을 돌린다.
    v = n % 3
    if v == 1:
        out = [f"{who if kind != 'theme_continue' else '한 업종'}{'이' if kind != 'theme_continue' else '에'} {('파는' if (chk.get('sign') or -1) < 0 else '사는') if kind != 'theme_continue' else '돈이 오는'} 게 어느 하루의 사정이면 다음 날 끊깁니다. 그래서 며칠째인지를 셉니다."]
    elif v == 2:
        out = ["하루치 숫자는 이유가 백 가지라 방향을 말해 주지 않습니다. 며칠째인지가 방향을 말해 줍니다."]   # why 문장은 어제와 글자까지 같아서 뺀다
    else:
        out = [f"하루 수급은 그날 사정일 수 있어서, {why[0].lower() + why[1:] if why[:1].isascii() else why}"]
    if n <= 2:
        out.append("이틀은 아직 이릅니다. 사흘째까지 이어지면 그때 자리를 잡는 쪽으로 볼 수 있습니다.")
    elif v == 1:
        out.append(f"{days_ko(n)}면 어느 하루의 사정이 아니라 방향입니다.")
    elif v == 2:
        out.append(f"{days_ko(n)}까지 왔으면 우연이라고 부르기는 어렵습니다.")
    else:
        out.append(f"{days_ko(n)} 이어졌다면 하루 사정으로 보기는 어렵습니다.")
    return out


# 지난 편 약속을 훅에서 쓸 수 있게 사람 말로 푼다.
# 저장된 형태("외국인 순매도가 나흘째 이어지는지")는 장부용이라 그대로 읽으면 딱딱하다.
# check 에 구조가 남아 있으므로 문자열을 정규식으로 뜯지 않고 거기서 만든다.
def _q_spoken(cb: dict | None) -> str:
    chk = (cb or {}).get("check") or {}
    kind, n = chk.get("kind"), chk.get("n")
    dk = days_ko(n) if n else ""
    if kind == "inv_continue":
        who = chk.get("name") or ""
        act = "파는지" if (chk.get("sign") or -1) < 0 else "사는지"
        return " ".join(x for x in (subj(who), dk, act) if x)
    if kind == "theme_continue":
        th = chk.get("theme") or ""
        return " ".join(x for x in (f"{th}에", dk, "돈이 들어오는지") if x)
    if kind == "theme_sell_stop":
        return f"{chk.get('theme') or ''}에서 돈 빠지는 게 멈추는지".strip()
    if kind == "theme_sell_cont":
        return f"{chk.get('theme') or ''}에서 돈이 계속 빠지는지".strip()
    if kind == "kosdaq_break":
        return f"코스닥 {chk.get('n') or ''}일 연속 하락이 끊기는지".strip()
    return ""


def _q_noun(cb: dict | None) -> str:
    """다리 문장에서 쓰는 명사구. "외국인 순매도" / "금융 순매수" / "반도체 순매도"."""
    chk = (cb or {}).get("check") or {}
    kind = chk.get("kind")
    if kind == "inv_continue":
        return f"{chk.get('name') or ''} {'순매도' if (chk.get('sign') or -1) < 0 else '순매수'}".strip()
    if kind in ("theme_continue",):
        return f"{chk.get('theme') or ''} 순매수".strip()
    if kind in ("theme_sell_stop", "theme_sell_cont"):
        return f"{chk.get('theme') or ''} 순매도".strip()
    return ""


# ⓘ 훅 — 플레이북 §4-2 의 첫 문장 유형 H01~H06 을 그대로 쓴다.
#    §4-1 절대 수치: 첫 물음표 ≤36자, 훅 질문 정확히 1개, 훅 숫자 2개(첫 문장 1개).
#    최근 3편에서 쓴 유형은 뺀다(§4-2). 고른 유형은 hook_id 로 남긴다.
def _skeleton(x: str) -> str:
    """문장 뼈대. 숫자·주체·업종을 지우고 남는 모양으로 비교한다 —
    id 가 같아서가 아니라 '같은 소리로 들리면' 쓰지 않는다(JJ 2026-09-14)."""
    x = re.sub(r"약\s?", "", x or "")
    x = re.sub(r"\d[\d,.]*\s?(조|천억|억|%|선|포인트|배|거래일)?", "N", x)
    for g in ("기타법인", "외국인", "기관", "개인"):
        x = x.replace(g, "G")
    x = re.sub(r"(하루|이틀|사흘|나흘|닷새)(째)?", "D", x)
    return re.sub(r"\s+", "", x)


def _recent_s0(d: str, n: int = 3) -> list[str]:
    """최근 편들의 첫 문장 원문. hook_id 가 없던 시절 편도 이걸로 걸러진다."""
    from _common import DATA, load_json
    cur, out = datetime.strptime(d, "%Y%m%d"), []
    for i in range(1, 15):
        day = (cur - timedelta(days=i)).strftime("%Y%m%d")
        # 같은 날 여러 판(20260911_v8 처럼 접미사가 붙은 폴더)도 본다 — 9/11 은 그런 폴더에만 남아 있어서
        # 금요일 훅("…누가 받았을까요?")을 못 거르고 9/15 에 그대로 다시 골랐다.
        found = False
        for folder in sorted(DATA.glob(day + "*"), reverse=True):
            c = load_json(folder / "computed_kr.json")
            if not c:
                continue
            t = next((x.get("tts") for x in (c.get("scenes") or []) if x.get("id") == "s0"), "")
            if t and t not in out:
                out.append(t)
                found = True
        if found and len(out) >= n:
            break
    return out


def _hook_candidates(P: str, amt_bare: str, sold: bool, ct: dict, cb: dict | None,
                     opp_name: str, opp_amt: str, others_big: bool, ask: str,
                     intraday_gap: tuple[str, str] | None = None) -> list[tuple[str, str]]:
    """[(hook_id, 훅 문장)] — 그날 조건에 맞는 것만."""
    got, gave = ("받았을까요", "내놓은") if sold else ("팔았을까요", "사들인")
    ctp = (ct.get("text") or "").replace("그런데 ", "", 1)
    out: list[tuple[str, str]] = []
    # H01 빈칸 질문 — 기본형. 첫 물음표가 가장 빨리 온다
    out.append(("H01", f"오늘 {subj(P)} {gave} {amt_bare}, 누가 {got}?"))
    # H04 반전 — 지수와 수급 방향이 어긋난 날
    if ct.get("opposite"):
        out.append(("H04", f"{ctp} 그런데 {josa(P)} {obj(amt_bare)} {'팔았습니다' if sold else '샀습니다'}. {ask}"))
    # H02 비대칭 — 두 주체가 정반대로 갔을 때
    if opp_name and opp_amt:
        out.append(("H02", f"{subj(opp_name)} {opp_amt} {'사는' if sold else '파는'} 동안 "
                           f"{josa(P)} {obj(amt_bare)} {'팔았습니다' if sold else '샀습니다'}. {ask}"))
    # H03 어제 예고 연속 — 주 1~2회. 결과가 선명한 날만
    if cb and cb.get("check") and cb.get("ok") is not None:
        q = _q_spoken(cb)
        if q:
            out.append(("H03", f"지난 편에서 {q} 보겠다고 했습니다. 오늘 답이 나왔습니다. {ask}"))
    # H07 시간 반전 — 오후 2시와 마감이 크게 갈린 날(플레이북 §5-3 T02)
    if intraday_gap:
        _ask2 = "그럼 이 물량을 오늘 누가 샀을까요?" if sold else "그럼 이 물량을 오늘 누가 팔았을까요?"
        out.append(("H07", f"{josa(P)} 오후 2시까지 {intraday_gap[0]} {'팔지' if sold else '사지'} 않았습니다. "
                           f"그런데 마지막 한 시간 반에 {intraday_gap[1].replace('가', '인')} {obj(amt_bare)} {'팔았습니다' if sold else '샀습니다'}. {_ask2}"))
    # H06 완충 단정 — 기타법인이 그날 크게 받아 낸 날(자사주 연결)
    if others_big:
        out.append(("H06", f"오늘 {subj(P)} {gave} {amt_bare}, 받아 낸 쪽에 기타법인이 있었습니다. {ask}"))
    return out


def _pick_hook(d: str, cands: list[tuple[str, str]]) -> tuple[str, str]:
    # 최근 편의 첫 문장과 '뼈대가 같은' 후보는 뺀다. 숫자만 바꾼 같은 문장이 제일 큰 AI 티다.
    recent = _recent_s0(d)
    seen = {_skeleton(x) for t in recent for x in re.split(r"(?<=[.?!])\s+", t) if x.strip()}
    tails = {re.sub(r"\s+", "", t)[-7:] for t in recent if t}          # 끝맺음이 같으면 같은 소리로 들린다
    heads = {_skeleton(re.split(r"(?<=[.?!])\s+", t)[0])[:14] for t in recent if t}
    def clash(x: str) -> bool:
        parts = [y for y in re.split(r"(?<=[.?!])\s+", x) if y.strip()]
        if any(_skeleton(y) in seen for y in parts):
            return True
        if re.sub(r"\s+", "", x)[-7:] in tails:
            return True
        return _skeleton(parts[0])[:14] in heads if parts else False
    fresh = [x for x in cands if not clash(x[1])]
    pool = fresh or cands
    rare = [x for x in pool if x[0] in ("H03", "H06")]
    plain = [x for x in pool if x[0] not in ("H03", "H06")]
    pool = plain or rare
    return pool[int(d[-2:]) % len(pool)]


# ⓘ 전환 장치 — 플레이북 §5-3. 같은 자리를 매일 같은 문장으로 열면 그게 AI 티다.
#    JJ 2026-09-14: "그냥 금요일에 썼던 형식을 쓰지 말라고."
#    최근 3편에 쓴 id 는 빼고 고른다. 쓴 id 는 devices 로 남긴다.
def _recent_devices(d: str, n: int = 3) -> set[str]:
    from _common import DATA, load_json
    cur, out, seen = datetime.strptime(d, "%Y%m%d"), set(), 0
    for i in range(1, 15):
        c = load_json(DATA / (cur - timedelta(days=i)).strftime("%Y%m%d") / "computed_kr.json")
        if c and c.get("devices"):
            out |= set(c["devices"])
            seen += 1
            if seen >= n:
                break
    return out


def _pick_device(d: str, used: set[str], recent: set[str], cands: list[tuple[str, str]]) -> tuple[str, str]:
    fresh = [x for x in cands if x[0] not in recent and x[0] not in used] or             [x for x in cands if x[0] not in used] or cands
    pick = fresh[int(d[-2:]) % len(fresh)]
    used.add(pick[0])
    return pick


# ⓘ 조심할 것 — JJ 2026-09-14: "그러면 투자자들은 어떤걸 조심해야할까? 어떻게 행동을 해야할까?"
#    '어떻게 행동하라'는 우리가 못 한다(가진 건 수급 며칠치뿐이다). 대신 '무엇을 잘못 읽기 쉬운가'까지 간다.
#    후보 12개를 금지선 기준으로 적대 검증해 8개가 통과했고, 그중 JJ가 고른 한 줄이다.
#    끝을 '다른 숫자입니다'로 둔 이유: 바로 뒤 ⑤가 "…이어지는지입니다"라 어미가 겹치면 기계 티가 난다.
def _caution(d: str, P: str, sold: bool, inv: dict, streak: dict) -> str:
    if not sold:
        return ""                                   # 주인공이 산 날엔 이 문장이 성립하지 않는다
    st = (streak.get(NAME_KEY[P]) or {}).get("streak") or 0
    if st >= 0 or abs(st) < 2:
        return ""                                   # 판 쪽이 이틀 이상 이어진 날에만
    buyers = [(n, inv.get(k)) for n, k in NAME_KEY.items() if (inv.get(k) or 0) > 0]
    if not buyers:
        return ""
    top = max(buyers, key=lambda x: x[1])
    if top[0] == P:
        return ""
    if _used_recently(d, "caution_id", "C1", 3):     # 조건이 며칠 연달아 참일 수 있다 — 주 1~2회로 묶는다
        return ""
    return f"오늘 {top[0]} 순매수가 가장 컸어도 {P} 순매도가 멈춘 건 아니었고, 하루 크기와 며칠째는 다른 숫자입니다."


def _used_recently(d: str, key: str, val: str, n: int) -> bool:
    from _common import DATA, load_json
    cur = datetime.strptime(d, "%Y%m%d")
    for i in range(1, n * 3):
        c = load_json(DATA / (cur - timedelta(days=i)).strftime("%Y%m%d") / "computed_kr.json")
        if c and c.get(key):
            if c[key] == val:
                return True
            n -= 1
            if n <= 0:
                return False
    return False


# ⓘ 다리 — 장면이 끝날 때 다음을 궁금하게 만드는 한 줄. 지금까지 s3 는 답만 하고 닫혀 있어
#    거기서 사슬이 끊겼다(2026-09-14 점검). 예측을 시키지 않는다 — 우리가 한 약속으로 넘긴다.
# 대명사로 부르지 않는다 — "우리가 보자고 한 건"은 처음 본 사람에게 빈칸이다.
def _bridge_cb(when: str, noun: str) -> list[str]:
    at = when if when in ("어제", "오늘", "그제", "내일") else f"{when}에"   # '어제에'는 틀린 말(2026-09-15)
    return [f"그럼 {at} 보자고 한 {noun}는 어떻게 됐을까요?",
            f"그럼 {at} 확인하기로 한 {noun}는 오늘 어떻게 됐을까요?"]


# 훅이 이미 사실을 회수한 날은 같은 질문을 두 번 울리지 않는다 — 판단 기준 쪽으로 넘긴다
BRIDGE_TOOK = [
    "그럼 이 흐름, 어디까지 봐야 방향을 잡았다고 할 수 있을까요?",
    "그럼 며칠째까지 이어져야 하루 사정이 아니라고 볼 수 있을까요?",
]
BRIDGE_NO = [
    "그럼 이 돈은 오늘 하루짜리였을까요?",
    "그럼 이건 오늘만의 일이었을까요?",
    "그럼 이 흐름, 오늘로 끝일까요?",
]


def _bridge(d: str, cb: dict | None, when: str = "", took: bool = False) -> str:
    noun = _q_noun(cb)
    if cb and noun and when:
        bank = BRIDGE_TOOK if took else _bridge_cb(when, noun)
    elif cb:
        bank = BRIDGE_TOOK
    else:
        bank = BRIDGE_NO
    return bank[int(d[-2:]) % len(bank)]


# ② 시청자에게 던지는 질문 — 끝 멘트는 고정이라 그 앞에 둔다. 날짜를 씨앗으로 돌려 매일 같은 문장이 되지 않게.
#    예측을 시키지 않는다("어디로 갈까요" 금지). 오늘 숫자를 어떻게 읽었는지만 묻는다.
ASK_VIEWER = [
    "오늘 이 돈의 움직임, 여러분은 어떻게 보셨습니까? 댓글로 남겨 주세요.",
    "{th}에서 빠진 이 돈, 여러분은 어떻게 읽으셨습니까? 댓글에 적어 주세요.",
    "오늘 숫자에서 가장 이상했던 건 무엇이었습니까? 댓글로 알려 주세요.",
    "{P}의 오늘 움직임, 여러분은 어떻게 보셨습니까? 댓글로 남겨 주세요.",
    "여러분이라면 {when} 무엇을 먼저 보시겠습니까? 댓글로 남겨 주세요.",
    "오늘 여러분 눈에 걸린 숫자는 무엇이었습니까? 댓글로 알려 주세요.",
]
# ③ 좋아요 — 지금까지 아예 요청하지 않았다. 구독 동기(내일 답)는 그대로 두고 좋아요를 붙인다.
LIKE_SUB = [
    "그 답이 궁금하면 구독, 오늘 도움이 되셨다면 좋아요 눌러 주세요.",
    "답이 궁금하면 구독, 도움이 되셨다면 좋아요 눌러 주세요.",
    "내일 답을 같이 보시려면 구독, 오늘 도움이 되셨다면 좋아요 부탁드립니다.",
]


def _ask_viewer(d: str, P: str, th: str | None, when: str) -> str:
    """그날 이야기에 붙은 질문 하나. th가 없으면 테마를 쓰는 변형은 건너뛴다."""
    n = datetime.strptime(d, "%Y%m%d").toordinal()
    cand = [x for x in ASK_VIEWER if "{th}" not in x or th]
    return cand[n % len(cand)].format(P=P, th=th or "", when=when)


def _like_sub(d: str) -> str:
    return LIKE_SUB[datetime.strptime(d, "%Y%m%d").toordinal() % len(LIKE_SUB)]


def build_aplus(c: dict) -> dict:
    brand = c.get("brand") or "누가샀나"
    d = c["date"]
    k = c["kospi"]
    inv = c.get("inv") or {}
    streak = c.get("inv_streak") or {}
    it = c.get("intraday") or {}
    moves = c.get("moves") or []
    ev = c.get("event") or {}
    prev_inv = c.get("prev_inv") or {}

    P, amount = protagonist(inv)
    sold = amount < 0
    ct = contrast(k, c.get("recent_closes") or [], sold)
    line1 = f"{P} {_amt(amount)} {'순매도' if sold else '순매수'}"
    line2 = "그럼 누가 샀나?" if sold else "그럼 누가 팔았나?"

    # s0: 주인공 숫자 → 지수 대비 → 질문(첫 화면 둘째 줄과 같은 질문을 소리로)
    ask = "그럼 오늘 누가 샀을까요?" if sold else "그럼 오늘 누가 팔았을까요?"   # '오늘'을 넣어 그날의 이야기임을 못 박는다(JJ 2026-09-13)
    # 첫 물음표는 5초 안쪽(SCRIPT_PLAYBOOK 4-1). '약'과 '순매도했습니다'를 빼 앞 두 문장을 40자 밑으로 줄인다.
    _dev_used: set[str] = set()
    _dev_recent = _recent_devices(d)
    _cb = c.get("callback")
    _amt_bare = won(abs(amount)).replace("약 ", "")
    # 반대 방향으로 간 가장 큰 주체(H02 조건)
    _others = [(n, inv.get(k)) for n, k in NAME_KEY.items() if n != P and n != "기타법인" and inv.get(k) is not None]
    # 주인공과 반대로 간 주체: 주인공이 팔았으면 산 쪽(v>0), 샀으면 판 쪽(v<0)
    _opp = max([(n, v) for n, v in _others if (v > 0) == sold and abs(v) >= 3000], key=lambda x: abs(x[1]), default=(None, None))
    _opp_amt = obj(won(abs(_opp[1])).replace("약 ", "")) if _opp[0] else ""
    _others_big = (inv.get("others") or 0) >= 8000
    # H07 재료: 오후 2시 잠정치와 마감이 크게 갈린 날(같은 방향으로 3배 이상 불었을 때)
    _snap = ((c.get("intraday") or {}).get("snap") or {}).get(NAME_KEY[P])
    _gap = None
    if _snap is not None and (_snap < 0) == sold and abs(_snap) >= 100 and abs(amount) >= 3 * abs(_snap):
        _gap = (won(abs(_snap)).replace("약 ", "") + "도", _mult_ko(abs(amount - _snap) / abs(_snap)))
    hook_id, s0 = _pick_hook(d, _hook_candidates(P, _amt_bare, sold, ct, _cb,
                                                 _opp[0] or "", _opp_amt, _others_big, ask, _gap))
    # 손으로 쓴 훅(data/D/hook.txt)이 있으면 그걸 쓴다 — 자동 후보가 전부 최근 편과 같은 소리일 때(2026-09-15).
    # S0V4 는 큐 순서(주체·금액 → 지수 등락 → '?' 문장)로 화면을 넘기니, 그 순서로 쓴다.
    from _common import DATA as _DATA
    _ov = _DATA / d / "hook.txt"
    if _ov.exists() and _ov.read_text(encoding="utf-8").strip():
        hook_id, s0 = "H99", " ".join(_ov.read_text(encoding="utf-8").split())
    _took = hook_id == "H03"

    # s2: 답 — 가장 많이 산(판) 쪽 → 나머지 → 같은 편 → 오후 2시→마감
    parties = [(n, inv.get(key)) for n, key in NAME_KEY.items() if n != P and inv.get(key) is not None]
    opp = sorted([(n, v) for n, v in parties if (v > 0) == sold and abs(v) >= 300], key=lambda x: -abs(x[1]))
    same = [(n, v) for n, v in parties if (v < 0) == sold and abs(v) >= 1000]
    word_opp = "순매수" if sold else "순매도"
    verb_opp = "산" if sold else "판"
    parts2 = []

    def _st(n: str, v: float) -> int:
        st = (streak.get(NAME_KEY[n]) or {}).get("streak") or 0
        return abs(st) if n in ("외국인", "기관") and abs(st) >= 2 and (st > 0) == (v > 0) else 0

    # ① 답 공개: '가장 많이 산 쪽은 기관도, 개인도 아니었습니다. 기타법인입니다.' — 화면이 '{이름}입니다'에서 이름을 크게 띄운다
    ans = opp[0][0] if opp else None
    prev_ans = None
    if opp:
        n0, v0 = opp[0]
        if n0 == "기타법인":
            parts2.append(f"가장 많이 {verb_opp} 쪽은 기타법인입니다.")   # 뜸 들이는 문장 없이 바로 답(질문 뒤 약 10초)
            pv = prev_inv.get("others")
            if pv is not None and (pv > 0) == (v0 > 0) and abs(pv) >= 3000:
                parts2.append(f"{obj(won(abs(v0)))} {word_opp}했고, 전날에도 {obj(won(abs(pv)))} {'샀' if v0 > 0 else '팔았'}습니다.")
                prev_ans = pv
            else:
                parts2.append(f"{obj(won(abs(v0)))} {'샀' if v0 > 0 else '팔았'}습니다.")
            parts2 += _others_link(c, v0, d=d)
        else:
            _rest = [x for x, _ in same[:1]] + [x for x, _ in opp[1:2] if x != "기타법인"]   # 반대로 간 주체부터
            _cands = [("D01", f"가장 많이 {verb_opp} 쪽은 {n0}입니다."),
                      ("T08", f"그럼 이 물량을 받아 간 곳은 어디였을까요? {n0}입니다." if sold
                              else f"그럼 이 물량을 내놓은 곳은 어디였을까요? {n0}입니다."),
                      ("T09", f"{josa(_rest[0])} 아니었습니다. {n0}입니다." if _rest else f"{n0}입니다.")]
            _id, _line = _pick_device(d, _dev_used, _dev_recent, _cands)
            parts2.append(_line)
            st0 = _st(n0, v0)
            parts2.append(f"{obj(won(abs(v0)))} {word_opp}해, {days_ko(st0)} {'사들였' if v0 > 0 else '팔았'}습니다." if st0
                          else f"{obj(won(abs(v0)))} {'샀' if v0 > 0 else '팔았'}습니다.")
    # ② 주인공의 오후 2시(잠정) → 마감: 질문으로 궁금증을 한 번 더 → 두 시점 숫자(중간 경로는 말하지 않음)
    snap = (it.get("snap") or {})
    a = snap.get(NAME_KEY[P])
    intraday_line, counter_mark = "", None
    P_eun = P + ("은" if _bat(P) else "는")
    word_P = "순매도" if sold else "순매수"
    verb_P = "팔았" if sold else "샀"
    if hook_id != "H07" and a is not None and abs(a) >= 100 and abs(amount - a) >= 1000 and ((a < 0) == (amount < 0) or abs(a) >= 300):
        if (a < 0) == (amount < 0):
            grew = abs(amount) > abs(a)
            if grew and abs(a) <= 0.6 * abs(amount):
                # 배수 앵커(편당 1~2회) + 'A가 아니라 B' 재정의. 막판 물량이 오후 2시까지의 몇 배인지가 이 장면의 핵심.
                x = abs(amount - a) / abs(a) if a else 0
                mult = _mult_ko(x)
                tail = (f"마지막 한 시간 반에 {mult} 더 나왔습니다. 하루 종일 흘러나온 게 아니라, 장 막판에 몰린 겁니다."
                        if mult else f"마감까지 {subj(won(abs(amount - a)))} 더 늘었습니다. 하루 종일 흘러나온 게 아니라, 장 후반에 몰린 겁니다.")
                intraday_line = (f"그런데 {P_eun} 하루 내내 {verb_P}을까요? "
                                 f"오후 2시까진 {_round_won(abs(a))}. {tail}")
            elif grew:
                intraday_line = (f"그런데 {P_eun} 언제 이렇게 많이 {verb_P}을까요? "
                                 f"오후 2시에 이미 {_was(won(abs(a)))}고, 마감까지 {subj(won(abs(amount - a)))} 더 늘었습니다.")
            else:
                intraday_line = (f"그런데 {P_eun} 마감까지 계속 {verb_P}을까요? "
                                 f"오후 2시엔 {word_P}가 {_was(won(abs(a)))}는데, 마감엔 {ro(won(abs(amount)))} 줄었습니다.")
            counter_mark = "오후 2시"
        else:
            intraday_line = (f"그런데 {P_eun} 처음부터 {verb_P}을까요? 오후 2시만 해도 {obj(won(abs(a)))} "
                             f"{'순매수' if a > 0 else '순매도'}하고 있었습니다. 마감엔 {word_P}로 돌아섰습니다.")
            counter_mark = "마감엔 " + word_P[:2]      # 방향이 바뀐 날은 '마감엔 …로 돌아섰습니다'에서 카운터
    # 그 사이 돌아선 주체: 주인공 쪽으로 돌아선 주체는 마감 금액까지 한 문장에, 반대쪽은 '반대로 …' 다음 '마감엔 …'
    p_sign = -1 if sold else 1
    p_side, opp_side = [], []
    if intraday_line:
        for t in (it.get("turns") or []):
            if t.get("kind") == "flip" and t.get("name") != P and t.get("name") in NAME_KEY:
                (p_side if (t.get("b") or 0) * p_sign > 0 else opp_side).append(t["name"])
    flip_sents = []
    if p_side:
        vals = [abs(inv.get(NAME_KEY[n]) or 0) for n in p_side]
        amt_txt = obj(won(vals[0])) if len(vals) == 1 else "각각 " + ", ".join(won(v) for v in vals[:-1]) + ", " + obj(won(vals[-1]))
        frm, to = ("사는 쪽", "파는 쪽") if sold else ("파는 쪽", "사는 쪽")
        flip_sents.append(f"그 사이 {josa(_and(p_side))} {frm}에서 {to}으로 돌아서, 마감엔 {amt_txt} {word_P}했습니다.")
    if opp_side:
        frm, to = ("파는 쪽", "사는 쪽") if sold else ("사는 쪽", "파는 쪽")
        flip_sents.append(f"{'반대로' if p_side else '그 사이'} {josa(_and(opp_side))} {frm}에서 {to}으로 돌아섰습니다.")
    if intraday_line:
        parts2.append(intraday_line)
    parts2 += flip_sents
    # ③ 나머지 받은 쪽: 돌아선 주체가 먼저 '마감엔 …', 아니면 오후 2시 이야기 뒤라 '{답} 다음으로 많이 산 쪽은 …'으로 다시 잡는다
    same = sorted([x for x in same if x[0] not in p_side], key=lambda x: -abs(x[1]))
    rest = sorted(opp[1:], key=lambda x: x[0] not in opp_side)
    bits = []
    for i, (n, v) in enumerate(rest):
        stn = _st(n, v)
        tail = f"{word_opp}해 {days_ko(stn)} {'사들였' if v > 0 else '팔았'}" if stn else ('샀' if v > 0 else '팔았')
        if i == 0 and n in opp_side:
            bits.append(f"마감엔 {subj(n)} {obj(won(abs(v)))} {tail}")
        elif i == 0 and intraday_line and ans:
            bits.append(f"{ans} 다음은 {n}입니다. {obj(won(abs(v)))} {tail}")
        else:
            bits.append(f"{n}도 {obj(won(abs(v)))} {tail}")
    if bits:
        parts2.append("고, ".join(bits) + "습니다.")
    # 답이 아니어도 기타법인이 크게 샀으면(5,000억 이상) 어느 종목·자사주인지 연결(JJ 2026-09-11)
    oth = next(((n, v) for n, v in rest if n == "기타법인" and v * (1 if sold else -1) > 0 and abs(v) >= 5000), None)
    if oth and c.get("top_others"):
        parts2 += _others_link(c, oth[1], lead="그 돈의", d=d)
    for n, v in same[:1]:
        parts2.append(f"{n}도 {P}처럼 {obj(won(abs(v)))} {'팔았' if v < 0 else '샀'}습니다.")
    # 화면 단계 표지(문장 앞부분, 숫자 없는 부분만): 공개 이름 · 카운터 시작 · 막대 시작
    bars_from = ""
    if flip_sents:
        bars_from = flip_sents[0][:4]
    elif bits:
        bars_from = bits[0][:5]
    elif same:
        bars_from = f"{same[0][0]}도"
    s2_marks = {"answer": ans, "counter": counter_mark, "bars": bars_from or None,
                "snap": a if intraday_line else None, "prev": prev_ans}
    s2 = " ".join(parts2)

    # s3: 누가 → 어디서(어디로). 질문 다음 문장 '{테마}입니다.'에서 화면이 테마를 크게 띄운다
    s3, story_lead = "", None
    top_mv = c.get("top_move")
    if moves or top_mv:
        m = top_mv or max(moves, key=lambda x: abs(x.get("t") or 0))
        t, y, th = m.get("t") or 0, m.get("y"), m["theme"]
        if t < 0:
            _id, s3 = _pick_device(d, _dev_used, _dev_recent, [
                ("D02", f"그럼 가장 큰 돈이 빠진 곳은 어디였을까요? {th}입니다."),
                ("T03", f"지수만 보면 하루치 조정입니다. 그런데 {ro(th)} 한 업종에서만 이만큼이 빠졌습니다."),
                ("T05", f"오늘 빠진 돈은 여러 업종에 고르게 흩어진 게 아닙니다. {th} 한 곳입니다."),
            ])
            if y is not None and y < 0 and abs(t) > abs(y):
                s3 += f" 외국인과 기관이 합쳐 판 돈이 전날 {won(abs(y))}에서 {ro(won(abs(t)))} 커졌습니다."
            elif y is not None and y > 0:
                s3 += f" 외국인과 기관을 합쳐 전날엔 {obj(won(y))} 순매수했는데, 오늘은 {obj(won(abs(t)))} 순매도했습니다."
            else:
                s3 += f" 외국인과 기관을 합쳐 {subj(won(abs(t)))} 빠졌습니다."
            # 재정의 한 줄 — 이 테마가 외국인+기관 순매도의 대부분이면 '넓게 팔린 게 아니라'로 뜻을 준다.
            _fi, _in = inv.get("foreign") or 0, inv.get("inst") or 0
            _tot = abs(min(_fi, 0) + min(_in, 0))
            if _tot and abs(t) / _tot >= 0.7 and _id != "T05":   # 여는 문장이 이미 재정의면 같은 말을 두 번 하지 않는다
                s3 += " 넓게 팔린 게 아니라, 한 업종에 몰린 하루였다는 뜻입니다."
            names = []
        else:
            _id, s3 = _pick_device(d, _dev_used, _dev_recent, [
                ("D03", f"그럼 가장 큰 돈이 들어간 곳은 어디였을까요? {th}입니다."),
                ("T08", f"그럼 이 돈은 어디로 갔을까요? {th}입니다."),
                ("T05", f"오늘 들어온 돈은 넓게 퍼지지 않았습니다. {th} 한 곳입니다."),
            ])
            s3 += f" 외국인과 기관을 합쳐 {subj(won(t))} 들어왔습니다."
            if (m.get("state") or "").startswith("쌓임") and (m.get("streak") or 0) >= 2:
                s3 += f" {days_ko(m['streak'])} 쌓이고 있습니다."
            names = (m.get("spread_names") or [])[:3]
            if names:
                s3 += f" 돈은 {_and(names)}에 몰렸습니다."
        story_lead = {"theme": th, "t": t, "who": "외국인+기관 합산", "names": names}

    # s4: 이슈(있는 날만) — '간밤엔 … 발표도 있었습니다'로 화제를 넘기고 평균과 상승·하락 수로(상위 종목만 고르지 않음)
    # 이슈는 그날 돈의 흐름에 들 만큼 컸을 때만(평균 ±2% 이상 또는 외국인+기관 1,000억 이상) — 아니면 영상·제목·해시태그에서 뺀다
    s4 = ""
    ev_flow = sum((x.get("foreign") or 0) + (x.get("inst") or 0) for x in (ev.get("stocks") or []))
    if ev.get("stocks") and (abs(ev.get("avg_pct") or 0.0) >= 2.0 or abs(ev_flow) >= 1000):
        st4 = ev["stocks"]
        label = ev.get("label") or ""
        org = "애플" if "애플" in label else ""
        spoken = ev.get("spoken") or label
        avg = ev.get("avg_pct") or 0.0
        grp = ev.get("group") or "관련주"
        # events.json 에 head 를 적어 두면 그 문장을 쓴다 — '간밤엔'이 늘 맞는 건 아니다(주말에 나온 일도 있다).
        head = (ev.get("head") or "").strip()
        if not head:
            head = f"간밤엔 {org} 발표도 있었습니다. {obj(spoken)} 공개했고," if org else f"간밤엔 {label} 소식도 있었습니다."
        s4 = f"{head} {ro(grp)} 꼽힌 {len(st4)}종목은 평균 {pct(avg)} {'올랐' if avg > 0 else '내렸'}습니다."

    # s5: 어제 약속 확인 → 누적 → 다음 확인
    cb = c.get("callback")
    try:
        wk_also, wk_said, wk_rows = weekend_watch.block(d, c, done_q=(cb or {}).get("q") or "")
    except Exception:                              # 주말 파일이 없거나 모양이 달라도 그날 대본은 나가야 한다
        wk_also, wk_said, wk_rows = [], "", []
    parts5 = []
    cbs = callback_v3(cb, d, wk_also, _took)   # 훅이 이미 불렀으면 짧게, 아니면 머리에 합쳐 한 문장으로
    if cbs:
        parts5.append(cbs)
    if wk_said:
        parts5.append(wk_said)
    parts5 += _why_check(cb)                       # 왜 이걸 확인하는지 + 며칠째부터 흐름으로 보는지(판단 기준)
    _cau = _caution(d, P, sold, inv, streak)       # 무엇을 잘못 읽기 쉬운가
    if _cau:
        parts5.append(_cau)
    # 전적은 화면(S5V4)이 '확인 N번 · 이어짐 K · 끊김 M'으로 그린다. 말로 또 읽으면 3.3초를 같은 말에 쓴다.
    _ = record_line(c.get("ledger_stats"))
    key = NAME_KEY[P]
    st = (streak.get(key) or {}).get("streak") or 0
    if P in ("외국인", "기관") and st and (st < 0) == sold:
        nxt_n = abs(st) + 1
    elif P in ("외국인", "기관"):
        nxt_n = 2
    else:
        nxt_n = None
    word = "순매도" if sold else "순매수"
    next_q = f"{P} {word}가 {days_ko(nxt_n)} 이어지는지" if nxt_n else f"{P} {word}가 이어지는지"
    nd = next_trading_day(d)
    when_n = _day_word(d, nd, past=False)
    when_x = f"{when_n}{'은' if when_n == '내일' else '엔'}"
    # 다음 확인은 '하나만'. 조건 분기('이어지면…끊기면…')는 뺀다 — 시청자가 들고 가는 게 판단이 아니라 숙제가 된다.
    parts5.append(f"{when_x} 하나만 봅니다. {P} {word}가 {days_ko(nxt_n) + ' ' if nxt_n else ''}이어지는지.")
    _th = (c.get("top_move") or {}).get("theme") or ((c.get("moves") or [{}])[0].get("theme"))
    # ② 시청자에게 묻던 줄은 뺐다 — 대본 시스템 v1.2 §0-1(JJ 2026-09-15): "여러분은 어떻게 읽으셨습니까" 삭제, S5 는 판정과 뒤집히는 조건으로 끝난다
    _ = (_ask_viewer, _th, when_x)
    parts5.append(_like_sub(d))                            # ③ 좋아요 + 구독 한 줄
    s5 = " ".join(parts5)

    # 끝 멘트(JJ 2026-09-15: "내일부터는 저녁 5시에 올린다고 명시… 마지막 멘트와 장면이 바뀌어야 해").
    # 9/15 편만 '내일부터', 그 뒤로는 '매일 저녁 5시'. 시각 문구는 publish_config 의 publish_at 에서 온다.
    # 이번 주(9/14~9/18)는 애프터마켓(9/14 개시, 정규장 후 16~20시)을 시그니처 앞에 한 문장 붙인다.
    _when = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    _after = "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다. " if d <= AFTER_MARKET_NOTICE_UNTIL else ""
    _since = "내일부터 " if d == "20260915" else ""
    s6 = f"{_after}{_ieot(brand)} 국장 마감은 {_since}매일 {_when}에 올라옵니다."

    # 화면용: 막대(말하는 순서), 카드 제목
    bars = [{"name": P, "v": amount}] + [{"name": n, "v": v} for n, v in opp] + [{"name": n, "v": v} for n, v in same] + \
           [{"name": n, "v": v} for n, v in parties if n not in {x for x, _ in opp} | {x for x, _ in same}]
    s2_title = f"{P} {_won_screen(amount, True)},<br>{'·'.join(n for n, _ in opp) or '—'}{'이' if opp else ''} {'받았다' if sold else '팔았다'}"

    # 다리 질문("…어떻게 됐을까요?")은 답(s5) 바로 앞 장면에 붙인다. s3 에 붙이고 s4 가 끼면
    # 질문 뒤에 이슈가 나와 답이 끊긴다(JJ 2026-09-14). 이슈가 있는 날은 s4 끝, 없는 날은 s3 끝.
    _bw = _day_word(d, datetime.strptime(cb["prev_date"], "%Y%m%d"), past=True) if (cb and cb.get("prev_date")) else ""
    _br = _bridge(d, cb, _bw, _took)
    if s4:
        s4 = s4.rstrip() + " " + _br
    elif s3:
        s3 = s3.rstrip() + " " + _br
    scenes = [{"id": "s0", "min": 4.0, "tts": s0, "sub": ""},
              {"id": "s2", "min": 8.0, "tts": s2, "sub": s2}]
    if s3:
        scenes.append({"id": "s3", "min": 6.0, "tts": s3, "sub": s3})
    if s4:
        scenes.append({"id": "s4", "min": 5.0, "tts": s4, "sub": s4})
    scenes += [{"id": "s5", "min": 6.0, "tts": s5, "sub": s5},
               {"id": "s6", "min": 4.0, "tts": s6, "sub": ""}]

    cbv = None
    if cb:
        ch = cb["check"]
        cbv = {"q": cb.get("q"), "kind": ch.get("kind"), "theme": ch.get("theme") or ch.get("name") or "", "n": ch.get("n"), "sign": ch.get("sign"),
               "when": _day_word(d, datetime.strptime(cb["prev_date"], "%Y%m%d"), past=True) if cb.get("prev_date") else "어제",
               "ok": cb["ok"], "amount": cb.get("t")}
    return {
        "brand": brand, "tagline": TAGLINE_V3, "hook": line1, "hook_parts": [line1, line2],
        "scenes": scenes, "s2_title": s2_title, "s3_title": (story_lead or {}).get("theme", ""), "bars": bars,
        "fx_said": False, "bonding": "",
        "s3_story": {"verdict": None, "lead": story_lead, "summary": ""} if story_lead else None,
        "protagonist": {"name": P, "amount": amount, "sold": sold}, "contrast": ct,
        "check": {"verdict": cbv, "record": c.get("ledger_stats"), "next_q": next_q, "next_day": f"{nd.month}/{nd.day}"},
        "next_q": next_q, "s2_marks": s2_marks, "event_used": bool(s4), "others_top": _others_top(c),
        "weekend_watch": wk_rows, "hook_id": hook_id, "caution_id": "C1" if _cau else None, "devices": sorted(_dev_used),
    }
