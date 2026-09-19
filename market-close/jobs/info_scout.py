"""생활형 정보 쇼츠 후보 찾기 — 매일 저녁(예약 작업 nugasatna-info-scout). JJ 2026-09-19.

오늘(when:1d) 구글 뉴스에서 '투자자 생활에 바로 닿는 제도·일정·세금·시장 큰 선' 기사를 모으고,
같은 이야기를 쓴 매체가 3곳 이상인 것만 후보로 남긴다(지어내지 않는다 — 여러 매체가 같이 말한 것만).
결과: data/<날짜>/info_candidates.json {"date", "cands": [{"topic", "score", "outlets", "titles": [...], "links": [...], "why"}]}
후보를 고르고 대본을 쓰는 건 예약 작업(Claude)이 한다 — 이 스크립트는 사람 판단 전의 목록만 만든다.

실행: python info_scout.py [YYYYMMDD]
"""
from __future__ import annotations

import email.utils
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from _common import DATA, log, save_json

KST = timezone(timedelta(hours=9))
# 주제 → 검색어. 시청자(45세 이상 76%)가 '내 돈·내 계좌'에 바로 닿는다고 느끼는 것
TOPICS = {
    "거래시간·휴장": ["주식 거래시간", "애프터마켓", "프리마켓", "증시 휴장", "넥스트레이드"],
    "세금": ["양도소득세 주식", "배당소득 분리과세", "금융투자소득세", "증권거래세", "대주주 요건"],
    "절세계좌·연금": ["ISA 개편", "연금저축 세액공제", "IRP 한도", "국민연금 수익률"],
    "공매도·신용": ["공매도", "신용융자 반대매매", "빚투"],
    "배당·자사주": ["배당 기준일", "자사주 소각 의무", "밸류업 배당"],
    "공모주·상장": ["공모주 청약", "상장 첫날", "따상"],
    # JJ 2026-09-19 "우리 주가 한국주식 관련이잖아" — 대출·예금 같은 가계 금융은 뺀다(구독 전환: 생활형 9/13 조회 1천당 0.4명 vs 국장편 2~5명).
    # 금리·환율은 제목에 증시 말이 같이 있을 때만(아래 STOCK_CTX).
    "금리·환율(증시)": ["기준금리 결정", "환율 1400", "환율 1500"],
    "지수 큰 선": ["코스피 7000", "코스피 사상 최고", "코스피 8000", "코스닥 1000"],
    "증권사·앱": ["증권사 수수료 무료", "MTS 장애", "증권사 앱 먹통"],
}
# 제목에 이 말이 있으면 '오늘 바뀌는/정해진 일' — 가산점
IMPACT = re.compile(r"부터|시행|바뀐다|달라진다|달라지는|도입|폐지|연장|인하|인상|확정|마감|신청|개편|허용|금지|재개|사상 최고|돌파|붕괴|먹통|장애")
STOCK_CTX = re.compile(r"코스피|코스닥|증시|주식|주가|국장|외국인|반도체|삼성전자|SK하이닉스")
NOISE = re.compile(r"\[포토\]|카지노|토토|운세|날씨|부고|인사\]|사설|칼럼|기고")


def fetch(q: str) -> list[dict]:
    u = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:1d") + "&hl=ko&gl=KR&ceid=KR:ko"
    try:
        x = ET.fromstring(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
    except Exception:
        return []
    out = []
    for it in x.iter("item"):
        t = it.findtext("title") or ""
        if NOISE.search(t):
            continue
        src = (it.findtext("source") or "").strip() or (t.rsplit(" - ", 1)[-1] if " - " in t else "")
        try:
            dt = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(KST)
        except Exception:
            continue
        out.append({"title": t.rsplit(" - ", 1)[0].strip(), "source": src, "link": it.findtext("link") or "", "at": dt})
    return out


def main(d: str) -> dict:
    day = datetime.strptime(d, "%Y%m%d").date()
    cands = []
    for topic, qs in TOPICS.items():
        rows, seen = [], set()
        for q in qs:
            key = max(q.split(), key=len)                  # 구글 검색은 느슨하다(9/19 '프리마켓' → 종교계 기사) — 가장 구체적인 낱말이 제목에 있어야 한다
            for r in fetch(q):
                if r["at"].date() != day or r["title"] in seen or key not in r["title"]:
                    continue
                if topic.startswith("금리") and not STOCK_CTX.search(r["title"]):
                    continue
                seen.add(r["title"])
                r["q"] = q
                rows.append(r)
        if not rows:
            continue
        # 같은 검색어로 모인 기사끼리가 한 이야기 — 검색어마다 매체 수를 센다
        by_q: dict[str, list] = defaultdict(list)
        for r in rows:
            by_q[r["q"]].append(r)
        for q, rs in by_q.items():
            outlets = sorted({r["source"] for r in rs if r["source"]})
            if len(outlets) < 3:
                continue
            imp = sum(1 for r in rs if IMPACT.search(r["title"]))
            score = len(outlets) + 2 * imp
            rs = sorted(rs, key=lambda r: (not IMPACT.search(r["title"]), r["at"]))
            cands.append({"topic": topic, "query": q, "score": score, "outlets": len(outlets), "impact_titles": imp,
                          "titles": [f"{r['at']:%H:%M} {r['source']} · {r['title']}" for r in rs[:8]],
                          "links": [r["link"] for r in rs[:4]],
                          "why": f"{len(outlets)}개 매체, 바뀌는/정해진 일 제목 {imp}건"})
    cands.sort(key=lambda c: -c["score"])
    out = {"date": d, "made_at": datetime.now(KST).isoformat(timespec="minutes"), "cands": cands[:6]}
    (DATA / d).mkdir(parents=True, exist_ok=True)
    save_json(DATA / d / "info_candidates.json", out)
    log(d, "info_scout", "후보 " + (", ".join(f"{c['topic']}({c['query']}, {c['outlets']}곳)" for c in out["cands"]) or "없음"))
    return out


if __name__ == "__main__":
    r = main(sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).strftime("%Y%m%d"))
    for c in r["cands"]:
        print(f"[{c['score']}] {c['topic']} · {c['query']} · {c['why']}")
        for t in c["titles"][:4]:
            print("    ", t)
