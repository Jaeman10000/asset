"""
공개 시세 서비스 — API 키 없이 동작하는 암호화폐 현재가/등락률 조회.

업비트·빗썸 공개 ticker API는 인증이 필요 없다. 그래서 계좌 조회(보유 수량)와
분리해서, 시세만 먼저 가져올 수 있다. 이 서비스는 두 군데서 쓰인다:
  1) 업비트/빗썸 어댑터 — 보유 수량(계좌 API, 키 필요)에 현재가를 곱해 평가금액 계산
  2) 수동입력 포지션 — 사용자가 수량만 입력하면 현재가는 여기서 채운다

각 마켓 응답을 공통 Quote 형태로 정규화한다.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

UPBIT_TICKER = "https://api.upbit.com/v1/ticker"
BITHUMB_TICKER_ALL = "https://api.bithumb.com/public/ticker/ALL_KRW"

_TIMEOUT = httpx.Timeout(8.0)
_HEADERS = {"Accept": "application/json"}


@dataclass
class Quote:
    symbol: str  # "BTC", "ETH" 등 (마켓 접두사 제거된 순수 심볼)
    price: float  # 현재가 (KRW)
    change_rate: float  # 전일 대비 등락률 % (부호 있음)


def _parse_upbit_rows(rows: list[dict]) -> dict[str, Quote]:
    quotes: dict[str, Quote] = {}
    for row in rows:
        market = row.get("market", "")  # "KRW-BTC"
        symbol = market.split("-", 1)[-1]
        quotes[symbol] = Quote(
            symbol=symbol,
            price=float(row["trade_price"]),
            change_rate=round(float(row.get("signed_change_rate", 0.0)) * 100, 2),
        )
    return quotes


async def fetch_upbit_quotes(symbols: list[str]) -> dict[str, Quote]:
    """symbols: ['BTC', 'ETH', ...] → KRW 마켓 기준 시세.

    업비트는 배치에 존재하지 않는 마켓이 하나라도 섞이면 전체 요청을 404로
    거부한다. 그래서 배치가 실패하면 심볼별로 개별 재조회해서, 오타 하나가
    나머지 멀쩡한 종목 시세까지 죽이지 않도록 한다. 개별 조회도 다 실패하면
    예외를 던진다 (호출부가 SourceError로 변환)."""
    if not symbols:
        return {}
    markets = ",".join(f"KRW-{s.upper()}" for s in symbols)
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        resp = await client.get(UPBIT_TICKER, params={"markets": markets})
        if resp.status_code == 200:
            return _parse_upbit_rows(resp.json())

        # 배치 실패 → 심볼별 개별 재시도 (유효한 것만 건짐)
        quotes: dict[str, Quote] = {}
        any_ok = False
        for s in symbols:
            try:
                r = await client.get(UPBIT_TICKER, params={"markets": f"KRW-{s.upper()}"})
                if r.status_code == 200:
                    quotes.update(_parse_upbit_rows(r.json()))
                    any_ok = True
            except httpx.HTTPError:
                continue
        if not any_ok:
            resp.raise_for_status()  # 전부 실패 → 원래 배치 에러를 던짐
        return quotes


async def fetch_bithumb_quotes(symbols: list[str]) -> dict[str, Quote]:
    """빗썸은 ALL_KRW로 전체를 한 번에 받고 필요한 심볼만 추린다
    (심볼별 개별 호출보다 요청 수가 적다)."""
    if not symbols:
        return {}
    wanted = {s.upper() for s in symbols}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        resp = await client.get(BITHUMB_TICKER_ALL)
        resp.raise_for_status()
        payload = resp.json()

    if payload.get("status") != "0000":
        raise RuntimeError(f"빗썸 시세 응답 오류: status={payload.get('status')}")

    data = payload.get("data", {})
    quotes: dict[str, Quote] = {}
    for symbol, row in data.items():
        if symbol == "date" or symbol not in wanted:
            continue
        if not isinstance(row, dict):
            continue
        quotes[symbol] = Quote(
            symbol=symbol,
            price=float(row["closing_price"]),
            change_rate=round(float(row.get("fluctate_rate_24H", 0.0)), 2),
        )
    return quotes
