"""
VITALITY_NEXUS_SPEC.md 4장의 데이터 모델을 그대로 옮긴 pydantic 스키마.

프론트엔드는 원본 거래소 API 응답을 절대 몰라야 한다 — 이 스키마가 그 경계다.
필드명은 스펙 문서와 1:1로 맞춰서, 나중에 TypeScript 인터페이스와 대조하기 쉽게 했다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InvestorFlow(BaseModel):
    """종목/섹터의 투자자별 순매수 (단위: 억원). 키움/KRX 연동 전엔 모의 데이터."""

    foreign: float = 0.0  # 외국인
    inst: float = 0.0  # 기관
    individual: float = 0.0  # 개인
    program: float = 0.0  # 프로그램 매매


class InvestorPeriod(BaseModel):
    """기간 누적 순매수 (억원). 키움/KRX의 당일 외 5/20/60일 누적 뷰에 대응.

    당일(InvestorFlow)이 기본이고, 이건 옆에 작게 보여줄 기간 누적치다.
    실 키움 연동 시 이 값이 실제 일자별 누적으로 대체된다.
    """

    label: str  # '20일', '60일'
    foreign: float = 0.0
    inst: float = 0.0
    individual: float = 0.0
    program: float = 0.0


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
    # 종목별 수급 (KR 주식만, 키움 연동 전엔 모의) — 호버 Truth Layer에 표시
    investors: InvestorFlow | None = None
    # 기간 누적 수급 (20일/60일 등) — 호버에서 당일 옆에 작게
    investorPeriods: list[InvestorPeriod] = Field(default_factory=list)
    # 이 종목 수급이 모의인지 (키움 ka10059 실데이터면 False). 호버 '모의' 표기용.
    investorsMock: bool = False
    lastUpdated: int  # epoch ms


class MarketStock(BaseModel):
    """오늘의 시장 랭킹 항목 (보유 여부와 무관한 시장 전체 종목)."""

    symbol: str
    name: str
    price: float
    ret: float  # 등락률 %
    volume: int  # 거래량 (주)
    # 거래대금(억원). 키움이 주는 실제값(ka10030 trde_amt, 백만원)을 우선 쓰고,
    # 그 필드가 없는 TR은 현재가×거래량으로 근사한다(실측 오차 ±5% 이내).
    value: float = 0.0
    investors: InvestorFlow  # 수급 (외국인/기관/개인/프로그램, 억원)
    investorPeriods: list[InvestorPeriod] = Field(default_factory=list)  # 20일/60일 누적
    investorsMock: bool = False  # 이 종목 수급이 모의인지 (키움 실데이터면 False)
    # True = '외국인 순매수' 탭 보정용으로만 넣은 대장주 후보. 상승/하락/거래량 탭은
    # 키움 공식 랭킹(ka10027/ka10030)만 써야 하므로 이 종목들은 그 탭에서 제외한다.
    flowOnly: bool = False


class SectorFlow(BaseModel):
    region: Literal["KR", "US"]
    id: str  # 'semi', 'XLK' 등
    name: str  # '반도체', '기술' (한글)
    # 한국만 — 투자자별 당일 순매수 (억원, 부호 있음: 음수=순매도)
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
    # 오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관 탭용) — 키움 연동 전엔 모의
    marketRanking: list[MarketStock] = Field(default_factory=list)
    fetchedAt: int  # epoch ms
    errors: list[SourceError] = Field(default_factory=list)
    isEstimate: bool = False  # errors가 하나라도 있으면 True — UI에서 흐리게 표시
    # 섹터 flow·종목 수급이 모의(mock_market)인지 (키움 수급/섹터 연동 전엔 True).
    # 프론트가 해당 패널에 "샘플 데이터" 워터마크를 씌운다.
    marketMock: bool = False
    # 시장 랭킹이 모의인지 (키움 랭킹 연동되면 False). 랭킹 카드 워터마크용 — 별도 플래그라
    # 랭킹만 실데이터가 돼도 섹터/수급 모의와 독립적으로 표시된다.
    rankingMock: bool = True
