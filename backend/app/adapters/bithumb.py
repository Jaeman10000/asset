"""빗썸 어댑터 — 실계좌 보유 코인 (info/balance, HMAC-SHA512 인증).

빗썸 1.0 프라이빗 API: endpoint를 바디에 포함해 서명한다.
  msg  = endpoint + \\0 + urlencode(body) + \\0 + nonce
  sign = base64( hex( HMAC_SHA512(msg, secret) ) )
잔고 응답엔 평단가가 없어 avg=현재가(ret 0)로 둔다(보유·평가금액은 정확).

keychain(exchange="bithumb"): api_key, secret_key.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

from ..keychain import get_api_key
from ..schemas import Position, SourceError
from .base import AdapterResult, BaseAdapter

_BASE = "https://api.bithumb.com"
_ENDPOINT = "/info/balance"
_TIMEOUT = httpx.Timeout(8.0)


def _sign(endpoint: str, body: dict, secret: str, nonce: str) -> str:
    str_data = urlencode(body)
    msg = f"{endpoint}\0{str_data}\0{nonce}"
    digest = hmac.new(secret.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return base64.b64encode(digest.encode()).decode()


class BithumbAdapter(BaseAdapter):
    name = "bithumb"

    async def fetch(self) -> AdapterResult:
        api_key = get_api_key("bithumb", "api_key")
        secret = get_api_key("bithumb", "secret_key")
        if not (api_key and secret):
            return AdapterResult(
                unconfigured=True,
                error=SourceError(
                    source=self.name,
                    message="빗썸 API 키 미설정 — 앱의 '거래소 연동'에서 등록",
                ),
            )
        nonce = str(int(time.time() * 1000))
        body = {"endpoint": _ENDPOINT, "currency": "ALL"}
        headers = {
            "Api-Key": api_key,
            "Api-Sign": _sign(_ENDPOINT, body, secret, nonce),
            "Api-Nonce": nonce,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{_BASE}{_ENDPOINT}", headers=headers, data=body)
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                error=SourceError(source=self.name, message=f"빗썸 조회 실패: {exc}")
            )
        if str(payload.get("status")) != "0000":
            return AdapterResult(
                error=SourceError(
                    source=self.name,
                    message=f"빗썸 오류: {payload.get('message') or payload.get('status')}",
                )
            )

        data = payload.get("data", {}) or {}

        def num(v) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        now = int(time.time() * 1000)
        positions: list[Position] = []
        i = 0
        for key, val in data.items():
            if not key.startswith("total_"):
                continue
            coin = key[len("total_") :].upper()
            if coin == "KRW":
                continue
            qty = num(val)
            if qty <= 0:
                continue
            price = num(data.get(f"xcoin_last_{coin.lower()}"))
            if price <= 0:
                continue  # 시세 없는 코인은 평가 불가 → 스킵
            positions.append(
                Position(
                    id=f"bithumb:{i}:{coin}",
                    exchange="bithumb",
                    assetType="crypto",
                    region=None,
                    symbol=coin,
                    name=coin,
                    qty=qty,
                    avg=price,  # 빗썸 잔고엔 평단 없음 → 현재가로(ret 0)
                    price=price,
                    currency="KRW",
                    value=qty * price,
                    cost=qty * price,
                    ret=0.0,
                    lastUpdated=now,
                )
            )
            i += 1
        return AdapterResult(positions=positions)
