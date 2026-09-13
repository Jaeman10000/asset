"""미국편 수집 — 키움 해외주식 일봉(usa06012)·분봉(usa06011).
지수 대용 ETF: QQQ(나스닥100) SPY(S&P500) DIA(다우) · 섹터 ETF 12개(돈의 이동용) · QQQ 1분봉(이벤트 반응).
결과: data/D/raw/us_kiwoom.json   (D = 실행일 KST, 세션 = 직전 미국 영업일 ET)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta

import httpx

from _common import day_dir, kiwoom_call, log, num, save_json
from app.services.kiwoom_client import KiwoomClient  # noqa: E402
from collect_kiwoom import _us_minutes  # noqa: E402

INDEX_ETF = [("QQQ", "ND", "나스닥100"), ("SPY", "NY", "S&P500"), ("DIA", "NY", "다우")]
SECTOR_ETF = [("SMH", "ND", "반도체"), ("XLK", "NY", "기술"), ("XLC", "NY", "통신·미디어"), ("XLY", "NY", "경기소비재"),
              ("XLF", "NY", "금융"), ("XLV", "NY", "헬스케어"), ("XLI", "NY", "산업재"), ("XLE", "NY", "에너지"),
              ("XLB", "NY", "소재"), ("XLP", "NY", "필수소비재"), ("XLU", "NY", "유틸리티"), ("XLRE", "NY", "부동산")]
# 서학개미 보관액 상위(예탁결제원 2026-07 기준: 테슬라·엔비디아·알파벳·애플·마이크론·MS) — 순매수 순위는 주간 변동이 심해 보관액 순으로 고정
# 후보군 36 = 미국 시총 상위 30 + 서학개미 보관·순매수 상위. 서술은 이 중 3% 이상 움직인 것만(compute_us.MOVER_MIN).
STOCKS = [("NVDA", "ND", "엔비디아"), ("MSFT", "ND", "마이크로소프트"), ("AAPL", "ND", "애플"), ("AMZN", "ND", "아마존"), ("GOOGL", "ND", "알파벳"),
          ("META", "ND", "메타"), ("AVGO", "ND", "브로드컴"), ("TSLA", "ND", "테슬라"), ("LLY", "NY", "일라이릴리"), ("JPM", "NY", "JP모건"),
          ("WMT", "NY", "월마트"), ("V", "NY", "비자"), ("XOM", "NY", "엑슨모빌"), ("MA", "NY", "마스터카드"), ("ORCL", "NY", "오라클"),
          ("NFLX", "ND", "넷플릭스"), ("COST", "ND", "코스트코"), ("JNJ", "NY", "존슨앤드존슨"), ("PLTR", "ND", "팔란티어"), ("AMD", "ND", "AMD"),
          ("MU", "ND", "마이크론"), ("INTC", "ND", "인텔"), ("QCOM", "ND", "퀄컴"), ("TSM", "NY", "TSMC"), ("ASML", "ND", "ASML"),
          ("COIN", "ND", "코인베이스"), ("MSTR", "ND", "마이크로스트래티지"), ("SMCI", "ND", "슈퍼마이크로"), ("ARM", "ND", "ARM"), ("CRM", "NY", "세일즈포스"),
          ("UNH", "NY", "유나이티드헬스"), ("HD", "NY", "홈디포"), ("BAC", "NY", "뱅크오브아메리카"), ("SNDK", "ND", "샌디스크"), ("IONQ", "NY", "아이온큐"),
          ("RKLB", "ND", "로켓랩")]
SEOHAK = {"TSLA", "NVDA", "GOOGL", "AAPL", "MU", "MSFT", "PLTR", "AMD", "TSM", "COIN", "SNDK", "IONQ"}   # 서학개미 보관·순매수 상위(화면 표기용)
# 국장 연결·레버리지: 필라델피아 반도체(SOXX), 한국 ETF(EWY), SOXL(3배), TQQQ(3배)
LINK_ETF = [("SOXX", "ND", "필라델피아 반도체"), ("EWY", "NY", "한국 ETF"), ("SOXL", "NY", "SOXL 반도체 3배"), ("TQQQ", "ND", "TQQQ 나스닥 3배")]


def us_session_for(run_date: str) -> str:
    """실행일(KST) 기준 직전 미국 영업일(ET 날짜). 토·일·월 실행 → 금요일."""
    dt = datetime.strptime(run_date, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def _row_date(r: dict) -> str:
    for k, v in r.items():
        if ("dt" in k or "date" in k) and isinstance(v, str) and v[:8].isdigit():
            return v[:8]
    return ""


async def _daily_ctx(hc, tok, stex: str, code: str, sess: str) -> dict:
    """일봉에서 전일 종가·20일 평균 거래대금·연속 상승일수·5일 수익률(확정된 과거 행 기준)."""
    d, _, _ = await kiwoom_call(hc, tok, "us_chart", "usa06012",
                                {"stex_tp": stex, "stk_cd": code, "strt_dt": sess, "upd_stkpc_tp": "0", "exrt_appl_tp": "0"})
    rows = [r for r in d.get("result_list") or [] if _row_date(r) <= sess]
    if not rows:
        return {}
    has_today = _row_date(rows[0]) == sess
    hist = rows[1:] if has_today else rows          # 확정된 과거
    closes = [num(r["cur_prc"]) for r in hist[:25]]
    vals = [num(r.get("acc_trde_prica")) for r in hist[:20]]
    return {"prev_close": closes[0] if closes else None, "avg20_value": sum(vals) / len(vals) if vals else None,
            "hist_closes": closes, "today_value": num(rows[0].get("acc_trde_prica")) if has_today else None,
            "today_daily": {"open": num(rows[0]["open_pric"]), "high": num(rows[0]["high_pric"]), "low": num(rows[0]["low_pric"]),
                            "close": num(rows[0]["cur_prc"]), "pct": num(rows[0].get("flu_rt"))} if has_today else None}


async def _etf(hc, tok, stex: str, code: str, name: str, sess: str) -> dict | None:
    m = await _us_minutes(hc, tok, stex, code, sess)
    ctx = await _daily_ctx(hc, tok, stex, code, sess)
    if not m.get("minutes"):
        return {"symbol": code, "name": name, "missing": True}
    prev = ctx.get("prev_close") or m.get("prev_close")
    close = m["session_close"] or m["minutes"][-1]["c"]
    closes = [close] + (ctx.get("hist_closes") or [])
    streak = 0
    if len(closes) > 1:
        sign = 1 if closes[0] > closes[1] else -1
        for i in range(len(closes) - 1):
            d_ = closes[i] - closes[i + 1]
            if (d_ > 0 and sign > 0) or (d_ < 0 and sign < 0):
                streak += 1
            else:
                break
        streak *= sign
    return {"symbol": code, "name": name, "session": sess, "open": m["open"], "high": m["high"], "low": m["low"], "close": close,
            "prev_close": prev, "pct": round((close / prev - 1) * 100, 2) if prev else m.get("session_pct"),
            "value_usd": ctx.get("today_value"), "value_ratio20": round(ctx["today_value"] / ctx["avg20_value"], 2) if ctx.get("today_value") and ctx.get("avg20_value") else None,
            "streak": streak, "pct5": round((closes[0] / closes[5] - 1) * 100, 2) if len(closes) > 5 else None,
            "minutes": m["minutes"] if code == "QQQ" else None, "complete": m.get("complete")}


async def main(run_date: str) -> None:
    raw = day_dir(run_date)
    sess = us_session_for(run_date)
    c = KiwoomClient()
    out = {"run_date": run_date, "session_et": sess, "fetched_at": datetime.now().isoformat(timespec="seconds"), "index": {}, "sectors": {}}
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        for code, stex, name in INDEX_ETF:
            r = await _etf(hc, tok, stex, code, name, sess)
            out["index"][code] = r
            log(run_date, "us_kw", f"{code}: " + str({k: v for k, v in (r or {}).items() if k not in ("minutes",)}))
        for code, stex, name in SECTOR_ETF:
            out["sectors"][code] = await _etf(hc, tok, stex, code, name, sess)
        log(run_date, "us_kw", f"섹터 {sum(1 for v in out['sectors'].values() if v and not v.get('missing'))}/{len(SECTOR_ETF)}")
        out["stocks"], out["links"] = {}, {}
        for code, stex, name in STOCKS:
            out["stocks"][code] = await _etf(hc, tok, stex, code, name, sess)
        for code, stex, name in LINK_ETF:
            out["links"][code] = await _etf(hc, tok, stex, code, name, sess)
        log(run_date, "us_kw", "종목 " + ", ".join(f"{k} {v.get('pct')}" for k, v in out["stocks"].items() if v) + " | 연결 " + ", ".join(f"{k} {v.get('pct')}" for k, v in out["links"].items() if v))
        try:
            r = await hc.get("https://api.upbit.com/v1/ticker?markets=KRW-BTC", timeout=10)
            b = r.json()[0]
            out["btc"] = {"price": b["trade_price"], "chg_pct": round(b["signed_change_rate"] * 100, 2), "src": "업비트 KRW-BTC 24h"}
        except Exception as e:
            out["btc"] = None
            log(run_date, "us_kw", f"업비트 실패: {e}")
    save_json(raw / "us_kiwoom.json", out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")))
