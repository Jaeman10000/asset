"""compute 단계(flows 뒤) — 수급 브리핑 S4 의 종목 둘: 유입 1위 업종(없으면 |순매수| 최대 업종)의 **대장주 1 + 최대 상승 1**.
설계 docs/BRIEF_FORMAT_DESIGN.md §3.
  대장주   = flow_store sectors[].leader → 없으면 그 업종에서 거래대금 최대 종목
  최대 상승 = 그 업종 구성 종목 ∪ raw/event.json 종목 가운데 등락 최대(대장주 제외)
  숫자     = 키움 ka10059 당일 행(외/기/개·거래대금·등락, 억 단위) — collect_event._one 을 그대로 쓴다. 등락은 data/events.json 의 pct_fix 가 있으면 그것(16시 이후 수집이면 애프터마켓 체결이 섞인다).
결과: raw/brief_stocks.json {"date","theme","stocks":[{code,name,role:"대장주"|"최대 상승",theme,pct,foreign,inst,indiv,value,close}]}
실패해도 예외 없이 {} 를 저장하고 로그만 남긴다(무인 제작을 막지 않는다). 키움 호출은 읽기 전용.
사용: python collect_brief.py YYYYMMDD [출력경로]   — 출력경로를 주면 data/ 대신 거기에 쓴다(오프라인 시험, brief_try.py).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

from _common import DATA, load_json, log, save_json

sys.path.insert(0, str(DATA.parent.parent / "backend"))


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def pick(fl: dict | None, day: dict | None, ev: dict | None) -> dict | None:
    """순수 선택(네트워크 없음): {"theme", "picks": [{"code","name","role","theme"}, …]} 또는 None(업종 표가 없을 때).
    fl = raw/flows.json, day = flow_store.load_day(d), ev = raw/event.json."""
    fl, day, ev = fl or {}, day or {}, ev or {}
    rows = [r for r in (day.get("stocks") or []) if isinstance(r, dict) and r.get("theme") and r.get("code")]
    nets: dict[str, float] = {}
    if fl.get("ready") and fl.get("table_t"):
        nets = {th: _num((row or {}).get("net")) for th, row in fl["table_t"].items() if _num((row or {}).get("net")) is not None}
    if not nets and rows:
        for r in rows:
            nets[r["theme"]] = nets.get(r["theme"], 0.0) + (_num(r.get("foreign")) or 0) + (_num(r.get("inst")) or 0)
    if not nets:
        return None
    pos = {th: v for th, v in nets.items() if v > 0}
    theme = max(pos, key=pos.get) if pos else max(nets, key=lambda t: abs(nets[t]))
    try:
        from app.services.themes import CODE_NAME, THEMES
    except Exception:
        CODE_NAME, THEMES = {}, {}
    trows = [r for r in rows if r["theme"] == theme]
    leader_code = next((s.get("leader") for s in (day.get("sectors") or []) if isinstance(s, dict) and s.get("theme") == theme and s.get("leader")), None)
    lead = next((r for r in trows if r["code"] == leader_code), None)
    if lead is None and trows:
        lead = max(trows, key=lambda r: _num(r.get("value")) or 0)
    if lead is None and leader_code:
        lead = {"code": leader_code, "name": CODE_NAME.get(leader_code, leader_code)}
    if lead is None and THEMES.get(theme):
        code, name = THEMES[theme][0]
        lead = {"code": code, "name": name}
    if lead is None:
        return None
    cands = [{"code": r["code"], "name": r.get("name") or CODE_NAME.get(r["code"], r["code"]), "pct": _num(r.get("ret"))} for r in trows]
    cands += [{"code": s.get("code"), "name": s.get("name"), "pct": _num(s.get("pct"))} for s in (ev.get("stocks") or []) if isinstance(s, dict) and s.get("code")]
    cands = [c for c in cands if c["code"] != lead["code"] and c["pct"] is not None]
    top = max(cands, key=lambda c: c["pct"]) if cands else None
    picks = [{"code": lead["code"], "name": lead.get("name") or CODE_NAME.get(lead["code"], lead["code"]), "role": "대장주", "theme": theme}]
    if top:
        picks.append({"code": top["code"], "name": top["name"], "role": "최대 상승", "theme": theme})
    return {"theme": theme, "picks": picks}


async def _fetch(d: str, picks: list[dict], fix: dict | None) -> list[dict]:
    import httpx
    from app.services.kiwoom_client import KiwoomClient
    import collect_event
    c = KiwoomClient()
    out = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        for p in picks:
            try:
                r = await collect_event._one(hc, tok, d, p["code"], p["name"], fix)
            except Exception as e:  # noqa: BLE001
                log(d, "brief", f"{p['name']} ka10059 실패: {e}")
                r = None
            if r:
                out.append({**r, "role": p["role"], "theme": p["theme"]})
            await asyncio.sleep(0.25)
    return out


async def main(d: str, out_path: str | Path | None = None) -> dict:
    """raw/brief_stocks.json(또는 out_path) 을 쓴다. 어떤 실패에도 예외를 내지 않고 {} 를 저장한다."""
    raw = DATA / d / "raw"
    path = Path(out_path) if out_path else raw / "brief_stocks.json"
    out: dict = {}
    try:
        fl = load_json(raw / "flows.json") or {}
        ev = load_json(raw / "event.json") or {}
        if ev and ev.get("date") not in (None, d):
            ev = {}
        try:
            from app.services import flow_store
            day = flow_store.load_day(d) or {}
        except Exception as e:  # noqa: BLE001
            log(d, "brief", f"flow_store 읽기 실패(무시): {e}")
            day = {}
        sel = pick(fl, day, ev)
        if not sel:
            log(d, "brief", "업종 표 없음 → 종목 둘 생략({})")
        else:
            fix = ((load_json(DATA / "events.json") or {}).get(d) or {}).get("pct_fix")
            stocks = await _fetch(d, sel["picks"], fix)
            close = {r.get("code"): r.get("close") for r in (day.get("stocks") or []) if isinstance(r, dict)}
            for s in stocks:
                s.setdefault("close", close.get(s.get("code")))
            if stocks:
                out = {"date": d, "theme": sel["theme"], "stocks": stocks, "fetched_at": datetime.now().isoformat(timespec="seconds")}
                log(d, "brief", f"{sel['theme']}: " + ", ".join(f"{s['role']} {s['name']} {s['pct']:+.2f}% 외{s['foreign']:+,} 기{s['inst']:+,} 개{s['indiv']:+,} 대금{s['value']:,}" for s in stocks))
            else:
                log(d, "brief", f"{sel['theme']}: 종목 행 없음(휴장?) → {{}}")
    except Exception as e:  # noqa: BLE001 — 부가 수집, 제작을 막지 않는다
        log(d, "brief", f"수집 실패(무시): {e!r}")
        out = {}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        save_json(path, out)
    except Exception as e:  # noqa: BLE001
        log(d, "brief", f"저장 실패 {path}: {e}")
    return out


if __name__ == "__main__":
    _d = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    _p = sys.argv[2] if len(sys.argv) > 2 else None
    print(asyncio.run(main(_d, _p)))
