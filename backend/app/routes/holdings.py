"""
보유종목 편집 엔드포인트 — UI에서 holdings.json을 직접 손대지 않고
추가/삭제할 수 있게 한다. 로컬 파일에만 쓰므로 서버로 데이터가 안 나간다.
"""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.holdings import load_manual_holdings, save_manual_holdings

router = APIRouter()


class HoldingItem(BaseModel):
    exchange: Literal["manual"] = "manual"
    assetType: Literal["stock", "crypto"]
    region: Literal["KR", "US"] | None = None
    market: Literal["upbit", "bithumb"] | None = None
    yahoo: str | None = None
    symbol: str
    name: str
    qty: float
    avg: float
    sector: str | None = None


class HoldingsPayload(BaseModel):
    positions: list[HoldingItem] = Field(default_factory=list)


@router.get("/holdings", response_model=HoldingsPayload)
async def get_holdings() -> HoldingsPayload:
    raw = load_manual_holdings()
    # 저장된 raw dict를 스키마로 통과시켜 정규화 (알 수 없는 필드/누락은 관대하게)
    items: list[HoldingItem] = []
    for r in raw:
        try:
            items.append(HoldingItem(**r))
        except Exception:
            continue  # 깨진 행은 건너뜀
    return HoldingsPayload(positions=items)


@router.put("/holdings", response_model=HoldingsPayload)
async def put_holdings(payload: HoldingsPayload) -> HoldingsPayload:
    save_manual_holdings([item.model_dump(exclude_none=True) for item in payload.positions])
    return payload
