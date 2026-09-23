"""주사위 탐정이 언제 어디에 나올지 정한다 — 정보형 전용. 실행(jobs/): python mascot_beats.py 20260924 (둘째 편은 --n=2)

JJ 2026-09-20 결정:
- 캐릭터는 **v3 정장**(모자·트렌치코트·돋보기·손전등 없음). 컷은 render/public/mascot/v3/*.png.
  → beats 의 pose 에 "v3/" 를 붙여 적는다(MascotLayer 가 mascot/<pose>.png 로 읽는다).
- **첫 장면(훅)에는 안 나온다** — "캐릭터가 뜬금없이 등장".
- 질문 글자가 다 뜬 **0.5초 뒤** 들어온다. 남은 시간이 1.0초 미만이면 건너뛴다.
- 가운데로, 크게, 아래를 잘라 상반신만(clip). 질문 글자(top 600~880) 아래, 자막 상자(top ~1510) 위.
"""
from __future__ import annotations

import json
import pathlib
import sys

from PIL import Image

MC = pathlib.Path(__file__).resolve().parent.parent
CUTS = MC / "render" / "public" / "mascot" / "v3"
POSES = ["tablet_think", "point_surprise", "arms_suspect", "phone_close"]   # 손전운(light_search)은 JJ가 뺐다
END_POSE = "thumbs_found"
TOP, BOTTOM = 900, 1500


def build(d: str, n: int = 1) -> list[dict]:
    ed = "info" if n <= 1 else f"info{n}"          # 하루에 두 편 이상이면 info2_script.json (build_info.ed_of 와 같은 이름)
    comp = json.loads((MC / "data" / d / f"computed_{ed}.json").read_text(encoding="utf-8"))
    sp = MC / "data" / d / f"{ed}_script.json"
    spec = json.loads(sp.read_text(encoding="utf-8"))
    cards = (spec.get("info") or {}).get("cards", {})

    ratio = {}
    for n in set(POSES + [END_POSE]):
        with Image.open(CUTS / f"{n}.png") as im:
            ratio[n] = im.size[0] / im.size[1]

    beats, qi = [], 0
    first = comp["scenes"][0]["id"]
    for s in comp["scenes"]:
        if s["id"] == "iz" or s["id"] == first:       # 끝 화면은 따로, 훅은 사건과 질문만
            continue
        q = (cards.get(s["id"]) or {}).get("q")
        if not q:
            continue
        at, cues = q[0].get("at"), s.get("cues") or []
        if at is None or at >= len(cues):
            continue
        start = s["start"] + cues[at]["start"] + 0.5
        end = s["start"] + s["frames"] / 30 - 0.2
        if end - start < 1.0:
            continue
        pose = POSES[qi % len(POSES)]
        w = 1250 * ratio[pose]
        beats.append({"t": round(start, 2), "dur": round(min(3.0, end - start), 1), "pose": f"v3/{pose}",
                      "x": round(540 - w / 2), "y": TOP, "h": 1250, "clip": BOTTOM - TOP})
        qi += 1

    iz = next((x for x in comp["scenes"] if x["id"] == "iz"), None)
    if iz:
        w = 640 * ratio[END_POSE]
        beats.append({"t": round(iz["start"] + 0.3, 2), "dur": round(iz["frames"] / 30 - 0.6, 1),
                      "pose": f"v3/{END_POSE}", "x": round(1080 - w - 60), "y": 660, "h": 640})

    spec["mascot_beats"] = beats
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return beats


if __name__ == "__main__":
    nth = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--n=")), "1"))
    for day in [a for a in sys.argv[1:] if not a.startswith("--")]:
        bs = build(day, nth)
        print(day, f"탐정 {len(bs)}번 —", [(b["t"], b["pose"]) for b in bs])
