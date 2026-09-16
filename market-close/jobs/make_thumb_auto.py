"""썸네일 자동 생성 — 그날 훅의 두 숫자로 큰 글자 세 줄을 만든다.

왜(JJ 2026-09-16): 이번 주는 JJ가 직접 올린다. 영상·제목·설명·태그만 있고 썸네일이 없으면
올릴 때마다 손이 한 번 더 간다. 훅(s0)이 이미 부딪히는 숫자 둘을 들고 있으니 그걸로 만든다.

규칙(기억 [[thumbnail-rule]]): 큰 글자 2~3줄 질문, 표·고지 카드 금지, 지저분하면 안 누른다
(JJ 2026-09-14: "저렇게 지저분하게 만들면 누가 누르겠냐"). 그래서 글로우 하나 + 세 줄만 둔다.

  1줄 숫자 A(노랑)  ·  2줄 잇는 말  ·  3줄 숫자 B + ?!

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


def spec(d: str) -> dict | None:
    """computed_kr.json 의 훅(s0)에서 썸네일 세 줄을 만든다. 훅이 없으면 None.
    한 줄 11자를 넘기면 화면에서 두 줄로 접혀 지저분해진다 — 그래서 라벨은 첫 낱말만 쓴다."""
    c = load_json(DATA / d / "computed_kr.json")
    if not c:
        return None
    h = ((c.get("hunter") or {}).get("s0")) or {}
    a, b = h.get("a") or {}, h.get("b") or {}
    if not a.get("value") or not b.get("value"):
        return None
    k1, k2 = _kw(a.get("label") or ""), _kw(b.get("label") or "")
    an = a.get("num")
    day = int(d[6:8]) if d[:8].isdigit() else 1                 # 접미사 날짜(20260915_b1)도 받는다
    line1 = f"{k1} {a['value']}".strip()
    mid = (MID_OUT if (isinstance(an, (int, float)) and an < 0) else MID_IN)[day % 3]
    v2 = str(b["value"]).lstrip("+")
    if "%" in v2:                                              # 지수·등락이면 '0.2%만 내렸다?!'
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
        lines = " / ".join(x["t"] for x in s["cands"]["A"]["lines"])
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
