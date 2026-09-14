"""전날 예고 → 다음 날 검증 → 전적 기록(data/ledger.json).

전날 s5의 '내일 볼 것'(watch[0].q)을 기계가 판정할 수 있는 조건으로 저장하고, 다음 날 마감 데이터로 이어졌는지/끊겼는지 판정한다.
판정 결과는 narrate가 s3 첫머리("어제 … 보자고 했죠. 오늘 …")와 스레드 본문에 쓴다. 누적 전적은 '돈이 머문 곳이 다음 날도 이어진 경우 n번 중 k번'으로 말한다.

entry: {"date": "20260908", "q": "반도체 순매수가 나흘째 이어지는지", "check": {"kind": "theme_continue", "theme": "반도체", "n": 4},
        "result": {"date": "20260909", "ok": false, "t": -964, "streak": -1}}
kinds: theme_continue(theme, n) · theme_sell_stop(theme) · theme_sell_cont(theme) · inv_continue(key, sign) · kosdaq_break(sign)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from _common import DATA, load_json, log, save_json

LEDGER = DATA / "ledger.json"
DAYS = {"이틀째": 2, "사흘째": 3, "나흘째": 4, "닷새째": 5, "엿새째": 6, "이레째": 7}
INV_KEY = {"외국인": "foreign", "기관": "inst", "개인": "indiv", "기타법인": "others"}


def parse_q(q: str) -> dict | None:
    """compute가 만든 '내일 볼 것' 문장을 판정 조건으로 바꾼다(문장 형식은 compute.py에서만 만들어지므로 정규식으로 충분)."""
    q = (q or "").strip()
    m = re.match(r"^(.+?)(?:으)?로 옮겨간 돈이 이틀째 이어지는지$", q)
    if m:
        return {"kind": "theme_continue", "theme": m.group(1), "n": 2}
    m = re.match(r"^(기타법인|외국인|기관|개인) (순매수|순매도)가 (?:(\S+째) )?이어지는지$", q)
    if m:
        return {"kind": "inv_continue", "key": INV_KEY[m.group(1)], "name": m.group(1), "sign": 1 if m.group(2) == "순매수" else -1,
                "n": DAYS.get(m.group(3) or "")}
    m = re.match(r"^코스닥 (\d+)일 연속 (하락|상승)이 끊기는지$", q)
    if m:
        return {"kind": "kosdaq_break", "sign": -1 if m.group(2) == "하락" else 1, "n": int(m.group(1))}
    m = re.match(r"^(.+?) 순매도가 멈추는지$", q)
    if m:
        return {"kind": "theme_sell_stop", "theme": m.group(1)}
    m = re.match(r"^(.+?) 순매수가 (.+?) 이어지는지$", q)
    if m:
        word = m.group(2)
        n = DAYS.get(word) or (int(re.sub(r"\D", "", word)) if re.search(r"\d", word) else None)
        return {"kind": "theme_continue", "theme": m.group(1), "n": n}
    m = re.match(r"^(.+?) 순매도가 이어지는지$", q)
    if m:
        return {"kind": "theme_sell_cont", "theme": m.group(1)}
    return None


def _load() -> dict:
    j = load_json(LEDGER) or {}
    j.setdefault("entries", [])
    return j


def record(d: str, q: str) -> bool:
    """오늘의 예고를 저장(같은 날 재실행이면 덮어씀). 기록됐으면 True."""
    chk = parse_q(q)
    if not chk:
        log(d, "ledger", f"⚠ 예고 형식 인식 못 함(기록 안 함): {q}")
        return False
    j = _load()
    j["entries"] = [e for e in j["entries"] if e.get("date") != d]
    j["entries"].append({"date": d, "q": q, "check": chk, "result": None})
    j["entries"].sort(key=lambda e: e["date"])
    save_json(LEDGER, j)
    return True


def _prev_entry(j: dict, d: str) -> dict | None:
    prev = [e for e in j["entries"] if e.get("date") < d]
    return prev[-1] if prev else None


def _backfill(j: dict, d: str) -> dict | None:
    """장부에 전날 예고가 없으면(도입 전) 전날 computed_kr.json의 watch[0]에서 만든다."""
    base = datetime.strptime(d, "%Y%m%d")
    for i in range(1, 6):
        pd = (base - timedelta(days=i)).strftime("%Y%m%d")
        c = load_json(DATA / pd / "computed_kr.json") or {}
        w = (c.get("watch") or [{}])[0]
        if w.get("q"):
            chk = parse_q(w["q"])
            if not chk:
                return None
            e = {"date": pd, "q": w["q"], "check": chk, "result": None, "backfilled": True}
            j["entries"] = [x for x in j["entries"] if x.get("date") != pd] + [e]
            j["entries"].sort(key=lambda x: x["date"])
            return e
    return None


def _theme_t(theme: str, moves: list[dict], all_moves: list[dict]) -> tuple[float | None, int | None]:
    for src in (moves, all_moves):
        for m in src or []:
            if m.get("theme") == theme and m.get("t") is not None:
                return m["t"], m.get("streak")
    return None, None


def verify(d: str, moves: list[dict], all_moves: list[dict], inv: dict | None, kosdaq: dict | None) -> dict | None:
    """전날 예고를 오늘 데이터로 판정. 반환: {"prev_date","q","check","ok","t","streak","stats":{"n","k"}} 또는 None(판정 불가)."""
    j = _load()
    e = _prev_entry(j, d) or _backfill(j, d)
    if not e:
        return None
    # 전날이 아니라 며칠 전 예고면(휴장·결측) 그래도 '지난 영상'으로 취급
    chk = e["check"]
    ok, t, streak = None, None, None
    if chk["kind"] in ("theme_continue", "theme_sell_stop", "theme_sell_cont"):
        t, streak = _theme_t(chk["theme"], moves, all_moves)
        if t is not None:
            ok = (t > 0) if chk["kind"] == "theme_continue" else (t >= 0) if chk["kind"] == "theme_sell_stop" else (t < 0)
    elif chk["kind"] == "inv_continue" and inv and inv.get(chk["key"]) is not None:
        t = inv[chk["key"]]
        ok = (t > 0) == (chk["sign"] > 0) and t != 0
    elif chk["kind"] == "kosdaq_break" and kosdaq and kosdaq.get("chg_pct") is not None:
        t = kosdaq["chg_pct"]
        ok = (t > 0) != (chk["sign"] > 0)
    if ok is None:
        log(d, "ledger", f"판정 불가: {e['q']} (테마 데이터 없음)")
        return None
    e["result"] = {"date": d, "ok": bool(ok), "t": t, "streak": streak}
    save_json(LEDGER, j)
    done = [x for x in j["entries"] if x.get("result") and x["check"]["kind"] == "theme_continue"]
    stats = {"n": len(done), "k": sum(1 for x in done if x["result"]["ok"])}
    log(d, "ledger", f"검증 {e['date']} '{e['q']}' → {'이어짐' if ok else '끊김'} (t={t}) | 전적 {stats['k']}/{stats['n']}")
    return {"prev_date": e["date"], "q": e["q"], "check": chk, "ok": bool(ok), "t": t, "streak": streak, "stats": stats}
