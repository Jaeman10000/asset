"""15:35 키움 수집 — 지수 1분봉(001/101) · 일봉 · 프로그램 · 업종 연속일수 · 거래대금 상위 · 미국 QQQ/SPY 1분봉.
조회 전용. 결과: data/D/raw/kiwoom.json
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta

import httpx

from _common import day_dir, kiwoom_call, log, num, save_json
from app.services.kiwoom_client import KiwoomClient  # noqa: E402  (sys.path는 _common에서)


def _us_session_date(d: str) -> str:
    """국내 날짜 D의 '전날 밤' 미국 세션 영업일(ET 기준 날짜 = KST 개장일). 월요일이면 금요일."""
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


async def _index_minutes(hc, tok, inds: str, d: str) -> list[dict]:
    rows, cont, nk = [], "N", ""
    for _ in range(6):
        data, cont, nk = await kiwoom_call(hc, tok, "chart", "ka20005", {"inds_cd": inds, "tic_scope": "1"}, cont, nk)
        rows += data.get("inds_min_pole_qry") or []
        if any(str(r["cntr_tm"]) < d + "000000" for r in rows) or cont != "Y":
            break
    day = sorted((r for r in rows if str(r["cntr_tm"]).startswith(d)), key=lambda r: r["cntr_tm"])
    return [{"t": r["cntr_tm"][8:12], "o": num(r["open_pric"]) / 100, "h": abs(num(r["high_pric"])) / 100,
             "l": abs(num(r["low_pric"])) / 100, "c": abs(num(r["cur_prc"])) / 100, "v": num(r["trde_qty"])} for r in day]


async def _index_daily(hc, tok, inds: str, d: str) -> dict:
    data, _, _ = await kiwoom_call(hc, tok, "chart", "ka20006", {"inds_cd": inds, "base_dt": d})
    rows = data.get("inds_dt_pole_qry") or []
    by = {r["dt"]: r for r in rows}
    today = by.get(d)
    prev = next((r for r in rows if r["dt"] < d), None)
    def conv(r):
        return None if not r else {"open": num(r["open_pric"]) / 100, "high": num(r["high_pric"]) / 100,
                                   "low": num(r["low_pric"]) / 100, "close": num(r["cur_prc"]) / 100,
                                   "value_mn": num(r["trde_prica"]), "volume": num(r["trde_qty"])}
    recent = [{"dt": r["dt"], "close": num(r["cur_prc"]) / 100} for r in rows if r["dt"] <= d][:12]
    return {"today": conv(today), "prev": conv(prev), "prev_dt": prev["dt"] if prev else None, "recent": recent}


async def _stock_flows(hc, tok, codes: list[str], d: str) -> dict[str, dict]:
    """거래대금 상위 종목의 당일 투자자별 순매수(ka10059, 백만원→억원)."""
    out = {}
    for code in codes:
        try:
            data, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059",
                                           {"dt": d, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
            row = next((r for r in data.get("stk_invsr_orgn") or [] if r.get("dt") == d), None)
            if row:
                out[code] = {"indiv": round(num(row["ind_invsr"]) / 100), "foreign": round(num(row["frgnr_invsr"]) / 100),
                             "inst": round(num(row["orgn"]) / 100), "pct": num(row["flu_rt"]) / 100, "close": abs(num(row["cur_prc"]))}
        except Exception as e:
            log(d, "kiwoom", f"ka10059 {code} 실패: {e}")
    return out


async def _program(hc, tok, mkt: str, d: str) -> dict | None:
    data, _, _ = await kiwoom_call(hc, tok, "mrkcond", "ka90010",
                                   {"date": d, "amt_qty_tp": "1", "mrkt_tp": mkt, "min_tic_tp": "0", "stex_tp": "3"})
    row = next((r for r in data.get("prm_trde_trnsn") or [] if str(r["cntr_tm"]).startswith(d)), None)
    if not row:
        return None
    return {"all_mn": num(row["all_netprps"]), "arb_mn": num(row["dfrt_trde_netprps"]),
            "nonarb_mn": num(row["ndiffpro_trde_netprps"]), "basis": num(row["basis"])}


async def _sector_streaks(hc, tok, d: str) -> list[dict]:
    data, _, _ = await kiwoom_call(hc, tok, "frgnistt", "ka10131",
                                   {"dt": d, "mrkt_tp": "001", "netslmt_tp": "2", "stk_inds_tp": "1", "amt_qty_tp": "1", "stex_tp": "3"})
    out = []
    for r in data.get("orgn_frgnr_cont_trde_prst") or []:
        out.append({"code": r["stk_cd"], "name": r["stk_nm"], "inst_days": num(r["orgn_cont_netprps_dys"]),
                    "frgn_days": num(r["frgnr_cont_netprps_dys"]), "inst_amt": num(r["orgn_nettrde_amt"]),
                    "frgn_amt": num(r["frgnr_nettrde_amt"])})
    return out


async def _value_top(hc, tok) -> list[dict]:
    data, _, _ = await kiwoom_call(hc, tok, "rkinfo", "ka10032", {"mrkt_tp": "000", "mang_stk_incls": "1", "stex_tp": "3"})
    out = []
    for r in (data.get("trde_prica_upper") or [])[:20]:
        out.append({"code": str(r["stk_cd"]).split("_")[0], "name": r["stk_nm"], "pct": num(r["flu_rt"]),
                    "value_mn": num(r["trde_prica"]), "price": abs(num(r["cur_prc"]))})
    return out


def _row_date(r: dict) -> str:
    for k, v in r.items():
        if ("dt" in k or "date" in k) and isinstance(v, str) and len(v) >= 8 and v[:8].isdigit():
            return v[:8]
    return ""


def _et_offset_hours(sess: str) -> int:
    """ET→KST 시차. 미국 DST: 3월 둘째 일요일 ~ 11월 첫째 일요일 → 13h, 그 외 14h."""
    dt = datetime.strptime(sess, "%Y%m%d")
    mar = datetime(dt.year, 3, 8); mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(dt.year, 11, 1); nov += timedelta(days=(6 - nov.weekday()) % 7)
    return 13 if mar <= dt < nov else 14


async def _us_minutes(hc, tok, stex: str, code: str, us_dt: str) -> dict:
    """미국 정규장(ET us_dt 09:30~16:00) 1분봉. 실측(2026-09-05): 키움 해외 분봉 cntr_tm은 **ET 날짜+ET 시각**이며
    자정 이후 시간외는 24시 이상으로 표기된다(20260903263200 = ET 9/4 02:32). 정규장은 0930~1600 라벨만 고르면 된다.
    t_kst는 차트용(ET+13/14h). exrt_appl_tp=0 → 달러."""
    w0, w1 = us_dt + "0930", us_dt + "1600"
    rows, cont, nk = [], "N", ""
    body = {"stex_tp": stex, "stk_cd": code, "strt_dt": us_dt, "tic_scope": "1", "upd_stkpc_tp": "0", "exrt_appl_tp": "0"}
    for _ in range(16):
        data, cont, nk = await kiwoom_call(hc, tok, "us_chart", "usa06011", body, cont, nk)
        lst = data.get("result_list") or []
        rows += lst
        if not lst or any(str(r["cntr_tm"])[:12] < w0 for r in lst) or cont != "Y":
            break
    sess = sorted((r for r in rows if w0 <= str(r["cntr_tm"])[:12] <= w1), key=lambda r: r["cntr_tm"])
    off = _et_offset_hours(us_dt)
    mins = []
    for r in sess:
        h, m = int(r["cntr_tm"][8:10]), int(r["cntr_tm"][10:12])
        hk = (h + off) % 24
        mins.append({"t_et": r["cntr_tm"][8:12], "t_kst": f"{hk:02d}{m:02d}", "o": num(r["open_pric"]), "h": num(r["high_pric"]),
                     "l": num(r["low_pric"]), "c": num(r["cur_prc"]), "v": num(r["trde_qty"])})
    complete = bool(mins) and mins[-1]["t_et"] >= "1555"
    if not complete:
        log(us_dt, "kiwoom", f"{code} 정규장 분봉 미완성 — 마지막 ET {mins[-1]['t_et'] if mins else '없음'}")
    prev_close, sess_close, sess_pct, daily = None, None, None, None
    try:
        dd, _, _ = await kiwoom_call(hc, tok, "us_chart", "usa06012",
                                     {"stex_tp": stex, "stk_cd": code, "strt_dt": us_dt, "upd_stkpc_tp": "0", "exrt_appl_tp": "0"})
        drows = [r for r in dd.get("result_list") or [] if _row_date(r) <= us_dt]
        if drows and _row_date(drows[0]) == us_dt:
            d0 = drows[0]
            daily = {"open": num(d0["open_pric"]), "high": num(d0["high_pric"]), "low": num(d0["low_pric"]), "close": num(d0["cur_prc"]),
                     "pct": num(d0.get("flu_rt"))}
            sess_close, sess_pct = daily["close"], daily["pct"]
            if len(drows) > 1:
                prev_close = num(drows[1]["cur_prc"])
    except Exception as e:
        log(us_dt, "kiwoom", f"usa06012 실패({e})")
    # 실측(2026-09-05): 키움 해외 일봉의 당일 행은 시간외·야간 거래를 따라 계속 움직인다(11:40 KST에 -0.09%, 다음날 +0.18%).
    # 정규장 종가는 항상 16:00 ET 분봉(종가 단일가 포함)으로 확정하고, 일봉은 전일 종가에만 쓴다.
    if mins:
        sess_close = mins[-1]["c"]
        sess_pct = round((sess_close / prev_close - 1) * 100, 2) if prev_close else sess_pct
    if mins and not prev_close:
        prev_close = mins[0]["o"]
    return {"symbol": code, "session_et": us_dt, "window_et": [w0, w1], "prev_close": prev_close,
            "prev_close_src": "daily" if daily else "first_open", "session_close": sess_close, "session_pct": sess_pct,
            "high": max(x["h"] for x in mins) if mins else (daily or {}).get("high"), "low": min(x["l"] for x in mins) if mins else (daily or {}).get("low"),
            "open": mins[0]["o"] if mins else (daily or {}).get("open"), "daily": daily,
            "minutes": mins, "n": len(mins), "complete": complete}


async def main(d: str) -> None:
    raw = day_dir(d)
    c = KiwoomClient()
    if not c.configured:
        log(d, "kiwoom", "앱키 없음 — 건너뜀"); return
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        out: dict = {"date": d, "fetched_at": datetime.now().isoformat(timespec="seconds")}
        for key, inds, pm in (("kospi", "001", "P00101"), ("kosdaq", "101", "P10102")):
            out[key] = {"minutes": await _index_minutes(hc, tok, inds, d),
                        "daily": await _index_daily(hc, tok, inds, d),
                        "program": await _program(hc, tok, pm, d)}
            log(d, "kiwoom", f"{key}: 1분봉 {len(out[key]['minutes'])}행, 일봉 {'OK' if out[key]['daily']['today'] else '없음'}, 프로그램 {'OK' if out[key]['program'] else '없음'}")
            await asyncio.sleep(0.3)
        out["sector_streaks"] = await _sector_streaks(hc, tok, d)
        out["value_top"] = await _value_top(hc, tok)
        out["stock_flows"] = await _stock_flows(hc, tok, [s["code"] for s in out["value_top"][:10]], d)
        log(d, "kiwoom", f"거래대금 상위 {len(out['value_top'])} · 종목 수급 {len(out['stock_flows'])}")
        us_dt = _us_session_date(d)
        out["us"] = {}
        for stex, code in (("ND", "QQQ"), ("NY", "SPY")):
            out["us"][code] = await _us_minutes(hc, tok, stex, code, us_dt)
            log(d, "kiwoom", f"{code} {us_dt} 세션 1분봉 {out['us'][code]['n']}행, prev_close={out['us'][code]['prev_close']}")
            await asyncio.sleep(0.3)
    save_json(raw / "kiwoom.json", out)
    log(d, "kiwoom", f"저장 {raw / 'kiwoom.json'}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")))
