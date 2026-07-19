"""
7초 TTL 캐시 (스펙: "캐시 7초 TTL").

프론트엔드가 폴링해도 매번 6개 어댑터를 다 때리지 않도록, 짧은 시간 동안은
직전 결과를 재사용한다. asyncio.Lock으로 동시 요청이 몰려도 fetch_fn이
한 번만 실행되게 한다 (thundering herd 방지).
"""
import asyncio
import time
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float):
        self.ttl = ttl_seconds
        self._value: T | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_or_fetch(self, fetch_fn: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        if self._value is not None and now < self._expires_at:
            return self._value

        async with self._lock:
            # 락 대기 중 다른 요청이 이미 갱신했을 수 있으니 재확인
            now = time.monotonic()
            if self._value is not None and now < self._expires_at:
                return self._value

            value = await fetch_fn()
            self._value = value
            self._expires_at = time.monotonic() + self.ttl
            return value

    def clear(self) -> None:
        """캐시 무효화 — 다음 조회에서 새로 fetch (예: 키 변경 직후)."""
        self._value = None
        self._expires_at = 0.0
