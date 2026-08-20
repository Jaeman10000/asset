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

# '마켓' 뉴스만 — 연합 경제 피드는 생활경제(케이크 출시·전세보증…)까지 쏟아져
# 잡뉴스가 섞였다(유저 지적). 제목에 시장 키워드가 있어야 통과.
_MARKET_KW = (
    "증시", "코스피", "코스닥", "주가", "주식", "상장", "반도체", "금리", "환율",
    "외국인", "기관", "나스닥", "다우", "S&P", "연준", "FOMC", "실적", "급등", "급락",
    "매수", "매도", "비트코인", "가상자산", "ETF", "채권", "유가", "수출", "삼성전자",
    "SK하이닉스", "공모", "IPO", "배당", "시총", "장중", "마감",
)


def _is_market_news(title: str) -> bool:
    return any(k in title for k in _MARKET_KW)


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
                    if not title or title in seen_titles or not _is_market_news(title):
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
