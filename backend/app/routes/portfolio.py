"""
통합 포트폴리오 엔드포인트.

6개 어댑터를 병렬로 부르고, 실패한 것들은 죽이지 않고 errors 배열에 모아서
반환한다 (스펙: "부분 실패 지원"). 7초 TTL 캐시로 폴링 부하를 줄인다.
"""
import asyncio
import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

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
    # return_exceptions=True: 어댑터 하나가 예외를 던져도 전체 스냅샷이 500으로
    # 죽지 않게 한다 (부분실패 원칙 — 나머지 어댑터 결과는 살린다).
    results = await asyncio.gather(
        *(a.fetch() for a in ADAPTERS), return_exceptions=True
    )

    positions: list[Position] = []
    sector_flows = []
    real_ranking: list = []  # 실데이터 랭킹(키움) — 있으면 mock 대신 사용
    errors = []
    real_failures = 0  # "설정 대기"가 아닌 진짜 실패만 센다
    for adapter, result in zip(ADAPTERS, results):
        if isinstance(result, BaseException):
            # 어댑터가 통째로 터진 경우: 로그성 에러로 담고 진짜 실패로 카운트
            errors.append(
                SourceError(source=adapter.name, message=f"어댑터 예외: {result}")
            )
            real_failures += 1
            continue
        positions.extend(result.positions)
        sector_flows.extend(result.sector_flows)
        if result.market_ranking:
            real_ranking = result.market_ranking
        if result.error:
            errors.append(result.error)
            # 설정 대기(키 미입력)·배경 시장데이터(US 섹터) 실패는 내 자산 평가와
            # 무관하므로 isEstimate(전체 흐림) 판정에서 제외한다.
            if not result.unconfigured and not result.background:
                real_failures += 1

    # ── 실데이터(키움)로 채워지지 않은 시장 정보만 모의로 보충한다.
    #    모의가 하나라도 섞이면 marketMock=True로 내려 프론트가 "샘플" 워터마크를 씌운다.
    #    키움 연동 시 랭킹은 실데이터로 대체되고, 남은 수급/섹터만 모의로 표시된다. ──
    market_mock = False
    if not any(s.region == "KR" for s in sector_flows):
        sector_flows.extend(mock_market.kr_sector_flows())
        market_mock = True
    for p in positions:
        if p.assetType == "stock" and p.region == "KR" and p.investors is None:
            p.investors = mock_market.investors_for(p.symbol)
            p.investorPeriods = mock_market.investor_periods_for(p.symbol)
            market_mock = True
    # 시장 랭킹: 키움 실데이터가 있으면 그걸, 없으면 모의로
    if real_ranking:
        market_ranking = real_ranking
    else:
        market_ranking = mock_market.market_ranking()
        market_mock = True
    if market_mock:
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
        marketMock=market_mock,
    )

    # 동기 sqlite write를 스레드풀로 — async 요청 경로에서 이벤트 루프 블로킹 방지(QA)
    await run_in_threadpool(save_snapshot, snapshot.fetchedAt, snapshot.model_dump_json())
    return snapshot


@router.get("/portfolio/snapshot", response_model=PortfolioSnapshot)
async def get_snapshot() -> PortfolioSnapshot:
    return await _cache.get_or_fetch(_build_snapshot)


@router.get("/debug/kiwoom")
async def debug_kiwoom() -> dict:
    """키움 실제 응답 원문을 그대로 반환 — 필드 매핑 확정용(로컬 전용).
    키 등록 후 http://127.0.0.1:8787/debug/kiwoom 을 열어 응답 키 이름을 확인한다."""
    from ..services.kiwoom_client import KiwoomClient

    c = KiwoomClient()
    if not c.configured:
        return {"configured": False, "hint": "키움 앱키/시크릿 미설정"}
    calls = [
        ("acnt", "kt00005", {"qry_tp": "1", "dmst_stex_tp": "KRX"}),  # 잔고
        ("rkinfo", "ka10027", {"mrkt_tp": "000"}),  # 상승률 상위
    ]
    out: dict = {"configured": True, "is_mock": c.is_mock}
    for cat, tr, body in calls:
        try:
            out[tr] = await c.call(cat, tr, body)
        except Exception as exc:  # noqa: BLE001
            out[tr] = {"error": str(exc)}
    return out


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
