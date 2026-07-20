"""업비트 어댑터 — 실계좌 보유 코인 (JWT 인증 /v1/accounts).

시세(현재가)는 공개 API지만 "내가 얼마 보유했는지"는 계좌 조회라 API 키가 필요하다.
업비트 인증은 access_key + secret_key로 JWT(HS256)를 서명한다. PyJWT 의존성 없이
hmac+base64url로 직접 만든다(오프라인 사이드카에 추가 패키지 최소화).

keychain(exchange="upbit"): access_key, secret_key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import httpx

from ..keychain import get_api_key
from ..schemas import Position, SourceError
from ..services.quotes import fetch_upbit_quotes
from .base import AdapterResult, BaseAdapter

_ACCOUNTS = "https://api.upbit.com/v1/accounts"
_TIMEOUT = httpx.Timeout(8.0)
# 소액/비상장(먼지) 자산 숨김 임계값(KRW) — 평가금액이 이 값 미만이면 목록 제외.
_DUST_KRW = 1000.0


def _jwt(access_key: str, secret_key: str) -> str:
    """파라미터 없는 요청용 업비트 JWT (access_key + nonce). HS256 직접 서명."""

    def seg(obj: dict) -> bytes:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing = seg({"alg": "HS256", "typ": "JWT"}) + b"." + seg(
        {"access_key": access_key, "nonce": str(uuid.uuid4())}
    )
    sig = base64.urlsafe_b64encode(
        hmac.new(secret_key.encode(), signing, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (signing + b"." + sig).decode()


class UpbitAdapter(BaseAdapter):
    name = "upbit"

    async def fetch(self) -> AdapterResult:
        access = get_api_key("upbit", "access_key")
        secret = get_api_key("upbit", "secret_key")
        if not (access and secret):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="업비트 API 키 미설정 — 앱의 '거래소 연동'에서 등록",
                ),
            )
        try:
            token = _jwt(access, secret)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    _ACCOUNTS, headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code != 200:
                    # 업비트가 주는 실제 원인(error.name)을 표면화 → 유저가 IP/권한/키를
                    # 바로 구분할 수 있게. 예: no_authorization_ip(IP 미허용),
                    # invalid_access_key(키 오류), jwt_verification(서명 오류).
                    name = ""
                    try:
                        name = resp.json().get("error", {}).get("name", "")
                    except Exception:
                        name = resp.text[:80]
                    hint = {
                        "no_authorization_ip": "키에 등록한 허용 IP가 현재 IP와 다릅니다 — 업비트 Open API 관리에서 현재 IP로 갱신하세요",
                        "invalid_access_key": "Access Key가 올바르지 않습니다 (오타/누락 확인)",
                        "jwt_verification": "Secret Key가 올바르지 않습니다",
                        "out_of_scope": "키에 '자산조회' 권한이 없습니다",
                    }.get(name, "업비트 Open API 관리에서 자산조회 권한 + 현재 IP 등록을 확인하세요")
                    return AdapterResult(
                        error=SourceError(
                            source=self.name,
                            message=f"업비트 인증 실패({resp.status_code}, {name or '?'}) — {hint}",
                        )
                    )
                accounts = resp.json()
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                error=SourceError(source=self.name, message=f"업비트 조회 실패: {exc}")
            )

        # accounts: [{currency, balance, locked, avg_buy_price, unit_currency}]
        coins: list[tuple[str, float, float]] = []
        for a in accounts if isinstance(accounts, list) else []:
            cur = str(a.get("currency", "")).upper()
            if not cur or cur == "KRW":  # 원화 예수금은 코인 아님 → 제외
                continue
            try:
                qty = float(a.get("balance", 0) or 0) + float(a.get("locked", 0) or 0)
                avg = float(a.get("avg_buy_price", 0) or 0)
            except (TypeError, ValueError):
                continue
            if qty > 0:
                coins.append((cur, qty, avg))
        if not coins:
            return AdapterResult()  # 키는 정상, 보유 코인 없음

        quotes = await fetch_upbit_quotes([c for c, _, _ in coins])
        now = int(time.time() * 1000)
        positions: list[Position] = []
        for i, (cur, qty, avg) in enumerate(coins):
            q = quotes.get(cur)
            price = q.price if q else avg
            ret = round((price - avg) / avg * 100, 2) if avg else 0.0
            positions.append(
                Position(
                    id=f"upbit:{i}:{cur}",
                    exchange="upbit",
                    assetType="crypto",
                    region=None,
                    symbol=cur,
                    name=cur,
                    qty=qty,
                    avg=avg,
                    price=price,
                    currency="KRW",
                    value=qty * price,
                    cost=qty * avg,
                    ret=ret,
                    lastUpdated=now,
                )
            )
        # 소액/비상장(먼지) 숨김 — 평가금액 기준
        positions = [p for p in positions if p.value >= _DUST_KRW]
        return AdapterResult(positions=positions)
