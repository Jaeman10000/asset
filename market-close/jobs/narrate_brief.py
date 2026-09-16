"""국장편 v5 '수급 브리핑' 대본 — 경제사냥꾼 7슬롯 장치(정본 docs/SCRIPT_SYSTEM_HUNTER_v1.0.md) 위에 **수급 순서를 매일 고정**한 것.
설계 docs/BRIEF_FORMAT_DESIGN.md §1(장면↔장치↔데이터) · §2(대체 규칙) · §3(계약). 견본 docs/scripts/2026-09-15_brief.md(승인본 문장 그대로는 1,349자 —
검사 상한 1,250자에 맞춰 같은 사실을 더 짧은 문장으로 말한다).

체인은 매일 같다(헌터 1차가 어지러웠던 이유가 날마다 다른 블록을 골랐기 때문):
  s0 모순 후킹 → s1 질문(항상 돈의 행방) → s2 코스피 수급 넷 나열(대변→차단, 네 번째 막대 = 기타법인·자사주)
  → s3a 코스닥 수급 + 지수 둘 + 한 줄 판정 + 어제 콜백 → s3b 돈이 빠진 곳·정체된 곳 → s3c 돈이 들어온 곳(이동 선언 1회, 비율)
  → s4 종목 둘(직접 열어봤습니다 + 계산 1개 검산) → s5 뉴스와 맞물렸나(양면 프레임 고정 → 판정 → 뒤집히는 조건 → S0 콜백 → 한계)
  → s6 내일 포인트 2~3 + 이벤트 시각 + 애프터마켓 + 시그니처.

코드가 지키는 것:
  - 대사는 매일 새로: 틀 문장마다 후보 3벌 이상, script_memory.pick(문장 단위 회피) + attempt 회전. 시그니처만 고정.
  - 이어지는 사실은 처음 말하듯 하지 않는다: 외국인 '닷새째', 기타법인 '9월 들어 매일/N일째', 유출 업종 'N일째', 유입 '이틀째'(script_memory.continuity).
  - 한 문장 숫자 ≤2(qa_script.num_tokens 기준), 100억 단위(narrate_hunter.hwon), 부호를 말한다. 그런데는 블록당 1회, 화면 지시어 ≥4.
  - 종목 추천·목표주가·전망 없음. '여러분'·자기 영상 언급 없음. 마지막 문장은 관측값. 길이 950~1,250자: 넘치면 선택 문장을 GLOBAL_DROP 순서로 빼고,
    그래도 넘치면 짧은 후보 + 압축 뉴스(이슈 메모 키워드 한 줄)로 한 번 더 만든다.
  - 데이터가 없어도 장면을 비우지 않는다(§2 대체 규칙 — 각 _sX 함수 주석).
BRIEF_FIX_2(JJ 2026-09-16 아침)가 더한 네 가지 — 이 칸들은 길이 예산에서 빼지 않는다(GLOBAL_DROP 에 없다):
  A 어제 숙제의 답을 빠짐없이(s3a) — watch[0] 은 ledger 도장(promise), watch[1] 부터는 _verify_watch 가 오늘 숫자로 직접 판정(promise2·promise3).
    판정할 수 없는 질문 꼴이면 그 문장은 아예 말하지 않는다(틀린 답보다 침묵).
  B 흐름 방향 한 줄(s5 flow, 판정 뒤·조건 앞) — _flow_score 가 −3~+3 으로 재고 등급마다 다른 문장 + 근거 한 마디(이미 말한 숫자만 되쓴다).
    돈의 흐름에 대한 판정이지 매매 판단이 아니다(사라·팔아라·비중·관망·전망 없음, 주어는 돈·흐름·수급).
  C '내일도 같은 자리'(s6 watch_same) — script_memory.continuity 의 promise_days 가 2 이상이면 첫 관측값 앞에 한 줄.
    장부 문장('{주체} {순매수|순매도}가 {N일째} 이어지는지')은 따로 떨어진 한 문장 그대로 둔다 — ledger.parse_q 가 읽는다.
  D 이슈와 수급을 잇는다 — s3c issue(유입 업종 안의 이슈 종목), s4 row(이슈 종목 표시, s3c 가 이미 말했으면 생략), s5 판정(이슈 라벨이 업종과 다르면 둘 다).
헌터의 hwon/hshort/Picker/J/subj/obj/_was/ro/_callback/_s0/_next_event/_ob_word/_calc 는 import 해 재사용한다(복사 금지).
반환은 narrate_hunter.build 와 같은 키(build_aplus 호환) + format="brief" + hunter(화면용 사전, 장면마다 steps).
"""
from __future__ import annotations

import re
from datetime import datetime

from narrate import _and, _bat, _won_screen, ro
import narrate_aplus as na
import narrate_hunter as nh
import script_memory as sm
from narrate_hunter import (J, Picker, _calc, _callback, _choose, _ctx, _day_word, _next_event, _ob_word, _recent_ids, _steps, _text,
                            _was, dko, han, hshort, hwon, obj, pct1, pct1_dir, pct_s, sgn_pct, subj, updn)

try:
    import qa_script as _qa
except Exception:  # noqa: BLE001 — 검사 모듈이 없어도 대본은 나간다
    _qa = None

AFTER_MARKET_NOTICE_UNTIL = na.AFTER_MARKET_NOTICE_UNTIL
NAME_KEY = na.NAME_KEY
TOTAL_MAX, TOTAL_MIN = 1200, 950   # 1,200자 ≈ 164초(9/15 실측 1,241자=169.6초) — 쇼츠 한계 180초, 우리 상한 172초에 여유를 둔다
MONEY_MIN = 500     # 억 — 이 아래면 '들어온 큰손 돈은 작았다'(JJ 9/15 판정: 로봇 380억은 뉴스 쪽, 이차전지 940억은 돈 쪽)
COUNT_WORD = {1: "하나", 2: "둘", 3: "셋", 4: "넷"}
# 말할 때 줄이는 업종 이름(화면은 원래 이름)
SPOKEN_THEME = {"원전/에너지": "원전", "바이오/제약": "바이오", "인터넷/게임": "인터넷·게임", "전력/유틸": "전력"}
# 뉴스 문장을 업종에 붙일 때 보는 낱말(업종 이름·구성 종목 이름은 자동으로 더한다)
THEME_KW = {"이차전지": ["배터리", "CATL", "전지", "양극재", "리튬"], "로봇": ["로봇", "AI 전환", "제조업 AI", "제조AI", "휴머노이드", "자동화"],
            "반도체": ["반도체", "HBM", "엔비디아", "메모리", "파운드리"], "방산": ["방산", "무기", "국방", "수출 계약"], "조선": ["조선", "선박", "수주"],
            "금융": ["금융", "은행", "지주"], "바이오/제약": ["바이오", "제약", "신약", "임상"], "자동차": ["자동차", "전기차", "완성차"],
            "원전/에너지": ["원전", "원자력", "에너지"], "건설": ["건설", "주택", "재건축"], "철강": ["철강", "관세", "포스코"], "화장품": ["화장품", "뷰티"],
            "엔터": ["엔터", "아이돌", "음원"], "인터넷/게임": ["게임", "인터넷", "포털"], "통신": ["통신", "요금"], "전력/유틸": ["전력", "변압기", "전선"],
            "해운": ["해운", "운임"], "유통": ["유통", "소비"], "화학": ["화학", "석유화학"]}
_GENERIC_KW = re.compile(r"순매[수도]|금리|FOMC|코스피|코스닥|급락|급등|강세|약세|관련주|외국인|기관|개인")
# 슬롯 자수 예산(적어 두는 값) — 헌터 것을 그대로 쓰되 s3a 는 +40(어제 숙제의 답이 항목 수만큼 들어간다, BRIEF_FIX_2 §A-4).
# 브리핑은 헌터의 슬롯별 _fit 을 부르지 않고 아래 GLOBAL_DROP 으로만 줄인다 — 그래서 §A-4 의 상쇄는 이 표가 아니라
# GLOBAL_DROP 순서로 한다(s3a verdict 를 앞쪽으로, s3c names·s3b sum·s3c move 를 뒤쪽에 더했다). lint() 는 헌터의 예산 경고를 걸러 낸다.
CAPS = {**nh.CAPS, "s3a": nh.CAPS.get("s3a", 150) + 40}
# 선택 단계 — 전체가 1,250자를 넘으면 앞에서부터 뺀다. 뒤쪽 것(콜백·소개)은 마지막 수단
# s3a 한 줄 판정(verdict)은 어제 숙제의 답이 들어온 만큼 앞쪽(먼저 빠지는 자리)으로 옮겼다(BRIEF_FIX_2 §A-4).
GLOBAL_DROP = [("s5", "news_x"), ("s3a", "verdict"), ("s3b", "meaning"), ("s3c", "ratio_2"), ("s5", "lead"), ("s3b", "others2"), ("s3a", "turn"),
               ("s2", "inst_streak"), ("s3c", "streak"),
               ("s4", "driver"), ("s5", "verdict_why"), ("s6", "note"), ("s5", "limit"), ("s3b", "others"), ("s3b", "y"), ("s6", "intro"),
               ("s5", "callback"), ("s5", "news:1"), ("s3a", "weekend"), ("s3c", "t2_sum"), ("s5", "ab"), ("s3c", "t1_sum"), ("s3b", "q"), ("s2", "top"),
               ("s5", "verdict:1"), ("s4", "open_2"), ("s2", "turn_2"), ("s3c", "names"), ("s3b", "sum"), ("s3c", "move"), ("s1", "q_2"), ("s4", "calc"), ("s5", "b")]
# JJ 2026-09-15 가 매일 요구한 칸은 예산에서 절대 빼지 않는다(그래서 위 목록에 없다 — BRIEF_FIX_1 §A):
#   코스닥 개인(s3a kosdaq_2) · 종목별 개인·거래대금(s4 row:0_3 · row:1_3) — "외국인 개인 기관 이것도 샀는지 팔았는지 알려주고"
#   둘째 유입 업종 수급(s3c t2) · 자사주 받침(s3b support) · 다음 이벤트(s6 event) — 빼면 s6 이 '…는지.'로 끝나 검사도 실패한다.
#   양면 프레임 한쪽(s5 b)은 두 쪽이 다 있어야 뜻이 사니 목록 맨 뒤(마지막으로 빠지는 칸)에 둔다.
#   어제 숙제의 답(s3a promise·promise2·promise3) · 흐름 방향(s5 flow) · '내일도 같은 자리'(s6 watch_same) · 이슈-수급 연결(s3c issue)은
#   BRIEF_FIX_2 가 매일 요구한 칸이라 어떤 경우에도 빼지 않는다.
# 한 장면 안에서 같은 낱말이 세 번을 넘지 않게 — 후보를 고를 때 가벼운 벌점을 준다(BRIEF_FIX_1 §C). '왼쪽·오른쪽'의 쪽은 세지 않는다.
GUARD_WORDS = {"오늘": re.compile("오늘"), "막대": re.compile("막대"), "칸": re.compile("칸"), "쪽": re.compile(r"(?<![왼른양])쪽")}
GUARD_MAX = 3
_DG = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ── 작은 도우미 ──
class ScenePick:
    """장면 하나를 만드는 동안 Picker 를 감싼다 — '오늘·막대·칸·쪽'이 그 장면에서 세 번을 넘게 하는 후보는 먼저 뺀다(BRIEF_FIX_1 §C).
    후보가 전부 걸리면 벌점을 무시하고 원래 후보로 고른다(장면을 비우지 않는다)."""

    def __init__(self, pk: Picker):
        self.pk = pk
        self.n: dict[str, int] = {w: 0 for w in GUARD_WORDS}

    @staticmethod
    def _count(s: str) -> dict[str, int]:
        return {w: len(rx.findall(s or "")) for w, rx in GUARD_WORDS.items()}

    def _over(self, s: str) -> bool:
        c = self._count(s)
        return any(self.n[w] + c[w] > GUARD_MAX for w in GUARD_WORDS)

    def __call__(self, cands: list[str], fallback: str = "") -> str:
        cands = [c for c in cands if c and c.strip()]
        ok = [c for c in cands if not self._over(c)]
        r = self.pk(ok or cands, fallback)
        for w, k in self._count(r).items():
            self.n[w] += k
        return r


def tname(th: str | None) -> str:
    """말하는 업종 이름 — '원전/에너지' → '원전'."""
    return SPOKEN_THEME.get(th or "", th or "")


def pct2(v: float | None) -> str:
    """원문 표의 등락 그대로(소수 2자리, 끝 0은 뗀다): 3.98→'3.98%', 29.8→'29.8%', 0.2→'0.2%'. S4 종목 칸에만 쓴다(1차 자료 = 표 숫자)."""
    if v is None:
        return "미확정"
    return f"{abs(v):.2f}".rstrip("0").rstrip(".") + "%"


def _ntok(s: str) -> int:
    if _qa is not None:
        try:
            return len(_qa.num_tokens(s))
        except Exception:
            pass
    return len(_DG.findall(s or ""))


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def _word(v: float) -> str:
    return "순매수" if v > 0 else "순매도"


def _verb(v: float) -> str:
    return "샀" if v > 0 else "팔았"


def _sum_stocks(rows: list[dict]) -> dict:
    """flow_day 종목행 → 업종 합(외/기/순·거래대금 가중 등락·순매수 종목 이름·거래대금)."""
    f = sum(_num(r.get("foreign")) or 0 for r in rows)
    i = sum(_num(r.get("inst")) or 0 for r in rows)
    val = sum(_num(r.get("value")) or 0 for r in rows)
    wret = sum((_num(r.get("ret")) or 0) * (_num(r.get("value")) or 0) for r in rows)
    pos = sorted([r for r in rows if (_num(r.get("foreign")) or 0) + (_num(r.get("inst")) or 0) > 0],
                 key=lambda r: -((_num(r.get("foreign")) or 0) + (_num(r.get("inst")) or 0)))
    return {"foreign": round(f), "inst": round(i), "net": round(f + i), "ret": round(wret / val, 2) if val else None, "value": round(val),
            "pos_names": [r.get("name") for r in pos if r.get("name")], "n": len(rows), "stocks": rows}


# ══════════════════════════════════════════════════════════════════════════════
# 어제 숙제의 답 — 어제 편 watch 를 오늘 숫자로 직접 판정한다(BRIEF_FIX_2 §A)
# watch[0] 은 ledger 가 판정한 callback(도장)을 그대로 쓰고, watch[1] 부터가 여기로 온다.
# ══════════════════════════════════════════════════════════════════════════════
_W_KOSDAQ = re.compile(r"^코스닥 (외국인|기관|개인) (순매수|순매도)가")
_W_KEEP = re.compile(r"^(외국인|기관|개인|기타법인) (순매수|순매도)가 (.+?)[을를] 지키는지$")
_W_INV = re.compile(r"^(외국인|기관|개인|기타법인) (순매수|순매도)가 (?:(\S+) )?이어지는지$")
_W_TH = re.compile(r"^(.+?) (순매수|순매도)가 (?:(\S+) )?이어지는지$")
_KQ_KEY = {"외국인": "foreign", "기관": "inst", "개인": "indiv"}


def _won_num(s: str) -> float | None:
    """말로 쓴 금액 → 억 단위 숫자. '1조 4,000억'→14000 · '9천억'→9000 · '940억'→940. 못 읽으면 None."""
    t = (s or "").replace(",", "")
    v, hit = 0.0, False
    if m := re.search(r"(\d+(?:\.\d+)?)\s*조", t):
        v, hit, t = v + float(m.group(1)) * 10000, True, t[m.end():]
    if m := re.search(r"(\d+(?:\.\d+)?)\s*천억", t):
        v, hit = v + float(m.group(1)) * 1000, True
    elif m := re.search(r"(\d+(?:\.\d+)?)\s*억", t):
        v, hit = v + float(m.group(1)), True
    return v if hit else None


def _prev_watch(d: str, prev_date: str | None) -> list[str]:
    """어제 편이 남긴 '내일 볼 것' 질문들(data/<전 거래일>/computed_kr.json 의 watch). 없으면 빈 목록."""
    try:
        from _common import DATA, load_json
    except Exception:  # noqa: BLE001
        return []
    seen: list[str] = []
    for pd in [p for p in (prev_date, nh._prev_weekday(d)) if p]:
        if pd in seen:
            continue
        seen.append(pd)
        try:
            c = load_json(DATA / pd / "computed_kr.json") or {}
        except Exception:  # noqa: BLE001
            continue
        qs = [str(w.get("q")).strip() for w in (c.get("watch") or []) if isinstance(w, dict) and w.get("q")]
        if qs:
            return qs
    return []


def _verify_watch(q: str, c: dict, pk=None) -> tuple[bool | None, str] | None:
    """어제 숙제 한 줄(q)을 오늘 숫자로 판정한다. c 는 bctx() 가 만든 오늘 사실.
    반환 (이어졌나, 말할 문장) — 질문 꼴을 못 읽거나 오늘 숫자가 없으면 None 이고, 그러면 그 문장은 **아예 말하지 않는다**(틀린 답보다 침묵).
    pk 는 ScenePick/Picker — 주면 후보 넷 이상에서 고른다(없으면 첫 후보)."""
    q = (q or "").strip().rstrip(".")
    if not q:
        return None
    ch = pk or (lambda cands, fallback="": next((x for x in cands if x), fallback))
    vals = c.get("vals") or {}
    # ① 코스닥 주체 — investors.kosdaq
    if m := _W_KOSDAQ.match(q):
        who, word = m.group(1), m.group(2)
        v = _num((c.get("kq") or {}).get(_KQ_KEY[who]))
        if v is None or not c.get("kq_ok"):
            return None
        ok, V = (v > 0) == (word == "순매수") and v != 0, hwon(v)
        if ok:
            return ok, ch([f"코스닥 {who} {word}도 오늘 이어졌습니다. {V}입니다.", f"코스닥에서도 {J(who)} 같은 방향입니다. {V} {word}.",
                           f"코스닥 {who}는 오늘도 {word}, {V}입니다.", f"코스닥 쪽 답도 이어짐입니다. {who} {V} {word}."])
        return ok, ch([f"코스닥 {who} {word}는 오늘 끊겼습니다. {V} {_word(v)}입니다.", f"코스닥에선 {J(who)} 방향을 바꿨습니다. {V} {_word(v)}.",
                       f"코스닥 쪽 답은 끊김입니다. {who} {V} {_word(v)}.", f"코스닥 {who}는 오늘 {V} {_word(v)}, 끊겼습니다."])
    # ② 선을 지키는지 — investors.kospi[주체] 와 임계값
    if m := _W_KEEP.match(q):
        who, word, amt = m.group(1), m.group(2), m.group(3)
        thr, v = _won_num(amt), _num(vals.get(who))
        if thr is None or v is None:
            return None
        ok, V = (v >= thr) if word == "순매수" else (v <= -thr), hwon(v)
        if ok:
            return ok, ch([f"{J(who)} {amt} 선을 지켰습니다. 오늘 {V}입니다.", f"{amt} 선은 지켜졌습니다. {who} {V}입니다.",
                           f"{J(who)} {amt} 선 위에 남았습니다. 오늘 {V}입니다.", f"{who} {word}는 {amt} 선을 지켰습니다. {V}입니다."])
        return ok, ch([f"{J(who)} {amt} 선을 내줬습니다. 오늘 {V}입니다.", f"{amt} 선은 무너졌습니다. {who} {V}입니다.",
                       f"{J(who)} {amt} 선 아래로 내려왔습니다. 오늘 {V}입니다.", f"{who} {word}는 {amt} 선을 못 지켰습니다. {V}입니다."])
    # ③ 주체 순매수·순매도가 N일째 이어지는지 — investors.kospi[주체] 부호
    if m := _W_INV.match(q):
        who, word = m.group(1), m.group(2)
        v = _num(vals.get(who))
        if v is None:
            return None
        ok, V = (v > 0) == (word == "순매수") and v != 0, hwon(v)
        st = abs(((c.get("streak") or {}).get(NAME_KEY.get(who, "")) or {}).get("streak") or 0)
        tail = f"{V}, {dko(st)}입니다." if st >= 2 else f"{V}입니다."
        if ok:
            return ok, ch([f"{who} {word}는 오늘도 이어졌습니다. {tail}", f"{J(who)} 오늘도 같은 방향입니다. {tail}",
                           f"{who} {word}, 오늘도 그대로입니다. {tail}", f"그 답은 이어짐입니다. {who} {tail}"])
        return ok, ch([f"{who} {word}는 오늘 끊겼습니다. {V} {_word(v)}입니다.", f"{J(who)} 오늘 방향을 바꿨습니다. {V} {_word(v)}입니다.",
                       f"{who} {word}, 오늘 멈췄습니다. {V} {_word(v)}입니다.", f"그 답은 끊김입니다. {who} {V} {_word(v)}."])
    # ④ 업종 순매수·순매도가 N일째 이어지는지 — 업종 표(flows.table_t) 의 net 부호
    if m := _W_TH.match(q):
        th, word = m.group(1), m.group(2)
        themes = c.get("themes") or {}
        key = th if th in themes else next((t for t in themes if tname(t) == th), None)
        net = _num((themes.get(key) or {}).get("net")) if key else None
        if net is None:
            return None
        ok, tn, T = (net > 0) == (word == "순매수"), tname(key), hwon(net)
        stk = abs(int((themes.get(key) or {}).get("streak") or 0))
        tail = f"{T}, {dko(stk)}입니다." if stk >= 2 else f"{T}입니다."
        if ok:
            return ok, ch([f"{tn} {word}는 오늘도 이어졌습니다. {tail}", f"{J(tn)} 오늘도 같은 색입니다. {tail}",
                           f"{tn} {word}, 하루 더 갔습니다. {tail}", f"그 답은 이어짐입니다. {tn} {tail}"])
        return ok, ch([f"{tn} {word}는 오늘 끊겼습니다. {T} {_word(net)}입니다.", f"{J(tn)} 오늘 막대 색이 바뀌었습니다. {T} {_word(net)}입니다.",
                       f"{tn} {word}, 오늘 멈췄습니다. {T} {_word(net)}입니다.", f"그 답은 끊김입니다. {tn} {T} {_word(net)}."])
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 오늘 돈이 어느 쪽으로 가고 있나 — 점수 −3~+3(BRIEF_FIX_2 §B). 매매 판단이 아니라 **돈의 흐름**에 대한 판정이다.
#   · 주인공(외국인) 오늘 방향: 순매수 +1 / 순매도 −1(연속 사흘 이상이면 ±2)
#   · 어제 숙제 답: 유입 약속 이어짐 +1 / 끊김 −1, 유출 약속 이어짐 −1 / 끊김 +1
#   · 유입 업종 합 ÷ 유출 1위 절대값: 1/3 이상 +1, 1/10 미만 −1
# ══════════════════════════════════════════════════════════════════════════════
def _flow_score(x: dict) -> tuple[int, list[str]]:
    """(점수 −3~+3, 근거 한 마디 후보들). 근거는 **이미 말한 숫자만** 되쓴다(새 숫자 금지)."""
    score = 0
    why: list[str] = []
    frg = _num(x["vals"].get("외국인"))
    st_f = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
    if frg:
        s = 1 if frg > 0 else -1
        score += s * 2 if st_f >= 3 else s
        why.append(f"외국인이 {dko(st_f)} {'사고' if frg > 0 else '팔고'} 있어서입니다." if st_f >= 2 else
                   f"외국인이 오늘 {hwon(frg)} {_word(frg)}라서입니다.")
    cb = x["cb"]
    if cb and cb.get("ok") is not None and isinstance(cb.get("check"), dict):
        kind, sign = cb["check"].get("kind"), cb["check"].get("sign")
        inflow = kind in ("theme_continue", "theme_sell_stop") or (kind == "inv_continue" and (sign or -1) > 0)
        ok = bool(cb["ok"])
        score += (1 if ok else -1) if inflow else (-1 if ok else 1)
        qn = na._q_noun(cb) or "어제 숫자"
        why.append(f"어제 보자고 한 {J(qn)} 오늘도 {'이어져서' if ok else '끊겨서'}입니다.")
    ins, out_t = x["in_ths"], x["out_t"]
    if ins and out_t:
        in_sum = sum(x["themes"][t]["net"] for t in ins)
        r = in_sum / abs(out_t)
        if r >= 1 / 3:
            score += 1
        elif r < 0.1:
            score -= 1
        frac = _calc("fraction", in_sum, out_t)
        on = tname(x["out_th"])
        why.append(f"들어온 돈이 {on} 유출의 {frac['n']}분의 1이라서입니다." if frac else
                   f"들어온 돈이 {on}에서 나간 돈의 {round(r * 100)}%라서입니다.")
    return max(-3, min(3, score)), why


_FLOW_TXT = {
    2: ["돈이 들어오는 쪽으로 방향을 잡아 가는 흐름입니다.", "받는 손이 늘어나는 쪽입니다.", "들어오는 돈이 나가는 돈을 눌러 가는 흐름입니다.",
        "돈의 무게가 들어오는 쪽으로 실린 하루입니다.", "받는 쪽이 더 무거워진 흐름입니다."],
    1: ["아직 세지는 않지만 들어오는 쪽으로 기운 하루입니다.", "세지는 않아도 무게는 들어오는 쪽입니다.", "조금이지만 돈은 들어오는 쪽으로 기울었습니다.",
        "약하게나마 받는 손이 앞선 하루입니다.", "들어오는 쪽이 아주 조금 더 무거운 하루입니다."],
    0: ["들어온 돈과 나간 돈이 맞서는 하루입니다.", "나간 돈과 들어온 돈이 팽팽한 하루입니다.", "어느 쪽으로도 기울지 않은 하루입니다.",
        "들어온 돈과 나간 돈이 서로를 지운 하루입니다.", "양쪽 무게가 비슷한 하루입니다."],
    -1: ["들어온 돈이 나간 돈을 못 받치는 쪽입니다.", "받는 손이 나가는 돈을 다 못 받은 쪽입니다.", "나가는 쪽이 조금 더 무거운 하루입니다.",
         "들어온 돈만으로는 나간 자리를 못 메운 하루입니다.", "무게는 나가는 쪽으로 살짝 기울었습니다."],
    -2: ["돈이 빠져나가는 흐름이 더 무겁습니다.", "아직 나가는 쪽이 이기고 있는 하루입니다.", "돈의 방향은 나가는 쪽에 있습니다.",
         "나가는 돈이 들어오는 돈을 누르는 흐름입니다.", "무게는 여전히 나가는 쪽입니다."],
}


def _flow_grade(n: int) -> int:
    return 2 if n >= 2 else -2 if n <= -2 else n


# ── 오늘 이슈와 수급을 잇는다(BRIEF_FIX_2 §D) ──
def _issue_names(x: dict) -> list[str]:
    """raw/event.json 의 이슈 종목 이름들."""
    return [str(s.get("name")) for s in (x.get("ev_st") or []) if isinstance(s, dict) and s.get("name")]


def _issue_lab(x: dict, th: str | None) -> str:
    """이슈 라벨이 이 업종과 다르면 그 라벨, 같거나 없으면 빈 문자열 — 다를 때만 s5 판정에 둘 다 붙인다(§D-3)."""
    ev = x.get("ev") or {}
    lab = str(ev.get("group") or ev.get("label") or "").strip()
    if not lab or not th or th in lab or tname(th) in lab:
        return ""
    return lab


# ══════════════════════════════════════════════════════════════════════════════
# 오늘 사실 — 헌터 _ctx 위에 브리핑이 더 쓰는 것(업종 표 전체·종목행·종목 둘·뉴스)
# ══════════════════════════════════════════════════════════════════════════════
def bctx(c: dict) -> dict:
    x = _ctx(c)
    fd = c.get("flow_day") if isinstance(c.get("flow_day"), dict) else {}
    rows_all = [r for r in (fd.get("stocks") or []) if isinstance(r, dict) and r.get("theme")]
    by_theme: dict[str, list[dict]] = {}
    for r in rows_all:
        by_theme.setdefault(r["theme"], []).append(r)
    trows = c.get("theme_rows") if isinstance(c.get("theme_rows"), dict) else {}
    trows_y = c.get("theme_rows_y") if isinstance(c.get("theme_rows_y"), dict) else {}
    moves = {m["theme"]: m for m in x["moves"]}
    themes: dict[str, dict] = {}
    for th in set(x["flows"]) | set(by_theme) | set(trows):
        row = dict(trows.get(th) or {})
        if th in by_theme:
            agg = _sum_stocks(by_theme[th])
            for k in ("foreign", "inst", "net", "ret", "value", "pos_names", "n"):
                row.setdefault(k, agg[k])
            row["value"], row["stocks"] = agg["value"], agg["stocks"]
        m = moves.get(th) or {}
        if "net" not in row:
            row["net"] = x["flows"].get(th, m.get("t"))
        row.setdefault("foreign", m.get("foreign"))
        row.setdefault("inst", m.get("inst"))
        row.setdefault("ret", m.get("ret"))
        row.setdefault("pos_names", m.get("spread_names") or [])
        row["streak"] = m.get("streak")
        row["y"] = (trows_y.get(th) or {}).get("net", (c.get("theme_table_y") or {}).get(th, m.get("y")))
        if _num(row.get("net")) is not None:
            themes[th] = row
    outs = sorted([t for t, r in themes.items() if r["net"] < 0], key=lambda t: themes[t]["net"])
    ins = sorted([t for t, r in themes.items() if r["net"] > 0], key=lambda t: -themes[t]["net"])
    bs = c.get("brief_stocks") if isinstance(c.get("brief_stocks"), dict) else {}
    bstocks = [s for s in (bs.get("stocks") or []) if isinstance(s, dict) and s.get("name")]
    news = [n for n in (c.get("news_items") or []) if isinstance(n, dict) and n.get("title")]
    kq = x["kq"]
    kq_ok = all(isinstance(kq.get(k), (int, float)) for k in ("foreign", "inst", "indiv")) if kq else False
    x.update({"themes": themes, "outs": outs, "ins": ins, "out_th": outs[0] if outs else None, "in_ths": ins[:2],
              "out_t": themes[outs[0]]["net"] if outs else None, "in_t": themes[ins[0]]["net"] if ins else None, "in_th": ins[0] if ins else None,
              "bstocks": bstocks, "btheme": bs.get("theme"), "news": news, "flow_day": fd, "kq_ok": kq_ok,
              "fomc_prob": _num(c.get("fomc_prob"))})
    return x


# ══════════════════════════════════════════════════════════════════════════════
# S1 단일 질문 — 항상 돈의 행방(틀 5벌 회전, 최근 편 것 제외). 질문 정확히 1개 + '하나만 봅니다' 류 꼬리.
# ══════════════════════════════════════════════════════════════════════════════
_Q1 = {"Q1": ["오늘 그 돈이 어디로 갔느냐", "그 돈이 오늘 어디로 갔느냐", "빠진 돈이 오늘 어디로 갔느냐"],
       "Q2": ["나간 돈을 누가 받았느냐", "빠진 돈을 오늘 누가 받았느냐", "그 돈을 받은 손이 누구냐"],
       "Q3": ["돈이 어디서 빠져 어디로 옮겨 갔느냐", "어디서 나가 어디로 들어갔느냐", "빠진 자리와 들어온 자리가 어디냐"],
       "Q4": ["오늘 돈의 행방이 어디냐", "돈의 행방, 오늘은 어디냐", "오늘 큰돈의 행방이 어디냐"],
       "Q5": ["빠진 돈이 어느 자리에 닿았느냐", "나간 돈이 어느 업종에 닿았느냐", "돈이 머문 자리가 어디냐"]}
_Q1_TAIL = ["이것 하나만 봅니다.", "이 질문 하나만 봅니다.", "이것 하나만 보겠습니다.", "답은 이 하나만 찾습니다.", "오늘의 전부입니다.",
            "오늘은 이 하나만 봅니다.", "오늘 답은 이것 하나만 찾습니다.", "끝까지 이 하나만 봅니다.", "이 하나만 봅니다."]


def _s1(x: dict, pk: Picker, attempt: int) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    kind = _choose(list(_Q1), _recent_ids(d, "devices"), d, attempt)
    qs = _Q1[kind]
    # 질문에 이미 든 낱말('오늘')을 꼬리가 또 말하지 않게 — 같은 낱말 반복 금지(BRIEF_FIX_1 §C)
    s = pk([f"{q}. {t}" for q in qs for t in _Q1_TAIL if not ("오늘" in q and "오늘" in t)])
    q = next((q for q in qs if q in s), qs[0])
    tail = next((t for t in _Q1_TAIL if t in s), _Q1_TAIL[0])
    return [("q", s)], {"q": q, "tail": tail, "text": s, "kind": kind}, kind


# ══════════════════════════════════════════════════════════════════════════════
# S2 대변→차단 + 코스피 수급 나열 — 뻔한 답(N1 개인이 받았다 / N2 기관이 받았다 / N3 외국인이 돌아왔다 / N4 지수 올랐으니 돈이 들어왔다 / N6 새 돈)
# → 외국인(연속일) → 기관·개인, 넷 다 숫자 → '그런데 [화면 지시어] 네 번째 막대' → 기타법인 + 상위 두 종목·자사주 비중 + '9월 들어 매일/N일째'
# → 질문(코스닥은 어땠나). 대체: 기타법인 <3,000억이면 자사주 문장 생략, '기타법인 N억' 한 마디.
# ══════════════════════════════════════════════════════════════════════════════
_S2_Q = ["그럼 코스닥은 어땠을까요?", "그럼 코스닥 쪽은 어땠을까요?", "그럼 코스닥도 같은 그림일까요?", "그럼 코스닥에선 누가 샀을까요?",
         "그럼 코스닥 막대는 어느 쪽일까요?", "그럼 코스닥은 어느 쪽일까요?"]


def _s2(x: dict, cont: dict, pk: Picker, attempt: int) -> tuple[list, dict, str]:
    d, P, sold, vals, oth = x["d"], x["P"], x["sold"], x["vals"], x["oth"]
    pk = ScenePick(pk)
    frg, inst, ind = vals.get("외국인"), vals.get("기관"), vals.get("개인")
    st_f = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
    st_i = abs(((x["streak"].get("inst") or {}).get("streak")) or 0)
    # ── 뻔한 답 고르기 ──
    kinds: list[str] = []
    if ind is not None and ind > 0 and sold:
        kinds.append("N1")
    if inst is not None and inst > 0 and sold and P != "기관":
        kinds.append("N2")
    y = cont.get("yesterday") or {}
    if frg is not None and frg > 0 and (y.get("foreign_streak") or 0) < 0:
        kinds.append("N3")
    if x["chg"] > 0 and ((frg or 0) + (inst or 0)) < -1000:
        kinds.append("N4")
    if oth >= 3000 and x["oth_in_bb"] and x["oth_share"] >= 0.6:
        kinds.append("N6")
    if not kinds:
        kinds = ["N1"] if ind is not None else ["N5"]
    kind = _choose(kinds, _recent_ids(d, "devices"), d, attempt)
    pairs: list[tuple[str, str]] = []
    if kind == "N1":
        naive, naive_name = "개인이 받았다", "개인"
        pairs.append(("naive", pk(["개인이 다 받았다고 보이기 쉽습니다.", "받은 쪽은 개인 하나로 읽히기 쉽습니다.", "개인이 받아 낸 날로 보이기 쉽습니다.",
                                   "개인 몫으로만 읽히기 쉽습니다.", "답은 개인이라고 생각하기 쉽습니다.", "판 물량은 개인이 받았다고 보이기 쉽습니다."])))
    elif kind == "N2":
        naive, naive_name = "기관이 받았다", "기관"
        pairs.append(("naive", pk(["기관이 받아 준 날로 보이기 쉽습니다.", "받은 쪽은 기관으로 읽히기 쉽습니다.", "기관이 받쳤다고 읽히기 쉽습니다.", "기관 몫으로 생각하기 쉽습니다.",
                                   "답은 기관이라고 생각하기 쉽습니다.", "기관이 받은 날로 보이기 쉽습니다."])))
    elif kind == "N3":
        naive, naive_name = "외국인이 돌아왔다", "외국인"
        pairs.append(("naive", pk(["외국인이 돌아온 날로 보이기 쉽습니다.", "외국인 매도가 끝났다고 읽히기 쉽습니다.", "외국인 손이 바뀐 날로 읽히기 쉽습니다.",
                                   "외국인이 다시 들어왔다고 보이기 쉽습니다.", "답은 외국인이라고 생각하기 쉽습니다.", "외국인이 돌아섰다고 읽히기 쉽습니다."])))
    elif kind == "N4":
        naive, naive_name = "지수가 올랐으니 돈이 들어왔다", "코스피"
        pairs.append(("naive", pk(["오른 날이니 돈이 들어왔다고 보이기 쉽습니다.", "지수만 보면 큰손이 산 날로 읽히기 쉽습니다.", "올랐으니 돈이 들어왔다고 읽히기 쉽습니다.",
                                   "상승한 날은 받는 손이 컸다고 보이기 쉽습니다.", "답은 지수라고 생각하기 쉽습니다.", "오른 날이니 산 손이 컸다고 읽히기 쉽습니다."])))
    elif kind == "N6":
        naive, naive_name = "새 돈이 들어왔다", "기타법인"
        pairs.append(("naive", pk(["새 돈이 들어온 날로 보이기 쉽습니다.", "기타법인 막대는 바깥 돈으로 보이기 쉽습니다.", "새 돈이 받쳤다고 읽히기 쉽습니다.",
                                   "네 번째 막대가 새 돈으로 보이기 쉽습니다.", "답은 새 돈이라고 생각하기 쉽습니다.", "바깥 돈이 받친 날로 읽히기 쉽습니다."])))
    else:
        naive, naive_name = "한 손이 다 받았다", "개인"
        pairs.append(("naive", pk(["한 손이 다 받았다고 보이기 쉽습니다.", "받은 손이 하나로 읽히기 쉽습니다.", "막대 하나로 끝난 날로 읽히기 쉽습니다.",
                                   "답은 한 손이라고 생각하기 쉽습니다.", "받은 쪽이 하나로 보이기 쉽습니다.", "한 손이 다 받은 날로 보이기 쉽습니다."])))
    # ── 코스피 수급 나열: 외국인 → 기관·개인 ──
    if frg is not None:
        F, wf = hwon(frg), _word(frg)
        if st_f >= 2:
            pairs.append(("bar:0", pk([f"외국인 {F} {wf}, {dko(st_f)}입니다.", f"외국인 {wf} {F}, {dko(st_f)}입니다.", f"외국인은 {obj(F)} {_verb(frg)}습니다. {dko(st_f)}입니다.",
                                       f"오늘도 외국인은 {F} {wf}, {dko(st_f)}입니다.", f"외국인은 {dko(st_f)}, 오늘 {F} {wf}입니다.", f"외국인 막대는 {F} {wf}, {dko(st_f)}입니다."])))
        else:
            pairs.append(("bar:0", pk([f"외국인 {F} {wf}, 오늘이 첫날입니다.", f"외국인은 {obj(F)} {_verb(frg)}습니다. 방향이 바뀐 날입니다.", f"외국인 {wf} {F}, 오늘 돌아선 손입니다.",
                                       f"외국인은 오늘 {F} {ro(wf)} 방향을 바꿨습니다.", f"외국인 막대는 {F} {wf}, 오늘 뒤집혔습니다.", f"외국인 {F} {wf}, 방향이 바뀐 날입니다."])))
    if inst is not None and ind is not None:
        I_, D_, wi, wd = hwon(inst), hwon(ind), _word(inst), _word(ind)
        pairs.append(("bar:1", pk([f"기관 {I_} {wi}, 개인 {D_} {wd}입니다.", f"기관은 {I_} {wi}, 개인은 {D_} {wd}입니다.", f"기관은 {obj(I_)} {_verb(inst)}고, 개인은 {obj(D_)} {_verb(ind)}습니다.",
                                   f"기관 {I_} {wi}에 개인 {D_} {wd}입니다.", f"기관 {wi} {I_}, 개인 {wd} {D_}입니다.", f"기관 막대 {I_} {wi}, 개인 {D_} {wd}입니다."])))
        if st_i >= 2 and inst < 0:
            pairs.append(("inst_streak", pk([f"기관도 {dko(st_i)} 파는 중입니다.", f"기관 순매도는 {dko(st_i)}입니다.", f"기관 막대도 {dko(st_i)} 같은 색입니다."])))
    # ── 그런데 + 네 번째 막대(기타법인) ──
    obw, ob_capped = _ob_word(cont, d, cont.get("others_buy_days") or 0)
    ob_days = cont.get("others_buy_days") or 0
    top = [{"name": t["name"], "v": t["v"]} for t in x["top_others"]]
    names = _and([t["name"] for t in top]) if top else "두 회사"
    O = hwon(oth)
    is_top = bool(x["buyers"]) and x["buyers"][0][0] == "기타법인"
    days_word = None
    if oth >= 3000:
        pairs.append(("turn", pk(["그런데 맨 오른쪽에 막대가 하나 더 있습니다.", "그런데 네 번째 막대를 보세요.", "그런데 오른쪽 끝에 막대가 하나 더 섭니다.",
                                  "그런데 막대는 셋이 아니라 넷입니다.", "그런데 오른쪽 끝, 네 번째 막대입니다.", "그런데 맨 오른쪽 막대가 남았습니다."])))
        if ob_days >= 2:
            days_word = obw
            if is_top and cont.get("top_buyer_days", 1) >= 2:
                n = cont["top_buyer_days"]
                pairs.append(("reveal", pk([f"기타법인 {O}, {dko(n)} 1위입니다.", f"오늘도 1위는 기타법인, {O}입니다.", f"{dko(n)} 1위는 기타법인 {O}입니다.",
                                            f"기타법인 {O}입니다. {dko(n)} 1위입니다.", f"가장 긴 막대는 기타법인 {O}입니다.", f"기타법인 순매수 {O}, {dko(n)} 맨 위입니다."])))
            elif is_top:
                pairs.append(("reveal", pk([f"기타법인 {O}, {obw} 1위입니다.", f"{obw} 1위는 기타법인 {O}입니다.", f"기타법인 {O}, {obw} 산 쪽입니다.",
                                            f"기타법인 {O}, {obw} 맨 위입니다.", f"1위는 기타법인 {O}, {obw} 같은 색입니다.", f"기타법인 순매수 {O}, {obw} 1위입니다."])))
            else:
                pairs.append(("reveal", pk([f"기타법인도 {obj(O)} 샀습니다. {obw} 이어진 순매수입니다.", f"기타법인 {O}, {obw} 사는 중입니다.", f"네 번째 막대는 기타법인 {O}, {obw}입니다.",
                                            f"기타법인 순매수 {O}, {obw} 이어졌습니다.", f"기타법인 {O}, {obw} 같은 방향입니다.", f"기타법인 {O}, {obw} 산 쪽입니다."])))
        else:
            pairs.append(("reveal", pk([f"가장 많이 산 쪽은 기타법인, {O}입니다." if is_top else f"기타법인 {O}입니다.", f"네 번째 막대는 기타법인, {O}입니다.", f"기타법인이 {obj(O)} 샀습니다.",
                                        f"{O}, 기타법인 몫입니다.", f"오른쪽 끝 막대, 기타법인 {O}입니다.", f"기타법인 순매수는 {O}입니다."])))
        sh = round(x["oth_share"] * 100)
        if top and x["oth_share"] >= 0.5:
            same = cont.get("others_top_same_days") or 0
            tag = " 자사주" if x["oth_in_bb"] else ""
            co = "두 회사" if len(top) == 2 else names
            if same >= 2 and len(top) == 2:
                pairs.append(("top", pk([f"그중 {sh}%가 오늘도 {co}{tag}입니다.", f"{sh}%는 {dko(same)} 같은 {co}{tag}입니다.", f"{co}{tag}가 그 {sh}%입니다.",
                                         f"{sh}%는 오늘도 {co}{tag} 몫입니다.", f"{dko(same)} 같은 {co}{tag}, {sh}%입니다.", f"그중 {sh}%가 {co}{tag} 몫입니다."])))
            else:
                pairs.append(("top", pk([f"그중 {sh}%가 {co}{tag}입니다.", f"{sh}%는 {co}{tag}입니다.", f"{co}{tag} 몫이 {sh}%입니다.", f"막대의 {sh}%가 {co}{tag}입니다.",
                                         f"{co}{tag}, 그 막대의 {sh}%입니다.", f"그 {sh}%가 {co}{tag} 몫입니다."])))
        elif top:
            pairs.append(("top", pk([f"가장 큰 이름은 {top[0]['name']}, {hwon(top[0]['v'])}입니다.", f"기타법인 돈이 가장 많이 간 곳은 {top[0]['name']}입니다.",
                                     f"{top[0]['name']} {subj(hwon(top[0]['v']))} 그 막대의 맨 위입니다."])))
    else:
        pairs.append(("turn", pk([f"그런데 네 번째 막대는 작습니다. 기타법인 {O}입니다.", f"그런데 오른쪽 끝 막대, 기타법인은 {O}뿐입니다.", f"그런데 네 번째 막대를 보세요. 기타법인 {O}에 그쳤습니다.",
                                  f"그런데 기타법인 막대는 {O}, 오늘은 짧습니다."])))
    pairs.append(("q", pk(_S2_Q)))
    bars = [{"name": n, "v": vals.get(n), "days": (st_f if n == "외국인" else st_i if n == "기관" else None) or None}
            for n in ("외국인", "기관", "개인") if vals.get(n) is not None]
    s2 = {"naive": naive, "naive_name": naive_name, "naive_v": vals.get(naive_name) if naive_name != "코스피" else x["chg"], "kind": kind, "bars": bars,
          "reveal": {"name": "기타법인", "v": oth, "days": (0 if ob_capped else ob_days), "days_word": days_word, "top": top, "share": round(x["oth_share"] * 100),
                     "kind": "buyback" if x["oth_in_bb"] else "party"},
          "said_share": any(n == "top" and "%" in t for n, t in pairs), "pairs": pairs}
    return pairs, s2, kind


# ══════════════════════════════════════════════════════════════════════════════
# S3a 코스닥 수급 3주체 + 지수 둘 + 한 줄 판정 + 어제 콜백(도장, 월요일은 주말편 것도) + 그런데(크기 변화) + 질문(어느 업종에서 나갔나).
# 대체: 코스닥 수급 없음 → 지수 둘 + 코스피 판정 + 콜백. 어제 약속 없음 → 콜백 대신 외국인 연속일 사실.
# ══════════════════════════════════════════════════════════════════════════════
_S3A_Q = ["그럼 어느 업종에서 나갔을까요?", "그럼 빠진 돈은 어느 업종일까요?", "그럼 어느 업종에서 빠졌을까요?", "그럼 돈이 빠진 업종은 어디일까요?",
          "그럼 나간 자리는 어느 업종일까요?", "그럼 어느 업종이 팔렸을까요?"]


def _side_words(vals: dict, bb: bool) -> tuple[str, str]:
    sellers = [n for n in ("외국인", "기관", "개인") if (vals.get(n) or 0) < 0]
    buyers = [n for n in ("외국인", "기관", "개인") if (vals.get(n) or 0) > 0]
    if bb:
        buyers.append("자사주")
    return "·".join(sellers), "·".join(buyers)


def _s3a(x: dict, cont: dict, c: dict, pk: Picker) -> tuple[list, dict, list]:
    d, P, sold, amt = x["d"], x["P"], x["sold"], x["amount"]
    kq, kqi, k = x["kq"], x["kqi"], x["k"]
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    kbars = []
    if x["kq_ok"]:
        fq, iq, dq = kq["foreign"], kq["inst"], kq["indiv"]
        kbars = [{"name": "외국인", "v": round(fq)}, {"name": "기관", "v": round(iq)}, {"name": "개인", "v": round(dq)}]
        opp = isinstance(x["vals"].get("외국인"), (int, float)) and (fq > 0) != (x["vals"]["외국인"] > 0)
        FQ, IQ, DQ = hwon(fq), hwon(iq), hwon(dq)
        rel = "반대로" if opp else "같은 쪽으로"
        if (fq > 0) == (iq > 0):
            pairs.append(("kosdaq", pk([f"코스닥 외국인 {FQ}, 기관 {IQ} {_word(fq)}.", f"코스닥은 외국인 {FQ}, 기관 {IQ} {_word(fq)}입니다.",
                                        f"코스닥은 {rel} 외국인 {FQ}, 기관 {IQ} {_word(fq)}.", f"코스닥 쪽, 외국인 {FQ}에 기관 {IQ} {_word(fq)}.",
                                        f"코스닥은 {'반대입니다' if opp else '같은 쪽입니다'}. 외국인 {FQ}, 기관 {IQ}.",
                                        f"코스닥 외국인 {FQ}, 기관 {IQ}, 둘 다 {_word(fq)}."])))
        else:
            pairs.append(("kosdaq", pk([f"코스닥 외국인 {FQ} {_word(fq)}, 기관 {IQ} {_word(iq)}입니다.", f"코스닥은 갈렸습니다. 외국인 {FQ}, 기관 {IQ} {_word(iq)}.",
                                        f"코스닥 외국인 {FQ} {_word(fq)}, 기관은 {IQ} {_word(iq)}.", f"코스닥 쪽은 갈렸습니다. 외국인 {FQ}에 기관 {IQ} {_word(iq)}.",
                                        f"코스닥 외국인 {FQ} {_word(fq)}, 기관 {IQ} {_word(iq)}, 방향이 다릅니다.",
                                        f"코스닥에선 외국인이 {obj(FQ)} {_verb(fq)}고, 기관은 {obj(IQ)} {_verb(iq)}습니다."])))
        pairs.append(("kosdaq_2", pk([f"개인은 {DQ} {_word(dq)}입니다.", f"개인 {DQ} {_word(dq)}입니다.", f"개인은 {obj(DQ)} {_verb(dq)}습니다.",
                                      f"개인 막대는 {DQ} {_word(dq)}.", f"개인 쪽은 {DQ} {_word(dq)}.", f"개인은 {DQ} {_word(dq)}."])))
    kc, qc = _num(k.get("chg_pct")), _num(kqi.get("chg_pct"))
    index = [{"name": "코스피", "close": k.get("close"), "chg_pct": kc}, {"name": "코스닥", "close": kqi.get("close"), "chg_pct": qc}]
    if kc is not None and qc is not None:
        pairs.append(("index", pk([f"코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}입니다.", f"지수는 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.",
                                   f"코스피 {pct_s(kc)} {updn(kc)}에 코스닥 {pct_s(qc)} {updn(qc)}입니다.", f"지수 둘, 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.",
                                   f"코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.", f"오늘 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}."])))
    elif kc is not None:
        pairs.append(("index", pk([f"코스피는 {pct_s(kc)} {'내렸' if kc < 0 else '올랐'}습니다.", f"지수는 코스피 {pct_s(kc)} {updn(kc)}입니다.", f"코스피 {pct_s(kc)} {updn(kc)}으로 끝났습니다."])))
    # 한 줄 판정
    bb = x["oth"] > 0 and bool(x["oth_in_bb"]) and x["oth_share"] >= 0.5
    ks, kb = _side_words(x["vals"], bb)
    ks, kb = ks or "큰손", kb or "아무도"
    if x["kq_ok"]:
        qs, qb = _side_words({"외국인": kq["foreign"], "기관": kq["inst"], "개인": kq["indiv"]}, False)
        qs, qb = qs or "아무도", qb or "아무도"
        v_txt = f"받은 손은 코스피 {kb}, 코스닥 {qb}입니다."
        pairs.append(("verdict", pk([v_txt, f"코스피는 {subj(kb)}, 코스닥은 {subj(qb)} 받았습니다.", f"코스피는 {subj(kb)}, 코스닥은 {subj(qb)} 받은 날입니다.",
                                     f"정리하면 받은 손은 코스피 {kb}, 코스닥 {qb}입니다.", f"코스피에선 {subj(kb)}, 코스닥에선 {subj(qb)} 받았습니다.",
                                     f"한 줄로, 코스피는 {subj(kb)} 받쳤고 코스닥은 {subj(qb)} 받쳤습니다."])))
    else:
        v_txt = f"코스피는 {subj(ks)} 빼고 {subj(kb)} 받은 날입니다."
        pairs.append(("verdict", pk([v_txt, f"한 줄로, {subj(ks)} 팔고 {subj(kb)} 산 날입니다.", f"정리하면 {subj(kb)} 받친 날입니다."])))
    # 어제 콜백(도장) — 없으면 외국인 연속일 사실
    cb = x["cb"]
    promise, result, ok, num = "", "", None, None
    wk_rows: list = []
    if cb and isinstance(cb.get("check"), dict) and cb.get("ok") is not None:
        chk, ok, t = cb["check"], bool(cb["ok"]), cb.get("t")
        num = t
        qn = na._q_noun(cb) or "어제 숫자"
        when = _day_word(d, cb.get("prev_date"), past=True)
        promise = cb.get("q") or qn
        kind = chk.get("kind")
        n = chk.get("n")
        result = ("끊김" if ok else "이어짐") if kind == "kosdaq_break" else ("이어짐" if ok else "끊김")
        qt = f"{qn} {dko(n)}" if (n and kind in ("inv_continue", "theme_continue")) else qn
        pairs.append(("promise", pk([f"{when} 보자고 한 {qt}, 도장은 {result}입니다.", f"{when} 숙제 {qt}, 오른쪽 도장은 {result}.", f"{when} 보자고 한 {qt}, {result}입니다.",
                                     f"오른쪽 카드, {when} 숙제 {qt}는 {result}.", f"{when} 카드의 {J(qt)} {result}, 오른쪽 도장입니다.",
                                     f"{when} 짚어 둔 {qt}, {result}입니다."])))
    else:
        st = x["st_p"]
        promise, result, ok, num = f"{P} {_word(amt)} {dko(max(st, 1))}", "오늘", None, amt
        pairs.append(("promise", pk([f"오른쪽 카드를 보세요. {P} {_word(amt)}는 {dko(max(st, 1))}입니다.", f"{J(P)} {dko(max(st, 1))} 같은 방향, 오른쪽 카드에 그렇게 적힙니다.",
                                     f"오른쪽 카드, {P} {_word(amt)} {dko(max(st, 1))}입니다."])))
    # 어제 숙제가 둘 이상이면 빠짐없이 답한다 — watch[0] 은 위 도장(ledger), watch[1] 부터는 오늘 숫자로 직접 판정(BRIEF_FIX_2 §A).
    # 판정할 수 없는 꼴이면 그 문장은 아예 말하지 않는다. 이 칸은 예산에서 절대 빼지 않는다(GLOBAL_DROP 에 없다).
    answers: list[dict] = []
    for q2 in _prev_watch(d, (cb or {}).get("prev_date") or x["prev_date"])[1:3]:
        r2 = _verify_watch(q2, x, pk)
        if not r2:
            continue
        ok2, txt2 = r2
        if not txt2:
            continue
        pairs.append((f"promise{len(answers) + 2}", txt2))
        answers.append({"q": q2, "ok": ok2, "text": txt2})
    try:
        import weekend_watch
        _also, _said, wk_rows = weekend_watch.block(d, c, done_q=promise)
        for r in wk_rows:
            if r.get("a") and not r.get("merged"):
                a = nh._fix_won(r["a"])
                q_raw = str(r["q"]).strip().rstrip(".")
                pairs.append(("weekend", pk([f"주말에 짚어 둔 {q_raw}, {a}", f"주말 숙제 {q_raw}의 답, {a}", f"주말에 보자고 한 {weekend_watch.obj_q(q_raw)} 보면 {a}"])))
                break
    except Exception:
        wk_rows = []
    # 그런데: 주인공 물량이 어제와 크게 다르면(±25%) — 실제 반전만
    changed = None
    yv = x["y_P"]
    wy = _day_word(d, x["prev_date"], past=True)
    if isinstance(yv, (int, float)) and abs(yv) >= 1000 and (yv < 0) == sold and (abs(amt) <= 0.75 * abs(yv) or abs(amt) >= 1.25 * abs(yv)):
        grew = abs(amt) > abs(yv)
        changed = {"label": "크기", "before": f"{P} {hshort(yv)}", "after": f"{P} {hshort(amt)}", "before_label": wy}
        pairs.append(("turn", pk([f"그런데 {P} 물량은 {wy} {hwon(yv)}에서 {ro(hwon(amt))} {'불었' if grew else '줄었'}습니다.", f"그런데 크기는 {'커졌' if grew else '작아졌'}습니다. {wy} {hwon(yv)}, 오늘 {hwon(amt)}.",
                                  f"그런데 같은 손인데 막대는 {'길어졌' if grew else '짧아졌'}습니다. {hwon(yv)}에서 {hwon(amt)}.", f"그런데 {P} 막대가 {wy}보다 {'깁니다' if grew else '짧습니다'}. {hwon(yv)}에서 {hwon(amt)}."])))
    pairs.append(("q", pk(_S3A_Q)))
    return pairs, {"kosdaq": {"bars": kbars} if kbars else None, "index": index, "verdict": v_txt, "promise": promise, "result": result, "ok": ok, "num": num,
                   "answers": answers, "changed": changed, "head": "어제 보자고 한 것" if cb else "오늘의 손", "pairs": pairs}, wk_rows


# ══════════════════════════════════════════════════════════════════════════════
# S3b 돈이 빠진 곳·정체된 곳 — 유출 1위 업종(외/기 분리, N일째, 어제 대비) + '왼쪽 막대' + 대장주 등락(값은 안 빠졌는데 돈은 나감) + 자사주 받침
# + 나머지 유출 2~3개 → 질문(그 돈은 어디로 들어갔나). 대체: 유출 업종이 없으면 '빠진 업종이 없었다' + 가장 덜 들어온 곳.
# ══════════════════════════════════════════════════════════════════════════════
_S3B_Q = ["그럼 그 돈은 어디로 갔을까요?", "그럼 나간 돈은 어디로 갔을까요?", "그럼 들어온 쪽은 어디였을까요?", "그럼 돈이 옮겨 간 곳은 어디일까요?",
          "그럼 받은 업종은 어디였을까요?", "그럼 그 돈을 누가 받았을까요?"]


def _leaders(x: dict, th: str, n: int = 2) -> list[dict]:
    """업종의 거래대금 상위 n종목 등락 — flow_day 종목행, 없으면 거래대금 상위 20 종목 수급(stock_flows) 가운데 그 업종 종목."""
    rows = (x["themes"].get(th) or {}).get("stocks") or []
    if rows:
        top = sorted([r for r in rows if _num(r.get("ret")) is not None], key=lambda r: -(_num(r.get("value")) or 0))[:n]
        return [{"name": r["name"], "pct": float(r["ret"]), "code": r.get("code")} for r in top if r.get("name")]
    try:
        from app.services.themes import CODE_THEME
    except Exception:
        return []
    out = [{"name": r.get("name"), "pct": float(r["pct"]), "code": code} for code, r in x["sflows"].items()
           if isinstance(r, dict) and CODE_THEME.get(code) == th and _num(r.get("pct")) is not None and r.get("name")]
    return sorted(out, key=lambda r: -(_num((x["sflows"].get(r["code"]) or {}).get("value_mn")) or 0))[:n]


def _theme_codes(th: str) -> set[str]:
    try:
        from app.services.themes import THEME_CODES
        return set(THEME_CODES.get(th) or [])
    except Exception:
        return set()


def _s3b(x: dict, pk: Picker) -> tuple[list, dict]:
    d = x["d"]
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    outs, themes = x["outs"], x["themes"]
    leaders, support = [], None
    if not outs:
        least = min(x["ins"], key=lambda t: themes[t]["net"]) if x["ins"] else None
        pairs.append(("head", pk(["오늘은 빠진 업종이 없었습니다. 왼쪽 막대가 비어 있습니다.", "돈이 빠진 곳은 없었습니다. 업종 표가 전부 순매수입니다.", "나간 곳이 없는 날입니다. 왼쪽 막대를 보세요, 비어 있습니다."])))
        if least:
            pairs.append(("y", pk([f"가장 덜 들어온 곳은 {tname(least)}, {hwon(themes[least]['net'])}입니다.", f"가장 짧은 막대는 {tname(least)} {hwon(themes[least]['net'])}입니다.",
                                   f"{subj(tname(least))} 가장 적게 받았습니다. {hwon(themes[least]['net'])}입니다."])))
        pairs.append(("q", pk(_S3B_Q)))
        return pairs, {"out": [], "leaders": [], "support": None, "pairs": pairs}
    th = outs[0]
    r = themes[th]
    T = hwon(r["net"])
    F = hwon(r["foreign"]) if _num(r.get("foreign")) is not None else None
    I = hwon(r["inst"]) if _num(r.get("inst")) is not None else None
    stk = abs(int(r.get("streak") or 0)) if (r.get("streak") or 0) < 0 else 0
    tn = tname(th)
    if F is not None and I is not None:
        fo, io = r["foreign"], r["inst"]
        if fo < 0 and io < 0:
            # 머리 문장은 어느 후보를 골라도 '빠졌|나갔|순매도'를 달고 나온다 — 합계(sum)가 예산에서 빠져도 s3b 가 뜻을 잃지 않는다(qa_script.S3B_OUT)
            pairs.append(("head", pk([f"{tn} 막대에서 외국인 {F}, 기관 {subj(I)} 빠졌습니다.", f"{tn} 막대는 외국인 {F}, 기관 {I} 순매도입니다.", f"빠진 곳은 {tn}, 막대는 외국인 {F}에 기관 {I} 순매도.",
                                      f"나간 돈 1위 막대는 {tn}, 외국인 {F}, 기관 {I} 순매도.", f"가장 긴 막대는 {tn}, 외국인 {F}에 기관 {subj(I)} 빠졌습니다.",
                                      f"가장 큰 유출 막대는 {tn}, 외국인 {F}, 기관 {I} 순매도."])))
        else:
            big = ("외국인", fo, "기관", io) if fo < io else ("기관", io, "외국인", fo)
            pairs.append(("head", pk([f"돈이 빠진 곳은 {tn}입니다. {big[0]} {hwon(big[1])} 순매도, {big[2]}은 {hwon(big[3])} {_word(big[3])}입니다.",
                                      f"나간 돈 1위는 {tn}, {big[0]} {hwon(big[1])} 순매도, {big[2]} {hwon(big[3])} {_word(big[3])}.",
                                      f"{tn}에서 돈이 빠졌습니다. 뺀 쪽은 {big[0]} {hwon(big[1])} 순매도, {big[2]}은 {hwon(big[3])} {_word(big[3])}입니다."])))
    else:
        pairs.append(("head", pk([f"{tn}에서 돈이 빠졌습니다.", f"나간 돈 1위는 {tn}, 여기서 빠졌습니다.", f"빠진 자리부터, {tn}에서 나갔습니다.",
                                  f"돈이 가장 많이 빠진 곳, {tn}에서 나갔습니다."])))
    wy = _day_word(d, x["prev_date"], past=True)
    if stk >= 2:
        pairs.append(("sum", pk([f"왼쪽 막대, 합쳐 {subj(T)} {dko(stk)} 나갔습니다.", f"왼쪽 막대, 합쳐 {T} {dko(stk)} 순매도입니다.", f"왼쪽 막대를 보세요. 합쳐 {T} {dko(stk)} 순매도입니다.",
                                 f"둘을 더하면 {T}, 왼쪽 막대가 {dko(stk)} 나갔습니다.", f"왼쪽 막대, 합계 {subj(T)} {dko(stk)} 빠졌습니다.",
                                 f"{subj(T)} {dko(stk)} 나갔습니다. 왼쪽 막대입니다."])))
    else:
        pairs.append(("sum", pk([f"왼쪽 막대, 합쳐 {subj(T)} 나갔습니다.", f"둘을 더하면 {T}, 왼쪽 막대가 나갔습니다.", f"왼쪽 막대, 합계 {T} 순매도입니다."])))
    yv = _num(r.get("y"))
    if yv is not None and yv < 0 and abs(yv) >= 100:
        Y = hwon(yv)
        if abs(r["net"]) <= 0.8 * abs(yv):
            pairs.append(("y", pk([f"{wy} {Y}보다는 줄었습니다.", f"{wy} {Y}에서 줄어든 크기입니다.", f"{J(wy)} {Y}였으니 짧아진 쪽입니다.", f"{wy} {Y}보다 짧아진 막대입니다."])))
        elif abs(r["net"]) >= 1.25 * abs(yv):
            pairs.append(("y", pk([f"{wy} {Y}보다 늘었습니다.", f"{wy} {Y}에서 불어난 크기입니다.", f"{wy}보다 길어진 막대, {Y}에서입니다."])))
        else:
            pairs.append(("y", pk([f"{wy} {J(Y, '과', '와')} 비슷한 크기입니다.", f"{wy} {Y}, 거의 그대로입니다.", f"{wy} {J(Y, '과', '와')} 같은 길이입니다."])))
    elif yv is not None and yv > 0:
        pairs.append(("y", pk([f"{J(wy)} {hwon(yv)} 순매수였습니다.", f"{J(wy)} 받았던 자리입니다. {hwon(yv)}, 막대 색이 바뀌었습니다.", f"{wy} {hwon(yv)} 순매수에서 오늘 순매도로 돌아섰습니다."])))
    # 그런데: 대장주 등락 — 값은 안 빠졌는데 돈은 나감 / 값도 같이 밀림
    leaders = _leaders(x, th)
    if leaders:
        a = leaders[0]
        b = leaders[1] if len(leaders) > 1 else None
        small = all(abs(l["pct"]) < 1.0 for l in leaders)
        if b:
            if small:
                pairs.append(("turn", pk([f"그런데 {J(a['name'])} {pct1(a['pct'])}, {J(b['name'])} {pct1(b['pct'])} {'내렸을' if a['pct'] < 0 else '움직였을'} 뿐입니다.",
                                          f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}뿐입니다.",
                                          f"그런데 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}, 값은 버텼습니다.",
                                          f"그런데 {a['name']} {pct1(a['pct'])}, {b['name']} {pct1(b['pct'])} {'하락' if a['pct'] < 0 else '등락'}뿐입니다.",
                                          f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
            elif a["pct"] < 0 and (b["pct"] < 0):
                pairs.append(("turn", pk([f"그런데 값도 같이 밀려 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}, 값까지 같이 빠진 자리입니다.",
                                          f"그런데 돈도 값도 나간 자리, {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩도 같은 색, {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다."])))
            elif a["pct"] > 0 and b["pct"] > 0:
                # 돈은 빠졌는데 값은 오른 날 — 받은 쪽이 따로 있다는 뜻이다(9/16: 외국인이 팔고 기관이 받았다).
                # 까닭을 먼저 말하고 '그런데'로 닫는다 — 블록 끝은 '그런데' 문장이나 질문이어야 한다(정본 체크리스트 ⑤).
                _who = "기관" if (x["themes"].get(th) or {}).get("inst", 0) > 0 else ""
                if _who:
                    pairs.append(("turn_why", pk([f"판 쪽은 외국인이고, 받은 쪽은 {_who}입니다.",
                                                  f"{_who}이 그 물량을 받았습니다.",
                                                  f"외국인이 내놓은 걸 {_who}이 받았습니다.",
                                                  f"받은 쪽에 {_who}이 있었습니다."])))
                pairs.append(("turn", pk([f"그런데 값은 올랐습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 반대입니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 값은 거꾸로 갔습니다. {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 판 쪽 값이 올랐습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
            else:
                pairs.append(("turn", pk([f"그런데 값은 갈렸습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 서로 다릅니다. {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 두 종목 값이 엇갈렸습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 값은 한 방향이 아닙니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
        else:
            pairs.append(("turn", pk([f"그런데 {J(a['name'])} {pct1_dir(a['pct'])}{'에 그쳤습니다' if small else '입니다'}.", f"그런데 대장주 {a['name']}의 값은 {pct1_dir(a['pct'])}입니다.",
                                      f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}{'뿐입니다' if small else '입니다'}."])))
        codes = _theme_codes(th) | {l.get("code") for l in leaders if l.get("code")}
        bb = [t for t in x["top_others"] if t.get("code") in codes and t.get("code") in x["act"]]
        if bb and small:
            S = hwon(sum(t["v"] for t in bb))
            support = {"label": "자사주", "v": round(sum(t["v"] for t in bb))}
            two = "두 회사" if len(bb) == 2 else bb[0]["name"]
            pairs.append(("support", pk([f"그 물량은 자사주 {subj(S)} 받쳤습니다.", f"받친 돈은 {two} 자사주 {S}입니다.", f"{two} 자사주 {subj(S)} 받아 냈습니다.",
                                         f"값을 붙든 건 {two} 자사주 {S}입니다.", f"{two} 자사주 {subj(S)} 받은 자리입니다.", f"자사주 {S}, 그 물량을 받은 돈입니다."])))
            pairs.append(("meaning", pk(["돈이 정체된 자리는 여기입니다.", "정체된 돈이 고인 곳이 여기입니다.", "값은 서 있고 돈은 나가는 자리, 정체는 여기입니다.", "돈은 나가는데 값이 안 밀리는 자리, 여기가 정체입니다."])))
        elif small:
            pairs.append(("meaning", pk(["돈은 나갔는데 값은 서 있는 자리입니다.", "값과 돈이 따로 노는 자리, 정체는 여기입니다.", "나간 돈만큼 값이 밀리지 않은 자리입니다."])))
    else:
        rt = _num(r.get("ret"))
        pairs.append(("turn", pk([f"그런데 {tn} 값은 {pct1_dir(rt)}{'에 그쳤습니다' if abs(rt) < 1 else '입니다'}." if rt is not None else "그런데 이 막대 하나가 오늘 유출의 대부분입니다.",
                                  f"그런데 업종 등락은 {pct1_dir(rt)}입니다." if rt is not None else "그런데 나머지 막대는 이보다 훨씬 짧습니다."])))
    out_rows = [{"theme": t, "v": round(themes[t]["net"]), "foreign": themes[t].get("foreign"), "inst": themes[t].get("inst"), "ret": themes[t].get("ret"),
                 "streak": themes[t].get("streak"), "y": themes[t].get("y")} for t in outs[:4]]
    rest = [t for t in outs[1:4] if abs(themes[t]["net"]) >= 100]
    if len(rest) >= 2:
        t2, t3 = rest[0], rest[1]
        V2, V3 = hwon(themes[t2]["net"]), hwon(themes[t3]["net"])
        if V2 == V3:
            pairs.append(("others", pk([f"{J(tname(t2), '과', '와')} {tname(t3)}에서 {V2}씩도 빠졌습니다.", f"{tname(t2)}, {tname(t3)}에서도 {V2}씩 나갔습니다.", f"{J(tname(t2), '과', '와')} {tname(t3)}도 {V2}씩 순매도입니다."])))
        else:
            pairs.append(("others", pk([f"{tname(t2)}에서 {V2}, {tname(t3)}에서 {V3} 더 빠졌습니다.", f"{tname(t2)} {V2}, {tname(t3)} {V3}도 나갔습니다.", f"그다음이 {tname(t2)} {V2}, {tname(t3)} {V3}입니다.",
                                        f"{J(tname(t2), '과', '와')} {tname(t3)}도 {V2}, {V3} 순매도입니다."])))
        if len(rest) >= 3:
            t4 = rest[2]
            pairs.append(("others2", pk([f"{tname(t4)} {hwon(themes[t4]['net'])}도 빠졌습니다.", f"{tname(t4)}에서도 {subj(hwon(themes[t4]['net']))} 나갔습니다.", f"{tname(t4)} {hwon(themes[t4]['net'])}까지 순매도입니다."])))
    elif len(rest) == 1:
        t2 = rest[0]
        pairs.append(("others", pk([f"{tname(t2)}에서도 {subj(hwon(themes[t2]['net']))} 빠졌습니다.", f"그다음은 {tname(t2)}, {hwon(themes[t2]['net'])}입니다.", f"{tname(t2)} {hwon(themes[t2]['net'])}도 나갔습니다."])))
    pairs.append(("q", pk(_S3B_Q)))
    return pairs, {"out": out_rows, "leaders": [{"name": l["name"], "pct": l["pct"]} for l in leaders], "support": support, "pairs": pairs}


# ══════════════════════════════════════════════════════════════════════════════
# S3c 돈이 들어온 곳 — 이동 선언 1회 + 유입 상위 2 업종(외/기 분리, 등락, 순매수 종목 ≤4, N일째) + 유출 1위 대비 비율('16분의 1') → 질문(그 안에서 누가 샀나).
# 대체: 유입 업종 없음 → '들어온 곳이 없었습니다. 가장 덜 빠진 곳은 …' + '전부 유출'.
# ══════════════════════════════════════════════════════════════════════════════
_S3C_Q = ["그럼 그 안에서 누가 샀을까요?", "그럼 그 업종 안에선 누가 샀을까요?", "그럼 종목으로는 누가 샀을까요?", "그럼 누가 그 종목을 샀을까요?",
          "그럼 종목 표에선 누가 샀을까요?", "그럼 대장주는 누가 샀을까요?"]


def _s3c(x: dict, pk: Picker) -> tuple[list, dict]:
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    ins, themes = x["in_ths"], x["themes"]
    in_rows, ratio = [], None
    if not ins:
        least = max(x["outs"], key=lambda t: themes[t]["net"]) if x["outs"] else None
        pairs.append(("move", pk(["이번엔 들어온 쪽입니다.", "여기까지가 나간 돈, 이제 들어온 돈입니다.", "이제 받은 쪽 표로 갑니다.", "나간 자리 다음은 들어온 자리입니다."])))
        pairs.append(("head", pk(["들어온 곳이 없었습니다. 업종 전부 유출입니다.", "오늘은 받은 업종이 없습니다. 막대가 전부 유출 쪽입니다.", "들어온 막대가 하나도 없는 날입니다. 전부 유출입니다."])))
        if least:
            pairs.append(("t1", pk([f"가장 짧은 막대는 {tname(least)}, {hwon(themes[least]['net'])}입니다.", f"가장 덜 빠진 막대는 {tname(least)} {hwon(themes[least]['net'])}입니다.",
                                    f"그나마 덜 나간 곳이 {tname(least)} {hwon(themes[least]['net'])}입니다.",
                                    f"{subj(tname(least))} 가장 적게 빠졌습니다. {hwon(themes[least]['net'])}입니다."])))
        pairs.append(("q", pk(_S3C_Q)))
        return pairs, {"in": [], "ratio": None, "pairs": pairs}
    a = ins[0]
    b = ins[1] if len(ins) > 1 else None
    ra, rb = themes[a], (themes[b] if b else None)
    ta, tb = tname(a), (tname(b) if b else None)
    if b:
        pairs.append(("move", pk([f"들어온 쪽은 {J(ta, '과', '와')} {tb}입니다.", f"이번엔 들어온 쪽, {J(ta, '과', '와')} {tb}입니다.", f"받은 쪽은 {J(ta, '과', '와')} {tb}입니다.",
                                  f"들어온 막대는 {J(ta, '과', '와')} {tb}입니다.", f"받은 업종은 {J(ta, '과', '와')} {tb}입니다.",
                                  f"이번엔 받은 쪽, {J(ta, '과', '와')} {tb}입니다."])))
    else:
        pairs.append(("move", pk([f"들어온 쪽은 {ta} 하나입니다.", f"이번엔 들어온 쪽, {ta} 하나입니다.", f"받은 업종은 {ta}뿐입니다.", f"나간 돈 다음은 들어온 돈, {ta} 하나입니다."])))
    for tag, th, r, tn in (("t1", a, ra, ta), ("t2", b, rb, tb)):
        if not th:
            continue
        T = hwon(r["net"])
        F = hwon(r["foreign"]) if _num(r.get("foreign")) is not None else None
        I = hwon(r["inst"]) if _num(r.get("inst")) is not None else None
        ret = _num(r.get("ret"))
        RT = f"{pct1(ret)} {'올랐' if ret > 0 else '내렸'}" if ret is not None else None
        RS = f"{pct1(ret)} {updn(ret)}" if ret is not None else None
        if F is not None and I is not None:
            fo, io = r["foreign"], r["inst"]
            if fo > 0 and io > 0:
                if tag == "t1":
                    pairs.append((tag, pk([f"{tn} 막대에 외국인 {F}, 기관 {subj(I)} 들어왔습니다.", f"{tn} 막대, 외국인 {F}에 기관 {I} 순매수.", f"{tn} 막대는 외국인 {F}, 기관 {I} 순매수.",
                                           f"{tn} 막대를 보세요. 외국인 {F}, 기관 {I} 순매수.", f"{tn} 막대는 두 색, 외국인 {F}에 기관 {I} 순매수.",
                                           f"막대의 두 색, {tn} 외국인 {F}, 기관 {I} 순매수."])))
                else:
                    pairs.append((tag, pk([f"{J(tn)} 외국인 {F}, 기관 {I} 순매수입니다.", f"{tn}에는 외국인 {F}, 기관 {I} 순매수.", f"{tn}에 외국인 {F}, 기관 {subj(I)} 들어왔습니다.",
                                           f"{J(tn)} 외국인 {F}에 기관 {I} 순매수입니다.", f"{tn} 쪽은 외국인 {F}, 기관 {I} 순매수.", f"{tn}에도 외국인 {F}, 기관 {I} 순매수."])))
            else:
                who, wv, other, ov = ("외국인", fo, "기관", io) if fo > io else ("기관", io, "외국인", fo)
                if tag == "t1":
                    pairs.append((tag, pk([f"{tn} 막대를 보세요. {who} {hwon(wv)} 순매수, {other}은 {hwon(ov)} {_word(ov)}.", f"{J(tn)} {who}이 {obj(hwon(wv))} 넣었고, {other}은 {hwon(ov)} {_word(ov)}입니다.",
                                           f"{tn} 막대는 {who} {subj(hwon(wv))} 세웠습니다. {other}은 {hwon(ov)} {_word(ov)}."])))
                else:
                    pairs.append((tag, pk([f"{tn}에는 {who} {hwon(wv)} 순매수, {other} {hwon(ov)} {_word(ov)}.", f"{J(tn)} {who}이 {hwon(wv)}, {other}이 {hwon(ov)}입니다."])))
            if RT:
                pairs.append((f"{tag}_sum", pk([f"합쳐 {T} 순매수, {RS}.", f"합쳐 {T}, 업종은 {RT}습니다.", f"둘을 더해 {T}, {RS}입니다.", f"합계 {T}에 값은 {RT}습니다.", f"{subj(T)} 들어왔고 {RT}습니다.", f"합계 {T} 순매수, 업종은 {RS}."])))
            else:
                pairs.append((f"{tag}_sum", pk([f"합쳐 {subj(T)} 들어왔습니다.", f"둘을 더하면 {T}입니다.", f"합계 {T}입니다."])))
        else:
            if RT:
                pairs.append((tag, pk([f"{tn} 막대를 보세요. {subj(T)} 들어왔고, {RT}습니다.", f"{tn}에 {T}, 업종은 {RT}습니다.", f"{tn} 막대는 {T}, 값은 {RT}습니다."])))
            else:
                pairs.append((tag, pk([f"{tn} 막대를 보세요. {subj(T)} 들어왔습니다.", f"{tn}에 {T}입니다.", f"{tn} 막대는 {T}입니다."])))
        names = [n for n in (r.get("pos_names") or []) if n][:4]
        n_all = r.get("n")
        if tag == "t1" and names:
            if n_all and len(names) >= n_all and n_all >= 2:
                pairs.append(("names", pk([f"{_and(names)} {han(len(names))} 종목 모두 순매수였습니다.", f"{_and(names)}, {han(len(names))} 종목 전부 받았습니다.", f"{han(len(names))} 종목 {subj(_and(names))} 다 순매수입니다."])))
            elif len(names) >= 2:
                pairs.append(("names", pk([f"종목은 {_and(names)}입니다.", f"{_and(names)}에 몰렸습니다.", f"{_and(names)} 순매수입니다."])))
            else:
                pairs.append(("names", pk([f"종목은 {names[0]} 하나에 몰렸습니다.", f"받은 종목은 {names[0]}입니다.", f"{names[0]} 한 종목이 받았습니다."])))
        # 오늘 이슈로 꼽힌 종목이 이 업종 안에 있으면 한 마디로 잇는다(BRIEF_FIX_2 §D-1) — 예산에서 빼지 않는다
        if tag == "t1" and not x.get("issue_said"):
            pool = set(names) | {str(s.get("name")) for s in (r.get("stocks") or []) if isinstance(s, dict) and s.get("name")}
            hit = next((n for n in _issue_names(x) if n in pool), None)
            if hit:
                x["issue_said"] = hit
                pairs.append(("issue", pk([f"{subj(hit)} 그 이슈 종목입니다.", f"{subj(hit)} 오늘 이슈 종목입니다.",
                                           f"{hit}, 그 이슈 종목입니다.", f"{hit}, 오늘 이슈 종목입니다.",
                                           f"이 가운데 {subj(hit)} 이슈 종목입니다.", f"{subj(hit)} 오늘 이슈로 꼽힌 종목입니다."])))
        stk = int(r.get("streak") or 0)
        if tag == "t1" and stk >= 2:
            pairs.append(("streak", pk([f"{dko(stk)} 이어진 유입입니다.", f"{dko(stk)} 같은 자리에 돈이 들어오는 중입니다.", f"하루짜리가 아니라 {dko(stk)} 쌓이는 돈입니다."])))
        in_rows.append({"theme": th, "v": round(r["net"]), "foreign": r.get("foreign"), "inst": r.get("inst"), "ret": r.get("ret"), "names": names, "streak": stk})
    # 유출 1위 대비 비율
    if x["out_th"] and x["out_t"]:
        in_sum = sum(themes[t]["net"] for t in ins)
        O, IS = hwon(x["out_t"]), hwon(in_sum)
        on = tname(x["out_th"])
        frac = _calc("fraction", in_sum, x["out_t"])
        two = "둘을 합치면" if b else "여기 들어온 돈은"
        if frac:
            kk = frac["n"]
            ratio = {"out_theme": x["out_th"], "out": round(x["out_t"]), "in": round(in_sum), "text": f"{kk}분의 1"}
            pairs.append(("ratio", pk([f"합쳐 {IS}, {on} 유출의 {kk}분의 1입니다.", f"들어온 {IS}, {on} 유출의 {kk}분의 1입니다.", f"합쳐 {IS}인데 {on} 유출의 {kk}분의 1입니다.",
                                       f"{on}에서 나간 돈에 견주면 {kk}분의 1입니다.", f"{IS}, {on} 유출의 {kk}분의 1 크기입니다.",
                                       f"{two} {IS}, {on} 유출의 {kk}분의 1입니다."])))
            pairs.append(("ratio_2", pk(["옮겨간 돈보다 나간 돈이 훨씬 큽니다.", "돈은 옮겨간 게 아니라 나간 쪽이 큽니다.", "들어온 돈은 나간 돈의 조각입니다.", "나간 막대가 들어온 막대를 압도합니다."])))
        else:
            pct = round(in_sum / abs(x["out_t"]) * 100)
            ratio = {"out_theme": x["out_th"], "out": round(x["out_t"]), "in": round(in_sum), "text": f"{pct}%"}
            if pct >= 100:
                pairs.append(("ratio", pk([f"{on}에서 나간 {O}보다 들어온 {subj(IS)} 큽니다.", f"들어온 {subj(IS)} {on} 유출 {obj(O)} 넘습니다.", f"나간 {on} {O}보다 들어온 {subj(IS)} 더 큰 날입니다."])))
            else:
                pairs.append(("ratio", pk([f"{on}에서 나간 {O}에 견주면 들어온 돈은 {pct}%입니다.", f"{two} {IS}, {on} 유출의 {pct}%입니다.", f"나간 돈 {O} 가운데 {pct}%만큼이 옮겨 왔습니다."])))
    pairs.append(("q", pk(_S3C_Q)))
    return pairs, {"in": in_rows, "ratio": ratio, "pairs": pairs}


# ══════════════════════════════════════════════════════════════════════════════
# S4 1차 자료 한 칸 — '직접 열어봤습니다, 키움 종목별 투자자 표, M월 D일 마감 기준' + 대장주 1 + 최대 상승 1(등락·외/기/개·거래대금) + 계산 1개(검산)
# + '누가 밀어 올렸나'. 대체: brief_stocks 없음 → flow_day 종목행(외/기·등락·거래대금만, 개인은 말하지 않음, no_indiv), 계산은 외+기 ÷ 거래대금.
# ══════════════════════════════════════════════════════════════════════════════
def _aw(n: str, v: float) -> str:
    """'기관 150억 순매수' / 0 이면 '기관 순매수 없음'."""
    return f"{n} 순매수 없음" if abs(v) < 0.5 else f"{n} {hwon(v)} {_word(v)}"


def _driver(s: dict) -> tuple[str, float]:
    """가장 많이 산 주체(이름, 값). 셋 다 순매도면 가장 덜 판 쪽."""
    cands = [(n, _num(s.get(k))) for n, k in (("외국인", "foreign"), ("기관", "inst"), ("개인", "indiv")) if _num(s.get(k)) is not None]
    return max(cands, key=lambda t: t[1]) if cands else ("외국인", 0.0)


def _pick_stocks(x: dict) -> tuple[list[dict], str, bool]:
    """(종목 둘, 업종, brief_stocks 에서 왔는가). §2: 유입 업종 없으면 유출 1위 대장주 + 그 업종에서 가장 덜 내린 종목."""
    bs = x["bstocks"]
    if bs:
        lead = next((s for s in bs if s.get("role") == "대장주"), bs[0])
        top = next((s for s in bs if s is not lead), None)
        return [lead] + ([top] if top else []), x["btheme"] or lead.get("theme") or "", True
    th = x["in_th"] or x["out_th"]
    if not th:
        return [], "", False
    rows = [r for r in ((x["themes"].get(th) or {}).get("stocks") or []) if r.get("name") and _num(r.get("ret")) is not None]
    if not rows:
        return [], th, False
    leader_code = next((s.get("leader") for s in (x["flow_day"].get("sectors") or []) if s.get("theme") == th), None)
    lead = next((r for r in rows if r.get("code") == leader_code), None) or max(rows, key=lambda r: _num(r.get("value")) or 0)
    others = [r for r in rows if r is not lead]
    top = max(others, key=lambda r: r["ret"]) if others else None
    conv = lambda r, role: {"code": r.get("code"), "name": r["name"], "role": role, "theme": th, "pct": float(r["ret"]), "foreign": r.get("foreign"), "inst": r.get("inst"),
                            "indiv": None, "value": r.get("value"), "close": r.get("close")}
    return [conv(lead, "대장주")] + ([conv(top, "최대 상승" if x["in_th"] else "가장 덜 내림")] if top else []), th, False


def _s4(x: dict, pk: Picker) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    day = f"{int(d[4:6])}월 {int(d[6:8])}일"
    doc = f"키움 종목별 투자자 표 · {int(d[4:6])}/{int(d[6:8])} 마감 기준"
    pairs: list[tuple[str, str]] = []
    pairs.append(("open", pk([f"{day} 종목별 투자자 표를 직접 열어봤습니다.", f"{day} 마감 종목별 투자자 표를 직접 열어봤습니다.", f"{day} 키움 종목별 투자자 표를 직접 열어봤습니다.",
                              f"키움 종목별 투자자 표를 직접 열어봤습니다.", f"{day} 마감 표를 직접 열어봤습니다.", f"{day} 마감, 종목별 투자자 표를 직접 열어봤습니다."])))
    stocks, th, full = _pick_stocks(x)
    calc, kind = None, "K0"
    rows_out = []
    if not stocks:
        pairs.append(("row:0", pk(["오늘은 종목 표가 비어 있습니다. 업종 합계까지만 확정입니다.", "종목 칸은 집계 대기입니다. 위 칸의 업종 숫자까지가 확정입니다.", "종목별 칸은 오늘 비어 있어 업종 표까지만 봅니다."])))
        pairs.append(("calc", pk(["확정치가 오면 이 칸에서 계산을 다시 합니다.", "숫자가 오면 같은 자리에서 비율을 셉니다.", "이 칸은 다음 편에 다시 채웁니다."])))
        return pairs, {"doc": doc, "date": day, "stocks": [], "calc": None, "kind": kind, "full": full, "no_indiv": True, "pairs": pairs}, kind
    tn = tname(th)
    for i, s in enumerate(stocks):
        name, pct = s["name"], _num(s.get("pct"))
        fo, io, dv, val = _num(s.get("foreign")), _num(s.get("inst")), _num(s.get("indiv")), _num(s.get("value"))
        role = s.get("role") or ("대장주" if i == 0 else "최대 상승")
        P1 = f"{pct2(pct)} {'올랐' if pct > 0 else '내렸'}" if pct is not None else None
        PD = f"{pct2(pct)} {updn(pct)}" if pct is not None else ""
        # 이 종목이 오늘 이슈 종목이면 그 줄에 한 번만 표시한다(BRIEF_FIX_2 §D-2) — s3c 가 이미 이슈를 말했으면 생략
        iss = bool(name in _issue_names(x) and not x.get("issue_said"))
        if iss:
            x["issue_said"] = name
        if i == 0:
            pairs.append((f"row:{i}", pk(([f"위 칸, 이슈 종목인 {J(name)} {P1}습니다.", f"위 칸, {tn} 대장주이자 이슈 종목 {name} {PD}입니다.",
                                           f"이슈 종목인 {J(name)} {P1}습니다. 위 칸입니다.", f"위 칸을 보세요. 이슈 종목 {name} {PD}.",
                                           f"위 칸, 오늘 이슈 종목 {name} {PD}."] if iss else
                                          [f"위 칸, {tn} 대장주 {J(name)} {P1}습니다.", f"위 칸, {tn} 대장주 {name} {PD}입니다.", f"위 칸의 {tn} 대장주 {J(name)} {P1}습니다.",
                                           f"{tn} 대장주 {J(name)} {P1}습니다. 위 칸입니다.", f"위 칸을 보세요. {tn} 대장주 {name} {PD}.", f"위 칸, {tn} 대장주 {name} {PD}."])) if P1 else
                          pk([f"위 칸, {tn} 대장주 {name}입니다.", f"위 칸을 보세요. {tn} 대장주 {name}입니다.", f"위 칸의 {tn} 대장주는 {name}입니다."])))
        else:
            lim = pct is not None and pct >= 29.5
            rl = "최대 상승" if role == "최대 상승" else "가장 덜 내린 종목" if role == "가장 덜 내림" else "둘째 종목"
            if iss and pct is not None:
                pairs.append((f"row:{i}", pk([f"아래 칸, 이슈 종목인 {J(name)} {'상한가 ' if lim else ''}{pct2(pct)}입니다.",
                                              f"아래 칸, 이슈 종목 {name} {'상한가 ' if lim else ''}{pct2(pct)}입니다.",
                                              f"아래 칸은 {name}, 이슈 종목이자 {rl}입니다.",
                                              f"아래 칸의 이슈 종목 {J(name)} {'상한가 ' if lim else ''}{pct2(pct)}입니다.",
                                              f"아래 칸은 이슈 종목 {name}, {'상한가 ' if lim else ''}{PD}."])))
            else:
                pairs.append((f"row:{i}", pk([f"{J(rl)} {name}, {'상한가 ' if lim else ''}{pct2(pct)}입니다." if pct is not None else f"{J(rl)} {name}입니다.",
                                              f"아래 칸, {rl} {name} {'상한가 ' if lim else ''}{pct2(pct)}입니다." if pct is not None else f"아래 칸, {rl} {name}입니다.",
                                              f"{name}, {rl}입니다. {'상한가 ' if lim else ''}{PD}." if pct is not None else f"{name}, {rl}입니다.",
                                              f"아래 칸의 {J(name)} {'상한가 ' if lim else ''}{pct2(pct)}입니다." if pct is not None else f"아래 칸의 {J(name)} {rl}입니다.",
                                              f"아래 칸은 {rl} {name}, {'상한가 ' if lim else ''}{PD}." if pct is not None else f"아래 칸은 {rl} {name}입니다.",
                                              f"{rl} {J(name)} {'상한가 ' if lim else ''}{pct2(pct)}입니다." if pct is not None else f"{rl} 칸은 {name}입니다."])))
        if fo is not None and io is not None and dv is not None:
            dn, dvv = _driver(s)
            oth = [(n, v) for n, v in (("외국인", fo), ("기관", io), ("개인", dv)) if n != dn]
            (n2, v2), (n3, v3) = oth[0], oth[1]
            if abs(v2) < 0.5 or abs(dvv) < 0.5:
                pairs.append((f"row:{i}_2", pk([f"{_aw(dn, dvv)}, {_aw(n2, v2)}.", f"{_aw(dn, dvv)}에 {_aw(n2, v2)}입니다.", f"{_aw(dn, dvv)}이고 {_aw(n2, v2)}입니다.",
                                                f"{_aw(dn, dvv)}, 그리고 {_aw(n2, v2)}.", f"{_aw(dn, dvv)}였고 {_aw(n2, v2)}입니다.", f"{_aw(dn, dvv)}. {_aw(n2, v2)}입니다."])))
            else:
                same_w = (dvv > 0) == (v2 > 0)
                pairs.append((f"row:{i}_2", pk([f"{dn} {hwon(dvv)}, {n2} {hwon(v2)} {_word(v2)}입니다." if same_w else f"{dn} {hwon(dvv)} {_word(dvv)}, {n2} {hwon(v2)} {_word(v2)}.",
                                                f"{dn} {hwon(dvv)}, {n2} {hwon(v2)} {_word(v2)}." if same_w else f"{dn} {hwon(dvv)} {_word(dvv)}에 {n2} {hwon(v2)} {_word(v2)}.",
                                                f"{subj(dn)} {obj(hwon(dvv))} {_verb(dvv)}고, {J(n2)} {hwon(v2)}입니다.",
                                                f"{dn} {hwon(dvv)}에 {n2} {hwon(v2)} {_word(v2)}." if same_w else f"{dn} {hwon(dvv)} {_word(dvv)}, {J(n2)} {hwon(v2)} {_word(v2)}.",
                                                f"{subj(dn)} {hwon(dvv)}, {subj(n2)} {hwon(v2)} {_word(v2)}." if same_w else f"{J(dn)} {hwon(dvv)} {_word(dvv)}, {J(n2)} {hwon(v2)} {_word(v2)}.",
                                                f"{dn} {hwon(dvv)}, {n2} {hwon(v2)} 둘 다 {_word(v2)}." if same_w else f"{dn} {hwon(dvv)} {_word(dvv)}, {n2}은 {hwon(v2)} {_word(v2)}."])))
            if val and i > 0:      # 거래대금은 둘째 종목에서(큰손 돈이 작다는 근거). 첫 종목 거래대금은 계산 문장이 말한다
                pairs.append((f"row:{i}_3", pk([f"{_aw(n3, v3)}, 거래대금 {hwon(val)}입니다.", f"{_aw(n3, v3)}에 거래대금 {hwon(val)}.",
                                                f"{_aw(n3, v3)}, 거래대금은 {hwon(val)}.", f"거래대금 {hwon(val)}, {_aw(n3, v3)}입니다.",
                                                f"{_aw(n3, v3)}, 거래대금 {hwon(val)}짜리입니다.", f"{_aw(n3, v3)}. 거래대금 {hwon(val)}."])))
            else:
                pairs.append((f"row:{i}_3", pk([f"{_aw(n3, v3)}입니다.", f"{J(n3)} {hwon(v3)} {_word(v3)}입니다." if abs(v3) >= 0.5 else f"{_aw(n3, v3)}.",
                                                f"{J(n3)} {obj(hwon(v3))} {_verb(v3)}습니다." if abs(v3) >= 0.5 else f"{J(n3)} 손을 대지 않았습니다.",
                                                f"{_aw(n3, v3)}.", f"그리고 {_aw(n3, v3)}.", f"마지막은 {_aw(n3, v3)}."])))
            driver = dn
        elif fo is not None and io is not None:
            pairs.append((f"row:{i}_2", pk([f"외국인 {hwon(fo)} {_word(fo)}, 기관 {hwon(io)} {_word(io)}." + (f" 거래대금 {hwon(val)}입니다." if val else ""),
                                            f"외국인 {hwon(fo)}에 기관 {hwon(io)}, {_word(fo + io)}입니다." + (f" 거래대금은 {hwon(val)}입니다." if val else ""),
                                            f"외국인 {hwon(fo)}, 기관 {hwon(io)}, 둘 다 {_word(fo)}입니다." if (fo > 0) == (io > 0) else f"외국인 {hwon(fo)} {_word(fo)}에 기관 {hwon(io)} {_word(io)}입니다."])))
            driver = "외국인" if fo >= io else "기관"
        else:
            driver = None
        rows_out.append({"name": name, "role": role, "theme": s.get("theme") or th, "pct": pct, "foreign": fo, "inst": io, "indiv": dv, "value": val, "driver": driver})
    # 계산 1개 — 주도 주체 순매수 ÷ 거래대금(%) → 두 종목 큰손 합 ÷ 개인 순매도(배) → 외+기 ÷ 거래대금(%)
    s0 = stocks[0]
    val0 = _num(s0.get("value"))
    dn, dvv = _driver(s0)
    if full and val0 and dvv > 0 and _num(s0.get("indiv")) is not None:
        r = _calc("share", dvv, val0)
        if r and r["n"] >= 3:
            calc, kind = r, "K-share"
            pairs.append(("calc", pk([f"{dn} 순매수는 거래대금 {hwon(val0)}의 {r['n']}%입니다.", f"{dn} 몫은 거래대금 {hwon(val0)}의 {r['n']}%입니다.",
                                      f"{dn} 순매수를 거래대금 {ro(hwon(val0))} 나누면 {r['n']}%.", f"거래대금 {hwon(val0)} 가운데 {dn} 몫이 {r['n']}%입니다.",
                                      f"거래대금 {hwon(val0)}에서 {dn} 몫은 {r['n']}%입니다.", f"거래대금 {hwon(val0)}의 {r['n']}%가 {dn} 순매수입니다."])))
    if calc is None and len(stocks) == 2 and all(_num(s.get("indiv")) is not None for s in stocks):
        big = sum((_num(s.get("foreign")) or 0) + (_num(s.get("inst")) or 0) for s in stocks)
        ind = sum(_num(s.get("indiv")) or 0 for s in stocks)
        if big > 0 and ind < 0:
            r = _calc("ratio", big, ind)
            if r:
                calc, kind = r, "K-ratio"
                pairs.append(("calc", pk([f"두 종목 큰손 순매수 {obj(hwon(big))} 개인 순매도로 나누면 {r['n']}배입니다.", f"외국인·기관 {hwon(big)} 대 개인, 나누면 {r['n']}배입니다.",
                                          f"두 종목에서 큰손이 산 {J(hwon(big))} 개인이 판 돈의 {r['n']}배입니다."])))
    if calc is None and val0:
        big0 = (_num(s0.get("foreign")) or 0) + (_num(s0.get("inst")) or 0)
        r = _calc("share", abs(big0), val0) if big0 else None
        if r:
            calc, kind = r, "K-fi"
            pairs.append(("calc", pk([f"외국인·기관 순매{'수' if big0 > 0 else '도'}를 거래대금 {ro(hwon(val0))} 나누면 {r['n']}%입니다.", f"거래대금 {hwon(val0)} 가운데 큰손 몫은 {r['n']}%입니다.",
                                      f"큰손 돈을 거래대금 {ro(hwon(val0))} 나눈 값은 {r['n']}%입니다."])))
    if calc is None:
        pairs.append(("calc", pk(["큰손 돈이 거래대금에 견줘 작아 비율은 1%도 안 됩니다.", "거래대금에 견주면 큰손 몫은 1% 아래입니다.", "비율로 재면 큰손 돈은 1%에도 못 미칩니다."])))
    if calc:
        calc = {k: v for k, v in calc.items() if k != "n"}
        calc["verified"] = True
    # 누가 밀어 올렸나
    if len(rows_out) == 2 and rows_out[0]["driver"]:
        a, b = rows_out
        big_b = (_num(b.get("foreign")) or 0) + (_num(b.get("inst")) or 0)
        small_b = (b.get("value") or 0) and big_b < 0.1 * (b.get("value") or 1)
        bd = "큰손 돈이 작은 상승" if (small_b and (b.get("pct") or 0) > 0) else ("외국인과 기관이 같이 산 상승" if ((b.get("foreign") or 0) > 0 and (b.get("inst") or 0) > 0 and (b.get("pct") or 0) > 0)
                                                                              else f"{b['driver']}이 받친 자리" if b.get("driver") else "돈보다 값이 먼저 움직인 자리")
        ad = f"{a['driver']}이 밀어 올린 상승" if (a.get("pct") or 0) > 0 else f"{a['driver']}이 받은 자리"
        pairs.append(("driver", pk([f"{J(a['name'])} {ad}, {J(b['name'])} {bd}입니다.", f"{obj(a['name'])} 밀어 올린 손은 {a['driver']}, {J(b['name'])} {bd}입니다.",
                                    f"정리하면 {J(a['name'])} {ad}이고 {J(b['name'])} {bd}입니다."])))
    elif rows_out and rows_out[0]["driver"]:
        a = rows_out[0]
        pairs.append(("driver", pk([f"{J(a['name'])} {a['driver']}이 {'밀어 올린' if (a.get('pct') or 0) > 0 else '받은'} 자리입니다.", f"{obj(a['name'])} {'밀어 올린' if (a.get('pct') or 0) > 0 else '받친'} 손은 {a['driver']}입니다."])))
    return pairs, {"doc": doc, "date": day, "stocks": rows_out, "calc": calc, "kind": kind, "full": full, "no_indiv": not full, "pairs": pairs}, kind


# ══════════════════════════════════════════════════════════════════════════════
# S5 뉴스와 맞물렸나 — 뉴스 ≤2(이슈 메모 head 문장 → 제목에 업종·종목 이름이 든 기사; 압축 판은 이슈 키워드 한 줄) → 양면 프레임 고정(말은 회전)
# → 업종마다 '오늘 [업종]은 [돈/뉴스] 쪽입니다' → 뒤집히는 조건(임계값) → S0 콜백(계산) → 한계 1문장. 대체: 이슈·기사 없음 → '뉴스 없이 수급만 움직인 날' + 판정은 돈 쪽.
# ══════════════════════════════════════════════════════════════════════════════
_A = ["뉴스가 올린 값이면 큰손 돈은 작습니다.", "뉴스가 올린 값에는 큰손 막대가 짧습니다.", "값을 뉴스가 올렸다면 큰손 돈은 작습니다.",
      "뉴스가 밀어 올린 값이면 큰손 순매수는 작습니다.", "왼쪽 칸, 뉴스가 올린 값이면 큰손 돈은 작습니다.", "뉴스가 올린 값이면 큰손 순매수가 작습니다."]
_B = ["돈이 올린 값이면 큰손이 같이 삽니다.", "돈이 올린 값에는 큰손 막대가 같이 섭니다.", "값을 돈이 올렸다면 큰손이 같이 삽니다.",
      "돈이 밀어 올린 값이면 큰손 막대가 나란히 섭니다.", "오른쪽 칸, 돈이 올린 값이면 큰손이 같이 삽니다.", "돈이 올린 값이면 외국인과 기관이 같이 삽니다."]
NEWS_MAX = 46      # 말하는 뉴스 문장 상한(글자) — 넘거나 한 업종에 문장이 둘이면 이슈 키워드 한 줄로 줄인다(BRIEF_FIX_1 §B)


def _clauses(head: str) -> list[str]:
    """이슈 메모 head → 문장 조각들('…됐고, …열었습니다. …겹쳤고요.' → 셋). 끝은 '습니다.' 로 맞춘다(문장 하나 = 단계 하나)."""
    out = []
    for sent in re.split(r"(?<=[다요])\.\s*", (head or "").strip()):
        for cl in re.split(r"(?<=[았었됐했겼왔갔])고,?\s+", sent.strip().rstrip(".")):
            cl = cl.strip().rstrip(".,")
            if not cl:
                continue
            if cl.endswith("고요"):
                cl = cl[:-2] + "습니다"
            elif not cl.endswith(("습니다", "입니다")):
                cl += "습니다" if cl[-1] in "았었됐했겼왔갔" else "입니다"
            out.append(cl + ".")
    return out


def _kw_for(th: str) -> list[str]:
    kws = [th, tname(th)] + list(THEME_KW.get(th) or [])
    try:
        from app.services.themes import THEMES
        kws += [n for _, n in THEMES.get(th) or []]
    except Exception:
        pass
    return [k for k in dict.fromkeys(kws) if k]


def _bad(s: str) -> bool:
    try:
        import sys
        from _common import DATA
        sys.path.insert(0, str(DATA.parent))
        from checks import forbidden
        return any(not h.startswith("단정:") for h in forbidden.find(s))
    except Exception:
        return False


def _theme_of(text: str, themes: list[str], kws: dict[str, list[str]]) -> str | None:
    score = {th: sum(1 for k in kws[th] if k and k in text) for th in themes}
    return max(score, key=score.get) if score and max(score.values()) > 0 else None


def _news_for(x: dict, themes: list[str], stock_names: list[str]) -> tuple[list[dict], list[dict]]:
    """(업종별 뉴스 문장 ≤3, 압축 키워드 줄). 문장: [{theme, spoken, title, source, extra}] — 이슈 메모(event.head) 가 그 업종을 말하면 그 문장, 아니면 제목에 이름이 든 기사.
    압축: 이슈 keywords 가운데 업종 이름·종목 이름·수급 낱말이 아닌 것을 업종별로 묶은 [{theme, kws}] — 길이 예산이 모자랄 때 한 문장으로 말한다."""
    out: list[dict] = []
    ev = x["ev"]
    kws = {th: _kw_for(th) + [n for n in stock_names if n] for th in themes}
    ev_names = [s.get("name") for s in x["ev_st"] if s.get("name")]
    ev_group = (ev.get("group") or ev.get("label") or "이슈 종목") if ev else ""
    compact: list[dict] = []
    if ev and ev.get("head"):
        prev = None
        for cl in _clauses(ev["head"]):
            if _ntok(cl) > 2 or _bad(cl):
                continue
            th = _theme_of(cl, themes, kws) or prev or ev_group
            prev = th if th in themes else prev
            k = sum(1 for o in out if o["theme"] == th)
            if k >= 2 or len(out) >= 3:
                continue
            out.append({"theme": th, "spoken": cl, "title": cl.rstrip(".")[:60], "source": "이슈 메모", "extra": k >= 1})
        skip = set(themes) | {tname(t) for t in themes} | set(ev_names) | set(stock_names) | {f"{t}주" for t in themes}
        by: dict[str, list[str]] = {}
        for kw in (ev.get("keywords") or []):
            kw = str(kw).strip()
            if not kw or kw in skip or _GENERIC_KW.search(kw) or len(kw) > 14:
                continue
            th = _theme_of(kw, themes, kws) or ev_group
            if len(by.get(th, [])) < 2:
                by.setdefault(th, []).append(kw)
        compact = [{"theme": t, "kws": v} for t, v in by.items()]
    # 긴 문장(NEWS_MAX 초과)이거나 한 업종에 문장이 둘이면 그 업종은 이슈 키워드 한 줄로 줄인다 — 같은 재료를 절반 길이로(BRIEF_FIX_1 §B)
    kw_by = {k["theme"]: k["kws"] for k in compact if k.get("kws")}
    n_th = {th: sum(1 for o in out if o["theme"] == th) for th in {o["theme"] for o in out}}
    long_th = {o["theme"] for o in out if o["source"] == "이슈 메모" and o["theme"] in kw_by and (len(o["spoken"]) > NEWS_MAX or n_th[o["theme"]] >= 2)}
    if long_th:
        kept, done = [], set()
        for o in out:
            th = o["theme"]
            if th in long_th:
                if th not in done:
                    done.add(th)
                    kept.append({"theme": th, "spoken": "", "kws": kw_by[th], "title": " · ".join(kw_by[th]), "source": "이슈 메모", "extra": False, "kw": True})
                continue
            kept.append(o)
        out = kept
    used = {o["theme"] for o in out}
    for th in themes:
        if th in used or len(out) >= 3:
            continue
        for it in x["news"]:
            title = re.sub(r"\[[^\]]*\]|\([^)]*\)|[\"'“”‘’]", "", str(it.get("title") or "")).strip()
            if not any(k in title for k in kws[th][:3] + [n for n in stock_names if n]) or _ntok(title) > 2 or _bad(title):
                continue
            title = re.split(r"…|\.\.\.|\s[-–—]\s", title)[0].strip()[:48]
            if len(title) < 8:
                continue
            # 매체 이름이 도메인이면(digitaltoday.co.kr) 읽지 않는다 — 소리로 들으면 알아들을 수 없다
            src = (it.get("source") or "").strip()
            say_src = "" if ("." in src or not src) else src
            sp = f"{tname(th)} 쪽 기사는 {say_src}의 '{title}'입니다." if say_src else f"{tname(th)} 쪽 기사 제목은 '{title}'입니다."
            out.append({"theme": th, "spoken": sp, "title": title, "source": src, "extra": False})
            used.add(th)
            break
    return out, compact


def _side(r: dict) -> str:
    """돈 쪽(b): 외국인·기관 둘 다 순매수이고 합이 MONEY_MIN 이상. 아니면 뉴스 쪽(a)."""
    fo, io, net = _num(r.get("foreign")) or 0, _num(r.get("inst")) or 0, _num(r.get("net")) or 0
    return "b" if (fo > 0 and io > 0 and net >= MONEY_MIN) else "a"


def _s5(x: dict, s0: dict, s4: dict, pk: Picker, compact: bool = False) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    themes_in = x["in_ths"] or ([x["out_th"]] if x["out_th"] else [])
    stock_names = [s["name"] for s in (s4.get("stocks") or [])]
    news, kwl = _news_for(x, themes_in, stock_names)
    pairs: list[tuple[str, str]] = []
    if len(news) >= 2 and all(o.get("kw") for o in news[:2]) and not compact:
        # 두 업종 다 키워드 한 줄이면 한 문장으로 묶는다 — 'news:1' 은 예산에서 먼저 빠지는 칸이라 그대로 두면 둘째 뉴스가 사라진다
        news = news[:2]
        core = ", ".join(f"{J(tname(o['theme']))} {_and(o['kws'])}" for o in news)
        pairs.append(("news:0", pk([f"{core} 뉴스였습니다.", f"뉴스 둘, {core}입니다.", f"오늘 뉴스 둘, {core}입니다.", f"{core} 소식이 있었습니다.",
                                    f"{core}, 오늘 뉴스입니다.", f"{core} 뉴스입니다."])))
    elif news and compact and kwl:
        # 압축 판: 이슈 키워드를 업종별로 묶어 한 문장 — '이차전지는 포드 CATL 뉴스, 로봇은 제조AI와 중국산 로봇 규제 뉴스였습니다.'
        parts = [(f"{J(tname(k['theme']))} {_and(k['kws'])}" if k["theme"] in themes_in else f"{k['theme']} 쪽 {_and(k['kws'])}") for k in kwl[:2]]
        core = ", ".join(parts)
        pairs.append(("news:0", pk([f"뉴스는 {_was(core)}.", f"{core} 뉴스가 있었습니다.", f"뉴스 쪽은 {core}입니다.", f"뉴스 카드는 {core}입니다.", f"오늘 뉴스는 {_was(core)}.", f"{core}, 오늘 나온 뉴스입니다."])))
        news = [{"theme": k["theme"], "title": " · ".join(k["kws"]), "source": "이슈 메모", "extra": False} for k in kwl[:2]]
    elif news:
        n_groups = len({o["theme"] for o in news})
        pairs.append(("lead", pk(["뉴스는 두 갈래였습니다.", "뉴스 쪽을 보면 두 갈래입니다.", "오늘 뉴스는 둘로 갈립니다.", "뉴스 카드는 두 장입니다."] if n_groups >= 2 else
                                 ["뉴스는 한 갈래였습니다.", "뉴스 쪽은 하나입니다.", "오늘 뉴스 카드는 한 장입니다."])))
        seen_th: dict[str, int] = {}
        for o in news:
            k = seen_th.get(o["theme"], 0)
            seen_th[o["theme"]] = k + 1
            tn = tname(o["theme"])
            if o.get("kw"):        # 이슈 키워드 한 줄(긴 뉴스 문장을 줄인 판)
                core = _and(o["kws"])
                spoken = pk([f"{J(tn)} {core} 뉴스였습니다.", f"{tn} 쪽은 {core} 뉴스입니다.", f"{tn} 재료는 {core}입니다.", f"{tn} 쪽 재료는 {_was(core)}.",
                             f"뉴스는 {tn} 쪽 {core}입니다.", f"{J(tn)} {core} 소식이 있었습니다."])
            elif o["source"] == "이슈 메모":
                spoken = o["spoken"] if k else pk([f"{tn} 쪽 뉴스, {o['spoken']}", f"{J(tn)} {o['spoken']}", f"먼저 {tn}, {o['spoken']}"]) if o["theme"] in themes_in else \
                    pk([f"뉴스는 {o['theme']} 쪽에 있었습니다. {o['spoken']}", f"{o['theme']} 소식입니다. {o['spoken']}", f"이슈는 {o['theme']}, {o['spoken']}"])
            else:
                spoken = o["spoken"]
            pairs.append(("news_x" if o.get("extra") else f"news:{len([p for p in pairs if p[0].startswith('news:')])}", spoken))
    else:
        pairs.append(("news:0", pk(["뉴스 없이 수급만 움직인 날입니다.", "오늘은 업종 이름이 든 뉴스가 없었습니다. 돈만 움직였습니다.", "뉴스 카드는 비어 있습니다. 수급만 움직인 날입니다.",
                                    "제목에 이 업종이 든 기사가 없는 날, 돈만 먼저 움직였습니다.", "뉴스 칸은 비었습니다. 오늘은 돈이 먼저였습니다.", "업종 이름이 든 기사 없이 수급만 움직였습니다."])))
    if compact:
        pairs.append(("ab", pk(["뉴스가 올린 값이냐 돈이 올린 값이냐, 둘로 가릅니다.", "뉴스가 올린 값이면 큰손 돈이 작고, 돈이 올린 값이면 큰손이 같이 삽니다.",
                                "값을 올린 게 뉴스냐 돈이냐, 두 칸으로 봅니다.", "뉴스가 올린 값과 돈이 올린 값, 이 둘을 가릅니다.", "왼쪽 칸은 뉴스가 올린 값, 오른쪽 칸은 돈이 올린 값입니다.", "판정 칸은 둘, 뉴스가 올린 값이냐 돈이 올린 값이냐입니다."])))
    else:
        pairs.append(("a", pk(_A)))
        pairs.append(("b", pk(_B)))
    # 업종별 판정
    verdicts = []
    for i, th in enumerate(themes_in[:2]):
        r = x["themes"].get(th) or {}
        has_news = any(o["theme"] == th for o in news)
        net = r.get("net") or 0
        side = _side(r) if net > 0 else "b"
        if not has_news and net > 0:
            side = "b"
        tn, T = tname(th), hwon(net)
        sw = "돈" if side == "b" else "뉴스"
        # 이슈 라벨과 업종 이름이 다르면 둘 다 붙인다(BRIEF_FIX_2 §D-3)
        ilab = _issue_lab(x, th) if has_news else ""
        if side == "b":
            if net <= 0:
                _lead = _leaders(x, th)
                _up = bool(_lead) and (_lead[0].get("pct") or 0) > 0
                _inst = (r.get("inst") or 0) > 0 and (r.get("foreign") or 0) < 0
                if _up and _inst:            # 9/16 실측: 외국인이 팔고 기관이 받아 값이 오른 날
                    why = "외국인이 판 물량을 기관이 받아 값이 올랐습니다"
                elif _up:
                    why = "큰손 돈은 빠졌는데 값이 올랐습니다"
                else:
                    why = "뉴스보다 외국인·기관 매도가 값을 눌렀습니다" if has_news else "뉴스 없이 외국인과 기관이 같이 팔았습니다"
            else:
                why = "뉴스와 외국인·기관 순매수가 같이 갔습니다" if has_news else "뉴스 없이 외국인과 기관이 같이 샀습니다"
            txt = pk(([f"이슈로 묶인 {ilab} 가운데 {J(tn)} {sw} 쪽입니다.", f"{ilab} 가운데 {J(tn)} {sw} 쪽입니다.",
                       f"이슈로 묶인 {ilab}, 그중 {tn} 판정은 {sw} 쪽입니다.", f"{ilab} 중에서 {J(tn)} {sw} 쪽입니다."] if ilab else
                      [f"오늘 {J(tn)} {sw} 쪽입니다.", f"{J(tn)} {sw} 쪽입니다.", f"한 줄로, {J(tn)} {sw} 쪽입니다.", f"판정은 {tn} {sw} 쪽입니다.", f"오늘 판정, {J(tn)} {sw} 쪽입니다.", f"{tn} 판정은 {sw} 쪽입니다."]) if i == 0 else
                     [f"{tn}도 {sw} 쪽입니다.", f"{tn} 역시 {sw} 쪽입니다.", f"오늘 {J(tn)} {sw} 쪽입니다.", f"{tn}도 같은 {sw} 쪽입니다.", f"{tn} 판정도 {sw} 쪽입니다.", f"{tn}도 오늘은 {sw} 쪽입니다."])
            pairs.append(("verdict:0" if i == 0 else "verdict:1", txt))
            pairs.append(("verdict_why", pk([f"{why}.", f"{tn}에선 {why}." if has_news else f"{J(tn)} {why}.", f"{why}, 그래서 돈 쪽입니다.", f"근거는 하나, {why}.", f"{tn} 쪽은 {why}.", f"{why}, 그 칸에 섭니다."])))
        else:
            why = f"들어온 큰손 돈은 {ro(T)} 작았습니다" if (r.get("net") or 0) > 0 else "큰손 돈은 오히려 나갔습니다"
            short = f"큰손 돈은 {T}뿐입니다" if (r.get("net") or 0) > 0 else "큰손 돈은 나갔습니다"
            txt = pk(([f"이슈로 묶인 {ilab} 가운데 {J(tn)} {sw} 쪽입니다, {short}.", f"{ilab} 가운데 {J(tn)} {sw} 쪽입니다, {short}.",
                       f"이슈로 묶인 {ilab}, 그중 {tn} 판정은 {sw} 쪽입니다.", f"{ilab} 중에서 {J(tn)} {sw} 쪽입니다, {short}."] if ilab else
                      [f"오늘 {J(tn)} {sw} 쪽입니다, {short}.", f"{J(tn)} {sw} 쪽입니다, {short}.", f"판정은 {tn} {sw} 쪽입니다, {short}.", f"오늘 판정, {J(tn)} {sw} 쪽입니다, {short}.",
                          f"{tn} 판정은 {sw} 쪽입니다, {short}.", f"한 줄로, {J(tn)} {sw} 쪽입니다, {short}."]) if i == 0 else
                     [f"반면 {J(tn)} {sw} 쪽입니다, {short}.", f"{J(tn)} {sw} 쪽입니다, {short}.", f"{tn} 판정은 {sw} 쪽입니다, {short}.", f"{tn}은 반대로 {sw} 쪽입니다, {short}.",
                          f"반면 오늘 판정, {J(tn)} {sw} 쪽입니다, {short}.", f"반면 {tn} 판정은 {sw} 쪽입니다, {short}."])
            pairs.append(("verdict:0" if i == 0 else "verdict:1", txt))
        verdicts.append({"theme": th, "side": side, "text": txt})
    if not verdicts:
        txt = pk(["오늘은 돈 쪽입니다. 뉴스 없이 수급만 움직였습니다.", "판정은 돈 쪽입니다. 뉴스가 아니라 돈이 먼저였습니다.", "한 줄로, 오늘은 돈 쪽입니다."])
        pairs.append(("verdict", txt))
        verdicts.append({"theme": "", "side": "b", "text": txt})
    verdict = verdicts[0]["side"]
    # 오늘 돈이 어느 쪽으로 가고 있나 — 판정 바로 뒤 한 줄(BRIEF_FIX_2 §B). 매매 판단이 아니라 돈의 흐름에 대한 판정,
    # 주어는 '돈'·'흐름'·'수급'. 근거 한 마디는 이미 말한 숫자만 되쓴다. 예산에서 빼지 않는다.
    f_score, f_why = _flow_score(x)
    f_txt = pk(_FLOW_TXT[_flow_grade(f_score)])
    f_reason = pk(f_why) if f_why else ""
    pairs.append(("flow", f"{f_txt} {f_reason}".strip()))
    # 뒤집히는 조건(임계값 하나)
    news_side = next((v for v in verdicts if v["side"] == "a" and v["theme"]), None)
    nxt = _day_word(d, na.next_trading_day(d).strftime("%Y%m%d"), past=False)
    if news_side:
        r = x["themes"].get(news_side["theme"]) or {}
        thr = nh.hround(max(2 * (r.get("net") or 0), 500))
        cond = f"{nxt} {tname(news_side['theme'])}에 외국인·기관 돈이 {hwon(thr)} 넘게 들어오는"
        cond_note = f"{tname(news_side['theme'])}도 돈 쪽으로 넘어갑니다"
    elif verdicts[0]["theme"] and (x["themes"].get(verdicts[0]["theme"]) or {}).get("net", 0) <= 0:
        r = x["themes"].get(verdicts[0]["theme"]) or {}
        thr = nh.hround(max(abs(r.get("net") or 0) / 2, 500))
        cond = f"{nxt} {tname(verdicts[0]['theme'])}에 외국인·기관 돈이 {hwon(thr)} 넘게 돌아오는"
        cond_note = "나가는 돈이 멈춘 겁니다"
    elif verdicts[0]["theme"]:
        r = x["themes"].get(verdicts[0]["theme"]) or {}
        thr = nh.hround(max((r.get("net") or 0) / 2, 100))
        cond = f"{nxt} {tname(verdicts[0]['theme'])}에서 외국인·기관이 {hwon(thr)} 넘게 되파는"
        cond_note = "돈이 아니라 뉴스가 올린 값이 됩니다"
    else:
        cond = f"{nxt} 외국인이 {'사는' if x['sold'] else '파는'} 쪽으로 돌아서는"
        cond_note = "판정이 뒤집힙니다"
    cond_k = cond.replace("외국인·기관 돈이", "큰손 돈이").replace("외국인·기관이", "큰손이")
    pairs.append(("condition", pk([f"뒤집히는 조건은 하나, {cond_k} 겁니다.", f"뒤집히는 조건은 딱 하나, {cond_k} 겁니다.", f"이 판정이 뒤집히는 조건은 하나, {cond_k} 겁니다.",
                                   f"뒤집히는 조건은 {cond_k} 것 하나입니다.", f"판정이 뒤집히는 조건은 하나, {cond_k} 겁니다.", f"뒤집히는 조건은 그 하나, {cond_k} 겁니다."])))
    # S0 콜백(계산)
    cb_text, cb = _callback(s0, x, said_frac=False, pk=pk)
    if cb_text:
        pairs.append(("callback", cb_text))
    # 한계 1문장
    limit = pk(["주체별 합계라 종목 사이 이동은 이 표에 안 보입니다.", "정규장 체결만 더한 값이라 대량매매는 빠져 있습니다.", "업종 합계는 종목 안의 손바뀜까지는 말해 주지 않습니다.",
                "합산표라 한 종목 안에서 누가 누구에게 넘겼는지는 안 보입니다.", "시간외 거래는 이 합산에 들어 있지 않습니다.", "업종 합계는 그날 손바뀜의 결과일 뿐 이유까지는 말하지 않습니다."])
    pairs.append(("limit", limit))
    first = verdicts[0]
    r0 = x["themes"].get(first["theme"]) or {}
    support = {"label": f"{tname(first['theme'])} 외국인·기관", "value": hwon(r0.get("net") or 0)} if first["theme"] else None
    return pairs, {"news": [{"title": o["title"], "source": o["source"], "theme": o["theme"]} for o in news][:2], "a": "뉴스가 올린 값", "b": "돈이 올린 값",
                   "flow": {"score": f_score, "grade": _flow_grade(f_score), "text": f_txt, "why": f_reason},
                   "verdicts": verdicts, "verdict": verdict, "condition": cond + " 것", "limit": limit, "support": support, "callback": cb or None,
                   "callback_num": (cb or {}).get("a") or None, "pairs": pairs}, "V-" + ("money" if verdict == "b" else "news")


# ══════════════════════════════════════════════════════════════════════════════
# S6 내일 포인트 2~3 + 이벤트 시각 + 애프터마켓 + 시그니처. watch[0] 은 ledger.parse_q 형태.
# 관측값: 외국인(주인공) 순매도 N+1일째 → 유입 업종 이틀째(없으면 기타법인 선) → 이벤트 시각(있으면 셋째 포인트).
# ══════════════════════════════════════════════════════════════════════════════
def _s6(x: dict, c: dict, cont: dict, brand: str, pk: Picker, attempt: int, compact: bool = False) -> tuple[list, dict, str, list]:
    d, P, sold, st = x["d"], x["P"], x["sold"], x["st_p"]
    pk = ScenePick(pk)
    word = _word(x["amount"] if x["amount"] else -1)
    nd = na.next_trading_day(d)
    nxt = _day_word(d, nd.strftime("%Y%m%d"), past=False)
    if P in ("외국인", "기관"):
        n = (st + 1) if st >= 1 else 2
        next_q = f"{P} {word}가 {dko(n)} 이어지는지"
        w1 = {"q": next_q, "threshold": f"{n}거래일째", "spoken": next_q}
    else:
        frg = x["vals"].get("외국인")
        stf = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
        wf = "순매도" if (frg or 0) < 0 else "순매수"
        next_q = f"외국인 {wf}가 {dko(stf + 1)} 이어지는지" if stf else f"외국인 {wf}가 이어지는지"
        w1 = {"q": next_q, "threshold": f"{stf + 1}거래일째" if stf else "같은 부호", "spoken": next_q}
    watch = [w1]
    in_th = x["in_th"]
    oth, ob = x["oth"], cont.get("others_buy_days") or 0
    if in_th and (x["in_t"] or 0) >= 100:
        stk = max(int((x["themes"].get(in_th) or {}).get("streak") or 0), 1)
        q2 = f"{in_th} 순매수가 {dko(stk + 1)} 이어지는지"
        w2 = {"q": q2, "threshold": dko(stk + 1), "spoken": q2}   # 장부 문장 그대로 말한다 — 짧고, 겹침 검사 예외(BRIEF_FIX_1 §B)
    elif oth >= 3000 and ob >= 1:
        obw, _cap = _ob_word(cont, d, ob)
        thr = int(oth // 1000 * 1000)
        w2 = {"q": f"기타법인 순매수가 {obj(hwon(thr))} 지키는지", "threshold": hwon(thr), "spoken": f"기타법인 순매수가 {obj(hwon(thr))} 지키는지", "note": f"{obw} 지켜온 선입니다."}
    else:
        w2 = None
    if w2:
        watch.append(w2)
    ev = _next_event(d, c.get("schedule") or [], c.get("fomc_dates") or [])
    n_pts = len(watch) + (1 if ev else 0)
    cw = COUNT_WORD.get(n_pts, str(n_pts))
    pairs: list[tuple[str, str]] = []
    pairs.append(("intro", pk([f"{nxt} 볼 포인트는 {cw}입니다.", f"{nxt} 확인할 건 {cw}입니다.", f"{nxt} 마감에서 볼 건 {cw}입니다.", f"{nxt} 숙제는 {cw}입니다.", f"{nxt} 볼 숫자는 {cw}입니다.", f"{nxt} 체크할 칸은 {cw}입니다."])))
    # 같은 질문을 이틀 넘게 던지는 중이면 '내일도 같은 자리'로 말한다(BRIEF_FIX_2 §C).
    # 장부 문장(ledger.parse_q 가 읽는 '{주체} {순매수|순매도}가 {N일째} 이어지는지')은 앞말과 따로 떨어진 한 문장으로 그대로 둔다.
    try:
        promise_days = sm.continuity(d, {"watch_family": [sm.q_family(next_q)]}).get("promise_days") or 0
    except Exception:  # noqa: BLE001
        promise_days = 0
    if promise_days >= 2:
        pairs.append(("watch_same", pk([f"{nxt}도 같은 자리를 봅니다.", "볼 것은 어제와 같습니다.", "같은 숫자를 하루 더 따라갑니다.",
                                        "이 질문은 아직 안 끝났습니다.", "자리는 그대로입니다.", "어제 보던 자리를 하루 더 봅니다."])))
    pairs.append(("watch:0", f"{w1['spoken']}."))
    if w2:
        pairs.append(("watch:1", f"{w2['spoken']}."))
        if w2.get("note"):
            pairs.append(("note", w2["note"]))
    if ev:
        when, lab = ev["when"], ev["label"]
        prob = x.get("fomc_prob")
        third = n_pts == 3
        if prob is not None and "금리" in lab:
            pairs.append(("event", pk([f"그리고 {when} {lab}, 인상 확률 {prob:.0f}%입니다.", f"셋째는 {when} {lab}입니다. 인상 확률은 {prob:.0f}%입니다.", f"{when} {lab}까지 겹칩니다, 인상 확률 {prob:.0f}%."] if third else
                                      [f"그 전에 {when} {lab}, 인상 확률 {prob:.0f}%입니다.", f"{when} {subj(lab)} 먼저입니다. 인상 확률 {prob:.0f}%.", f"시계는 {when} {lab}, 인상 확률 {prob:.0f}%에 맞춰 둡니다."])))
        else:
            pairs.append(("event", pk([f"그리고 {when} {lab}입니다.", f"셋째는 {when} {lab}입니다.", f"{when} {lab}까지 겹칩니다.", f"거기에 {when} {subj(lab)} 있습니다.", f"마지막은 {when} {lab}입니다.", f"셋째 칸은 {when} {lab}입니다."] if third else
                                      [f"그 전에 {when} {subj(lab)} 있습니다.", f"{when} {subj(lab)} 먼저입니다.", f"시계는 {when} {lab}에 맞춰 둡니다.", f"그 앞에 {when} {subj(lab)} 놓여 있습니다.", f"{when} {lab}까지가 시간표입니다."])))
    when_up = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    after = "20260914" <= d <= AFTER_MARKET_NOTICE_UNTIL
    if after:
        pairs.append(("after", "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다."))
    since = "내일부터 " if d == "20260915" else ""
    pairs.append(("sig", f"{na._ieot(brand)} 국장 마감은 {since}매일 {when_up}에 올라옵니다."))
    note = f"인상 확률 {x['fomc_prob']:.0f}%" if (ev and x.get("fomc_prob") is not None and "금리" in ev["label"]) else None
    return pairs, {"watch": watch, "promise_days": promise_days, "event": ({"label": ev["label"], "when": ev["when"], "note": note} if ev else None),
                   "after_market": after, "when": when_up, "pairs": pairs}, next_q, watch


# ══════════════════════════════════════════════════════════════════════════════
# 조립
# ══════════════════════════════════════════════════════════════════════════════
def build(c: dict, avoid: set[str] | None = None, attempt: int = 0) -> dict:
    """수급 브리핑 대본. c 는 compute.narration_inputs() 입력(+ brief_stocks · news_items · flow_day · theme_rows).
    avoid 는 검사에서 걸린 문장 집합(문장 단위로 후보에서 뺀다), attempt 는 회전 오프셋. 전체가 1,250자를 넘으면 선택 문장을 빼고, 그래도 넘으면
    짧은 후보 + 압축 뉴스로 한 번 더 만든다. 어떤 키가 없어도 예외를 내지 않는다(§2 대체 규칙)."""
    out = _build_once(c, avoid, attempt, compact=False)
    if sum(len(sc["tts"]) for sc in out["scenes"]) > TOTAL_MAX:
        out2 = _build_once(c, avoid, attempt, compact=True)
        if sum(len(sc["tts"]) for sc in out2["scenes"]) < sum(len(sc["tts"]) for sc in out["scenes"]):
            out = out2
    return out


def _build_once(c: dict, avoid: set[str] | None, attempt: int, compact: bool) -> dict:
    brand = c.get("brand") or "누가샀나"
    attempt = max(0, int(attempt or 0))
    x = bctx(c)
    d = x["d"]
    try:
        exact, masked = sm.seen(d)
    except Exception:
        exact, masked = {}, {}
    comp_like = {"investors": {"kospi": x["inv"]}, "protagonist": {"name": x["P"], "amount": x["amount"]}, "moves": x["moves"],
                 "top_move": c.get("top_move"), "event": x["ev"] or None, "inv_streak": c.get("inv_streak") or {}, "kospi": x["k"],
                 "callback": x["cb"], "others_top": na._others_top({**c, "date": d})}
    try:
        cont = sm.continuity(d, sm.facts(comp_like))
    except Exception:
        cont = {"top_buyer_days": 1, "others_buy_days": 1 if x["oth"] > 0 else 0, "protagonist_days": 1, "yesterday": None}
    # 압축 판은 숫자만 다른 문장(masked)을 피하지 않는다 — 검사는 글자 그대로 겹침만 실패로 보고, 짧은 후보가 연일 소진되면 길이가 늘어난다
    pk = Picker(d, exact, {} if compact else masked, avoid, attempt, compact=compact)

    hook_kind, hook_parts, s0 = nh._s0(x, pk, attempt)
    p1, s1, q_kind = _s1(x, pk, attempt)
    p2, s2, n_kind = _s2(x, cont, pk, attempt)
    p3a, s3a, wk_rows = _s3a(x, cont, c, pk)
    p3b, s3b = _s3b(x, pk)
    p3c, s3c = _s3c(x, pk)
    p4, s4, k_kind = _s4(x, pk)
    p5, s5, v_kind = _s5(x, s0, s4, pk, compact=compact)
    p6, s6, next_q, watch = _s6(x, c, cont, brand, pk, attempt, compact=compact)

    slots: dict[str, tuple[list, dict]] = {"s0": (s0["pairs"], s0), "s1": (p1, s1), "s2": (p2, s2), "s3a": (p3a, s3a), "s3b": (p3b, s3b),
                                           "s3c": (p3c, s3c), "s4": (p4, s4), "s5": (p5, s5), "s6": (p6, s6)}
    drops = list(GLOBAL_DROP)
    while sum(len(_text(p)) for p, _ in slots.values()) > TOTAL_MAX and drops:
        sid, step = drops.pop(0)
        pairs, info = slots[sid]
        slots[sid] = ([p for p in pairs if p[0] != step], info)
    scenes = []
    mins = {"s0": 4.0, "s1": 2.5, "s2": 7.0, "s3a": 7.0, "s3b": 7.0, "s3c": 7.0, "s4": 7.0, "s5": 8.0, "s6": 5.0}
    for sid, (pairs, info) in slots.items():
        tts, steps = _steps(pairs)
        info["tts"], info["steps"] = tts, steps
        scenes.append({"id": sid, "min": mins[sid], "tts": tts, "sub": "" if sid in ("s0", "s6") else tts, "steps": steps})
    if s3b.get("support") and not any(st == "support" for st in s3b["steps"]):      # 말하지 않은 자사주 카드는 화면에도 안 띄운다
        s3b["support"] = None
    if s5.get("callback") and "callback" not in s5["steps"]:                        # 말하지 않은 S0 콜백 칩·한계 문장·어제 대비 칩도 화면에서 뺀다(말마다 화면 반응)
        s5["callback"], s5["callback_num"] = None, None
    if s5.get("limit") and "limit" not in s5["steps"]:
        s5["limit"] = None
    if s4.get("calc") and "calc" not in s4["steps"]:      # 계산 문장이 예산에서 빠졌으면 화면 칩도 검산 대상도 아니다(말한 것만 검산한다)
        s4["calc"] = None
    if "y" not in s3b["steps"]:
        for row in s3b.get("out") or []:
            row["y"] = None
    hunter = {k: {kk: vv for kk, vv in v.items() if kk not in ("tts", "pairs")} for k, v in
              (("s0", s0), ("s1", s1), ("s2", s2), ("s3a", s3a), ("s3b", s3b), ("s3c", s3c), ("s4", s4), ("s5", s5), ("s6", s6))}
    P, amount, sold = x["P"], x["amount"], x["sold"]
    ct = na.contrast(x["k"], c.get("recent_closes") or [], sold) if x["k"] else {"kind": "pct", "text": "", "short": "", "line": None, "n_days": None, "opposite": False}
    opp = [(n, v) for n, v in x["opp"] if n != P]
    bars = [{"name": P, "v": amount}] + [{"name": n, "v": v} for n, v in opp] + [{"name": n, "v": v} for n, v in x["same"]]
    seen_n = {b["name"] for b in bars}
    bars += [{"name": n, "v": v} for n, v in x["vals"].items() if n not in seen_n]
    s2_title = f"{P} {_won_screen(amount, True)},<br>{'·'.join(n for n, _ in opp) or '—'}{'이' if opp else ''} {'받았다' if sold else '팔았다'}"
    lead_th = x["out_th"] if (x["out_th"] and x["out_t"] and (not x["in_t"] or abs(x["out_t"]) >= x["in_t"])) else x["in_th"]
    story_lead = {"theme": lead_th, "t": (x["themes"].get(lead_th) or {}).get("net"), "who": "외국인+기관 합산",
                  "names": (x["themes"].get(lead_th) or {}).get("pos_names") or []} if lead_th else None
    cb = x["cb"]
    cbv = None
    if cb and isinstance(cb.get("check"), dict):
        ch = cb["check"]
        cbv = {"q": cb.get("q"), "kind": ch.get("kind"), "theme": ch.get("theme") or ch.get("name") or "", "n": ch.get("n"), "sign": ch.get("sign"),
               "when": _day_word(d, cb.get("prev_date"), past=True), "ok": cb.get("ok"), "amount": cb.get("t")}
    nd = na.next_trading_day(d)
    tag_when = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    return {
        "format": "brief", "brand": brand, "tagline": f"오늘 국장, 누가 샀나? · 평일 {tag_when}",
        "hook": hook_parts[0], "hook_parts": hook_parts, "hook_id": hook_kind,
        "devices": sorted({q_kind, n_kind, k_kind, v_kind}), "caution_id": None,
        "next_q": next_q, "watch": [{"q": w["q"], "how": f"{_day_word(d, nd.strftime('%Y%m%d'), past=False)} 15:40 수급에서 확인", "assist": "", "spoken": w.get("spoken") or w["q"]} for w in watch],
        "protagonist": {"name": P, "amount": amount, "sold": sold}, "contrast": ct,
        "check": {"verdict": cbv, "record": c.get("ledger_stats"), "next_q": next_q, "next_day": f"{nd.month}/{nd.day}"},
        "bars": bars, "s2_title": s2_title, "s3_title": lead_th or "", "s3_story": ({"verdict": None, "lead": story_lead, "summary": ""} if story_lead else None),
        "s2_marks": {"answer": "기타법인", "counter": None, "bars": None, "snap": None, "prev": x["prev_inv"].get("others")},
        "event_used": (bool(x["ev"]) and any(o.get("source") == "이슈 메모" for o in (s5.get("news") or []))) or hook_kind == "M4",
        "others_top": na._others_top({**c, "date": d}), "weekend_watch": wk_rows,
        "fx_said": False, "bonding": "", "attempt": attempt, "compact": compact,
        "scenes": scenes, "hunter": hunter,
    }


def lint(scenes: list[dict]) -> list[str]:
    """자체 점검(정식 검사는 qa_script.check_brief) — 숫자 3토큰 이상 · 그런데 2회/연속 · 화면 지시어 <4 · 길이 950~1,150."""
    out = [w for w in nh.lint(scenes) if not w.startswith("[전체]") and "> 예산" not in w]
    total = sum(len(sc.get("tts") or "") for sc in scenes)
    if total > TOTAL_MAX:
        out.append(f"[전체] {total}자 > {TOTAL_MAX}자")
    elif total < TOTAL_MIN:
        out.append(f"[전체] {total}자 < {TOTAL_MIN}자(경고)")
    return out


def check_brief(scenes: list[dict], comp: dict, recs: list[dict] | None = None) -> list[str]:
    """브리핑 검사 — qa_script.check_brief 가 있으면 그것(정식), 없으면 check_hunter 11항 + 설계 §3 고정 내용을 여기서. 실패 '[장면] 규칙 :: 문장'."""
    if _qa is not None and hasattr(_qa, "check_brief"):
        return _qa.check_brief(scenes, comp, recs)
    bad: list[str] = []
    if _qa is not None:
        try:
            bad += _qa.check_hunter(scenes, comp, recs)
        except Exception as e:  # noqa: BLE001
            bad.append(f"[all] 검사 예외 {e!r} :: ")
    by = {str(s.get("id")): (s.get("tts") or "") for s in scenes or []}
    sent = {k: sm.sentences(v) for k, v in by.items()}

    def fail(sid: str, rule: str, s: str = "") -> None:
        bad.append(f"[{sid}] {rule} :: {s}")

    if not all(n in by.get("s2", "") for n in ("외국인", "기관", "개인")):
        fail("s2", "외국인·기관·개인 세 이름이 다 없음", (sent.get("s2") or [""])[0])
    if sum(_ntok(s) for s in sent.get("s2", [])) < 3:
        fail("s2", "숫자 3개 미만", (sent.get("s2") or [""])[0])
    if "코스피" not in by.get("s3a", "") or "코스닥" not in by.get("s3a", ""):
        fail("s3a", "코스닥·코스피 없음", (sent.get("s3a") or [""])[0])
    if not re.search(r"빠졌|나갔|순매도", by.get("s3b", "")):
        fail("s3b", "빠졌|나갔|순매도 없음", (sent.get("s3b") or [""])[0])
    if not re.search(r"들어왔|순매수|들어온 곳이 없었", by.get("s3c", "")):
        fail("s3c", "들어왔|순매수|들어온 곳이 없었 없음", (sent.get("s3c") or [""])[0])
    h = (comp or {}).get("hunter") or {}
    s4h = h.get("s4") or {}
    names = [s.get("name") for s in (s4h.get("stocks") or []) if s.get("name")]
    if names and not all(n in by.get("s4", "") for n in names):
        fail("s4", "두 종목 이름이 다 없음", (sent.get("s4") or [""])[0])
    for p in (("외국인", "기관") if s4h.get("no_indiv") else ("외국인", "기관", "개인")):
        if names and p not in by.get("s4", ""):
            fail("s4", f"주체 없음({p})", (sent.get("s4") or [""])[-1])
    s5 = by.get("s5", "")
    if "뉴스" not in s5:
        fail("s5", "뉴스 없음", (sent.get("s5") or [""])[0])
    if "쪽입니다" not in s5 or "뒤집히는 조건" not in s5:
        fail("s5", "판정(쪽입니다)·뒤집히는 조건 없음", (sent.get("s5") or [""])[-1])
    if "누가샀나였습니다" not in by.get("s6", "") or "국장 마감은" not in by.get("s6", ""):
        fail("s6", "시그니처 없음", (sent.get("s6") or [""])[-1])
    total = sum(len(v) for v in by.values())
    if total > TOTAL_MAX:
        fail("all", f"총 {total}자 > {TOTAL_MAX}자", "")
    return bad
