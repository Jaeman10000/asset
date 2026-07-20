"""빗썸 어댑터 — 실계좌 보유 코인 (v1 API, JWT 인증).

빗썸이 2024년 구API(HMAC-SHA512, /info/balance)를 신API(v1, Upbit와 동일 구조의
JWT)로 전환했다. 새로 발급한 키는 신API 전용이라 이 방식으로만 동작한다.
  JWT payload: {access_key, nonce(uuid), timestamp(ms)}, HS256 서명, Bearer 헤더.
  GET https://api.bithumb.com/v1/accounts → [{currency, balance, locked,
  avg_buy_price, unit_currency}, ...] (리스트를 바로 반환, wrapper 없음).

keychain(exchange="bithumb"): api_key, secret_key.
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
from .base import AdapterResult, BaseAdapter

_ACCOUNTS = "https://api.bithumb.com/v1/accounts"
_TIMEOUT = httpx.Timeout(8.0)
# 소액/비상장(먼지) 자산 숨김 임계값(KRW). 0.00001개씩 사둔 잔여·상장폐지(시세 0)
# 코인이 수십 개씩 잡히는 걸 막는다. 평가금액이 이 값 미만이면 목록에서 제외.
_DUST_KRW = 1000.0


def _jwt(access_key: str, secret_key: str) -> str:
    """빗썸 v1 JWT — access_key+nonce+timestamp, HS256 직접 서명(PyJWT 없이)."""

    def seg(obj: dict) -> bytes:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
    }
    signing = seg({"alg": "HS256", "typ": "JWT"}) + b"." + seg(payload)
    sig = base64.urlsafe_b64encode(
        hmac.new(secret_key.encode(), signing, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (signing + b"." + sig).decode()


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
        try:
            token = _jwt(api_key, secret)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    _ACCOUNTS, headers={"Authorization": f"Bearer {token}"}
                )
                resp.raise_for_status()
                accounts = resp.json()
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                error=SourceError(source=self.name, message=f"빗썸 조회 실패: {exc}")
            )

        # accounts: [{currency, balance, locked, avg_buy_price, unit_currency}]
        now = int(time.time() * 1000)
        positions: list[Position] = []
        i = 0
        for a in accounts if isinstance(accounts, list) else []:
            cur = str(a.get("currency", "")).upper()
            if not cur or cur == "KRW":
                continue
            try:
                qty = float(a.get("balance", 0) or 0) + float(a.get("locked", 0) or 0)
                avg = float(a.get("avg_buy_price", 0) or 0)
            except (TypeError, ValueError):
                continue
            if qty <= 0:
                continue
            price = avg  # 현재가는 공개 시세로 별도 보강(quotes.py) — 우선 평단으로 채움
            ret = 0.0
            positions.append(
                Position(
                    id=f"bithumb:{i}:{cur}",
                    exchange="bithumb",
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
            i += 1
        if not positions:
            return AdapterResult()  # 키는 정상, 보유 코인 없음

        # 공개 시세로 현재가 보강 (평단 대신 실시간가로 평가 + 수익률 계산)
        try:
            from ..services.quotes import fetch_bithumb_quotes

            quotes = await fetch_bithumb_quotes([p.symbol for p in positions])
            for p in positions:
                q = quotes.get(p.symbol)
                if q:
                    p.price = q.price
                    p.value = p.qty * q.price
                    p.ret = round((q.price - p.avg) / p.avg * 100, 2) if p.avg else 0.0
        except Exception:
            pass  # 시세 보강 실패해도 평단 기준 값은 이미 있음

        # 소액/비상장(먼지) 숨김 — 시세 보강 후의 실제 평가금액 기준
        positions = [p for p in positions if p.value >= _DUST_KRW]
        return AdapterResult(positions=positions)
