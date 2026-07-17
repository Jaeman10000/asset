"""
업비트 어댑터 — 아직 미구현 (API 키 없음).

업비트 시세(ticker)는 공개 API(https://api.upbit.com/v1/ticker)라 키 없이도
현재가는 가져올 수 있지만, "내가 얼마나 보유했는지"(수량·평단가)는
계좌 조회 API라 JWT 서명된 API 키가 반드시 필요하다. 그래서 포지션
데이터 자체는 키 없이는 만들 수 없다.
"""
from ..keychain import has_api_key
from ..schemas import SourceError
from .base import AdapterResult, BaseAdapter


class UpbitAdapter(BaseAdapter):
    name = "upbit"

    async def fetch(self) -> AdapterResult:
        if not has_api_key("upbit", "access_key"):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="업비트 API 키 미설정 — scripts/set_api_key.py upbit access_key 로 등록",
                ),
            )
        # TODO: 키가 등록되면 JWT 서명 + /v1/accounts 호출로 실제 보유 종목 구현
        return AdapterResult(
            error=SourceError(source=self.name, message="업비트 어댑터 미구현 (키는 등록됨)")
        )
