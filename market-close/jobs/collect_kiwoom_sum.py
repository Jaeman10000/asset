"""키움만으로 시장 전체 투자자별 수급 — 코스피 주권 전 종목(ka10099 '거래소'·'리츠'·'인프라투자금융'·'뮤추얼펀드')의
ka10059(종목별투자자기관별, 당일 행)를 합산한다. ETF·ETN·ELW 제외 = KRX '주식' 모집단과 같은 정의.
약 940콜, 동시 3 → 3~4분. 결과: data/D/raw/kiwoom_sum.json  (억원)
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime

import httpx

from _common import day_dir, kiwoom_call, log, num, save_json
from app.services.kiwoom_client import KiwoomClient  # noqa: E402

STOCK_MARKETS = {"거래소", "리츠", "인프라투자금융", "뮤추얼펀드", "코스닥"}  # ETF·ETN·ELW 제외
FIELDS = {"ind_invsr": "indiv", "frgnr_invsr": "foreign", "orgn": "inst", "fnnc_invt": "sec", "insrnc": "ins", "invtrt": "trust",
          "etc_fnnc": "etc_fin", "bank": "bank", "penfnd_etc": "pension", "samo_fund": "private", "natn": "nation",
          "etc_corp": "others", "natfor": "etc_foreign"}


async def market_sum(hc, tok, mrkt_tp: str, d: str, conc: int = 3) -> dict:
    data, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10099", {"mrkt_tp": mrkt_tp})
    rows = next((v for v in data.values() if isinstance(v, list)), [])
    codes = [r["code"] for r in rows if r.get("marketName") in STOCK_MARKETS and r.get("code")]
    names = {r["code"]: r.get("name") or r["code"] for r in rows if r.get("code")}
    per_others: list[tuple[str, float]] = []          # 종목별 기타법인 순매수(억) — 자사주 매입이 여기 잡힌다
    tot = {v: 0.0 for v in FIELDS.values()}
    got, miss = 0, []
    sem = asyncio.Semaphore(conc)

    async def one(code: str):
        nonlocal got
        async with sem:
            try:
                dd, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059",
                                             {"dt": d, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
                row = next((r for r in dd.get("stk_invsr_orgn") or [] if r.get("dt") == d), None)
                if row:
                    for k, v in FIELDS.items():
                        tot[v] += num(row.get(k)) / 100  # 백만원 → 억원
                    per_others.append((code, num(row.get("etc_corp")) / 100))
                    got += 1
                else:
                    miss.append(code)
            except Exception as e:
                miss.append(f"{code}:{type(e).__name__}")

    t0 = time.time()
    await asyncio.gather(*(one(c) for c in codes))
    out = {k: round(v) for k, v in tot.items()}
    srt = sorted(per_others, key=lambda x: -x[1])
    out["top_others_buy"] = [{"code": c, "name": names.get(c, c), "v": round(v)} for c, v in srt[:5] if v > 0]
    out["top_others_sell"] = [{"code": c, "name": names.get(c, c), "v": round(v)} for c, v in srt[::-1][:5] if v < 0]
    out.update({"n_codes": len(codes), "n_got": got, "n_miss": len(miss), "miss_sample": miss[:10], "seconds": round(time.time() - t0)})
    return out


async def main(d: str, markets: str = "kospi", out_name: str = "kiwoom_sum.json") -> None:
    raw = day_dir(d)
    c = KiwoomClient()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        from _common import load_json
        out = load_json(raw / out_name) or {}
        out.update({"date": d, "unit": "억원", "definition": "주권 전 종목 ka10059 합산(ETF·ETN·ELW 제외)",
                    "collected_at": datetime.now().strftime("%H:%M")})
        for key, mt in (("kospi", "0"), ("kosdaq", "10")):
            if key not in markets:
                continue
            out[key] = await market_sum(hc, tok, mt, d)
            s = out[key]
            log(d, "ksum", f"{key}: 개인 {s['indiv']:+,} 외국인 {s['foreign']:+,} 기관 {s['inst']:+,} 기타법인 {s['others']:+,} "
                           f"기타외국인 {s['etc_foreign']:+,} | {s['n_got']}/{s['n_codes']}종목 {s['seconds']}s")
    save_json(raw / out_name, out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"),
                     sys.argv[2] if len(sys.argv) > 2 else "kospi", sys.argv[3] if len(sys.argv) > 3 else "kiwoom_sum.json"))
