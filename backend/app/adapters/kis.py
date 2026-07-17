"""
KIS(한국투자증권) API 어댑터 — 아직 미구현 (API 키 없음).

스펙: "키움만으로는 미국 주식 안 됨 — KIS 필수". KIS Developers 포털에서
앱키/시크릿 발급 → OAuth 토큰 → REST. 순수 REST라 키움 Open API+보다 훨씬
간단하게 이 프로세스 안에서 직접 구현 가능하다.
"""
from ..keychain import has_api_key
from ..schemas import SourceError
from .base import AdapterResult, BaseAdapter


class KISAdapter(BaseAdapter):
    name = "kis"

    async def fetch(self) -> AdapterResult:
        if not has_api_key("kis", "app_key"):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="KIS API 키 미설정 — scripts/set_api_key.py kis app_key 로 등록",
                ),
            )
        # TODO: 키가 등록되면 여기서 실제 REST 호출 구현
        return AdapterResult(
            error=SourceError(source=self.name, message="KIS 어댑터 미구현 (키는 등록됨)")
        )
