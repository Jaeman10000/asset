"""생활형 정보 쇼츠 만들기 — 국장 마감편과 별도 트랙(JJ 2026-09-19).

JJ: "생활형 정보가 가장 높았잖아? 그날 생활형 정보성이 짙은 뉴스나 이슈가 나오면 따로 영상을 만들어서 밤에 올려도 돼.
     하루 1개는 국장용만 필요하고, 다른 정보성 영상은 몇 개가 되든 상관없어."
근거: 조회 1위가 수급이 아니라 "오늘 밤 8시 한국 주식 거래 가능!?"(9/13, 5,490회) — docs/CHANNEL_REVIEW_2W.md.

대본 파일: data/<날짜>/info_script.json (둘째 편은 info2_script.json …)
  {"badge": "증시 정보", "date_label": "9/19 토", "title": "...", "caption": "설명란", "tags": [...], "hashtags": "#…",
   "threads": "...", "threads_reply": "...", "sources": ["매체 · 제목", …],
   "info": {"bg": "city|market|chip", "tone": "up|down|neutral",
            "cards": {"i0": {"kind": "hook", "badge": "…", "lines": [{"t": "…", "size": 1, "color": "yellow"}], "q": [{"t": "…"}]},
                      "i1": {"kind": "fact", "head": "…", "big": "…", "sub": "…"},
                      "i2": {"kind": "compare", "head": "…", "before": {"label": "…", "value": "…"}, "after": {...}},
                      "i3": {"kind": "list", "head": "…", "items": ["…", "…"]},
                      "i4": {"kind": "note", "head": "…", "text": "…"}}},
   "thumb": {"lines": [{"t": "…", "size": 0.9}, {"t": "…", "size": 1.1, "color": "yellow"}]},
   "scenes": {"i0": "…", "i1": "…", …, "i6": "누가샀나였습니다. 국장 마감은 매일 저녁 5시에 올라옵니다."}}
화면: render/src/v4/InfoV1.tsx(i0~i5), i6 은 평일 끝 화면.

실행(jobs/):
  python build_info.py 20260919 --stage=script     대본 점검(길이·금지어·질문·끝 멘트)만
  python build_info.py 20260919                    script → tts → render → 썸네일
  python build_info.py 20260919 --n=2              둘째 편(info2_script.json)
결과: out/<날짜>/info[N]/video.mp4 · thumb_A.jpg · youtube_title.txt · youtube_description.txt · youtube_tags.txt · threads.txt · threads_reply.txt
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from _common import DATA, computed_path, date_tail, load_json, log, out_dir, save_json

ORDER = ["i0", "i1", "i2", "i3", "i4", "i5", "i6"]
CPS = 7.35
LIMIT, FLOOR = 172, 60        # 초. 쇼츠 3분 선 — 넘기면 쇼츠 피드에서 빠진다
SIGN = r"누가샀나였습니다\. 국장 마감은 매일 저녁 5시에 올라옵니다\.$"
WD = "월화수목금토일"


def ed_of(n: int) -> str:
    return "info" if n <= 1 else f"info{n}"


def spec_path(d: str, n: int = 1) -> Path:
    return DATA / d / f"{ed_of(n)}_script.json"


def build(d: str, n: int = 1) -> dict:
    spec = load_json(spec_path(d, n))
    if not spec:
        raise SystemExit(f"{spec_path(d, n)} 없음 — 대본 파일을 먼저 만든다")
    dt = datetime.strptime(d[:8], "%Y%m%d")
    scenes = [{"id": sid, "tts": spec["scenes"][sid].strip(), "min": 2.0, "sub": spec["scenes"][sid].strip() if sid not in ("i0", "i6") else ""}
              for sid in ORDER if (spec.get("scenes") or {}).get(sid)]
    comp = {"date": d, "date_label": spec.get("date_label") or f"{dt.month}/{dt.day} {WD[dt.weekday()]}",
            "badge": spec.get("badge") or "증시 정보", "brand": "누가샀나", "format": "info", "visual": "info",
            "title": spec.get("title") or "", "caption": spec.get("caption") or "", "threads": spec.get("threads") or "",
            "threads_reply": spec.get("threads_reply") or "", "info": spec.get("info") or {}, "scenes": scenes,
            "kospi": {"close": None, "chg_pct": None}}
    save_json(computed_path(d, ed_of(n)), comp)
    return comp


def check(d: str, n: int = 1) -> list[str]:
    spec = load_json(spec_path(d, n)) or {}
    comp = build(d, n)
    bad: list[str] = []
    sys.path.insert(0, str(DATA.parent))
    from checks import forbidden
    import tts as _tts
    total = sum(len(s["tts"]) for s in comp["scenes"])
    sec = total / CPS + 0.4 * len(comp["scenes"])
    if sec > LIMIT:
        bad.append(f"길이 {sec:.0f}초 > {LIMIT}초 ({total}자) — 쇼츠 3분 선")
    if sec < FLOOR:
        bad.append(f"길이 {sec:.0f}초 < {FLOOR}초 ({total}자)")
    for s in comp["scenes"]:
        if hits := forbidden.find(_tts.speakable(s["tts"])):
            bad.append(f"{s['id']} 금지어 {hits}")
        if re.search(r"구독|좋아요|알림 설정", s["tts"]):
            bad.append(f"{s['id']} 부탁 문장 — 끝 부탁은 곡선이 −12~16 빠진다(v7)")
    if not comp["scenes"] or comp["scenes"][0]["id"] != "i0" or "?" not in comp["scenes"][0]["tts"]:
        bad.append("i0 훅에 질문이 없다 — 첫 장면은 사건 + 질문")
    if comp["scenes"] and not re.search(SIGN, comp["scenes"][-1]["tts"].strip()):
        bad.append("끝 멘트가 고정문과 다르다")
    qs = sum(1 for s in comp["scenes"] if "?" in s["tts"])
    if qs < 3:
        bad.append(f"질문이 {qs}개뿐 — 장면 끝 질문 → 다음 장면 답으로 이어지게")
    cards = (spec.get("info") or {}).get("cards") or {}
    for s in comp["scenes"]:
        if s["id"] != "i6" and s["id"] not in cards:
            bad.append(f"{s['id']} 화면 카드 없음 — 말만 하고 빈 화면이면 넘긴다")
    if len(spec.get("sources") or []) < 2:
        bad.append("출처 2곳 미만 — 여러 매체가 같이 말한 사실만 쓴다")
    for k in ("threads", "caption", "title"):
        if spec.get(k) and (hits := (forbidden.find_threads if k == "threads" else forbidden.find)(spec[k])):
            bad.append(f"{k} 금지어 {hits}")
    log(d, "info", f"{ed_of(n)}: {total}자 · 예상 {sec:.0f}초 · 장면 {len(comp['scenes'])}")
    return bad


def texts(d: str, n: int = 1) -> Path:
    """업로드 문안 — 제목 끝 날짜(JJ 2026-09-19), 설명란, 태그(줄임말 몇 개), 쓰레드."""
    spec = load_json(spec_path(d, n)) or {}
    od = out_dir(d, ed_of(n))
    dt = datetime.strptime(d[:8], "%Y%m%d")
    title = date_tail(spec.get("title") or "", f"{dt.month}/{dt.day} {spec.get('title_tag') or '증시 정보'}")
    src = "\n".join(f"· {s}" for s in (spec.get("sources") or []))
    desc = (f"{title}\n{spec.get('caption') or ''}\n\n출처\n{src}\n\n누가샀나는 평일 저녁 5시에 국장 마감 수급을 올립니다."
            f"\n자동 생성 · AI 음성 · 종목·매매 추천 아님\n\n{spec.get('hashtags') or '#누가샀나'}").strip()
    (od / "youtube_title.txt").write_text(title, encoding="utf-8")
    (od / "youtube_description.txt").write_text(desc[:5000], encoding="utf-8")
    (od / "youtube_tags.txt").write_text(", ".join(spec.get("tags") or []), encoding="utf-8")
    (od / "threads.txt").write_text(spec.get("threads") or "", encoding="utf-8")
    (od / "threads_reply.txt").write_text(spec.get("threads_reply") or "", encoding="utf-8")
    return od


def thumb(d: str, n: int = 1) -> None:
    spec = load_json(spec_path(d, n)) or {}
    lines = (spec.get("thumb") or {}).get("lines")
    if not lines:
        log(d, "info", "썸네일 문구 없음(thumb.lines) → 건너뜀")
        return
    ed = ed_of(n)
    info = spec.get("info") or {}
    t = {"out": f"out/{d}/{ed}", "cands": {"A": {"bg": info.get("bg") or "city", "tone": info.get("tone") or "neutral", "dim": 0.45,
         "objects": [{"k": "glow", "x": 540, "y": 780, "r": 640, "color": "yellow", "a": 0.18}], "lines": lines[:3], "logo": True,
         **({"badge": spec["thumb"]["badge"]} if (spec.get("thumb") or {}).get("badge") else {})}}}
    (DATA / d / ed).mkdir(parents=True, exist_ok=True)
    save_json(DATA / d / ed / "thumbs.json", t)
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("make_thumb.py")), f"{d}/{ed}", "--only=A"],
                       cwd=str(Path(__file__).parent), capture_output=True, text=True, encoding="utf-8", timeout=240)
    log(d, "info", f"썸네일 {'완료' if r.returncode == 0 else '실패 ' + (r.stderr or r.stdout)[-200:]}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else datetime.now().strftime("%Y%m%d")
    n = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--n=")), "1"))
    stage = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--stage=")), "all")
    ed = ed_of(n)
    if stage in ("all", "script"):
        bad = check(d, n)
        print("대본 점검:", "통과" if not bad else f"{len(bad)}건")
        for x in bad:
            print("  ✗", x)
        if bad and stage == "all":
            raise SystemExit(1)
    if stage in ("all", "tts"):
        import tts
        asyncio.run(tts.main(d, ed))
    if stage in ("all", "render"):
        import render
        render.run(d, "video", ed)
    if stage in ("all", "texts"):
        print("문안:", texts(d, n))
    if stage in ("all", "thumb"):
        thumb(d, n)


if __name__ == "__main__":
    main()
