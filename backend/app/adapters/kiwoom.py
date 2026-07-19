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
_hist_cache: dict[str, tuple[float, list[float]]] = {}
_flow_cache: dict[str, tuple[float, "tuple[InvestorFlow, list[InvestorPeriod]]"]] = {}


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
            ranking, sectors = await asyncio.gather(
                self._ranking(client), self._kr_sectors(client)
            )
            # 수급(ka10059)·일봉(ka10081)을 동시에 부착
            await asyncio.gather(
                self._attach_investors(client, positions, ranking),
                self._attach_history(client, positions),
            )
        except (KiwoomError, Exception) as exc:
            return AdapterResult(
                error=SourceError(source=self.name, message=f"키움 조회 실패: {exc}")
            )
        return AdapterResult(
            positions=positions, market_ranking=ranking, sector_flows=sectors
        )

    # ── KR 섹터(업종별 투자자순매수 ka10051) — 수급 흐름 레인 실데이터 ──
    async def _kr_sectors(self, client: KiwoomClient) -> list[SectorFlow]:
        base = datetime.now().strftime("%Y%m%d")

        # KOSPI(mrkt_tp=0)만 사용 — 깔끔한 업종명(전기전자·화학·금융업…). KOSDAQ은
        # '업종' 대신 규모/등급 버킷(KOSDAQ 100·MID 300·우량기업…)이 섞여 나와 제외.
        try:
            data = await client.call(
                "sect",
                "ka10051",
                {"mrkt_tp": "0", "amt_qty_tp": "1", "base_dt": base, "stex_tp": "3"},
            )
            rows = data.get("inds_netprps") or _first_list(data)
        except Exception:
            rows = []
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

    # ── 종목별 수급 (ka10059) — 보유 KR 종목 + 랭킹 종목에 당일 + 20/60일 누적 부착 ──
    async def _attach_investors(
        self,
        client: KiwoomClient,
        positions: list[Position],
        ranking: list[MarketStock],
    ) -> None:
        kr = [p for p in positions if p.region == "KR" and p.assetType == "stock"]
        # 보유 + 랭킹 종목코드를 합쳐 중복 제거 (한 종목당 ka10059 1회만)
        codes = sorted({p.symbol for p in kr} | {m.symbol for m in ranking})
        if not codes:
            return
        dt = datetime.now().strftime("%Y%m%d")
        sem = asyncio.Semaphore(3)  # 레이트리밋 대비 동시 3
        now = time.time()

        async def one(code: str) -> tuple[InvestorFlow, list[InvestorPeriod]] | None:
            cached = _flow_cache.get(code)
            if cached and now - cached[0] < _FLOW_TTL:
                return cached[1]
            async with sem:
                try:
                    data = await client.call(
                        "stkinfo",
                        "ka10059",
                        {
                            "dt": dt,
                            "stk_cd": code,
                            "amt_qty_tp": "1",  # 1=금액
                            "trde_tp": "0",  # 0=순매수
                            "unit_tp": "1000",
                        },
                    )
                    rows = data.get("stk_invsr_orgn") or _first_list(data)
                except Exception:
                    return None
            if not rows:
                return None
            built = self._build_flow(rows)
            _flow_cache[code] = (now, built)
            return built

        results = await asyncio.gather(*(one(c) for c in codes))
        flows = {code: r for code, r in zip(codes, results) if r}
        for p in kr:
            if p.symbol in flows:
                p.investors, p.investorPeriods = flows[p.symbol]
                p.investorsMock = False
        for m in ranking:
            if m.symbol in flows:
                m.investors, m.investorPeriods = flows[m.symbol]
                m.investorsMock = False

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

    # ── 오늘의 시장 순위 (상승률/거래량) ──
    async def _ranking(self, client: KiwoomClient) -> list[MarketStock]:
        async def one(api_id: str, body: dict[str, Any]) -> list[dict[str, Any]]:
            try:
                return _first_list(await client.call("rkinfo", api_id, body))
            except Exception:
                return []

        up = await one(
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
        )
        vol = await one(
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
        )
        merged: dict[str, MarketStock] = {}
        for r in [*up, *vol]:
            code = _clean_code(_f(r, "stk_cd", "종목코드", "item_cd"))
            if not code or code in merged:
                continue
            merged[code] = MarketStock(
                symbol=code,
                name=str(_f(r, "stk_nm", "종목명", "item_nm", default=code)),
                price=abs(_num(_f(r, "cur_prc", "현재가", "prpr"))),
                ret=_num(_f(r, "flu_rt", "등락률", "prdy_ctrt", "chg_rt", "fluc_rt")),
                volume=int(abs(_num(_f(r, "trde_qty", "거래량", "acml_vol", "now_trde_qty")))),
                investors=InvestorFlow(),
            )
        return list(merged.values())[:14]
