"""
통합 포트폴리오 엔드포인트.

6개 어댑터를 병렬로 부르고, 실패한 것들은 죽이지 않고 errors 배열에 모아서
반환한다 (스펙: "부분 실패 지원"). 7초 TTL 캐시로 폴링 부하를 줄인다.
"""
import asyncio
import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..adapters.base import BaseAdapter
from ..adapters.bithumb import BithumbAdapter
from ..adapters.kiwoom import KiwoomAdapter
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
    UpbitAdapter(),
    BithumbAdapter(),
    YahooAdapter(),
]
# KIS(한국투자증권)·KRX 어댑터는 제거 — KIS는 키움 연동으로 불필요, KRX는 미구현
# 스텁이라 '대기/오류'만 띄웠다. 필요해지면 다시 ADAPTERS에 추가한다.

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
        if result.warning:
            # 부가정보(랭킹/섹터)만 실패한 경우 — 내 자산가치는 정확하므로 isEstimate엔
            # 영향 안 주지만, "왜 모의로 폴백했는지"는 화면에 보이게 한다.
            errors.append(result.warning)

    # ── 실데이터(키움)로 채워지지 않은 시장 정보만 모의로 보충한다.
    #    모의가 하나라도 섞이면 marketMock=True로 내려 프론트가 "샘플" 워터마크를 씌운다.
    #    키움 연동 시 랭킹은 실데이터로 대체되고, 남은 수급/섹터만 모의로 표시된다. ──
    # marketMock = '섹터 카드가 모의인가'만 뜻한다. 개별 보유종목 수급이 아직 안
    # 채워진 건(투자자 mock 주입) 종목별 investorsMock으로 따로 표시하지, 섹터 카드
    # 배지(샘플)를 켜지 않는다 — 테마 섹터가 실데이터인데 "샘플"로 잘못 뜨는 걸 막음.
    market_mock = False
    if not any(s.region == "KR" for s in sector_flows):
        sector_flows.extend(mock_market.kr_sector_flows())
        market_mock = True
    # (v0.4에서 제거) 보유 종목 수급이 아직 안 받아졌을 때 mock을 주입하던 로직 —
    # 키움 실연동 후엔 '가짜 수급이 진짜처럼' 보이는 해악만 남는다(실측: 삼성전자에
    # program=+14 같은 존재하지 않는 값이 꽂힘). 못 받았으면 그냥 비워두고,
    # 호버 시 on-demand(/flow)가 채운다 — 실데이터만 원칙.
    # 시장 랭킹: 키움 실데이터가 있으면 그걸(rankingMock=False), 없으면 모의로
    if real_ranking:
        market_ranking = real_ranking
        ranking_mock = False
    else:
        market_ranking = mock_market.market_ranking()
        for m in market_ranking:
            m.investorsMock = True
        ranking_mock = True
    if market_mock or ranking_mock:
        errors.append(
            SourceError(
                source="모의",
                message="섹터·수급"
                + ("·랭킹" if ranking_mock else "")
                + "은 모의 데이터 (키움 연동 시 실데이터로 대체)",
            )
        )

    from ..services.market_hours import kr_session, us_session

    snapshot = PortfolioSnapshot(
        totals=_compute_totals(positions),
        positions=positions,
        sectorFlows=sector_flows,
        marketRanking=market_ranking,
        fetchedAt=int(time.time() * 1000),
        krSession=kr_session(),
        usSession=us_session(),
        errors=errors,
        # 설정 안 된 소스(키 미입력)는 정상 상태다 — 진짜 데이터 조회 실패가
        # 있을 때만 "추정치"로 표시한다 (스펙: isEstimate = UI에서 흐리게)
        isEstimate=real_failures > 0,
        marketMock=market_mock,
        rankingMock=ranking_mock,
    )

    # 동기 sqlite write를 스레드풀로 — async 요청 경로에서 이벤트 루프 블로킹 방지(QA)
    await run_in_threadpool(save_snapshot, snapshot.fetchedAt, snapshot.model_dump_json())
    return snapshot


@router.get("/portfolio/snapshot", response_model=PortfolioSnapshot)
async def get_snapshot(fresh: bool = False) -> PortfolioSnapshot:
    """fresh=1이면 스냅샷 7초 캐시 + 종목 수급/일봉 캐시까지 비우고 즉시 재조회한다
    (수동 새로고침 버튼용 — '지금 이 순간'의 최신 수급을 받아온다)."""
    if fresh:
        from ..adapters import kiwoom

        kiwoom.clear_caches()
        _cache.clear()
    return await _cache.get_or_fetch(_build_snapshot)


@router.get("/chart/{code}")
async def get_chart(code: str, period: str = "D", market: str = "kr") -> dict:
    """종목 캔들(OHLC) — ChartPanel이 종목 클릭/기간전환 시 호출. 일(D)/주(W)/월(M)봉.
    market=kr → 키움 ka10081/82/83, market=us → Yahoo(1d/1wk/1mo). 암호화폐/실패면
    candles=[] (프론트가 보유 history 라인으로 폴백)."""
    p = (period or "D").upper()
    if market == "us":
        from ..services.stock_quotes import fetch_us_candles

        candles = await fetch_us_candles(code, p)
    else:
        from ..adapters.kiwoom import fetch_candles

        candles = await fetch_candles(code, p)
    return {"code": code, "period": p, "market": market, "candles": candles}


@router.get("/flow/{code}")
async def get_flow(code: str) -> dict:
    """단일 KR 종목 종목별 수급(외국인/기관/개인, 당일+20/60일) — 호버 시 on-demand.
    스냅샷 통합조회는 시간예산에 잘려 보유·랭킹 대부분을 못 채우므로, 호버한 종목만
    즉석 조회한다. 미설정/실패/데이터없음이면 investors=null(프론트가 '수급 없음' 표기)."""
    from ..adapters.kiwoom import fetch_flow

    built = await fetch_flow(code)
    if not built:
        return {"code": code, "investors": None, "investorPeriods": []}
    inv, periods = built
    return {
        "code": code,
        "investors": inv.model_dump(),
        "investorPeriods": [p.model_dump() for p in periods],
    }


_perf_cache: dict = {"at": 0.0, "data": None}


@router.get("/portfolio/perf")
async def get_portfolio_perf() -> dict:
    """기간별 손익 (v0.3 도넛 카드 기간 칩) — 스냅샷 DB 시계열에서 계산.
    기간 시작 직전 스냅샷을 기준선으로: 손익 = 현재총액 − 기준총액. 60초 캐시."""
    import time as _t

    from ..db import total_series

    now = _t.time()
    if _perf_cache["data"] and now - _perf_cache["at"] < 60:
        return _perf_cache["data"]
    series = await run_in_threadpool(total_series)
    out: dict = {"periods": {}}
    if series:
        cur_ts, cur_v = series[-1]
        day = 86400_000
        spans = {"D": day, "W": 7 * day, "M": 30 * day, "6M": 182 * day, "1Y": 365 * day, "ALL": None}
        for label, span in spans.items():
            if span is None:
                base = series[0]
            else:
                cutoff = cur_ts - span
                # 기간 시작 '직전' 스냅샷 (없으면 기간 내 첫 스냅샷)
                before = [r for r in series if r[0] <= cutoff]
                base = before[-1] if before else series[0]
            b_ts, b_v = base
            won = cur_v - b_v
            out["periods"][label] = {
                "won": round(won),
                "pct": round(won / b_v * 100, 2) if b_v else 0.0,
                "baseTs": b_ts,
                # 데이터가 기간을 다 못 덮으면(예: 6M인데 DB가 34일치) 실제 커버 일수 표기
                "coveredDays": round((cur_ts - b_ts) / day, 1),
            }
        out["total"] = round(cur_v)
        out["ts"] = cur_ts
    _perf_cache.update(at=now, data=out)
    return out


@router.get("/news")
async def get_news() -> dict:
    """마켓 뉴스 — 언론사 공개 RSS 수집 (10분 캐시, stale-on-error)."""
    from ..services.news_feed import fetch_news

    items = await fetch_news()
    return {"items": items}


@router.get("/signal/top")
async def get_flow_top(scope: str = "market") -> dict:
    """수급 시그널 — 추적 풀에서 오늘 외+기 순매수/순매도 상위. scope=market|held.
    (/flow/top으로 두면 /flow/{code}가 'top'을 종목코드로 삼켜버려 경로를 분리했다)"""
    from ..adapters.kiwoom import flow_top

    return await flow_top("held" if scope == "held" else "market")


# 자금 흐름 API는 /moneyflow/* 네임스페이스 — /flow/{code}(종목 수급)가 경로 변수라
# /flow/status 같은 이름을 종목코드로 삼켜버린다(실측: status가 code="status"로 처리됨).
@router.get("/moneyflow/status")
async def get_flow_status() -> dict:
    """자금 흐름 아카이브 상태 — 저장 일수·기간·용량·폴더 경로."""
    from ..services import flow_collector
    return flow_collector.status()


class CollectBody(BaseModel):
    pages: int = 1  # 1=최근 100거래일, 5≈2년 소급


@router.post("/moneyflow/collect")
async def post_flow_collect(body: CollectBody) -> dict:
    """수집 실행 — 백필(pages>1) 또는 최신 보충(pages=1). 이미 저장된 날짜는 건너뜀."""
    from ..services import flow_collector
    return await flow_collector.collect(pages=max(1, min(8, body.pages)))


@router.get("/moneyflow/history")
async def get_flow_history(days: int = 120) -> dict:
    """히트맵·전이 분석용 테마 일별 시계열."""
    from ..services import flow_store
    rows = flow_store.sector_series(max(5, min(400, days)))
    from ..services.themes import CODE_NAME
    out = {}
    dates = []
    for date, theme, f, i, v, s, leader in rows:
        if date not in out:
            out[date] = {}
            dates.append(date)
        out[date][theme] = {
            "foreign": f, "inst": i, "value": v, "strength": s,
            "leader": CODE_NAME.get(leader or "", leader),
        }
    return {"dates": sorted(set(dates)), "byDate": out, "archive": flow_store.archive_stats()}


@router.get("/moneyflow/forecast")
async def get_flow_forecast() -> dict:
    """예상 경로 — 후보 테마 top3 + 주도주 5 + 워크포워드 백테스트 적중률."""
    from ..services import forecast
    return await run_in_threadpool(forecast.forecast)


@router.get("/stocks/master")
async def get_stock_master() -> dict:
    """전 종목 마스터(KOSPI+KOSDAQ ≈4,300) — 검색 자동완성용. 서버 하루 1회 캐시.
    프론트는 이걸 한 번 받아 로컬에서 검색하므로 타이핑 중 API 호출이 없다."""
    from ..services.stock_master import fetch_master

    items = await fetch_master()
    return {"count": len(items), "items": items}


@router.get("/stocks/info/{code}")
async def get_stock_info(code: str) -> dict:
    """단일 종목 기본정보(ka10001) — 검색 상세 헤더·52주·시총·PER 등.
    장중 60초 캐시, 장외엔 캐시 유지(값이 안 변함)."""
    from ..adapters.kiwoom import fetch_stock_info

    info = await fetch_stock_info(code)
    return {"code": code, "info": info}


@router.get("/watchlist")
async def get_watchlist() -> dict:
    from ..services.watchlist import load_watchlist

    return {"items": load_watchlist()}


class WatchlistBody(BaseModel):
    items: list[dict]


@router.put("/watchlist")
async def put_watchlist(body: WatchlistBody) -> dict:
    from ..services.watchlist import save_watchlist

    return {"items": save_watchlist(body.items)}


@router.get("/watchlist/quotes")
async def get_watchlist_quotes() -> dict:
    """관심종목 시세 한 방 조회 — 행마다 현재가·등락률 + 스파크라인(최근 30일 종가).
    ka10001은 장중 60초 캐시·캔들은 5분 캐시라 폴링해도 호출이 적다."""
    import asyncio as _aio

    from ..adapters.kiwoom import fetch_candles, fetch_stock_info
    from ..services.watchlist import load_watchlist

    items = load_watchlist()
    sem = _aio.Semaphore(4)

    async def one(it: dict) -> dict:
        async with sem:
            info = await fetch_stock_info(it["code"])
            candles = await fetch_candles(it["code"], "D", 30)
        row = {"code": it["code"], "name": it["name"], "spark": [c["c"] for c in candles]}
        if info:
            row.update(price=info["price"], ret=info["ret"], name=info["name"] or it["name"])
        return row

    rows = await _aio.gather(*(one(it) for it in items))
    return {"items": list(rows)}


@router.get("/crypto/context")
async def get_crypto_context(symbols: str = "") -> dict:
    """크립토 시장 지표 — 도미넌스·공포탐욕 + 코인별 글로벌 시세(김프 계산용).
    무료 공개 API(코인게코·alternative.me), 서버 캐시 2~30분."""
    from ..services.crypto_context import get_context

    syms = [s.strip() for s in symbols.split(",") if s.strip()][:20]
    return await get_context(syms)


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
        (
            "rkinfo",
            "ka10027",
            {
                "mrkt_tp": "000",
                "sort_tp": "1",
                "trde_qty_cnd": "0000",
                "stk_cnd": "0",
                "crd_cnd": "0",
                "updown_incls": "1",
                "pric_cnd": "0",
                "trde_prica_cnd": "0",
                "stex_tp": "3",
            },
        ),  # 상승률 상위
    ]
    out: dict = {"configured": True, "is_mock": c.is_mock}
    for cat, tr, body in calls:
        try:
            out[tr] = await c.call(cat, tr, body)
        except Exception as exc:  # noqa: BLE001
            out[tr] = {"error": str(exc)}
    return out


class KiwoomConfigIn(BaseModel):
    app_key: str
    app_secret: str
    is_mock: bool = False
    account_no: str | None = None


@router.get("/config/kiwoom")
async def get_kiwoom_config() -> dict:
    """키움 연동 상태 (값은 노출하지 않음)."""
    from ..keychain import get_api_key, has_api_key

    return {
        "configured": has_api_key("kiwoom", "app_key") and has_api_key("kiwoom", "app_secret"),
        "isMock": get_api_key("kiwoom", "is_mock") == "1",
        "hasAccount": has_api_key("kiwoom", "account_no"),
    }


@router.put("/config/kiwoom")
async def set_kiwoom_config(cfg: KiwoomConfigIn) -> dict:
    """앱 안에서 키움 앱키/시크릿을 저장한다 (터미널 불필요). OS 키체인에만 저장."""
    from ..keychain import set_api_key
    from ..services.kiwoom_client import KiwoomClient

    set_api_key("kiwoom", "app_key", cfg.app_key.strip())
    set_api_key("kiwoom", "app_secret", cfg.app_secret.strip())
    set_api_key("kiwoom", "is_mock", "1" if cfg.is_mock else "0")
    if cfg.account_no and cfg.account_no.strip():
        set_api_key("kiwoom", "account_no", cfg.account_no.strip())
    # 캐시된 토큰·스냅샷 무효화 → 다음 조회부터 새 키로
    KiwoomClient._token = None
    KiwoomClient._token_exp = 0.0
    _cache.clear()
    return {"ok": True}


class CryptoConfigIn(BaseModel):
    upbit_access: str | None = None
    upbit_secret: str | None = None
    bithumb_key: str | None = None
    bithumb_secret: str | None = None


@router.get("/config/crypto")
async def get_crypto_config() -> dict:
    """업비트/빗썸 연동 상태 (값 노출 안 함)."""
    from ..keychain import has_api_key

    return {
        "upbit": has_api_key("upbit", "access_key") and has_api_key("upbit", "secret_key"),
        "bithumb": has_api_key("bithumb", "api_key") and has_api_key("bithumb", "secret_key"),
    }


@router.put("/config/crypto")
async def set_crypto_config(cfg: CryptoConfigIn) -> dict:
    """앱 안에서 업비트/빗썸 API 키 저장 (터미널 불필요). OS 키체인에만 저장."""
    from ..keychain import set_api_key

    saved = []
    if cfg.upbit_access and cfg.upbit_secret:
        set_api_key("upbit", "access_key", cfg.upbit_access.strip())
        set_api_key("upbit", "secret_key", cfg.upbit_secret.strip())
        saved.append("upbit")
    if cfg.bithumb_key and cfg.bithumb_secret:
        set_api_key("bithumb", "api_key", cfg.bithumb_key.strip())
        set_api_key("bithumb", "secret_key", cfg.bithumb_secret.strip())
        saved.append("bithumb")
    _cache.clear()  # 다음 조회부터 새 키로
    return {"ok": True, "saved": saved}


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
