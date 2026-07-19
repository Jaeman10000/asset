"""
어댑터 공통 인터페이스.

스펙 원칙: "부분 실패 지원 (한 소스 실패해도 나머지는 반환)".
그래서 fetch()는 예외를 던지지 않고 항상 AdapterResult를 반환한다 —
실패는 result.error에 담기고, 호출부(routes/portfolio.py)가 그걸 모아
PortfolioSnapshot.errors 배열로 합친다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schemas import MarketStock, Position, SectorFlow, SourceError


@dataclass
class AdapterResult:
    positions: list[Position] = field(default_factory=list)
    sector_flows: list[SectorFlow] = field(default_factory=list)
    # 실데이터 시장 랭킹(키움 등). 하나라도 있으면 portfolio가 mock 대신 이걸 쓴다.
    market_ranking: list[MarketStock] = field(default_factory=list)
    error: SourceError | None = None
    # "설정 대기"는 진짜 오류가 아니다 — API 키를 일부러 안 넣은 사용자에게
    # isEstimate 경고를 상시 띄우면 안 되므로, unconfigured=True인 결과는
    # 상태 표시용으로만 errors에 담고 isEstimate 판정에서는 제외한다.
    unconfigured: bool = False
    # 사용자 보유 자산 평가와 무관한 '배경 시장 데이터'(예: 미국 SPDR 섹터 등락률)
    # 전용 어댑터. 이런 소스가 실패해도 내 포트폴리오 가치가 추정치가 되는 건 아니므로
    # isEstimate(전체 흐림)에서 제외한다 (errors에는 담아 상태만 표시).
    background: bool = False


class BaseAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> AdapterResult: ...
