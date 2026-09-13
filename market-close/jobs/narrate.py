"""대본 생성 v2.4 — 수급·돈의 흐름 중심. SPEC §5-2.
원칙(JJ 2026-09-05):
  - 인트로 10초 이내: 브랜드 + 날짜·요일 + '국내장/미국 주식 마감입니다' + 한 줄 훅(원인+결과 또는 미국→국장 방향 연결).
  - 지수는 고점·저점·종가·등락만. 시각(몇 시 몇 분) 서술 금지.
  - 이벤트는 결과 숫자 → 시장 반응 → 배경(뉴스 근거, 완곡) → 다음 관문(조건부 전망)으로 엮는다.
  - 수급이 본론: 누가 샀고(3주체·기타법인·프로그램·연속일), 돈이 어디로 들어와 어디에 머물고 어디로 옮겼는지(테마·종목).
  - 국장편은 간밤 미국 요약을 반복하지 않는다 → "아침 영상을 참고하세요" 한 줄.
  - 체크 항목은 '내일/다음 주 우리가 체크해야 할 것은' + 조건부 어시스트 문장(테마 단위, 종목명 없음).
"""
from __future__ import annotations

import re
from datetime import datetime

BRAND_DEFAULT = "밤낮장"
TAGLINE = "오늘 국장, 누가 샀고 돈은 어디로 갔나"


def brand_was(brand: str) -> str:
    """'밤낮장이었습니다' / '누가샀나였습니다'"""
    return f"{brand}{'이었' if _bat(brand) else '였'}습니다."
FX_MIN_MOVE = 5.0  # 원


# ── 말하기 포맷 ──
def josa(w: str, a: str = "은", b: str = "는") -> str:
    ch = (w or "").strip()[-1:]
    if ch and "가" <= ch <= "힣":
        return w + (a if (ord(ch) - 0xAC00) % 28 else b)
    return w + a


def won(v: float | None) -> str:
    """억원 → '약 3.7조' / '약 5천억' / '약 1,700억' / '약 630억'"""
    if v is None:
        return "미확정"
    a = abs(round(v))
    if a >= 10000:
        s = f"{a / 10000:.1f}".rstrip("0").rstrip(".")
        return f"약 {s}조"
    if a >= 1000:
        h = int(round(a / 100.0) * 100)
        if h >= 10000:
            return "약 1조"
        return f"약 {h // 1000}천억" if h % 1000 == 0 else f"약 {h:,}억"
    if a >= 100:
        return f"약 {int(round(a / 10.0) * 10):,}억"
    return f"{a}억"


def idx(v: float | None) -> str:
    return "미확정" if v is None else f"{int(round(v)):,}"


def pct(v: float | None) -> str:
    return "미확정" if v is None else f"{abs(v):.2f}%"


def pct1(v: float | None) -> str:
    """소수 한 자리(듣기용) — 0.05 미만 차이는 버린다."""
    return "미확정" if v is None else f"{abs(v):.1f}%"


def updown(v: float | None, up: str = "상승", down: str = "하락") -> str:
    return up if (v or 0) > 0 else down


def tm(t: str) -> str:
    h, m = int(t[:2]), int(t[2:])
    if h < 12:
        return f"오전 {h}시" + (f" {m}분" if m else "")
    return f"오후 {h - 12 if h > 12 else 12}시" + (f" {m}분" if m else "")


def date_spoken(d: str) -> str:
    dt = datetime.strptime(d, "%Y%m%d")
    return f"{dt.month}월 {dt.day}일 {'월화수목금토일'[dt.weekday()]}요일"


def sched_spoken(s: dict, today: str | None = None) -> str:
    dd = s["d"]
    if "~" in dd:
        a, b = dd.split("~")
        return f"{int(a[5:7])}월 {int(a[8:10])}일부터 {int(b[-2:])}일 {s['t']}"
    base = f"{int(dd[5:7])}월 {int(dd[8:10])}일"
    if today:
        t = datetime.strptime(today, "%Y%m%d")
        delta = (datetime.strptime(dd[:10], "%Y-%m-%d") - t).days
        if delta == 0:
            base = "오늘"
        elif delta == 1:
            base = "내일"
    if len(dd) >= 16:
        h, m = int(dd[11:13]), int(dd[14:16])
        when = ("밤" if h >= 18 else "오후" if h >= 12 else "오전") + f" {h - 12 if h > 12 else h}시" + (f" {m}분" if m else "")
        return f"{base} {when} {s['t']}"
    return f"{base} {s['t']}"


_DIGIT_BATCHIM = {"0": True, "1": "ㄹ", "2": False, "3": True, "4": False, "5": False, "6": True, "7": "ㄹ", "8": "ㄹ", "9": False}


def _bat(w: str) -> bool:
    """마지막 글자 받침 여부. 숫자는 읽는 소리 기준(영·삼·육 받침, 일·칠·팔 ㄹ받침, 이·사·오·구 없음)."""
    w = (w or "").strip()
    if w.endswith("%"):
        return False  # '퍼센트'
    ch = w.rstrip("원")[-1:]
    if ch.isdigit():
        return bool(_DIGIT_BATCHIM[ch])
    return bool(ch) and "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


def ro(w: str) -> str:
    """(으)로 — 받침 없거나 ㄹ받침이면 '로'"""
    ch = (w or "").strip()[-1:]
    if ch.isdigit():
        return w + ("으로" if _DIGIT_BATCHIM[ch] is True else "로")
    if ch and "가" <= ch <= "힣":
        code = (ord(ch) - 0xAC00) % 28
        return w + ("로" if code in (0, 8) else "으로")
    return w + "로"


def obj(w: str) -> str:
    """을/를"""
    return w + ("을" if _bat(w) else "를")


def subj(w: str) -> str:
    """이/가"""
    return w + ("이" if _bat(w) else "가")


def _and(names: list[str]) -> str:
    """['개인','외국인','기관'] → '개인, 외국인과 기관' / 2개 → '외국인과 기관' (받침에 따라 과/와)"""
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    head, last = names[:-1], names[-1]
    conj = "과 " if _bat(head[-1]) else "와 "
    return (", ".join(head[:-1]) + ", " if len(head) > 1 else "") + head[-1] + conj + last


DAYS_KO = {1: "하루째", 2: "이틀째", 3: "사흘째", 4: "나흘째", 5: "닷새째", 6: "엿새째", 7: "이레째"}


def days_ko(n: int) -> str:
    return DAYS_KO.get(n, f"{n}일째")


def _won_screen(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "—"
    a = abs(round(v))
    s = f"{a // 10000}조 {a % 10000:,}억" if a >= 10000 and a % 10000 else (f"{a // 10000}조" if a >= 10000 else f"{a:,}억")
    return (("＋" if v > 0 else "−" if v < 0 else "") if sign else "") + s


# ── 방향 어시스트(테마·시장 단위, 조건문, 종목명 없음) ──
# 방향 어시스트 문장(테마·주체 수준). forbidden.assist_ok 를 통과해야 compute 의 「다음에 볼 것」에 실린다
# — 조건 표지(면/경우/전까지/뒤에/확인) 필수, 금지어 부분문자열(잡아·사라 …) 금지. checks/test_forbidden.py 가 전 항목을 검사한다.
ASSIST_DEFAULT = "이어지면 방향을 잡고, 끊기면 판단은 미뤄도 늦지 않습니다."
ASSIST = {
    "buy_continue": "이어지면 그 흐름에 방향을 맞추고, 끊기면 매수 판단은 미루는 편이 안전해 보입니다.",
    "moved": "옮겨간 곳에서 이틀째 이어지는지 확인한 뒤에 방향을 정해도 늦지 않습니다.",
    "sell": "매도가 멈추는 게 확인되기 전까지는 서두를 이유가 없어 보입니다.",
    "rebound": "하루 반등인지는 이틀째 수급으로 갈리니, 확인 전까지는 판단을 미뤄도 늦지 않습니다.",
    "others": "자사주나 블록딜이면 하루짜리일 수 있어, 이틀째 확인 뒤에 판단해도 늦지 않습니다.",
    "foreign": "이어지면 방향을 잡고, 끊기면 판단은 미뤄도 늦지 않습니다.",
    "streak": "끊기면 되돌림의 시작일 수 있고, 이어지면 아직 기다릴 때로 보입니다.",
    "us_link": "이어지면 방향을 잡고, 끊기면 판단은 미뤄도 늦지 않습니다.",
}


def assist_for(kind: str) -> str:
    return ASSIST.get(kind, ASSIST_DEFAULT)


# 동행 한 줄(날짜로 순환). 수익 약속 없이 '같이 확인하고 기록으로 증명한다'는 결.
BONDING = [
    "시장에서 눈을 떼지 않고, 돈이 머무는 곳만 매일 같이 보겠습니다.",
    "맞은 날도 틀린 날도 기록에 그대로 남깁니다. 돈의 흐름만 보고도 되는지, 같이 증명해 가겠습니다.",
    "오늘 본 흐름이 이어지는지는 내일 수급이 말해 줍니다. 같이 확인하겠습니다.",
    "오늘도 누가 샀는지까지만 봤습니다. 사고파는 건 각자의 몫이고, 보는 건 같이 합니다.",
    "돈이 어디에 머무는지만 매일 같이 확인합니다. 그 기록이 이 채널의 답입니다.",
]
BONDING_SHORT = "돈이 어디에 머무는지만 매일 확인합니다. 맞는지는 기록으로 남깁니다."


def bonding_for(d: str) -> str:
    return BONDING[datetime.strptime(d, "%Y%m%d").toordinal() % len(BONDING)]


def hook_fact(c: dict) -> str:
    """첫 문장(첫 프레임): 오늘의 가장 센 사실 하나 + 금액. 장중→마감 반전 > 지수·수급 엇갈림 > 나스닥 연결 > 기본."""
    k, inv = c["kospi"], c.get("inv") or {}
    chg = k.get("chg_pct")
    turns = (c.get("intraday") or {}).get("turns") or []
    us = c.get("us_link") or {}
    three = sorted([(n, inv.get(kk) or 0) for n, kk in (("개인", "indiv"), ("외국인", "foreign"), ("기관", "inst"))], key=lambda x: -x[1])
    buyers = [(n, v) for n, v in three if v > 0][:2]
    if turns and turns[0]["kind"] == "flip":
        t = turns[0]
        nm = josa(t['name'], '이', '가')
        if t['a'] > 0:
            return f"{nm} 오후 2시 {obj(won(abs(t['a'])))} 매수하다가, 마감엔 {obj(won(abs(t['b'])))} 매도했습니다."
        return f"{nm} 오후 2시 {obj(won(abs(t['a'])))} 매도하다가, 마감엔 {obj(won(abs(t['b'])))} 매수했습니다."
    if chg is None:
        return ""
    both = [b for b in buyers if b[0] in ("외국인", "기관")]
    if chg < 0 and len(both) == 2:
        a, b = both[0][1], both[1][1]
        amt = f"{won(min(a, b))}씩" if abs(a - b) <= 0.15 * max(a, b) else f"{won(a)}, {won(b)}"
        return f"코스피는 {pct(chg)} 내렸는데 외국인과 기관은 {amt} 샀습니다."
    if chg > 0 and not buyers and (inv.get("others") or 0) > 0:
        return f"코스피는 {pct(chg)} 올랐는데 개인, 외국인, 기관은 다 팔았습니다."
    top = buyers[0] if buyers else None
    side = f" {josa(top[0], '이', '가')} {obj(won(top[1]))} 샀습니다." if top else ""
    if us.get("pct") is not None and abs(chg) >= 0.1:
        when = us.get("when") or "간밤"
        if (us["pct"] > 0) == (chg > 0):
            return f"{when} 나스닥 따라 코스피도 {pct(chg)} {updown(chg, '올랐고', '내렸고')},{side}" if side else \
                   f"{when} 나스닥 따라 코스피도 {pct(chg)} {updown(chg, '올랐습니다', '내렸습니다')}."
        return f"{when} 나스닥은 {updown(us['pct'], '올랐', '내렸')}지만 코스피는 {pct(chg)} {updown(chg, '올랐고', '내렸고')},{side}" if side else \
               f"{when} 나스닥은 {updown(us['pct'], '올랐', '내렸')}지만 코스피는 {pct(chg)} {updown(chg, '올랐습니다', '내렸습니다')}."
    if abs(chg) < 0.1:
        return f"코스피는 보합, {idx(k['close'])}에 마쳤고,{side}" if side else f"코스피는 보합, {idx(k['close'])}에 마쳤습니다."
    return f"코스피는 {pct(chg)} {updown(chg, '오른', '내린')} {idx(k['close'])}에 마쳤고,{side}" if side else \
           f"코스피는 {pct(chg)} {updown(chg, '오른', '내린')} {idx(k['close'])}에 마쳤습니다."


def stance_for(lead: dict | None) -> str:
    """돈의 상태별 방향 문장(테마·주체 수준, 종목 없음, 완곡). s5 맨 앞에 온다."""
    if not lead:
        return ""
    st, streak, t = lead.get("state") or "", lead.get("streak") or 0, lead.get("t") or 0
    if st.startswith("쌓임") and streak >= 3:
        return "돈이 머무는 곳을 먼저 눈여겨보는 게 순서입니다. 새로 들어가는 건 하루 더 이어지는지 확인한 뒤가 안전해 보입니다."
    if st.startswith("쌓임"):
        return "이틀째면 자리를 잡는 중으로 보입니다. 사흘째까지 이어지면 흐름으로 볼 수 있습니다."
    if st == "되돌림" or (t > 0 and streak <= 1):
        return "첫날 들어온 돈은 하루짜리일 때가 많아, 이틀째 확인이 먼저입니다."
    if st == "이동":
        return "돈이 떠난 곳은 쉬어가는 구간으로 보이고, 옮겨간 곳은 이틀째 이어지는지 확인이 먼저입니다."
    if st in ("이탈", "매도 확대", "매도 지속"):
        return "돈이 빠지는 곳은 쉬어가는 구간으로 보입니다. 매도가 멈추는 게 확인되기 전까지는 서두를 이유가 없어 보입니다."
    if st == "매도 축소":
        return "매도가 줄어드는 건 바닥을 다지는 신호일 수 있지만, 순매수로 돌아서는지 확인이 먼저입니다."
    return ""


def callback_sentence(cb: dict | None, hot: str | None = None) -> str:
    """전날 예고 검증: '어제 … 보자고 했죠. 오늘 …'. 끊긴 날도 그대로 말한다(신뢰는 여기서 쌓인다)."""
    if not cb:
        return ""
    chk, ok, t = cb["check"], cb["ok"], cb.get("t")
    kind = chk["kind"]
    if kind == "theme_continue":
        th, n = chk["theme"], chk.get("n")
        ask = f"어제 {josa(th, '이', '가')} {days_ko(n)} 이어지는지 보자고 했죠." if n else f"어제 {th} 순매수가 이어지는지 보자고 했죠."
        if ok:
            out = f"{ask} 오늘도 이어졌습니다. {subj(won(t))} 더 들어왔고, 돈은 아직 여기 있습니다."
        else:
            gone = f" {subj(won(abs(t)))} 빠졌습니다." if t is not None and t < 0 else ""
            out = f"{ask} 오늘은 끊겼습니다.{gone} 끊기면 판단은 미뤄도 늦지 않다고 한 이유가 이겁니다."
    elif kind == "theme_sell_stop":
        th = chk["theme"]
        out = f"어제 {th} 순매도가 멈추는지 보자고 했죠. " + (f"오늘 멈췄습니다. {subj(won(t))} 들어왔습니다." if ok else "오늘도 이어졌습니다. 아직 빠지는 중입니다.")
    elif kind == "theme_sell_cont":
        th = chk["theme"]
        out = f"어제 {th} 순매도가 이어지는지 보자고 했죠. " + ("오늘도 이어졌습니다." if ok else f"오늘은 멈췄습니다. {subj(won(t))} 들어왔습니다.")
    elif kind == "inv_continue":
        nm, word = chk["name"], "순매수" if chk["sign"] > 0 else "순매도"
        out = f"어제 {nm} {word}가 이어지는지 보자고 했죠. " + (f"오늘도 이어졌습니다. {won(abs(t))}입니다." if ok else f"오늘은 {'순매도' if chk['sign'] > 0 else '순매수'}로 돌아섰습니다. {won(abs(t))}입니다.")
    elif kind == "kosdaq_break":
        out = "어제 코스닥 연속 " + ("하락" if chk["sign"] < 0 else "상승") + "이 끊기는지 보자고 했죠. " + ("오늘 끊겼습니다." if ok else "오늘도 이어졌습니다.")
    else:
        return ""
    st = cb.get("stats") or {}
    if kind == "theme_continue" and st.get("n", 0) >= 5:
        out += f" 돈이 머문 곳이 다음 날도 이어진 경우는 지금까지 {st['n']}번 중 {st['k']}번입니다."
    return out


def _p(v: float) -> str:
    return f"{abs(v):.1f}%"


def event_pick(ev: dict) -> tuple[str, list[dict]]:
    """이슈 묶음 방향과 대표 종목 2개. up/down/mixed."""
    st = ev.get("stocks") or []
    if not st:
        return "none", []
    n_up, n_down, avg = ev.get("n_up", 0), ev.get("n_down", 0), ev.get("avg_pct", 0) or 0
    if n_up and n_down and abs(avg) < 0.5:
        return "mixed", [st[0], st[-1]]
    if n_up > n_down or (n_up == n_down and avg > 0):
        return "up", st[:2]
    return "down", st[-2:][::-1]


def event_sentence(ev: dict | None) -> str:
    """s4 앞 이슈 문장. 사실만(발표 → 등락 병치), 이유는 폴리시가 헤드라인 근거로만 덧붙인다."""
    if not ev:
        return ""
    kind, top = event_pick(ev)
    if kind == "none":
        return ""
    sp, grp = ev.get("spoken") or ev.get("label"), ev.get("group") or "관련주"
    st = ev.get("stocks") or []
    f_ = sum(x.get("foreign") or 0 for x in st)
    i_ = sum(x.get("inst") or 0 for x in st)
    if kind == "up":
        out = f"간밤 애플이 {obj(sp)} 공개했는데, 국장 {josa(grp)} {top[0]['name']} {_p(top[0]['pct'])}, {top[1]['name']} {_p(top[1]['pct'])}로 올랐습니다." if len(top) > 1 else f"간밤 애플이 {obj(sp)} 공개했는데, 국장 {josa(grp)} {top[0]['name']} {_p(top[0]['pct'])}로 올랐습니다."
    elif kind == "down":
        out = f"간밤 애플이 {obj(sp)} 공개했지만, 국장 {josa(grp)} {top[0]['name']} {_p(top[0]['pct'])}, {top[1]['name']} {_p(top[1]['pct'])}로 내렸습니다." if len(top) > 1 else f"간밤 애플이 {obj(sp)} 공개했지만, 국장 {josa(grp)} {top[0]['name']} {_p(top[0]['pct'])}로 내렸습니다."
    else:
        out = f"간밤 애플이 {obj(sp)} 공개했는데, 국장 {josa(grp)} 엇갈렸습니다. {josa(top[0]['name'])} {_p(top[0]['pct'])} 올랐고 {josa(top[1]['name'])} {_p(top[1]['pct'])} 내렸습니다."
    if abs(f_) + abs(i_) >= 100:
        bits = []
        if abs(f_) >= 50:
            bits.append(f"외국인은 {obj(won(abs(f_)))} {'순매수' if f_ > 0 else '순매도'}")
        if abs(i_) >= 50:
            bits.append(f"기관은 {obj(won(abs(i_)))} {'순매수' if i_ > 0 else '순매도'}")
        if bits:
            out += " 이 묶음에서 " + ", ".join(bits) + "했습니다."
    return out


# ── 국장편(저녁) ──
def build(c: dict) -> dict:
    brand = c.get("brand") or BRAND_DEFAULT
    k, q = c["kospi"], c["kosdaq"]
    inv, moves, stocks, schedule = c.get("inv"), c.get("moves") or [], c.get("stocks") or [], c.get("schedule") or []
    fx, us = c.get("fx"), c.get("us_link") or {}
    inv_streak = c.get("inv_streak") or {}
    next_label = c.get("next_label") or "내일"
    chg = k.get("chg_pct")

    # S0 인트로(≤10초): 브랜드·날짜 + 미국→국장 방향 연결 + 코스피 한 숫자
    head = f"{brand}, {date_spoken(c['date'])} 국내장 마감입니다."
    kr_word = "보합" if chg is not None and abs(chg) < 0.1 else None
    # 산 쪽/판 쪽 한 마디(조사 근거: 지수는 종속절, 수급 주체가 주절)
    side = ""
    if inv:
        three = sorted([(n, inv.get(kk) or 0) for n, kk in (("개인", "indiv"), ("외국인", "foreign"), ("기관", "inst"))], key=lambda x: -x[1])
        buyers = [n for n, v in three if v > 0][:2]
        if buyers:
            side = f" {_and(buyers)}이 샀습니다."
        elif (inv.get("others") or 0) > 0:
            side = " 셋 다 팔았고 기타법인이 샀습니다."
    when = us.get("when") or "간밤"
    if us.get("pct") is not None and chg is not None:
        us_dir = updown(us["pct"], "오른", "내린")
        us_did = updown(us["pct"], "올랐", "내렸")
        if kr_word:
            hook = f"{when} 나스닥이 {us_dir} 가운데 코스피는 보합, {idx(k['close'])}에 마쳤습니다.{side}"
        elif (us["pct"] > 0) == (chg > 0):
            hook = f"{when} 나스닥 따라 코스피도 {pct(chg)} {updown(chg, '올랐고', '내렸고')},{side}" if side else                    f"{when} 나스닥 {updown(us['pct'])}에 이어 코스피도 {pct(chg)} {updown(chg, '오른', '내린')} {idx(k['close'])}에 마쳤습니다."
        else:
            hook = f"{when} 나스닥은 {us_did}지만 코스피는 {pct(chg)} {updown(chg, '올랐고', '내렸고')},{side}" if side else                    f"{when} 나스닥은 {us_did}지만 코스피는 반대로 {pct(chg)} {updown(chg, '오른', '내린')} {idx(k['close'])}에 마쳤습니다."
    elif chg is not None:
        contrast = side and ((chg < 0 and "샀습니다" in side) or (chg > 0 and "팔았" in side))
        if contrast and not kr_word:
            hook = f"코스피는 {pct(chg)} {updown(chg, '올랐', '내렸')}는데,{side.replace('이 샀습니다', '은 샀습니다').replace('가 샀습니다', '는 샀습니다')}"
        else:
            hook = (f"코스피는 {pct(chg)} {updown(chg, '오른', '내린')} {idx(k['close'])}에 마쳤습니다." if not kr_word else f"코스피는 보합, {idx(k['close'])}에 마쳤습니다.") + side
    else:
        hook = "오늘 국장에서 돈이 어디로 움직였는지 보겠습니다."
    fact = hook_fact(c) or hook
    d0 = datetime.strptime(c["date"], "%Y%m%d")
    hook_parts = [fact, "그 돈은 어디로 갔을까요?", f"{d0.month}월 {d0.day}일 국장 마감, {brand}."]
    s0 = " ".join(hook_parts)
    hook = fact

    # S1 지수(고·저·종가만) + 배경 한 문장(뉴스 근거는 polish가 채움, 여기선 데이터 기반 완곡문)
    parts = []
    if k.get("high") and k.get("low") and k.get("close"):
        parts.append(f"코스피는 고점 {idx(k['high'])}, 저점 {obj(idx(k['low']))} 거쳐 {idx(k['close'])}에 마감했고,")
    if q.get("close") and q.get("chg_pct") is not None:
        qs = q.get("streak") or 0
        tail = f" {abs(qs)}일 연속 {'하락' if qs < 0 else '상승'}입니다" if abs(qs) >= 3 else ""
        parts.append(f"코스닥은 {pct(q['chg_pct'])} {updown(q['chg_pct'], '올랐', '내렸')}습니다.{tail}")
    reason = c.get("reason_fallback")
    if reason:
        parts.append(reason)
    s1 = " ".join(parts)

    # S2 수급 — 본론 1
    bars, s2_title = [], "수급 집계 대기"
    if inv:
        three = [("개인", inv.get("indiv")), ("외국인", inv.get("foreign")), ("기관", inv.get("inst"))]
        sellers = [(n, v) for n, v in three if v is not None and v < 0]
        buyers = [(n, v) for n, v in three if v is not None and v > 0]
        others = inv.get("others")
        idx_up = (chg or 0) > 0
        bars = [{"name": n, "v": v} for n, v in three] + [{"name": "기타법인", "v": others}]

        def grp(items: list, verb: str) -> str:
            names = [n for n, _ in items]
            amts = [won(v) for _, v in items]
            if len(items) == 1:
                return f"{josa(names[0])} {obj(amts[0])} {verb}"
            return f"{_and(names)}은 각각 {obj(_and(amts))} {verb}"

        if len(sellers) == 3:
            s2 = f"국장 수급입니다. 개인, 외국인, 기관이 각각 {obj(_and([won(v) for _, v in three]))} 순매도했습니다. " + \
                 (f"셋 다 팔았는데 지수는 올랐고, 산 쪽은 기타법인으로 {obj(won(others))} 순매수했습니다." if idx_up and others and others > 0
                  else "셋 다 팔았고 지수도 내렸습니다." + (f" 기타법인은 {obj(won(others))} 순매수했습니다." if others and others > 0 else ""))
            s2_title = f"셋이 판 {_won_screen(-sum(v for _, v in three))},<br>산 쪽은 {'기타법인' if others and others > 0 else '없음'}"
        elif len(buyers) == 3:
            s2 = f"국장 수급입니다. 개인, 외국인, 기관이 각각 {obj(_and([won(v) for _, v in three]))} 순매수했습니다. " + \
                 (f"셋 다 샀는데 지수는 내렸고, 판 쪽은 기타법인으로 {obj(won(others))} 순매도했습니다." if not idx_up and others and others < 0
                  else "셋 다 샀고 지수도 올랐습니다.")
            s2_title = f"셋이 산 {_won_screen(sum(v for _, v in three))}"
        else:
            s2 = "국장 수급입니다. " + grp(sellers, "순매도했고") + ", " + grp(buyers, "순매수했습니다") + "."
            if others is not None and abs(others) >= 3000:
                s2 += f" 기타법인도 {obj(won(others))} {'순매수' if others > 0 else '순매도'}했습니다."
            big = max(three, key=lambda x: abs(x[1] or 0))
            _o = [("기타법인", others)] if others is not None and abs(others) >= 3000 else []
            _buy = [n for n, v in sorted([x for x in buyers + [o for o in _o if o[1] > 0]], key=lambda x: -x[1])]
            _sell = [n for n, v in sorted([x for x in sellers + [o for o in _o if o[1] < 0]], key=lambda x: x[1])]
            s2_title = (f"{big[0]} {_won_screen(big[1], True)},<br>{'·'.join(n for n in _buy if n != big[0])}{'이' if _buy else ''} 받았다" if big[1] < 0
                        else f"{big[0]} {_won_screen(big[1], True)},<br>{'·'.join(n for n in _sell if n != big[0])}{'이' if _sell else ''} 팔았다")
        # 연속일·전환(외국인·기관)
        turns = []
        for name, key in (("외국인", "foreign"), ("기관", "inst")):
            st = inv_streak.get(key) or {}
            n, back = st.get("streak") or 0, st.get("turned_after") or 0
            v = inv.get(key)
            if v is None:
                continue
            if back >= 3:
                turns.append(f"{josa(name)} {back}일 만에 {'순매수' if v > 0 else '순매도'}로 돌아섰고")
            elif abs(n) >= 2:
                turns.append(f"{josa(name)} {days_ko(abs(n))} {'순매수' if n > 0 else '순매도'}를 이어갔고")
        if len(turns) == 2 and turns[0].split(" ", 1)[1] == turns[1].split(" ", 1)[1]:
            turns = ["외국인과 기관 모두 " + turns[0].split(" ", 1)[1]]
        if turns:
            s2 += " " + ", ".join(turns[:-1] + [turns[-1][:-1] + "습니다."])
        it = c.get("intraday") or {}
        if it.get("turns"):
            t = it["turns"][0]
            hm = it.get("at", "14:00"); hh, mm = int(hm[:2]), int(hm[3:5])
            when = f"오후 {hh - 12}시" + (f" {mm}분" if mm else "")
            if t["kind"] == "flip":
                s2 += f" {when}엔 {subj(t['name'])} {won(abs(t['a']))} {'순매도' if t['a'] < 0 else '순매수'}였는데, 마감엔 {won(abs(t['b']))} {'순매수' if t['b'] > 0 else '순매도'}로 돌아섰습니다."
            elif t["kind"] == "more":
                s2 += f" {t['name']} {'순매수' if t['b'] > 0 else '순매도'}는 {when} {won(abs(t['a']))}에서 마감 {ro(won(abs(t['b'])))} 막판에 더 {'들어왔' if t['b'] > 0 else '늘었'}습니다."
            else:
                s2 += f" {t['name']} {'순매수' if t['b'] > 0 else '순매도'}는 {when} {won(abs(t['a']))}에서 마감 {ro(won(abs(t['b'])))} 막판에 줄었습니다."
        prog = k.get("program_eok")
        if prog is not None and abs(prog) >= 10000:
            s2 += f" 프로그램 매매는 {won(prog)} {'순매수' if prog > 0 else '순매도'}였습니다."
        if c.get("others_why"):
            s2 += f" {c['others_why']}"
    else:
        s2 = "국장 수급은 집계가 끝나는 대로 다시 전해드리겠습니다."

    # S3 돈의 흐름 — 본론 2 (어디로 들어왔고, 어디에 머물고, 어디로 옮겼는지 + 누가 샀는지)
    def who(m: dict) -> str:
        f, i = m.get("foreign"), m.get("inst")
        if f is None or i is None:
            return ""
        if f > 0 and i > 0:
            return "외국인과 기관이 둘 다 샀고"
        if f > 0 > i:
            return f"외국인이 {obj(won(f))} 사고 기관은 {won(abs(i))} 팔았고"
        if i > 0 > f:
            return f"기관이 {obj(won(i))} 사고 외국인은 {won(abs(f))} 팔았고"
        return "외국인과 기관이 둘 다 팔았고"

    def move_sentence(m: dict, lead: bool) -> str:
        t, st = m["theme"], m["state"]
        names = (m.get("spread_names") or [])[:3]
        tail_names = f" {_and(names)}로 번졌습니다." if lead and names and st.startswith("쌓임") and "확산" in st else ""
        if st.startswith("쌓임"):
            s = f"{t}에는 {days_ko(m['streak'])} 쌓이고 있습니다."
            if lead:
                s += f" 오늘만 {won(m['t'])}, {who(m)} {_and(names)}에 몰렸습니다." if names else f" 오늘만 {won(m['t'])}, {who(m).rstrip('고')}습니다."
            return s + tail_names
        if st == "되돌림":
            if lead:
                w = who(m)
                s = f"{t}에 {subj(won(m['t']))} 들어와 전날 급락분을 되돌렸고, {w[:-1] + '습니다.' if w else ''}"
                return s.strip() + (f" {_and(names)}에 몰렸습니다." if names else "")
            return f"{josa(t)} {subj(won(m['t']))} 들어오며 전날 급락분을 되돌렸습니다."
        if st == "매도 축소":
            return f"{t} 순매도는 {won(abs(m['y']))}에서 {ro(won(abs(m['t'])))} 크게 줄었습니다."
        if st == "매도 확대":
            return f"{t} 순매도는 {won(abs(m['y']))}에서 {ro(won(abs(m['t'])))} 늘었습니다."
        if st == "매도 지속":
            return f"{josa(t)} {won(m['t'])} 순매도가 이어졌습니다."
        if st == "이동":
            return f"{t}에서는 {subj(won(abs(m['t'])))} 빠졌습니다." if m.get("t", 0) < 0 else f"돈은 {t}에서 {ro(m.get('moved_to', '다른 테마'))} 옮겨갔습니다."
        if st == "이탈":
            return f"{josa(t)} 순매수에서 순매도로 돌아섰습니다."
        return f"{josa(t)} {won(m['y'])}에서 {ro(won(m['t']))} 바뀌었습니다."

    if moves:
        lead = max(moves, key=lambda m: m["t"]) if any(m["t"] > 0 for m in moves) else moves[0]
        s4_names = {x["name"] for x in stocks[:2]}
        if s4_names & set(lead.get("spread_names") or []):
            lead = {**lead, "spread_names": []}
        ordered = [lead] + [m for m in moves if m is not lead and m["theme"] != lead["theme"] and not (m["state"] == "이동" and m.get("moved_to") == lead["theme"])]
        hot = [m["theme"] for m in sorted(moves, key=lambda m: -m["t"]) if m["t"] > 0][:2]
        cold = [m["theme"] for m in moves if m["t"] < 0][:2]
        if not cold:
            cold = [m["theme"] for m in moves if m["state"] == "이동" and m.get("moved_to") == lead["theme"]][:1]
        stay = [m["theme"] for m in moves if m["state"].startswith("쌓임") and m["streak"] >= 3 and m["theme"] != lead["theme"]]
        summ = ""
        _in = sum(m["t"] for m in moves if m["theme"] in hot)
        _out = sum(-m["t"] for m in moves if m["theme"] in cold and m["t"] < 0)
        if hot and cold and _out > 0 and _in < 0.3 * _out:
            summ = f" 정리하면 오늘은 {_and(cold)}에서 빠진 돈이 훨씬 컸고, 들어온 곳은 {_and(hot)} 정도였습니다."
        elif hot and cold:
            summ = f" 정리하면 돈은 {_and(cold)}에서 {ro(_and(hot))} 옮겨갔습니다."
        elif hot:
            summ = f" 정리하면 오늘 돈은 {_and(hot)}에 들어와 있습니다."
        elif cold:
            summ = f" 정리하면 오늘 돈은 {_and(cold)}에서 빠져나갔습니다."
        if stay:
            summ += f" {_and(stay)}에는 며칠째 머물고 있습니다."
        cb_s = callback_sentence(c.get("callback"), hot[0] if hot else None)
        reveal = f"{lead['theme']}입니다. " if lead["t"] > 0 else ""
        s3 = (cb_s + " " if cb_s else "") + "그럼 오늘 국장에서 돈은 어디로 갔을까요? " + reveal + " ".join(move_sentence(m, i == 0) for i, m in enumerate(ordered)) + summ
        cb = c.get("callback")
        _f, _i = lead.get("foreign"), lead.get("inst")
        who_short = ("외국인·기관 둘 다 매수" if (_f or 0) > 0 and (_i or 0) > 0 else "외국인 매수" if (_f or 0) > 0 else "기관 매수" if (_i or 0) > 0 else "")
        names_spoken = (lead.get("spread_names") or [])[:3] if (lead["state"].startswith("쌓임") or lead["state"] == "되돌림") else []
        s3_story = {
            "verdict": ({"kind": cb["check"]["kind"], "theme": cb["check"].get("theme") or cb["check"].get("name") or "", "n": cb["check"].get("n"), "ok": cb["ok"], "amount": cb.get("t")} if cb else None),
            "lead": ({"theme": lead["theme"], "t": lead["t"], "who": who_short, "names": names_spoken} if lead["t"] > 0 else None),
            "summary": summ.strip(),
        }
        s3_title = (f"{lead['theme']}에 {lead['streak']}일째 쌓인다" if lead["state"].startswith("쌓임")
                    else f"{lead['theme']}에서 {lead.get('moved_to', '')}로" if lead["state"] == "이동"
                    else f"{lead['theme']}, {lead['state']}")
    else:
        s3, s3_title = "테마별 자금 흐름은 집계 뒤 전해드리겠습니다.", "테마 수급 대기"
        s3_story = None

    # S4 종목 수급 + 환율(의미 있을 때) + 아침 영상 안내
    parts = []
    if stocks:
        bits = []
        for s in stocks[:2]:
            f, i = s.get("foreign") or 0, s.get("inst") or 0
            w = max((("외국인", f), ("기관", i), ("개인", s.get("indiv") or 0)), key=lambda x: x[1])
            if s.get("mover"):
                bits.append(f"{josa(s['name'])} {pct(s['pct'])} {updown(s['pct'], '올랐고', '내렸고')} {subj(w[0])} {obj(won(w[1]))} 순매수했습니다")
            elif f > 0 and i > 0:
                bits.append(f"{s['name']}에 {subj(won(f + i))} 들어왔습니다")
            else:
                bits.append(f"{s['name']}에 {w[0]} {subj(won(w[1]))} 들어왔습니다")
        parts.append("종목별로는 " + ". ".join(bits) + ".")
    fx_said = False
    if fx and fx.get("chg") is not None and (abs(fx["chg"]) >= FX_MIN_MOVE or fx.get("note")):
        parts.append(f"환율은 {abs(fx['chg']):.1f}원 {'내린' if fx['chg'] < 0 else '오른'} {fx['close']:,.1f}원입니다." + (f" {fx['note']}입니다." if fx.get("note") else ""))
        fx_said = True
    s4 = " ".join(parts)
    ev_s = event_sentence(c.get("event"))
    if ev_s:
        s4 = (ev_s + " " + s4).strip()

    # S5 체크 + 어시스트 + 일정
    watch = c.get("watch") or []
    s5 = ""
    if watch:
        w0 = watch[0]
        if w0.get("stance"):
            s5 = f"{w0['stance']} {next_label} 우리가 볼 것은 {w0['q']}입니다."
        else:
            s5 = f"{next_label} 우리가 체크해야 할 것은 {w0['q']}입니다. {w0.get('assist') or assist_for('foreign')}"
    if schedule:
        gates = pick_gates(schedule, 2)
        near = [g for g in gates if (datetime.strptime(g["d"][:10], "%Y-%m-%d") - datetime.strptime(c["date"], "%Y%m%d")).days <= 3]
        gates = gates[:2] if len(near) >= 2 else gates[:1]
        s5 += (" " if s5 else "") + "주요 일정은 " + _and([sched_spoken(x, c['date']) + gate_watch(x) for x in gates]) + "입니다."
    bonding = bonding_for(c["date"])
    s5 += (" " if s5 else "") + bonding

    # 훅이 장중→마감 반전이면 s2의 같은 문장은 뺀다(중복·길이)
    if "오후 2시" in fact and s2:
        s2 = " ".join(x for x in re.split(r"(?<=[.])\s+", s2) if "오후 2시" not in x)

    # S6 아웃트로
    ut = c.get("upload_times") or {}
    s6 = f"{brand_was(brand)} 국장 마감은 매일 {ut.get('kr', '오후 4시 30분')}에 올라옵니다."

    return {
        "brand": brand, "tagline": c.get("tagline") or TAGLINE, "hook": hook, "hook_parts": hook_parts, "bonding": bonding, "s3_story": s3_story,
        "scenes": [
            {"id": "s0", "min": 4.0, "tts": s0, "sub": ""},
            {"id": "s1", "min": 7.0, "tts": s1, "sub": s1},
            {"id": "s2", "min": 8.0, "tts": s2, "sub": s2},
            {"id": "s3", "min": 10.0, "tts": s3, "sub": s3},
            {"id": "s4", "min": 6.0, "tts": s4, "sub": s4},
            {"id": "s5", "min": 7.0, "tts": s5, "sub": s5},
            {"id": "s6", "min": 3.0, "tts": s6, "sub": ""},
        ],
        "s2_title": s2_title, "s3_title": s3_title, "bars": bars, "fx_said": fx_said,
    }


GATE_TIER = {"미국 고용보고서": 0, "미국 소비자물가 CPI": 0, "미국 CPI": 0, "FOMC": 0, "선물·옵션 동시만기": 1, "미국 생산자물가 PPI": 2, "미국 PPI": 2,
             "옵션 만기": 2, "미국 구인건수 JOLTS": 2, "미국 JOLTS": 2, "미국 실질임금": 3, "미국 생산성 지표": 3, "미국 생산성": 3, "미국 고용비용지수": 3}
GATE_SHORT = {"미국 고용보고서": "고용보고서", "미국 소비자물가 CPI": "CPI", "미국 생산자물가 PPI": "PPI", "선물·옵션 동시만기": "국장 동시만기",
              "옵션 만기": "국장 옵션 만기", "미국 구인건수 JOLTS": "JOLTS", "미국 실질임금": "실질임금"}


def pick_gates(gates: list[dict], n: int = 2) -> list[dict]:
    """다음 관문: 중요도(고용·CPI·FOMC) 우선, 같은 등급이면 가까운 순. 3등급(실질임금 등)은 다른 게 없을 때만."""
    g = sorted(gates, key=lambda x: (GATE_TIER.get(x["t"], 2), x["d"][:10]))
    top = [x for x in g if GATE_TIER.get(x["t"], 2) <= 1][:n] or g[:1]
    return sorted(top, key=lambda x: x["d"][:10])


GATE_WATCH = {"미국 고용보고서": "실업률", "미국 소비자물가 CPI": "근원 물가", "미국 CPI": "근원 물가", "FOMC": "점도표",
              "선물·옵션 동시만기": "장 막판 대형주 매물", "미국 생산자물가 PPI": "전월비", "미국 PPI": "전월비"}


def gate_watch(g: dict) -> str:
    w = GATE_WATCH.get(g["t"])
    return f", {w} 확인" if w else ""


def gate_spoken(g: dict) -> str:
    """'11일 CPI', '15일부터 16일 FOMC', '10일 국장 동시만기'"""
    dd, t = g["d"], GATE_SHORT.get(g["t"], g["t"])
    if "~" in dd:
        a, b = dd.split("~")
        return f"{int(a[8:10])}일부터 {int(b[-2:])}일 {t}"
    return f"{int(dd[8:10])}일 {t}"


# ── 스레드 본문(글로 읽는 하루) ──
def build_threads(c: dict) -> str:
    """500자 이내 산문. 지표 나열이 아니라 '오늘 이런 날이었다'로 읽히게 쓴다.
    순서: 결론 한 줄 → 수급에서 눈에 띈 것 → 돈이 간 곳 → 개인 → 내일 볼 것."""
    k, q = c["kospi"], c["kosdaq"]
    inv, moves = c.get("inv") or {}, c.get("moves") or []
    chg, close = k.get("chg_pct"), k.get("close")
    it = c.get("intraday") or {}
    streak = c.get("inv_streak") or {}
    d = datetime.strptime(c["date"], "%Y%m%d")
    P = []

    # 1) 결론 — 지수와 산 주체를 한 문장에
    three = [("개인", inv.get("indiv")), ("외국인", inv.get("foreign")), ("기관", inv.get("inst"))]
    buyers = [(n, v) for n, v in three if v is not None and v > 0]
    sellers = [(n, v) for n, v in three if v is not None and v < 0]
    move = f"{pct(chg)} {updown(chg, '올라', '내려')}" if chg is not None and abs(chg) >= 0.1 else "거의 제자리에서"
    head = f"{d.month}월 {d.day}일 국장. 코스피가 {move} {idx(close)}에 마감했습니다."
    if len(buyers) == 2 and {n for n, _ in buyers} == {"외국인", "기관"}:
        amts = [won(v) for _, v in buyers]
        head += f" 외국인과 기관이 나란히 {amts[0]}, {ro(amts[1])} 샀습니다." if amts[0] != amts[1] else f" 외국인과 기관이 나란히 {amts[0]}씩 샀습니다."
    elif buyers:
        head += " " + _and([f"{n} {won(v)}" for n, v in buyers]) + " 순매수였습니다."
    elif (inv.get("others") or 0) > 0:
        head += f" 셋 다 파는데 기타법인 혼자 {obj(won(inv['others']))} 받아냈습니다."
    P.append(head)

    # 2) 눈에 띈 것 — 장중→마감 반전 > 연속일/전환 > 프로그램
    line = ""
    turns = it.get("turns") or []
    if turns:
        t = turns[0]
        hm = it.get("at", "14:00"); hh = int(hm[:2])
        when = f"오후 {hh - 12}시" if hh > 12 else f"{hh}시"
        if t["kind"] == "flip":
            line = (f"눈에 띈 건 시간대였습니다. {when}까지 {josa(t['name'])} {won(abs(t['a']))} {'순매도' if t['a'] < 0 else '순매수'}였는데, "
                    f"마감엔 {won(abs(t['b']))} {'순매수' if t['b'] > 0 else '순매도'}로 돌아섰습니다.")
        elif t["kind"] == "more":
            line = (f"눈에 띈 건 시간대였습니다. {when}까지 {t['name']} 순매수는 {won(abs(t['a']))}뿐이었는데 마감엔 {won(abs(t['b']))}. "
                    f"막판에 몰려 들어왔습니다." if t["b"] > 0 else
                    f"눈에 띈 건 시간대였습니다. {t['name']} 순매도가 {when} {won(abs(t['a']))}에서 마감 {ro(won(abs(t['b'])))} 늘었습니다.")
        else:
            line = f"{t['name']} {'순매수' if t['b'] > 0 else '순매도'}는 {when} {won(abs(t['a']))}에서 마감 {ro(won(abs(t['b'])))} 줄었습니다."
    else:
        bits = []
        for name, key in (("외국인", "foreign"), ("기관", "inst")):
            st = streak.get(key) or {}
            n, back = st.get("streak") or 0, st.get("turned_after") or 0
            if back >= 3:
                bits.append(f"{josa(name)} {back}일 만에 방향을 바꿨고")
            elif abs(n) >= 3:
                bits.append(f"{josa(name)} {days_ko(abs(n))} 같은 방향입니다")
        if bits:
            line = " ".join(bits[:1]).rstrip("고") + "습니다." if len(bits) == 1 else bits[0].rstrip("고") + ", " + bits[1] + "."
    if line:
        P.append(line)

    # 3) 돈이 간 곳
    if moves:
        lead = max(moves, key=lambda m: m["t"]) if any(m["t"] > 0 for m in moves) else moves[0]
        out = [m for m in moves if m["t"] < 0 or m["state"] in ("이탈", "매도 확대")]
        s3 = ""
        if lead["t"] > 0:
            keep = f"{days_ko(lead['streak'])} 쌓이는 중이고, " if lead["state"].startswith("쌓임") and lead["streak"] >= 2 else ""
            s3 = f"돈은 {ro(lead['theme'])} 갔습니다. {keep}오늘 하루{'만' if keep else ''} {subj(won(lead['t']))}"
            f_, i_ = lead.get("foreign"), lead.get("inst")
            s3 += " 들어왔습니다. 외국인과 기관이 둘 다 샀습니다." if (f_ and i_ and f_ > 0 and i_ > 0) else " 들어왔습니다."
        if out:
            o = out[0]
            s3 += (" 반대로 " if s3 else "돈은 ") + (f"{o['theme']}에서는 순매수가 순매도로 돌아섰습니다." if o["state"] == "이탈"
                                                  else f"{o['theme']}에서는 {subj(won(abs(o['t'])))} 빠졌습니다.")
        if s3:
            P.append(s3)
    cb = c.get("callback")
    if cb and cb["check"]["kind"] == "theme_continue":
        th = cb["check"]["theme"]
        P.append(f"어제 보자고 한 {th}, 오늘도 이어졌습니다. 돈은 아직 여기 있습니다." if cb["ok"] else f"어제 보자고 한 {josa(th)} 오늘 끊겼습니다.")

    ev = c.get("event")
    if ev and (ev.get("stocks") or []):
        kind, top = event_pick(ev)
        if kind != "none":
            word = {"up": "올랐습니다", "down": "내렸습니다", "mixed": "엇갈렸습니다"}[kind]
            P.append(f"간밤 애플 {ev.get('spoken') or ev.get('label')} 발표. {ev.get('group') or '관련주'}는 " + ", ".join(f"{x['name']} {'+' if x['pct'] > 0 else '−' if x['pct'] < 0 else ''}{abs(x['pct']):.1f}%" for x in top) + f"로 {word}.")

    # 4) 개인
    ip = inv.get("indiv")
    if ip is not None and abs(ip) >= 5000:
        if ip < 0:
            P.append(f"개인은 {obj(won(ip))} 팔았습니다." + (" 지수가 오른 날 개인이 내놓는 그림입니다." if (chg or 0) > 0 else ""))
        else:
            P.append(f"개인은 {obj(won(ip))} 담았습니다." + (" 지수가 내린 날 개인이 받는 그림입니다." if (chg or 0) < 0 else ""))

    # 5) 내일 볼 것
    watch = c.get("watch") or []
    if watch:
        nxt = "다음 주" if d.weekday() >= 4 else "내일"
        P.append(f"{nxt}은 {watch[0]['q'].replace('이어지는지', '이어지는지가')} 관건입니다."
                 if "이어지는지" in watch[0]["q"] else f"{nxt} 볼 것은 {watch[0]['q']}입니다.")

    P.append(BONDING_SHORT)
    text = "\n\n".join(P)
    while len(text) > 430 and len(P) > 4:
        P.pop(-3)
        text = "\n\n".join(P)
    return text


# ── 미국편(아침) ──
def usd(v: float | None) -> str:
    return "미확정" if v is None else f"{v:,.0f}달러" if v >= 100 else f"{v:,.2f}달러"


def event_values_spoken(bv: dict | None) -> str:
    """BLS 실제값 → 한 문장."""
    if not bv or bv.get("stale") or not bv.get("values"):
        return ""
    v, what = bv["values"], bv["what"]
    m = int(bv["period"][5:])
    if what == "Employment Situation":
        bits = []
        if v.get("nfp_k") is not None:
            n = v["nfp_k"]
            man = f"{abs(n) // 10}만" + (f" {abs(n) % 10}천" if abs(n) % 10 else "") if abs(n) >= 10 else f"{abs(n)}천"
            bits.append(f"비농업 고용은 {man} 명 {'늘었' if n >= 0 else '줄었'}고")
        if v.get("unemp") is not None:
            bits.append(f"실업률은 {v['unemp']}%" + ("로 전달과 같았습니다" if v.get("unemp_prev") == v["unemp"] else f"로 전달 {v['unemp_prev']}%에서 {'올랐' if v['unemp'] > v['unemp_prev'] else '내렸'}습니다"))
        return f"{m}월 " + " ".join(bits) if bits else ""
    if what == "Consumer Price Index":
        bits = []
        if v.get("cpi_yy") is not None:
            bits.append(f"소비자물가는 전년 대비 {v['cpi_yy']}%")
        if v.get("cpi_mm") is not None:
            bits.append(f"전월 대비 {v['cpi_mm']}%")
        if v.get("core_mm") is not None:
            bits.append(f"근원 물가는 전월 대비 {v['core_mm']}%")
        return f"{m}월 " + ", ".join(bits) + "였습니다." if bits else ""
    if what == "Producer Price Index" and v.get("ppi_mm") is not None:
        return f"{m}월 생산자물가는 전월 대비 {v['ppi_mm']}%였습니다."
    if what == "Job Openings" and v.get("jolts_k") is not None:
        return f"{m}월 구인 건수는 {round(v['jolts_k'] / 10):,}만 건이었습니다."
    return ""


def build_us(c: dict) -> dict:
    """미국편 v4 — 인트로 훅(원인+결과) → 지수 고·저·종가 → 이벤트 결과·반응·배경·다음 관문 → 돈의 흐름(섹터·레버리지·종목) → 국장 연결·오늘 체크. 목표 80초."""
    brand = c.get("brand") or BRAND_DEFAULT
    sess = c["session_et"]
    ix = c.get("idx") or {}          # 공식 지수(야후): IXIC/GSPC/DJI/SOX/VIX
    etf = c.get("index") or {}       # ETF(키움): QQQ/SPY/DIA
    links = c.get("links") or {}
    secs = [v for v in (c.get("sectors") or {}).values() if v and not v.get("missing")]
    secs.sort(key=lambda x: -x["pct"])
    evs = c.get("events") or []
    stocks = sorted([x for x in (c.get("stocks") or []) if x and not x.get("missing")], key=lambda x: -abs(x["pct"]))
    bv = c.get("bls_values")

    def ok(e): return e and not e.get("missing") and e.get("pct") is not None
    def ud(v): return f"{pct(v)} {updown(v)}"

    nas = ix.get("IXIC") if ok(ix.get("IXIC")) else None
    nas_name = "나스닥" if nas else "나스닥100 QQQ"
    nas_src = nas or (etf.get("QQQ") if ok(etf.get("QQQ")) else None)

    # u0 인트로(≤10초) — 훅: 이벤트 뒤 결과. 원인 서술은 polish가 뉴스 근거로 채움.
    ev = evs[0] if evs else None
    night = "지난 금요일 밤" if c.get("weekend") else "간밤"
    if nas_src and ev:
        hook = f"{ev['what'].replace('미국 ', '', 1)} 뒤 {nas_name}은 {pct(nas_src['pct'])} {updown(nas_src['pct'], '올랐', '내렸')}습니다."
    elif nas_src and secs:
        top = secs[0]
        hook = f"{top['name']} {updown(top['pct'], '강세', '약세')} 속에 {nas_name}은 {pct(nas_src['pct'])} {updown(nas_src['pct'])} 마감했습니다."
    elif nas_src:
        hook = f"{nas_name}은 {pct(nas_src['pct'])} {updown(nas_src['pct'])} 마감했습니다."
    else:
        hook = "미국 주식 마감 정리입니다."
    headline = hook.replace(" 마감했습니다.", "").replace(" 올랐습니다.", " 상승").replace(" 내렸습니다.", " 하락").replace("은 ", " ").replace("는 ", " ")
    u0 = f"{brand}, {date_spoken(sess)} 미국 주식 마감입니다. {hook}"

    # u1 지수 — 고·저·종가만
    parts = []
    if nas:
        parts.append(f"나스닥은 고점 {idx(nas['high'])}, 저점 {obj(idx(nas['low']))} 거쳐 {idx(nas['close'])}에 마감했고,")
    elif ok(etf.get("QQQ")):
        qq = etf["QQQ"]
        parts.append(f"나스닥100 QQQ는 고점 {usd(qq['high'])}, 저점 {obj(usd(qq['low']))} 거쳐 {usd(qq['close'])}에 마감했고,")
    sp = ix.get("GSPC") if ok(ix.get("GSPC")) else etf.get("SPY")
    dj = ix.get("DJI") if ok(ix.get("DJI")) else etf.get("DIA")
    sox = ix.get("SOX") if ok(ix.get("SOX")) else links.get("SOXX")
    rest = []
    if ok(sp) and ok(dj) and (sp["pct"] > 0) == (dj["pct"] > 0):
        rest.append(f"S&P500과 다우는 각각 {pct(sp['pct'])}, {pct(dj['pct'])} {updown(sp['pct'], '올랐', '내렸')}습니다.")
    else:
        if ok(sp): rest.append(f"S&P500은 {ud(sp['pct'])},")
        if ok(dj): rest.append(f"다우는 {ud(dj['pct'])}입니다.")
    if ok(sox):
        rest.append(f"반도체지수는 {pct(sox['pct'])} {updown(sox['pct'], '올랐', '내렸')}습니다.")
    u1 = " ".join(parts + rest) if (parts or rest) else "미국 지수 데이터가 아직 확정되지 않았습니다."

    # u2 이벤트 → 결과 숫자 → 시장 반응 → 배경(뉴스, polish) → 다음 관문(조건부)
    parts = []
    gates = pick_gates((c.get("schedule_us") or []) + (c.get("schedule_kr") or []), 2)
    if ev:
        parts.append(f"{night} 주요 일정은 {ev['what'].replace('미국 ', '', 1)}였습니다.")
        vs = event_values_spoken(bv)
        if vs:
            parts.append(vs if vs.endswith(".") else vs + ".")
        if ev.get("react30") is not None and ev.get("react_close") is not None:
            r30, rc = ev["react30"], ev["react_close"]
            if (r30 > 0) != (rc > 0) and abs(rc) >= 0.3:
                parts.append(f"발표 직후 30분은 {pct(r30)} {updown(r30, '올랐', '내렸')}지만 마감까지 {'되밀렸' if r30 > 0 else '되돌렸'}습니다.")
            else:
                parts.append(f"발표 직후 30분 동안 {nas_name if nas else '나스닥'}은 {pct(r30)} {updown(r30, '올랐', '내렸')}고, 마감까지 그 방향이 이어졌습니다.")
        parts.append(c.get("reason_fallback_us") or "")
    else:
        parts.append(f"{night}에는 예정된 주요 지표가 없었습니다.")
        parts.append(c.get("reason_fallback_us") or "")
    if gates:
        parts.append(("이번 주 관문은 " if c.get("weekend") else "다음 관문은 ") + _and([gate_spoken(g) + gate_watch(g) for g in gates]) + "입니다.")
        g0 = min(gates, key=lambda g: GATE_TIER.get(g["t"], 2))["t"]
        if "CPI" in g0 or "PPI" in g0:
            parts.append("물가까지 강하게 나오면 금리 부담이 이어질 수 있습니다." if (nas_src and nas_src["pct"] < 0) else "물가가 강하게 나오면 금리 부담이 다시 커질 수 있습니다.")
        elif "고용" in g0:
            parts.append("고용이 강하면 금리 부담이, 약하면 경기 걱정이 앞설 수 있습니다.")
        elif "FOMC" in g0:
            parts.append("금리 결정과 점도표 방향에 따라 흐름이 갈릴 수 있습니다.")
        elif "만기" in g0:
            parts.append("만기 전후로 프로그램 매물이 출렁일 수 있어 수급을 다시 확인해야 할 수 있습니다.")
    tre = c.get("tre") or {}
    bp = tre.get("chg_bp")
    if tre.get("y10") is not None and bp is not None and abs(bp) >= 5:
        parts.append(f"미국 10년물 금리는 {abs(bp)}bp {'내린' if bp < 0 else '오른'} {tre['y10']:.2f}%입니다.")
    u2 = " ".join(p for p in parts if p)

    # u3 돈의 흐름 — 섹터(들어온 곳·빠진 곳·머무는 곳) + 레버리지 ETF + 종목
    if secs:
        top, bot = secs[0], secs[-1]
        hot_tag = f" 거래대금이 평소의 {top['value_ratio20']:.1f}배였습니다." if (top.get("value_ratio20") or 0) >= 1.3 else " 가장 강했습니다."
        stay_tag = f" {days_ko(top['streak'])} 오름세입니다." if (top.get("streak") or 0) >= 5 else ""
        u3 = f"미국 주식시장에서 돈은 {ro(top['name'])} 몰렸습니다. {top['name']} ETF는 {pct(top['pct'])} {updown(top['pct'], '오르며', '내리며')}{hot_tag}{stay_tag}"
        cold = [x["name"] for x in secs[-2:] if x["pct"] < 0][::-1]
        if cold:
            u3 += f" 반대로 {_and(cold)}에서는 돈이 빠져나갔습니다."
        lev = [links.get(s) for s in ("SOXL", "TQQQ") if ok(links.get(s))]
        lev_hot = [x for x in lev if (x.get("value_ratio20") or 0) >= 1.3]
        if lev_hot:
            u3 += f" 레버리지 {_and([x['name'] for x in lev_hot])} 거래대금도 평소의 {max(x['value_ratio20'] for x in lev_hot):.1f}배로 늘었습니다."
        u3_title = f"{ro(top['name'])} 몰렸다" if (top.get("value_ratio20") or 0) >= 1.3 else f"{top['name']} 강세, {bot['name']} 약세"
    else:
        u3, u3_title = "섹터 데이터는 확정 뒤 전해드리겠습니다.", "섹터 대기"
    movers = c.get("movers") or []
    if movers:
        ups = [x for x in movers if x["pct"] > 0]; downs = [x for x in movers if x["pct"] < 0]
        if ups and downs:
            u3 += f" 종목 중엔 {ups[0]['name']} {pct(ups[0]['pct'])} 상승, {downs[0]['name']} {pct(downs[0]['pct'])} 하락이 컸습니다."
        elif ups:
            u3 += f" 종목 중엔 {subj(ups[0]['name'])} {pct(ups[0]['pct'])}" + (f", {subj(ups[1]['name'])} {pct(ups[1]['pct'])} 올랐습니다." if len(ups) > 1 else " 올랐습니다.")
        else:
            u3 += f" 종목 중엔 {subj(downs[0]['name'])} {pct(downs[0]['pct'])}" + (f", {subj(downs[1]['name'])} {pct(downs[1]['pct'])} 내렸습니다." if len(downs) > 1 else " 내렸습니다.")

    # u4 국장 연결 + 오늘 체크 + 어시스트 (+ 주말이면 이번 주 관문)
    parts = []
    ewy = links.get("EWY")
    link_bits = []
    pf = c.get("prev_foreign")
    if pf and pf.get("foreign") is not None:
        link_bits.append(f"{'지난 금요일' if c.get('weekend') else '전날'} 국장 외국인은 {won(pf['foreign'])} {'순매수' if pf['foreign'] > 0 else '순매도'}")
    fx = c.get("fx")
    if fx and fx.get("chg") is not None and abs(fx["chg"]) >= FX_MIN_MOVE * 3:
        link_bits.append(f"환율은 {abs(fx['chg']):.1f}원 {'내린' if fx['chg'] < 0 else '오른'} {fx['close']:,.1f}원")
    if link_bits:
        parts.append("국장 연결로 보면 " + ", ".join(link_bits) + ("입니다." if link_bits[-1].startswith("환율") or not any("순매" in b for b in link_bits) else "였습니다."))
    watch = c.get("watch") or []
    if watch:
        parts.append(f"오늘 국장에서 체크할 것은 {watch[0]['q']}입니다. {watch[0].get('assist') or assist_for('us_link')}")
    u4 = " ".join(parts)

    u5 = f"{brand_was(brand)} 국장 마감은 저녁에 이어집니다."

    return {"brand": brand, "tagline": TAGLINE, "u3_title": u3_title, "headline": headline, "hook": hook,
            "scenes": [{"id": "u0", "min": 4.0, "tts": u0, "sub": ""},
                       {"id": "u1", "min": 6.0, "tts": u1, "sub": u1},
                       {"id": "u2", "min": 10.0, "tts": u2, "sub": u2},
                       {"id": "u3", "min": 10.0, "tts": u3, "sub": u3},
                       {"id": "u4", "min": 8.0, "tts": u4, "sub": u4},
                       {"id": "u5", "min": 3.0, "tts": u5, "sub": ""}]}
