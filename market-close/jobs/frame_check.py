"""완성 영상 마지막 점검 — **문장마다 한 장씩** 프레임을 뽑아 말과 화면을 대조한다.

JJ 2026-09-23: *"항상 영상이 완성될 때 음성과 화면이 일치하는지, 화면 안에서 다른 카드가 글씨나 다른 카드를
침범하지 않는지는 마지막 단계에서 니가 직접 영상을 돌려보면서 확인한 후 업로드해라."*

몇 초만 찍어 보면 9/22 처럼 어긋난 구간을 통째로 놓친다. 그래서 **문장 경계마다** 뽑는다
(문장 시작 +0.6초 = 그 문장의 화면 조각이 다 뜬 시점).

실행(jobs/):
    python frame_check.py 20260923            국장 마감(kr)
    python frame_check.py 20260923 --ed=info2 정보형 둘째 편
    python frame_check.py 20260923 --sheet=6  한 장에 6컷(기본 5)

만드는 것 — out/<날짜>/<ed>/framecheck/
    sheet_0.jpg … : 문장별 프레임 + 그 문장 자막(위에 적어 준다)
    index.txt     : 컷 번호 ↔ 장면·단계·시각·문장

보는 법(이 순서로 한 장씩):
    1) 자막 문장이 말하는 숫자·이름이 그 화면에 있나
    2) 아직 말하지 않은 것이 먼저 떠 있지 않나
    3) 카드가 다른 카드나 글자를 덮고 있지 않나
    4) 앞 컷과 화면이 똑같은데 3초 넘게 흘렀나(= 그 문장엔 화면 조각이 없다)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MC = Path(__file__).resolve().parent.parent
FFMPEG = MC / "render" / "node_modules" / "@remotion" / "compositor-win32-x64-msvc" / "ffmpeg.exe"
LEAD = 0.6          # 문장 시작 뒤 이만큼 — 그 문장에 붙은 조각이 다 뜬 시점
W, H = 430, 764     # 컷 한 장 크기(세로 9:16)
CAP = 46            # 자막 줄 높이
FONT = next((p for p in (Path(r"C:/Windows/Fonts/malgunbd.ttf"), Path(r"C:/Windows/Fonts/malgun.ttf")) if p.exists()), None)


def _f(size: int):
    try:
        return ImageFont.truetype(str(FONT), size) if FONT else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def cuts(comp: dict) -> list[dict]:
    out = []
    for s in comp.get("scenes") or []:
        st = s.get("steps") or []
        for i, c in enumerate(s.get("bounds") or s.get("cues") or []):
            out.append({"id": s["id"], "step": st[i] if i < len(st) else "?",
                        "t": round(s["start"] + c["start"] + LEAD, 2), "text": (c.get("text") or "").strip()})
    return out


def run(d: str, ed: str = "kr", per_sheet: int = 5) -> Path:
    od = MC / "out" / d / ed
    comp_p = MC / "data" / d / (f"computed_{ed}.json" if ed != "kr" else "computed_kr.json")
    comp = json.loads(comp_p.read_text(encoding="utf-8"))
    vid = od / "video.mp4"
    if not vid.exists():
        raise SystemExit(f"{vid} 없음 — 렌더 먼저")
    out = od / "framecheck"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.*"):
        f.unlink()

    cs = cuts(comp)
    for k, c in enumerate(cs):
        subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-ss", str(c["t"]),
                        "-i", str(vid), "-frames:v", "1", str(out / f"_{k:03d}.png"), "-y"], check=True)

    sheets = []
    for n in range(0, len(cs), per_sheet):
        grp = cs[n: n + per_sheet]
        sh = Image.new("RGB", (W * len(grp), H + CAP * 2 + 8), "#0A0A0A")
        d2 = ImageDraw.Draw(sh)
        f_id, f_tx = _f(17), _f(19)
        for i, c in enumerate(grp):
            im = Image.open(out / f"_{n + i:03d}.png").resize((W, H))
            sh.paste(im, (i * W, CAP * 2 + 8))
            d2.text((i * W + 8, 6), f"#{n+i}  {c['id']}.{c['step']}  {c['t']:.1f}s", fill="#FFD43B", font=f_id)
            t = c["text"]
            d2.text((i * W + 8, 30), t[:24], fill="#FFFFFF", font=f_tx)
            if len(t) > 24:
                d2.text((i * W + 8, 56), t[24:48], fill="#FFFFFF", font=f_tx)
        p = out / f"sheet_{n // per_sheet}.jpg"
        sh.save(p, quality=88)
        sheets.append(p)
    for f in out.glob("_*.png"):
        f.unlink()

    (out / "index.txt").write_text(
        "\n".join(f"#{k:3d}  {c['id']:4s}.{c['step']:14s} {c['t']:6.1f}s  {c['text']}" for k, c in enumerate(cs)),
        encoding="utf-8")
    print(f"컷 {len(cs)}장 · 시트 {len(sheets)}장 → {out}")
    for p in sheets:
        print("  ", p)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ed = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--ed=")), "kr")
    ps = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--sheet=")), "5"))
    run(args[0], ed, ps)
