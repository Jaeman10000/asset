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

from ..schemas import InvestorFlow, InvestorPeriod, MarketStock, Position, SourceError
from ..services.kiwoom_client import KiwoomClient, KiwoomError
from .base import AdapterResult, BaseAdapter

# 투자자 순매수 금액 단위 = 백만원 → 억원 환산(÷100). (acc_trde_prica 교차검증으로 확인)
_AMT_TO_EOK = 100.0


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
            positions = await self._holdings(client)
            ranking = await self._ranking(client)
            await self._attach_investors(client, positions, ranking)
        except (KiwoomError, Exception) as exc:
            return AdapterResult(
                error=SourceError(source=self.name, message=f"키움 조회 실패: {exc}")
            )
        return AdapterResult(positions=positions, market_ranking=ranking)

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

        async def one(code: str) -> list[dict[str, Any]]:
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
                    return data.get("stk_invsr_orgn") or _first_list(data)
                except Exception:
                    return []

        lists = await asyncio.gather(*(one(c) for c in codes))
        flows: dict[str, tuple[InvestorFlow, list[InvestorPeriod]]] = {}
        for code, rows in zip(codes, lists):
            if rows:
                flows[code] = self._build_flow(rows)
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
