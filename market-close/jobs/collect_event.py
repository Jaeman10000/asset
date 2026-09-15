"""오늘의 이슈(예: 애플 신제품 발표)에 엮인 국장 종목 묶음의 마감 등락·투자자별 순매수 — data/events.json[날짜] 설정이 있는 날만.
raw/event.json: {"label","spoken","group","keywords","hashtags","news_query",
                 "stocks":[{"code","name","pct","foreign","inst","indiv","value"}...], "avg_pct","n_up","n_down"}
등락률·순매수는 키움 ka10059 당일 행(등락률 flu_rt는 1/100%, 금액은 백만원→억원).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime

import httpx

from _common import DATA, day_dir, kiwoom_call, load_json, log, save_json

sys.path.insert(0, str(DATA.parent.parent / "backend"))
from app.services.kiwoom_client import KiwoomClient  # noqa: E402


def _num(v) -> float:
    try:
        return float(str(v).replace("+", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


async def _one(hc, tok, d: str, code: str, name: str) -> dict | None:
    data, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059", {"dt": d, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
    rows = data.get("stk_invsr_orgn") or []
    row = next((r for r in rows if r.get("dt") == d), None)
    if not row:
        return None
    try:
        info, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10001", {"stk_cd": code})
        name = info.get("stk_nm") or name
    except Exception:
        pass
    return {"code": code, "name": name, "pct": round(_num(row.get("flu_rt")) / 100, 2),
            "foreign": round(_num(row.get("frgnr_invsr")) / 100), "inst": round(_num(row.get("orgn")) / 100),
            "indiv": round(_num(row.get("ind_invsr")) / 100), "value": round(_num(row.get("acc_trde_prica")) / 100)}


async def main(d: str) -> dict:
    ev = (load_json(DATA / "events.json") or {}).get(d)
    if not ev:
        return {}
    c = KiwoomClient()
    stocks = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        for code, name in (ev.get("codes") or {}).items():
            try:
                r = await _one(hc, tok, d, code, name)
                if r:
                    stocks.append(r)
            except Exception as e:
                log(d, "event", f"{name} 실패: {e}")
            await asyncio.sleep(0.25)
    if not stocks:
        log(d, "event", "종목 데이터 없음(휴장?)")
        return {}
    stocks.sort(key=lambda s: -s["pct"])
    out = {k: ev.get(k) for k in ("label", "spoken", "group", "keywords", "hashtags", "news_query", "image", "head", "icons")}
    out.update({"date": d, "stocks": stocks, "avg_pct": round(sum(s["pct"] for s in stocks) / len(stocks), 2),
                "n_up": sum(1 for s in stocks if s["pct"] > 0), "n_down": sum(1 for s in stocks if s["pct"] < 0)})
    save_json(day_dir(d) / "event.json", out)
    log(d, "event", f"{out['label']}: " + ", ".join(f"{s['name']} {s['pct']:+.2f}%" for s in stocks) + f" | 평균 {out['avg_pct']:+.2f}%")
    return out


if __name__ == "__main__":
    print(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))))
