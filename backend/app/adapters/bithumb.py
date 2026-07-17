"""
빗썸 어댑터 — 아직 미구현 (API 키 없음). 업비트와 동일한 이유로
시세는 공개, 보유 종목(계좌 조회)은 API 키 필수.
"""
from ..keychain import has_api_key
from ..schemas import SourceError
from .base import AdapterResult, BaseAdapter


class BithumbAdapter(BaseAdapter):
    name = "bithumb"

    async def fetch(self) -> AdapterResult:
        if not has_api_key("bithumb", "api_key"):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="빗썸 API 키 미설정 — scripts/set_api_key.py bithumb api_key 로 등록",
                ),
            )
        # TODO: 키가 등록되면 실제 계좌 조회 구현
        return AdapterResult(
            error=SourceError(source=self.name, message="빗썸 어댑터 미구현 (키는 등록됨)")
        )
