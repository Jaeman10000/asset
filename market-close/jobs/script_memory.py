"""전 편 기억 — 지금까지 만든 모든 편의 문장과 사실을 불러와, 오늘 대본이 (1) 같은 문장을 다시 쓰지 않고
(2) 이어지는 사실은 '오늘도·N일째'로 잇게 한다.

왜(JJ 2026-09-15): "매일 영상을 올리는데 올리는 대사가 똑같으면 안 돼. 비슷한 건 인정, 그런데 똑같으면 다시 보는
사람들은 '돌려막기네?' 하고 넘어가 버려. 모든 영상을 기억하고 오늘 영상을 만들 때 만들었던 영상들의 내용을 다
기억해서 연관지어서 해야 해. 오늘(9/15) 기타법인 대목을 월요일과 똑같이 말했다. '오늘도 마찬가지로 기타법인이
매수를 했습니다' 이런 식으로 연관 지었어야지."

네 가지 일:
  editions()        전 편 목록(평일 computed_kr.json — 없으면 computed.json, out/<날짜>_v*/kr/ 에만 남은 재렌더 판,
                    주간 script.json, 공지 notice_script.json). 같은 날의 여러 판(20260911_v8 …)도 모두 읽는다 —
                    시청자가 본 문장을 피하는 게 목적이라 많이 기억할수록 안전하다. 올라간 편은 aired(유튜브 id)를 단다.
  seen()/pick()     이미 쓴 문장(글자 그대로 / 숫자·단위만 다른 것)을 가려내고, 후보 중 새 문장을 고른다.
                    mask() 는 단위를 안다 — '1.2조'와 '9천억', '그 돈의'와 '이 가운데'는 같은 문장이다(9/14·9/15 가 그렇게 겹쳤다).
  continuity(d)     어제·그제와 이어지는 사실을 센다: 가장 많이 산 쪽이 며칠째 같은지, 기타법인이 며칠째 순매수인지(어느 두 종목·자사주까지),
                    주인공이 같은지, 가장 큰 돈이 움직인 업종이 같은지, 어제 약속이 며칠째 맞는지, 같은 질문을 며칠째 던지는지 —
                    대본은 이걸로 "오늘도 마찬가지로 …, 이틀째입니다" 를 만든다.
  record_history()  오늘 편을 data/script_history.json 에 한 줄로 남긴다(문장 raw/norm/mask/skeleton + 사실 + aired).
                    compute 가 computed_kr.json 을 저장한 뒤 매일 부른다. 실패해도 예외를 밖으로 내지 않는다(무인 제작을 막지 않는다).

사용(market-close/jobs 에서):
  python script_memory.py                 전 편 사실표 + 전 편끼리 겹친 문장
  python script_memory.py 20260915        그 편이 이전 편들과 겹친 문장(글자 그대로 / 숫자만 다름) + 이어짐 사실
  python script_memory.py --selftest      mask/skeleton/pick 자체 검사
  python script_memory.py --history 20260915 [경로]   그 편을 script_history.json(또는 경로)에 기록
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import DATA, OUT, load_json, save_json
import ledger
import weekend_watch

SIGNATURE = ("누가샀나였습니다", "국장 마감은 매일", "주간 결산이었습니다", "평일엔 매일", "정규장이 끝나도 저녁 8시까지",
             "우리는 같은 것을 봅니다",   # JJ 2026-09-17 고정 문장("내일도 우리는 같은 것을 봅니다")
             "오늘 주요 이슈를 보겠습니다")   # JJ 2026-09-17 s5 여는 문장 — 매일 같아도 된다(가이드 §9 빼지 않는 칸)
# 장부 문장(S6 관측값·S3a 회수) — 어제 던진 질문을 오늘 글자 그대로 되읽는 게 맞는 문장이라 겹침 검사에서 뺀다(HUNTER_FIXLIST B2).
LEDGER_FORM = (re.compile(r"순매[수도]가 .*(?:이어지는지|이어질 것인지)\.?$"), re.compile(r"을 지키는지\.?$"))
OVERLAP_WINDOW = 5          # check_hunter 가 보는 창: 올라간 편 가운데 최근 5편
_SPLIT = re.compile(r"(?<=[.?!])\s+")
_WS = re.compile(r"\s+")
_NUM = re.compile(r"[0-9][0-9,.]*")
_PUNCT = re.compile(r"[\s.,·!?'\"“”‘’()\[\]~\-–—…:;]")
INV = {"indiv": "개인", "foreign": "외국인", "inst": "기관", "others": "기타법인"}
GROUPS = ("기타법인", "외국인", "기관", "개인")           # 긴 것부터 — '기타법인' 안의 '기관'을 먼저 지우면 안 된다
HISTORY = DATA / "script_history.json"
_ED = {"kr": "kr", "weekly": "weekly", "weekly_us": "weekly_us", "notice": "notice"}   # kind → out/<폴더>/<ed>/

# ── mask 용: 숫자+단위, 한글 수사, 동의어 ──
# norm() 뒤에 쓰므로 숫자엔 쉼표·점이 없다('1.2조' → '12조'). 단위는 긴 것부터(일째 > 일).
_UNIT = r"(?:조|천억|억|천만|만|%|퍼센트|거래일째|거래일|일째|일|배|선|포인트|원|종목|번|시간|시|분|년|월|주째|주|회)?"
_NUM_UNIT = re.compile(r"약?\d+" + _UNIT)
_KO_DAYS = re.compile(r"(?:이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)째?")
_KO_COUNT = re.compile(r"(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)(?:번|배|개|종목|곳|시간|주|달|가지|명|건|칸|줄|회사)")
_SYN = (("그돈의", "#OF#"), ("이돈의", "#OF#"), ("이가운데", "#OF#"), ("그가운데", "#OF#"), ("그중", "#OF#"))
# 숫자를 지우면 조사만 남아 갈린다('9천억을' vs '1.2조를') — 숫자 뒤 조사는 한 쪽으로 몬다.
_JOSA = (("#(?:이었|였)", "#였"), ("#(?:이나|나)", "#나"), ("#(?:을|를)", "#을"), ("#(?:이|가)", "#이"),
         ("#(?:은|는)", "#은"), ("#(?:과|와)", "#과"), ("#(?:으로|로)", "#로"))
_JOSA_RE = tuple((re.compile(p), r) for p, r in _JOSA)

# ── skeleton 용(narrate_aplus._skeleton 을 따른다: 숫자→N, 주체→G, 날짜어→D) ──
_SK_DAYS = re.compile(r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘|\d+거래일|\d+일)째?")
_SK_NUM = re.compile(r"\d[\d,.]*\s?(?:조|천억|억|천만|만|%|퍼센트|선|포인트|배|거래일|원|종목|번|시간|시|분|년|월)?")
_SK_DATE = re.compile(r"(?:그제|어제|오늘|내일|전날|지난\s*[월화수목금토일]요일|[월화수목금토일]요일|이번\s*주|다음\s*주)")
_SK_JOSA = tuple((re.compile(p.replace("#", "N")), r.replace("#", "N")) for p, r in _JOSA)


# ── 문장 정규화 ──
def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split((text or "").strip()) if s.strip()]


def norm(s: str) -> str:
    """글자 그대로 비교용 — 공백·문장부호만 뺀다."""
    return _PUNCT.sub("", s or "")


def mask(s: str) -> str:
    """숫자·단위만 다른 문장을 같은 문장으로 보기 위한 형태. '약 1.2조를'과 '약 9천억을'이 같아지고,
    '닷새째'와 '5일째', '그 돈의 95%'와 '이 가운데 99%'도 같아진다(9/14·9/15 편이 이렇게 겹쳤는데 숫자 마스킹만으론 못 잡았다)."""
    x = norm(s)
    for a, b in _SYN:
        x = x.replace(a, b)
    x = _KO_COUNT.sub("#", x)
    x = _KO_DAYS.sub("#", x)
    x = _NUM_UNIT.sub("#", x)
    x = re.sub(r"#+", "#", x)                 # '1조 6,431억' → '##' → '#' ('1.6조'와 같게)
    for pat, rep in _JOSA_RE:
        x = pat.sub(rep, x)
    return x


def skeleton(s: str) -> str:
    """문장 뼈대 — 숫자→N, 주체(외국인·기관·개인·기타법인)→G, 날짜어(어제·오늘·N일째·지난 X요일)→D, 문장부호 제거.
    id 가 같아서가 아니라 '같은 소리로 들리면' 쓰지 않기 위한 형태(narrate_aplus._skeleton 과 같은 뜻)."""
    x = re.sub(r"약\s?", "", s or "")
    x = _SK_DAYS.sub("D", x)
    x = _SK_NUM.sub("N", x)
    for g in GROUPS:
        x = x.replace(g, "G")
    x = _SK_DATE.sub("D", x)
    x = _PUNCT.sub("", x)
    for pat, rep in _SK_JOSA:
        x = pat.sub(rep, x)
    return x


def is_signature(s: str) -> bool:
    return any(k in (s or "") for k in SIGNATURE)


# ── 전 편 불러오기 ──
def _date_of(folder: Path | str) -> str:
    name = folder.name if isinstance(folder, Path) else str(folder)
    m = re.match(r"(\d{8})", name)
    return m.group(1) if m else ""


def _scene_list(scenes) -> list[dict]:
    """scenes 가 목록이면 그대로, 사전(notice_script.json 의 {n0: 대사, …})이면 id 순 목록으로."""
    if isinstance(scenes, dict):
        return [{"id": k, "tts": v if isinstance(v, str) else (v or {}).get("tts") or ""} for k, v in sorted(scenes.items())]
    return [s for s in (scenes or []) if isinstance(s, dict)]


def _aired(folder: str, ed: str) -> dict | None:
    """올라간 편인지 — out/<폴더>/<ed>/publish.json(youtube.id 가 맨 위에 있는 판과 results.youtube.id 밑에 있는 판, 두 모양)
    또는 yt_link.txt(9/11 은 이것뿐). 없으면 None."""
    p = OUT / folder / ed
    pub = load_json(p / "publish.json") or {}
    yt = pub.get("youtube") if isinstance(pub, dict) else None
    if not isinstance(yt, dict):
        yt = (pub.get("results") or {}).get("youtube") if isinstance(pub, dict) and isinstance(pub.get("results"), dict) else None
    yt = yt if isinstance(yt, dict) else {}
    vid = yt.get("id")
    if not vid:
        try:
            txt = (p / "yt_link.txt").read_text(encoding="utf-8")
        except OSError:
            txt = ""
        m = re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]{6,})", txt)
        vid = m.group(1) if m else None
    if not vid:
        return None
    out = {"youtube_id": vid}
    if yt.get("title"):
        out["title"] = yt["title"]
    if yt.get("published_at") or yt.get("at"):
        out["published_at"] = yt.get("published_at") or yt.get("at")
    return out


def editions(before: str | None = None, kinds: tuple[str, ...] = ("kr", "weekly", "weekly_us", "notice")) -> list[dict]:
    """전 편 목록(날짜순). before 를 주면 그 날짜 미만만(오늘 편을 스스로와 비교하지 않게).
    평일편: data/<날짜*>/computed_kr.json → 없으면 computed.json(9/3) → data 에 없고 out/<날짜_v*>/kr/computed_kr.json 에만 있는 재렌더 판.
    공지편: data/<날짜>/notice_script.json(scenes 가 사전). 주간편: data/weekly*/<날짜>/script.json."""
    out: list[dict] = []
    if "kr" in kinds:
        have: set[str] = set()
        for folder in sorted(DATA.glob("2026*")):
            d = _date_of(folder)
            if not d or not folder.is_dir() or (before and d >= before):
                continue
            c = load_json(folder / "computed_kr.json") or load_json(folder / "computed.json")
            if not c or not c.get("scenes"):
                continue
            have.add(folder.name)
            out.append(_record("kr", d, folder.name, c, c["scenes"]))
        for folder in sorted(OUT.glob("2026*")):
            d = _date_of(folder)
            if not d or folder.name in have or (before and d >= before):
                continue
            c = load_json(folder / "kr" / "computed_kr.json")
            if not c or not c.get("scenes"):
                continue
            out.append(_record("kr", d, folder.name, c, c["scenes"], src="out"))
    if "notice" in kinds:
        for folder in sorted(DATA.glob("2026*")):
            d = _date_of(folder)
            if not d or (before and d >= before):
                continue
            n = load_json(folder / "notice_script.json")
            if not n or not n.get("scenes"):
                continue
            out.append(_record("notice", d, folder.name, n, n["scenes"]))
    for kind, sub in (("weekly", "weekly"), ("weekly_us", "weekly_us")):
        if kind not in kinds:
            continue
        for folder in sorted((DATA / sub).glob("2026*")):
            d = _date_of(folder)
            if not d or (before and d >= before):
                continue
            s = load_json(folder / "script.json")
            if not s or not s.get("scenes"):
                continue
            out.append(_record(kind, d, folder.name, s, s["scenes"]))
    out.sort(key=lambda r: (r["date"], r["folder"]))
    return out


def _record(kind: str, d: str, folder: str, c: dict, scenes, src: str = "data") -> dict:
    scs = _scene_list(scenes)
    rec_scenes = []
    for s in scs:
        row = {"id": s.get("id"), "tts": s.get("tts") or ""}
        if isinstance(s.get("steps"), list) and s["steps"]:      # 헌터 포맷은 문장별 단계 이름을 남긴다 → 슬롯 회전에 쓴다
            row["steps"] = list(s["steps"])
        if s.get("slot"):
            row["slot"] = s["slot"]
        rec_scenes.append(row)
    return {"kind": kind, "date": d, "folder": folder, "draft": "_" in folder, "src": src,
            "aired": _aired(folder, _ED.get(kind, kind)),
            "scenes": rec_scenes,
            "facts": facts(c) if kind == "kr" else _facts_other(kind, c, scs)}


_WEEKEND_PROMISE = {"weekly": ("w6", (weekend_watch._SAT_LEAD, weekend_watch._SAT_ALT)),
                    "weekly_us": ("uw6", (weekend_watch._SUN, weekend_watch._SUN_ALT))}


def _facts_other(kind: str, s: dict, scs: list[dict]) -> dict:
    """주간·공지편의 사실 — 월요일이 회수할 약속(watch)과 장면마다 던진 질문(asks).
    주말편은 watch 를 따로 저장하지 않아(2026-09-15 기준) 마지막 장면 대사에서 weekend_watch 와 같은 정규식으로 뽑는다."""
    watch = [w.get("q") for w in (s.get("watch") or []) if isinstance(w, dict) and w.get("q")]
    sid = None
    if not watch and kind in _WEEKEND_PROMISE:
        sid, pats = _WEEKEND_PROMISE[kind]
        q = weekend_watch._pick(s, sid, pats)
        if q:
            watch = [q]
    return {"title": s.get("title"), "watch": watch, "watch_family": [q_family(q) for q in watch],
            "promise_sid": sid if watch else None,
            "asks": [sc.get("ask") for sc in scs if isinstance(sc.get("ask"), str) and sc.get("ask").strip()]}


def _sign(v) -> int:
    return 0 if not isinstance(v, (int, float)) or v == 0 else (1 if v > 0 else -1)


def q_family(q: str) -> str | None:
    """'내일 볼 것' 한 줄의 질문 가족 — '외국인 순매도가 닷새째'와 '외국인 순매도가 엿새째'는 같은 질문이다.
    ledger.parse_q 가 읽는 형태면 그 kind·주체·부호로, 아니면 '주체+순매수/순매도' 또는 '테마+순매수/순매도'로."""
    q = (q or "").strip().rstrip(".")
    if not q:
        return None
    chk = ledger.parse_q(q)
    if chk:
        k = chk["kind"]
        if k == "inv_continue":
            return f"inv_continue:{chk.get('key')}:{chk.get('sign')}"
        if k == "kosdaq_break":
            return f"kosdaq_break:{chk.get('sign')}"
        return f"{k}:{chk.get('theme')}"
    m = re.search(r"(외국인|기관|개인|기타법인)\s*(순매수|순매도)", q)
    if m:
        return f"inv:{m.group(1)}:{1 if m.group(2) == '순매수' else -1}"
    m = re.search(r"([가-힣A-Za-z·]+)\s*(순매수|순매도)", q)
    if m:
        return f"theme:{m.group(1)}:{1 if m.group(2) == '순매수' else -1}"
    return None


def facts(c: dict) -> dict:
    """한 편의 사실 — 내일 편이 '이어짐'을 셀 때 쓰는 것만 뽑는다.
    top_theme 은 moves[0] 이 아니라 |t| 가 가장 큰 업종(narrate 가 s3 에서 말하는 그 업종) — 9/15 는 moves[0]=방산인데 말한 건 반도체였다."""
    inv = c.get("investors") or {}
    k = inv.get("kospi") if isinstance(inv.get("kospi"), dict) else {}
    pos = {n: v for n, v in k.items() if n in INV and isinstance(v, (int, float)) and v > 0}
    neg = {n: v for n, v in k.items() if n in INV and isinstance(v, (int, float)) and v < 0}
    top_buyer = max(pos, key=pos.get) if pos else None
    top_seller = min(neg, key=neg.get) if neg else None
    hook = c.get("hook") or {}
    pr = c.get("protagonist") or (hook.get("protagonist") if isinstance(hook, dict) else None) or {}
    moves = [m for m in (c.get("moves") or []) if isinstance(m, dict) and m.get("theme")]
    tm = c.get("top_move") if isinstance(c.get("top_move"), dict) and c["top_move"].get("theme") else None
    if tm is None and moves:
        tm = max(moves, key=lambda m: abs(m.get("t") or 0))
    top_move = {"theme": tm.get("theme"), "t": tm.get("t"), "streak": tm.get("streak")} if tm else None
    ev = c.get("event") if isinstance(c.get("event"), dict) else {}
    st = c.get("inv_streak") if isinstance(c.get("inv_streak"), dict) else {}
    cb = c.get("callback") if isinstance(c.get("callback"), dict) else {}
    chk = c.get("check") if isinstance(c.get("check"), dict) else {}
    verdict = chk.get("verdict") if isinstance(chk.get("verdict"), dict) else {}
    cb_kind = (cb.get("check") or {}).get("kind") if isinstance(cb.get("check"), dict) else None
    watch = [w.get("q") for w in (c.get("watch") or []) if isinstance(w, dict) and w.get("q")]
    others_top = [{"name": x.get("name"), "v": x.get("v"), "buyback": bool(x.get("buyback"))}
                  for x in (c.get("others_top") or []) if isinstance(x, dict) and x.get("name")]
    s2m = c.get("s2_marks") if isinstance(c.get("s2_marks"), dict) else {}
    return {
        "protagonist": pr.get("name") if isinstance(pr, dict) else None,
        "protagonist_amount": pr.get("amount") if isinstance(pr, dict) else None,
        "kospi": {n: k.get(n) for n in INV if n in k},
        "top_buyer": INV.get(top_buyer) if top_buyer else None,
        "top_seller": INV.get(top_seller) if top_seller else None,
        "others": k.get("others"),
        "others_top": others_top,
        "prev_others": s2m.get("prev"),
        "foreign_streak": (st.get("foreign") or {}).get("streak"),
        "inst_streak": (st.get("inst") or {}).get("streak"),
        "top_theme": top_move["theme"] if top_move else None,
        "top_move": top_move,
        "themes": {m["theme"]: m.get("t") for m in moves},
        "event_label": ev.get("label"),
        "event_group": ev.get("group"),
        "event_avg_pct": ev.get("avg_pct"),
        "hook_id": c.get("hook_id"),
        "devices": c.get("devices") or [],
        "caution_id": c.get("caution_id"),
        "watch": watch,
        "watch_family": [q_family(q) for q in watch],
        "callback": cb.get("q"),
        "callback_ok": cb.get("ok"),
        "callback_kind": cb_kind or verdict.get("kind"),
        "kospi_chg": (c.get("kospi") or {}).get("chg_pct") if isinstance(c.get("kospi"), dict) else None,
        "kosdaq_chg": (c.get("kosdaq") or {}).get("chg_pct") if isinstance(c.get("kosdaq"), dict) else None,
        "format": c.get("format"),
        "ep": c.get("ep"),
    }


# ── 이미 쓴 문장 ──
def _index(recs: list[dict], key_fn) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for r in recs:
        for sc in r["scenes"]:
            for s in sentences(sc["tts"]):
                if is_signature(s) or len(norm(s)) < 8:
                    continue
                idx.setdefault(key_fn(s), []).append(f"{r['date']}/{r['folder']}/{sc['id']}")
    return idx


def seen(before: str | None = None, recs: list[dict] | None = None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(글자 그대로 → [date/folder/scene], 숫자·단위 마스킹 → [...]). 시그니처는 뺀다."""
    recs = recs if recs is not None else editions(before)
    return _index(recs, norm), _index(recs, mask)


def skeletons(before: str | None = None, recs: list[dict] | None = None) -> dict[str, list[str]]:
    """뼈대 → [date/folder/scene]. 훅처럼 '같은 소리로 들리는' 문장까지 피하고 싶을 때."""
    return _index(recs if recs is not None else editions(before), skeleton)


def _units(c: str) -> list[str]:
    """후보를 비교 단위로 쪼갠다 — 문장 하나하나(길이 8 미만 문장·시그니처 제외). 전부 짧으면 후보 통째로 한 단위.
    후보가 두세 문장이면 그중 한 문장만 전 편에 있어도 겹친 후보다(리뷰 C1a·b: 통째 비교는 다문장 후보를 늘 '새 문장'으로 봤다)."""
    ss = [s for s in sentences(c) if not is_signature(s) and len(norm(s)) >= 8]
    return ss or [c]


def _hits(c: str, idx: dict, key_fn) -> int:
    return sum(len(idx.get(key_fn(s), [])) for s in _units(c))


def pick(cands: list[str], d: str, exact: dict | None = None, masked: dict | None = None,
         avoid: set[str] | None = None, offset: int = 0) -> str:
    """후보 문장 중 전 편에 없던 것을 고른다. 글자 그대로 겹치는 건 빼고, 숫자·단위만 다른 것도 되도록 피한다.
    비교는 **후보 안의 문장 단위** — 어느 한 문장이라도 exact/masked/avoid 에 있으면 그 후보는 겹친 것(길이 8 미만 문장은 안 본다).
    전부 겹치면 가장 덜 쓴 것. avoid(검사에서 걸린 원문 집합, norm 으로 비교)에 든 후보는 아예 빼며,
    그래서 후보가 다 빠지면 빈 문자열 — 부르는 쪽이 다른 슬롯 후보로 바꾼다. 후보가 비어도 빈 문자열.
    offset 은 회전 색인에 더하는 값 — 재시도(attempt)마다 다른 새 후보가 나오게 한다."""
    if avoid:
        av = {norm(a) for a in avoid} | {norm(s) for a in avoid for s in sentences(a) if len(norm(s)) >= 8}
        cands = [c for c in cands if norm(c) not in av and not any(norm(s) in av for s in _units(c))]
    if not cands:
        return ""
    if exact is None or masked is None:
        exact, masked = seen(d)
    fresh = [c for c in cands if not any(norm(s) in exact or mask(s) in masked for s in _units(c))]
    if fresh:
        return fresh[(int(d[-2:]) + int(offset or 0)) % len(fresh)]
    semi = [c for c in cands if not any(norm(s) in exact for s in _units(c))]
    if semi:
        return min(semi, key=lambda c: _hits(c, masked, mask))
    return min(cands, key=lambda c: _hits(c, exact, norm))


def _window(recs: list[dict], window: int | None, aired_only: bool) -> list[dict]:
    """겹침 검사 창. aired_only: 올라간 편(aired 가 있거나 접미사 없는 본판) — 안 올라간 초안(_v5·_v7 …)은 시청자가 못 봤다.
    window: 최근 N편(날짜 기준, 오늘 이전)만. 둘 다 없으면 전 편(리포트용 CLI 기본)."""
    if aired_only:
        recs = [r for r in recs if r.get("aired") or not r.get("draft")]
    if window:
        keep = set(sorted({r["date"] for r in recs}, reverse=True)[:window])
        recs = [r for r in recs if r["date"] in keep]
    return recs


def _exempt(s: str, pats) -> bool:
    t = (s or "").strip()
    for p in pats or ():
        if (p.search(t) if hasattr(p, "search") else re.search(p, t)):
            return True
    return False


def overlaps(d: str, scenes: list[dict], recs: list[dict] | None = None, with_skeleton: bool = False,
             window: int | None = None, aired_only: bool = False, exempt=()) -> list[dict]:
    """오늘 대본이 이전 편들과 겹치는 문장. kind: exact(글자 그대로) / numbers(숫자·단위만 다름) / skeleton(with_skeleton 일 때, 뼈대만 같음).
    window=N 이면 최근 N편만, aired_only 면 올라간 편(초안 제외)만 본다 — check_hunter 는 window=5·aired_only=True·exempt=LEDGER_FORM 으로 부른다(B2).
    CLI 리포트는 기본값(전 편)으로 본다. exempt 는 정규식(문자열/컴파일) 목록 — 맞는 오늘 문장은 검사하지 않는다."""
    recs = _window(recs if recs is not None else editions(d), window, aired_only)
    exact, masked = seen(d, recs)
    sk = skeletons(d, recs) if with_skeleton else {}
    out = []
    for sc in _scene_list(scenes):
        for s in sentences(sc.get("tts") or ""):
            if is_signature(s) or len(norm(s)) < 8 or _exempt(s, exempt):
                continue
            if norm(s) in exact:
                out.append({"scene": sc.get("id"), "kind": "exact", "sentence": s, "seen": exact[norm(s)]})
            elif mask(s) in masked:
                out.append({"scene": sc.get("id"), "kind": "numbers", "sentence": s, "seen": masked[mask(s)]})
            elif with_skeleton and skeleton(s) in sk:
                out.append({"scene": sc.get("id"), "kind": "skeleton", "sentence": s, "seen": sk[skeleton(s)]})
    return out


# ── 이어지는 사실 ──
def _prev(d: str, n: int = 10, kinds: tuple[str, ...] = ("kr",)) -> list[dict]:
    """d 직전 편들(최신부터). 같은 날 여러 판이면 접미사 없는 것(올라간 판)을, 없으면 마지막 판을 쓴다."""
    by_key: dict[tuple, dict] = {}
    for r in editions(before=d, kinds=kinds):
        key = (r["date"], r["kind"])
        if key not in by_key or not r["draft"]:
            by_key[key] = r
    return [by_key[k] for k in sorted(by_key, reverse=True)[:n]]


def _prev_kr(d: str, n: int = 10) -> list[dict]:
    return _prev(d, n, ("kr",))


def _others_key(f: dict) -> tuple | None:
    """기타법인이 산 상위 두 종목 + 둘 다 자사주 매입 중인지 — 이게 같으면 '오늘도 그 두 회사' 다."""
    ot = f.get("others_top") or []
    names = tuple(sorted(x.get("name") for x in ot if x.get("name")))
    return (names, all(x.get("buyback") for x in ot)) if names else None


def continuity(d: str, today: dict) -> dict:
    """오늘 사실(facts(comp))이 어제·그제와 얼마나 이어지는지. 대본은 이걸로 '오늘도 … N일째' 를 만든다.
    '일째'는 편 수(오늘 포함)다 — 주말을 건너뛰어도 편이 이어지면 센다.

    반환:
      top_buyer_days        오늘 가장 많이 산 쪽이 며칠째 같은지(오늘 포함, 1이면 오늘이 처음)
      others_buy_days       기타법인이 며칠째 순매수인지(오늘 포함, 오늘 순매수가 아니면 0). 이력 전체를 거슬러 센다(10편 제한 없음)
      others_buy_days_capped 그 연속이 이력 첫 편(또는 수급 자료가 없는 편)까지 닿아 실제론 더 길 수 있으면 True — 대본은 "N일째" 대신
                            "9월 들어 매일"/"N일째 이상"으로 말한다(M-3: 9/15 의 '여드레째'는 자료 창 길이였다)
      history_first_date    이력의 첫 편 날짜(평일편, 없으면 None) · others_first_date: 기타법인 연속이 닿은 가장 이른 편 날짜
      others_top_same_days  기타법인이 산 상위 두 종목(과 자사주 여부)이 며칠째 같은지(오늘 포함, 자료 없으면 0)
      protagonist_days      주인공이 며칠째 같은지(오늘 포함)
      protagonist_sign_days 주인공이 같은 방향(팔았다/샀다)으로 며칠째인지(주인공 없으면 0)
      top_move_days         가장 큰 돈이 움직인 업종이 같은 방향으로 며칠째인지(오늘 포함, 자료 없으면 0)
      callback_chain        같은 종류의 어제 약속이 며칠째 연속 '이어짐'인지(오늘 약속이 맞았을 때만, 아니면 0)
      promise_days          오늘 던지는 '내일 볼 것'이 며칠째 같은 질문 가족인지(오늘 포함, 없으면 0)
      event_repeat_days     같은 이슈 라벨이 며칠 안에 있었는지(0이면 없음)
      yesterday             어제 편 사실(없으면 None)
      said_yesterday        어제 편 문장 목록(회수용)
    """
    prev = _prev(d)
    y = prev[0]["facts"] if prev else None
    prev_all = _prev(d, n=10 ** 6)          # 연속일은 이력 전체로 센다(10편 창이면 열흘 넘는 연속이 잘린다)

    def run(key_fn) -> int:
        n = 1
        for r in prev:
            if key_fn(r["facts"]):
                n += 1
            else:
                break
        return n

    tb = today.get("top_buyer")
    pn, pa = today.get("protagonist"), today.get("protagonist_amount")
    ot_key = _others_key(today)
    tm = today.get("top_move") or {}
    tm_theme, tm_sign = tm.get("theme"), _sign(tm.get("t"))
    fam = next((f for f in (today.get("watch_family") or []) if f), None)
    cb_ok, cb_kind = today.get("callback_ok") is True, today.get("callback_kind")
    ob_days, ob_capped, ob_first = 0, False, None
    if (today.get("others") or 0) > 0:
        ob_days, ob_first, ob_capped = 1, d, True          # 이력이 없으면 오늘이 곧 첫 편 — 닿았다
        for r in prev_all:
            v = r["facts"].get("others")
            if not isinstance(v, (int, float)):         # 수급 자료가 없는 편(9/3) — 여기서 자료가 끊긴다
                break
            if v <= 0:
                ob_capped = False
                break
            ob_days += 1
            ob_first = r["date"]
    out = {
        "top_buyer_days": run(lambda f: tb is not None and f.get("top_buyer") == tb),
        "others_buy_days": ob_days,
        "others_buy_days_capped": ob_capped,
        "others_first_date": ob_first,
        "history_first_date": prev_all[-1]["date"] if prev_all else None,
        "others_top_same_days": run(lambda f: _others_key(f) == ot_key) if ot_key else 0,
        "protagonist_days": run(lambda f: today.get("protagonist") and f.get("protagonist") == today.get("protagonist")),
        "protagonist_sign_days": run(lambda f: f.get("protagonist") == pn and _sign(f.get("protagonist_amount")) == _sign(pa)) if pn else 0,
        "top_move_days": run(lambda f: (f.get("top_move") or {}).get("theme") == tm_theme
                             and _sign((f.get("top_move") or {}).get("t")) == tm_sign) if tm_theme else 0,
        "callback_chain": run(lambda f: f.get("callback_ok") is True and f.get("callback_kind") == cb_kind) if cb_ok else 0,
        "promise_days": run(lambda f: fam in (f.get("watch_family") or [])) if fam else 0,
        "event_repeat_days": 0,
        "yesterday": y,
        "said_yesterday": [s for sc in (prev[0]["scenes"] if prev else []) for s in sentences(sc["tts"])],
    }
    if today.get("event_label"):
        for i, r in enumerate(prev, 1):
            if r["facts"].get("event_label") == today["event_label"]:
                out["event_repeat_days"] = i
                break
    return out


def said_within(d: str, needle: str, n: int = 3, kinds: tuple[str, ...] = ("kr",)) -> bool:
    """최근 n편 대사에 이 말이 있었으면 True — 용어 설명을 매일 되풀이하지 않는다(narrate_aplus._said_recently 와 같은 뜻,
    다만 editions() 를 써서 computed.json 만 있는 편·재렌더 판도 본다)."""
    return any(needle in sc["tts"] for r in _prev(d, n, kinds) for sc in r["scenes"])


def glossary_said_within(d: str, term: str, n: int = 3) -> bool:
    """이 용어를 최근 n편 안에서 설명했거나 입에 올렸으면 True.
    data/glossary_log.json(처음 설명한 날)이 그 창 안에 있거나, 최근 n편 문장에 용어가 나오면 — 둘 중 하나면 다시 풀어 쓰지 않는다."""
    prev = _prev(d, n)
    if not prev:
        return False
    g = load_json(DATA / "glossary_log.json") or {}
    first = g.get(term) if isinstance(g, dict) else None
    if isinstance(first, str) and prev[-1]["date"] <= first < d:
        return True
    return any(term in sc["tts"] for r in prev for sc in r["scenes"])


def _slot_tags(rec: dict) -> set[str]:
    """한 편이 쓴 슬롯 태그 — 장면의 slot, 장면 steps('s2:reveal'), 기록 파일의 문장별 slot."""
    tags: set[str] = set()
    for sc in rec.get("scenes") or []:
        if sc.get("slot"):
            tags.add(sc["slot"])
        for st in sc.get("steps") or []:
            tags.add(f"{sc.get('id')}:{st}")
    for s in rec.get("sentences") or []:
        if s.get("slot"):
            tags.add(s["slot"])
    return tags


def slot_last_used(d: str, slot_tag: str, kinds: tuple[str, ...] = ("kr",)) -> str | None:
    """이 슬롯 태그를 마지막으로 쓴 편의 날짜(d 이전). 편이 슬롯 태그(scenes[].steps / slot)를 남길 때만 뜻이 있다 — 없으면 None."""
    last = None
    for r in editions(before=d, kinds=kinds):
        if slot_tag in _slot_tags(r):
            last = r["date"]
    for r in history():
        if r.get("date", "") < d and r.get("kind") in kinds and slot_tag in _slot_tags(r):
            last = max(last or "", r["date"])
    return last


def days_ko(n: int) -> str:
    return {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레", 8: "여드레", 9: "아흐레", 10: "열흘"}.get(n, f"{n}일")


# ── 기록 파일(data/script_history.json) ──
def history(path: Path | None = None) -> list[dict]:
    """기록 파일의 편 목록(없으면 빈 목록)."""
    j = load_json(path or HISTORY) or {}
    return [e for e in (j.get("editions") or []) if isinstance(e, dict)] if isinstance(j, dict) else []


def record_history(d: str, comp: dict, kind: str = "kr", folder: str | None = None, path: Path | None = None) -> dict | None:
    """오늘 편 한 줄을 기록 파일에 넣는다(같은 kind·folder 면 덮어씀). compute 가 computed_kr.json 을 저장한 뒤 부른다.
    문장은 raw/norm/mask/skeleton 네 모양으로(내일 pick 이 그대로 비교), 사실은 facts(), 올라갔으면 aired.
    지난 편 중 aired 가 비어 있던 것은 다시 확인해 채운다(업로드는 compute 뒤에 일어나므로 당일엔 늘 비어 있다).
    실패해도 예외를 내지 않고 None — 무인 제작(15:55)이 기록 하나 때문에 멈추면 안 된다."""
    path = path or HISTORY
    try:
        folder = folder or d
        rec = _record(kind, d, folder, comp, comp.get("scenes") or [])
        if not rec["scenes"]:
            return None
        f = rec["facts"]
        sents = []
        for sc in rec["scenes"]:
            steps = sc.get("steps") or []
            for i, s in enumerate(sentences(sc["tts"])):
                row = {"scene": sc["id"], "i": i, "raw": s, "norm": norm(s), "mask": mask(s), "skeleton": skeleton(s)}
                if i < len(steps):
                    row["slot"] = f"{sc['id']}:{steps[i]}"
                elif sc.get("slot"):
                    row["slot"] = sc["slot"]
                sents.append(row)
        entry = {"date": d, "kind": kind, "folder": folder, "draft": rec["draft"], "aired": rec["aired"],
                 "format": f.get("format"), "ep": f.get("ep"), "hook_id": f.get("hook_id"),
                 "devices": f.get("devices") or [], "caution_id": f.get("caution_id"),
                 "sentences": sents, "facts": f, "recorded_at": datetime.now().isoformat(timespec="seconds")}
        if kind != "kr":
            entry["asks"] = f.get("asks") or []
        j = load_json(path) or {}
        eds = [e for e in (j.get("editions") or []) if isinstance(e, dict)
               and not (e.get("kind") == kind and e.get("folder") == folder)]
        for e in eds:
            if not e.get("aired"):
                e["aired"] = _aired(e.get("folder") or e.get("date") or "", _ED.get(e.get("kind") or "kr", "kr"))
        eds.append(entry)
        eds.sort(key=lambda e: (e.get("date") or "", e.get("folder") or ""))
        save_json(path, {"version": 1, "updated_at": datetime.now().isoformat(timespec="seconds"), "editions": eds})
        return entry
    except Exception as e:  # noqa: BLE001 — 기록은 부가 작업, 제작을 막지 않는다
        try:
            from _common import log
            log(d, "memory", f"⚠ script_history 기록 실패: {e!r}")
        except Exception:
            print(f"script_history 기록 실패: {e!r}", file=sys.stderr)
        return None


# ── 자체 검사 ──
def selftest() -> None:
    """mask/skeleton/pick 이 약속대로 움직이는지 — 9/14·9/15 가 겹친 그 문장들로 확인한다."""
    assert mask("기관도 외국인처럼 약 1.2조를 팔았습니다.") == mask("기관도 외국인처럼 약 9천억을 팔았습니다."), "단위가 다른 금액"
    assert mask("그 돈의 95%는 A와 B였습니다") == mask("이 가운데 99%는 A와 B였습니다"), "그 돈의/이 가운데"
    assert mask("외국인 순매도가 닷새째 이어지는지.") == mask("외국인 순매도가 엿새째 이어지는지.") == mask("외국인 순매도가 4일째 이어지는지."), "한글 수사"
    assert mask("약 1조 6,431억을 샀습니다.") == mask("약 1.6조를 샀습니다."), "조+억 두 토막"
    assert mask("기타법인도 약 1.5조를 샀습니다.") != mask("개인도 약 8,300억을 샀습니다."), "주체가 다르면 다른 문장"
    assert skeleton("외국인이 닷새째, 오늘만 1.6조를 팔았습니다.") == skeleton("기관이 이틀째, 어제만 약 9천억을 팔았습니다."), "뼈대"
    assert skeleton("오늘 외국인이 내놓은 1.6조, 누가 받았을까요?") != skeleton("그럼 오늘 누가 샀을까요?"), "다른 뼈대"
    ex, mk = {norm("A 문장입니다 하나"): ["x"]}, {}
    assert pick(["A 문장입니다 하나", "B 문장입니다 둘"], "20260916", ex, mk) == "B 문장입니다 둘", "exact 회피"
    assert pick(["A 문장입니다 하나", "B 문장입니다 둘"], "20260916", ex, mk, avoid={"B 문장입니다 둘."}) == "A 문장입니다 하나", "avoid 는 norm 으로 비교"
    assert pick(["B 문장입니다 둘"], "20260916", {}, {}, avoid={"B 문장입니다 둘"}) == "", "avoid 로 다 빠지면 빈 문자열"
    # B1: 후보 안의 한 문장만 겹쳐도 그 후보는 겹친 것
    two = "그런데 막대 밑을 보세요. 이름이 둘 붙습니다."
    assert pick([two, "C 문장입니다 셋"], "20260916", {}, {}, avoid={"이름이 둘 붙습니다."}) == "C 문장입니다 셋", "avoid 는 문장 단위"
    assert pick([two, "C 문장입니다 셋"], "20260916", {norm("이름이 둘 붙습니다"): ["x"]}, {}) == "C 문장입니다 셋", "exact 는 문장 단위"
    two_n = "그런데 막대 밑을 보세요. 기타법인 1조 6천억을 샀습니다."
    assert pick([two_n, "C 문장입니다 셋"], "20260916", {}, {mask("기타법인 9천억을 샀습니다"): ["x"]}) == "C 문장입니다 셋", "masked 는 문장 단위"
    assert pick([two], "20260916", {norm("이름이 둘 붙습니다"): ["x"]}, {}) == two, "다 겹치면 가장 덜 쓴 것"
    assert pick(["A 문장입니다 하나", "B 문장입니다 둘"], "20260916", {}, {}, offset=1) != pick(["A 문장입니다 하나", "B 문장입니다 둘"], "20260916", {}, {}), "offset 회전"
    # B2: 창·올라간 편·장부 문장 예외
    mk = lambda dt, folder, tts, aired=None: {"kind": "kr", "date": dt, "folder": folder, "draft": "_" in folder, "aired": aired,
                                              "scenes": [{"id": "s6", "tts": tts}], "facts": {}}
    recs = [mk("20260901", "20260901", "아주 오래된 문장입니다 하나."), mk("20260911", "20260911_v8", "초안에만 있던 문장입니다."),
            mk("20260915", "20260915", "외국인 순매도가 엿새째 이어지는지. 기타법인 순매수가 1조 4천억을 지키는지. 어제 문장입니다 그대로.", {"youtube_id": "x"})]
    today = [{"id": "s3a", "tts": "외국인 순매도가 엿새째 이어지는지. 어제 문장입니다 그대로. 초안에만 있던 문장입니다. 아주 오래된 문장입니다 하나."}]
    hit = lambda **kw: sorted(o["sentence"] for o in overlaps("20260916", today, recs, **kw) if o["kind"] == "exact")
    assert hit() == sorted(["외국인 순매도가 엿새째 이어지는지.", "어제 문장입니다 그대로.", "초안에만 있던 문장입니다.", "아주 오래된 문장입니다 하나."]), "기본은 전 편·전 문장"
    assert hit(aired_only=True) == sorted(["외국인 순매도가 엿새째 이어지는지.", "어제 문장입니다 그대로.", "아주 오래된 문장입니다 하나."]), "초안 제외"
    assert hit(window=1, aired_only=True) == sorted(["외국인 순매도가 엿새째 이어지는지.", "어제 문장입니다 그대로."]), "최근 1편 창"
    assert hit(window=1, aired_only=True, exempt=LEDGER_FORM) == ["어제 문장입니다 그대로."], "장부 문장 예외"
    assert q_family("외국인 순매도가 닷새째 이어지는지") == q_family("외국인 순매도가 4일째 이어지는지") == "inv_continue:foreign:-1"
    assert q_family("반도체 순매수가 이틀째 이어지는지") == "theme_continue:반도체"
    print("selftest ok")
    recs = editions()
    kinds = {(r["kind"], r["folder"]) for r in recs}
    print(f"  editions={len(recs)} kinds={sorted({r['kind'] for r in recs})} "
          f"0903(computed.json)={'20260903' in {r['folder'] for r in recs}} v5(out)={('kr', '20260911_v5') in kinds} "
          f"notice={('notice', '20260913') in kinds} aired={[r['folder'] for r in recs if r.get('aired')]}")


# ── CLI ──
def _print_table(recs: list[dict]) -> None:
    print(f"{'date':9} {'folder':18} {'kind':9} {'aired':11} {'주인공':6} {'가장 산 쪽':8} {'기타법인':>8} {'외인연속':>6} {'top테마':8} {'훅':4} 이슈 / 내일 볼 것")
    for r in recs:
        f = r["facts"]
        yt = (r.get("aired") or {}).get("youtube_id") or "-"
        if r["kind"] != "kr":
            print(f"{r['date']:9} {r['folder']:18} {r['kind']:9} {yt:11} watch={f.get('watch')} asks={len(f.get('asks') or [])}")
            continue
        print(f"{r['date']:9} {r['folder']:18} {r['kind']:9} {yt:11} {str(f.get('protagonist') or '-'):6} {str(f.get('top_buyer') or '-'):8} "
              f"{str(f.get('others') or '-'):>8} {str(f.get('foreign_streak') or '-'):>6} {str(f.get('top_theme') or '-'):8} "
              f"{str(f.get('hook_id') or '-'):4} {f.get('event_label') or '-'} / {f.get('watch')}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--selftest":
        selftest()
        return
    if args and args[0] == "--history":
        d = args[1]
        path = Path(args[2]) if len(args) > 2 else None
        comp = load_json(DATA / d / "computed_kr.json") or load_json(DATA / d / "computed.json")
        if not comp:
            print(f"{d} 평일편 없음")
            return
        e = record_history(d, comp, path=path)
        print(f"기록: {path or HISTORY} ← {d} 문장 {len(e['sentences']) if e else 0}개, aired={e.get('aired') if e else None}")
        return
    if args:
        d = args[0]
        recs_today = [r for r in editions(kinds=("kr",)) if r["date"] == d and not r["draft"]]
        if not recs_today:
            print(f"{d} 평일편 없음")
            return
        today = recs_today[-1]
        print(f"== {d} 가 이전 편들과 겹친 문장  (aired={today.get('aired')})")
        ov = overlaps(d, today["scenes"])
        for o in ov:
            print(f"  [{o['kind']:7}] ({o['scene']}) {o['sentence'][:70]}  ← {', '.join(o['seen'][:3])}")
        if not ov:
            print("  없음")
        f = today["facts"]
        c = continuity(d, f)
        ot = "·".join(x["name"] for x in f.get("others_top") or []) or "-"
        tm = f.get("top_move") or {}
        print(f"== 이어짐: 가장 산 쪽 {f.get('top_buyer')} {c['top_buyer_days']}일째 · 기타법인 순매수 {c['others_buy_days']}일째"
              f"({ot} {c['others_top_same_days']}일째) · 주인공 {f.get('protagonist')} {c['protagonist_days']}일째(같은 방향 {c['protagonist_sign_days']}일째)"
              f" · 큰 돈 {tm.get('theme')} {'유출' if _sign(tm.get('t')) < 0 else '유입'} {c['top_move_days']}일째"
              f" · 약속 적중 연속 {c['callback_chain']} · 같은 질문 {c['promise_days']}일째 · 이슈 반복 {c['event_repeat_days']}일 전")
        print(f"== 최근 3편: 자사주 말함={said_within(d, '자사주')} · 기타법인 용어={glossary_said_within(d, '기타법인')} · 거래대금 용어={glossary_said_within(d, '거래대금')}")
        return
    recs = editions()
    _print_table(recs)
    print()
    print("== 전 편끼리 글자 그대로 겹친 문장(시그니처 제외)")
    exact, masked = seen(recs=recs)
    for s, where in exact.items():
        dates = sorted({w.split('/')[0] for w in where})
        if len(dates) >= 2:
            print(f"  {s[:60]}  ← {', '.join(dates)}")
    print("== 전 편끼리 숫자·단위만 다른 문장(글자 그대로 겹친 건 제외)")
    exact_multi = {mask(e) for e, ws in exact.items() if len({w.split('/')[0] for w in ws}) >= 2}
    for m, where in masked.items():
        dates = sorted({w.split('/')[0] for w in where})
        if len(dates) >= 2 and m not in exact_multi:
            print(f"  {m[:60]}  ← {', '.join(dates)}")


if __name__ == "__main__":
    main()
