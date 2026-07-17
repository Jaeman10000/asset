"""
키움 REST/Open API+ 어댑터 — 아직 미구현 (API 키 없음).

키움은 두 갈래다:
  1) Open API+ (레거시): Windows 32비트 COM(OCX) 기반, 키움 로그인 프로그램이
     실제로 떠 있어야 동작. Python에서 쓰려면 별도 32비트 프로세스 + pywin32로
     브리지해야 해서 이 FastAPI 프로세스에서 직접 부르긴 어렵다.
  2) 키움 REST API (신규): 계좌 실물 없이 앱키/시크릿 발급 → OAuth 토큰 → REST 호출.
     이쪽이 이 아키텍처(FastAPI 단일 프로세스)와 훨씬 잘 맞는다.

API 키가 keychain에 등록되면 이 스텁을 실제 구현으로 교체하면 된다.
"""
from ..keychain import has_api_key
from ..schemas import SourceError
from .base import AdapterResult, BaseAdapter


class KiwoomAdapter(BaseAdapter):
    name = "kiwoom"

    async def fetch(self) -> AdapterResult:
        if not has_api_key("kiwoom", "app_key"):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="키움 API 키 미설정 — scripts/set_api_key.py kiwoom app_key 로 등록",
                ),
            )
        # TODO: 키가 등록되면 여기서 실제 REST 호출 구현
        return AdapterResult(
            error=SourceError(source=self.name, message="키움 어댑터 미구현 (키는 등록됨)")
        )
