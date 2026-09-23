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
   "ai_images": {"bg": "영상 배경 프롬프트(영어)", "thumb": "썸네일 배경 프롬프트(영어)"},   ← 이슈 해설편: AI 배경(키 없으면 기본 배경)
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
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from _common import (DATA, computed_path, load_json, log, out_dir, pct_speech_issues,
                     save_json, strip_date, tag_tail)

ORDER = [f"i{k}" for k in range(20)] + ["iz"]      # iz = 끝 화면(기업 해부편). 생활형 카드편은 i6 이 끝 화면
END = ("i6", "iz")
RENDER = Path(__file__).resolve().parent.parent / "render"
CPS = 7.35
# 초. 쇼츠 3분(180초) 선 — 넘기면 쇼츠 피드에서 빠진다.
# CPS 7.35 는 실제(타입캐스트 약 7.8~8.2자/초)보다 보수적이다 — 추정 190초 ≈ 실제 175초.
# 음성이 만들어진 뒤에는 추정이 아니라 **실제 길이**로 잰다(REAL_LIMIT).
# JJ 2026-09-21: "길이에 국한되지 말고 만들 수 있는 거 다 만들어 넣어서 질 좋은 정보를 제공해라."
LIMIT, FLOOR, REAL_LIMIT = 205, 60, 178   # 추정 상한은 넉넉히, 진짜 선은 실제 길이 178초(쇼츠 3분 벽 180초)
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
    scenes = [{"id": sid, "tts": spec["scenes"][sid].strip(), "min": 2.0, "sub": spec["scenes"][sid].strip() if sid != "i0" and sid not in END else ""}
              for sid in ORDER if (spec.get("scenes") or {}).get(sid)]
    comp = {"date": d, "date_label": spec.get("date_label") or f"{dt.month}/{dt.day} {WD[dt.weekday()]}",
            "badge": spec.get("badge") or "증시 정보", "brand": "누가샀나", "format": "info", "visual": "info",
            "title": spec.get("title") or "", "caption": spec.get("caption") or "", "threads": spec.get("threads") or "",
            "threads_reply": spec.get("threads_reply") or "", "info": spec.get("info") or {}, "scenes": scenes,
            "kospi": {"close": None, "chg_pct": None}, "mascot_beats": spec.get("mascot_beats") or []}   # 주사위 탐정 출연(JJ 9/20)
    bgp = RENDER / "public" / "info" / f"{d}_{ed_of(n)}_bg.png"
    if bgp.exists():
        comp["info"] = {**comp["info"], "bg_image": f"info/{bgp.name}"}
    old = load_json(computed_path(d, ed_of(n))) or {}
    if old.get("total_frames") and [s["tts"] for s in old.get("scenes", [])] == [s["tts"] for s in scenes]:
        comp = {**old, **{k: v for k, v in comp.items() if k != "scenes"}}      # 음성 뒤에 다시 부르면 장면 길이·큐는 살린다
    save_json(computed_path(d, ed_of(n)), comp)
    return comp


def ai(d: str, n: int = 1) -> None:
    """AI 배경·썸네일(JJ 2026-09-19). 이미 만든 파일이 있으면 다시 안 만든다(돈이 든다). 키가 없으면 기본 배경."""
    import ai_image
    spec = load_json(spec_path(d, n)) or {}
    pr = spec.get("ai_images") or {}
    ed = ed_of(n)
    if not pr:
        return
    if not ai_image.available():
        log(d, "info", "AI 이미지 키 없음(openai:api_key / gemini:api_key) → 기본 배경")
        return
    bgp = RENDER / "public" / "info" / f"{d}_{ed}_bg.png"
    if pr.get("bg") and not bgp.exists():
        log(d, "info", f"AI 배경 {'완료' if ai_image.generate(pr['bg'], bgp) else '실패'}")
    thp = RENDER / "public" / "bg" / f"ai_{d}_{ed}.jpg"
    if pr.get("thumb") and not thp.exists():
        tmp = RENDER / "public" / "info" / f"{d}_{ed}_thumb.png"
        if ai_image.generate(pr["thumb"], tmp):
            from PIL import Image
            Image.open(tmp).convert("RGB").save(thp, "JPEG", quality=92)
            log(d, "info", "AI 썸네일 배경 완료")
    build(d, n)


def check(d: str, n: int = 1) -> list[str]:
    spec = load_json(spec_path(d, n)) or {}
    comp = build(d, n)
    bad: list[str] = []
    sys.path.insert(0, str(DATA.parent))
    from checks import forbidden
    import tts as _tts
    total = sum(len(s["tts"]) for s in comp["scenes"])
    sec = total / CPS + 0.4 * len(comp["scenes"])
    real = (comp.get("total_frames") or 0) / 30
    if real:                                   # 음성이 있으면 추정 대신 실제 길이로
        if real > REAL_LIMIT:
            bad.append(f"실제 길이 {real:.0f}초 > {REAL_LIMIT}초 ({total}자) — 쇼츠 3분 선")
    elif sec > LIMIT:
        bad.append(f"길이 {sec:.0f}초 > {LIMIT}초 ({total}자) — 쇼츠 3분 선(추정)")
    if sec < FLOOR:
        bad.append(f"길이 {sec:.0f}초 < {FLOOR}초 ({total}자)")
    for s in comp["scenes"]:
        if hits := forbidden.find(_tts.speakable(s["tts"])):
            bad.append(f"{s['id']} 금지어 {hits}")
        if pb := pct_speech_issues(s["tts"]):
            bad.append(f"{s['id']} 말하는 % {pb} — 소수 첫째 자리까지, .0 은 뗀다(5.01% → 5%)")
        # v7 은 '끝 부탁 없음'이었다(스튜디오 실측: 곡선 −12~16). JJ 2026-09-21 이 정보형에 한해 열었다 —
        # "이런 숫자 직접 찾는 건 귀찮으니 누가샀나가 매일 알려드린다, 그러니 구독과 좋아요 좀 부탁한다고 하고."
        # 그래서 **끝 멘트 바로 앞 한 장면에서만** 허용한다. 중간에 흩뿌리면 v7 이 잰 그 손해가 그대로 난다.
        if re.search(r"구독|좋아요|알림 설정", s["tts"]):
            last_body = [x["id"] for x in comp["scenes"] if x["id"] not in END][-1:]
            if s["id"] not in last_body:
                bad.append(f"{s['id']} 부탁 문장이 끝 장면이 아니다 — 끝 멘트 바로 앞 한 장면에서만(v7 실측 −12~16)")
    if not comp["scenes"] or comp["scenes"][0]["id"] != "i0" or "?" not in comp["scenes"][0]["tts"]:
        bad.append("i0 훅에 질문이 없다 — 첫 장면은 사건 + 질문")
    if comp["scenes"] and not re.search(SIGN, comp["scenes"][-1]["tts"].strip()):
        bad.append("끝 멘트가 고정문과 다르다")
    qs = sum(1 for s in comp["scenes"] if "?" in s["tts"])
    if qs < 3:
        bad.append(f"질문이 {qs}개뿐 — 장면 끝 질문 → 다음 장면 답으로 이어지게")
    cards = (spec.get("info") or {}).get("cards") or {}
    for s in comp["scenes"]:
        if s["id"] not in END and s["id"] not in cards:
            bad.append(f"{s['id']} 화면 카드 없음 — 말만 하고 빈 화면이면 넘긴다")
    bad += card_at_issues(comp["scenes"], cards)
    bad += chart_issues(comp["scenes"], cards)
    bad += echo_issues(comp["scenes"], cards)
    bad += dropped_field_issues(comp["scenes"], cards)
    bad += color_issues(comp["scenes"], cards)
    bad += future_tense_issues(comp["scenes"])
    bad += dead_screen_issues(comp["scenes"], cards, has_thumb=bool((spec.get("info") or {}).get("thumbS")))
    bad += blank_card_issues(comp["scenes"], cards)
    bad += upload_date_issues(spec)
    bad += weapon_issues(comp["scenes"])
    bad += kind_mix_issues(d, cards)
    bad += number_sync_issues(comp["scenes"], cards)
    bad += jargon_issues(comp["scenes"], cards)
    bad += tautology_issues(comp["scenes"])
    bad += hook_answer_issues(comp["scenes"])
    bad += hook_screen_issues(comp["scenes"], cards)
    bad += hook_double_question_issues(comp["scenes"], spec.get("info") or {})
    bad += dup_head_issues(comp["scenes"], cards)
    bad += subtitle_pick_issues()
    # 렌더러가 만들어 둔 장면 칸을 넘으면 그 장면은 **통째로 검정**이 된다 — 화면이 안 그려지고 소리만 난다.
    # (JJ 2026-09-21 "10월1일 영상 2분부터 검정색 화면이 나와 8초동안" — DISSECT_COMP/INFO_COMP 이 i9 까지였다)
    # render/src/v4/DissectV1.tsx DISSECT_COMP · InfoV1.tsx INFO_COMP 의 length 와 같아야 한다.
    if over := [s["id"] for s in comp["scenes"]
                if s["id"].startswith("i") and s["id"][1:].isdigit() and int(s["id"][1:]) >= RENDER_SCENES]:
        bad.append(f"렌더러에 없는 장면 {' '.join(over)} — 화면이 검정으로 나온다. "
                   f"DISSECT_COMP·INFO_COMP 을 i{RENDER_SCENES - 1} 너머까지 늘리거나 장면을 줄인다")
    # 문장을 고치면 cue 가 비워진다 → 화면 정지 검사를 할 수 없다. 통과했다고 믿으면 안 된다.
    # 한 문장짜리 장면은 cue 가 하나인 게 정상이다 — 문장 수와 견줘서 판단한다(2026-09-22 오탐 고침).
    if mute := [s["id"] for s in comp["scenes"]
                if len(s.get("cues") or []) < _sent_count(s.get("tts", "")) and isinstance(cards.get(s["id"]), dict)]:
        bad.append(f"음성이 없어 화면 정지를 못 쟀다: {' '.join(mute)} — "
                   f"--stage=tts 를 돌린 뒤 이 검사를 다시 한다(그 전 '통과'는 잠정)")

    if not (spec.get("topic_line") or "").strip():
        bad.append('topic_line 이 없다 — 이 편이 답하는 질문 한 줄을 적는다. 모든 장면이 그 한 줄에 답해야 한다'
                   ' (JJ 2026-09-21 "배당락 영상 주제가 뭐야? 왜 이렇게 중구난방이야?")')
    bad += rhythm_issues(comp["scenes"], cards, spec.get("mascot_beats") or [], d)
    # 숫자가 상하는 편은 만든 날과 올리는 날이 멀면 틀린 영상이 된다(JJ 2026-09-21)
    fu = spec.get("fresh_until")
    if fu:
        if str(fu).replace("-", "") < d[:8]:
            bad.append(f"fresh_until {fu} 이 지났다 — 올리는 날은 {d[:8]}. 숫자를 다시 뽑고 대본을 고친다")
    elif any(x in (spec.get("caption") or "") + " ".join((spec.get("scenes") or {}).values() if isinstance(spec.get("scenes"), dict) else [])
             for x in ("기준", "거래일", "현재")):
        bad.append("fresh_until 이 없다 — 기준일이 박힌 편은 언제까지 유효한지 적는다(예: \"fresh_until\": \"2026-09-23\")")
    if len(spec.get("sources") or []) < 2:
        bad.append("출처 2곳 미만 — 여러 매체가 같이 말한 사실만 쓴다")
    for k in ("threads", "caption", "title"):
        if spec.get(k) and (hits := (forbidden.find_threads if k == "threads" else forbidden.find)(spec[k])):
            bad.append(f"{k} 금지어 {hits}")
    log(d, "info", f"{ed_of(n)}: {total}자 · 예상 {sec:.0f}초 · 장면 {len(comp['scenes'])}")
    return bad



def _sent_count(tts: str) -> int:
    return len([x for x in re.split(r"(?<=[.?!])\s+", (tts or "").strip()) if x])


def card_at_issues(scenes: list[dict], cards: dict) -> list[str]:
    """화면 조각의 at(문장 번호) 점검 — JJ 2026-09-20 "말은 이전 문장인데 다음 줄이 먼저 켜져 있다".
    ① 글줄(items·timeline·score)은 한 문장에 하나만 — 같은 at 을 둘이 쓰면 아직 안 한 말이 먼저 보인다(차트 막대·달력은 한 문장이 두 숫자를 말할 수 있어 예외)(한 문장에 두 줄이 같이 켜져, 아직 안 한 말이 먼저 보인다 → 문장을 쪼갠다)
    ② at 이 그 장면의 문장 수보다 크면 안 된다(끝까지 안 켜진다)
    ③ 첫 조각은 0 이나 1 이어야 한다(처음 몇 초가 빈 화면이면 나간다)"""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        n = _sent_count(s.get("tts", ""))
        art = c.get("art") if isinstance(c.get("art"), dict) else None
        if art and art.get("full") and c.get("items") and not c.get("list_ok"):
            out.append(f"{s['id']} 배경 장면에 글줄 {len(c['items'])}개 — 자막이 같은 말을 한다. big + big_sub 하나로(§17-6). 상품 목록처럼 대사와 다른 내용이면 list_ok: true")
        groups: list[tuple[str, list]] = []
        for key in ("items", "rows", "bars", "groups", "score", "timeline", "marks"):
            v = c.get(key)
            if isinstance(v, list):
                groups.append((key, v))
        if isinstance(c.get("cal"), dict) and isinstance(c["cal"].get("marks"), list):
            groups.append(("cal.marks", c["cal"]["marks"]))
        if isinstance(c.get("chart"), dict) and isinstance(c["chart"].get("rows"), list):
            groups.append(("chart.rows", c["chart"]["rows"]))
        for key, v in groups:
            ats = [x.get("at") for x in v if isinstance(x, dict) and x.get("at") is not None]
            if not ats:
                continue
            dup = {a for a in ats if ats.count(a) > 1} if key in ("items", "timeline", "score") else set()
            if dup:
                out.append(f"{s['id']}.{key} at 중복 {sorted(dup)} — 한 문장에 두 줄을 붙이지 않는다(문장을 쪼개라)")
            over = [a for a in ats if a >= n]
            if over:
                out.append(f"{s['id']}.{key} at {over} 가 문장 수({n})보다 크다 — 끝까지 안 켜진다")
            if min(ats) > 1:
                out.append(f"{s['id']}.{key} 첫 조각 at={min(ats)} — 앞 {min(ats)}문장이 빈 화면이다(0 이나 1 로)")
    return out

# 각주(note)를 화면에 그리는 카드 — 나머지에 note 를 쓰면 조용히 사라진다
# (JJ 2026-09-21: check 의 쿠팡 고지, duo 의 기타법인 문구가 그렇게 날아갔다)
NOTE_KINDS = {"sides", "timeline", "art", "cal", "steps", "line", "bars", "hbars",
              "picto", "stack", "big", "check", "duo", "split"}
# 카드 종류마다 실제로 읽는 자료 열쇠 — 비어 있으면 빈 카드가 된다
KIND_KEY = {"hook2": "chips", "line": "series", "bars": "bars", "hbars": "rows", "duo": "duo",
            "score": "score", "steps": "steps", "cal": "cal", "timeline": "timeline",
            "check": "items", "sides": "sides", "art": "art", "split": "up", "big": "big"}


def dropped_field_issues(scenes: list[dict], cards: dict) -> list[str]:
    """쓴 대로 안 그려지는 것을 잡는다 — 써 놓고 화면에 없으면 알아차릴 방법이 없다."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        kind = c.get("kind")
        if c.get("note") and kind not in NOTE_KINDS:
            out.append(f"{s['id']} '{kind}' 카드는 note 를 그리지 않는다 — 써도 화면에 안 나온다"
                       f"(DissectV1 에 Note 를 넣거나 다른 카드로)")
        key = KIND_KEY.get(kind)
        if key and not c.get(key):
            out.append(f"{s['id']} '{kind}' 카드에 {key} 가 없다 — 빈 카드가 된다")
    return out


# 정보형은 아침 7:30 — 장이 열리기 전이다. 그날 주가 움직임을 사실로 말하면 안 된다
# (JJ 2026-09-21: "오늘 아침 삼성전자가 내려서 시작합니다? 아직 벌어진 일도 아니잖아")
TODAY_WORDS = ("오늘", "지금", "현재")
MOVE_WORDS = ("내려서 시작", "올라서 시작", "내려서 출발", "올라서 출발", "내렸습니다", "올랐습니다",
              "내리고 있습니다", "오르고 있습니다", "떨어졌습니다", "뛰었습니다", "급등", "급락")


def future_tense_issues(scenes: list[dict]) -> list[str]:
    """업로드(아침 7:30) 시점에 아직 벌어지지 않은 그날 주가 움직임을 단정한 곳."""
    out: list[str] = []
    for s in scenes:
        for sent in re.split(r"(?<=[.?!])\s+", (s.get("tts") or "").strip()):
            if any(w in sent for w in TODAY_WORDS) and any(m in sent for m in MOVE_WORDS):
                out.append(f"{s['id']} 아직 안 벌어진 일을 사실로 말한다 — \"{sent[:30]}\". "
                           f"정보형은 장 열리기 전(7:30)에 올라간다. '오늘 …했습니다'를 쓰지 않는다")
    return out


def _piece_ats(c: dict) -> list[int]:
    """카드 안에서 화면이 바뀌는 시점(문장 번호)을 모두 모은다."""
    ats: list[int] = []

    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get("at"), int):
                ats.append(v["at"])
            for k, x in v.items():
                if k != "at":
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(c)
    if isinstance(c.get("note_at"), int):
        ats.append(c["note_at"])
    if isinstance(c.get("big_at"), int):
        ats.append(c["big_at"])
    if isinstance(c.get("big_sub_at"), int):   # big_sub 가 제 문장에서 따로 뜬다(SCHD → 배당률 3.1%, 2026-09-22)
        ats.append(c["big_sub_at"])
    # big 의 큰 숫자는 장면 '시작'에 뜬다(DissectV1 Big 의 pop(0.05)) — marks[0]=0 이 이미 그걸 센다.
    # 그래서 big 카드는 note·ratio·q 가 없으면 장면 내내 화면이 그대로다. 그게 사실이므로 봐주지 않는다.
    return sorted(set(ats))


RENDER_SCENES = 20   # render/src/v4 의 DISSECT_COMP·INFO_COMP 이 만들어 둔 i0~i19 (넘으면 검정 화면)
ART_LIMIT = 10.0  # 그림만 가는 장면은 짧게 — 길어지면 "글자 하나 띄워 놓고 말만"이 된다(JJ 2026-09-21)


BLANK_LIMIT = 4.0        # 카드 틀만 있고 알맹이가 안 들어온 구간 — 머리글은 보이니 '빈 화면'은 아니다
BLANK_KINDS = {"bars", "hbars", "timeline", "check", "sides", "duo", "split", "cal", "steps", "score"}


def blank_card_issues(scenes: list[dict], cards: dict) -> list[str]:
    """첫 조각이 늦게 들어오면 그 동안 카드가 텅 빈 채로 서 있다 — 9/30 i2 막대 카드가
    축 이름만 띄운 채 3초를 갔다(JJ 2026-09-21 '지루하다'). 1~2초 뜸은 리듬이라 놔둔다."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict) or c.get("kind") not in BLANK_KINDS:
            continue
        key = KIND_KEY.get(c["kind"])
        items = c.get(key) if key else None
        if not isinstance(items, list):
            continue
        ats = [x["at"] for x in items if isinstance(x, dict) and isinstance(x.get("at"), int)]
        cues = s.get("cues") or []
        if not ats or not cues:
            continue
        first = min(ats)
        if first >= len(cues):
            continue
        blank = cues[first]["start"]
        if s is scenes[0]:
            blank -= 2.45          # 훅은 첫 2.45초가 썸네일이라 카드가 아직 안 보인다(OpenHook)
        if blank > BLANK_LIMIT:
            out.append(f"{s['id']} 카드가 {blank:.1f}초 동안 알맹이 없이 서 있다(최대 {BLANK_LIMIT:.0f}초) — "
                       f"앞 문장을 줄이거나 앞 장면으로 넘긴다")
    return out


DATE_IN_TEXT = re.compile(r"(\d{1,2}월\s*\d{1,2}일|\d{1,2}/\d{1,2})")


def upload_date_issues(spec: dict) -> list[str]:
    """정보형은 업로드 날짜를 화면·제목·썸네일에 박지 않는다 — JJ 2026-09-21
    "정보성 영상은 날짜를 앞으로 안 보여줘도 될 것 같아. 그러면 유기적으로 업로드 날짜 변경할 때 그냥 바꾸면 되니까."
    박아 두면 날짜를 옮길 때마다 음성·영상·썸네일을 통째로 다시 만들어야 한다.
    (국장 마감·주간 브리핑은 반대로 **항상** 붙인다 — 그쪽은 date_tail 이 담당한다.)"""
    out: list[str] = []
    info = spec.get("info") or {}
    for label, val in (("title_tag", spec.get("title_tag")), ("badge", spec.get("badge"))):
        if val and DATE_IN_TEXT.search(str(val)):
            out.append(f"{label} 에 날짜가 있다 — \"{val}\". 정보형은 날짜를 보여 주지 않는다(날짜를 옮기면 다시 만들어야 한다)")
    for k in ("thumbS", "thumbB", "thumb"):
        tag = (info.get(k) or {}).get("tag") if isinstance(info.get(k), dict) else None
        if tag and DATE_IN_TEXT.search(str(tag)):
            out.append(f"info.{k}.tag 에 날짜가 있다 — \"{tag}\". 날짜를 뺀 꼬리표만 쓴다")
    title = (spec.get("title") or "").strip()
    if "|" in title and DATE_IN_TEXT.search(title.rsplit("|", 1)[1]):
        out.append(f"제목 꼬리에 날짜가 있다 — \"{title.rsplit('|', 1)[1].strip()}\". 정보형 제목엔 날짜를 붙이지 않는다")
    return out


# 우리가 매일 재는 수급 숫자를 '어디서 보는지' 가르치면 시청자가 우리한테 올 이유가 없어진다.
# JJ 2026-09-21: "나의 무기를 오픈하면 안되겠지? … 그걸 말하면 자기가 직접 보게 되니까 이걸 안 볼 수도 있다라고
#  생각을 해야지. 우린 비지니스야. … 이런 숫자들을 직접 찾는 건 귀찮은 일이니까 누가샀나가 매일 국장이 끝나면
#  깔끔하게 알려드리니 항상 오라고 말을 해야지."
# 막는 것은 **수급 데이터의 출처 안내**뿐이다. 재무제표·용어 설명처럼 우리가 매일 제공하지 않는 것은 자유.
WEAPON_SRC = ("거래소 누리집", "거래소 홈페이지", "정보데이터시스템", "krx", "세이브로", "예탁결제원",
              "증권사 앱", "증권사 어플", "엠티에스", "에이치티에스", "HTS", "MTS")
WEAPON_TEACH = ("어디서 보", "어디서 확인", "보는 법", "찾는 법", "찾아보시", "검색하시", "검색하면",
                "들어가시면", "들어가 보", "확인하실 수", "보실 수 있습니다", "볼 수 있습니다")


# 한 편 안에서 같은 카드 종류가 몰리면, 종류를 바꿔도 틀(종이 바탕·머리글·자막 상자)이 같아서 다 같은 화면으로 보인다.
# 실측(2026-09-22): 9/26 은 상위 두 종류가 78%, 9/24 67%, 9/28 64%. 18종 중 17종을 쓰는데 check·art·big·timeline·bars 가 70%.
# JJ 2026-09-22 "10월 3일부터 만들 영상에는 한번 넣어보자" → 그 뒤 편부터 막는다.
KIND_MIX_FROM = "20261003"
KIND_MIX_MAX = 0.35
KIND_MIX_FREE = {"art"}          # 그림 장면은 많을수록 좋다 — 틀을 통째로 깬다

# 종이 카드가 몇 장면까지 내리 이어져도 되나 — 종류가 달라도 같은 틀은 같은 화면으로 보인다.
# JJ 2026-09-22(챗지피티 평가 검토): "통계 구간에 이미지가 없으면 숫자 나열처럼 느껴진다" → 진단은 맞다.
# 다만 해법은 그림을 11~12장으로 늘리는 게 아니다 — 그림엔 글줄을 못 얹어 숫자를 못 싣는다(숫자는 카드 몫).
# 마른 구간에 그림 한 장을 끼워 끊는 것으로 충분하다.
CARD_RUN_FROM = "20260922"
CARD_RUN_MAX = 5                 # 5연속이면 실패 → 최대 4연속



def kind_mix_issues(d: str, cards: dict) -> list[str]:
    if d < KIND_MIX_FROM:
        return []
    ks = [v.get("kind") for v in cards.values() if isinstance(v, dict) and v.get("kind")]
    n = len(ks)
    if n < 8:
        return []
    out = []
    for k in set(ks) - KIND_MIX_FREE:
        c = ks.count(k)
        if c / n > KIND_MIX_MAX:
            out.append(f"카드 '{k}' 가 {c}/{n}({c / n * 100:.0f}%) — 한 종류가 {KIND_MIX_MAX * 100:.0f}% 를 넘으면 같은 화면으로 보인다. "
                       f"안 쓰는 종류를 쓴다(picto·stack·vs·score·steps·sides·line)")
    return out


# ── JJ 2026-09-22 밤, 9/27~9/29 세 편을 보고 지적한 것들을 그대로 검사기로 옮긴다 ──
_NUM = re.compile(r"\d[\d,.]*")


def _nums_of(s: str) -> set[str]:
    return {m.group(0).rstrip(".").replace(",", "") for m in _NUM.finditer(s or "")}


def number_sync_issues(scenes: list[dict], cards: dict) -> list[str]:
    """**화면에 뜬 숫자는 그 숫자를 말하는 문장에 붙어야 한다.**
    JJ 2026-09-22: "세금을 떼면 이자는 연 몇 %가 남는다 할 때 화면이 이게 맞냐? 말하는 강세와
     장면이 보여주려는 포인트가 안 맞잖아!" — 9/28 에서 세금을 말하는데 물가 숫자가 떠 있었다.
    라벨(vlabel·t·big)만 본다. note·sub·head 는 꼬리표라 뺀다."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        sents = [x for x in re.split(r"(?<=[.!?])\s+", (s.get("tts") or "").strip()) if x]
        if not sents:
            continue
        pieces: list[tuple[str, str, int | None]] = []
        for key in ("bars", "rows"):
            for b in (c.get(key) or []):
                if isinstance(b, dict):
                    pieces.append((f"{key}.vlabel", b.get("vlabel") or "", b.get("at")))
        for key in ("items", "timeline"):
            for b in (c.get(key) or []):
                if isinstance(b, dict):
                    pieces.append((f"{key}.t", b.get("t") or "", b.get("at")))
        if c.get("big"):
            pieces.append(("big", str(c["big"]), c.get("big_at")))
        for where, txt, at in pieces:
            want = _nums_of(txt)
            if not want or at is None or at >= len(sents):
                continue
            # 다음 문장까지 봐주면 안 된다 — 그 여유가 바로 JJ가 잡은 어긋남을 숨긴다.
            said = _nums_of(sents[at])
            elsewhere = _nums_of(" ".join(x for i, x in enumerate(sents) if i != at))
            # 이 장면 어디에도 없는 숫자는 앞 장면을 되부르는 것이거나 한글로 읽는 것("다섯 시")이라 넘어간다.
            # **이 장면의 다른 문장에서 말하는데 엉뚱한 문장에 붙어 있는 것**만 잡는다 — 그게 어긋남이다.
            miss = [n for n in want if n not in said and n in elsewhere]
            if miss:
                out.append(f"{s['id']}.{where} '{txt}' 의 숫자 {miss} 가 엉뚱한 문장에 붙어 있다 — "
                           f"at={at} 은 \"{sents[at][:26]}…\" 인데 그 숫자는 이 장면의 다른 문장에서 말한다")
    return out


# 시청자가 모르는 업계 말. 왼쪽을 쓰면 오른쪽으로 바꾼다.
JARGON = {"회원사": "증권사", "잠정치": "아직 확정 전인 값", "추정치": "어림한 값",
          "익일": "다음 날", "전일 대비": "어제보다", "장중값": "장 중에 보이는 숫자",
          "기준일": "세는 날", "공표": "내놓는 것"}


def jargon_issues(scenes: list[dict], cards: dict) -> list[str]:
    """JJ 2026-09-22: "회원사 보고를 모은 추정? 뭔 개소리야. 너만 아는 거 써 놓고 이해하라는 식이냐" """
    out: list[str] = []
    blob = {s["id"]: (s.get("tts") or "") for s in scenes}
    for sid, c in (cards or {}).items():
        if isinstance(c, dict):
            blob[sid] = blob.get(sid, "") + " " + json.dumps(c, ensure_ascii=False)
    for sid, t in blob.items():
        for bad_w, good in JARGON.items():
            if bad_w in t:
                out.append(f"{sid} 업계 말 '{bad_w}' — 시청자는 모른다. '{good}' 로 바꾼다")
    return out


_TAUTO = re.compile(r"(\S{1,6})\s*치면\s*\1|(\S{1,6})\s*이면\s*\2|(\S{1,6})\s*면\s*\3")


def tautology_issues(scenes: list[dict]) -> list[str]:
    """JJ 2026-09-22: "10년 치면 10년, 30년 치면 30년? 무슨 말장난하냐" — 같은 말을 되돌려주는 문장."""
    out = []
    for s in scenes:
        for m in _TAUTO.finditer(s.get("tts") or ""):
            out.append(f"{s['id']} 말장난 '{m.group(0)}' — 같은 말을 되돌려 주면 아무 정보가 없다")
    return out


# 훅이 이 말로 물으면, 끝에서 그 단위로 답해야 한다
HOOK_ANSWER = {"얼마": ("원", "달러"), "몇 년": ("년", "해"), "몇 %": ("%",), "언제": ("시", "일", "월", "분기")}


def hook_answer_issues(scenes: list[dict]) -> list[str]:
    """**훅에서 물은 것은 끝 장면이 같은 단위로 답해야 한다.**
    JJ 2026-09-22: "훅은 저렇게 잡았으면 결과에서 그 답을 줘야 할 거 아냐. 영상 끝까지 봤는데
     그래서 얼마를 가지고 있어야 하는데? 그딴 말 하나도 없고" — 9/27 이 그랬다."""
    if not scenes:
        return []
    # 물음표로 닫는 문장에 들어 있을 때만 '물었다'로 본다("얼마를 샀다는 말" 같은 건 질문이 아니다)
    hook = " ".join(x for x in re.split(r"(?<=[.!?])\s+", scenes[0].get("tts") or "") if x.strip().endswith("?"))
    tail = " ".join(s.get("tts") or "" for s in scenes[-4:])
    out = []
    for word, units in HOOK_ANSWER.items():
        if word in hook and not any(u in tail for u in units):
            out.append(f"훅이 '{word}' 를 물었는데 끝 장면에 답({'·'.join(units)})이 없다 — "
                       f"물었으면 끝에서 그 단위로 답한다")
    return out


def hook_screen_issues(scenes: list[dict], cards: dict) -> list[str]:
    """**첫 화면 글자는 훅에서 하는 말과 같아야 한다.**
    JJ 2026-09-22: "처음 훅이 '얼마가 있어야 할까요' 라고 쳐말하면서 화면 글은 '얼마가 아니라 몇 년일까?'
     라고 쓰여 있고. 장난하냐?" """
    if not scenes:
        return []
    c = cards.get(scenes[0]["id"])
    q = (c or {}).get("q") if isinstance(c, dict) else None
    if not q:
        return []
    qt = " ".join(x.get("t", "") if isinstance(x, dict) else str(x) for x in q)
    hook_q = [x for x in re.split(r"(?<=[.!?])\s+", (scenes[0].get("tts") or "")) if "?" in x]
    if not hook_q:
        return []
    out: list[str] = []
    # ① 첫 화면은 **묻기만** 한다. 답을 먼저 적으면 훅이 죽고 말과 화면이 어긋난다.
    for w in ("아니라", "아니고", "말고", "이 아니라"):
        if w in qt:
            out.append(f"첫 화면 질문 \"{qt}\" 가 답을 먼저 말한다('{w}') — 훅 화면은 묻기만 한다. "
                       f"대사는 \"{hook_q[0][:30]}…\" 라고 묻고 있다")
            break
    # ② 훅 대사의 질문과 낱말이 하나도 안 겹치면 다른 얘기를 띄운 것이다
    key = [w for w in re.findall(r"[가-힣]{2,}", " ".join(hook_q))]
    if key and not any(w in qt for w in key):
        out.append(f"첫 화면 질문 \"{qt}\" 가 훅에서 하는 말과 겹치는 낱말이 없다 — 말과 화면이 어긋나면 바로 나간다")
    return out


def hook_double_question_issues(scenes: list[dict], info: dict) -> list[str]:
    """**훅 장면은 큰 질문을 두 번 던지지 않는다.**
    JJ 2026-09-22: "첫 장면 …얼마가 있어야 할까? 가 1초만에 사라지며 …글씨가 화면 중앙에 다시떠.
     이걸 왜 이딴식으로 만드는거야? 그냥 첫화면 그대로 두면될껄?" — 썸네일(OpenHook)이 이미 질문을
     크게 던진 뒤라, 첫 장면 대사 질문이 자동으로 또 크게 깔리면 첫 글자가 다른 문장으로 바뀌어 깨져 보인다.
    렌더러(DissectV1 qCue)는 대사 질문을 **마지막 문장이 ? 로 끝날 때만** 자동으로 띄운다 — 그래서
     첫 장면의 마지막 문장이 질문이면서 card.q(명시 질문)가 없으면 그 자동 질문이 썸네일과 겹친다.
    막는 조건: thumbS(썸네일 훅)가 있고, 첫 장면 마지막 문장이 ? 이고, 첫 장면 카드에 q 가 없을 때."""
    if not scenes or not (info or {}).get("thumbS"):
        return []
    first = scenes[0]
    sents = [x for x in re.split(r"(?<=[.!?])\s+", (first.get("tts") or "").strip()) if x]
    if not sents or not sents[-1].rstrip().endswith("?"):
        return []
    c = (info.get("cards") or {}).get(first["id"])
    if isinstance(c, dict) and c.get("q"):
        return []
    return [f"{first['id']} 훅 장면 마지막 문장이 질문인데 card.q 가 없다 — 썸네일 훅과 큰 질문이 "
            f"겹쳐 첫 글자가 바뀌어 보인다(JJ 2026-09-22). 질문을 앞 문장으로 옮겨 마지막을 서술문으로 "
            f"닫거나, 화면에 띄울 질문을 card.q 로 명시한다"]


def dup_head_issues(scenes: list[dict], cards: dict) -> list[str]:
    """**이웃 장면이 같은 머리(head)를 달면 안 된다** — JJ 2026-09-22: 9/27 i13·i14 가 둘 다
     '오늘부터 할 수 있는 것' 이었다. 두 장면이 같은 꼬리표를 달면 화면이 안 넘어간 듯 보이고 지루하다."""
    out: list[str] = []
    prev_id = prev_head = None
    for s in scenes:
        c = cards.get(s["id"])
        head = (c.get("head") or "").strip() if isinstance(c, dict) else ""
        if head and head == prev_head:
            out.append(f"{prev_id}·{s['id']} 머리(head)가 똑같다 \"{head}\" — 이웃 장면은 다른 꼬리표로 "
                       f"(화면이 안 넘어간 듯 보인다, JJ 2026-09-22)")
        prev_id, prev_head = s["id"], head
    return out


def weapon_issues(scenes: list[dict]) -> list[str]:
    """수급 숫자를 '어디서 보는지' 알려주지 않는다(JJ 2026-09-21 — 우린 비즈니스다)."""
    out: list[str] = []
    for s in scenes:
        t = s["tts"]
        if any(w.lower() in t.lower() for w in WEAPON_SRC) and any(v in t for v in WEAPON_TEACH):
            out.append(f"{s['id']} 수급을 어디서 보는지 알려주고 있다 — 그 자리는 '직접 찾긴 번거롭다 → "
                       f"누가샀나가 매일 정리해 올린다'로 쓴다(JJ 2026-09-21)")
    return out


SUB_PICK_FILES = ("v4/DissectV1.tsx", "v4/ScenesV4.tsx", "v4/WeeklyV4.tsx",
                  "v4/WeeklyV5.tsx", "v4/WeeklyUSV4.tsx")


def subtitle_pick_issues() -> list[str]:
    """자막은 '지금 말하는 것'이어야 한다 — JJ 2026-09-21 "말과 보여지는 영상의 장면이 또 차이가난다".
    자막에 0.5초 꼬리를 주면 두 자막의 창이 겹치는데, cues.find(...) 는 늘 **앞** 것을 집는다.
    그래서 다음 문장이 시작됐는데도 이전 자막이 남아 화면보다 늦는다. filter(...).pop() 으로 나중 것을 써야 한다."""
    out: list[str] = []
    root = Path(__file__).resolve().parents[1] / "render" / "src"
    for rel in SUB_PICK_FILES:
        f = root / rel
        if not f.exists():
            continue
        if re.search(r"cues\??\.?\s*(?:\?\?\s*\[\])?\s*\.find\(\(x\)\s*=>\s*t\s*>=\s*x\.start", f.read_text(encoding="utf-8")):
            out.append(f"{rel} 가 자막을 find 로 고른다 — 0.5초 꼬리 때문에 앞 자막이 잡혀 화면보다 늦는다. "
                       f"filter 로 바꿔 시작한 것 중 나중 것을 쓴다")
    return out


def dead_screen_issues(scenes: list[dict], cards: dict, gap: float = 6.0, has_thumb: bool = False) -> list[str]:
    """화면이 오래 안 바뀌는 구간 — 글자 하나 띄우고 말만 하는 장면을 막는다
    (JJ 2026-09-21: "35~51초까지 이 글자 하나만 띄어놓고 말만 하네?")."""
    out: list[str] = []
    for s in scenes:
        cues = s.get("cues") or []
        if len(cues) < 2:
            continue                      # 음성 전이면 잴 수 없다
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        end = s.get("frames", 0) / 30
        # 그림만 가는 장면(art full)은 천천히 확대되니 조각이 없어도 된다 — 대신 짧아야 한다.
        # JJ 2026-09-21 "그림 한 장 띄워 놓고 말만 하면 지루하다" → 뒤 문장은 떼어서 숫자 카드로.
        if c.get("kind") == "art" and (c.get("art") or {}).get("full"):
            if end > ART_LIMIT:
                out.append(f"{s['id']} 그림 장면이 {end:.0f}초다(최대 {ART_LIMIT:.0f}초) — "
                           f"뒤 문장을 떼어 숫자 카드로 만든다. 그림 위에 글줄을 더 얹지 않는다")
            continue
        if s is scenes[0] and has_thumb:
            continue                      # 첫 장면은 훅 대사가 끝날 때까지 썸네일(OpenHook)이 덮는다 — 카드가 아예 안 보인다
                                          # (JJ 2026-09-23 "그 대사가 끝날 때까지는 보여줘라"). 길이는 ART_LIMIT 이 따로 막는다.
        marks = [0.0] + [cues[a]["start"] for a in _piece_ats(c) if a < len(cues)]
        marks = sorted(set(marks)) + [end]
        worst, at_t = 0.0, 0.0
        for i in range(len(marks) - 1):
            d = marks[i + 1] - marks[i]
            if d > worst:
                worst, at_t = d, marks[i]
        if worst > gap:
            out.append(f"{s['id']} 화면이 {worst:.0f}초 동안 안 바뀐다(장면 {at_t:.0f}초부터) — "
                       f"말만 하고 그림이 멈춰 있다. 그 사이 문장에 화면 조각을 붙인다")
    return out


# 우리 색: 빨강 = 오른 것, 파랑 = 내린 것. 내려간 값을 빨강으로 그리면 거꾸로 읽힌다
# (JJ 2026-09-21: 9/23 에서 한 번 고쳤는데 9/30 에서 또 나왔다 → 검사기로)
_NUM = re.compile(r"[\d,]+(?:\.\d+)?")
BEFORE_WORDS = ("이전", "기존", "작년", "처음", "상장 첫날", "한 달 전", "석 달 전", "전날", "직전")
AFTER_WORDS = ("낮춘 뒤", "지금", "올해", "이후", "현재", "오늘", "낮춘", "뒤")


def _nums(s: str) -> list[float]:
    return [float(x.replace(",", "")) for x in _NUM.findall(str(s or "")) if x.strip(", ")]


def color_issues(scenes: list[dict], cards: dict) -> list[str]:
    """내려간 값인데 빨강으로 그려지는 곳을 잡는다."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        groups: list[tuple[str, list]] = []
        for key in ("bars", "rows"):
            if isinstance(c.get(key), list):
                groups.append((key, c[key]))
        for i, pn in enumerate(c.get("duo") or []):
            if isinstance(pn, dict) and isinstance(pn.get("bars"), list):
                groups.append((f"duo[{i}]", pn["bars"]))
        for tag, arr in groups:
            rows = [x for x in arr if isinstance(x, dict)]
            # ① "76 → 62" 처럼 화살표로 방향이 적힌 라벨
            for r in rows:
                vl = str(r.get("vlabel") or "")
                if "→" not in vl:
                    continue
                lo, hi = vl.split("→", 1)
                na, nb = _nums(lo), _nums(hi)
                if not (na and nb):
                    continue
                col = r.get("color")
                if nb[0] < na[0] and col not in ("blue", "grey"):
                    out.append(f"{s['id']}.{tag} '{vl}' 는 내려간 값인데 빨강으로 그려진다 — color: \"blue\"")
                if nb[0] > na[0] and col == "blue":
                    out.append(f"{s['id']}.{tag} '{vl}' 는 오른 값인데 파랑이다")
            # ② '이전 / 지금' 두 막대 짝
            if len(rows) == 2:
                a0, a1 = rows
                l0, l1 = str(a0.get("label") or ""), str(a1.get("label") or "")
                v0, v1 = a0.get("v"), a1.get("v")
                if (any(w in l0 for w in BEFORE_WORDS) and any(w in l1 for w in AFTER_WORDS)
                        and isinstance(v0, (int, float)) and isinstance(v1, (int, float))
                        and v1 < v0 and v1 >= 0 and a1.get("color") not in ("blue", "grey")):
                    out.append(f"{s['id']}.{tag} '{l0}({v0}) → {l1}({v1})' 는 내려간 값인데 빨강이다 — color: \"blue\"")
    return out


def _bar_vals(c: dict) -> list[tuple[str, list[float]]]:
    out = []
    for key in ("rows", "bars"):
        for holder, tag in ((c, key), (c.get("chart") if isinstance(c.get("chart"), dict) else None, f"chart.{key}")):
            v = (holder or {}).get(key)
            if isinstance(v, list):
                vals = [x["v"] for x in v if isinstance(x, dict) and isinstance(x.get("v"), (int, float))]
                if len(vals) >= 2:
                    out.append((tag, vals))
    for pn in (c.get("duo") or []):
        vals = [x["v"] for x in (pn.get("bars") or []) if isinstance(x.get("v"), (int, float))]
        if len(vals) >= 2:
            out.append(("duo." + str(pn.get("title"))[:10], vals))
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^가-힣0-9a-zA-Z]", "", str(s or ""))


def _card_texts(c, path="") -> list[tuple[str, str]]:
    out = []
    if isinstance(c, dict):
        for k, v in c.items():
            if k in ("kind", "src", "color", "tone", "at", "note_at", "v", "mode"):
                continue
            out += _card_texts(v, f"{path}.{k}" if path else k)
    elif isinstance(c, list):
        for i, v in enumerate(c):
            out += _card_texts(v, f"{path}[{i}]")
    elif isinstance(c, str):
        out.append((path, c))
    return out


def _lcs(a: str, b: str) -> int:
    """가장 긴 공통 토막 길이."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def echo_issues(scenes: list[dict], cards: dict) -> list[str]:
    """화면 글자가 자막 문장을 그대로 되풀이하면 안 된다 — JJ 2026-09-20
    "이미 자막이 밑에 쓰여지는데 그 위에 같은 걸 또 보이게 하는 장면을 만들었다고?"
    화면은 말이 못 하는 것(숫자·비교·그림)을 한다. 말을 다시 쓰는 건 화면이 아니다."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        sents = [_norm(x) for x in re.split(r"(?<=[.?!])\s+", (s.get("tts") or "").strip())]
        for path, txt in _card_texts(c):
            if path.startswith("q"):        # 장면 끝 질문은 화면에 그대로 띄우는 게 우리 포맷
                continue
            n = _norm(txt)
            if len(n) < 12:
                continue
            for sent in sents:
                if len(sent) < 12:
                    continue
                # 어미만 바꿔 놓은 것도 되풀이다("…또 달라진다" vs "…또 달라집니다") → 가장 긴 공통 토막으로 잰다
                m = _lcs(n, sent)
                if m >= 10 and m / len(n) >= 0.6:
                    out.append(f"{s['id']}.{path} 가 자막 문장을 되풀이한다({m}자 겹침) — \"{txt[:28]}\". 화면은 숫자·비교·그림으로(§17-6)")
                    break
    return out


def chart_issues(scenes: list[dict], cards: dict) -> list[str]:
    """막대가 정보를 주는지 — JJ 2026-09-20 "'지금/2028년' 막대는 무슨 의미야?".
    ① 값이 전부 같으면 막대가 아니라 장식이다.
    ② 가장 작은 막대가 가장 큰 것의 2% 미만이면 화면에 안 보인다(4,937 옆의 11.7) → 다른 카드로."""
    out: list[str] = []
    for s in scenes:
        c = cards.get(s["id"])
        if not isinstance(c, dict):
            continue
        for tag, vals in _bar_vals(c):
            if len(set(vals)) == 1:
                out.append(f"{s['id']}.{tag} 막대 값이 전부 {vals[0]} — 정보를 주지 않는 장식이다. 지우거나 진짜 숫자로")
                continue
            av = [abs(x) for x in vals if x]
            if av and min(av) / max(av) < 0.02:
                out.append(f"{s['id']}.{tag} 가장 작은 막대가 큰 것의 {min(av)/max(av)*100:.1f}% — 화면에 안 보인다. big(초대형 숫자)·score 처럼 다른 카드로")
    return out


def rhythm_issues(scenes: list[dict], cards: dict, beats: list[dict], d: str = "") -> list[str]:
    """한 편 안에서 화면이 지루해지지 않는지 — JJ 2026-09-20 "모든 영상이 같은 바그래프".
    ① 같은 카드 종류가 3연속이면 화면이 멈춘 것처럼 보인다.
    ② 첫 장면(훅)에 탐정이 나오면 뜬금없다 — 훅은 사건과 질문만.
    ③ **종이 카드 장면이 CARD_RUN_MAX 연속이면 실패**(2026-09-22) — 종류가 서로 달라도
       크림 종이 틀이 내리 이어지면 같은 화면으로 보인다. 9/21 실측: 15장면 중 11장면이 한 틀이었다.
       통계 구간(수치만 이어지는 대목)에서 특히 터진다. 그림 장면(art full)을 하나 끼워 끊는다.
       ※ 해법은 '그림을 잔뜩 늘리기'가 아니다 — 그림엔 글줄을 못 얹어 숫자를 못 싣는다.
         숫자는 카드에 두고, 마른 구간에만 그림을 한 장 끼우는 것이 규칙이다."""
    out: list[str] = []
    ids = [s["id"] for s in scenes if s["id"] in cards]
    run, prev = 1, None
    for i in ids:
        k = (cards[i] or {}).get("kind")
        if k and k == prev:
            run += 1
            if run >= 3:
                out.append(f"{i} 까지 '{k}' 카드가 {run}연속 — 화면이 같아 보인다. 하나를 다른 종류로")
        else:
            run, prev = 1, k
    if ids and d >= CARD_RUN_FROM:
        crun, worst, at = 0, 0, None
        for i in ids:
            c = cards.get(i) or {}
            is_art = c.get("kind") == "art" and (c.get("art") or {}).get("full")
            crun = 0 if is_art else crun + 1
            if crun > worst:
                worst, at = crun, i
        if worst >= CARD_RUN_MAX:
            out.append(f"{at} 까지 종이 카드 장면이 {worst}연속 — 종류가 달라도 같은 틀이라 지루하다. "
                       f"중간에 그림 장면(art full)을 하나 넣어 끊는다(최대 {CARD_RUN_MAX - 1}연속)")
    if scenes and beats:
        first = scenes[0]
        end = first.get("start", 0) + (first.get("frames") or 0) / 30
        if any(b.get("t", 1e9) < end for b in beats):
            out.append("첫 장면(훅)에 탐정이 나온다 — 뜬금없다. 훅은 사건과 질문만(§17-6)")
    return out


def texts(d: str, n: int = 1) -> Path:
    """업로드 문안 — 제목 끝 날짜(JJ 2026-09-19), 설명란, 태그(줄임말 몇 개), 쓰레드."""
    spec = load_json(spec_path(d, n)) or {}
    od = out_dir(d, ed_of(n))
    dt = datetime.strptime(d[:8], "%Y%m%d")
    # 정보형 제목엔 날짜를 넣지 않는다 — 업로드 날짜를 옮겨도 제목·영상을 안 고쳐도 된다(JJ 2026-09-21)
    title = tag_tail(spec.get("title") or "", spec.get("title_tag") or "증시 정보")
    src = "\n".join(f"· {s}" for s in (spec.get("sources") or []))
    desc = (f"{title}\n{spec.get('caption') or ''}\n\n출처\n{src}\n\n누가샀나는 평일 저녁 5시에 국장 마감 수급을 올립니다."
            f"\n자동 생성 · AI 음성 · 종목·매매 추천 아님\n\n{spec.get('hashtags') or '#누가샀나'}").strip()
    (od / "youtube_title.txt").write_text(title, encoding="utf-8")
    (od / "youtube_description.txt").write_text(desc[:5000], encoding="utf-8")
    (od / "youtube_tags.txt").write_text(", ".join(spec.get("tags") or []), encoding="utf-8")
    (od / "threads.txt").write_text(spec.get("threads") or "", encoding="utf-8")
    (od / "threads_reply.txt").write_text(spec.get("threads_reply") or "", encoding="utf-8")
    return od


def thumb_dissect(d: str, n: int = 1) -> None:
    """기업 해부 썸네일 — Remotion 스틸 DissectThumb(종이 바탕 + 맞선 두 그림 + 3줄). 국장 마감 썸네일과 한눈에 갈리게(JJ 9/19)."""
    comp = build(d, n)
    ed = ed_of(n)
    props = RENDER / f"props_{ed}_thumb.json"
    save_json(props, comp)
    od = out_dir(d, ed)
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    info = comp.get("info") or {}
    # thumbB = BoldThumb(어두운 바탕·초대형 글자·빨간 질문 띠·SVG 그림, 정보 영상 기본 — JJ 9/19 밤 Gemini 판 대신) → thumb_B.jpg
    # thumb2 = 경제사냥꾼 틀(글자 세로 50%+) · 없으면 DissectThumb → thumb_A.jpg
    # thumbS = SceneThumb(경제사냥꾼식 장면 그림 + 주사위 탐정 + 우리 글자 3줄 — 2026-09-20 부터 정보형 기본) → thumb_S.jpg
    # 썸네일 태그에도 날짜를 넣지 않는다(JJ 2026-09-21) — 날짜를 옮겨도 썸네일을 다시 안 그린다
    for _k in ("thumbS", "thumbB", "thumb"):
        if isinstance(info.get(_k), dict) and info[_k].get("tag"):
            info[_k]["tag"] = strip_date(info[_k]["tag"])
    if info.get("thumbS"):
        comp_id, name = "SceneThumb", "thumb_S.jpg"
    else:
        comp_id, name = ("BoldThumb", "thumb_B.jpg") if info.get("thumbB") else ("HunterThumb" if info.get("thumb2") else "DissectThumb", "thumb_A.jpg")
    r = subprocess.run([npx, "remotion", "still", "src/index.ts", comp_id, str(od / name), f"--props={props}", "--log=error", "--image-format=jpeg", "--jpeg-quality=92"],
                       cwd=str(RENDER), capture_output=True, text=True, encoding="utf-8", timeout=300)
    log(d, "info", f"썸네일(기업 해부 {comp_id} → {name}) {'완료' if r.returncode == 0 else '실패 ' + (r.stderr or r.stdout)[-300:]}")


def thumb(d: str, n: int = 1) -> None:
    spec = load_json(spec_path(d, n)) or {}
    if (spec.get("info") or {}).get("style") == "dissect":
        return thumb_dissect(d, n)
    lines = (spec.get("thumb") or {}).get("lines")
    if not lines:
        log(d, "info", "썸네일 문구 없음(thumb.lines) → 건너뜀")
        return
    ed = ed_of(n)
    info = spec.get("info") or {}
    ai_bg = RENDER / "public" / "bg" / f"ai_{d}_{ed}.jpg"
    t = {"out": f"out/{d}/{ed}", "cands": {"A": {"bg": (f"ai_{d}_{ed}" if ai_bg.exists() else (info.get("bg") or "city")), "tone": info.get("tone") or "neutral", "dim": 0.45,
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
    if stage in ("all", "ai"):
        ai(d, n)
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
