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
TOP, BOTTOM = 940, 1500
# 원본 컷이 작다(시트 1024×1024 에 9포즈 → 포즈 하나가 약 200×290, 컷은 이미 2배로 오린 것).
# 1250px 로 띄우면 총 4배가 넘어 자글자글해진다(JJ 2026-09-23 "퀄리티가 낮아, 자글자글한 느낌").
# 그래서 **원본 높이의 1.35배**를 넘기지 않는다. 진짜 해결은 포즈마다 1024×1024 그림을 따로 받는 것.
MAX_UP = 1.35
# 탐정은 화면 아래 940~1500 을 쓴다. 거기까지 내려오는 카드 위에 올리면 **글씨를 가린다**
# (JJ 2026-09-23 프레임 확인: `score` 카드의 마지막 줄 '적어 두고 확인'을 머리가 덮었다).
# 그래서 아래가 비는 카드에만 올린다 — 큰 숫자 하나만 가운데 위에 뜨는 `big`.
# 목록형(score·check·steps·timeline·hbars·sides)과 축이 아래까지 내려오는 것(line·bars·vs·cal)은 전부 뺀다.
SAFE_KINDS = {"big"}
END_GAP = 8.0          # 끝 화면 탐정과 붙어 나오지 않게
MIN_GAP = 15.0         # 탐정끼리 — 이웃 장면에 연달아 나오면 한 덩어리로 보인다


def build(d: str, n: int = 1) -> list[dict]:
    ed = "info" if n <= 1 else f"info{n}"          # 하루에 두 편 이상이면 info2_script.json (build_info.ed_of 와 같은 이름)
    comp = json.loads((MC / "data" / d / f"computed_{ed}.json").read_text(encoding="utf-8"))
    sp = MC / "data" / d / f"{ed}_script.json"
    spec = json.loads(sp.read_text(encoding="utf-8"))
    cards = (spec.get("info") or {}).get("cards", {})

    ratio, src_h = {}, {}
    for n in set(POSES + [END_POSE]):
        with Image.open(CUTS / f"{n}.png") as im:
            ratio[n] = im.size[0] / im.size[1]
            src_h[n] = im.size[1]

    beats, qi = [], 0
    first = comp["scenes"][0]["id"]
    _iz = next((x for x in comp["scenes"] if x["id"] == "iz"), None)
    iz_start = _iz["start"] if _iz else 1e9
    for s in comp["scenes"]:
        if s["id"] == "iz" or s["id"] == first:       # 끝 화면은 따로, 훅은 사건과 질문만
            continue
        c = cards.get(s["id"]) or {}
        # 그림(art) 장면에는 띄우지 않는다 — 그 그림 안에 이미 탐정이 그려져 있어서
        # 한 화면에 탐정이 둘이 된다(JJ 2026-09-23 프레임 확인). 카드 장면에만 올라온다.
        if c.get("kind") not in SAFE_KINDS:
            continue
        q = c.get("q")
        if not q:
            continue
        at, cues = q[0].get("at"), s.get("cues") or []
        if at is None or at >= len(cues):
            continue
        start = s["start"] + cues[at]["start"] + 0.5
        end = s["start"] + s["frames"] / 30 - 0.2
        if end - start < 1.0 or start >= iz_start - END_GAP:
            continue
        pose = POSES[qi % len(POSES)]
        h = min(1250, int(src_h[pose] * MAX_UP))
        w = h * ratio[pose]
        beats.append({"t": round(start, 2), "dur": round(min(3.0, end - start), 1), "pose": f"v3/{pose}",
                      "x": round(540 - w / 2), "y": BOTTOM - min(h, BOTTOM - TOP), "h": h, "clip": min(h, BOTTOM - TOP)})
        qi += 1

    if len(beats) < 3:                      # 질문 장면이 모자라면 카드 장면 중 긴 것에 올린다
        used = {b["t"] for b in beats}
        cand = []
        for s in comp["scenes"]:
            if s["id"] in ("iz", first):
                continue
            c = cards.get(s["id"]) or {}
            cues = s.get("cues") or []
            if c.get("kind") not in SAFE_KINDS or len(cues) < 2:
                continue
            st = s["start"] + cues[-1]["start"] + 0.4
            en = s["start"] + s["frames"] / 30 - 0.2
            if en - st >= 1.4 and st not in used and st < iz_start - END_GAP:
                cand.append((en - st, st, en))
        cand = [x for x in cand if all(abs(x[1] - b["t"]) >= MIN_GAP for b in beats)]
        cand.sort(reverse=True)
        for _, st, en in cand:
            if len(beats) >= 3:
                break
            if any(abs(st - b["t"]) < MIN_GAP for b in beats):
                continue
            pose = POSES[qi % len(POSES)]
            h = min(1250, int(src_h[pose] * MAX_UP))
            w = h * ratio[pose]
            beats.append({"t": round(st, 2), "dur": round(min(2.6, en - st), 1), "pose": f"v3/{pose}",
                          "x": round(540 - w / 2), "y": BOTTOM - min(h, BOTTOM - TOP), "h": h,
                          "clip": min(h, BOTTOM - TOP)})
            qi += 1
        beats.sort(key=lambda b: b["t"])

    iz = next((x for x in comp["scenes"] if x["id"] == "iz"), None)
    if iz:
        he = min(640, int(src_h[END_POSE] * MAX_UP))
        w = he * ratio[END_POSE]
        beats.append({"t": round(iz["start"] + 0.3, 2), "dur": round(iz["frames"] / 30 - 0.6, 1),
                      "pose": f"v3/{END_POSE}", "x": round(1080 - w - 60), "y": 660 + (640 - he), "h": he})

    spec["mascot_beats"] = beats
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return beats


if __name__ == "__main__":
    nth = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--n=")), "1"))
    for day in [a for a in sys.argv[1:] if not a.startswith("--")]:
        bs = build(day, nth)
        print(day, f"탐정 {len(bs)}번 —", [(b["t"], b["pose"]) for b in bs])
