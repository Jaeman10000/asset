"""
수동입력 어댑터 — data/holdings.json의 보유 종목을 Position으로 변환.

시세는 전부 공개 API(키 불필요)로 채운다:
  - 암호화폐: 업비트/빗썸 공개 ticker
  - 주식: Yahoo Finance chart (국내 '005930.KS' / 미국 'AAPL')
평가금액(value)/매수금액(cost)은 전부 KRW로 환산한다 (미국 주식은 USD→KRW 환율 적용).
API 키가 전혀 필요 없어서, 어떤 증권사 사용자든 보유 종목을 직접 적으면 대시보드가 채워진다.
"""
from __future__ import annotations

import time
from typing import Any

import asyncio

from ..schemas import Position, SourceError
from ..services.holdings import load_manual_holdings
from ..services.quotes import (
    Quote,
    fetch_bithumb_history,
    fetch_bithumb_quotes,
    fetch_upbit_history,
    fetch_upbit_quotes,
)
from ..services.stock_quotes import StockQuote, fetch_stock_quotes, fetch_usdkrw
from .base import AdapterResult, BaseAdapter

# 환율 조회 실패 시 폴백 (대략치 — UI에서 isEstimate로 걸러짐)
_FALLBACK_USDKRW = 1350.0


def _yahoo_symbol(r: dict[str, Any]) -> str:
    """보유 종목 dict를 Yahoo Finance 심볼로 매핑.
    - 명시적 'yahoo' 필드가 있으면 그대로 사용 (코스닥/우선주 등 예외 대응)
    - 국내(region KR): 기본 '.KS'(코스피). 코스닥은 holdings에 'yahoo':'XXXXXX.KQ'로 지정
    - 미국(region US 등): 심볼 그대로
    """
    if r.get("yahoo"):
        return str(r["yahoo"])
    symbol = str(r["symbol"])
    if r.get("region") == "KR":
        return f"{symbol}.KS"
    return symbol


class ManualAdapter(BaseAdapter):
    name = "manual"

    async def fetch(self) -> AdapterResult:
        # 손편집된 holdings.json은 신뢰할 수 없다 — dict가 아니거나 symbol이 없는
        # 행은 시세 조회·포지션 변환 모두 불가하므로 여기서 조용히 걸러낸다.
        # (한 행이 깨져도 나머지는 살린다는 부분실패 원칙. 상세 방어는 _to_position.)
        raw = [r for r in load_manual_holdings() if isinstance(r, dict) and r.get("symbol")]
        if not raw:
            return AdapterResult()  # 수동입력 미사용/전부 무효 — 조용히 빈 결과 (에러 아님)

        crypto_rows = [r for r in raw if r.get("assetType") == "crypto"]
        stock_rows = [r for r in raw if r.get("assetType") == "stock"]

        errors: list[str] = []
        crypto_quotes: dict[str, Quote] = {}
        stock_quotes: dict[str, StockQuote] = {}
        fx = _FALLBACK_USDKRW

        # --- 암호화폐 시세 (업비트/빗썸) ---
        upbit_symbols = [
            r["symbol"] for r in crypto_rows if r.get("market", "upbit") == "upbit"
        ]
        bithumb_symbols = [
            r["symbol"] for r in crypto_rows if r.get("market") == "bithumb"
        ]
        if upbit_symbols:
            try:
                crypto_quotes.update(await fetch_upbit_quotes(upbit_symbols))
            except Exception as exc:
                errors.append(f"업비트 시세 실패: {exc}")
        if bithumb_symbols:
            try:
                crypto_quotes.update(await fetch_bithumb_quotes(bithumb_symbols))
            except Exception as exc:
                errors.append(f"빗썸 시세 실패: {exc}")

        # --- 암호화폐 스파크라인 히스토리 (60분봉 종가, 실데이터) ---
        crypto_histories: dict[str, list[float]] = {}
        if crypto_rows:
            hist_syms = [str(r["symbol"]).upper() for r in crypto_rows]
            hist_results = await asyncio.gather(
                *(
                    fetch_bithumb_history(sym)
                    if r.get("market") == "bithumb"
                    else fetch_upbit_history(sym)
                    for r, sym in zip(crypto_rows, hist_syms)
                )
            )
            crypto_histories = dict(zip(hist_syms, hist_results))

        # --- 주식 시세 (Yahoo) + 환율 ---
        if stock_rows:
            yahoo_symbols = [_yahoo_symbol(r) for r in stock_rows]
            try:
                stock_quotes = await fetch_stock_quotes(yahoo_symbols)
            except Exception as exc:
                errors.append(f"주식 시세 실패: {exc}")
            # 미국 주식(USD)이 하나라도 있으면 환율 필요
            if any(r.get("region") != "KR" for r in stock_rows):
                rate = await fetch_usdkrw()
                if rate:
                    fx = rate
                else:
                    errors.append(f"환율 조회 실패 (폴백 {_FALLBACK_USDKRW:.0f} 사용)")

        now = int(time.time() * 1000)
        positions: list[Position] = []
        for r in raw:
            pos = self._to_position(r, crypto_quotes, stock_quotes, crypto_histories, fx, now)
            if pos is not None:
                positions.append(pos)

        error = None
        if errors:
            error = SourceError(
                source=self.name,
                message="; ".join(errors) + " (해당 종목은 평단으로 대체 표시)",
            )
        return AdapterResult(positions=positions, error=error)

    def _to_position(
        self,
        r: dict[str, Any],
        crypto_quotes: dict[str, Quote],
        stock_quotes: dict[str, StockQuote],
        crypto_histories: dict[str, list[float]],
        fx: float,
        now: int,
    ) -> Position | None:
        # 한 행이라도 잘못되면(assetType/region/currency 오타로 pydantic Literal 위반,
        # qty/avg 파싱 실패 등) 그 행만 건너뛰고 나머지는 살린다. 전체 스냅샷이
        # 500으로 죽어 앱이 "영구 오프라인"이 되던 문제(QA 재현)를 막기 위해
        # Position() 생성까지 포함해 함수 전체를 방어한다.
        try:
            symbol = str(r["symbol"])
            qty = float(r["qty"])
            avg = float(r["avg"])

            asset_type = r.get("assetType", "crypto")
            history: list[float] = []

            # 통화: 명시값 > (미국주식이면 USD) > 기본 KRW
            currency = r.get("currency")
            if currency is None:
                currency = "USD" if (asset_type == "stock" and r.get("region") != "KR") else "KRW"

            # 현재가(원통화 기준) 결정
            price = avg  # 폴백: 시세 없으면 평단
            if asset_type == "crypto":
                q = crypto_quotes.get(symbol.upper())
                if q is not None:
                    price = q.price
                history = crypto_histories.get(symbol.upper(), [])
            elif asset_type == "stock":
                sq = stock_quotes.get(_yahoo_symbol(r))
                if sq is not None:
                    price = sq.price
                    history = sq.history
                    if sq.currency:
                        currency = sq.currency  # Yahoo가 알려준 실제 통화로 정정

            # 원통화 기준 수익률 (환율과 무관 — 같은 통화끼리 비교)
            ret = round((price - avg) / avg * 100, 2) if avg else 0.0

            # KRW 환산: USD 자산이면 환율 곱함
            krw = fx if currency == "USD" else 1.0
            value = qty * price * krw
            cost = qty * avg * krw

            return Position(
                id=f"manual:{symbol}",
                exchange="manual",
                assetType=asset_type,
                region=r.get("region"),
                symbol=symbol,
                name=r.get("name", symbol),
                qty=qty,
                avg=avg,
                price=price,
                currency=currency,
                value=value,
                cost=cost,
                ret=ret,
                history=history,
                sector=r.get("sector"),
                lastUpdated=now,
            )
        except Exception:
            return None  # 손상된 행은 조용히 건너뜀 (부분실패 원칙)
