"""장 마감 헤드라인 — Google News RSS 검색(공개, 키 불필요).
kr: D 15:20~23:59 KST 사이 발행된 코스피/코스닥 마감 기사.
us: 직전 미국 영업일 세션 마감 기사 = (세션일+1) 04:30~23:59 KST.
결과: data/D/raw/news_{ed}.json  (실패해도 빈 구조 + error 필드로 저장, 절대 예외로 죽지 않음)
사용: python collect_news.py YYYYMMDD [kr|us]
"""
from __future__ import annotations

import html
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from _common import DATA, load_json, day_dir, log, save_json

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
      "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8", "Accept-Language": "ko-KR,ko;q=0.9"}
TIMEOUT = 20
MAX_ITEMS = 25
SLEEP_BETWEEN = 0.5

QUERIES = {
    "kr": ["코스피 마감", "코스닥 마감", "코스피 외국인 순매수"],
    "us": ["뉴욕증시 마감", "나스닥 마감", "미국 증시 반도체"],
}
# 잘라낼 때 우선 남길 통신사/주요 매체 (앞쪽일수록 우선)
PREFERRED = ["연합뉴스", "연합인포맥스", "뉴시스", "뉴스1", "머니투데이", "한국경제", "매일경제", "이데일리", "서울경제",
             "YTN", "KBS", "MBC", "SBS", "조선비즈", "인포스탁데일리"]


def _us_session_date(d: str) -> datetime:
    """D 직전 미국 영업일(월→금). collect_us와 동일 규칙."""
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt


def _window(d: str, ed: str) -> tuple[datetime, datetime, str]:
    """(from, to, session_yyyymmdd) — naive KST."""
    if ed == "us":
        session = _us_session_date(d)
        base = session + timedelta(days=1)
        return base.replace(hour=4, minute=30), base.replace(hour=23, minute=59, second=59), session.strftime("%Y%m%d")
    day = datetime.strptime(d, "%Y%m%d")
    return day.replace(hour=15, minute=20), day.replace(hour=23, minute=59, second=59), d


def _rss_url(q: str) -> str:
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}+when:3d&hl=ko&gl=KR&ceid=KR:ko"


def _to_kst(pub: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(pub.strip())
    except Exception:
        return None
    if dt.tzinfo is None:  # 'GMT' 없이 오면 UTC로 간주
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).replace(tzinfo=None)


def _clean_title(title: str, source: str) -> str:
    t = html.unescape(title or "").strip()
    suffix = f" - {source}" if source else ""
    if suffix and t.endswith(suffix):
        while t.endswith(suffix):  # 머니투데이처럼 제목 안에 매체명을 또 붙이는 곳 → 반복 제거
            t = t[: -len(suffix)].rstrip()
        return t
    head, sep, tail = t.rpartition(" - ")
    if sep and head and len(tail) <= 25:  # 매체명 꼬리(짧음)만 제거
        return head.rstrip()
    return t


def _norm_key(title: str) -> str:
    return re.sub(r"[\W_]+", "", title, flags=re.UNICODE).lower()[:25]


def _pref_rank(source: str) -> int:
    for i, name in enumerate(PREFERRED):
        if name and name in (source or ""):
            return i
    return len(PREFERRED)


def _parse_items(xml_text: str) -> list[dict]:
    """<item> → dict(title, link, pub_raw, source). etree 실패 시 정규식 폴백."""
    out = []
    try:
        root = ET.fromstring(xml_text)
        for it in root.iter("item"):
            src = it.find("source")
            out.append({
                "title": (it.findtext("title") or ""),
                "link": (it.findtext("link") or "").strip(),
                "pub_raw": (it.findtext("pubDate") or ""),
                "source": (src.text or "").strip() if src is not None else "",
            })
        return out
    except ET.ParseError:
        pass
    for it in re.findall(r"<item>(.*?)</item>", xml_text, flags=re.S):
        def g(tag: str) -> str:
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", it, flags=re.S)
            v = m.group(1) if m else ""
            v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", v.strip(), flags=re.S)
            return v
        out.append({"title": g("title"), "link": g("link").strip(), "pub_raw": g("pubDate"), "source": g("source").strip()})
    return out


def _fetch(client: httpx.Client, q: str) -> list[dict]:
    r = client.get(_rss_url(q))
    r.raise_for_status()
    return _parse_items(r.text)


EXTRA_KEEP = 4      # 이슈·업종·종목 쿼리는 주요 매체 우선 정렬에서 밀려도 쿼리마다 이만큼은 남긴다(9/15 실측: 이슈 쿼리 기사가 25건 컷에 전부 밀렸다)


def main(d: str, ed: str = "kr", extra: list[str] | None = None) -> dict:
    """extra: 기본 쿼리 뒤에 더 붙일 검색어(브리핑 형식의 유입 업종·종목 이름 — run_day 가 collect_brief 뒤에 부른다). 같은 창·같은 파일에 합쳐 저장한다."""
    ed = (ed or "kr").lower()
    if ed not in QUERIES:
        ed = "kr"
    raw = day_dir(d)
    path = raw / f"news_{ed}.json"
    tag = f"news_{ed}"
    w_from, w_to, session = _window(d, ed)
    extra_q = [q.strip() for q in (extra or []) if isinstance(q, str) and q.strip()]
    out: dict = {
        "edition": ed, "date": d, "session": session,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"from": w_from.strftime("%Y-%m-%d %H:%M"), "to": w_to.strftime("%Y-%m-%d %H:%M")},
        "queries": list(QUERIES[ed]) + ([ev_q] if (ev_q := ((load_json(DATA / "events.json") or {}).get(d) or {}).get("news_query")) and ed == "kr" else [])
                   + [q for q in extra_q if q not in QUERIES[ed]], "items": [], "error": None,
    }
    try:
        seen: dict[str, dict] = {}
        fails: list[str] = []
        with httpx.Client(headers=UA, timeout=TIMEOUT, follow_redirects=True) as client:
            for i, q in enumerate(out["queries"]):
                if i:
                    time.sleep(SLEEP_BETWEEN)
                try:
                    items = _fetch(client, q)
                except Exception as e:
                    fails.append(f"{q}: {type(e).__name__} {str(e)[:80]}")
                    log(d, tag, f"'{q}' 실패: {e}")
                    continue
                kept = 0
                for it in items:
                    kst = _to_kst(it["pub_raw"])
                    if kst is None or not (w_from <= kst <= w_to):
                        continue
                    title = _clean_title(it["title"], it["source"])
                    if not title:
                        continue
                    key = _norm_key(title)
                    if not key or key in seen:
                        continue
                    seen[key] = {"title": title, "source": it["source"], "pub_kst": kst.strftime("%Y-%m-%d %H:%M"),
                                 "query": q, "link": it["link"], "_t": kst}
                    kept += 1
                log(d, tag, f"'{q}': 수신 {len(items)} → 창 안 신규 {kept}")
        rows = list(seen.values())
        # 잘라낼 때 주요 매체 우선, 그 다음 최신순 — 다만 이슈·업종·종목 쿼리(기본 쿼리 밖)는 쿼리마다 EXTRA_KEEP 건을 먼저 남긴다
        rows.sort(key=lambda r: (_pref_rank(r["source"]), -r["_t"].timestamp()))
        base_q = set(QUERIES[ed])
        keep: list[dict] = []
        for q in out["queries"]:
            if q in base_q:
                continue
            keep += [r for r in rows if r["query"] == q and r not in keep][:EXTRA_KEEP]
        rows = keep + [r for r in rows if r not in keep]
        rows = rows[:MAX_ITEMS]
        rows.sort(key=lambda r: r["_t"], reverse=True)
        for r in rows:
            r.pop("_t", None)
        out["items"] = rows
        if fails:
            out["error"] = f"{len(fails)}/{len(out['queries'])} 쿼리 실패: " + " | ".join(fails)
        log(d, tag, f"{ed} 세션 {session} 창 {out['window']['from']}~{out['window']['to']}: {len(rows)}건" + (f" (error: {out['error']})" if out["error"] else ""))
    except Exception as e:
        out["items"] = []
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log(d, tag, f"수집 실패: {e}")
    try:
        save_json(path, out)
    except Exception as e:
        log(d, tag, f"저장 실패 {path}: {e}")
    return out


if __name__ == "__main__":
    _d = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    _ed = sys.argv[2] if len(sys.argv) > 2 else "kr"
    res = main(_d, _ed)
    for it in res["items"][:8]:
        log(_d, f"news_{res['edition']}", f"  {it['pub_kst']} [{it['source']}] {it['title']}")
