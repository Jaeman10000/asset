"""키움 REST API 어댑터 — 실계좌 보유종목 + 종목별 수급 + 시장 순위.

앱키/시크릿이 keychain에 있으면 실제 REST를 호출한다(services/kiwoom_client).
없으면 unconfigured로 조용히 넘어가 mock_market이 채운다.

⚠️ 응답 필드명은 실제 응답으로 확정한다. 그래서:
  - 응답에서 '첫 dict 리스트'를 자동 탐색해 출력 배열을 찾고(_first_list),
  - 각 값은 여러 후보 키로 추출하며(_f),
  - 그래도 핵심 필드를 못 찾으면 raw 응답의 키 목록을 에러로 올려(진단),
    실제 필드명을 보고 이 파일의 후보 목록만 고치면 되게 했다.
TR코드: 잔고 kt00005 / 종목별투자자 ka10059 / 상승률 ka10027 / 하락률 ka10028
        / 거래량상위 ka10030 (실제 코드는 응답으로 검증).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from ..schemas import InvestorFlow, MarketStock, Position, SourceError
from ..services.kiwoom_client import KiwoomClient, KiwoomError
from .base import AdapterResult, BaseAdapter


def _first_list(data: Any) -> list[dict[str, Any]]:
    """응답에서 dict들의 리스트(출력 배열)를 자동으로 찾아 반환."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        # 한 단계 더 (output.list 같은 중첩)
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
        except (KiwoomError, Exception) as exc:
            return AdapterResult(
                error=SourceError(source=self.name, message=f"키움 조회 실패: {exc}")
            )
        return AdapterResult(positions=positions, market_ranking=ranking)

    # ── 보유종목 (실계좌 잔고 kt00005) ──
    async def _holdings(self, client: KiwoomClient) -> list[Position]:
        data = await client.call(
            "acnt", "kt00005", {"qry_tp": "1", "dmst_stex_tp": "KRX"}
        )
        rows = _first_list(data)
        now = int(time.time() * 1000)
        out: list[Position] = []
        for i, r in enumerate(rows):
            code_raw = _f(r, "stk_cd", "종목코드", "item_cd", "pdno")
            # 키움은 종목코드에 "A" 접두사("A000660") — 앱 표준(6자리)으로 정규화
            code = str(code_raw)[1:] if str(code_raw).startswith(("A", "Q")) else str(code_raw)
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
                    symbol=str(code),
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
            # 리스트는 받았는데 매핑이 하나도 안 됨 → 실제 키를 알려 확정에 쓴다
            raise KiwoomError(f"잔고 필드 매핑 실패 — 실제 키: {list(rows[0].keys())}")
        return out

    # ── 오늘의 시장 순위 (상승률/거래량) ──
    async def _ranking(self, client: KiwoomClient) -> list[MarketStock]:
        async def one(api_id: str, body: dict[str, Any]) -> list[dict[str, Any]]:
            try:
                return _first_list(await client.call("rkinfo", api_id, body))
            except Exception:
                return []

        # ka10027(등락률상위): sort_tp 필수(1=상승률). 나머지는 전체/조건없음 기본.
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
            code_raw = _f(r, "stk_cd", "종목코드", "item_cd")
            code = str(code_raw)[1:] if str(code_raw).startswith(("A", "Q")) else str(code_raw)
            if not code_raw or code in merged:
                continue
            merged[code] = MarketStock(
                symbol=code,
                name=str(_f(r, "stk_nm", "종목명", "item_nm", default=code)),
                price=abs(_num(_f(r, "cur_prc", "현재가", "prpr"))),
                ret=_num(_f(r, "flu_rt", "등락률", "prdy_ctrt", "chg_rt", "fluc_rt")),
                volume=int(abs(_num(_f(r, "trde_qty", "거래량", "acml_vol", "now_trde_qty")))),
                investors=InvestorFlow(),  # 순위 TR엔 투자자별 수급 없음 (수급은 종목 상세)
            )
        return list(merged.values())[:14]
