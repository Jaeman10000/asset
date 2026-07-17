"""
VITALITY_NEXUS_SPEC.md 4장의 데이터 모델을 그대로 옮긴 pydantic 스키마.

프론트엔드는 원본 거래소 API 응답을 절대 몰라야 한다 — 이 스키마가 그 경계다.
필드명은 스펙 문서와 1:1로 맞춰서, 나중에 TypeScript 인터페이스와 대조하기 쉽게 했다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Position(BaseModel):
    id: str  # "kiwoom:005930" | "upbit:KRW-BTC" | "manual:BTC"
    # "manual" = 수동입력(어떤 증권사든 커버하는 폴백). 스펙 4장 원본에는 없지만,
    # 미지원 증권사/API 키 미설정 사용자를 위해 추가했다.
    exchange: Literal["kiwoom", "kis", "upbit", "bithumb", "manual"]
    assetType: Literal["stock", "crypto"]
    region: Literal["KR", "US"] | None = None  # 주식만
    symbol: str
    name: str  # 한글 우선
    qty: float
    avg: float  # 평균 매입가
    price: float  # 현재가
    currency: Literal["KRW", "USD"]
    value: float  # KRW 환산 평가금액 (백엔드에서 계산)
    cost: float  # KRW 환산 매수금액
    ret: float  # 수익률 %
    history: list[float] = Field(default_factory=list)  # 최근 32개 가격
    sector: str | None = None  # KR 주식만
    lastUpdated: int  # epoch ms


class SectorFlow(BaseModel):
    region: Literal["KR", "US"]
    id: str  # 'semi', 'XLK' 등
    name: str  # '반도체', '기술' (한글)
    # 한국만 — 투자자별 순매수 강도 0~1
    foreign: float | None = None
    inst: float | None = None
    individual: float | None = None
    # 미국만
    ret: float | None = None  # 전일 등락률
    volume: float | None = None


class TotalsBucket(BaseModel):
    value: float = 0.0
    cost: float = 0.0
    pnl: float = 0.0
    pnlPct: float = 0.0


class Totals(BaseModel):
    kr: TotalsBucket = Field(default_factory=TotalsBucket)
    us: TotalsBucket = Field(default_factory=TotalsBucket)
    stock: TotalsBucket = Field(default_factory=TotalsBucket)
    crypto: TotalsBucket = Field(default_factory=TotalsBucket)
    total: TotalsBucket = Field(default_factory=TotalsBucket)


class SourceError(BaseModel):
    source: str
    message: str


class PortfolioSnapshot(BaseModel):
    totals: Totals
    positions: list[Position] = Field(default_factory=list)
    sectorFlows: list[SectorFlow] = Field(default_factory=list)
    fetchedAt: int  # epoch ms
    errors: list[SourceError] = Field(default_factory=list)
    isEstimate: bool = False  # errors가 하나라도 있으면 True — UI에서 흐리게 표시
