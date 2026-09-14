"""주말 두 편이 '월요일 국장'과 연결해 한 말을 가져와, 월요일 평일편에서 회수한다.

왜(JJ 2026-09-14): "금요일 영상에서 우리가 월요일에 봐야 할 점 다시 각인하고 어떻게 되었는지
말해줘야 해. 그리고 일요일과 토요일에도 월요일 국장과 연관된 언급들 다시 해주고 어떻게
되었는지 말해줘야 해."

금요일 평일편의 약속은 이미 ledger.py 가 기록·검증한다(callback). 여기서 채우는 건 주말 두 편이다.
주말편은 약속을 구조화해 저장하지 않아서(2026-09-14 기준 script.json 의 마지막 장면 대사에만 있다)
대사에서 뽑는다. 앞으로 narrate_weekly / narrate_us_weekly 가 watch 를 따로 저장하면 그걸 먼저 쓴다.

토요일 국장 주간(w6) 예: "그래서 다음 주에 볼 건 하나입니다. 외국인 순매도가 4일째 이어지는지."
일요일 미장 주간(uw6) 예: "월요일 국장에서 먼저 볼 곳은 반도체 외국인 수급입니다."
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from _common import DATA, load_json

# 토요일편에서 '다음 주에 볼 건' 다음에 오는 한 문장
_SAT_LEAD = re.compile(r"(?:다음\s*주|월요일)에?\s*볼\s*(?:건|것|곳)[^.]*\.\s*([^.?]+[.?])")
_SAT_ALT = re.compile(r"([^.?]*(?:이어지는지|들어오는지|멈추는지|돌아서는지)[^.?]*)[.?]")
# 일요일 미장편의 '월요일 국장에서 먼저 볼 곳은 …입니다'
_SUN = re.compile(r"월요일\s*국장에서\s*(?:먼저\s*)?볼\s*(?:곳|것)은\s*([^.]+?)입니다")
_SUN_ALT = re.compile(r"월요일\s*국장[^.]*?([가-힣A-Za-z0-9· ]{2,20}?)\s*(?:수급|흐름)")


def _sentences(t: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", (t or "").strip()) if x.strip()]


def _scene(script: dict | None, sid: str) -> str:
    for s in (script or {}).get("scenes") or []:
        if s.get("id") == sid:
            return s.get("tts") or ""
    return ""


def _back_to(d: str, weekday: int) -> str:
    """d 직전(포함하지 않음)의 해당 요일 날짜. weekday: 월=0 … 토=5, 일=6."""
    cur = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    for _ in range(8):
        if cur.weekday() == weekday:
            return cur.strftime("%Y%m%d")
        cur -= timedelta(days=1)
    return ""


def _pick(script: dict | None, sid: str, pats: tuple[re.Pattern, ...]) -> str:
    if not script:
        return ""
    w = script.get("watch")                      # 앞으로 주말편이 구조화해 남기면 그걸 쓴다
    if isinstance(w, list) and w and isinstance(w[0], dict) and w[0].get("q"):
        return str(w[0]["q"]).strip().rstrip(".")
    txt = _scene(script, sid)
    for pat in pats:
        m = pat.search(txt)
        if m:
            return m.group(1).strip().rstrip(".")
    return ""


def collect(d: str) -> list[dict]:
    """월요일이면 [{src, sid, q}] — 토·일 편이 월요일 국장을 두고 한 말. 월요일이 아니면 빈 목록."""
    if datetime.strptime(d, "%Y%m%d").weekday() != 0:
        return []
    sat, sun = _back_to(d, 5), _back_to(d, 6)
    out = []
    q = _pick(load_json(DATA / "weekly" / sat / "script.json"), "w6", (_SAT_LEAD, _SAT_ALT))
    if q:
        out.append({"src": "토요일 주간 결산", "sid": "w6", "date": sat, "q": q})
    q = _pick(load_json(DATA / "weekly_us" / sun / "script.json"), "uw6", (_SUN, _SUN_ALT))
    if q:
        out.append({"src": "일요일 미국 주간 결산", "sid": "uw6", "date": sun, "q": q})
    return out


# ── 오늘 데이터로 답하기 ──
_INV = {"외국인": "foreign", "기관": "inst", "개인": "indiv"}


def _kospi_inv(comp: dict) -> dict:
    """코스피 투자자 수급. compute 는 평평한 dict 를 'inv' 로 넘기고,
    저장된 computed_kr.json 은 'investors' 밑에 kospi/kosdaq 으로 중첩돼 있다 — 둘 다 받는다."""
    inv = comp.get("inv") or comp.get("investors") or {}
    if not isinstance(inv, dict):
        return {}
    k = inv.get("kospi")
    return k if isinstance(k, dict) else inv


def answer(q: str, comp: dict) -> str:
    """약속 한 줄을 오늘 수급으로 답한다. 답할 수 없으면 빈 문자열(그러면 답하는 척하지 않는다)."""
    from narrate import obj, subj, won

    # ① '외국인 순매도가 4일째 이어지는지' 꼴 — 투자자 주체의 방향
    m = re.search(r"(외국인|기관|개인)\s*(순매도|순매수)", q)
    k = _kospi_inv(comp)
    if m and k:
        who, word = m.group(1), m.group(2)
        v = k.get(_INV[who])
        if v is not None:
            went = (v < 0) if word == "순매도" else (v > 0)
            amt = obj(won(abs(v)))
            return (f"{who}은 오늘도 {amt} {word}하며 이어졌습니다." if went
                    else f"{word}는 오늘 끊겼습니다. 오히려 {who}이 {obj(won(abs(v)))} "
                         f"{'순매수' if word == '순매도' else '순매도'}했습니다.")

    # ② '반도체 외국인 수급' 꼴 — 업종 이름이 들어간 경우. 외국인을 물었으면 외국인 수치로 답한다
    for mv in comp.get("moves") or []:
        th = mv.get("theme") or ""
        if not th or th not in q:
            continue
        if "외국인" in q and mv.get("foreign") is not None:
            v = mv["foreign"]
            return (f"{th}에선 외국인이 {obj(won(abs(v)))} 팔았습니다." if v < 0
                    else f"{th}엔 외국인 돈이 {subj(won(v))} 들어왔습니다.")
        if "기관" in q and mv.get("inst") is not None:
            v = mv["inst"]
            return (f"{th}에선 기관이 {obj(won(abs(v)))} 팔았습니다." if v < 0
                    else f"{th}엔 기관 돈이 {subj(won(v))} 들어왔습니다.")
        if mv.get("t") is not None:
            v = mv["t"]
            return (f"{th}에선 {subj(won(abs(v)))} 빠졌습니다." if v < 0
                    else f"{th}엔 {subj(won(v))} 들어왔습니다.")
    return ""


def _same(a: str, b: str) -> bool:
    """'외국인 순매도가 4일째 이어지는지' 와 '외국인 순매도가 나흘째 이어지는지' 를 같은 약속으로 본다."""
    NUM = {"이틀": "2", "사흘": "3", "나흘": "4", "닷새": "5", "엿새": "6", "일주일": "7",
           "둘째": "2", "셋째": "3", "넷째": "4"}
    def norm(x: str) -> str:
        x = re.sub(r"\s+", "", x or "")
        for ko, n in NUM.items():
            x = x.replace(ko, n)
        return re.sub(r"[일째번]", "", x)
    return bool(a and b) and norm(a) == norm(b)


def block(d: str, comp: dict, done_q: str = "") -> tuple[str, list[dict]]:
    """월요일 회수 블록 한 덩어리와 화면용 목록.

    done_q 는 평일 ledger 가 이미 회수한 약속(금요일 편). 주말편이 같은 말을 했으면
    답을 두 번 읽지 않고 '금요일·토요일 둘 다 짚었다'로 합친다."""
    items = collect(d)
    if not items:
        return "", []
    said, rows = [], []
    for it in items:
        if done_q and _same(it["q"], done_q):
            rows.append({**it, "a": "", "merged": True})
            said.append(f"{it['src']}에서도 같은 걸 짚었습니다.")
            continue
        a = answer(it["q"], comp)
        rows.append({**it, "a": a, "merged": False})
        said.append(f"{it['src']}에선 {obj_q(it['q'])} 보라고 했죠. {a}".strip()
                    if a else f"{it['src']}에선 {obj_q(it['q'])} 보라고 했습니다.")
    return " ".join(said), rows


def obj_q(q: str) -> str:
    """'반도체 외국인 수급' → '반도체 외국인 수급을', '…이어지는지' → 그대로."""
    q = (q or "").strip().rstrip(".")
    if q.endswith(("는지", "을지", "ㄹ지")):
        return q + "를"
    last = q[-1] if q else ""
    if "가" <= last <= "힣":
        return q + ("을" if (ord(last) - 0xAC00) % 28 else "를")
    return q + "를"
