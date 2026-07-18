"""
통합 포트폴리오 엔드포인트.

6개 어댑터를 병렬로 부르고, 실패한 것들은 죽이지 않고 errors 배열에 모아서
반환한다 (스펙: "부분 실패 지원"). 7초 TTL 캐시로 폴링 부하를 줄인다.
"""
import asyncio
import time

from fastapi import APIRouter

from ..adapters.base import BaseAdapter
from ..adapters.bithumb import BithumbAdapter
from ..adapters.kis import KISAdapter
from ..adapters.kiwoom import KiwoomAdapter
from ..adapters.krx import KRXAdapter
from ..adapters.manual import ManualAdapter
from ..adapters.upbit import UpbitAdapter
from ..adapters.yahoo import YahooAdapter
from ..cache import TTLCache
from ..db import save_snapshot
from ..schemas import PortfolioSnapshot, Position, SourceError, Totals, TotalsBucket
from ..services import mock_market

router = APIRouter()

ADAPTERS: list[BaseAdapter] = [
    ManualAdapter(),  # 수동입력 (어떤 증권사든 커버하는 폴백)
    KiwoomAdapter(),
    KISAdapter(),
    UpbitAdapter(),
    BithumbAdapter(),
    KRXAdapter(),
    YahooAdapter(),
]

_cache: TTLCache[PortfolioSnapshot] = TTLCache(ttl_seconds=7.0)


def _bucket(positions: list[Position], predicate) -> TotalsBucket:
    matched = [p for p in positions if predicate(p)]
    value = sum(p.value for p in matched)
    cost = sum(p.cost for p in matched)
    pnl = value - cost
    pnl_pct = round(pnl / cost * 100, 2) if cost else 0.0
    return TotalsBucket(value=value, cost=cost, pnl=pnl, pnlPct=pnl_pct)


def _compute_totals(positions: list[Position]) -> Totals:
    return Totals(
        kr=_bucket(positions, lambda p: p.region == "KR"),
        us=_bucket(positions, lambda p: p.region == "US"),
        stock=_bucket(positions, lambda p: p.assetType == "stock"),
        crypto=_bucket(positions, lambda p: p.assetType == "crypto"),
        total=_bucket(positions, lambda _p: True),
    )


async def _build_snapshot() -> PortfolioSnapshot:
    results = await asyncio.gather(*(a.fetch() for a in ADAPTERS))

    positions: list[Position] = []
    sector_flows = []
    errors = []
    real_failures = 0  # "설정 대기"가 아닌 진짜 실패만 센다
    for result in results:
        positions.extend(result.positions)
        sector_flows.extend(result.sector_flows)
        if result.error:
            errors.append(result.error)
            if not result.unconfigured:
                real_failures += 1

    # ── 키움/KRX 연동 전: 프로토타입이 보여주던 시장 정보(수급/랭킹/KR섹터)를
    #    모의 데이터로 채워 UI를 완성한다. UI에 '모의'임이 표기된다. ──
    if not any(s.region == "KR" for s in sector_flows):
        sector_flows.extend(mock_market.kr_sector_flows())
    for p in positions:
        if p.assetType == "stock" and p.region == "KR" and p.investors is None:
            p.investors = mock_market.investors_for(p.symbol)
    market_ranking = mock_market.market_ranking()
    errors.append(
        SourceError(
            source="모의",
            message="시장 랭킹·수급·KR 섹터는 모의 데이터 (키움/KRX 연동 시 실데이터로 대체)",
        )
    )

    snapshot = PortfolioSnapshot(
        totals=_compute_totals(positions),
        positions=positions,
        sectorFlows=sector_flows,
        marketRanking=market_ranking,
        fetchedAt=int(time.time() * 1000),
        errors=errors,
        # 설정 안 된 소스(키 미입력)는 정상 상태다 — 진짜 데이터 조회 실패가
        # 있을 때만 "추정치"로 표시한다 (스펙: isEstimate = UI에서 흐리게)
        isEstimate=real_failures > 0,
    )

    save_snapshot(snapshot.fetchedAt, snapshot.model_dump_json())
    return snapshot


@router.get("/portfolio/snapshot", response_model=PortfolioSnapshot)
async def get_snapshot() -> PortfolioSnapshot:
    return await _cache.get_or_fetch(_build_snapshot)


@router.get("/config/sources")
async def get_source_status() -> dict[str, bool]:
    """각 소스가 설정됐는지만 알려준다 (키 값 자체는 노출 안 함) —
    프론트엔드가 '설정 필요' 상태를 조용히 처리하는 데 쓴다."""
    from ..keychain import has_api_key
    from ..services.holdings import load_manual_holdings

    return {
        "kiwoom": has_api_key("kiwoom", "app_key"),
        "kis": has_api_key("kis", "app_key"),
        "upbit": has_api_key("upbit", "access_key"),
        "bithumb": has_api_key("bithumb", "api_key"),
        "manual": len(load_manual_holdings()) > 0,
    }
