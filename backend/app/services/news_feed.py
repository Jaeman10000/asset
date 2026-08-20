"""마켓 뉴스 요약 — 언론사 공개 RSS (무료·무키). v0.3 좌측 하단 카드.

가짜 뉴스를 만들지 않기 위한 유일한 정직한 경로: 실제 언론사 RSS를 수집한다.
10분 캐시 + stale-on-error (피드 하나가 죽어도 나머지로 채우고, 전부 죽으면 이전 값 유지).
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

# 공개 RSS — 실제로 응답하는 피드만 살아남게 하고, 죽은 피드는 조용히 건너뜀
_FEEDS: list[tuple[str, str]] = [
    ("한경", "https://www.hankyung.com/feed/finance"),
    ("한경", "https://www.hankyung.com/feed/economy"),
    ("매경", "https://www.mk.co.kr/rss/30800011/"),  # 증권
    ("연합", "https://www.yna.co.kr/rss/economy.xml"),
]

_TTL = 600.0
_cache: dict[str, Any] = {"at": 0.0, "items": []}


def _parse_ts(s: str | None) -> int:
    if not s:
        return 0
    try:
        return int(parsedate_to_datetime(s).timestamp() * 1000)
    except Exception:
        try:
            return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            return 0


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return t.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


async def fetch_news(limit: int = 8) -> list[dict[str, Any]]:
    now = time.time()
    if _cache["items"] and now - _cache["at"] < _TTL:
        return _cache["items"]
    items: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    async with httpx.AsyncClient(
        timeout=6, headers={"User-Agent": "Mozilla/5.0 (VitalityNexus RSS)"}, follow_redirects=True
    ) as h:
        for source, url in _FEEDS:
            try:
                r = await h.get(url)
                if r.status_code != 200:
                    continue
                root = ET.fromstring(r.content)
                for item in root.iter("item"):
                    title = _clean(item.findtext("title") or "")
                    link = (item.findtext("link") or "").strip()
                    ts = _parse_ts(item.findtext("pubDate"))
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)
                    items.append({"source": source, "title": title, "link": link, "ts": ts})
            except Exception:
                continue  # 피드 하나 죽어도 나머지로
    if items:
        items.sort(key=lambda x: x["ts"], reverse=True)
        _cache.update(at=now, items=items[:limit])
    # 전부 실패 → 이전 캐시(있으면) 유지
    return _cache["items"]


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
