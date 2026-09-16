"""썸네일 자동 생성 — 그날 '가장 크게 움직인 주체'와 '지수'를 맞붙인다.

왜(JJ 2026-09-16 저녁): 제목과 썸네일이 서로 다른 궁금증을 만들면 안 된다.
제목이 "외국인 1.7조 팔았는데 코스피는 왜 올랐을까?"인데 썸네일이 "오후 2시 1,800억 → 마감 1.68조"이면,
제목은 '시장이 왜 올랐나'를 묻고 썸네일은 '외국인이 왜 갑자기 팔았나'를 묻는다. 궁금증이 둘로 쪼개진다.
그래서 **썸네일 = 부딪히는 사실 하나, 제목 = 그 사실에 대한 질문**으로 역할을 나눈다.

  외국인            (작게)
  −1.7조            (크게, 노랑)
  그런데 코스피      (작게)
  +1.37%            (크게, 오르면 빨강 내리면 파랑)
  누가 받았나?       (sub)

주체는 **지수와 반대로 간 쪽 중 금액이 가장 큰 쪽**을 고른다(= 모순이 가장 센 자리).
반대로 간 쪽이 없으면 금액이 가장 큰 쪽을 쓰고 '그런데'를 뺀다.

규칙(기억 [[thumbnail-rule]]): 큰 숫자 두 개, 표·고지 카드 금지, 지저분하면 안 누른다
(JJ 2026-09-14: "저렇게 지저분하게 만들면 누가 누르겠냐"). 그래서 글로우 하나 + 네 줄뿐이다.

쓰기(market-close/jobs 에서):
  python make_thumb_auto.py 20260916            data/D/thumbs.json 을 만들고 out/D/kr/thumb_A.jpg 까지
  python make_thumb_auto.py 20260916 --spec     대본만(그리지 않음)
run_day 의 review 단계가 매일 부른다. 실패해도 예외를 밖으로 내지 않는다(영상 제작을 막지 않는다).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _common import DATA, OUT, load_json, log, save_json

ROOT = Path(__file__).resolve().parent.parent
# 2줄에 쓸 잇는 말 — 1줄이 유출(−)이냐 유입(+)이냐로 고른다
MID_OUT = ("빠졌는데", "나갔는데", "던졌는데")
MID_IN = ("들어왔는데", "샀는데", "받았는데")


def _kw(label: str) -> str:
    """라벨에서 첫 낱말만 — 썸네일은 글자 수가 곧 크기다. '반도체 외국인·기관' → '반도체'."""
    for w in ("순매도", "순매수", "누적", "합계", "등락", "지수"):
        label = label.replace(w, " ")
    parts = [x for x in label.split() if x]
    return parts[0] if parts else ""


def _money(eok: int) -> str:
    """억 단위 정수 → 썸네일용 짧은 글자. 1조 넘으면 조로, 아니면 억으로."""
    a = abs(int(eok))
    if a >= 10000:
        t = f"{a / 10000:.1f}"
        return (t[:-2] if t.endswith(".0") else t) + "조"
    return f"{a:,}억"


def _pick_actor(c: dict) -> tuple[str, int] | None:
    """지수와 반대로 간 주체 중 금액이 가장 큰 쪽. 없으면 금액이 가장 큰 쪽."""
    bars = ((c.get("investors") or {}).get("bars")) or []
    bars = [b for b in bars if isinstance(b.get("v"), (int, float)) and b.get("name")]
    if not bars:
        return None
    idx = (c.get("kospi") or {}).get("chg_pct") or 0
    against = [b for b in bars if (b["v"] < 0) == (idx > 0) and b["v"] != 0]
    b = max(against or bars, key=lambda x: abs(x["v"]))
    return b["name"], int(b["v"])


def spec(d: str) -> dict | None:
    """computed_kr.json 의 주체 수급 + 지수 등락으로 썸네일 네 줄을 만든다.
    한 줄이 길면 화면에서 접혀 지저분해진다 — 라벨은 짧게, 숫자는 부호까지만."""
    c = load_json(DATA / d / "computed_kr.json")
    if not c:
        return None
    actor = _pick_actor(c)
    pct = (c.get("kospi") or {}).get("chg_pct")
    if not actor or pct is None:
        return _spec_hook(c, d)                                 # 수급이 없는 날은 옛 훅 방식으로
    name, v = actor
    idx_up = pct > 0
    clash = (v < 0) == idx_up                                   # 주체와 지수가 반대로 갔나
    sign = "−" if v < 0 else "+"
    lines = [
        {"t": name, "size": 0.58},
        {"t": f"{sign}{_money(v)}", "size": 1.52, "color": "yellow"},
        {"t": ("그런데 코스피" if clash else "코스피"), "size": 0.58, "gap": 46},
        {"t": f"{'+' if idx_up else '−'}{abs(pct):.2f}%", "size": 1.34, "color": ("red" if idx_up else "blue")},
    ]
    sub = "누가 받았나?" if v < 0 else "누가 판 걸까?"
    return {"out": f"out/{d}/kr",
            "cands": {"A": {"bg": "city", "tone": "up" if idx_up else "down", "dim": 0.45,
                            "objects": [{"k": "glow", "x": 540, "y": 700, "r": 620, "color": "yellow", "a": 0.18}],
                            "lines": lines, "sub": sub, "logo": True}}}


def _spec_hook(c: dict, d: str) -> dict | None:
    """대비(대체) — 수급이 비어 훅(s0)의 두 숫자밖에 없는 날."""
    h = ((c.get("hunter") or {}).get("s0")) or {}
    a, b = h.get("a") or {}, h.get("b") or {}
    if not a.get("value") or not b.get("value"):
        return None
    k1, k2 = _kw(a.get("label") or ""), _kw(b.get("label") or "")
    an = a.get("num")
    day = int(d[6:8]) if d[:8].isdigit() else 1
    line1 = f"{k1} {a['value']}".strip()
    mid = (MID_OUT if (isinstance(an, (int, float)) and an < 0) else MID_IN)[day % 3]
    v2 = str(b["value"]).lstrip("+")
    if "%" in v2:
        line3 = f"{v2.lstrip('−-')}만 {'내렸다' if v2.startswith(('−', '-')) else '올랐다'}?!"
    elif k2 and k2 != k1:
        line3 = f"{k2} {v2}?!"
    else:
        line3 = f"{v2}뿐?!"
    tone = "down" if (c.get("kospi") or {}).get("chg_pct", 0) < 0 else "up"
    return {"out": f"out/{d}/kr",
            "cands": {"A": {"bg": "city", "tone": tone, "dim": 0.45,
                            "objects": [{"k": "glow", "x": 540, "y": 640, "r": 620, "color": "yellow", "a": 0.18}],
                            "lines": [{"t": line1[:12], "size": 1.08, "color": "yellow"},
                                      {"t": mid, "size": 0.9},
                                      {"t": line3[:13], "size": 0.9}],
                            "logo": True}}}


def main(d: str, draw: bool = True) -> Path | None:
    try:
        s = spec(d)
        if not s:
            log(d, "thumb", "훅 숫자가 없어 썸네일을 건너뛴다")
            return None
        p = DATA / d / "thumbs.json"
        save_json(p, s)
        a = s["cands"]["A"]
        lines = " / ".join([x["t"] for x in a["lines"]] + ([a["sub"]] if a.get("sub") else []))
        log(d, "thumb", f"대본: {lines}")
        if not draw:
            return p
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("make_thumb.py")), d, "--only=A"],
                           cwd=str(Path(__file__).parent), capture_output=True, text=True, encoding="utf-8", timeout=180)
        out = ROOT / "out" / d / "kr" / "thumb_A.jpg"
        if out.exists():
            log(d, "thumb", f"{out} ({out.stat().st_size // 1024}KB)")
            return out
        log(d, "thumb", f"그리기 실패: {(r.stderr or r.stdout or '')[-200:]}")
    except Exception as e:                                    # 썸네일 때문에 그날 영상이 안 나가면 안 된다
        log(d, "thumb", f"실패({type(e).__name__}): {e}")
    return None


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "", draw="--spec" not in sys.argv)
