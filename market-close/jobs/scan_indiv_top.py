"""최근 N거래일 개인 순매수 상위 종목 — 코스피·코스닥 전 종목을 ka10059 로 한 번씩 훑는다(읽기 전용).
ka10059 는 종목당 최근 100거래일 행을 한 번에 준다. 그래서 전 종목 1회 호출이면 다섯 달치가 모인다.
결과: data/<날짜>/indiv_top.json {"asof", "days", "rows":[{code,name,indiv,foreign,inst,etc,close,ret}]}
실행(jobs/): python scan_indiv_top.py 20260918 [--days=100]
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime

import httpx

from _common import DATA, kiwoom_call, log, save_json

sys.path.insert(0, str(DATA.parent.parent / "backend"))
from app.services.kiwoom_client import KiwoomClient  # noqa: E402


def num(v) -> float:
    try:
        return float(str(v).replace("+", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


async def codes(hc, tok) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for mrkt in ("0", "10"):
        data, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10099", {"mrkt_tp": mrkt})
        for s in data.get("list") or []:
            name = (s.get("name") or "").strip()
            code = (s.get("code") or "").strip()
            kind = (s.get("stockClassification") or s.get("marketName") or "")
            if not code or not name:
                continue
            if any(x in name for x in ("스팩", "ETN")) or name.endswith("우") or "우B" in name:
                continue
            if s.get("auditInfo") and "관리" in str(s.get("auditInfo")):
                continue
            if kind and any(x in str(kind) for x in ("ETF", "ETN", "ELW")):
                continue
            out.append((code, name))
    return out


async def main(d: str, days: int) -> None:
    c = KiwoomClient()
    rows = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as hc:
        tok = await c._ensure_token(hc)
        cs = await codes(hc, tok)
        log(d, "scan", f"전 종목 {len(cs)}개 — 최근 {days}거래일 개인 순매수 합산 시작")
        for i, (code, name) in enumerate(cs):
            try:
                data, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059",
                                               {"dt": d, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
                rs = (data.get("stk_invsr_orgn") or [])[:days]
                if len(rs) < 20:
                    continue
                g = lambda k: round(sum(num(x.get(k)) for x in rs) / 100)      # 백만원 → 억원
                last, first = rs[0], rs[-1]
                cur, old = abs(num(last.get("cur_prc"))), abs(num(first.get("cur_prc")))
                rows.append({"code": code, "name": name, "indiv": g("ind_invsr"), "foreign": g("frgnr_invsr"),
                             "inst": g("orgn"), "etc": g("etc_corp"), "close": cur, "from_close": old,
                             "ret": round((cur / old - 1) * 100, 1) if old else None,
                             "days": len(rs), "from_dt": first.get("dt"), "to_dt": last.get("dt")})
            except Exception as e:
                if i % 50 == 0:
                    log(d, "scan", f"{name} 실패: {e}")
            if i % 100 == 0:
                log(d, "scan", f"{i}/{len(cs)} …")
    rows.sort(key=lambda x: -x["indiv"])
    save_json(DATA / d / "indiv_top.json", {"asof": d, "days": days, "n": len(rows),
                                            "top_buy": rows[:30], "top_sell": rows[-30:][::-1]})
    log(d, "scan", f"완료 — {len(rows)}종목. 1위 {rows[0]['name']} {rows[0]['indiv']:,}억")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else datetime.now().strftime("%Y%m%d")
    days = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--days=")), "100"))
    asyncio.run(main(d, days))
