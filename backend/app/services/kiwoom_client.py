"""키움 REST API 클라이언트 (신규 openapi.kiwoom.com — OCX 아님).

앱키/시크릿 → 접근토큰 → REST 호출. 계좌 실물·32bit OCX 없이 이 FastAPI
프로세스에서 직접 부른다. 토큰은 만료 전까지 캐시한다.

⚠️ 저수준 프로토콜(엔드포인트 경로·헤더 이름·응답 필드)은 키움 공식 문서 기준이며,
실제 키로 첫 응답을 받아 확정한다. 바뀌기 쉬운 값은 이 파일 상단 상수/주석에 모아
두었으니, 실제 응답과 다르면 여기만 고치면 된다.

인증 정보(keychain, exchange="kiwoom"):
  app_key, app_secret  — 필수 (openapi.kiwoom.com 발급)
  account_no           — 잔고 조회용 계좌번호
  is_mock              — "1"이면 모의투자 도메인(mockapi) 사용

참고: 키움 REST 가이드 https://openapi.kiwoom.com/guide
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..keychain import get_api_key

# ── 도메인 (실전/모의) ──
_BASE_REAL = "https://api.kiwoom.com"
_BASE_MOCK = "https://mockapi.kiwoom.com"

# ── 저수준 경로/헤더 (⚠ 실제 응답으로 검증) ──
_TOKEN_PATH = "/oauth2/token"  # 접근토큰 발급
# 국내주식 요청은 카테고리별 경로 + 헤더 api-id(TR코드)로 라우팅된다.
# 예: 계좌=/api/dostk/acnt, 종목정보=/api/dostk/stkinfo, 순위=/api/dostk/rkinfo
_API_PATHS = {
    "acnt": "/api/dostk/acnt",       # 계좌 (잔고·평가·예수금)
    "stkinfo": "/api/dostk/stkinfo",  # 종목정보 (현재가·투자자수급)
    "rkinfo": "/api/dostk/rkinfo",    # 순위정보 (상승/하락/거래량)
    "chart": "/api/dostk/chart",      # 차트 (일봉/주봉 등)
    "sect": "/api/dostk/sect",        # 업종 (업종별 투자자순매수 등)
    "us_acnt": "/api/us/acnt",        # 미국주식 계좌 (2026-07 신규, 국내와 다른 /api/us)
}

_TIMEOUT = httpx.Timeout(8.0)
_TOKEN_SAFETY_SEC = 60  # 만료 60초 전에 미리 갱신


class KiwoomError(RuntimeError):
    pass


class KiwoomClient:
    """토큰 캐시 + 카테고리 호출. 인스턴스는 요청마다 새로 만들어도 되고
    (토큰 캐시는 클래스 레벨) 재사용해도 된다."""

    _token: str | None = None
    _token_exp: float = 0.0  # epoch seconds

    def __init__(self) -> None:
        self.app_key = get_api_key("kiwoom", "app_key")
        self.app_secret = get_api_key("kiwoom", "app_secret")
        self.account_no = get_api_key("kiwoom", "account_no")
        self.is_mock = get_api_key("kiwoom", "is_mock") == "1"
        self.base = _BASE_MOCK if self.is_mock else _BASE_REAL

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret)

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        now = time.time()
        if KiwoomClient._token and now < KiwoomClient._token_exp - _TOKEN_SAFETY_SEC:
            return KiwoomClient._token
        resp = await client.post(
            f"{self.base}{_TOKEN_PATH}",
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            raise KiwoomError(f"토큰 발급 응답에 token 없음: {data}")
        # expires_dt(만료시각 문자열) 또는 expires_in(초) 지원 — 없으면 12시간 가정
        exp_in = data.get("expires_in")
        KiwoomClient._token = token
        KiwoomClient._token_exp = now + (float(exp_in) if exp_in else 12 * 3600)
        return token

    async def call(
        self,
        category: str,
        api_id: str,
        body: dict[str, Any] | None = None,
        cont_yn: str = "N",
        next_key: str = "",
    ) -> dict[str, Any]:
        """category(_API_PATHS 키) + api_id(TR코드)로 국내주식 REST 호출.
        연속조회는 cont_yn/next_key로. 응답 JSON(dict)을 그대로 반환한다."""
        if not self.configured:
            raise KiwoomError("키움 앱키/시크릿 미설정")
        path = _API_PATHS.get(category)
        if not path:
            raise KiwoomError(f"알 수 없는 카테고리: {category}")
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            token = await self._ensure_token(client)
            resp = await client.post(
                f"{self.base}{path}",
                headers={
                    "authorization": f"Bearer {token}",
                    "api-id": api_id,
                    "cont-yn": cont_yn,
                    "next-key": next_key,
                },
                json=body or {},
            )
            resp.raise_for_status()
            return resp.json()
