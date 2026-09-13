"""검색 키워드 수집 — 주식 투자자가 유튜브에서 실제로 치는 말을 매일 모아 제목·태그·해시태그에 끼운다.
소스(키 없음): ① 유튜브 자동완성(suggestqueries, client=youtube) — 시드 검색어별 상위 제안
              ② 구글 트렌드 KR 일간 급상승 RSS — 오늘 마감시황 헤드라인이나 금융 어휘에 걸리는 것만
결과: data/D/raw/trends.json {"daily":[{"kw","score","src"}…], "weekly":[…]} + data/trends_week.json(7일 누적)
실패해도 빈 목록을 저장하고 제작은 계속된다.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta

import httpx

from _common import DATA, day_dir, load_json, log, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
SEEDS = ["코스피", "코스닥", "주식", "국장", "증시", "외국인 순매수", "기관 순매수", "반도체", "삼성전자", "SK하이닉스", "환율", "금리", "수급"]
# 금융 어휘 — 제안·트렌드 중 이 중 하나라도 들어가야 채택
FIN = ("주가", "주식", "전망", "실시간", "야간선물", "순매수", "순매도", "외국인", "기관", "코스피", "코스닥", "반도체", "관세", "etf", "ETF", "배당",
       "금리", "환율", "마감", "시황", "증시", "국장", "하이닉스", "삼성전자", "실적", "공매도", "프로그램", "동시만기", "선물", "옵션", "매매동향",
       "수급", "테마", "급등", "급락", "상승", "하락", "연준", "FOMC", "CPI", "고용", "물가", "엔비디아", "젠슨", "미장", "나스닥", "달러", "채권")
# 우리 채널과 안 맞거나 검색 품질을 떨어뜨리는 말 — 제외
STOP = ("여행", "먹방", "반응", "브이로그", "학과", "공정", "강의", "시작하는법", "고백", "여자친구", "한식", "불닭", "라이브", "방송", "추천", "리딩",
        "단타", "세력", "하면 안되는", "설명", "기초", "명사수", "단테", "아가방", "애소리", "아저씨", "장인", "세금")
WEEK = DATA / "trends_week.json"


def _suggest(q: str) -> list[str]:
    r = httpx.get("https://suggestqueries.google.com/complete/search", params={"client": "youtube", "ds": "yt", "hl": "ko", "gl": "kr", "q": q},
                  headers=UA, timeout=15)
    m = re.search(r"\((.*)\)\s*$", r.text, flags=re.S)
    data = json.loads(m.group(1))
    return [x[0] for x in data[1] if isinstance(x, list) and x]


def _gtrends() -> list[tuple[str, int]]:
    r = httpx.get("https://trends.google.com/trending/rss?geo=KR", headers=UA, timeout=15)
    items = re.findall(r"<item>(.*?)</item>", r.text, flags=re.S)
    out = []
    for it in items:
        t = re.search(r"<title>(.*?)</title>", it)
        tr = re.search(r"<ht:approx_traffic>(.*?)</ht:approx_traffic>", it)
        if t:
            n = int(re.sub(r"\D", "", tr.group(1)) or 0) if tr else 0
            out.append((t.group(1).strip(), n))
    return out


# 제목·해시태그에 쓸 때 요구하는 '검색 의도' 어휘 — 우리 영상이 실제로 답하는 것만(전망·실시간·추천은 태그에만)
INTENT = ("주가", "순매수", "순매도", "마감", "시황", "오르는 이유", "내리는 이유", "외국인", "기관", "수급", "야간선물", "관세", "금리", "환율",
          "매매동향", "공매도", "동시만기", "ETF", "etf", "대장주", "급등", "급락")
TITLE_BLOCK = ("전망", "실시간", "추천", "대장주", "라이브")


def _ok(kw: str, entities: list[str]) -> bool:
    if any(s in kw for s in STOP):
        return False
    return any(f.lower() in kw.lower() for f in FIN)


def _norm(kw: str) -> str:
    return re.sub(r"[\s·]", "", kw).lower()


def main(d: str, entities: list[str] | None = None, headlines: list[str] | None = None) -> dict:
    raw = day_dir(d)
    entities = [e for e in (entities or []) if e]
    scores: dict[str, dict] = {}

    def add(kw: str, sc: float, src: str):
        kw = re.sub(r"\s+", " ", kw).strip()
        if len(kw) < 2 or len(kw) > 20 or not _ok(kw, entities):
            return
        cur = scores.setdefault(kw, {"kw": kw, "score": 0.0, "src": set()})
        cur["score"] += sc
        cur["src"].add(src)

    # ① 유튜브 자동완성: 고정 시드 + 오늘의 테마·종목
    seeds = SEEDS + [e for e in entities if e not in SEEDS][:6]
    for i, s in enumerate(seeds):
        try:
            for rank, kw in enumerate(_suggest(s)[:10]):
                if kw == s:
                    continue
                add(kw, (10 - rank) * (1.3 if s in entities else 1.0), f"yt:{s}")
            time.sleep(0.2)
        except Exception as e:
            log(d, "trends", f"자동완성 실패 {s}: {str(e)[:80]}")
    # ② 구글 트렌드 급상승 — 헤드라인에 등장하거나 금융 어휘·오늘 엔티티에 걸리면
    try:
        heads = " ".join(headlines or [])
        for kw, n in _gtrends():
            if kw in heads or _ok(kw, entities):
                add(kw, 6 + min(n, 20000) / 2000, "gtrends")
    except Exception as e:
        log(d, "trends", f"구글 트렌드 실패: {str(e)[:80]}")

    daily = sorted(({**v, "src": sorted(v["src"]), "score": round(v["score"], 1)} for v in scores.values()), key=lambda x: -x["score"])
    seen, dedup = [], []
    for x in daily:
        n = _norm(x["kw"])
        if any(n == s or (n.startswith(s) and len(n) - len(s) <= 4) for s in seen):
            continue
        seen.append(n); dedup.append(x)
    daily = dedup
    # 7일 누적
    week = load_json(WEEK) or {}
    cutoff = (datetime.strptime(d, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
    for kw, rec in list(week.items()):
        rec["days"] = {k: v for k, v in rec.get("days", {}).items() if k >= cutoff}
        if not rec["days"]:
            week.pop(kw)
    for x in daily[:40]:
        week.setdefault(x["kw"], {"days": {}})["days"][d] = x["score"]
    save_json(WEEK, week)
    weekly = sorted(({"kw": k, "score": round(sum(v["days"].values()), 1), "days": len(v["days"])} for k, v in week.items()), key=lambda x: -x["score"])
    out = {"date": d, "fetched_at": datetime.now().isoformat(timespec="seconds"), "entities": entities,
           "daily": daily[:30], "weekly": weekly[:20]}
    save_json(raw / "trends.json", out)
    log(d, "trends", f"일간 {len(daily)}개 → 상위 {[x['kw'] for x in daily[:6]]} | 주간 상위 {[x['kw'] for x in weekly[:4]]}")
    return out


# 제목·해시태그에 들어가는 검색어는 영상(대본)에 실제로 나오는 말이어야 한다. 아래 일반어는 대본 등장 여부를 따지지 않는다.
GENERIC = ("주가", "주식", "순매수", "순매도", "종목", "마감", "시황", "오늘", "외국인", "기관", "개인", "코스피", "코스닥", "국장", "증시", "수급", "이유")


# 남의 채널 이름은 태그·제목·해시태그에 절대 넣지 않는다(오해 소지 메타데이터 정책). 자동완성엔 채널명이 자주 섞여 온다.
BRAND_BLOCK = ("증시각도기", "삼프로", "슈카", "김작가", "달란트", "전인구", "박곰희", "부읽남", "신사임당", "체슬리", "소수몽키", "월가아재",
               "미주미", "경제사냥꾼", "한국경제tv", "매일경제", "머니투데이", "이데일리", "연합뉴스", "sbs", "kbs", "mbc", "jtbc", "ytn")
_BRAND_CACHE = DATA / "trends_brand_cache.json"


def _is_brand(kw: str) -> bool:
    """검색어가 특정 유튜브 채널의 이름인지. 정적 목록 → 'tv/티비' 접미 → 유튜브 검색 결과(채널 카드·상위 채널명) 순으로 판정, 결과는 캐시."""
    n = _norm(kw)
    if any(b in n for b in BRAND_BLOCK) or re.search(r"(tv|티비|채널)$", n):
        return True
    cache = load_json(_BRAND_CACHE) or {}
    if kw in cache:
        return bool(cache[kw])
    res = False
    try:
        r = httpx.get("https://www.youtube.com/results", params={"search_query": kw, "hl": "ko", "gl": "KR"}, headers=UA, timeout=15)
        chan_cards = re.findall(r'"channelRenderer":\{"channelId":"[^"]+","title":\{"simpleText":"([^"]+)"', r.text)
        owners = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', r.text)[:10]
        if any(n in _norm(c) for c in chan_cards):
            res = True
        elif sum(1 for o in owners if len(_norm(o)) >= 3 and n in _norm(o)) >= 3:
            res = True
    except Exception:
        res = False
    cache[kw] = res
    try:
        save_json(_BRAND_CACHE, cache)
    except Exception:
        pass
    return res


def _tok_ok(tok: str, script: str) -> bool:
    if not tok:
        return True
    if tok in script or tok in GENERIC:
        return True
    for g in GENERIC:
        if tok.startswith(g) and _tok_ok(tok[len(g):], script):
            return True
        if tok.endswith(g) and _tok_ok(tok[:-len(g)], script):
            return True
    return False


def in_video(kw: str, script: str) -> bool:
    """검색어의 토큰이 전부 대본에 있거나 일반어(또는 일반어+대본 말 조합)여야 참.
    '삼성전기 주가'(삼성전기 대본에 있음) ✓, '기관순매수종목' ✓, '반도체 관세'(관세 없음) ✗, '코스닥150커버드콜' ✗"""
    if not script:
        return True
    toks = [x for x in re.split(r"[\s·]+", kw) if x]
    return all(_tok_ok(tok, script) for tok in toks)


def pick(d: str, entities: list[str] | None = None, script: str = "") -> dict:
    """제목·태그·해시태그용 선택. title: 오늘 내용과 직접 맞닿는 검색어 1개, tags: 일간 10 + 주간 5, hashtags: 2(대본에 있는 말만)."""
    t = load_json(day_dir(d) / "trends.json") or {}
    daily, weekly = t.get("daily") or [], t.get("weekly") or []
    entities = [e for e in (entities or []) if e]
    def intent(kw: str) -> bool:
        return any(w.lower() in kw.lower() for w in INTENT)

    def usable(kw: str) -> bool:
        return in_video(kw, script) and not _is_brand(kw)

    def titleable(kw: str) -> bool:
        return intent(kw) and not any(b in kw for b in TITLE_BLOCK) and " " in kw and len(kw) <= 12 and usable(kw)

    # 제목: 오늘 테마·종목과 맞닿고 우리가 실제로 답하는 검색어("삼성전자 주가", "외국인 순매수 종목")
    title_kw = next((x["kw"] for x in daily if titleable(x["kw"]) and any(e in x["kw"] for e in entities)), None)
    if not title_kw:
        title_kw = next((x["kw"] for x in daily if titleable(x["kw"]) and x["kw"].startswith(("코스피", "외국인", "국장"))), None)
    # 태그도 영상에 실제로 나오는 말만(남의 채널명·영상에 없는 종목/이슈 금지) — 일간에서 10, 주간에서 5
    tags = []
    for x in [y for y in daily if usable(y["kw"])][:10] + [y for y in weekly if usable(y["kw"])][:5]:
        if x["kw"] not in tags:
            tags.append(x["kw"])
    hashtags = []
    for x in daily:
        if not intent(x["kw"]) or any(b in x["kw"] for b in TITLE_BLOCK[:3]) or not usable(x["kw"]):
            continue
        h = "#" + _norm(x["kw"])
        if 3 <= len(h) <= 12 and h not in hashtags:
            hashtags.append(h)
        if len(hashtags) >= 2:
            break
    # 제목 교체 후보(전날 쓴 검색어 회피용)도 같은 기준
    alts = [x["kw"] for x in daily if titleable(x["kw"]) and x["kw"] != title_kw][:5]
    return {"title": title_kw, "tags": tags, "hashtags": hashtags, "alts": alts}


if __name__ == "__main__":
    dd = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    main(dd, sys.argv[2].split(",") if len(sys.argv) > 2 else [])
