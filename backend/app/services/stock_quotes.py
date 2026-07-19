"""
주식 현재가 서비스 — Yahoo Finance chart API (키 불필요).

국내 주식은 '005930.KS'(코스피)/'.KQ'(코스닥), 미국 주식은 'AAPL'처럼 심볼을
그대로 쓴다. 등락률은 일봉 close 배열의 뒤에서 두 번째 값(= 전일 종가)을
기준으로 계산한다 — meta.previousClose는 주식에서 자주 null이고,
meta.chartPreviousClose는 range 시작점(며칠 전) 종가라 일간 등락률로는 틀리기
때문이다. history(스파크라인용)도 같은 close 배열에서 뽑는다.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FX_SYMBOL = "USDKRW=X"

# ── Yahoo 요청 절약 캐시 ──
# 상시 위젯이 7초마다 폴링하면 Yahoo(비공식 chart API)에 하루 수만 요청이 나가
# 레이트리밋(429)/차단 위험이 있다. 일봉 기반 현재가는 그렇게 자주 안 변하므로
# 심볼당 60초 캐시하고, 조회 실패 시엔 만료된 캐시라도 반환한다(stale-on-error —
# 일시 장애가 "시세 없음(평단 폴백 0%)"으로 보이는 것보다 낫다).
_QUOTE_TTL = 60.0
_FX_TTL = 300.0
_quote_cache: dict[str, tuple[float, StockQuote]] = {}
_fx_cache: tuple[float, float] | None = None  # (ts, rate)

_TIMEOUT = httpx.Timeout(8.0)
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

# 스파크라인용 history 길이 (스펙: "최근 32개 가격")
HISTORY_LEN = 32


@dataclass
class StockQuote:
    symbol: str
    price: float  # 현재가 (원통화)
    change_rate: float  # 전일 대비 등락률 %
    currency: str  # "KRW" | "USD"
    history: list[float] = field(default_factory=list)


def _parse_chart(symbol: str, data: dict) -> StockQuote | None:
    result = (data.get("chart") or {}).get("result")
    if not result:
        return None
    node = result[0]
    meta = node.get("meta", {})
    price = meta.get("regularMarketPrice")
    currency = meta.get("currency", "USD")
    if price is None:
        return None

    # 일봉 종가 배열 (None 제거)
    closes: list[float] = []
    try:
        raw = node["indicators"]["quote"][0]["close"]
        closes = [float(c) for c in raw if c is not None]
    except (KeyError, IndexError, TypeError):
        closes = []

    # 전일 종가: close 배열 뒤에서 두 번째 (마지막은 오늘 forming/종가라 현재가와 중복)
    prev_close = None
    if len(closes) >= 2:
        prev_close = closes[-2]
    elif meta.get("chartPreviousClose"):
        prev_close = float(meta["chartPreviousClose"])  # 최후 폴백 (부정확할 수 있음)

    change_rate = 0.0
    if prev_close:
        change_rate = round((price - prev_close) / prev_close * 100, 2)

    history = closes[-HISTORY_LEN:] if closes else []

    return StockQuote(
        symbol=symbol,
        price=float(price),
        change_rate=change_rate,
        currency=currency,
        history=history,
    )


async def _fetch_one(client: httpx.AsyncClient, symbol: str) -> StockQuote | None:
    # range=3mo면 32거래일 history를 확보하면서 전일 종가도 안정적으로 잡힌다
    resp = await client.get(
        CHART_URL.format(symbol=symbol), params={"range": "3mo", "interval": "1d"}
    )
    resp.raise_for_status()
    return _parse_chart(symbol, resp.json())


async def fetch_stock_quotes(symbols: list[str]) -> dict[str, StockQuote]:
    """symbols는 Yahoo 심볼 그대로('005930.KS', 'AAPL'). 개별 실패는 건너뛰고
    성공한 것만 반환한다 (한 종목 실패가 나머지를 죽이지 않음).

    60초 캐시 + stale-on-error: 신선한 캐시는 그대로 쓰고, 만료된 심볼만 조회하며,
    조회가 실패하면 만료된 값이라도 반환한다 (Yahoo 레이트리밋/일시 장애 대비)."""
    if not symbols:
        return {}
    now = time.monotonic()
    quotes: dict[str, StockQuote] = {}
    stale: list[str] = []
    for s in symbols:
        hit = _quote_cache.get(s)
        if hit and now - hit[0] < _QUOTE_TTL:
            quotes[s] = hit[1]
        else:
            stale.append(s)

    if stale:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            results = await asyncio.gather(
                *(_fetch_one(client, s) for s in stale), return_exceptions=True
            )
        for sym, r in zip(stale, results):
            if isinstance(r, StockQuote):
                quotes[sym] = r
                _quote_cache[sym] = (now, r)
            else:
                old = _quote_cache.get(sym)
                if old:
                    quotes[sym] = old[1]  # stale-on-error
    return quotes


async def fetch_usdkrw() -> float | None:
    """USD→KRW 환율 (5분 캐시 + stale-on-error). 실패하면 None (호출부가 폴백 사용)."""
    global _fx_cache
    now = time.monotonic()
    if _fx_cache and now - _fx_cache[0] < _FX_TTL:
        return _fx_cache[1]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                CHART_URL.format(symbol=FX_SYMBOL), params={"range": "1d", "interval": "1d"}
            )
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
            rate = meta.get("regularMarketPrice")
            if rate:
                _fx_cache = (now, float(rate))
                return float(rate)
            return _fx_cache[1] if _fx_cache else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return _fx_cache[1] if _fx_cache else None  # stale-on-error


# ── 미국주식 캔들 (OHLC) — ChartPanel 일/주/월봉 (Yahoo interval 1d/1wk/1mo) ──
# period → (interval, range). 봉 개수 넉넉하게 range를 잡는다.
_US_PERIOD = {
    "D": ("1d", "1y"),
    "W": ("1wk", "5y"),
    "M": ("1mo", "max"),
}
_US_CANDLE_TTL = 300.0  # 5분 캐시 (일/주/월봉은 자주 안 변함)
_us_candle_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


async def fetch_us_candles(symbol: str, period: str = "D", limit: int = 140) -> list[dict]:
    """미국 티커(Yahoo 심볼)의 OHLC 캔들 최근 limit개. 실패/미상장 시 []."""
    period = period.upper()
    if period not in _US_PERIOD:
        period = "D"
    key = (symbol.upper(), period)
    now = time.monotonic()
    cached = _us_candle_cache.get(key)
    if cached and now - cached[0] < _US_CANDLE_TTL:
        return cached[1]
    interval, rng = _US_PERIOD[period]
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                CHART_URL.format(symbol=symbol), params={"range": rng, "interval": interval}
            )
            resp.raise_for_status()
            node = resp.json()["chart"]["result"][0]
            ts = node.get("timestamp") or []
            q = node["indicators"]["quote"][0]
            opens, highs = q.get("open", []), q.get("high", [])
            lows, closes = q.get("low", []), q.get("close", [])
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return cached[1] if cached else []  # stale-on-error
    out: list[dict] = []
    for t, o, h, low, c in zip(ts, opens, highs, lows, closes):
        if None in (o, h, low, c):
            continue
        dt = time.strftime("%Y%m%d", time.gmtime(t)) if t else ""
        out.append({"dt": dt, "o": float(o), "h": float(h), "l": float(low), "c": float(c), "v": 0})
    out = out[-limit:]
    if out:
        _us_candle_cache[key] = (now, out)
    return out
