"""키움 REST API 어댑터 — 실계좌 보유종목 + 종목별 수급 + 시장 순위.

앱키/시크릿이 keychain에 있으면 실제 REST를 호출한다(services/kiwoom_client).
없으면 unconfigured로 조용히 넘어가 mock_market이 채운다.

실제 응답으로 확정한 필드/TR:
  - 잔고 kt00005: 리스트 stk_cntr_remn, 종목코드 stk_cd("A" 접두사),
    보유수량 cur_qty, 평단 buy_uv, 현재가 cur_prc, 종목명 stk_nm.
  - 종목별투자자 ka10059(stkinfo): dt 필수(YYYYMMDD), 리스트 stk_invsr_orgn,
    일별 순매수(백만원) 외국인 frgnr_invsr / 기관 orgn / 개인 ind_invsr.
    일별이라 최근 N행을 합산해 20/60일 누적을 만든다.
  - 순위 ka10027(등락률상위)/ka10030(거래량상위): sort_tp 등 필수 파라미터.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from ..schemas import (
    InvestorFlow,
    InvestorPeriod,
    MarketStock,
    Position,
    SectorFlow,
    SourceError,
)
from ..services.kiwoom_client import KiwoomClient, KiwoomError
from .base import AdapterResult, BaseAdapter

# 종목별 투자자 순매수(ka10059) 금액 단위 = 백만원 → 억원 환산(÷100). acc_trde_prica 교차검증.
_AMT_TO_EOK = 100.0
# 업종별 투자자 순매수(ka10051, amt_qty_tp=1) 값은 억원 직접(종합KOSPI 개인≈+7,900 = +7,900억).
_SECT_TO_EOK = 1.0

# 일봉·수급은 인트라데이로 거의 안 변하므로 스냅샷 7s 캐시보다 길게 둔다
# (스냅샷마다 종목별 ka10081/ka10059를 다시 부르면 레이트리밋·지연). 모듈 레벨 캐시.
_HIST_TTL = 600.0  # 일봉(종가) 10분
_FLOW_TTL = 180.0  # 수급 3분
_HIST_LEN = 120  # 보관 일봉 개수(스파크라인·차트용)

# 랭킹 '껍데기 상한가' 제외 — 거래대금 하한. 실측: 상승률 상위 20개 중 원풍물산은
# +29.84%인데 하루 거래대금이 3천만원, 엔젠바이오·비케이홀딩스는 2억이다. 몇 천만원으로
# 만들어지는 상한가는 시장 신호가 아니라 노이즈다. 50억이면 이런 껍데기는 걸러지면서
# 실제 자금이 들어온 상한가(에브리봇 114억·코스모로보틱스 342억)는 살아남는다.
_MIN_TRDE_PRICA = 50e8
# 키움이 32비트 한계로 잘라 보내는 쓰레기 거래량(2^32-1). 실제값이 아니므로 '미상' 처리
# (실측: ka10030 거래량 1위 KODEX 200선물인버스2X = 4,294,967,295).
_QTY_OVERFLOW = 4294967295.0
# ka10059의 flu_rt는 1/100 단위(1273 = 12.73%). ka10027의 flu_rt(30.00 = 30%)와 스케일이
# 달라서 그대로 쓰면 100배가 된다(유저 지적: 레인보우 1200%).
_KA10059_RT_DIV = 100.0
_hist_cache: dict[str, tuple[float, list[float]]] = {}
_flow_cache: dict[str, tuple[float, "tuple[InvestorFlow, list[InvestorPeriod]]"]] = {}
# ka10059 응답에 같이 오는 시세(현재가/등락률/거래량) — 대장주를 랭킹 후보로 올릴 때
# 별도 시세 조회 없이 재사용한다. {코드: (ts, {price, ret, volume})}
_quote_cache: dict[str, tuple[float, dict[str, float]]] = {}


def _first_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        for v in data.values():
            if isinstance(v, dict):
                got = _first_list(v)
                if got:
                    return got
    return []


def _f(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return default


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return default


def _clean_code(raw: Any) -> str:
    """키움 종목코드 정규화 — 'A000660'/'008290_AL' → '000660'/'008290'."""
    s = str(raw)
    if s[:1] in ("A", "Q"):
        s = s[1:]
    return s.split("_")[0]


# ── 캔들 차트 (일/주/월봉) — ChartPanel 요청 시 on-demand ──
# period → (TR코드, 응답 리스트 키). 세 TR 모두 파라미터/필드(OHLC) 구조 동일.
_PERIOD_TR = {
    "D": ("ka10081", "stk_dt_pole_chart_qry"),  # 일봉
    "W": ("ka10082", "stk_stk_pole_chart_qry"),  # 주봉
    "M": ("ka10083", "stk_mth_pole_chart_qry"),  # 월봉
}
_CANDLE_TTL = 300.0  # 캔들 5분 캐시 (일/주/월봉은 자주 안 변함)
_candle_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}


async def fetch_candles(code: str, period: str = "D", limit: int = 140) -> list[dict[str, Any]]:
    """종목 캔들(OHLC) 최근 limit개를 시간순(오름차순)으로. 키 미설정/실패 시 []."""
    period = period.upper()
    if period not in _PERIOD_TR:
        period = "D"
    code = _clean_code(code)
    key = (code, period)
    now = time.time()
    cached = _candle_cache.get(key)
    if cached and now - cached[0] < _CANDLE_TTL:
        return cached[1]
    client = KiwoomClient()
    if not client.configured:
        return []
    tr, lkey = _PERIOD_TR[period]
    base = datetime.now().strftime("%Y%m%d")
    try:
        data = await client.call(
            "chart", tr, {"stk_cd": code, "base_dt": base, "upd_stkpc_tp": "1"}
        )
        rows = data.get(lkey) or _first_list(data)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        c = abs(_num(r.get("cur_prc")))
        if not c:
            continue
        out.append(
            {
                "dt": str(r.get("dt", "")),
                "o": abs(_num(r.get("open_pric"))) or c,
                "h": abs(_num(r.get("high_pric"))) or c,
                "l": abs(_num(r.get("low_pric"))) or c,
                "c": c,
                "v": int(abs(_num(r.get("trde_qty")))),
            }
        )
    out.reverse()  # 최신순 → 시간순
    out = out[-limit:]
    _candle_cache[key] = (now, out)
    return out


async def _fetch_one_flow(
    client: KiwoomClient, code: str
) -> tuple[InvestorFlow, list[InvestorPeriod]] | None:
    """단일 종목 ka10059 → (당일, 20/60일). 캐시 히트면 재조회 안 함. _flow_cache에 기록."""
    code = _clean_code(code)
    now = time.time()
    cached = _flow_cache.get(code)
    if cached and now - cached[0] < _FLOW_TTL:
        return cached[1]
    dt = datetime.now().strftime("%Y%m%d")
    try:
        data = await client.call(
            "stkinfo",
            "ka10059",
            {"dt": dt, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"},
        )
        rows = data.get("stk_invsr_orgn") or _first_list(data)
    except Exception:
        return None
    if not rows:
        return None
    built = KiwoomAdapter._build_flow(rows)
    now2 = time.time()
    _flow_cache[code] = (now2, built)
    # 같은 응답의 시세도 챙겨둔다(대장주를 랭킹 후보로 올릴 때 사용).
    r0 = rows[0]
    _quote_cache[code] = (
        now2,
        {
            "price": abs(_num(r0.get("cur_prc"))),
            # flu_rt는 1/100 단위(1273 = 12.73%) — 나누지 않으면 100배로 찍힌다.
            "ret": _num(r0.get("flu_rt")) / _KA10059_RT_DIV,
            "volume": abs(_num(r0.get("acc_trde_qty"))),
        },
    )
    return built


async def fetch_flow(code: str) -> tuple[InvestorFlow, list[InvestorPeriod]] | None:
    """단일 KR 종목 수급 — 호버 즉석조회(폴백)용. 평소엔 워머가 미리 채워 캐시 히트."""
    client = KiwoomClient()
    if not client.configured:
        return None
    return await _fetch_one_flow(client, code)


# ── 백그라운드 수급 워머 ──────────────────────────────────────────────────
# 유저 요청: 호버할 때 받지 말고, 보유·랭킹이 정해지면 '미리미리' 받아놔라.
# 키움 레이트리밋(ka10059 ~40종목=32초, 세마포어 4가 최적)이라 한 번에 다 못 받으므로,
# 스냅샷과 별개로 도는 백그라운드 루프가 대상 종목을 계속 캐시에 채운다(만료 전 갱신).
# 스냅샷/호버는 이 캐시를 읽기만 → 화면엔 점진적으로(수 초~수십 초) 다 채워진다.
_warm_codes: set[str] = set()
_warm_task: "asyncio.Task | None" = None
# ka10059 전역 동시성 — 스냅샷 조회와 워머가 '같이' 쓴다. 각자 4씩 쓰면 총 8이 되어
# 스로틀링이 심해지고(실측: 8은 4보다 느림) 스냅샷이 워머 뒤에 밀려 40초까지 걸렸다.
_flow_sem: asyncio.Semaphore = asyncio.Semaphore(4)
# 스냅샷이 보유 수급을 블로킹 조회하는 동안엔 워머가 양보한다(첫 로딩을 최우선).
_snapshot_busy: bool = False


async def _warm_loop() -> None:
    while True:
        try:
            client = KiwoomClient()
            if _snapshot_busy:
                await asyncio.sleep(1)
                continue
            if client.configured and _warm_codes:
                now = time.time()
                todo = [
                    c
                    for c in list(_warm_codes)
                    if not (
                        (hit := _flow_cache.get(c)) and now - hit[0] < _FLOW_TTL
                    )
                ]
                if todo:

                    async def one(code: str) -> None:
                        if _snapshot_busy:  # 로딩 시작하면 즉시 양보
                            return
                        async with _flow_sem:
                            await _fetch_one_flow(client, code)

                    await asyncio.gather(*(one(c) for c in todo[:80]), return_exceptions=True)
        except Exception:
            pass
        await asyncio.sleep(3)


def start_warm(codes: "set[str] | list[str]") -> None:
    """워밍 대상(보유+랭킹+테마)을 갱신하고, 워머 루프가 없으면 띄운다."""
    global _warm_codes, _warm_task
    _warm_codes = {_clean_code(c) for c in codes}
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _warm_task is None or _warm_task.done():
        _warm_task = loop.create_task(_warm_loop())


def clear_caches() -> None:
    """수동 새로고침 시 종목 수급/일봉/캔들 캐시를 모두 비워 즉시 재조회하게 한다.
    (평소엔 수급 3분·일봉 10분 캐시라 새로고침 눌러도 캐시값이 나올 수 있어서.)"""
    _flow_cache.clear()
    _hist_cache.clear()
    _candle_cache.clear()


# ── 테마 섹터: 대표 종목들의 종목별 수급(ka10059)을 합산해 '반도체' 같은 테마 단위
#    수급을 만든다. 키움은 테마별 투자자 수급을 안 주고 업종(전기/전자 뭉뚱그림)만
#    주므로, 유저가 실제로 생각하는 섹터(반도체 독립)를 보려면 대표 종목 합산이 유일한
#    방법이다. '어떤 종목=반도체'는 대표 대형주 기준(근사치) — 필요하면 여기만 고친다. ──
#    ※ 대표 종목은 각 테마의 '대장주' 2~3개만 — 키움 레이트리밋(초당 호출 제한) 때문에
#      종목별 수급(ka10059)을 너무 많이 부르면 throttle이 걸려 첫 로딩이 20초+가 된다.
#      대장주만으로도 테마 수급 방향·규모는 충분히 대표된다.
_THEME_SECTORS: list[tuple[str, list[str]]] = [
    ("반도체", ["005930", "000660", "042700"]),  # 삼성전자·SK하이닉스·한미반도체
    ("이차전지", ["373220", "006400", "247540"]),  # LG엔솔·삼성SDI·에코프로비엠
    ("자동차", ["005380", "000270"]),  # 현대차·기아
    ("바이오/제약", ["207940", "068270"]),  # 삼성바이오·셀트리온
    ("방산", ["012450", "047810"]),  # 한화에어로·한국항공우주
    ("조선", ["009540", "010140", "042660"]),  # HD한국조선·삼성중공업·한화오션
    ("원전/에너지", ["034020", "052690", "010120"]),  # 두산에너빌리티·한전기술·LS ELECTRIC
    ("인터넷/게임", ["035420", "035720"]),  # NAVER·카카오
    ("금융", ["105560", "055550", "086790"]),  # KB·신한·하나
    ("로봇", ["277810", "454910", "058610"]),  # 레인보우·두산로보틱스·에스피지
    ("엔터", ["352820", "035900"]),  # 하이브·JYP
    # ── 아래는 순매수/순매도 방향에 더 다양한 섹터가 잡히도록 확장(유저 요청). 시장
    #    큰손이 자주 움직이는 대형 테마 위주. 한전·HMM은 기존 랭킹엔 잡히나 테마엔 없어
    #    빠졌던 것들 → 독립 테마로 추가.
    ("화학", ["051910", "011170"]),  # LG화학·롯데케미칼
    ("철강", ["005490", "004020"]),  # POSCO홀딩스·현대제철
    ("통신", ["017670", "030200"]),  # SK텔레콤·KT
    ("건설", ["000720", "006360"]),  # 현대건설·GS건설
    ("전력/유틸", ["015760", "036460"]),  # 한국전력·한국가스공사
    ("해운", ["011200", "028670"]),  # HMM·팬오션
    ("화장품", ["090430", "051900"]),  # 아모레퍼시픽·LG생활건강
    ("유통", ["139480", "023530"]),  # 이마트·롯데쇼핑
]

# 테마 대장주 종목명 — ka10059 응답엔 종목명이 없어서, 이들을 '외국인 순매수' 랭킹
# 후보로 합류시킬 때 표시용으로 쓴다. (키움 ka10034는 '수량'순이라 SK하이닉스처럼
# 주가가 비싼 종목은 금액이 커도 순위에서 통째로 빠진다 → 대형주를 직접 후보에 넣는다.)
_MAJOR_NAMES: dict[str, str] = {
    "005930": "삼성전자", "000660": "SK하이닉스", "042700": "한미반도체",
    "373220": "LG에너지솔루션", "006400": "삼성SDI", "247540": "에코프로비엠",
    "005380": "현대차", "000270": "기아",
    "207940": "삼성바이오로직스", "068270": "셀트리온",
    "012450": "한화에어로스페이스", "047810": "한국항공우주",
    "009540": "HD한국조선해양", "010140": "삼성중공업", "042660": "한화오션",
    "034020": "두산에너빌리티", "052690": "한전기술", "010120": "LS ELECTRIC",
    "035420": "NAVER", "035720": "카카오",
    "105560": "KB금융", "055550": "신한지주", "086790": "하나금융지주",
    "277810": "레인보우로보틱스", "454910": "두산로보틱스", "058610": "에스피지",
    "352820": "하이브", "035900": "JYP Ent.",
    "051910": "LG화학", "011170": "롯데케미칼",
    "005490": "POSCO홀딩스", "004020": "현대제철",
    "017670": "SK텔레콤", "030200": "KT",
    "000720": "현대건설", "006360": "GS건설",
    "015760": "한국전력", "036460": "한국가스공사",
    "011200": "HMM", "028670": "팬오션",
    "090430": "아모레퍼시픽", "051900": "LG생활건강",
    "139480": "이마트", "023530": "롯데쇼핑",
}

# 지금까지 만든 '가장 완전한' 테마 섹터 세트를 기억한다. 콜드/불안정으로 이번 빌드가
# 몇 개만 나오면(레이트리밋 예산 컷) 이 완전 세트로 대체해 SECTOR FLOW가 '2개만
# 뜨는' 문제를 막는다(약간 stale해도 부분보다 낫다). 완전 세트를 새로 받으면 갱신.
_sector_state: dict[str, list[SectorFlow]] = {"last": []}


class KiwoomAdapter(BaseAdapter):
    name = "kiwoom"

    async def fetch(self) -> AdapterResult:
        client = KiwoomClient()
        if not client.configured:
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="키움 API 키 미설정 — openapi.kiwoom.com에서 앱키/시크릿 발급 후 등록",
                ),
            )
        try:
            kr_pos, us_pos = await asyncio.gather(
                self._holdings(client), self._us_holdings(client)
            )
            positions = kr_pos + us_pos
        except (KiwoomError, Exception) as exc:
            # 잔고(내 자산가치)를 못 받으면 이건 진짜 실패 — 전체를 에러로.
            return AdapterResult(
                error=SourceError(source=self.name, message=f"키움 잔고 조회 실패: {exc}")
            )

        # 랭킹은 부가정보 — 실패해도 잔고·나머지는 살린다.
        ranking_r = await asyncio.gather(self._ranking(client), return_exceptions=True)
        ranking_res = ranking_r[0]
        ranking = ranking_res if isinstance(ranking_res, list) else []
        rank_err = str(ranking_res) if isinstance(ranking_res, Exception) else None

        # ── 종목별 수급(ka10059) — 유저 요청: 호버 때 말고 '미리미리' 받아놔라 ──
        # 레이트리밋(ka10059 ~40종목=32초, 실측상 세마포어 4가 스로틀링 최소)이라 한 번에
        # 다 못 받는다. 그래서 둘로 나눈다:
        #  · 보유(소수 ~10): 첫 로딩 중 블로킹으로 다 받아 화면에 바로 뜬다(이후 캐시 히트=즉시).
        #  · 랭킹·테마(수십 개): 백그라운드 워머(start_warm)가 계속 캐시에 채운다 → 호버는
        #    그 '미리 받아둔' 캐시를 읽기만(라이브 대기 아님). 스냅샷도 캐시를 읽어 점진 반영.
        kr = [p for p in positions if p.region == "KR" and p.assetType == "stock"]
        theme_codes = {c for _, codes in _THEME_SECTORS for c in codes}
        held_codes = [p.symbol for p in kr]
        # 블로킹 조회 = 보유 먼저 + 테마(부분이라도 SECTOR FLOW 즉시 반영). 보유는 예산 안에
        # 완주하고 테마 나머지는 워머가 채운다. 캐시 히트면 즉시 반환하므로 평소엔 안 느리다.
        blocking = held_codes + [c for c in theme_codes if c not in set(held_codes)]
        global _snapshot_busy
        _snapshot_busy = True  # 이 구간엔 워머가 양보 → 첫 로딩이 레이트리밋을 독점
        try:
            work = asyncio.gather(
                self._fetch_flows(client, blocking),
                self._attach_history(client, positions),
                return_exceptions=True,
            )
            await asyncio.wait_for(work, timeout=14.0)  # 보유 ~10종목 완주(≈8s)+여유
        except (asyncio.TimeoutError, Exception):
            pass
        finally:
            _snapshot_busy = False

        # 워머 대상 = 보유+랭킹+테마 전체. 계속 미리 받아둔다(호버/스냅샷은 이 캐시를 읽음).
        start_warm(set(held_codes) | {m.symbol for m in ranking} | theme_codes)

        now2 = time.time()

        def cached_flow(code: str):
            hit = _flow_cache.get(code)
            return hit[1] if hit and now2 - hit[0] < _FLOW_TTL else None

        def cached_quote(code: str):
            hit = _quote_cache.get(code)
            return hit[1] if hit and now2 - hit[0] < _FLOW_TTL else None

        for p in kr:
            cf = cached_flow(p.symbol)
            if cf:
                p.investors, p.investorPeriods = cf
                p.investorsMock = False

        # ── 랭킹 종목의 수급 = ka10059 실데이터(당일 순매수 금액, 억원) ──
        # '외국인' 탭은 이 값으로 정렬된다. ka10034의 수량순/환산값은 실제와 어긋나므로
        # 쓰지 않는다(삼성전자 환산 3,377억 vs 실제 807억).
        for m in ranking:
            cf = cached_flow(m.symbol)
            if cf:
                m.investors, m.investorPeriods = cf
                m.investorsMock = False

        # 대형주(테마 대장주)를 랭킹 후보로 합류 — ka10034가 수량순이라 고가주가 통째로
        # 빠지는 문제 보정(SK하이닉스 +1,037억인데 순위에 없던 원인). 시세는 ka10059
        # 응답에 같이 온 값을 재사용하므로 추가 조회 없음.
        have = {m.symbol for m in ranking}
        for code in theme_codes:
            if code in have:
                continue
            cf, q = cached_flow(code), cached_quote(code)
            if not cf or not q:
                continue
            ranking.append(
                MarketStock(
                    symbol=code,
                    name=_MAJOR_NAMES.get(code, code),
                    price=q["price"],
                    ret=q["ret"],
                    volume=int(q["volume"]),
                    investors=cf[0],
                    investorPeriods=cf[1],
                    investorsMock=False,
                    # 외국인 탭 보정 전용 — 상승/하락/거래량 순위엔 끼지 않는다.
                    flowOnly=True,
                )
            )

        # 테마 섹터 = 대표종목 당일 수급 합산 (캐시에 있는 것만 — 부분→완전 점진 채움)
        sectors: list[SectorFlow] = []
        for name, tcodes in _THEME_SECTORS:
            members = [cf[0] for c in tcodes if (cf := cached_flow(c))]
            if not members:
                continue
            sectors.append(
                SectorFlow(
                    region="KR",
                    id=name,
                    name=name,
                    foreign=round(sum(m.foreign for m in members)),
                    inst=round(sum(m.inst for m in members)),
                    individual=round(sum(m.individual for m in members)),
                )
            )
        # 이번 빌드가 더 완전하면(같거나 많으면) 갱신, 아니면 마지막 완전 세트로 대체 →
        # 콜드/불안정에도 SECTOR FLOW가 '몇 개만' 뜨는 일이 없다.
        if len(sectors) >= len(_sector_state["last"]):
            _sector_state["last"] = sectors
        else:
            sectors = _sector_state["last"]

        fail_parts = []
        if rank_err:
            fail_parts.append(f"랭킹={rank_err}")
        if not sectors:
            fail_parts.append("테마섹터=종목 수급 조회 실패")
        warning = (
            SourceError(
                source=self.name,
                message="키움 부가정보 실패(" + ", ".join(fail_parts) + ") — 모의로 대체됨",
            )
            if fail_parts
            else None
        )

        return AdapterResult(
            positions=positions,
            market_ranking=ranking,
            sector_flows=sectors,
            warning=warning,
        )

    # ── KR 섹터(업종별 투자자순매수 ka10051) — 수급 흐름 레인 실데이터 ──
    async def _kr_sectors(self, client: KiwoomClient) -> list[SectorFlow]:
        base = datetime.now().strftime("%Y%m%d")

        # KOSPI(mrkt_tp=0)만 사용 — 깔끔한 업종명(전기전자·화학·금융업…). KOSDAQ은
        # '업종' 대신 규모/등급 버킷(KOSDAQ 100·MID 300·우량기업…)이 섞여 나와 제외.
        # 실패는 삼키지 않고 그대로 올린다 — fetch()가 return_exceptions=True로 받아
        # "왜 모의로 폴백했는지"를 warning으로 화면에 보여준다(예전엔 조용히 []였음).
        data = await client.call(
            "sect",
            "ka10051",
            {"mrkt_tp": "0", "amt_qty_tp": "1", "base_dt": base, "stex_tp": "3"},
        )
        rows = data.get("inds_netprps") or _first_list(data)
        out: list[SectorFlow] = []
        seen: set[str] = set()
        for r in rows:
            name = str(_f(r, "inds_nm", default="")).strip()
            code = _clean_code(_f(r, "inds_cd"))
            # 종합/대형·중형·소형주 같은 크기 버킷은 '업종'이 아니므로 제외
            if not name or code in seen or any(
                k in name for k in ("종합", "대형주", "중형주", "소형주")
            ):
                continue
            seen.add(code)
            out.append(
                SectorFlow(
                    region="KR",
                    id=code,
                    name=name,
                    foreign=round(_num(_f(r, "frgnr_netprps")) / _SECT_TO_EOK),
                    inst=round(_num(_f(r, "orgn_netprps")) / _SECT_TO_EOK),
                    individual=round(_num(_f(r, "ind_netprps")) / _SECT_TO_EOK),
                    ret=round(_num(_f(r, "flu_rt")) / 100, 2),  # -637 → -6.37%
                )
            )
        # 외국인+기관 순매수 절대값이 큰 상위 12개 업종만 (레인·궤도 과밀 방지)
        out.sort(key=lambda s: abs((s.foreign or 0) + (s.inst or 0)), reverse=True)
        return out[:12]

    # ── 보유종목 (실계좌 잔고 kt00005) ──
    async def _holdings(self, client: KiwoomClient) -> list[Position]:
        data = await client.call("acnt", "kt00005", {"qry_tp": "1", "dmst_stex_tp": "KRX"})
        rows = _first_list(data)
        now = int(time.time() * 1000)
        out: list[Position] = []
        for i, r in enumerate(rows):
            code_raw = _f(r, "stk_cd", "종목코드", "item_cd", "pdno")
            code = _clean_code(code_raw)
            qty = _num(_f(r, "cur_qty", "rmnd_qty", "보유수량", "hold_qty", "qty", "hldg_qty"))
            if not code_raw or qty == 0:
                continue
            avg = _num(_f(r, "buy_uv", "pur_pric", "매입단가", "avg_prc", "pchs_avg_pric"))
            price = _num(_f(r, "cur_prc", "현재가", "prpr", "now_pric"), avg)
            name = _f(r, "stk_nm", "종목명", "item_nm", "prdt_name", default=str(code))
            ret = round((price - avg) / avg * 100, 2) if avg else 0.0
            out.append(
                Position(
                    id=f"kiwoom:{i}:{code}",
                    exchange="kiwoom",
                    assetType="stock",
                    region="KR",
                    symbol=code,
                    name=str(name),
                    qty=qty,
                    avg=avg,
                    price=price,
                    currency="KRW",
                    value=qty * price,
                    cost=qty * avg,
                    ret=ret,
                    lastUpdated=now,
                )
            )
        if rows and not out:
            raise KiwoomError(f"잔고 필드 매핑 실패 — 실제 키: {list(rows[0].keys())}")
        return out

    # ── 미국주식 잔고 (ust21070, 2026-07 신규 /api/us/acnt) ──
    async def _us_holdings(self, client: KiwoomClient) -> list[Position]:
        try:
            data = await client.call("us_acnt", "ust21070", {})
        except Exception:
            return []  # 해외 미신청/미보유는 조용히 스킵 (국내는 계속)
        rows = data.get("result_list") or _first_list(data)
        now = int(time.time() * 1000)
        out: list[Position] = []
        for i, r in enumerate(rows):
            code = str(_f(r, "stk_cd", default="")).strip()
            if not code:
                continue
            # 평가는 결제완료 보유수량(poss_qty) 기준 — evlt_amt와 일치. 없으면 qty.
            qty = _num(_f(r, "poss_qty", "qty"))
            if qty == 0:
                continue
            avg = _num(_f(r, "frgn_stk_book_uv"))  # 평단(USD)
            price = _num(_f(r, "now_pric"), avg)  # 현재가(USD)
            name = _f(r, "frgn_stk_nm", default=code)
            ret = _num(_f(r, "pl_rt"))
            # 키움이 원화 환산까지 제공 → 그대로 사용(자체 환율 불필요)
            value_krw = _num(_f(r, "evlt_amt_krw"))
            cost_krw = _num(_f(r, "frgn_stk_book_amt_krw"))
            out.append(
                Position(
                    id=f"kiwoom-us:{i}:{code}",
                    exchange="kiwoom",
                    assetType="stock",
                    region="US",
                    symbol=code,
                    name=str(name),
                    qty=qty,
                    avg=avg,
                    price=price,
                    currency="USD",
                    value=value_krw or 0.0,
                    cost=cost_krw or 0.0,
                    ret=round(ret, 2),
                    lastUpdated=now,
                )
            )
        # 스파크라인·라인차트용 history를 Yahoo 일봉으로 채운다(미국 티커=Yahoo 심볼 그대로).
        if out:
            try:
                from ..services.stock_quotes import fetch_stock_quotes

                quotes = await fetch_stock_quotes([p.symbol for p in out])
                for p in out:
                    q = quotes.get(p.symbol)
                    if q and q.history:
                        p.history = q.history
            except Exception:
                pass  # history 없어도 보유/평가는 정상 표시
        return out

    # ── 종목별 수급 (ka10059) — 코드 집합 → {코드: (당일 InvestorFlow, 20/60일 누적)} ──
    #    _flow_cache로 중복/재조회를 막는다. 보유·랭킹 호버 수급과 테마 섹터 합산이 공용.
    async def _fetch_flows(
        self, client: KiwoomClient, codes: "list[str]"
    ) -> dict[str, tuple[InvestorFlow, list[InvestorPeriod]]]:
        # 입력 순서를 보존한다 — 앞쪽(보유)이 세마포어를 먼저 잡아 예산 안에 먼저 완주.
        seen: set[str] = set()
        ordered = [c for c in codes if not (c in seen or seen.add(c))]
        if not ordered:
            return {}

        async def one(code: str) -> tuple[InvestorFlow, list[InvestorPeriod]] | None:
            async with _flow_sem:  # 워머와 공유하는 전역 동시성(총 4)
                return await _fetch_one_flow(client, code)

        results = await asyncio.gather(*(one(c) for c in ordered))
        return {code: r for code, r in zip(ordered, results) if r}

    @staticmethod
    def _build_flow(rows: list[dict[str, Any]]) -> tuple[InvestorFlow, list[InvestorPeriod]]:
        """ka10059 일별 순매수 행들 → 당일(InvestorFlow) + 20/60일 누적(InvestorPeriod)."""

        def agg(rs: list[dict[str, Any]]) -> tuple[int, int, int]:
            f = sum(_num(r.get("frgnr_invsr")) for r in rs) / _AMT_TO_EOK
            i = sum(_num(r.get("orgn")) for r in rs) / _AMT_TO_EOK
            ind = sum(_num(r.get("ind_invsr")) for r in rs) / _AMT_TO_EOK
            return round(f), round(i), round(ind)

        f0, i0, ind0 = agg(rows[:1])
        today = InvestorFlow(foreign=f0, inst=i0, individual=ind0, program=0)
        periods: list[InvestorPeriod] = []
        for label, n in (("20일", 20), ("60일", 60)):
            f, i, ind = agg(rows[:n])
            periods.append(
                InvestorPeriod(label=label, foreign=f, inst=i, individual=ind, program=0)
            )
        return today, periods

    # ── 일봉 종가 (ka10081) — 보유 KR 종목의 history(스파크라인·차트) 채우기 ──
    async def _attach_history(self, client: KiwoomClient, positions: list[Position]) -> None:
        kr = [p for p in positions if p.region == "KR" and p.assetType == "stock"]
        if not kr:
            return
        base = datetime.now().strftime("%Y%m%d")
        sem = asyncio.Semaphore(3)
        now = time.time()

        async def one(code: str) -> list[float] | None:
            cached = _hist_cache.get(code)
            if cached and now - cached[0] < _HIST_TTL:
                return cached[1]
            async with sem:
                try:
                    data = await client.call(
                        "chart",
                        "ka10081",
                        {"stk_cd": code, "base_dt": base, "upd_stkpc_tp": "1"},
                    )
                    rows = data.get("stk_dt_pole_chart_qry") or _first_list(data)
                except Exception:
                    return None
            if not rows:
                return None
            # 응답은 최신일자 먼저(내림차순) → 시간순(오름차순)으로 뒤집고 종가만, 최근 N개
            closes = [abs(_num(r.get("cur_prc"))) for r in rows if r.get("cur_prc")]
            closes.reverse()
            hist = closes[-_HIST_LEN:]
            _hist_cache[code] = (now, hist)
            return hist

        results = await asyncio.gather(*(one(p.symbol) for p in kr))
        for p, hist in zip(kr, results):
            if hist:
                p.history = hist

    # ── 오늘의 시장 순위 (상승/하락/거래량) ──
    async def _ranking(self, client: KiwoomClient) -> list[MarketStock]:
        last_err: str | None = None

        async def one(api_id: str, body: dict[str, Any]) -> list[dict[str, Any]]:
            nonlocal last_err
            try:
                return _first_list(await client.call("rkinfo", api_id, body))
            except Exception as exc:
                last_err = str(exc)  # 개별 호출 실패는 다른 소스로 흡수 가능하니 계속 진행
                return []

        # ka10027 등락률상위: sort_tp 1=상승률, 3=하락률 (실응답으로 확인).
        def updown(sort_tp: str) -> dict[str, Any]:
            return {
                "mrkt_tp": "000",
                "sort_tp": sort_tp,
                "trde_qty_cnd": "0000",
                "stk_cnd": "0",
                "crd_cnd": "0",
                "updown_incls": "1",
                "pric_cnd": "0",
                "trde_prica_cnd": "0",
                "stex_tp": "3",
            }

        up, down, vol, frgn = await asyncio.gather(
            one("ka10027", updown("1")),  # 상승률상위
            one("ka10027", updown("3")),  # 하락률상위 (하락 탭이 실제 하락 종목을 보게)
            one(
                "ka10030",
                {
                    "mrkt_tp": "000",
                    "sort_tp": "1",
                    "mang_stk_incls": "0",
                    "crd_tp": "0",
                    "trde_qty_tp": "0",
                    "pric_tp": "0",
                    "trde_prica_tp": "0",
                    "mrkt_open_tp": "0",
                    "stex_tp": "3",
                },
            ),
            # ka10034 외인기간별매매상위: 외국인 순매수 상위. trde_tp 2=순매수,
            # dt 1=최근 완결 거래일(dt 0=장중 당일은 값이 희박). 리스트 for_dt_trde_upper.
            one(
                "ka10034",
                {"mrkt_tp": "000", "trde_tp": "2", "dt": "1", "amt_qty_tp": "1", "stex_tp": "3"},
            ),
        )
        merged: dict[str, MarketStock] = {}

        def take(rows: list[dict[str, Any]], n: int = 12) -> list[MarketStock]:
            """한 소스에서 '거래대금 하한'을 통과한 상위 n개만. 응답 전량(≈100)을 훑으므로
            껍데기를 걸러도 탭마다 10개가 채워진다."""
            out: list[MarketStock] = []
            for r in rows:
                code = _clean_code(_f(r, "stk_cd", "종목코드", "item_cd"))
                if not code:
                    continue
                price = abs(_num(_f(r, "cur_prc", "현재가", "prpr")))
                # 거래량 필드명이 TR마다 다르다: ka10027=now_trde_qty, ka10030=trde_qty
                qty = abs(_num(_f(r, "now_trde_qty", "trde_qty", "거래량", "acml_vol")))
                if qty >= _QTY_OVERFLOW:
                    qty = 0.0  # 32비트 오버플로우 값 → 신뢰 불가
                if price * qty < _MIN_TRDE_PRICA:
                    continue
                out.append(
                    MarketStock(
                        symbol=code,
                        name=str(_f(r, "stk_nm", "종목명", "item_nm", default=code)),
                        price=price,
                        ret=_num(_f(r, "flu_rt", "등락률", "prdy_ctrt", "chg_rt", "fluc_rt")),
                        volume=int(qty),
                        investors=InvestorFlow(),
                    )
                )
                if len(out) >= n:
                    break
            return out

        for m in [*take(up), *take(down), *take(vol)]:
            if m.symbol not in merged:
                merged[m.symbol] = m
        # ka10034는 '외국인 순매수 후보 발굴'에만 쓴다 — 정렬이 금액이 아니라 '수량(주)'
        # 이라 순위 자체를 믿으면 안 된다(1위가 저가 ETF 962만주, SK하이닉스는 +1,037억을
        # 사도 5.7만주뿐이라 100위 밖으로 탈락). 수량×현재가 환산도 실제와 4배씩 어긋났다
        # (ka10034 dt=1과 ka10059 당일이 서로 다른 날짜 기준). 따라서 여기선 종목만 담고,
        # 외국인 순매수 '금액'은 fetch()에서 ka10059 실데이터로 채운다.
        for r in frgn[:15]:
            code = _clean_code(_f(r, "stk_cd", "종목코드"))
            if not code or code in merged:
                continue
            qty = abs(_num(_f(r, "trde_qty")))
            merged[code] = MarketStock(
                symbol=code,
                name=str(_f(r, "stk_nm", "종목명", default=code)),
                price=abs(_num(_f(r, "cur_prc"))),
                ret=0.0,
                volume=int(0 if qty >= _QTY_OVERFLOW else qty),
                investors=InvestorFlow(),
                # 외국인 탭 후보일 뿐 — 상승/하락/거래량은 키움 공식 랭킹만 쓴다.
                flowOnly=True,
            )
        if not merged and last_err:
            # 상승/하락/거래량 세 소스 다 실패 — 진짜 장애. 원인을 올려서 fetch()가
            # warning으로 화면에 보이게 한다(비었다고 조용히 넘기면 "오늘 랭킹 없음"과
            # 구분이 안 됨).
            raise KiwoomError(f"랭킹 조회 실패: {last_err}")
        # 4개 소스(상승/하락/거래량/외국인) 합집합 — 프론트가 탭별 재정렬 후 top10 슬라이스.
        return list(merged.values())[:60]
