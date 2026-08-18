"""전 종목 마스터(ka10099) — 검색 자동완성의 근간.

키움 ka10099(종목정보 리스트)로 KOSPI(mrkt_tp=0)+KOSDAQ(10) 전 종목의
코드·이름·업종을 받는다(실측: 2,475 + 1,822 ≈ 4,300종목. mrkt_tp=3은 ELW라 제외).
하루 1번만 받아 캐시하므로, 프론트가 이 목록을 한 번 내려받으면
타이핑 중 검색은 전부 로컬에서 돈다(API 호출 0회 — 키움 레이트리밋 안전).
"""
from __future__ import annotations

import time
from typing import Any

from .kiwoom_client import KiwoomClient

_TTL = 86400.0  # 상장 종목 목록은 하루면 충분
_cache: dict[str, Any] = {"at": 0.0, "items": []}

_MARKETS = (("0", "KOSPI"), ("10", "KOSDAQ"))


def _rows_of(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


async def fetch_master() -> list[dict[str, str]]:
    """[{code, name, market, industry}] — 실패 시 이전 캐시(있으면) 유지."""
    now = time.time()
    if _cache["items"] and now - _cache["at"] < _TTL:
        return _cache["items"]
    client = KiwoomClient()
    if not client.configured:
        return _cache["items"]
    items: list[dict[str, str]] = []
    for mrkt_tp, label in _MARKETS:
        try:
            data = await client.call("stkinfo", "ka10099", {"mrkt_tp": mrkt_tp})
        except Exception:
            return _cache["items"]  # 부분 실패면 통째로 이전 캐시 유지(반쪽 목록 방지)
        for r in _rows_of(data):
            code = str(r.get("code") or "").strip()
            name = str(r.get("name") or "").strip()
            if not code or not name:
                continue
            # 스팩(기업인수목적회사)은 검색 노이즈 — 제외
            if "스팩" in name:
                continue
            items.append(
                {
                    "code": code,
                    "name": name,
                    "market": label,
                    "industry": str(r.get("upName") or "").strip(),
                }
            )
    if items:
        _cache.update(at=now, items=items)
    return _cache["items"]
