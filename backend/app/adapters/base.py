"""
어댑터 공통 인터페이스.

스펙 원칙: "부분 실패 지원 (한 소스 실패해도 나머지는 반환)".
그래서 fetch()는 예외를 던지지 않고 항상 AdapterResult를 반환한다 —
실패는 result.error에 담기고, 호출부(routes/portfolio.py)가 그걸 모아
PortfolioSnapshot.errors 배열로 합친다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schemas import Position, SectorFlow, SourceError


@dataclass
class AdapterResult:
    positions: list[Position] = field(default_factory=list)
    sector_flows: list[SectorFlow] = field(default_factory=list)
    error: SourceError | None = None
    # "설정 대기"는 진짜 오류가 아니다 — API 키를 일부러 안 넣은 사용자에게
    # isEstimate 경고를 상시 띄우면 안 되므로, unconfigured=True인 결과는
    # 상태 표시용으로만 errors에 담고 isEstimate 판정에서는 제외한다.
    unconfigured: bool = False


class BaseAdapter(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> AdapterResult: ...
