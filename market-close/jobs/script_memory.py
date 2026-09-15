"""전 편 기억 — 지금까지 만든 모든 편의 문장과 사실을 불러와, 오늘 대본이 (1) 같은 문장을 다시 쓰지 않고
(2) 이어지는 사실은 '오늘도·N일째'로 잇게 한다.

왜(JJ 2026-09-15): "매일 영상을 올리는데 올리는 대사가 똑같으면 안 돼. 비슷한 건 인정, 그런데 똑같으면 다시 보는
사람들은 '돌려막기네?' 하고 넘어가 버려. 모든 영상을 기억하고 오늘 영상을 만들 때 만들었던 영상들의 내용을 다
기억해서 연관지어서 해야 해. 오늘(9/15) 기타법인 대목을 월요일과 똑같이 말했다. '오늘도 마찬가지로 기타법인이
매수를 했습니다' 이런 식으로 연관 지었어야지."

세 가지 일:
  editions()        전 편 목록(평일 computed_kr.json, 주간 script.json). 같은 날의 여러 판(20260911_v8 …)도 모두 읽는다 —
                    시청자가 본 문장을 피하는 게 목적이라 많이 기억할수록 안전하다.
  seen()/pick()     이미 쓴 문장(글자 그대로 / 숫자만 다른 것)을 가려내고, 후보 중 새 문장을 고른다.
  continuity(d)     어제·그제와 이어지는 사실을 센다: 가장 많이 산 쪽이 며칠째 같은지, 기타법인이 며칠째 순매수인지,
                    주인공이 같은지, 이슈가 반복인지 — 대본은 이걸로 "오늘도 마찬가지로 …, 이틀째입니다" 를 만든다.

사용(market-close/jobs 에서):
  python script_memory.py                 전 편 사실표 + 전 편끼리 겹친 문장
  python script_memory.py 20260915        그 편이 이전 편들과 겹친 문장(글자 그대로 / 숫자만 다름) + 이어짐 사실
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import DATA, load_json

SIGNATURE = ("누가샀나였습니다", "국장 마감은 매일", "주간 결산이었습니다", "평일엔 매일", "정규장이 끝나도 저녁 8시까지")
_SPLIT = re.compile(r"(?<=[.?!])\s+")
_WS = re.compile(r"\s+")
_NUM = re.compile(r"[0-9][0-9,.]*")
_PUNCT = re.compile(r"[\s.,·!?'\"“”‘’()\[\]~\-–—…:;]")
INV = {"indiv": "개인", "foreign": "외국인", "inst": "기관", "others": "기타법인"}


# ── 문장 정규화 ──
def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split((text or "").strip()) if s.strip()]


def norm(s: str) -> str:
    """글자 그대로 비교용 — 공백·문장부호만 뺀다."""
    return _PUNCT.sub("", s or "")


def mask(s: str) -> str:
    """숫자만 다른 문장을 같은 문장으로 보기 위한 형태. '1.6조'와 '3.3조'가 같아진다."""
    return _NUM.sub("#", norm(s))


def is_signature(s: str) -> bool:
    return any(k in (s or "") for k in SIGNATURE)


# ── 전 편 불러오기 ──
def _date_of(folder: Path) -> str:
    m = re.match(r"(\d{8})", folder.name)
    return m.group(1) if m else ""


def editions(before: str | None = None, kinds: tuple[str, ...] = ("kr", "weekly", "weekly_us")) -> list[dict]:
    """전 편 목록(날짜순). before 를 주면 그 날짜 미만만(오늘 편을 스스로와 비교하지 않게)."""
    out: list[dict] = []
    if "kr" in kinds:
        for folder in sorted(DATA.glob("2026*")):
            d = _date_of(folder)
            if not d or (before and d >= before):
                continue
            c = load_json(folder / "computed_kr.json")
            if not c or not c.get("scenes"):
                continue
            out.append(_record("kr", d, folder, c, c.get("scenes") or []))
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
            out.append(_record(kind, d, folder, s, s.get("scenes") or []))
    out.sort(key=lambda r: (r["date"], r["folder"]))
    return out


def _record(kind: str, d: str, folder: Path, c: dict, scenes: list[dict]) -> dict:
    return {"kind": kind, "date": d, "folder": folder.name, "draft": "_" in folder.name,
            "scenes": [{"id": s.get("id"), "tts": s.get("tts") or ""} for s in scenes],
            "facts": facts(c) if kind == "kr" else {"watch": [w.get("q") for w in (c.get("watch") or []) if isinstance(w, dict)]}}


def facts(c: dict) -> dict:
    """한 편의 사실 — 내일 편이 '이어짐'을 셀 때 쓰는 것만 뽑는다."""
    inv = c.get("investors") or {}
    k = inv.get("kospi") if isinstance(inv.get("kospi"), dict) else {}
    pos = {n: v for n, v in k.items() if n in INV and isinstance(v, (int, float)) and v > 0}
    neg = {n: v for n, v in k.items() if n in INV and isinstance(v, (int, float)) and v < 0}
    top_buyer = max(pos, key=pos.get) if pos else None
    top_seller = min(neg, key=neg.get) if neg else None
    hook = c.get("hook") or {}
    pr = c.get("protagonist") or (hook.get("protagonist") if isinstance(hook, dict) else None) or {}
    moves = c.get("moves") or []
    ev = c.get("event") or {}
    st = c.get("inv_streak") or {}
    return {
        "protagonist": pr.get("name") if isinstance(pr, dict) else None,
        "protagonist_amount": pr.get("amount") if isinstance(pr, dict) else None,
        "kospi": {n: k.get(n) for n in INV if n in k},
        "top_buyer": INV.get(top_buyer) if top_buyer else None,
        "top_seller": INV.get(top_seller) if top_seller else None,
        "others": k.get("others"),
        "foreign_streak": (st.get("foreign") or {}).get("streak"),
        "inst_streak": (st.get("inst") or {}).get("streak"),
        "top_theme": (moves[0].get("theme") if moves else None),
        "themes": {m.get("theme"): m.get("t") for m in moves if m.get("theme")},
        "event_label": ev.get("label"),
        "event_avg_pct": ev.get("avg_pct"),
        "hook_id": c.get("hook_id"),
        "devices": c.get("devices") or [],
        "caution_id": c.get("caution_id"),
        "watch": [w.get("q") for w in (c.get("watch") or []) if isinstance(w, dict)],
        "callback": (c.get("callback") or {}).get("q") if isinstance(c.get("callback"), dict) else None,
        "callback_ok": (c.get("callback") or {}).get("ok") if isinstance(c.get("callback"), dict) else None,
        "kospi_chg": (c.get("kospi") or {}).get("chg_pct"),
    }


# ── 이미 쓴 문장 ──
def seen(before: str | None = None, recs: list[dict] | None = None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(글자 그대로 → [date/folder/scene], 숫자 마스킹 → [...]). 시그니처는 뺀다."""
    exact: dict[str, list[str]] = {}
    masked: dict[str, list[str]] = {}
    for r in (recs if recs is not None else editions(before)):
        for sc in r["scenes"]:
            for s in sentences(sc["tts"]):
                if is_signature(s) or len(norm(s)) < 8:
                    continue
                where = f"{r['date']}/{r['folder']}/{sc['id']}"
                exact.setdefault(norm(s), []).append(where)
                masked.setdefault(mask(s), []).append(where)
    return exact, masked


def pick(cands: list[str], d: str, exact: dict | None = None, masked: dict | None = None) -> str:
    """후보 문장 중 전 편에 없던 것을 고른다. 글자 그대로 겹치는 건 빼고, 숫자만 다른 것도 되도록 피한다.
    전부 겹치면 가장 덜 쓴 것. 후보가 비면 빈 문자열."""
    if not cands:
        return ""
    if exact is None or masked is None:
        exact, masked = seen(d)
    fresh = [c for c in cands if norm(c) not in exact and mask(c) not in masked]
    if fresh:
        return fresh[int(d[-2:]) % len(fresh)]
    semi = [c for c in cands if norm(c) not in exact]
    if semi:
        return min(semi, key=lambda c: len(masked.get(mask(c), [])))
    return min(cands, key=lambda c: len(exact.get(norm(c), [])))


def overlaps(d: str, scenes: list[dict], recs: list[dict] | None = None) -> list[dict]:
    """오늘 대본이 이전 편들과 겹치는 문장. kind: exact(글자 그대로) / numbers(숫자만 다름)."""
    exact, masked = seen(d, recs)
    out = []
    for sc in scenes:
        for s in sentences(sc.get("tts") or ""):
            if is_signature(s) or len(norm(s)) < 8:
                continue
            if norm(s) in exact:
                out.append({"scene": sc.get("id"), "kind": "exact", "sentence": s, "seen": exact[norm(s)]})
            elif mask(s) in masked:
                out.append({"scene": sc.get("id"), "kind": "numbers", "sentence": s, "seen": masked[mask(s)]})
    return out


# ── 이어지는 사실 ──
def _prev_kr(d: str, n: int = 10) -> list[dict]:
    """d 직전 평일편들(최신부터). 같은 날 여러 판이면 접미사 없는 것을, 없으면 마지막 판을 쓴다."""
    by_date: dict[str, dict] = {}
    for r in editions(before=d, kinds=("kr",)):
        if r["date"] not in by_date or not r["draft"]:
            by_date[r["date"]] = r
    return [by_date[k] for k in sorted(by_date, reverse=True)[:n]]


def continuity(d: str, today: dict) -> dict:
    """오늘 사실(facts(comp))이 어제·그제와 얼마나 이어지는지. 대본은 이걸로 '오늘도 … N일째' 를 만든다.

    반환:
      top_buyer_days     오늘 가장 많이 산 쪽이 며칠째 같은지(오늘 포함, 1이면 오늘이 처음)
      others_buy_days    기타법인이 며칠째 순매수인지(오늘 포함)
      protagonist_days   주인공이 며칠째 같은지(오늘 포함)
      event_repeat_days  같은 이슈 라벨이 며칠 안에 있었는지(0이면 없음)
      yesterday          어제 편 사실(없으면 None)
      said_yesterday     어제 편 문장 목록(회수용)
    """
    prev = _prev_kr(d)
    y = prev[0]["facts"] if prev else None

    def run(key_fn) -> int:
        n = 1
        for r in prev:
            if key_fn(r["facts"]):
                n += 1
            else:
                break
        return n

    tb = today.get("top_buyer")
    out = {
        "top_buyer_days": run(lambda f: tb is not None and f.get("top_buyer") == tb),
        "others_buy_days": run(lambda f: (today.get("others") or 0) > 0 and (f.get("others") or 0) > 0) if (today.get("others") or 0) > 0 else 0,
        "protagonist_days": run(lambda f: today.get("protagonist") and f.get("protagonist") == today.get("protagonist")),
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


def days_ko(n: int) -> str:
    return {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레", 8: "여드레", 9: "아흐레", 10: "열흘"}.get(n, f"{n}일")


# ── CLI ──
def _print_table(recs: list[dict]) -> None:
    print(f"{'date':9} {'folder':18} {'주인공':6} {'가장 산 쪽':8} {'기타법인':>8} {'외인연속':>6} {'top테마':8} {'훅':4} 이슈 / 내일 볼 것")
    for r in recs:
        f = r["facts"]
        if r["kind"] != "kr":
            print(f"{r['date']:9} {r['folder']:18} [{r['kind']}] watch={f.get('watch')}")
            continue
        print(f"{r['date']:9} {r['folder']:18} {str(f.get('protagonist') or '-'):6} {str(f.get('top_buyer') or '-'):8} "
              f"{str(f.get('others') or '-'):>8} {str(f.get('foreign_streak') or '-'):>6} {str(f.get('top_theme') or '-'):8} "
              f"{str(f.get('hook_id') or '-'):4} {f.get('event_label') or '-'} / {f.get('watch')}")


def main() -> None:
    if len(sys.argv) > 1:
        d = sys.argv[1]
        recs_today = [r for r in editions(kinds=("kr",)) if r["date"] == d and not r["draft"]]
        if not recs_today:
            print(f"{d} 평일편 없음")
            return
        today = recs_today[-1]
        print(f"== {d} 가 이전 편들과 겹친 문장")
        ov = overlaps(d, today["scenes"])
        for o in ov:
            print(f"  [{o['kind']:7}] ({o['scene']}) {o['sentence'][:70]}  ← {', '.join(o['seen'][:3])}")
        if not ov:
            print("  없음")
        c = continuity(d, today["facts"])
        print(f"== 이어짐: 가장 산 쪽 {today['facts'].get('top_buyer')} {c['top_buyer_days']}일째 · 기타법인 순매수 {c['others_buy_days']}일째 · "
              f"주인공 {today['facts'].get('protagonist')} {c['protagonist_days']}일째 · 이슈 반복 {c['event_repeat_days']}일 전")
        return
    recs = editions()
    _print_table(recs)
    print()
    print("== 전 편끼리 글자 그대로 겹친 문장(시그니처 제외)")
    exact, _ = seen(recs=recs)
    for s, where in exact.items():
        dates = sorted({w.split('/')[0] for w in where})
        if len(dates) >= 2:
            print(f"  {s[:60]}  ← {', '.join(dates)}")


if __name__ == "__main__":
    main()
