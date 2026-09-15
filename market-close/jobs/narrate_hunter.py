"""국장편 v4 '헌터 포맷' 대본 — 경제사냥꾼 완주 장치 7슬롯(S0~S6)을 15:55 자동 제작에 옮긴 것.
정본 docs/SCRIPT_SYSTEM_HUNTER_v1.0.md(슬롯·문장 규칙 10·체크리스트 11) · 설계 docs/HUNTER_FORMAT_DESIGN.md §1·§6.1(인터페이스 계약).

코드가 지키는 것:
  - 슬롯 순서 고정 s0 s1 s2 s3a s3b s3c s4 s5 s6. 데이터가 빠져도 슬롯을 비우지 않는다 — 슬롯마다 대체 후보가 있다(각 _sX 함수 주석).
  - 틀 문장마다 후보 3벌 이상 → script_memory.pick 이 전 편에 없던 문장을 고른다. avoid(검사에 걸린 문장)를 만든 후보는 뺀다.
  - 이어지는 사실(script_memory.continuity)은 처음 말하듯 하지 않는다: "오늘도 마찬가지로 기타법인이 가장 많이 샀습니다. N일째입니다."
  - 한 문장 한 숫자(qa 기준 최대 2 토큰). 억 단위 반올림('1조 6천억'), 소수점은 %에만. '그런데'는 블록당 1회, 연속 금지.
  - 화면 지시어: S2 1개 + S3 블록마다 1개 + S4 '여기 이 칸'. S4 계산은 코드가 검산한 값만 말한다(calc.verified).
  - 종목 추천·매매 판단 없음(사라/팔아라/비중/관망/전망). '여러분'·자기 채널 과거 영상 언급 없음. 마지막 문장은 판정/관측값.
반환은 narrate_aplus.build_aplus 와 같은 키 + format="hunter" + hunter(화면용 사전, 장면마다 steps).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from narrate import _and, _bat, _won_screen, josa, obj, ro, subj
import narrate_aplus as na
import script_memory as sm

AFTER_MARKET_NOTICE_UNTIL = na.AFTER_MARKET_NOTICE_UNTIL
NAME_KEY = na.NAME_KEY
KEY_NAME = {v: k for k, v in NAME_KEY.items()}
HAN = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
DAYS = {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레", 8: "여드레", 9: "아흐레", 10: "열흘"}
WD = "월화수목금토일"
_DG = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ── 숫자 말하기 ──
def hwon(v: float | None) -> str:
    """억 → 말·자막용. 소수점 없이 억 단위 반올림: 15736→'1조 6천억', 8324→'8,300억', 9044→'9천억', 937→'940억'."""
    if v is None:
        return "미확정"
    a = abs(round(v))
    if a >= 10000:
        jo, rem = divmod(a, 10000)
        k = int(round(rem / 1000.0))
        if k >= 10:
            jo, k = jo + 1, 0
        return f"{jo}조" if k == 0 else f"{jo}조 {k}천억"
    if a >= 1000:
        h = int(round(a / 100.0)) * 100
        if h >= 10000:
            return "1조"
        return f"{h // 1000}천억" if h % 1000 == 0 else f"{h:,}억"
    if a >= 100:
        return f"{int(round(a / 10.0)) * 10:,}억"
    return f"{a}억"


def hshort(v: float | None) -> str:
    """화면용 짧은 금액 '1.6조' / '8,300억'."""
    if v is None:
        return "—"
    a = abs(round(v))
    if a >= 10000:
        return f"{a / 10000:.1f}조".replace(".0조", "조")
    return f"{a:,}억"


def pct_s(v: float | None) -> str:
    return "미확정" if v is None else f"{abs(v):.2f}%"


def han(n: int) -> str:
    return HAN.get(n, str(n))


def dko(n: int) -> str:
    """N일째 — 열흘까지는 우리말 수사."""
    return f"{DAYS[n]}째" if n in DAYS else f"{n}일째"


def _ngroups(s: str) -> int:
    return len(_DG.findall(s or ""))


def _sig_pct(v: float) -> str:
    return f"{'플러스' if v > 0 else '마이너스'} {abs(v):.2f}%"


# ── 후보 고르기 ──
class Picker:
    """script_memory.pick 을 감싼다: avoid 로 후보가 다 빠지면 avoid 없이 다시, 그래도 없으면 첫 후보.
    후보 문장 중 한 문장에 숫자 토막이 3개 이상인 것은 먼저 뺀다(문장 규칙 2)."""

    def __init__(self, d: str, exact: dict, masked: dict, avoid: set[str] | None):
        self.d, self.exact, self.masked, self.avoid = d, exact, masked, set(avoid or [])
        self.used: set[str] = set()          # 같은 편 안에서 같은 문장을 두 번 쓰지 않는다

    def __call__(self, cands: list[str], fallback: str = "") -> str:
        cands = [c.strip() for c in cands if c and c.strip()]
        safe = [c for c in cands if all(_ngroups(x) <= 2 for x in sm.sentences(c))]
        cands = safe or cands
        cands = [c for c in cands if sm.norm(c) not in self.used] or cands
        if not cands:
            return fallback
        r = ""
        try:
            r = sm.pick(cands, self.d, self.exact, self.masked, avoid=self.avoid or None)
            if not r:
                r = sm.pick(cands, self.d, self.exact, self.masked)
        except Exception:
            r = ""
        r = r or cands[int(self.d[-2:]) % len(cands)]
        self.used.add(sm.norm(r))
        return r


def _rot(d: str, n: int) -> int:
    """종류 회전용 색인 — 날짜 숫자합(같은 달 안에서 요일마다 다르게)."""
    return sum(int(ch) for ch in d if ch.isdigit()) % max(n, 1)


def _recent_ids(d: str, key: str, n: int = 3) -> set[str]:
    """최근 n편이 쓴 hook_id / devices — 그 종류는 오늘 빼고 고른다."""
    out: set[str] = set()
    try:
        for r in sm._prev_kr(d, n):
            v = (r.get("facts") or {}).get(key)
            if isinstance(v, list):
                out |= {str(x) for x in v}
            elif v:
                out.add(str(v))
    except Exception:
        pass
    return out


def _choose(kinds: list[str], recent: set[str], d: str) -> str:
    """후보 종류 중 최근 편에 없던 것에서 회전. 다 최근이면 전체에서 회전."""
    pool = [k for k in kinds if k not in recent] or list(kinds)
    return pool[_rot(d, len(pool))]


def _steps(pairs: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """[(단계, 문장들)] → (tts, 문장별 단계 이름). 한 단계에 문장이 둘이면 이름을 나눠 붙인다(화면은 문장 수 = 단계 수)."""
    tts, names = [], []
    for name, text in pairs:
        ss = sm.sentences(text)
        for i, s in enumerate(ss):
            tts.append(s)
            names.append(name if i == 0 else f"{name}{i + 1}")
    return " ".join(tts), names


def _day_word(d: str, other: str | None, past: bool) -> str:
    """어제/내일, 아니면 지난 X요일/X요일. 날짜를 모르면 어제/내일."""
    if not other:
        return "어제" if past else "내일"
    try:
        return na._day_word(d, datetime.strptime(other, "%Y%m%d"), past)
    except Exception:
        return "어제" if past else "내일"


def _prev_weekday(d: str) -> str:
    t = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while t.weekday() >= 5:
        t -= timedelta(days=1)
    return t.strftime("%Y%m%d")


def _fix_won(s: str) -> str:
    """'약 2.9조를 팔았습니다' → '2조 9천억을 팔았습니다' (weekend_watch.answer 가 won() 꼴로 준다)."""
    JOSA = {"를": "을", "가": "이", "는": "은", "로": "으로", "와": "과", "였": "이었"}
    s = re.sub(r"약 (\d+)\.(\d)조(를|가|는|로|와|였)?", lambda m: f"{m.group(1)}조 {m.group(2)}천억" + (JOSA[m.group(3)] if m.group(3) else ""), s or "")
    return s.replace("약 ", "")


def _f1_verdict(x: dict) -> str:
    """F1: 받는 쪽이 버텼다(b) / 파는 쪽이 줄었다(a) — 주인공이 이틀 이상 같은 방향이고 어제의 절반 이상이면 b."""
    yv = x.get("y_P")
    return "b" if (x["st_p"] >= 2 and (not isinstance(yv, (int, float)) or abs(x["amount"]) >= 0.5 * abs(yv))) else "a"


def _mult_word(v: float) -> str:
    """배수 말 — 6.46 → '여섯 배 넘는', 1.97 → '두 배 가까이', 5.02 → '다섯 배'. 열 배 넘으면 숫자로."""
    if v >= 10.5:
        return f"{int(v + 0.5)}배"
    n, frac = int(v), v - int(v)
    if frac < 0.15:
        return f"{han(n)} 배"
    if frac > 0.85:
        return f"{han(n + 1)} 배 가까이"
    return f"{han(n)} 배 이상"


# ── 오늘 사실 모으기 ──
def _ctx(c: dict) -> dict:
    """대본이 쓰는 사실을 한 번에 뽑는다. 없는 키는 None/빈 값 — 어느 슬롯도 여기서 죽지 않는다."""
    d = c.get("date") or datetime.now().strftime("%Y%m%d")
    inv = c.get("inv") or {}
    k = c.get("kospi") or {}
    P, amount = na.protagonist(inv) if inv else ("외국인", 0)
    amount = amount or 0
    sold = amount < 0
    streak = c.get("inv_streak") or {}
    st_p = abs((streak.get(NAME_KEY.get(P, "")) or {}).get("streak") or 0)
    vals = {n: inv.get(key) for n, key in NAME_KEY.items() if isinstance(inv.get(key), (int, float))}
    buyers = sorted([(n, v) for n, v in vals.items() if v > 0], key=lambda x: -x[1])
    sellers = sorted([(n, v) for n, v in vals.items() if v < 0], key=lambda x: x[1])
    opp = buyers if sold else sellers                  # 주인공과 반대로 간 쪽(받은 쪽)
    same = [(n, v) for n, v in (sellers if sold else buyers) if n != P]
    oth = vals.get("기타법인") or 0
    top_others = [x for x in (c.get("top_others") or []) if isinstance(x, dict) and (x.get("v") or 0) > 0][:2]
    act = na._active_buybacks(d, c.get("buybacks") or [])
    oth_share = (sum(x["v"] for x in top_others) / oth) if (oth > 0 and top_others) else 0.0
    oth_in_bb = [x for x in top_others if x.get("code") in act]
    prev_inv = c.get("prev_inv") or {}
    y_vals = {n: prev_inv.get(key) for n, key in NAME_KEY.items() if isinstance(prev_inv.get(key), (int, float))}
    y_buyers = sorted([(n, v) for n, v in y_vals.items() if v > 0], key=lambda x: -x[1])
    prev_date = c.get("prev_date") or ((c.get("callback") or {}).get("prev_date") if isinstance(c.get("callback"), dict) else None) or _prev_weekday(d)
    # 업종 흐름: theme_table(전 업종) 이 있으면 그걸로, 없으면 moves+top_move
    moves = [m for m in (c.get("moves") or []) if isinstance(m, dict) and m.get("theme")]
    top_mv = c.get("top_move") if isinstance(c.get("top_move"), dict) and c["top_move"].get("theme") else None
    table = {th: v for th, v in (c.get("theme_table") or {}).items() if isinstance(v, (int, float))}
    table_y = {th: v for th, v in (c.get("theme_table_y") or {}).items() if isinstance(v, (int, float))}
    by_theme = {m["theme"]: m for m in moves}
    if top_mv:
        by_theme.setdefault(top_mv["theme"], top_mv)
    flows = dict(table) if table else {th: (m.get("t") or 0) for th, m in by_theme.items()}
    out_th = min(flows, key=flows.get) if flows and min(flows.values()) < 0 else None
    in_th = max(flows, key=flows.get) if flows and max(flows.values()) > 0 else None
    out_t = flows.get(out_th) if out_th else None
    in_t = flows.get(in_th) if in_th else None
    out_y = (by_theme.get(out_th) or {}).get("y") if out_th else None
    if out_y is None and out_th and table_y:
        out_y = table_y.get(out_th)
    out_m = by_theme.get(out_th) or {}
    in_m = by_theme.get(in_th) or {}
    ev = c.get("event") if isinstance(c.get("event"), dict) else {}
    ev_st = [x for x in (ev.get("stocks") or []) if isinstance(x, dict)]
    ev_flow = sum((x.get("foreign") or 0) + (x.get("inst") or 0) for x in ev_st)
    ev_indiv = sum((x.get("indiv") or 0) for x in ev_st)
    it = c.get("intraday") if isinstance(c.get("intraday"), dict) else {}
    snap = (it.get("snap") or {}).get(NAME_KEY.get(P, ""))
    at = str(it.get("at") or "14:00")
    snap_ok = (isinstance(snap, (int, float)) and at[:2].isdigit() and int(at[:2]) < 15
               and abs(snap) >= 100 and (snap < 0) == sold and abs(amount) >= 3 * abs(snap))
    kq = c.get("kosdaq") if isinstance(c.get("kosdaq"), dict) else {}
    if "close" in kq and "foreign" not in kq:        # 지수 사전이 들어왔으면 수급이 아니다
        kq = {}
    kqi = c.get("kosdaq_index") if isinstance(c.get("kosdaq_index"), dict) else {}
    sflows = c.get("stock_flows") if isinstance(c.get("stock_flows"), dict) else {}
    chg = k.get("chg_pct") if isinstance(k.get("chg_pct"), (int, float)) else 0.0
    return {
        "d": d, "P": P, "amount": amount, "sold": sold, "st_p": st_p, "inv": inv, "vals": vals, "buyers": buyers, "sellers": sellers,
        "opp": opp, "same": same, "oth": oth, "top_others": top_others, "act": act, "oth_share": oth_share, "oth_in_bb": oth_in_bb,
        "prev_inv": prev_inv, "y_vals": y_vals, "y_buyers": y_buyers, "y_P": y_vals.get(P), "prev_date": prev_date,
        "moves": moves, "flows": flows, "out_th": out_th, "out_t": out_t, "out_y": out_y, "out_m": out_m,
        "in_th": in_th, "in_t": in_t, "in_m": in_m,
        "ev": ev, "ev_st": ev_st, "ev_flow": ev_flow, "ev_indiv": ev_indiv, "ev_avg": ev.get("avg_pct"),
        "snap": snap, "snap_ok": snap_ok, "kq": kq, "kqi": kqi, "sflows": sflows, "chg": chg, "k": k,
        "cb": c.get("callback") if isinstance(c.get("callback"), dict) else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# S0 모순 후킹 — 두 숫자가 부딪힌다. 종류 M1~M7(설계 §1), 첫 단어는 숫자 또는 주체, 인사·날짜·채널명 없음.
# 종류마다 첫 문장·둘째 문장 후보 3벌 이상. 최근 3편의 hook_id 와 같은 종류, 뼈대·꼬리가 같은 문장은 뺀다.
# 대체: 조건에 맞는 종류가 없으면 M1 완화형(주인공 금액 ↔ 지수 등락)으로 — S0 는 늘 나온다.
# ══════════════════════════════════════════════════════════════════════════════
def _s0_candidates(x: dict) -> dict[str, dict]:
    P, amt, sold, st, chg = x["P"], x["amount"], x["sold"], x["st_p"], x["chg"]
    A = hwon(amt)
    v_p = "팔았" if sold else "샀"
    gave = "내놓은" if sold else "사들인"
    dirw = "내렸" if chg < 0 else "올랐"
    B = pct_s(chg)
    stw = f"{dko(st)}, " if st >= 2 else ""
    out: dict[str, dict] = {}
    # M1 주인공 큰 금액 ↔ 지수는 조금만 움직임
    if abs(amt) >= 5000 and 0.05 <= abs(chg) < 1.0 and (sold == (chg < 0)):
        out["M1"] = {
            "l1": [f"{subj(P)} {stw}오늘만 {obj(A)} {v_p}습니다.",
                   f"{A}, 오늘 {subj(P)} {gave} 물량입니다.",
                   f"{P} {'순매도' if sold else '순매수'} {A}, {dko(st) if st >= 2 else '오늘 하루치'}입니다.",
                   f"{subj(P)} 오늘 {'판' if sold else '산'} 돈은 {A}입니다."],
            "l2": [f"코스피는 {B}밖에 안 {dirw}습니다.",
                   f"코스피는 {B} {'내리는' if chg < 0 else '오르는'} 데 그쳤습니다.",
                   f"지수는 {B} {dirw}을 뿐입니다.",
                   f"코스피 {'하락' if chg < 0 else '상승'}은 {B}가 전부였습니다."],
            "a": {"label": f"{P} {'순매도' if sold else '순매수'}", "value": hshort(amt), "num": amt, "unit": "억"},
            "b": {"label": "코스피", "value": _sig_pct(chg), "num": chg, "unit": "%"}}
    # M2 오후 2시 스냅 ↔ 마감(세 배 이상)
    if x["snap_ok"]:
        S, mult = hwon(x["snap"]), abs(amt) / abs(x["snap"])
        mw = _mult_word(mult)
        out["M2"] = {
            "l1": [f"{subj(P)} 오후 2시까지 {'판' if sold else '산'} 건 {S}이었습니다.",
                   f"{S}, {subj(P)} 오후 2시까지 {'판' if sold else '산'} 물량입니다.",
                   f"{josa(P)} 오후 2시엔 {S}밖에 {'팔지' if sold else '사지'} 않았습니다.",
                   f"{P} {'순매도' if sold else '순매수'}는 오후 2시에 {S}이었습니다."],
            "l2": [f"마감엔 {subj(A)} 됐습니다. {mw}입니다.",
                   f"장 마감까지 {obj(A)} {v_p}습니다. {ro(mw)} 불었습니다.",
                   f"마지막 한 시간 반에 {ro(A)} 늘었습니다. {mw}입니다.",
                   f"마감 숫자는 {A}. {subj(mw)} 막판에 나왔습니다."],
            "a": {"label": f"{P} 오후 2시", "value": hshort(x["snap"]), "num": x["snap"], "unit": "억"},
            "b": {"label": f"{P} 마감", "value": hshort(amt), "num": amt, "unit": "억"}}
    # M3 한 업종 유출 ↔ 그 업종 값은 거의 그대로
    om = x["out_m"] or {}
    ret = om.get("ret")
    if x["out_th"] and (x["out_t"] or 0) <= -10000 and isinstance(ret, (int, float)) and abs(ret) < 1.0:
        th, T = x["out_th"], hwon(x["out_t"])
        out["M3"] = {
            "l1": [f"{T}, 오늘 {th}에서 빠진 돈입니다.",
                   f"{th}에서 {subj(T)} 빠졌습니다.",
                   f"{th} 한 업종에서 나간 돈이 {T}입니다."],
            "l2": [f"{th} 값은 {pct_s(ret)}밖에 안 움직였습니다.",
                   f"그 업종 등락은 {pct_s(ret)}에 그쳤습니다.",
                   f"값은 {pct_s(ret)} {'내렸' if ret < 0 else '올랐'}을 뿐입니다."],
            "a": {"label": f"{th} 외국인·기관", "value": hshort(x["out_t"]), "num": x["out_t"], "unit": "억"},
            "b": {"label": f"{th} 등락", "value": _sig_pct(ret), "num": ret, "unit": "%"}}
    # M4 이슈 종목 평균 +N% ↔ 거기 들어온 큰돈은 작다
    ev, avg, n_ev = x["ev"], x["ev_avg"], len(x["ev_st"])
    if n_ev and isinstance(avg, (int, float)) and avg >= 2.0:
        grp = ev.get("group") or ev.get("label") or "관련주"
        f = x["ev_flow"]
        F = hwon(f) if abs(f) >= 100 else f"{abs(round(f))}억"
        out["M4"] = {
            "l1": [f"{grp} {n_ev}종목이 평균 {pct_s(avg)} 올랐습니다.",
                   f"{pct_s(avg)}, {grp} {n_ev}종목의 오늘 평균입니다.",
                   f"{josa(grp)} {n_ev}종목 평균 {pct_s(avg)} 상승입니다."],
            "l2": ([f"외국인과 기관이 거기 넣은 돈은 {F}{'이었' if _bat(F) else '였'}습니다.",
                    f"그 종목들에 들어온 외국인·기관 돈은 {F}입니다.",
                    f"큰손 돈은 {F}, 그게 전부였습니다."] if f >= 0 else
                   [f"외국인과 기관은 거기서 오히려 {obj(F)} 뺐습니다.",
                    f"그 종목들에서 외국인·기관 돈은 {F} 빠졌습니다.",
                    f"큰손은 오히려 {obj(F)} 팔았습니다."]),
            "a": {"label": f"{grp} 평균", "value": _sig_pct(avg), "num": avg, "unit": "%"},
            "b": {"label": "외국인+기관 유입", "value": hshort(f) if f >= 0 else "−" + hshort(f), "num": f, "unit": "억"}}
    # M5 주인공 N일째 매도 ↔ 지수 반대 방향
    if st >= 2 and abs(chg) >= 0.05 and (sold != (chg < 0)):
        out["M5"] = {
            "l1": [f"{subj(P)} {dko(st)} {v_p}습니다.",
                   f"{P} {'순매도' if sold else '순매수'}가 {dko(st)}입니다.",
                   f"{dko(st)}입니다, {subj(P)} {'파는' if sold else '사는'} 날이."],
            "l2": [f"코스피는 {B} {dirw}습니다.",
                   f"그래도 지수는 {B} {dirw}습니다.",
                   f"코스피 {'상승' if chg > 0 else '하락'}은 {B}입니다."],
            "a": {"label": f"{P} {'순매도' if sold else '순매수'}", "value": dko(st), "num": st, "unit": "일째"},
            "b": {"label": "코스피", "value": _sig_pct(chg), "num": chg, "unit": "%"}}
    # M6 개인 순매수 ↔ 기타법인이 그 두 배
    ind, oth = x["vals"].get("개인") or 0, x["oth"]
    if ind > 0 and oth >= 1.8 * ind:
        r = oth / ind
        rw = _mult_word(r)
        out["M6"] = {
            "l1": [f"개인이 {obj(hwon(ind))} 샀습니다.",
                   f"개인 순매수 {hwon(ind)}입니다.",
                   f"{hwon(ind)}, 오늘 개인이 산 돈입니다."],
            "l2": [f"기타법인은 그 {rw}, {obj(hwon(oth))} 샀습니다.",
                   f"기타법인 순매수는 {rw}, {hwon(oth)}입니다.",
                   f"그런데 기타법인이 그 {rw} 샀습니다. {hwon(oth)}입니다."],
            "a": {"label": "개인 순매수", "value": hshort(ind), "num": ind, "unit": "억"},
            "b": {"label": "기타법인 순매수", "value": hshort(oth), "num": oth, "unit": "억"}}
    # M7 어제 한 업종 유출 ↔ 오늘 가장 큰 유입은 그 N분의 1
    if x["out_th"] and isinstance(x["out_y"], (int, float)) and x["out_y"] <= -10000 and x["in_th"] and (x["in_t"] or 0) >= 100:
        kk = round(abs(x["out_y"]) / x["in_t"])
        if kk >= 3:
            wy = _day_word(x["d"], x["prev_date"], past=True)
            Y, I = hwon(x["out_y"]), hwon(x["in_t"])
            out["M7"] = {
                "l1": [f"{Y}, {wy} {x['out_th']}에서 빠진 돈입니다.",
                       f"{x['out_th']}에서 {wy} 나간 돈은 {Y}였습니다.",
                       f"{subj(Y)} {wy} {x['out_th']} 한 곳에서 빠졌습니다."],
                "l2": [f"오늘 가장 큰 유입은 {x['in_th']}, {I}입니다.",
                       f"오늘 돈이 가장 많이 들어간 {josa(x['in_th'])} {I}입니다.",
                       f"오늘 들어온 돈 1위 {josa(x['in_th'])} {I}에 그쳤습니다."],
                "a": {"label": f"{wy} {x['out_th']} 유출", "value": hshort(x["out_y"]), "num": x["out_y"], "unit": "억"},
                "b": {"label": f"오늘 {x['in_th']} 유입", "value": hshort(x["in_t"]), "num": x["in_t"], "unit": "억"}}
    if not out:   # 대체: 아무 조건도 안 맞는 날 — 주인공 금액과 지수 등락을 나란히 놓는다(충돌은 약해도 두 숫자는 있다)
        out["M1"] = {
            "l1": [f"{subj(P)} {stw}오늘 {obj(A)} {v_p}습니다.",
                   f"{A}, 오늘 {subj(P)} {gave} 돈입니다.",
                   f"{P} {'순매도' if sold else '순매수'} {A}입니다."],
            "l2": [f"코스피는 {B} {dirw}습니다." if abs(chg) >= 0.05 else f"코스피 등락은 {B}, 제자리였습니다.",
                   f"지수 등락은 {B}였습니다.",
                   f"코스피 {'하락' if chg < 0 else '상승'} 폭은 {B}입니다." if abs(chg) >= 0.05 else f"코스피는 {B}, 그대로였습니다."],
            "a": {"label": f"{P} {'순매도' if sold else '순매수'}", "value": hshort(amt), "num": amt, "unit": "억"},
            "b": {"label": "코스피", "value": _sig_pct(chg) if chg else "0%", "num": chg, "unit": "%"}}
    return out


def _s0(x: dict, pk: Picker) -> tuple[str, list, dict]:
    d = x["d"]
    cands = _s0_candidates(x)
    recent_ids = _recent_ids(d, "hook_id")
    # 최근 3편 첫 장면과 같은 소리(뼈대·꼬리·머리)인 문장은 뺀다 — narrate_aplus._pick_hook 과 같은 기준
    try:
        recent_s0 = na._recent_s0(d)
    except Exception:
        recent_s0 = []
    seen_sk = {na._skeleton(s) for t in recent_s0 for s in sm.sentences(t)}
    tails = {re.sub(r"\s+", "", t)[-7:] for t in recent_s0 if t}
    heads = {na._skeleton(sm.sentences(t)[0])[:14] for t in recent_s0 if sm.sentences(t)}

    def fresh(lines: list[str], head: bool) -> list[str]:
        ok = []
        for s in lines:
            parts = sm.sentences(s)
            if any(na._skeleton(p) in seen_sk for p in parts):
                continue
            if re.sub(r"\s+", "", s)[-7:] in tails:
                continue
            if head and parts and na._skeleton(parts[0])[:14] in heads:
                continue
            ok.append(s)
        return ok or lines
    order = [k for k in ("M2", "M6", "M1", "M4", "M7", "M5", "M3") if k in cands]
    kind = _choose(order, recent_ids, d)
    spec = cands[kind]
    l1 = pk(fresh(spec["l1"], head=True))
    l2 = pk(fresh(spec["l2"], head=False))
    tts, steps = _steps([("a", l1), ("b", l2)])
    return kind, [l1, l2], {"kind": kind, "a": spec["a"], "b": spec["b"], "tts": tts, "steps": steps}


# ══════════════════════════════════════════════════════════════════════════════
# S5 프레임(양면 판정) — S1 의 질문은 여기서 나온다. 프레임 F1~F4(설계 §1), 데이터 조건 + 최근 3편 제외 + 회전.
# ══════════════════════════════════════════════════════════════════════════════
def _frames(x: dict) -> list[str]:
    ok = []
    if x["sold"] and x["buyers"]:
        ok.append("F1")
    if x["out_th"] and x["in_th"]:
        ok.append("F2")
    if x["P"] in ("외국인", "기관"):
        ok.append("F3")
    if x["oth"] > 0 and x["oth_in_bb"] and x["oth_share"] >= 0.6:
        ok.append("F4")
    return ok or ["F3"]


_FRAME_PREF = {"M1": ["F1", "F3", "F4", "F2"], "M2": ["F1", "F3", "F2", "F4"], "M5": ["F3", "F1", "F2", "F4"],
               "M6": ["F4", "F1", "F3", "F2"], "M7": ["F2", "F1", "F4", "F3"], "M3": ["F2", "F3", "F1", "F4"], "M4": ["F2", "F4", "F1", "F3"]}


def _pick_frame(x: dict, hook_kind: str) -> str:
    allowed = _frames(x)
    recent = _recent_ids(x["d"], "devices")
    pref = [f for f in _FRAME_PREF.get(hook_kind, ["F1", "F2", "F3", "F4"]) if f in allowed] or allowed
    pool = [f for f in pref if f not in recent] or pref
    return pool[0]


_Q = {  # 프레임별 '오늘의 질문'(누가/얼마/언제까지 꼴 하나). 문장 안에 박혀도 질문으로 읽히게 끝은 늘 '느냐'.
    "F1": ["이 물량을 누가 받았느냐", "왜 이만큼만 빠졌느냐", "누가 버텼느냐"],
    "F1a": ["누가 손을 뗐느냐", "왜 이만큼만 빠졌느냐", "파는 손이 줄었느냐 받는 손이 버텼느냐"],
    "F2": ["그 돈이 어디로 갔느냐", "빠진 돈이 자리를 옮겼느냐", "나간 돈이 어디에 닿았느냐"],
    "F3": ["같은 손이 며칠째 팔았느냐", "하루 사정으로 봐야 하느냐, 방향으로 봐야 하느냐", "이 순매도가 며칠째 이어졌느냐"],
    "F4": ["이 돈이 새 돈으로 들어왔느냐", "받은 돈이 바깥에서 왔느냐 회사에서 왔느냐", "누구 돈으로 받았느냐"],
}


def _s1(x: dict, frame: str, pk: Picker) -> tuple[str, dict]:
    qs = list(_Q.get(frame) or _Q["F1"])
    if frame == "F3" and not x["sold"]:
        qs = ["같은 손이 며칠째 샀느냐", "하루 사정으로 봐야 하느냐, 방향으로 봐야 하느냐", "이 순매수가 며칠째 이어졌느냐"]
    if frame == "F1" and _f1_verdict(x) == "a":
        qs = list(_Q["F1a"])
    elif frame == "F1" and not (abs(x["chg"]) < 1.0):
        qs = ["이 물량을 누가 받았느냐", "누가 받아 냈느냐", "받은 손이 누구였느냐"]
    cands = []
    for q in qs:
        cands += [f"오늘은 {q} 하나만 봅니다.",
                  f"{q}. 오늘은 이것 하나만 봅니다.",
                  f"{q}가 오늘의 전부입니다.",
                  f"답은 하나만 찾습니다. {q}.",
                  f"{q}. 이 질문 하나만 봅니다."]
    s = pk(cands)
    q = next((q for q in qs if q in s), qs[0])
    tts, steps = _steps([("q", s)])
    return s, {"q": q, "frame": frame, "tts": tts, "steps": steps}


# ══════════════════════════════════════════════════════════════════════════════
# S2 대변 → 차단 — 시청자가 할 뻔한 답을 먼저 말하고(생각하기 쉽습니다) 숫자로 인정한 뒤, '그런데' + 화면 지시어로 막는다.
# 뻔한 답 N1~N6(설계 §1: 개인이 받았다 / 기관이 받았다 / 외국인이 돌아왔다 / 지수 올랐으니 돈이 들어왔다 / 새 돈이 들어왔다).
# 이어지는 사실은 continuity 로: 가장 많이 산 쪽이 N일째 같으면 "오늘도 마찬가지로 …, N일째입니다".
# 대체: 기타법인이 작으면 반전은 반대편 두 번째 주체, 그것도 없으면 주인공 편에 선 주체(왼쪽 막대).
# ══════════════════════════════════════════════════════════════════════════════
def _s2(x: dict, cont: dict, hook_kind: str, pk: Picker) -> tuple[str, dict, str]:
    P, sold, vals, oth = x["P"], x["sold"], x["vals"], x["oth"]
    d = x["d"]
    got, v_got = ("받았다", "샀") if sold else ("팔았다", "팔았")
    ind, inst, frg = vals.get("개인"), vals.get("기관"), vals.get("외국인")
    opp = [(n, v) for n, v in x["opp"] if n != P]
    kinds: list[str] = []
    if ind is not None and (ind > 0) == sold and abs(ind) >= 300:
        kinds.append("N1")
    if P != "기관" and inst is not None and (inst > 0) == sold and abs(inst) >= 3000 and opp and opp[0][0] != "기관":
        kinds.append("N2")
    turned = ((x.get("inv") or {}) and ((x.get("inv") or {}).get("foreign") or 0) > 0 and P != "외국인"
              and ((cont.get("yesterday") or {}).get("foreign_streak") or 0) < 0)
    if turned:
        kinds.append("N3")
    if x["chg"] > 0 and ((frg or 0) + (inst or 0)) < -1000:
        kinds.append("N4")
    if oth > 0 and x["oth_in_bb"] and x["oth_share"] >= 0.6 and (hook_kind == "M6" or (x["buyers"] and x["buyers"][0][0] == "기타법인")):
        kinds.append("N6")
    if hook_kind == "M6" and "N1" in kinds and "N6" in kinds:
        kinds.remove("N1")                      # 훅이 이미 '개인 vs 기타법인 두 배'를 말했다 — 개인이 받았다고 다시 대변하면 메아리
    if not kinds:
        kinds = ["N1"] if ind is not None else ["N5"]
    recent = _recent_ids(d, "devices")
    kind = _choose(kinds, recent, d)

    pairs: list[tuple[str, str]] = []
    # ── 뻔한 답 + 인정 ──
    reveal_name, reveal_v, reveal_kind = None, 0, "party"
    naive_name, naive_v, naive_txt = None, 0, ""
    if kind in ("N1", "N2", "N5"):
        naive_name = "개인" if kind in ("N1", "N5") else "기관"
        naive_v = vals.get(naive_name) or 0
        naive_txt = f"{naive_name}이 {got}"
        pairs.append(("naive", pk([f"{naive_name}이 {got}고 생각하기 쉽습니다.",
                                   f"{got.replace('다', '')}은 쪽은 {naive_name}이라고 생각하기 쉽습니다." if sold else f"{naive_name}이 판 거라고 생각하기 쉽습니다.",
                                   f"이 물량은 {naive_name}이 {got}고 보이기 쉽습니다.",
                                   f"{naive_name}이 다 {got}고 생각하기 쉽습니다.",
                                   f"답은 {naive_name}이라고 생각하기 쉽습니다.",
                                   f"{naive_name} 몫이라고 읽히기 쉽습니다."])))
        A = hwon(naive_v)
        top_same = cont.get("top_buyer_days", 1) >= 2 and x["buyers"] and x["buyers"][0][0] == naive_name and sold
        if top_same:
            n = cont["top_buyer_days"]
            pairs.append(("admit", pk([f"오늘도 마찬가지로 {naive_name}이 가장 많이 {v_got}습니다. {dko(n)}입니다.",
                                       f"{naive_name}이 가장 많이 {'산' if sold else '판'} 건 오늘도 같습니다. {dko(n)}입니다.",
                                       f"가장 많이 {'산' if sold else '판'} 쪽은 {dko(n)} {naive_name}입니다.",
                                       f"{dko(n)} {naive_name}이 1위입니다. 맞습니다."])))
            pairs.append(("admit_v", pk([f"오늘 몫은 {A}입니다.", f"{A}, 오늘 숫자입니다.", f"오늘은 {obj(A)} {v_got}습니다."])))
        else:
            pairs.append(("admit", pk([f"{naive_name} {A}, 맞습니다.",
                                       f"{josa(naive_name)} {obj(A)} {v_got}습니다. 맞는 말입니다.",
                                       f"{A}, {naive_name}이 {'산' if sold else '판'} 돈입니다. 틀린 말은 아닙니다.",
                                       f"{naive_name} {'순매수' if sold else '순매도'} {A}, 여기까진 맞습니다.",
                                       f"실제로 {josa(naive_name)} {obj(A)} {v_got}습니다."])))
        # 반전 주체: 기타법인(같은 편, 3천억 이상) → 반대편 둘째 → 주인공 편
        others_side = oth if sold else -oth
        if naive_name != "기타법인" and others_side >= 3000:
            reveal_name, reveal_v = "기타법인", oth
        else:
            rest = [(n, v) for n, v in opp if n != naive_name]
            if rest:
                reveal_name, reveal_v = rest[0]
            elif x["same"]:
                reveal_name, reveal_v, reveal_kind = x["same"][0][0], x["same"][0][1], "same"
    elif kind == "N3":
        naive_name, naive_v = "외국인", frg or 0
        naive_txt = "외국인이 돌아왔다"
        pairs.append(("naive", pk(["외국인이 돌아왔다고 생각하기 쉽습니다.", "외국인 순매수, 돌아섰다고 보이기 쉽습니다.",
                                   "외국인이 사는 쪽으로 돌아왔다고 읽히기 쉽습니다.", "외국인이 다시 들어왔다고 생각하기 쉽습니다.",
                                   "외국인 손이 바뀌었다고 생각하기 쉽습니다."])))
        pairs.append(("admit", pk([f"외국인 {hwon(naive_v)}, 맞습니다.", f"외국인은 {obj(hwon(naive_v))} 샀습니다. 맞는 말입니다.",
                                   f"{hwon(naive_v)}, 외국인이 산 돈입니다. 틀린 말은 아닙니다."])))
        cand = [(n, v) for n, v in x["sellers"] if n != "외국인"]
        if cand:
            reveal_name, reveal_v, reveal_kind = cand[0][0], cand[0][1], "same"
        elif oth > 0:
            reveal_name, reveal_v = "기타법인", oth
    elif kind == "N4":
        naive_name, naive_v = "코스피", x["chg"]
        naive_txt = "지수가 올랐으니 돈이 들어왔다"
        pairs.append(("naive", pk(["지수가 올랐으니 돈이 들어왔다고 생각하기 쉽습니다.", "오른 날이니 큰돈이 샀다고 보이기 쉽습니다.",
                                   "코스피가 올랐으니 외국인이 샀다고 생각하기 쉽습니다.", "상승한 날은 돈이 들어온 날이라고 읽히기 쉽습니다.",
                                   "지수만 보면 돈이 들어온 날로 생각하기 쉽습니다."])))
        pairs.append(("admit", pk([f"코스피 {pct_s(x['chg'])} 상승, 맞습니다.", f"코스피는 {pct_s(x['chg'])} 올랐습니다. 맞는 말입니다.",
                                   f"{pct_s(x['chg'])}, 오늘 코스피 상승 폭입니다. 틀린 말은 아닙니다."])))
        cand = sorted([(n, v) for n, v in x["sellers"] if n in ("외국인", "기관")], key=lambda t: t[1])
        if cand:
            reveal_name, reveal_v, reveal_kind = cand[0][0], cand[0][1], "same"
    else:  # N6 새 돈
        naive_name, naive_v = "기타법인", oth
        naive_txt = "새 돈이 들어왔다"
        pairs.append(("naive", pk(["기타법인이 받았으니 새 돈이 들어왔다고 생각하기 쉽습니다.", "밖에서 새 돈이 들어왔다고 보이기 쉽습니다.",
                                   "기타법인 순매수는 새 돈이라고 읽히기 쉽습니다.", "기타법인이라는 이름 때문에 바깥 돈으로 생각하기 쉽습니다."
                                   .replace(" 때문에", "이라"), "새로 들어온 돈이라고 생각하기 쉽습니다."])))
        n_days = cont.get("others_buy_days") or 0
        top_same = cont.get("top_buyer_days", 1) >= 2 and x["buyers"] and x["buyers"][0][0] == "기타법인"
        if top_same:
            pairs.append(("admit", pk([f"오늘도 마찬가지로 기타법인이 가장 많이 샀습니다. {dko(cont['top_buyer_days'])}, {hwon(oth)}입니다.",
                                       f"가장 많이 산 쪽은 오늘도 기타법인, {dko(cont['top_buyer_days'])}입니다. 오늘 {hwon(oth)}.",
                                       f"기타법인이 1위인 건 {dko(cont['top_buyer_days'])} 같습니다. 오늘 몫은 {hwon(oth)}입니다."])))
        elif n_days >= 2:
            pairs.append(("admit", pk([f"기타법인 순매수는 오늘도 이어졌습니다. {dko(n_days)}, {hwon(oth)}입니다.",
                                       f"오늘도 마찬가지로 기타법인이 샀습니다. {dko(n_days)}, 오늘 {hwon(oth)}.",
                                       f"기타법인은 {dko(n_days)} 사는 중입니다. 오늘 몫은 {hwon(oth)}입니다."])))
        else:
            pairs.append(("admit", pk([f"기타법인 {hwon(oth)}, 맞습니다.", f"기타법인은 {obj(hwon(oth))} 샀습니다. 맞는 말입니다.",
                                       f"{hwon(oth)}, 기타법인이 산 돈입니다. 틀린 말은 아닙니다."])))
        reveal_name, reveal_v, reveal_kind = "기타법인", oth, "buyback"

    # ── 그런데 + 화면 지시어 ──
    if reveal_kind == "buyback":
        pairs.append(("turn", pk(["그런데 그 막대 안을 보세요.", "그런데 오른쪽 끝 막대의 속을 보세요.", "그런데 이 막대는 둘로 쪼개집니다. 아래 칸을 보세요.",
                                  "그런데 막대 밑을 보세요. 이름이 둘 붙습니다.", "그런데 이 돈의 주인은 따로 있습니다. 아래 칸을 보세요.",
                                  "그런데 그 안을 열어 보세요."])))
    elif reveal_kind == "same":
        pairs.append(("turn", pk(["그런데 왼쪽 막대를 보세요.", "그런데 판 쪽도 하나가 아닙니다. 왼쪽 막대를 보세요.",
                                  "그런데 왼쪽에 막대가 하나 더 있습니다.", "그런데 화면 왼쪽을 보세요.",
                                  "그런데 그림 왼쪽이 남았습니다. 보세요.", "그런데 왼쪽 막대가 더 큽니다. 보세요."])))
    else:
        pairs.append(("turn", pk(["그런데 막대가 하나 더 있습니다. 오른쪽 끝을 보세요.", "그런데 오른쪽 끝에 막대가 하나 더 붙습니다.",
                                  "그런데 화면 오른쪽 끝, 네 번째 막대를 보세요.", "그런데 그림이 하나 더 남았습니다. 오른쪽 끝 막대입니다.",
                                  "그런데 오른쪽 끝을 보세요. 막대가 하나 더 있습니다.", "그런데 세 막대가 전부가 아닙니다. 오른쪽 끝을 보세요."])))

    # ── 반전 숫자 + 이어짐 ──
    days = 0
    top = [{"name": t["name"], "v": t["v"]} for t in x["top_others"]]
    if reveal_name == "기타법인" and reveal_kind != "buyback":
        R = hwon(reveal_v)
        is_top = bool(x["buyers"]) and x["buyers"][0][0] == "기타법인" and sold
        if is_top and cont.get("top_buyer_days", 1) >= 2:
            days = cont["top_buyer_days"]
            pairs.append(("reveal", pk([f"오늘도 마찬가지로 기타법인이 가장 많이 샀습니다. {dko(days)}, {R}입니다.",
                                        f"가장 많이 산 쪽은 오늘도 기타법인, {dko(days)}입니다. 오늘 {R}.",
                                        f"기타법인이 1위인 건 {dko(days)} 같습니다. 오늘 몫은 {R}입니다.",
                                        f"{dko(days)} 기타법인이 가장 큰 손이었습니다. {R}."])))
        elif (cont.get("others_buy_days") or 0) >= 2 and reveal_v > 0:
            days = cont["others_buy_days"]
            more = f"{R}, {naive_name}보다 큽니다." if is_top else f"{R}입니다."
            pairs.append(("reveal", pk([f"기타법인 순매수는 오늘도 이어졌습니다. {dko(days)}, {more}",
                                        f"오늘도 마찬가지로 기타법인이 샀습니다. {dko(days)}, 오늘 {more}",
                                        f"기타법인은 {dko(days)} 사는 중입니다. 오늘 몫은 {more}",
                                        f"{dko(days)} 이어진 기타법인 순매수입니다. {more}"])))
        else:
            pairs.append(("reveal", pk([f"기타법인 {R}.", f"기타법인이 {obj(R)} {v_got}습니다.", f"{R}, 기타법인입니다.",
                                        f"기타법인 {'순매수' if reveal_v > 0 else '순매도'} {R}입니다."])))
        # 자사주 연결: 최근 3편에 설명했으면 짧은 동격만
        if reveal_v > 0 and x["oth_in_bb"]:
            _said = _said_buyback(d)
            if not _said:
                pairs.append(("meaning", pk(["회사가 자기 주식을 사면 기타법인으로 잡힙니다. 두 회사 모두 자사주를 사는 중입니다." if len(x["oth_in_bb"]) == 2
                                             else f"회사가 자기 주식을 사면 기타법인으로 잡힙니다. {subj(x['oth_in_bb'][0]['name'])} 자사주를 사는 중입니다.",
                                             "기타법인이란 회사가 자기 주식을 사는 돈이 잡히는 칸입니다. 지금 자사주 매입이 진행 중입니다.",
                                             "이름은 기타법인이지만, 회사가 자기 주식을 사면 이 칸에 잡힙니다. 자사주입니다."])))
            else:
                pairs.append(("meaning", pk(["이 돈은 밖에서 새로 들어온 돈이 아닙니다.", "기타법인, 곧 자사주입니다.",
                                             "이름은 기타법인이지만 속은 자사주입니다.", "새 돈이 아니라 회사가 자기 주식을 산 돈입니다.",
                                             "이 막대의 정체는 자사주입니다.", "바깥 돈이 아니라 회사 예산입니다."])))
            if len(top) == 2 and x["oth_share"] >= 0.5:
                sh = round(x["oth_share"] * 100)
                pairs.append(("top", pk([f"{_and([t['name'] for t in top])}가 {sh}%입니다.",
                                         f"그중 {sh}%가 {_and([t['name'] for t in top])}입니다.",
                                         f"{sh}%는 {_and([t['name'] for t in top])} 두 종목입니다."])))
    elif reveal_kind == "buyback":
        sh = round(x["oth_share"] * 100)
        names = _and([t["name"] for t in top]) if top else "두 회사"
        pairs.append(("reveal", pk([f"{subj(names)} {sh}%입니다.", f"그중 {sh}%가 {names}입니다.", f"{sh}%는 {names}, 자기 주식입니다."])))
        if not _said_buyback(d):
            pairs.append(("meaning", pk(["회사가 자기 주식을 사면 기타법인으로 잡힙니다. 두 회사 모두 자사주를 사는 중입니다.",
                                         "기타법인이란 회사가 자기 주식을 사는 돈이 잡히는 칸입니다. 지금 자사주 매입이 진행 중입니다.",
                                         "이름은 기타법인이지만, 회사가 자기 주식을 사면 이 칸에 잡힙니다. 자사주입니다."])))
        else:
            pairs.append(("meaning", pk(["이 돈은 밖에서 새로 들어온 돈이 아닙니다.", "기타법인, 곧 자사주입니다.",
                                         "이름은 기타법인이지만 속은 자사주입니다.", "새 돈이 아니라 회사가 자기 주식을 산 돈입니다.",
                                         "이 막대의 정체는 자사주입니다.", "바깥 돈이 아니라 회사 예산입니다."])))
        days = cont.get("others_buy_days") or 0
    elif reveal_name:
        R = hwon(reveal_v)
        if reveal_kind == "same":
            pairs.append(("reveal", pk([f"{reveal_name}도 {P}처럼 {obj(R)} {'팔았' if reveal_v < 0 else '샀'}습니다.",
                                        f"{reveal_name} {'순매도' if reveal_v < 0 else '순매수'} {R}입니다.",
                                        f"{reveal_name}이 {obj(R)} {'팔았' if reveal_v < 0 else '샀'}습니다.",
                                        f"{R}, {reveal_name}이 {'판' if reveal_v < 0 else '산'} 돈입니다."])))
            pairs.append(("meaning", pk([f"{naive_name} 하나로 설명이 안 되는 날입니다.", "한쪽 손만 움직인 날이 아닙니다.",
                                         f"{naive_name}만 보면 절반만 본 겁니다.", "막대는 셋인데 방향은 둘입니다.", "받은 쪽과 판 쪽이 둘 다 둘입니다."])))
        else:
            is_top = bool(x["opp"]) and x["opp"][0][0] == reveal_name
            if is_top and cont.get("top_buyer_days", 1) >= 2 and sold:
                days = cont["top_buyer_days"]
                pairs.append(("reveal", pk([f"오늘도 마찬가지로 {reveal_name}이 가장 많이 샀습니다. {dko(days)}입니다.",
                                            f"가장 많이 산 쪽은 오늘도 {reveal_name}, {dko(days)}입니다.",
                                            f"{reveal_name}이 1위인 건 {dko(days)} 같습니다."])))
                pairs.append(("reveal_v", pk([f"오늘 몫은 {R}입니다.", f"{R}, 오늘 숫자입니다.", f"오늘은 {obj(R)} 샀습니다."])))
            else:
                pairs.append(("reveal", pk([f"{reveal_name} {R}.", f"{reveal_name}이 {obj(R)} {v_got}습니다.", f"{R}, {reveal_name}입니다.",
                                            f"{reveal_name} {'순매수' if reveal_v > 0 else '순매도'} {R}입니다."])))
            pairs.append(("meaning", pk([f"{naive_name} 하나로 설명이 안 되는 날입니다.", "받은 손이 하나가 아니었다는 뜻입니다.",
                                         f"{naive_name}만 보면 절반만 본 겁니다.", "막대 셋이 아니라 넷을 봐야 하는 날입니다.", "답은 둘로 갈립니다."])))
    else:
        pairs.append(("meaning", pk([f"{naive_name} 하나뿐인 날입니다.", "받은 손은 하나였습니다.", "다른 막대는 작았습니다."])))

    tts, steps = _steps(pairs)
    bars = [{"name": n, "v": v} for n, v in [(P, x["amount"])] + [(n, v) for n, v in vals.items() if n != P and n != "기타법인"]]
    s2 = {"naive": naive_txt, "naive_name": naive_name, "naive_v": naive_v, "kind": kind, "bars": bars,
          "said_share": any(n in ("top", "reveal") and "%" in s for n, s in pairs),
          "reveal": {"name": reveal_name, "v": reveal_v, "days": days, "top": top, "kind": reveal_kind}, "tts": tts, "steps": steps}
    return tts, s2, kind


def _said_buyback(d: str) -> bool:
    """자사주 설명을 최근 3편에 했으면 True — script_memory.said_within, 없으면 narrate_aplus._said_recently."""
    try:
        return bool(sm.said_within(d, "자사주"))
    except Exception:
        try:
            return bool(na._said_recently(d, "자사주"))
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════════════════
# S3a 어제의 돈 — 어제 보자고 한 숫자의 답(콜백) + 해석 + '그런데 달라진 것' + 다음 질문. 화면 지시어 1개(카드·도장).
# 대체: 콜백이 없으면 주인공 연속일 사실로, 그것도 없으면 어제 금액과 오늘 금액 비교로. 월요일은 주말편이 짚은 숫자를 사실로 덧붙인다.
# 자기 채널 영상 언급 없음('지난 영상에서' 금지) — 숫자와 약속만 말한다.
# ══════════════════════════════════════════════════════════════════════════════
def _s3a(x: dict, cont: dict, c: dict, pk: Picker) -> tuple[str, dict, list]:
    d, P, sold, amt = x["d"], x["P"], x["sold"], x["amount"]
    cb = x["cb"]
    pairs: list[tuple[str, str]] = []
    promise, result, ok, num = "", "", None, None
    wk_rows: list = []
    head = ""
    if cb and isinstance(cb.get("check"), dict) and cb.get("ok") is not None:
        chk, ok, t = cb["check"], bool(cb["ok"]), cb.get("t")
        num = t
        qn = na._q_noun(cb) or "어제 숫자"
        n = chk.get("n")
        when = _day_word(d, cb.get("prev_date"), past=True)
        head = f"{when} 보자고 한 것"
        promise = cb.get("q") or qn
        kind = chk.get("kind")
        if kind == "inv_continue":
            word = "순매수" if (chk.get("sign") or -1) > 0 else "순매도"
            res_w = f"{dko(n)} 이어졌습니다" if (ok and n) else ("오늘도 이어졌습니다" if ok else "오늘 끊겼습니다")
            result = "이어짐" if ok else "끊김"
            T = hwon(abs(t)) if isinstance(t, (int, float)) else ""
            today = (f" 오늘 {T}." if ok else f" 오늘은 오히려 {T} {'순매수' if word == '순매도' else '순매도'}.") if T else ""
            pairs.append(("promise", pk([f"{when} 보자고 한 {qn}, 카드 위 도장을 보세요. {res_w}.{today}",
                                         f"{when} 짚어 둔 {qn}입니다. 왼쪽 카드의 도장은 {result}.{today}",
                                         f"{qn}가 {dko(n) if n else '오늘도'} 이어지는지. {when} 남긴 질문의 도장은 {result}입니다.{today}",
                                         f"먼저 {when} 숙제입니다. {qn}는 {res_w}, 카드를 보세요.{today}",
                                         f"{qn}, {when} 보자고 한 숫자입니다. {qn} 카드의 도장을 보세요, {result}입니다.{today}"])))
            if ok and n and n >= 3:
                pairs.append(("meaning", pk([f"{dko(n)}면 어느 하루의 사정이 아니라는 뜻입니다.", f"{dko(n)}까지 왔으면 우연으로 부르기 어렵습니다.",
                                             f"{dko(n)} 같은 손이 {'팔았' if word == '순매도' else '샀'}다는 뜻입니다.", f"하루짜리가 아니라 {dko(n)} 쌓인 방향이라는 뜻입니다."])))
            elif ok:
                pairs.append(("meaning", pk(["이틀은 아직 이릅니다. 사흘째부터 방향으로 봅니다.", "이틀로는 하루 사정인지 방향인지 못 가릅니다.",
                                             "아직은 이틀, 방향이라 부르기엔 이릅니다."])))
            else:
                pairs.append(("meaning", pk(["하루 사정이었을 수 있다는 뜻입니다.", "며칠째가 끊기면 방향도 다시 셉니다.",
                                             "이어지던 손이 멈췄다는 뜻입니다."])))
        elif kind in ("theme_continue", "theme_sell_stop", "theme_sell_cont"):
            th = chk.get("theme") or ""
            result = "이어짐" if ok else "끊김"
            T = hwon(abs(t)) if isinstance(t, (int, float)) else ""
            went = "들어왔" if (isinstance(t, (int, float)) and t > 0) else "빠졌"
            pairs.append(("promise", pk([f"{when} 보자고 한 {qn}, 카드 위 도장을 보세요. {result}입니다.",
                                         f"{when} 짚어 둔 {qn}입니다. 왼쪽 카드의 도장, {result}입니다.",
                                         f"먼저 {when} 숙제입니다. {qn}는 {result}, 카드를 보세요.",
                                         f"{qn}, {when} 보자고 한 숫자입니다. {qn} 카드의 도장을 보세요, {result}입니다."])))
            if T:
                pairs.append(("num", pk([f"오늘 {th}엔 {subj(T)} {went}습니다.", f"{th} 오늘 숫자는 {T}, {went}습니다.", f"{T}이 {th}에서 {went}습니다."])))
            pairs.append(("meaning", pk(["첫날 들어온 돈이 다음 날도 머물렀는지가 이 도장입니다." if ok else "첫날 돈이 하루짜리였다는 뜻입니다.",
                                         "돈이 자리를 잡는지 보는 도장입니다.", "한 업종에 돈이 머무는지, 그걸 세는 칸입니다."])))
        else:  # kosdaq_break 등
            result = "끊김" if ok else "이어짐"
            pairs.append(("promise", pk([f"{when} 보자고 한 {promise}, 카드 위 도장을 보세요. {result}입니다.",
                                         f"{when} 짚어 둔 {promise}입니다. 왼쪽 카드의 도장, {result}입니다.",
                                         f"먼저 {when} 숙제, {promise}입니다. 도장은 {result}, 카드를 보세요."])))
            pairs.append(("meaning", pk(["도장 하나가 하루를 정리합니다.", "약속한 숫자는 이렇게 매일 도장으로 남깁니다.", "맞고 틀림을 카드에 그대로 둡니다."])))
    else:
        # 대체 1: 주인공 연속일 사실 / 대체 2: 어제 금액 대비
        st = x["st_p"]
        A = hwon(amt)
        head = "며칠째 같은 손" if st >= 2 else "오늘의 손"
        if st >= 2:
            promise = f"{P} {'순매도' if sold else '순매수'} {dko(st)}"
            result, ok, num = "이어짐", True, amt
            pairs.append(("promise", pk([f"{josa(P)} {dko(st)} {'팔고' if sold else '사고'} 있습니다. 왼쪽 카드를 보세요.",
                                         f"카드를 보세요. {P} {'순매도' if sold else '순매수'} {dko(st)}입니다.",
                                         f"{dko(st)}입니다, {subj(P)} {'파는' if sold else '사는'} 날이. 왼쪽 카드의 도장입니다."])))
            pairs.append(("num", pk([f"오늘 {A}.", f"오늘 숫자는 {A}입니다.", f"{A}, 오늘 몫입니다."])))
            pairs.append(("meaning", pk([f"{dko(st)}면 어느 하루의 사정이 아니라는 뜻입니다." if st >= 3 else "이틀은 아직 이릅니다. 사흘째부터 방향으로 봅니다.",
                                         f"{dko(st)}까지 왔으면 우연으로 부르기 어렵습니다." if st >= 3 else "이틀로는 하루 사정인지 방향인지 못 가릅니다.",
                                         f"하루짜리가 아니라 {dko(st)} 쌓인 방향이라는 뜻입니다." if st >= 3 else "아직은 이틀, 방향이라 부르기엔 이릅니다."])))
        else:
            promise = f"{P} 오늘 {A}"
            result, ok, num = "오늘", None, amt
            yv = x["y_P"]
            pairs.append(("promise", pk([f"{josa(P)} 오늘 {obj(A)} {'팔았' if sold else '샀'}습니다. 왼쪽 카드를 보세요.",
                                         f"카드를 보세요. {P} {'순매도' if sold else '순매수'} {A}입니다.",
                                         f"{A}, 오늘 {subj(P)} {'판' if sold else '산'} 돈입니다. 왼쪽 카드입니다."])))
            if isinstance(yv, (int, float)) and abs(yv) >= 100:
                pairs.append(("num", pk([f"어제는 {hwon(yv)}을 {'팔았' if yv < 0 else '샀'}습니다.", f"어제 숫자는 {hwon(yv)}였습니다.",
                                         f"전날엔 {hwon(yv)}, {'순매도' if yv < 0 else '순매수'}였습니다."])))
            pairs.append(("meaning", pk(["오늘이 첫날입니다. 며칠째가 되는지부터 셉니다.", "하루치 숫자는 아직 방향이 아닙니다.", "첫날은 크기만 있고 방향은 없습니다."])))
    # 월요일: 주말편이 짚어 둔 숫자를 사실로(이름 없이) 덧붙인다
    try:
        import weekend_watch
        _also, _said, wk_rows = weekend_watch.block(d, c, done_q=promise)
        for r in wk_rows:
            if r.get("a") and not r.get("merged"):
                a = _fix_won(r["a"])
                pairs.append(("weekend", pk([f"주말에 짚어 둔 {weekend_watch.obj_q(r['q'])}도 봅니다. {a}",
                                             f"주말 숙제 하나 더, {r['q']}. {a}",
                                             f"{a} 주말에 보자고 한 {r['q']}의 답입니다."])))
                break
    except Exception:
        wk_rows = []
    # ── 그런데: 달라진 것(받은 쪽 / 크기 / 며칠째≠크기) ──
    changed = None
    y_top = x["y_buyers"][0][0] if x["y_buyers"] else None
    t_top = x["buyers"][0][0] if x["buyers"] else None
    yv = x["y_P"]
    wy = _day_word(d, x["prev_date"], past=True)
    if sold and y_top and t_top and y_top != t_top:
        changed = {"label": "받은 쪽", "before": f"{y_top} {hshort(x['y_buyers'][0][1])}", "after": f"{t_top} {hshort(x['buyers'][0][1])}", "before_label": wy}
        pairs.append(("turn", pk(["그런데 받은 쪽이 바뀌었습니다.", "그런데 받아 낸 손이 어제와 다릅니다.", "그런데 물량을 받은 자리가 옮겨졌습니다.",
                                  "그런데 받은 쪽 이름이 바뀌었습니다.", "그런데 오른쪽 막대의 주인이 바뀌었습니다."])))
        YV, TV = hwon(x['y_buyers'][0][1]), hwon(x['buyers'][0][1])
        pairs.append(("turn_b", pk([f"{wy}는 {y_top} {YV}, 오늘은 {t_top} {TV}입니다.", f"{wy} 1위 {y_top} {YV}에서 오늘 {t_top} {ro(TV)} 넘어갔습니다.",
                                    f"{y_top} {YV}에서 {t_top} {ro(TV)}, 손이 바뀌었습니다."])))
    elif isinstance(yv, (int, float)) and abs(yv) >= 1000 and (yv < 0) == sold and abs(amt) <= 0.6 * abs(yv):
        changed = {"label": "크기", "before": f"{P} {hshort(yv)}", "after": f"{P} {hshort(amt)}", "before_label": wy}
        pairs.append(("turn", pk([f"그런데 크기는 {wy}의 절반 언저리입니다.", "그런데 크기는 줄었습니다.", "그런데 물량은 작아졌습니다.",
                                  "그런데 같은 손, 다른 크기입니다.", "그런데 며칠째는 같아도 크기는 다릅니다."])))
        pairs.append(("turn_b", pk([f"{wy} {hwon(yv)}, 오늘 {hwon(amt)}입니다.", f"{wy}는 {hwon(yv)}, 오늘은 {hwon(amt)}입니다.",
                                    f"{hwon(yv)}에서 {ro(hwon(amt))} 줄었습니다."])))
    elif isinstance(yv, (int, float)) and abs(yv) >= 1000 and (yv < 0) == sold and abs(amt) >= 1.5 * abs(yv):
        changed = {"label": "크기", "before": f"{P} {hshort(yv)}", "after": f"{P} {hshort(amt)}", "before_label": wy}
        pairs.append(("turn", pk(["그런데 크기는 커졌습니다.", f"그런데 물량은 {wy}보다 불었습니다.", "그런데 같은 손인데 크기가 다릅니다.",
                                  "그런데 며칠째보다 크기가 먼저 눈에 들어옵니다.", "그런데 숫자는 더 커졌습니다."])))
        pairs.append(("turn_b", pk([f"{wy} {hwon(yv)}, 오늘 {hwon(amt)}입니다.", f"{wy}는 {hwon(yv)}, 오늘은 {hwon(amt)}입니다.",
                                    f"{hwon(yv)}에서 {ro(hwon(amt))} 불었습니다."])))
    else:
        changed = {"label": "며칠째와 크기", "before": f"{P} {hshort(yv) if isinstance(yv, (int, float)) else '—'}", "after": f"{P} {hshort(amt)}", "before_label": wy}
        pairs.append(("turn", pk(["그런데 며칠째와 크기는 다른 숫자입니다.", "그런데 이어졌다는 것과 얼마나 팔았느냐는 다른 칸입니다." if sold
                                  else "그런데 이어졌다는 것과 얼마나 샀느냐는 다른 칸입니다.",
                                  "그런데 도장 하나로 크기까지 알 수는 없습니다.", "그런데 방향과 크기는 따로 셉니다.", "그런데 도장은 방향만 말합니다. 크기는 다음 칸입니다."])))
    # ── 다음 질문(S3b 로) ──
    pairs.append(("q", pk(["그럼 이 돈은 어디로 갔을까요?", "그럼 빠진 돈이 간 곳은 어디일까요?", "그럼 받은 돈은 어디에 쌓였을까요?",
                           "그럼 돈이 옮겨 간 자리는 어디일까요?", "그럼 나간 돈은 어디로 흘렀을까요?", "그럼 코스피 밖은 어땠을까요?"]) if sold else
                  pk(["그럼 그 돈은 어디로 들어갔을까요?", "그럼 들어온 돈이 머문 곳은 어디일까요?", "그럼 돈이 쌓인 자리는 어디일까요?",
                      "그럼 코스피 밖은 어땠을까요?", "그럼 이 돈은 어느 업종으로 갔을까요?"])))
    tts, steps = _steps(pairs)
    return tts, {"promise": promise, "result": result, "ok": ok, "num": num, "changed": changed, "head": head, "tts": tts, "steps": steps}, wk_rows


# ══════════════════════════════════════════════════════════════════════════════
# S3b 돈이 간 곳 — 이동 선언 1회 + 가장 큰 유입 업종(숫자) + 해석 + '그런데'(코스닥 표 / 유출 대비) + 다음 질문. 화면 지시어 1개(오른쪽 표).
# 대체: 업종 자료가 없으면 받은 주체(개인·기타법인)를 '돈이 간 곳'으로, 코스닥 수급이 없으면 유출 대비 비율로 반전한다.
# ══════════════════════════════════════════════════════════════════════════════
# S3b 끝 질문 — 다음 블록(S3c)의 종류에 맞춘다. 질문의 답이 다음 블록에 있어야 사슬이 이어진다(장치 #4).
_S3B_Q = {
    "C1": ["그럼 값은 돈을 따라갔을까요?", "그럼 돈이 멈춘 자리는 어디일까요?", "그럼 값과 돈이 따로 논 자리는 어디일까요?", "그럼 가격은 어땠을까요?"],
    "C1s": ["그럼 값은 그만큼 빠졌을까요?", "그럼 돈이 나간 자리의 주가는 어땠을까요?", "그럼 판 쪽 종목은 얼마나 내렸을까요?"],
    "C2": ["그럼 오늘 오른 종목엔 큰돈이 들어갔을까요?", "그럼 값이 뛴 자리엔 누구 돈이 있었을까요?", "그럼 오른 쪽은 돈이 따라갔을까요?",
           "그럼 값만 오른 자리는 없었을까요?", "그럼 오늘 이슈 종목은 돈이 받쳤을까요?"],
    "C3": ["그럼 자사주가 받은 종목의 값은 어땠을까요?", "그럼 받은 자리의 값은 버텼을까요?", "그럼 값은 돈을 따라갔을까요?",
           "그럼 회사 돈이 들어간 종목은 올랐을까요?", "그럼 받쳤는데도 내린 자리는 없었을까요?"],
    "C4": ["그럼 코스닥 쪽 값은 어땠을까요?", "그럼 값과 돈은 같은 방향이었을까요?", "그럼 받은 자리의 값은 어땠을까요?",
           "그럼 개인이 받은 자리는 올랐을까요?", "그럼 돈과 값이 갈린 자리는 어디일까요?"],
}


def _s3b(x: dict, pk: Picker, c_kind: str | None = None) -> tuple[str, dict]:
    """c_kind 는 S3c 가 고른 종류(C1~C4) — 끝 질문을 거기에 맞춘다. 없으면 C1 풀."""
    P, sold = x["P"], x["sold"]
    cb = x["cb"] if isinstance(x["cb"], dict) else {}
    chk = cb.get("check") if isinstance(cb.get("check"), dict) else {}
    cb_theme = chk.get("theme") if str(chk.get("kind") or "").startswith("theme") else None
    pairs: list[tuple[str, str]] = []
    pairs.append(("move", pk(["파는 쪽에서 받는 쪽으로 가 봅니다.", "이번엔 돈이 간 곳입니다.", "나간 돈 말고 들어온 돈을 봅니다.",
                              "받은 쪽 표로 넘어갑니다.", "돈이 도착한 자리로 가 봅니다.", "시계를 업종 표로 옮깁니다."])))
    rows = sorted([{"name": th, "v": round(v)} for th, v in x["flows"].items()], key=lambda r: -abs(r["v"]))[:3]
    in_th, in_t, out_th, out_t = x["in_th"], x["in_t"], x["out_th"], x["out_t"]
    used_ratio = False
    if in_th and in_t:
        I = hwon(in_t)
        if cb_theme and cb_theme == in_th:      # S3a 가 방금 그 업종의 도장을 찍었다 — 처음 말하듯 하지 않는다
            pairs.append(("num", pk([f"들어온 돈 1위도 역시 {in_th}, {I}입니다.", f"받은 쪽 표에서도 1위는 그 {in_th}입니다. {I}.",
                                     f"{subj(in_th)} 오늘 들어온 돈의 1위이기도 합니다, {I}.", f"방금 도장 찍은 {in_th}, 유입 표에서도 1위입니다. {I}."])))
        else:
            pairs.append(("num", pk([f"가장 큰 돈이 들어간 곳은 {in_th}, {I}입니다.", f"{in_th}에 {subj(I)} 들어왔습니다.",
                                     f"들어온 돈 1위는 {in_th}입니다. {I}.", f"{I}. 오늘 {ro(in_th)} 들어온 외국인·기관 돈입니다.",
                                     f"{subj(in_th)} 받았습니다. {I}."])))
        im = x["in_m"] or {}
        stk = im.get("streak") or 0
        names = [n for n in (im.get("spread_names") or [])[:3] if n]
        if str(im.get("state") or "").startswith("쌓임") and stk >= 2:
            pairs.append(("interp", pk([f"{dko(stk)} 쌓이는 돈입니다.", f"하루짜리가 아니라 {dko(stk)} 이어진 유입입니다.", f"{dko(stk)} 같은 자리에 돈이 들어오고 있습니다."])))
        elif names:
            pairs.append(("interp", pk([f"{_and(names)}에 몰렸습니다.", f"돈은 {_and(names)}로 갔습니다.", f"종목으로는 {_and(names)}입니다."])))
        elif out_th and out_t and abs(out_t) >= 3 * in_t:
            kk = round(abs(out_t) / in_t)
            used_ratio = True
            pairs.append(("interp", pk([f"{out_th}에서 빠진 돈의 {kk}분의 1입니다.", f"빠진 돈에 비하면 {kk}분의 1입니다.", f"{out_th} 유출과 견주면 {kk}분의 1 크기입니다."])))
        else:
            pairs.append(("interp", pk(["오늘 새로 들어온 돈의 자리입니다.", "받은 돈이 고인 곳입니다.", "돈이 도착한 첫 자리입니다."])))
    elif [b for b in x["buyers"] if b[0] != P] or x["sellers"]:
        side = [b for b in x["buyers"] if b[0] != P] or [s for s in x["sellers"] if s[0] != P]
        n0, v0 = side[0]
        rows = [{"name": n, "v": round(v)} for n, v in side[:3]]
        if v0 > 0:
            pairs.append(("num", pk([f"받은 돈 1위는 {n0}, {hwon(v0)}입니다.", f"{n0}이 {obj(hwon(v0))} 받았습니다.", f"{hwon(v0)}, {n0}에 쌓인 돈입니다."])))
        else:
            pairs.append(("num", pk([f"내놓은 쪽 1위는 {n0}, {hwon(v0)}입니다.", f"{n0}이 {obj(hwon(v0))} 내놓았습니다.", f"{hwon(v0)}, {n0}이 판 돈입니다."])))
        pairs.append(("interp", pk(["업종 표는 오늘 비어 있어 주체 표로 봅니다.", "오늘은 업종 대신 주체별로 봅니다.", "돈이 간 자리를 주체로 나눈 표입니다."])))
    else:
        pairs.append(("num", pk(["들어온 돈의 표는 오늘 비어 있습니다.", "오늘은 받은 쪽 표가 없습니다.", "유입 표는 집계 대기입니다."])))
        pairs.append(("interp", pk(["숫자가 오면 다시 채웁니다.", "이 칸은 다음 편에 다시 봅니다.", "확정치가 오면 같은 자리에 넣습니다."])))
    # 그런데: 코스닥 표
    kq = x["kq"]
    table = None
    fq, iq, dq = kq.get("foreign"), kq.get("inst"), kq.get("indiv")
    if isinstance(fq, (int, float)) and isinstance(x["vals"].get("외국인"), (int, float)) and abs(fq) >= 100:
        table = {"title": "코스닥", "rows": [{"name": n, "v": round(v)} for n, v in (("외국인", fq), ("기관", iq or 0), ("개인", dq or 0))]}
        fk = x["vals"]["외국인"]
        if (fq > 0) != (fk > 0):
            FQ, wq, vq = hwon(fq), ("순매수" if fq > 0 else "순매도"), ("샀" if fq > 0 else "팔았")
            pairs.append(("turn", pk([f"그런데 코스닥은 반대였습니다, 오른쪽 표의 외국인 {FQ} {wq}.",
                                      f"그런데 오른쪽 표, 코스닥에선 외국인이 {obj(FQ)} {vq}습니다.",
                                      f"그런데 코스닥 표는 방향이 다릅니다, 오른쪽 외국인 {FQ} {wq}.",
                                      f"그런데 오른쪽 표를 보세요, 코스닥 외국인은 {FQ} {wq}로 반대입니다."])))
        else:
            FQ, wq, vq = hwon(fq), ("순매도" if fq < 0 else "순매수"), ("팔았" if fq < 0 else "샀")
            pairs.append(("turn", pk([f"그런데 오른쪽 표의 코스닥도 같은 그림입니다, 외국인 {FQ} {wq}.",
                                      f"그런데 코스닥에서도 외국인은 {obj(FQ)} {vq}습니다, 오른쪽 표를 보세요.",
                                      f"그런데 오른쪽 표를 보세요, 코스닥 외국인 {FQ}도 같은 방향입니다.",
                                      f"그런데 코스닥 표의 외국인 칸도 {FQ} {wq}입니다, 오른쪽입니다."])))
    elif out_th and out_t and in_t and not used_ratio and abs(out_t) >= 3 * in_t:
        kk = round(abs(out_t) / in_t)
        pairs.append(("turn", pk([f"그런데 위 칸과 아래 칸을 견줘 보세요. {out_th}에서 빠진 돈의 {kk}분의 1입니다.",
                                  f"그런데 오른쪽 표의 {out_th} 칸을 보세요. 들어온 돈은 그 {kk}분의 1입니다.",
                                  f"그런데 {out_th} 유출 막대 옆에 세우면 {kk}분의 1 크기입니다. 보세요."])))
    else:
        pairs.append(("turn", pk(["그런데 오른쪽 표를 보세요. 큰 막대는 여전히 나가는 쪽에 있습니다.", "그런데 표의 오른쪽, 나가는 막대가 더 깁니다.",
                                  "그런데 오른쪽 표에서 들어온 칸은 작습니다. 보세요."])))
    qk = c_kind if c_kind in _S3B_Q else "C1"
    q_pool = list(_S3B_Q[qk]) + (list(_S3B_Q["C1s"]) if (qk == "C1" and sold) else [])
    pairs.append(("q", pk(q_pool)))
    tts, steps = _steps(pairs)
    said_ratio = any("분의 1" in s for _, s in pairs)
    return tts, {"title": "돈이 간 곳", "rows": rows, "table": table, "said_ratio": said_ratio, "tts": tts, "steps": steps}


# ══════════════════════════════════════════════════════════════════════════════
# S3c 돈이 정체한 곳 — C1 값은 그대로인데 돈이 나가는 종목 / C2 오르는데 큰돈이 안 들어온 이슈 / C3 자사주가 받았는데 값이 빠진 종목 / C4 코스닥·개인.
# 끝은 S4 로 넘기는 질문. 화면 지시어 1개(위 칸·아래 칸). 대체: C1→C2→C3→C4 순서로 데이터가 있는 첫 것(최근 3편 것은 뒤로).
# ══════════════════════════════════════════════════════════════════════════════
def _s3c_pick(x: dict) -> tuple[str, list, list]:
    """S3c 종류(C1~C4)와 후보 자료. build 는 이걸 먼저 불러 S3b 의 끝 질문을 맞춘다."""
    sold, d = x["sold"], x["d"]
    sflows = x["sflows"]
    # C1 후보: 값 |등락| < 1% 인데 외국인+기관이 3천억 이상 뺀(주인공이 판 날) / 넣은 종목
    c1 = []
    for code, r in sflows.items():
        if not isinstance(r, dict) or not r.get("name") or not isinstance(r.get("pct"), (int, float)):
            continue
        fi = (r.get("foreign") or 0) + (r.get("inst") or 0)
        if abs(r["pct"]) < 1.0 and ((fi <= -3000) if sold else (fi >= 3000)):
            c1.append({"code": code, "name": r["name"], "pct": r["pct"], "fi": fi, "indiv": r.get("indiv") or 0})
    c1 = sorted(c1, key=lambda r: abs(r["fi"]), reverse=True)[:2]
    # C2 후보: 이슈 종목 평균 +2% 이상인데 외국인+기관 유입 1천억 이하
    ev, avg = x["ev"], x["ev_avg"]
    c2 = bool(x["ev_st"]) and isinstance(avg, (int, float)) and avg >= 2.0 and x["ev_flow"] <= 1000
    # C3 후보: 기타법인이 산 상위 종목인데 값은 1% 넘게 빠짐
    c3 = []
    for t in x["top_others"]:
        r = sflows.get(t.get("code") or "") or {}
        if isinstance(r.get("pct"), (int, float)) and r["pct"] <= -1.0:
            c3.append({"name": t["name"], "v": t["v"], "pct": r["pct"]})
    kinds = ([k for k, okk in (("C1", bool(c1)), ("C2", c2), ("C3", bool(c3))) if okk]) + ["C4"]
    recent = _recent_ids(d, "devices")
    pool = [k for k in kinds if k not in recent] or kinds
    return pool[0], c1, c3


def _s3c(x: dict, pk: Picker, picked: tuple[str, list, list] | None = None) -> tuple[str, dict, str, bool]:
    P, sold, d = x["P"], x["sold"], x["d"]
    sflows = x["sflows"]
    ev_used = False
    ev, avg = x["ev"], x["ev_avg"]
    kind, c1, c3 = picked or _s3c_pick(x)
    pairs: list[tuple[str, str]] = []
    stocks, bars = [], []
    if kind == "C1":
        stocks = [{"name": r["name"], "pct": r["pct"]} for r in c1]
        fi_sum = sum(r["fi"] for r in c1)
        ind_sum = sum(r["indiv"] for r in c1)
        oth_sum = sum(t["v"] for t in x["top_others"] if t["name"] in {r["name"] for r in c1})
        bars = [{"name": "외국인+기관", "v": round(fi_sum)}] + ([{"name": "자사주", "v": round(oth_sum)}] if oth_sum else []) + [{"name": "개인", "v": round(ind_sum)}]
        if len(c1) == 2:
            a, b = c1
            pairs.append(("num", pk([f"{a['name']} {pct_s(a['pct'])}, {b['name']} {pct_s(b['pct'])}. 값은 거의 그대로입니다.",
                                     f"위 칸을 보세요. {josa(a['name'])} {pct_s(a['pct'])}, {josa(b['name'])} {pct_s(b['pct'])} 움직였습니다.",
                                     f"{_and([a['name'], b['name']])}의 등락은 {pct_s(a['pct'])}, {pct_s(b['pct'])}였습니다. 위 칸입니다."])))
            who = f"이 두 종목"
        else:
            a = c1[0]
            pairs.append(("num", pk([f"{a['name']} {pct_s(a['pct'])}. 값은 거의 그대로입니다.", f"위 칸을 보세요. {josa(a['name'])} {pct_s(a['pct'])} 움직였습니다.",
                                     f"{a['name']} 등락은 {pct_s(a['pct'])}였습니다. 위 칸입니다."])))
            who = a["name"]
        F = hwon(fi_sum)
        pairs.append(("turn", pk([f"그런데 아래 칸, 외국인과 기관이 {who}에서 {'뺀' if sold else '넣은'} 돈은 {F}입니다.",
                                  f"그런데 아래 칸을 보세요. 외국인·기관 {'순매도' if sold else '순매수'} {F}.",
                                  f"그런데 {who}에서 {'나간' if sold else '들어온'} 외국인·기관 돈은 {F}입니다. 아래 칸입니다."])))
        if oth_sum:
            pairs.append(("meaning", pk([f"값이 버틴 자리에 자사주 {hwon(oth_sum)}이 있었습니다.", f"그 자리를 받친 건 자사주 {hwon(oth_sum)}입니다.",
                                         f"자사주 {hwon(oth_sum)}이 그 물량을 받아 냈습니다."])))
        else:
            pairs.append(("meaning", pk([f"개인 {hwon(ind_sum)}이 그 물량을 받아 냈습니다." if ind_sum > 0 else "값이 안 움직인 건 받은 손이 있었다는 뜻입니다.",
                                         "돈은 나갔는데 값은 서 있는 자리입니다.", "값과 돈이 따로 노는 칸입니다."])))
    elif kind == "C2":
        ev_used = True
        grp = ev.get("group") or ev.get("label") or "관련주"
        n_ev = len(x["ev_st"])
        stocks = [{"name": s.get("name"), "pct": s.get("pct")} for s in sorted(x["ev_st"], key=lambda s: -(s.get("pct") or 0))[:3]]
        f, ind = x["ev_flow"], x["ev_indiv"]
        bars = [{"name": "외국인+기관", "v": round(f)}, {"name": "개인", "v": round(ind)}]
        pairs.append(("num", pk([f"{grp} {n_ev}종목은 평균 {pct_s(avg)} 올랐습니다. 위 칸입니다.",
                                 f"위 칸을 보세요. {grp} {n_ev}종목 평균 {pct_s(avg)} 상승.",
                                 f"{pct_s(avg)}. {grp} {n_ev}종목의 평균 등락, 위 칸입니다."])))
        F = hwon(f) if abs(f) >= 100 else f"{abs(round(f))}억"
        if f >= 0:
            pairs.append(("turn", pk([f"그런데 아래 칸, 외국인과 기관이 거기 넣은 돈은 {F}입니다.", f"그런데 아래 칸을 보세요. 외국인·기관 유입 {F}.",
                                      f"그런데 큰손 돈은 {subj(F)} 전부입니다. 아래 칸입니다."])))
        else:
            pairs.append(("turn", pk([f"그런데 아래 칸, 외국인과 기관은 거기서 {obj(F)} 뺐습니다.", f"그런데 아래 칸을 보세요. 외국인·기관은 오히려 {F} 순매도.",
                                      f"그런데 큰손은 오히려 {obj(F)} 팔았습니다. 아래 칸입니다."])))
        if ind > 100:
            pairs.append(("meaning", pk(["값을 올린 건 개인 돈이었다는 뜻입니다.", f"받친 건 개인 {hwon(ind)}이었습니다.", "큰손 없이 오른 자리라는 뜻입니다."])))
        else:
            pairs.append(("meaning", pk(["큰돈은 어느 쪽도 안 들어온 자리라는 뜻입니다.", "값만 뛰고 돈은 안 온 칸입니다.", "오름은 있는데 큰손은 없다는 뜻입니다."])))
    elif kind == "C3":
        a = c3[0]
        stocks = [{"name": r["name"], "pct": r["pct"]} for r in c3[:2]]
        r0 = sflows.get(next((t.get("code") for t in x["top_others"] if t["name"] == a["name"]), "") or "") or {}
        fi = (r0.get("foreign") or 0) + (r0.get("inst") or 0)
        bars = [{"name": "자사주", "v": round(a["v"])}, {"name": "외국인+기관", "v": round(fi)}, {"name": "개인", "v": round(r0.get("indiv") or 0)}]
        pairs.append(("num", pk([f"{a['name']}에 기타법인 돈 {subj(hwon(a['v']))} 들어갔습니다.", f"아래 칸을 보세요. {a['name']} 기타법인 순매수 {hwon(a['v'])}.",
                                 f"{hwon(a['v'])}. 기타법인이 {a['name']} 한 종목에 넣은 돈입니다."])))
        pairs.append(("turn", pk([f"그런데 위 칸을 보세요. 주가는 {pct_s(a['pct'])} 내렸습니다.", f"그런데 값은 {pct_s(a['pct'])} 빠졌습니다. 위 칸입니다.",
                                  f"그런데 위 칸의 등락은 {pct_s(a['pct'])} 하락입니다."])))
        if fi < 0:
            pairs.append(("meaning", pk([f"외국인과 기관이 {obj(hwon(fi))} 뺐다는 뜻입니다.", f"받은 돈보다 나간 돈이 컸습니다. 외국인·기관 {hwon(fi)}.",
                                         f"자사주가 받아도 외국인·기관 {josa(hwon(fi))} 못 막았다는 뜻입니다."])))
        else:
            pairs.append(("meaning", pk(["받은 돈이 값을 지키진 못했다는 뜻입니다.", "돈이 들어가도 값이 밀린 자리입니다.", "받쳤는데도 내린 칸입니다."])))
    else:  # C4 코스닥·개인
        kqi, kq = x["kqi"], x["kq"]
        qc = kqi.get("chg_pct") if isinstance(kqi.get("chg_pct"), (int, float)) else None
        dq = kq.get("indiv") if isinstance(kq.get("indiv"), (int, float)) else None
        ind = x["vals"].get("개인")
        if qc is not None and dq is not None and abs(dq) >= 100:
            stocks = [{"name": "코스닥", "pct": qc}]
            bars = [{"name": "개인", "v": round(dq)}, {"name": "외국인", "v": round(kq.get("foreign") or 0)}, {"name": "기관", "v": round(kq.get("inst") or 0)}]
            pairs.append(("num", pk([f"코스닥은 {pct_s(qc)} {'내렸' if qc < 0 else '올랐'}습니다. 위 칸입니다.", f"위 칸을 보세요. 코스닥 {pct_s(qc)} {'하락' if qc < 0 else '상승'}.",
                                     f"{pct_s(qc)}, 코스닥의 오늘 등락입니다. 위 칸입니다."])))
            pairs.append(("turn", pk([f"그런데 아래 칸, 개인이 거기서 {obj(hwon(dq))} {'받았' if dq > 0 else '팔았'}습니다.",
                                      f"그런데 아래 칸을 보세요. 코스닥 개인 {'순매수' if dq > 0 else '순매도'} {hwon(dq)}.",
                                      f"그런데 코스닥에서도 개인은 {obj(hwon(dq))} {'샀' if dq > 0 else '팔았'}습니다. 아래 칸입니다."])))
            pairs.append(("meaning", pk(["코스피와 같은 그림이라는 뜻입니다." if (dq > 0) == ((ind or 0) > 0) else "코스피와는 다른 그림이라는 뜻입니다.",
                                         "받은 손이 두 시장 모두 같다는 뜻입니다." if (dq > 0) == ((ind or 0) > 0) else "두 시장의 받은 손이 다르다는 뜻입니다.",
                                         "값과 돈이 따로 가는 칸입니다."])))
        else:
            A = hwon(ind or 0)
            stocks = [{"name": "코스피", "pct": x["chg"]}]
            bars = [{"name": "개인", "v": round(ind or 0)}]
            pairs.append(("num", pk([f"개인은 {obj(A)} {'받았' if (ind or 0) > 0 else '팔았'}습니다. 아래 칸입니다.", f"아래 칸을 보세요. 개인 {A}.",
                                     f"{A}, 개인의 오늘 몫입니다. 아래 칸입니다."])))
            pairs.append(("turn", pk([f"그런데 위 칸, 코스피는 {pct_s(x['chg'])} {'내렸' if x['chg'] < 0 else '올랐'}습니다.",
                                      f"그런데 위 칸을 보세요. 코스피 {pct_s(x['chg'])} {'하락' if x['chg'] < 0 else '상승'}.",
                                      f"그런데 값은 {pct_s(x['chg'])} {'빠졌' if x['chg'] < 0 else '올랐'}습니다. 위 칸입니다."])))
            pairs.append(("meaning", pk(["받아도 값은 밀린 자리라는 뜻입니다." if x["chg"] < 0 else "받은 손이 값을 밀어 올렸다는 뜻입니다.",
                                         "돈과 값이 따로 가는 칸입니다.", "받은 쪽과 값의 방향이 다른 날입니다." if x["chg"] < 0 else "받은 쪽과 값의 방향이 같은 날입니다."])))
    pairs.append(("q", pk(["그럼 나간 돈과 들어온 돈, 정확히 몇 배일까요?", "그럼 이 표를 직접 열어 볼까요?", "그럼 표에서 그 칸을 직접 짚어 볼까요?",
                           "그럼 원본 표엔 어떻게 적혀 있을까요?", "그럼 이 숫자, 표 어느 칸에서 나왔을까요?", "그럼 원문에서 한 칸만 골라 볼까요?"])))
    tts, steps = _steps(pairs)
    return tts, {"title": {"C1": "돈이 정체한 곳", "C2": "값만 오른 곳", "C3": "받았는데 빠진 곳", "C4": "돈과 값이 갈린 곳"}[kind],
                 "kind": kind, "stocks": stocks, "bars": bars, "tts": tts, "steps": steps}, kind, ev_used


# ══════════════════════════════════════════════════════════════════════════════
# S4 1차 자료 한 칸 — 원문(키움 전 종목 합산표 / 거래소 집계) + '여기 이 칸' + 계산 1개. 계산 K1~K6 은 코드가 검산한 값만 말한다.
#   K1 나간 돈 ÷ 들어온 돈(배) · K2 두 종목 ÷ 기타법인(%) · K3 자사주 예정 총액 ÷ 오늘 속도(거래일치) · K4 기타법인 ÷ 개인(배)
#   K5 한 업종 ÷ 외국인+기관 순매도 합(%) · K6 마감 ÷ 오후 2시(배). 훅이 이미 쓴 숫자 쌍(M2↔K6, M6↔K4)은 뺀다.
# 대체: 언제나 K2/K4/K5 중 하나는 성립한다(주체 합계만 있어도 됨). 그것마저 없으면 주인공 ÷ 받은 쪽 1위(배).
# ══════════════════════════════════════════════════════════════════════════════
def _parse_size(s: str) -> float | None:
    """'약 40조' → 400000억, '15조(장내)' → 150000억, '5,000억' → 5000억."""
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*조", s)
    if m:
        v = float(m.group(1)) * 10000
        m2 = re.search(r"조\s*(\d[\d,]*)\s*억", s)
        return v + (float(m2.group(1).replace(",", "")) if m2 else 0)
    m = re.search(r"(\d[\d,]*)\s*억", s)
    return float(m.group(1).replace(",", "")) if m else None


def _calc(kind: str, lhs: float, rhs: float) -> dict | None:
    """검산된 계산. ratio/fraction 은 정수 배, share 는 정수 %, days 는 정수 거래일치. 반올림이 3%·0.6 을 넘게 어긋나면 None."""
    if not rhs:
        return None
    a, b = abs(lhs), abs(rhs)
    if kind == "ratio":
        v = a / b
        if v < 1.5:
            return None
        n = int(v + 0.5)
        if abs(v - n) > max(0.3, 0.03 * v):
            return None
        return {"expr": f"{_won_screen(a)} ÷ {_won_screen(b)}", "result": f"{n}배", "lhs": round(lhs), "rhs": round(rhs), "value": round(v, 2), "kind": "ratio", "n": n}
    if kind == "fraction":
        v = a / b                     # a(작은 것) / b(큰 것) = 1/k
        if v <= 0 or v > 0.4:
            return None
        k = int(1 / v + 0.5)
        if abs(1 / v - k) > max(0.3, 0.03 / v):
            return None
        return {"expr": f"{_won_screen(a)} ÷ {_won_screen(b)}", "result": f"{k}분의 1", "lhs": round(lhs), "rhs": round(rhs), "value": round(v * 100, 2), "kind": "fraction", "n": k}
    if kind == "share":
        v = a / b * 100
        if v <= 0 or v > 100.5:
            return None
        n = round(v)
        if abs(v - n) > 0.6:
            return None
        return {"expr": f"{_won_screen(a)} ÷ {_won_screen(b)}", "result": f"{n}%", "lhs": round(lhs), "rhs": round(rhs), "value": round(v, 2), "kind": "share", "n": n}
    if kind == "days":
        v = a / b
        n = round(v)
        if n < 2 or abs(v - n) > max(0.6, 0.03 * v):
            return None
        return {"expr": f"{_won_screen(a)} ÷ {_won_screen(b)}", "result": f"{n}거래일치", "lhs": round(lhs), "rhs": round(rhs), "value": round(v, 2), "kind": "days", "n": n}
    return None


def _s4(x: dict, c: dict, hook_kind: str, pk: Picker, said_share: bool = False, said_ratio: bool = False) -> tuple[str, dict, str]:
    P, sold, d, oth = x["P"], x["sold"], x["d"], x["oth"]
    src = str(c.get("inv_src") or "")
    n_codes = c.get("n_codes")
    if "키움" in src or not src:
        doc = f"키움 {n_codes}종목 합산표 · 정규장 체결 기준 15:30" if n_codes else "키움 전 종목 합산표 · 정규장 체결 기준 15:30"
        doc_sp = f"키움 {n_codes}종목 합산표, 마감 기준" if n_codes else "키움 전 종목 합산표, 마감 기준"
    else:
        doc, doc_sp = "거래소 투자자별 매매 집계 · 마감 기준", "거래소 투자자별 매매 집계, 마감 기준"
    cands: dict[str, dict] = {}
    in_th, in_t, out_th, out_t = x["in_th"], x["in_t"], x["out_th"], x["out_t"]
    if out_th and out_t and in_th and in_t and out_t < 0 < in_t and not said_ratio:
        r = _calc("ratio", out_t, in_t)
        if r:
            cands["K1"] = {"calc": r, "l1": f"{out_th} 외국인·기관 순매도", "v1": out_t, "l2": f"{in_th} 순매수", "v2": in_t}
    top2 = x["top_others"]
    if oth > 0 and len(top2) >= 1 and not said_share:
        s = sum(t["v"] for t in top2)
        r = _calc("share", s, oth)
        if r:
            cands["K2"] = {"calc": r, "l1": f"기타법인 {_and([t['name'] for t in top2])}", "v1": s, "l2": "기타법인 순매수 합계", "v2": oth}
    bb = [(t, x["act"][t["code"]]) for t in top2 if t.get("code") in x["act"]]
    if bb and oth > 0:
        total = sum((_parse_size(p.get("size") or "") or 0) for _, p in bb)
        pace = sum(t["v"] for t, _ in bb)
        if total and pace:
            r = _calc("days", total, pace)
            if r:
                cands["K3"] = {"calc": r, "l1": f"{_and([t['name'] for t, _ in bb])} 자사주 예정 총액", "v1": total, "l2": "오늘 두 종목 기타법인 순매수" if len(bb) == 2 else "오늘 기타법인 순매수", "v2": pace}
    ind = x["vals"].get("개인")
    if isinstance(ind, (int, float)) and ind > 0 and oth > 0 and hook_kind != "M6":
        if oth >= ind:
            r = _calc("ratio", oth, ind)
            if r:
                cands["K4"] = {"calc": r, "l1": "기타법인 순매수", "v1": oth, "l2": "개인 순매수", "v2": ind}
        else:
            r = _calc("ratio", ind, oth)
            if r:
                cands["K4"] = {"calc": r, "l1": "개인 순매수", "v1": ind, "l2": "기타법인 순매수", "v2": oth}
    fi_neg = sum(min(x["vals"].get(n) or 0, 0) for n in ("외국인", "기관"))
    if out_th and out_t and out_t < 0 and fi_neg <= -1000:
        r = _calc("share", out_t, fi_neg)
        if r:
            cands["K5"] = {"calc": r, "l1": f"{out_th} 외국인·기관 순매도", "v1": out_t, "l2": "외국인·기관 순매도 합계", "v2": fi_neg}
    if x["snap_ok"] and hook_kind != "M2":
        r = _calc("ratio", x["amount"], x["snap"])
        if r:
            cands["K6"] = {"calc": r, "l1": f"{P} {'순매도' if sold else '순매수'} 마감치", "v1": x["amount"], "l2": f"{P} {'순매도' if sold else '순매수'} 오후 2시", "v2": x["snap"]}
    if not cands and x["opp"]:
        n0, v0 = x["opp"][0]
        r = _calc("ratio", x["amount"], v0) or _calc("share", v0, x["amount"])
        if r:
            cands["K7"] = {"calc": r, "l1": f"{P} {'순매도' if sold else '순매수'}", "v1": x["amount"], "l2": f"{n0} {'순매수' if sold else '순매도'}", "v2": v0}
    if not cands:   # 마지막 대체: 계산 없이 칸 하나만 짚는다(검사는 실패해도 대본은 나간다)
        cands["K0"] = {"calc": None, "l1": f"{P} {'순매도' if sold else '순매수'}", "v1": x["amount"], "l2": "", "v2": None}
    recent = _recent_ids(d, "devices")
    pool = [k for k in cands if k not in recent] or list(cands)
    kind = pool[int(d[-2:]) % len(pool)]
    spec = cands[kind]
    calc = spec["calc"]
    pairs: list[tuple[str, str]] = []
    pairs.append(("open", pk([f"직접 열어봤습니다. {doc_sp}.", f"{doc_sp}, 원본을 직접 열어봤습니다.", f"표를 직접 열어봤습니다. {doc_sp}입니다.",
                              f"원본을 직접 열어봤습니다. {doc_sp}.", f"{obj(doc_sp)} 열어보면 이렇게 나옵니다.", f"{doc_sp}, 원문을 직접 열어봤습니다."])))
    V1 = hwon(spec["v1"])
    pairs.append(("cell", pk([f"여기 이 칸, {spec['l1']} {V1}.", f"여기 이 칸을 보세요. {spec['l1']} {V1}.", f"칸 하나만 짚습니다. {spec['l1']} {V1}.",
                              f"{spec['l1']} 칸, {V1}.", f"테두리 친 칸, {spec['l1']} {V1}입니다.", f"여기 이 칸입니다. {spec['l1']}, {V1}."])))
    if spec.get("v2") is not None:
        V2 = hwon(spec["v2"])
        pairs.append(("cell2", pk([f"그 옆 칸, {spec['l2']} {V2}.", f"바로 아래 칸은 {spec['l2']}, {V2}입니다.", f"짝이 되는 칸은 {spec['l2']} {V2}.",
                                   f"견줄 칸은 {spec['l2']}, {V2}입니다.", f"다른 한 칸, {spec['l2']} {V2}.", f"옆 칸 {spec['l2']}는 {V2}입니다."])))
    rows = [{"label": spec["l1"], "v": round(spec["v1"]), "hi": True}]
    if spec.get("v2") is not None:
        rows.append({"label": spec["l2"], "v": round(spec["v2"]), "hi": True})
    if calc:
        n = calc["n"]
        if calc["kind"] == "ratio":
            pairs.append(("calc", pk([f"나누면 {n}배입니다.", f"앞 칸이 뒤 칸의 {n}배입니다.", f"{n}배 차이입니다.", f"뒤 칸의 {n}배가 앞 칸입니다.",
                                      f"비율로는 {n}배입니다.", f"두 칸을 나누면 {n}배가 나옵니다."])))
        elif calc["kind"] == "fraction":
            pairs.append(("calc", pk([f"앞 칸은 뒤 칸의 {n}분의 1입니다.", f"{n}분의 1, 그게 두 칸의 비율입니다.", f"나누면 {n}분의 1이 나옵니다.",
                                      f"뒤 칸에 견주면 {n}분의 1 크기입니다.", f"비율로는 {n}분의 1입니다."])))
        elif calc["kind"] == "share":
            pairs.append(("calc", pk([f"비율로는 {n}%입니다.", f"나누면 {n}%가 나옵니다.", f"앞 칸이 뒤 칸의 {n}%입니다.", f"{n}%, 그게 이 두 칸의 답입니다.",
                                      f"뒤 칸에서 앞 칸이 차지하는 몫은 {n}%입니다.", f"두 칸을 나누면 {n}%입니다."])))
        else:
            pairs.append(("calc", pk([f"나누면 {n}거래일치입니다.", f"이 속도면 {n}거래일치입니다.", f"하루치로 나누면 {n}거래일이 걸립니다." if False else f"오늘 속도로는 {n}거래일치입니다.",
                                      f"{n}거래일치 물량입니다.", f"앞 칸을 뒤 칸으로 나누면 {n}거래일치입니다."])))
        calc = {k: v for k, v in calc.items() if k != "n"}
        calc["verified"] = True
    tts, steps = _steps(pairs)
    return tts, {"doc": doc, "rows": rows, "calc": calc, "kind": kind, "tts": tts, "steps": steps}, kind


# ══════════════════════════════════════════════════════════════════════════════
# S5 양면 판정 + 조건 — "[A]면 [X]. [B]면 [Y]. 오늘은 [A] 쪽입니다." + S0 숫자 콜백 1회 + 한계 고백 1문장 + 뒤집히는 조건(마지막, 질문 아님).
# 프레임 F1~F4 는 _pick_frame 이 골랐다(S1 의 질문과 짝). '여러분'·질문 끝·매매 판단 없음.
# ══════════════════════════════════════════════════════════════════════════════
def _s5(x: dict, frame: str, s0: dict, c: dict, pk: Picker) -> tuple[str, dict]:
    P, sold, amt, st, d = x["P"], x["sold"], x["amount"], x["st_p"], x["d"]
    word, oppw = ("순매도", "순매수") if sold else ("순매수", "순매도")
    nxt = _day_word(d, na.next_trading_day(d).strftime("%Y%m%d"), past=False)
    wy = _day_word(d, x["prev_date"], past=True)
    yv = x["y_P"]
    pairs: list[tuple[str, str]] = []
    pairs.append(("lead", pk(["정리합니다.", "여기까지 놓고 판정합니다.", "이제 답입니다.", "두 칸으로 정리합니다.", "판정으로 갑니다.", "답을 내립니다."])))
    if frame == "F1":
        a_t, b_t = "파는 쪽이 줄어든 날", "받는 쪽이 버틴 날"
        verdict = _f1_verdict(x)
        pairs.append(("A", pk([f"파는 쪽이 줄어든 거면 {P} {word}가 {wy}보다 작아야 합니다.", f"파는 쪽이 줄어든 날이면 {P} {word} 막대가 짧아집니다.",
                               f"파는 쪽이 줄어든 거면 {P}이 먼저 손을 뗀 겁니다."])))
        pairs.append(("B", pk([f"받는 쪽이 버틴 거면 {P}은 오늘도 팔고, 그걸 누군가 받아야 합니다." if sold else f"받는 쪽이 버틴 거면 {P}은 오늘도 사고, 그걸 누군가 내놓아야 합니다.",
                               f"받는 쪽이 버틴 날이면 {P} 막대는 그대로고 받은 막대가 큽니다.", f"받는 쪽이 버틴 거면 {P} 손은 안 멈춘 겁니다."])))
        if verdict == "b":
            pairs.append(("verdict", pk(["오늘은 받는 쪽이 버틴 쪽입니다.", "오늘은 받는 쪽 손이 버틴 쪽입니다.", "판정은 받는 쪽이 버틴 쪽입니다."])))
            pairs.append(("support", pk([f"{P} {word} {dko(st)}, 오늘 {hwon(amt)}.", f"{josa(P)} {dko(st)} {'팔았' if sold else '샀'}고, 오늘 {hwon(amt)}입니다.",
                                         f"{dko(st)} 같은 손, 오늘 몫은 {hwon(amt)}입니다."])))
            cond = f"{subj(P)} {nxt} {oppw}로 돌아서는"
        else:
            pairs.append(("verdict", pk(["오늘은 파는 쪽이 줄어든 쪽입니다.", "오늘은 파는 손이 줄어든 쪽입니다.", "판정은 파는 쪽이 줄어든 쪽입니다."])))
            if isinstance(yv, (int, float)):
                pairs.append(("support", pk([f"{P} {word}는 {wy} {hwon(yv)}에서 오늘 {ro(hwon(amt))} 줄었습니다.", f"{wy} {hwon(yv)}, 오늘 {hwon(amt)}입니다.",
                                             f"{P} 막대가 {hwon(yv)}에서 {ro(hwon(amt))} 짧아졌습니다."])))
            else:
                pairs.append(("support", pk([f"{P} {word}는 오늘 {hwon(amt)}입니다.", f"오늘 {P} 몫은 {hwon(amt)}입니다.", f"{P} 막대는 {hwon(amt)}에 그쳤습니다."])))
            cond = f"{P} {word}가 {nxt} 다시 {hwon(yv)} 수준으로 커지는" if isinstance(yv, (int, float)) and abs(yv) >= 1000 else f"{P} {word}가 {nxt} 다시 1조를 넘는"
    elif frame == "F2":
        in_th, in_t, out_th, out_t = x["in_th"], x["in_t"] or 0, x["out_th"], x["out_t"] or 0
        a_t, b_t = "돈이 옮겨간 날", "돈이 나가는 중인 날"
        verdict = "a" if (out_t and in_t >= 0.5 * abs(out_t)) else "b"
        pairs.append(("A", pk([f"옮겨간 거면 {in_th} 유입이 {out_th} 유출의 절반은 돼야 합니다.", f"옮겨간 날이면 들어온 막대가 나간 막대의 절반은 됩니다.",
                               f"옮겨간 거면 {out_th}에서 나간 돈이 {ro(in_th)} 그대로 건너갑니다."])))
        pairs.append(("B", pk(["나가는 중이면 들어온 돈은 나간 돈의 몇 분의 일에 그칩니다.", "나가는 중인 날이면 들어온 막대는 짧고 나간 막대만 깁니다.",
                               "나가는 중이면 돈이 코스피 밖으로 빠지는 겁니다."])))
        if verdict == "b":
            pairs.append(("verdict", pk(["오늘은 나가는 중인 쪽입니다.", "오늘은 돈이 나가는 중인 쪽입니다.", "판정은 나가는 중인 쪽입니다."])))
            kk = round(abs(out_t) / in_t) if in_t else 0
            pairs.append(("support", pk([f"들어온 {in_th} {hwon(in_t)}, 나간 {out_th} {hwon(out_t)}." if in_t else f"{out_th}에서 {subj(hwon(out_t))} 나갔습니다.",
                                         f"들어온 {josa(hwon(in_t))} 나간 {hwon(out_t)}에 한참 못 미칩니다." if in_t else f"나간 돈 {hwon(out_t)}, 들어온 자리는 비었습니다.",
                                         f"들어온 돈은 나간 돈의 {kk}분의 1입니다." if kk >= 3 else f"{out_th} 유출 {subj(hwon(out_t))} 훨씬 큽니다."])))
            half = hwon(abs(out_t) / 2) if out_t else "1조"
            cond = f"{ro(in_th)} 하루 {half} 넘게 들어오거나, {subj(P)} {oppw}로 돌아서는" if in_th else f"{subj(P)} {oppw}로 돌아서는"
        else:
            pairs.append(("verdict", pk(["오늘은 옮겨간 쪽입니다.", "오늘은 돈이 자리를 옮긴 쪽입니다.", "판정은 옮겨간 쪽입니다."])))
            pairs.append(("support", pk([f"들어온 {in_th} {hwon(in_t)}, 나간 {out_th} {hwon(out_t)}.", f"들어온 {subj(hwon(in_t))} 나간 {hwon(out_t)}의 절반을 넘습니다.",
                                         f"{ro(in_th)} 건너간 돈이 {hwon(in_t)}입니다."])))
            cond = f"{in_th} 유입이 {nxt} 끊기는"
    elif frame == "F4":
        a_t, b_t = "새 돈이 받은 날", "회사 예산이 받은 날"
        oth = x["oth"]
        others_max = max([v for n, v in x["buyers"] if n != "기타법인"], default=0)
        received = sum(v for _, v in x["buyers"]) or 1
        verdict = "b" if (oth >= others_max or oth >= 0.3 * received) else "a"
        sh = round(x["oth_share"] * 100)
        pairs.append(("A", pk(["새 돈이면 개인이나 기관 순매수가 기타법인보다 커야 합니다.", "새 돈이 받은 날이면 기타법인 막대는 작고 개인·기관 막대가 큽니다.",
                               "새 돈이면 바깥에서 온 손이 가장 큰 막대여야 합니다."])))
        pairs.append(("B", pk(["회사 예산이면 기타법인 몫이 가장 크고, 그 안은 자사주입니다.", "회사 예산이 받은 날이면 가장 큰 막대의 정체가 자사주입니다.",
                               "회사 예산이면 받은 돈의 주인이 그 회사들입니다."])))
        if verdict == "b":
            pairs.append(("verdict", pk(["오늘은 회사 예산 쪽입니다.", "오늘은 회사 예산이 받은 쪽입니다.", "판정은 회사 예산 쪽입니다."])))
            pairs.append(("support", pk([f"기타법인 {hwon(oth)}, 그중 {sh}%가 두 회사 자사주입니다." if sh else f"기타법인 {subj(hwon(oth))} 가장 큰 막대입니다.",
                                         f"{sh}%가 자사주인 기타법인 {subj(hwon(oth))} 1위입니다." if sh else f"가장 큰 막대는 기타법인, {hwon(oth)}입니다.",
                                         f"받은 돈 가운데 기타법인이 {hwon(oth)}입니다."])))
            cond = "개인과 기관 순매수를 합쳐 기타법인을 넘어서는"
        else:
            top_n, top_v = x["buyers"][0] if x["buyers"] else ("개인", 0)
            pairs.append(("verdict", pk(["오늘은 새 돈 쪽입니다.", "오늘은 바깥 돈이 받은 쪽입니다.", "판정은 새 돈 쪽입니다."])))
            pairs.append(("support", pk([f"{top_n} {subj(hwon(top_v))} 기타법인 {hwon(oth)}보다 큽니다.", f"가장 큰 막대는 {top_n}, {hwon(top_v)}입니다.",
                                         f"{top_n}이 {obj(hwon(top_v))} 받아 기타법인을 앞섰습니다."])))
            cond = "기타법인 순매수가 개인을 넘어서는"
    else:  # F3
        a_t, b_t = "하루 사정", "방향"
        verdict = "b" if st >= 3 else "a"
        pairs.append(("A", pk(["하루 사정이면 다음 날 끊깁니다.", "하루 사정인 날은 다음 날 막대 색이 바뀝니다.", "하루 사정이면 며칠째가 쌓이지 않습니다."])))
        pairs.append(("B", pk(["방향이면 며칠째가 쌓입니다.", "방향인 날은 같은 색 막대가 이어집니다.", "방향이면 같은 손이 며칠을 갑니다."])))
        if verdict == "b":
            pairs.append(("verdict", pk([f"오늘은 방향 쪽입니다. {dko(st)}입니다.", f"오늘은 방향 쪽입니다, {P} {word} {dko(st)}.", f"판정은 방향 쪽입니다. {dko(st)}째가 아니라 {dko(st)}, 같은 손입니다.".replace(f"{dko(st)}째", dko(st))])))
            pairs.append(("support", pk([f"오늘 몫은 {hwon(amt)}입니다.", f"{P} {word} {hwon(amt)}, 같은 방향입니다.", f"오늘도 {obj(hwon(amt))} {'팔았' if sold else '샀'}습니다."])))
            cond = f"{subj(P)} {nxt} {oppw}로 돌아서는"
        else:
            pairs.append(("verdict", pk(["오늘은 아직 하루 사정 쪽입니다.", "오늘은 하루 사정 쪽입니다. 아직 이틀입니다." if st == 2 else "오늘은 하루 사정 쪽입니다. 첫날입니다.",
                                         "판정은 아직 하루 사정 쪽입니다."])))
            pairs.append(("support", pk([f"{P} {word} {hwon(amt)}, 아직 {dko(max(st, 1))}입니다.", f"오늘 몫은 {hwon(amt)}입니다.", f"{dko(max(st, 1))}로는 방향이라 부르지 않습니다."])))
            cond = f"{P} {word}가 {dko(max(st, 1) + 1)}까지 이어지는" if st < 3 else f"{subj(P)} {nxt} {oppw}로 돌아서는"
    # S0 숫자 콜백
    a = s0.get("a") or {}
    a_sp = hwon(a.get("num")) if a.get("unit") == "억" and isinstance(a.get("num"), (int, float)) else str(a.get("value") or "")
    if a_sp:
        pairs.append(("callback", pk([f"처음에 본 {a_sp}, 그 숫자의 답이 이겁니다.", f"{ro(a_sp)} 시작한 이야기의 답입니다.", f"맨 앞의 {josa(a_sp)} 이렇게 읽힙니다.",
                                      f"첫 화면의 {subj(a_sp)} 여기까지 왔습니다.", f"{a_sp}, 그 숫자는 이 판정으로 닫힙니다."])))
    # 한계 고백 1문장
    src = str(c.get("inv_src") or "")
    if "키움" in src or not src:
        limit = pk(["정규장 체결 기준이라 대량매매는 이 표에 없습니다.", "이 표는 주체별 합계라 종목 사이 이동은 보이지 않습니다.", "장 뒤 대량매매는 이 합산에 빠져 있습니다.",
                    "확정치가 아니라 정규장 체결만 더한 값입니다.", "종목별 이동은 이 표 밖에 있습니다."])
    else:
        limit = pk(["주체별 합계만 있어 종목 사이 이동은 이 표에 없습니다.", "거래소 집계라 오후 2시 이후 흐름은 따로 안 보입니다.", "종목별 이동은 이 표 밖에 있습니다."])
    pairs.append(("limit", limit))
    if "거나" in cond:      # 조건이 둘이면 '하나' 라고 말하지 않는다
        pairs.append(("condition", pk([f"뒤집히는 조건은 {cond} 겁니다.", f"이 판정이 뒤집히는 조건은 {cond} 겁니다.",
                                       f"{cond} 날이면 판정이 뒤집힙니다, 뒤집히는 조건은 그 둘입니다.", f"이 판정이 뒤집히는 조건은 둘, {cond} 겁니다."])))
    else:
        pairs.append(("condition", pk([f"이 판정이 뒤집히는 조건은 하나, {cond} 겁니다.", f"뒤집히는 조건은 {cond} 겁니다.", f"이 판정이 뒤집히는 조건은 {cond} 겁니다.",
                                       f"{cond} 날이면 판정이 뒤집힙니다, 뒤집히는 조건은 그 하나입니다."])))
    tts, steps = _steps(pairs)
    return tts, {"a": a_t, "b": b_t, "verdict": verdict, "frame": frame, "condition": cond + " 것", "limit": limit, "callback_num": a_sp, "tts": tts, "steps": steps}


# ══════════════════════════════════════════════════════════════════════════════
# S6 내일 관측값 + 시그니처 — 관측값 1~2개(임계값 숫자) + 다음 이벤트 시각(질문 아님) + (이번 주) 애프터마켓 + 고정 시그니처.
# watch[0] 은 ledger.parse_q 가 읽는 형태('외국인 순매도가 엿새째 이어지는지').
# ══════════════════════════════════════════════════════════════════════════════
def _next_event(d: str, sched: list, fomc: list) -> dict | None:
    base = datetime.strptime(d, "%Y%m%d").replace(hour=15, minute=30)
    items = []
    for s in sched or []:
        dd, t = str((s or {}).get("d") or ""), str((s or {}).get("t") or "")
        if not dd or not t:
            continue
        try:
            if len(dd) >= 16:
                items.append((datetime.strptime(dd[:16], "%Y-%m-%d %H:%M"), t))
            elif "~" in dd and t == "FOMC":
                a, b = dd.split("~")
                end = datetime.strptime(a[:8] + b[-2:], "%Y-%m-%d")
                items.append((end + timedelta(days=1, hours=3), "미국 금리 결정"))
            else:
                items.append((datetime.strptime(dd[:10], "%Y-%m-%d").replace(hour=9), t))
        except ValueError:
            continue
    for f in fomc or []:
        try:
            a, b = str(f).split("/")
            end = datetime.strptime(a[:8] + b[-2:], "%Y-%m-%d")
            items.append((end + timedelta(days=1, hours=3), "미국 금리 결정"))
        except (ValueError, IndexError):
            continue
    items = sorted([i for i in items if i[0] > base], key=lambda i: i[0])
    if not items:
        return None
    at, label = items[0]
    gap = (at.date() - base.date()).days
    h, m = at.hour, at.minute
    part = "새벽" if h < 6 else "아침" if h < 12 else "오후" if h < 18 else "밤"
    hh = f"{part} {h if h <= 12 else h - 12}시" + (f" {m}분" if m else "")
    if gap == 0:
        when = f"오늘 {hh}"
    elif gap == 1:
        when = f"내일 {hh}"
    elif gap <= 6:
        when = f"{WD[at.weekday()]}요일 {hh}"
    else:
        when = f"{at.month}월 {at.day}일"
    return {"label": label, "when": when, "note": None, "at": at.strftime("%Y-%m-%d %H:%M"), "gap": gap}


def _s6(x: dict, c: dict, cont: dict, brand: str, pk: Picker) -> tuple[str, dict, str, list]:
    P, sold, st, d = x["P"], x["sold"], x["st_p"], x["d"]
    word = "순매도" if sold else "순매수"
    nd = na.next_trading_day(d)
    nxt = _day_word(d, nd.strftime("%Y%m%d"), past=False)
    nxt_x = f"{nxt}{'은' if nxt == '내일' else '엔'}"
    if P in ("외국인", "기관") and st >= 1:
        n = st + 1
    elif P in ("외국인", "기관"):
        n = 2
    else:
        n = None
    next_q = f"{P} {word}가 {dko(n)} 이어지는지" if n else f"{P} {word}가 이어지는지"
    watch = [{"q": next_q, "threshold": f"{n}거래일째" if n else "같은 부호"}]
    # 둘째 관측값: 기타법인 선(전 편 최소값) → 없으면 유입 업종 이틀째
    w2 = None
    oth, ob = x["oth"], cont.get("others_buy_days") or 0
    if oth >= 5000 and ob >= 2:
        vals = [oth]
        try:
            for r in sm._prev_kr(d, ob - 1):
                v = (r.get("facts") or {}).get("others")
                if isinstance(v, (int, float)) and v > 0:
                    vals.append(v)
        except Exception:
            pass
        thr = int(min(vals) // 1000 * 1000) if min(vals) >= 1000 else int(min(vals))
        w2 = {"q": f"기타법인 순매수가 {hwon(thr)}을 지키는지", "threshold": hwon(thr), "note": f"{dko(ob)} 지켜온 선입니다."}
    elif x["in_th"] and (x["in_t"] or 0) >= 300:
        stk = (x["in_m"] or {}).get("streak") or 1
        w2 = {"q": f"{x['in_th']} 순매수가 {dko(max(stk, 1) + 1)} 이어지는지", "threshold": dko(max(stk, 1) + 1), "note": ""}
    if w2:
        watch.append(w2)
    pairs: list[tuple[str, str]] = []
    if w2:
        pairs.append(("lead", pk([f"{nxt_x} 두 숫자만 봅니다.", f"{nxt} 볼 숫자는 둘입니다.", f"{nxt} 확인할 건 두 개입니다.", f"{nxt_x} 이 둘만 봅니다.",
                                  f"{nxt} 숙제는 둘입니다.", f"{nxt_x} 두 칸만 봅니다."])))
    else:
        pairs.append(("lead", pk([f"{nxt_x} 하나만 봅니다.", f"{nxt} 볼 숫자는 하나입니다.", f"{nxt} 확인할 건 한 가지입니다.", f"{nxt_x} 이 하나만 봅니다.",
                                  f"{nxt} 숙제는 하나입니다."])))
    if w2:
        note = (" " + w2["note"]) if w2.get("note") else ""
        pairs.append(("watch", pk([f"{next_q}. {w2['q']}.{note}", f"하나, {next_q}. 둘, {w2['q']}.{note}", f"먼저 {next_q}. 그리고 {w2['q']}.{note}",
                                   f"{next_q}. 또 하나, {w2['q']}.{note}"])))
    else:
        pairs.append(("watch", pk([f"{next_q}.", f"하나, {next_q}.", f"먼저 {next_q}."])))
        if n:
            pairs.append(("w1_thr", pk([f"이어지면 {n}거래일째입니다.", f"채워지면 {n}거래일째입니다.", f"그러면 {n}거래일째가 됩니다."])))
        else:
            pairs.append(("w1_thr", pk(["부호가 같은지만 봅니다.", "방향이 같은지만 봅니다.", "막대 색이 같은지만 봅니다."])))
    ev = _next_event(d, c.get("schedule") or [], c.get("fomc_dates") or [])
    if ev:
        when, lab = ev["when"], ev["label"]
        if ev["gap"] < (nd - datetime.strptime(d, "%Y%m%d")).days:
            pairs.append(("event", pk([f"그 전에 {when} {subj(lab)} 있습니다.", f"{when} {subj(lab)} 먼저입니다.", f"{josa(lab)} {when}, 그다음이 이 둘입니다." if w2 else f"{josa(lab)} {when}, 그다음이 이 숫자입니다.",
                                       f"{when} {obj(lab)} 지나 {nxt} 마감에서 답을 냅니다."])))
        else:
            pairs.append(("event", pk([f"{when} {lab} 전까지, 이 {'둘' if w2 else '하나'}입니다.", f"{josa(lab)} {when}입니다. 그 전까지 이 {'둘' if w2 else '하나'}를 봅니다.",
                                       f"시계는 {when} {lab}에 맞춰 둡니다.", f"{when} {lab}까지 이 숫자{'들' if w2 else ''}을 따라갑니다.",
                                       f"{subj(lab)} {when}에 있습니다. 그때까지 이 {'둘' if w2 else '하나'}입니다."])))
    else:
        pairs.append(("event", pk([f"이 {'둘' if w2 else '하나'}로 {nxt}을 엽니다.", f"{nxt} 마감에서 이 {'둘' if w2 else '하나'}를 확인합니다.", f"답은 {nxt} 이 자리에서 냅니다.",
                                   f"{nxt} 같은 시각에 이 숫자를 다시 놓습니다."])))
    when_up = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    after = d <= AFTER_MARKET_NOTICE_UNTIL
    if after:
        pairs.append(("after", "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다."))
    since = "내일부터 " if d == "20260915" else ""
    pairs.append(("sig", f"{na._ieot(brand)} 국장 마감은 {since}매일 {when_up}에 올라옵니다."))
    tts, steps = _steps(pairs)
    return tts, {"watch": watch, "event": ({"label": ev["label"], "when": ev["when"], "note": ev.get("note")} if ev else None),
                 "after_market": after, "when": when_up, "tts": tts, "steps": steps}, next_q, watch


# ══════════════════════════════════════════════════════════════════════════════
# 조립
# ══════════════════════════════════════════════════════════════════════════════
def build(c: dict, avoid: set[str] | None = None) -> dict:
    """헌터 포맷 대본. c 는 compute.narration_inputs() 가 만든 입력(build_aplus 입력 + stocks/kosdaq/upload_times/schedule …).
    avoid 는 검사에서 걸린 문장 집합 — 그 문장을 만든 후보를 빼고 다시 고른다. 어떤 키가 없어도 예외를 내지 않는다."""
    brand = c.get("brand") or "누가샀나"
    x = _ctx(c)
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
    pk = Picker(d, exact, masked, avoid)

    hook_kind, hook_parts, s0 = _s0(x, pk)
    frame = _pick_frame(x, hook_kind)
    s1_tts, s1 = _s1(x, frame, pk)
    s2_tts, s2, n_kind = _s2(x, cont, hook_kind, pk)
    s3a_tts, s3a, wk_rows = _s3a(x, cont, c, pk)
    s3c_pick = _s3c_pick(x)
    s3b_tts, s3b = _s3b(x, pk, s3c_pick[0])
    s3c_tts, s3c, c_kind, ev_used = _s3c(x, pk, s3c_pick)
    s4_tts, s4, k_kind = _s4(x, c, hook_kind, pk, said_share=bool(s2.get("said_share")), said_ratio=bool(s3b.get("said_ratio")) or frame == "F2")
    s5_tts, s5 = _s5(x, frame, s0, c, pk)
    s6_tts, s6, next_q, watch = _s6(x, c, cont, brand, pk)

    scenes = [
        {"id": "s0", "min": 4.0, "tts": s0["tts"], "sub": "", "steps": s0["steps"]},
        {"id": "s1", "min": 2.5, "tts": s1["tts"], "sub": s1["tts"], "steps": s1["steps"]},
        {"id": "s2", "min": 6.0, "tts": s2["tts"], "sub": s2["tts"], "steps": s2["steps"]},
        {"id": "s3a", "min": 5.0, "tts": s3a["tts"], "sub": s3a["tts"], "steps": s3a["steps"]},
        {"id": "s3b", "min": 5.0, "tts": s3b["tts"], "sub": s3b["tts"], "steps": s3b["steps"]},
        {"id": "s3c", "min": 5.0, "tts": s3c["tts"], "sub": s3c["tts"], "steps": s3c["steps"]},
        {"id": "s4", "min": 6.0, "tts": s4["tts"], "sub": s4["tts"], "steps": s4["steps"]},
        {"id": "s5", "min": 7.0, "tts": s5["tts"], "sub": s5["tts"], "steps": s5["steps"]},
        {"id": "s6", "min": 4.0, "tts": s6["tts"], "sub": "", "steps": s6["steps"]},
    ]
    hunter = {k: {kk: vv for kk, vv in v.items() if kk not in ("tts",)} for k, v in
              (("s0", s0), ("s1", s1), ("s2", s2), ("s3a", s3a), ("s3b", s3b), ("s3c", s3c), ("s4", s4), ("s5", s5), ("s6", s6))}
    P, amount, sold = x["P"], x["amount"], x["sold"]
    ct = na.contrast(x["k"], c.get("recent_closes") or [], sold) if x["k"] else {"kind": "pct", "text": "", "short": "", "line": None, "n_days": None, "opposite": False}
    opp = [(n, v) for n, v in x["opp"] if n != P]
    bars = [{"name": P, "v": amount}] + [{"name": n, "v": v} for n, v in opp] + [{"name": n, "v": v} for n, v in x["same"]]
    seen_n = {b["name"] for b in bars}
    bars += [{"name": n, "v": v} for n, v in x["vals"].items() if n not in seen_n]
    s2_title = f"{P} {_won_screen(amount, True)},<br>{'·'.join(n for n, _ in opp) or '—'}{'이' if opp else ''} {'받았다' if sold else '팔았다'}"
    lead_th = x["out_th"] if (x["out_th"] and x["out_t"] and (not x["in_t"] or abs(x["out_t"]) >= x["in_t"])) else x["in_th"]
    lead_m = x["out_m"] if lead_th == x["out_th"] else x["in_m"]
    story_lead = {"theme": lead_th, "t": x["flows"].get(lead_th), "who": "외국인+기관 합산", "names": (lead_m or {}).get("spread_names") or []} if lead_th else None
    cb = x["cb"]
    cbv = None
    if cb and isinstance(cb.get("check"), dict):
        ch = cb["check"]
        cbv = {"q": cb.get("q"), "kind": ch.get("kind"), "theme": ch.get("theme") or ch.get("name") or "", "n": ch.get("n"), "sign": ch.get("sign"),
               "when": _day_word(d, cb.get("prev_date"), past=True), "ok": cb.get("ok"), "amount": cb.get("t")}
    nd = na.next_trading_day(d)
    tag_when = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    return {
        "format": "hunter", "brand": brand, "tagline": f"오늘 국장, 누가 샀나? · 평일 {tag_when}",
        "hook": hook_parts[0], "hook_parts": hook_parts, "hook_id": hook_kind,
        "devices": sorted({frame, n_kind, c_kind, k_kind}), "caution_id": None,
        "next_q": next_q, "watch": [{"q": w["q"], "how": f"{_day_word(d, nd.strftime('%Y%m%d'), past=False)} 15:40 수급에서 확인", "assist": ""} for w in watch],
        "protagonist": {"name": P, "amount": amount, "sold": sold}, "contrast": ct,
        "check": {"verdict": cbv, "record": c.get("ledger_stats"), "next_q": next_q, "next_day": f"{nd.month}/{nd.day}"},
        "bars": bars, "s2_title": s2_title, "s3_title": lead_th or "", "s3_story": ({"verdict": None, "lead": story_lead, "summary": ""} if story_lead else None),
        "s2_marks": {"answer": (s2.get("reveal") or {}).get("name"), "counter": None, "bars": None, "snap": None, "prev": x["prev_inv"].get("others")},
        "event_used": bool(ev_used or hook_kind == "M4"), "others_top": na._others_top({**c, "date": d}), "weekend_watch": wk_rows,
        "fx_said": False, "bonding": "",
        "scenes": scenes, "hunter": hunter,
    }


# ── 자체 점검(참고용 — 정식 검사는 qa_script.check_hunter) ──
def lint(scenes: list[dict]) -> list[str]:
    """숫자 3토막 이상·그런데 2회·연속 그런데·질문으로 끝나는 S5·화면 지시어 수·집 규칙 금지어. 경고 문자열 목록."""
    out = []
    n_dir = 0
    try:
        from checks import forbidden
    except Exception:
        forbidden = None
    for sc in scenes:
        ss = sm.sentences(sc.get("tts") or "")
        if sc["id"] in ("s2", "s3a", "s3b", "s3c", "s4"):
            n_dir += sum(1 for s in ss if re.search(r"보세요|여기 이 칸|왼쪽|오른쪽|위 칸|아래 칸|막대", s))
        if (sc.get("tts") or "").count("그런데") > 1 and sc["id"] != "s2":
            out.append(f"[{sc['id']}] 그런데 {(sc.get('tts') or '').count('그런데')}회")
        for i, s in enumerate(ss):
            if sm.is_signature(s):
                continue
            try:
                import qa_script
                nn = len(qa_script.num_tokens(s))
            except Exception:
                nn = _ngroups(s)
            if nn > 2:
                out.append(f"[{sc['id']}] 숫자 토막 {nn}개 :: {s}")
            if i and "그런데" in s and "그런데" in ss[i - 1]:
                out.append(f"[{sc['id']}] 그런데 연속 :: {s}")
            if forbidden:
                hits = [h for h in forbidden.find(s) if not h.startswith("단정:")]
                if hits:
                    out.append(f"[{sc['id']}] 금지어 {hits} :: {s}")
        if sc["id"] == "s5" and ss and (ss[-1].endswith("?") or re.search(r"(는지|일까요|을까요|느냐)\s*[.]?$", ss[-1])):
            out.append(f"[s5] 질문으로 끝남 :: {ss[-1]}")
    if n_dir < 4:
        out.append(f"[s2-s4] 화면 지시어 {n_dir}회 < 4")
    return out
