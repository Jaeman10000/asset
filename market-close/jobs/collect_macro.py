"""간밤 미국 금리 결정(FOMC) 확인 기사 — 대본은 여러 매체가 같이 말한 것만 쓴다.

왜(JJ 2026-09-17): "새벽 FOMC 금리 인상과 매파 발언, 관련 뉴스를 간단하게 — 피바람이면 엮고, 보합·상승이면 훅으로."
아침 미국편(05:40)의 news_us.json 은 뉴욕 마감 기사 위주라 '0.25%포인트·3년 2개월·만장일치·점도표·한미 금리차'가
제목에 잘 안 나온다. 국장 마감 뉴스 창(15:20~)에는 새벽 기사가 안 들어온다. 그래서 오늘 0시 이후 기사를 따로 모은다.

news_us.json 에 금리 결정 기사(같은 결정 3건 이상)가 없으면 아무것도 모으지 않는다(평소엔 빈 파일).
실패해도 예외를 내지 않는다 — 영상 제작을 막지 않는다.

쓰기(market-close/jobs 에서):  python collect_macro.py 20260917
결과: data/<날짜>/raw/news_macro.json  {date, queries, items:[{title, source, pub, q}]}
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone

import httpx

import collect_news as cn
from _common import DATA, load_json, log, save_json

KST = timezone(timedelta(hours=9))
QUERIES = ["연준 기준금리 인상", "연준 기준금리 인하", "연준 기준금리 동결", "FOMC 점도표", "워시 기자회견 인플레이션",
           "한미 금리차", "금리 인상 수혜 금융주 보험주", "연준 만장일치"]


def fed_event(d: str) -> bool:
    n = load_json(DATA / d / "raw" / "news_us.json") or {}
    titles = [str(it.get("title") or "") for it in (n.get("items") or []) if isinstance(it, dict)]
    return any(sum(1 for t in titles if re.search(rf"금리\s?{w}", t)) >= 3 for w in ("인상", "인하", "동결"))


def main(d: str) -> dict:
    path = DATA / d / "raw" / "news_macro.json"
    out: dict = {"date": d, "queries": [], "items": []}
    try:
        if not fed_event(d):
            out["skipped"] = "간밤 금리 결정 기사 없음"
            save_json(path, out)
            return out
        day0 = datetime.strptime(d[:8], "%Y%m%d")                     # cn._to_kst 는 KST 기준 naive 시각을 준다
        seen: set[str] = set()
        with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as cl:
            for q in QUERIES:
                try:
                    items = cn._fetch(cl, q)
                except Exception as e:  # noqa: BLE001
                    log(d, "macro", f"'{q}' 실패: {e}")
                    continue
                out["queries"].append(q)
                k = 0
                for it in items:
                    pub = cn._to_kst(it.get("pub_raw") or "")
                    if pub is None or pub < day0 - timedelta(hours=1):
                        continue
                    title = cn._clean_title(it.get("title") or "", it.get("source") or "")
                    key = cn._norm_key(title)
                    if not title or key in seen:
                        continue
                    seen.add(key)
                    out["items"].append({"title": title, "source": it.get("source") or "", "pub": pub.isoformat(), "q": q})
                    k += 1
                    if k >= 15:
                        break
        log(d, "macro", f"금리 결정 확인 기사 {len(out['items'])}건")
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        log(d, "macro", f"실패(무시): {e}")
    save_json(path, out)
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).strftime("%Y%m%d"))
