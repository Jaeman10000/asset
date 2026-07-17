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
from dataclasses import dataclass, field

import httpx

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FX_SYMBOL = "USDKRW=X"

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
    성공한 것만 반환한다 (한 종목 실패가 나머지를 죽이지 않음)."""
    if not symbols:
        return {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        results = await asyncio.gather(
            *(_fetch_one(client, s) for s in symbols), return_exceptions=True
        )
    quotes: dict[str, StockQuote] = {}
    for sym, r in zip(symbols, results):
        if isinstance(r, StockQuote):
            quotes[sym] = r
    return quotes


async def fetch_usdkrw() -> float | None:
    """USD→KRW 환율. 실패하면 None (호출부가 폴백 환율 사용)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(
                CHART_URL.format(symbol=FX_SYMBOL), params={"range": "1d", "interval": "1d"}
            )
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
            rate = meta.get("regularMarketPrice")
            return float(rate) if rate else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None
