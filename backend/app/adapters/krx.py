"""
KRX 정보데이터시스템 어댑터 — 아직 미구현.

한국 섹터별 투자자(외국인/기관/개인) 순매수 동향. 스펙 리스크 2번:
"KRX 투자자별 매매동향이 실시간 아님 — 장 마감 후 데이터. UI에 정직하게 표시"
API 키 문제가 아니라 KRX 정보데이터시스템 접근 방식(공식 API 신청 또는
정적 페이지 파싱) 자체를 아직 정하지 않아서 스텁 상태.
"""
from ..schemas import SourceError
from .base import AdapterResult, BaseAdapter


class KRXAdapter(BaseAdapter):
    name = "krx"

    async def fetch(self) -> AdapterResult:
        # TODO: KRX 정보데이터시스템 접근 방식 확정 후 구현.
        # 미구현도 "설정 대기"로 취급 — 섹터 흐름이 없다고 전체 스냅샷을
        # 추정치로 표시할 필요는 없다 (포지션/시세는 멀쩡함).
        return AdapterResult(
            unconfigured=True,
            error=SourceError(source=self.name, message="KRX 어댑터 미구현"),
        )
