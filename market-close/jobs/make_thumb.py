"""썸네일 전용 생성기 — 영상 프레임을 잘라 쓰지 않고 따로 만든다.

이유(JJ 2026-09-13): 영상 화면에는 로고·날짜·하단 고지·데이터 카드가 자리를 먹어 글자를 더 못 키운다.
썸네일은 피드 그리드에서 손톱만 하게 보이므로 남길 건 **큰 글자 2~3줄**뿐이다.

대본 파일: data/<날짜>/thumbs.json  — 후보를 여러 개 두고 골라 쓴다.
  {"out": "out/20260913/notice",
   "cands": {
     "A": {"bg": "city", "tone": "neutral", "badge": "내일 9월 14일",
           "lines": [{"t": "밤 8시까지", "color": "yellow"}, {"t": "주식 거래"}],
           "sub": "그런데 종가는 3시 반?"},
     "B": {...}
   }}

lines[].color: yellow | white | red | blue | green | grey       lines[].size: 1.0 기준 배율
bg: city | market | chip | us_fed        tone: up | down | neutral

실행:
  python make_thumb.py 20260913            thumbs.json의 후보 전부 렌더
  python make_thumb.py 20260913 --only=A   하나만
결과: <out>/thumb_<키>.jpg
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDER = ROOT / "render"
NPX = "npx.cmd" if sys.platform == "win32" else "npx"


def render_one(key: str, spec: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    props = RENDER / f"thumb_props_{key}.json"
    props.write_text(json.dumps({"thumb": spec, "date_label": "", "brand": "누가샀나",
                                 "kospi": {"close": None, "chg_pct": None}, "scenes": []},
                                ensure_ascii=False), encoding="utf-8")
    dst = out_dir / f"thumb_{key}.jpg"
    cmd = [NPX, "remotion", "still", "src/index.ts", "Thumb", str(dst),
           f"--props={props}", "--image-format=jpeg", "--jpeg-quality=92", "--log=error"]
    r = subprocess.run(cmd, cwd=str(RENDER), capture_output=True, text=True, encoding="utf-8", errors="replace")
    props.unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit(f"{key} 렌더 실패 rc={r.returncode}\n{r.stdout[-1200:]}\n{r.stderr[-1800:]}")
    print(f"  {key} → {dst} ({dst.stat().st_size // 1024}KB)")
    return dst


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), None)
    d = args[0]
    spec_path = ROOT / "data" / d / "thumbs.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir = ROOT / spec["out"] if not Path(spec["out"]).is_absolute() else Path(spec["out"])
    for key, cand in (spec.get("cands") or {}).items():
        if only and key != only:
            continue
        render_one(key, cand, out_dir)


if __name__ == "__main__":
    main()
