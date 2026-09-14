"""제도 안내편 만들기 — 수급 데이터가 없는 특별편(예: 2026-09-14 애프터마켓 개설).

평일·주말편은 그날 수급에서 대본이 나오지만, 안내편은 사람이 쓴 대본과 고정된 제도 사실로 만든다.
장면 id는 n0~n6이고 화면은 render/src/v4/NoticeV4.tsx가 맡는다(n6만 평일 끝 멘트 화면을 그대로 쓴다).

대본 파일: data/<날짜>/notice_script.json
  {"badge": "증시 안내", "date_label": "9/13 일", "title": "...", "caption": "...",
   "threads": "...", "threads_reply": "...", "scenes": {"n0": "...", ..., "n6": "..."}}

실행:
  python build_notice.py 20260913 --stage=script    대본만 점검(길이·금지어)
  python build_notice.py 20260913 --stage=tts
  python build_notice.py 20260913 --stage=render
  python build_notice.py 20260913                   script → tts → render
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from _common import DATA, computed_path, load_json, log, save_json

ED = "notice"
ORDER = ["n0", "n1", "n2", "n3", "n4", "n5", "n6"]
MIN_SEC = 2.0
CPS = 7.2
LIMIT, FLOOR = 172, 90       # 초. 3분(쇼츠 한도)은 절대 넘기지 않는다 — 넘기면 쇼츠 피드에서 빠진다


def spec_path(d: str):
    return DATA / d / "notice_script.json"


def build(d: str) -> dict:
    spec = load_json(spec_path(d))
    if not spec:
        raise SystemExit(f"{spec_path(d)} 없음 — 대본 파일을 먼저 만든다")
    scenes = []
    for sid in ORDER:
        t = (spec.get("scenes") or {}).get(sid)
        if not t:
            continue
        scenes.append({"id": sid, "tts": t.strip(), "min": MIN_SEC, "sub": ""})
    comp = {
        "date": d,
        "date_label": spec.get("date_label") or datetime.strptime(d, "%Y%m%d").strftime("%-m/%-d").replace("-", ""),
        "badge": spec.get("badge") or "증시 안내",
        "brand": spec.get("brand") or "누가샀나",
        "format": "notice", "visual": "notice",
        "title": spec.get("title") or "",
        "caption": spec.get("caption") or "",
        "threads": spec.get("threads") or "",
        "threads_reply": spec.get("threads_reply") or "",
        "scenes": scenes,
        # 화면이 kospi를 읽지는 않지만 공용 타입이 요구해서 빈 값을 둔다
        "kospi": {"close": None, "chg_pct": None},
    }
    save_json(computed_path(d, ED), comp)
    return comp


def check(d: str) -> list[str]:
    comp = load_json(computed_path(d, ED)) or build(d)
    bad = []
    sys.path.insert(0, str(DATA.parent))
    from checks import forbidden
    import tts as _tts
    total = sum(len(s["tts"]) for s in comp["scenes"])
    sec = total / CPS + 0.4 * len(comp["scenes"])
    if sec > LIMIT:
        bad.append(f"길이 {sec:.0f}초 > {LIMIT}초 ({total}자)")
    if sec < FLOOR:
        bad.append(f"길이 {sec:.0f}초 < {FLOOR}초 — 안내편치고 짧다 ({total}자)")
    for s in comp["scenes"]:
        spoken = _tts.speakable(s["tts"])
        if hits := forbidden.find(spoken):
            bad.append(f"{s['id']} 금지어 {hits}")
    if comp["scenes"] and comp["scenes"][-1]["tts"].strip() != "누가샀나였습니다. 국장 마감은 매일 오후 4시 30분에 올라옵니다.":
        bad.append("끝 멘트가 고정문과 다르다")
    qs = sum(1 for s in comp["scenes"] if "?" in s["tts"])
    if qs < 3:
        bad.append(f"질문이 {qs}개뿐 — 장면마다 다음 질문으로 이어지는지 볼 것")
    if comp.get("threads"):
        if hits := forbidden.find_threads(comp["threads"]):
            bad.append(f"쓰레드 금지어 {hits}")
    log(d, "notice", f"{total}자 · 예상 {sec:.0f}초 · 장면 {len(comp['scenes'])}")
    return bad


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else datetime.now().strftime("%Y%m%d")
    stage = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--stage=")), "all")
    if stage in ("all", "script"):
        build(d)
        bad = check(d)
        print("대본 점검:", "통과" if not bad else f"{len(bad)}건")
        for x in bad:
            print("  ✗", x)
        if bad and stage == "all":
            raise SystemExit(1)
    if stage in ("all", "tts"):
        import tts
        asyncio.run(tts.main(d, ED))
    if stage in ("all", "render"):
        import render
        render.run(d, "video", ED)


if __name__ == "__main__":
    main()
