"""
Yahoo Finance — 11개 SPDR 섹터 ETF 전일 종가 기준 등락률 (스펙: "미국 섹터 성과는
Yahoo Finance API로 무료"). 계정/API 키가 필요 없는 공개 데이터라 지금 바로
실제로 동작하는 유일한 어댑터다.

비공식 chart 엔드포인트(v8/finance/chart)를 쓴다 — quote 엔드포인트(v7)는
최근 crumb/쿠키 인증을 요구하는 경우가 많아 더 불안정하다.
"""
import asyncio

import httpx

from ..schemas import SectorFlow, SourceError
from .base import AdapterResult, BaseAdapter

# 스펙: "미국 섹터도 한글 이름"
SPDR_SECTORS: list[tuple[str, str]] = [
    ("XLK", "기술"),
    ("XLF", "금융"),
    ("XLV", "헬스케어"),
    ("XLY", "임의소비재"),
    ("XLP", "필수소비재"),
    ("XLE", "에너지"),
    ("XLI", "산업재"),
    ("XLB", "소재"),
    ("XLRE", "부동산"),
    ("XLU", "유틸리티"),
    ("XLC", "커뮤니케이션"),
]

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooAdapter(BaseAdapter):
    name = "yahoo"

    async def _fetch_one(
        self, client: httpx.AsyncClient, symbol: str, name_ko: str
    ) -> SectorFlow | None:
        resp = await client.get(
            CHART_URL.format(symbol=symbol), params={"range": "5d", "interval": "1d"}
        )
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("chart") or {}).get("result")
        if not result:
            return None

        node = result[0]
        meta = node.get("meta", {})
        price = meta.get("regularMarketPrice")
        volume = meta.get("regularMarketVolume")
        if price is None:
            return None

        # 전일 종가: 일봉 close 배열의 뒤에서 두 번째 (마지막은 오늘 값).
        # meta.previousClose는 자주 null이고 chartPreviousClose는 range 시작점
        # (5일 전) 종가라 일간 등락률이 아니라 5일 등락률이 나온다 — 그 버그를 피함.
        prev_close = None
        try:
            closes = [c for c in node["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) >= 2:
                prev_close = float(closes[-2])
        except (KeyError, IndexError, TypeError):
            prev_close = None
        if not prev_close:
            prev_close = meta.get("chartPreviousClose")  # 최후 폴백
        if not prev_close:
            return None

        ret_pct = (price - prev_close) / prev_close * 100
        return SectorFlow(
            region="US",
            id=symbol,
            name=name_ko,
            ret=round(ret_pct, 2),
            volume=volume,
        )

    async def fetch(self) -> AdapterResult:
        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    )
                },
            ) as client:
                results = await asyncio.gather(
                    *(self._fetch_one(client, sym, name) for sym, name in SPDR_SECTORS),
                    return_exceptions=True,
                )
        except Exception as exc:  # 클라이언트 자체 생성 실패 등
            return AdapterResult(
                error=SourceError(source=self.name, message=f"Yahoo Finance 연결 실패: {exc}")
            )

        flows: list[SectorFlow] = []
        failed = 0
        for r in results:
            if isinstance(r, SectorFlow):
                flows.append(r)
            else:
                failed += 1

        if not flows:
            return AdapterResult(
                error=SourceError(source=self.name, message="Yahoo Finance 응답 없음 (전체 실패)")
            )

        error = None
        if failed:
            error = SourceError(
                source=self.name,
                message=f"섹터 {failed}/{len(SPDR_SECTORS)}개 조회 실패 (부분 성공)",
            )

        return AdapterResult(sector_flows=flows, error=error)
