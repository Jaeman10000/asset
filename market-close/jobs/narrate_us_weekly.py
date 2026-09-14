# -*- coding: utf-8 -*-
"""미국 주간 결산(일요일 12:00 KST) 대본 + Threads — build_us_weekly(w, news).

입력
  w    : data/weekly_us/<build>/computed_us_weekly.json (공유 스키마. _meta가 있으면 결측 세션·휴장 이름에 쓴다)
  news : data/weekly_us/<build>/news.json — {"events": [...], "releases": [...]} 또는 이벤트 리스트. 필드 이름은 넓게 받는다.
         event   : d|date(현지 날짜) · title · what|fact_ko(사실 문장) · sources[{outlet}] · market_link · confidence(high/medium/low)
                   · kind(geopolitics/politics/trade/policy/company/earnings/data/rates/fx/oil) · importance · assets
                   · actual_vs_expected('PPI 전월비 0.4% (예상 0.4%) / 전년비 5.4% (예상 5.3%) / 근원 …' → 지표 결과로 파싱)
         release : name_ko · d|date · actual · expected|consensus|forecast|estimate · unit(기본 %) · basis('전년 대비' 등) · sources
출력 {"scenes":[uw0..uw6 {id,min,tts,sub}], "title", "threads", "threads_reply", "hook_parts":[훅 숫자, 훅 질문],
      + "variants"(슬롯별 고른 변형 번호), "complete", "missing", "hook", "checks", "total_chars", "est_sec"}
      기사 없는 주는 uw4를 빼고 uw3의 질문이 uw5로 바로 잇는다. 금요일 세션이 아직 없으면 uw1이 그 사실을 말하고 제목 날짜도 목요일까지.
길이: 장면별 한도(SCENE_CAP) + 전체 TOTAL_CAP(약 170초) — 넘으면 우선순위 낮은 문장부터 뺀다(0=필수).
지난주 파일: data/weekly_us/<이전 빌드>/narration_us_weekly.json (--save 로 이번 주 것을 남긴다).

말투(JJ 2026-09-13): 영상 대본(uw0~uw6)·제목·유튜브 설명은 합니다체, **Threads 본문·답글만 반말**이다.
  유튜브는 보러 온 사람이고 쓰레드 피드는 지나가는 사람이다. 쓰레드는 마지막 한 줄을 독자에게 던지는 질문으로 닫는다.

원칙(JJ): 합니다체, 묻고 답하는 사슬(첫 화면 질문을 음성도 말함, 섹션 꼬리표 없음), 장면당 숫자 5개 이하, 괄호 없이 쉼표,
원인·연결은 기사 근거가 있을 때만 '겹쳤습니다/볼 수 있습니다'로, 확신어(때문·이유·덕분·탓·영향으로·나오자·힘입어) 금지,
정치·전쟁은 날짜와 출처를 붙인 사실만, 종목·매매 권유 없음. 문장 슬롯마다 변형 3개 이상 — ISO 주차로 고르고 지난주 파일과 겹치면 건너뛴다.
평일·토요일 대본의 고정 문장은 다시 쓰지 않는다(자체 검사 reuse_hits).

Run:  python narrate_us_weekly.py [build_date=20260913] [--save]
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
import zlib
from datetime import date, timedelta

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
JOBS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(JOBS)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from checks import forbidden  # noqa: E402

DATA = os.path.join(ROOT, "data")
OUT_NAME = "narration_us_weekly.json"
SIGN_OFF = "누가샀나 미국 주간 결산이었습니다. 평일엔 매일 오후 4시 30분에 국장 마감이 올라옵니다."
TAG = "#미장"
YT = "{YT}"
MAX_FIGS = 5
CERTAINTY = ["때문", "이유", "덕분", "탓", "영향으로", "나오자", "힘입어"]
WD = "월화수목금토일"
HOLIDAY_KO = {"labor day": "노동절", "thanksgiving": "추수감사절", "memorial day": "메모리얼 데이", "juneteenth": "준틴스",
              "independence day": "독립기념일", "good friday": "성금요일", "christmas": "성탄절", "new year": "새해 첫날",
              "martin luther king": "마틴 루서 킹 데이", "presidents": "대통령의 날", "washington": "대통령의 날"}
US_HOLIDAYS = {"2026-09-07": "노동절", "2026-11-26": "추수감사절", "2026-12-25": "성탄절", "2027-01-01": "새해 첫날",
               "2027-01-18": "마틴 루서 킹 데이", "2027-02-15": "대통령의 날", "2027-03-26": "성금요일", "2027-05-31": "메모리얼 데이",
               "2027-06-18": "준틴스", "2027-07-05": "독립기념일", "2027-09-06": "노동절"}
KO_COUNT = {0: "한 곳도", 1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열", 11: "열한", 12: "열두"}
ND = {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새"}


# ── 한국어 조사 ──
_DIGIT_BAT = {"0": True, "1": True, "2": False, "3": True, "4": False, "5": False, "6": True, "7": True, "8": True, "9": False}


def _last(w: str) -> str:
    w = re.sub(r"[\s.,!?·'\"’”)\]]+$", "", w or "")
    return w[-1:]


def bat(w: str) -> bool:
    """마지막 소리 받침 여부. %(퍼센트)·%포인트는 받침 없음, 숫자는 읽는 소리, 로마자는 L·M·N·R(엘·엠·엔·알)만 받침."""
    w = (w or "").strip()
    if w.endswith("%") or w.endswith("포인트"):
        return False
    ch = _last(w)
    if ch.isdigit():
        return _DIGIT_BAT[ch]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch.upper() in "LMNR"


def _rieul(w: str) -> bool:
    ch = _last(w)
    if ch.isdigit():
        return ch in "178"
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 == 8
    return ch.upper() in "LR"


def eun(w): return w + ("은" if bat(w) else "는")
def i_ga(w): return w + ("이" if bat(w) else "가")
def eul(w): return w + ("을" if bat(w) else "를")
def wa(w): return w + ("과" if bat(w) else "와")
def ro(w): return w + ("으로" if bat(w) and not _rieul(w) else "로")
def ieot(w): return w + ("이었" if bat(w) else "였")


def _jong(ch: str) -> int:
    return (ord(ch) - 0xAC00) % 28 if "가" <= ch <= "힣" else -1


# ── 숫자 말하기 ──
def pct(v: float) -> str:
    a = abs(v or 0.0)
    if a >= 10:
        return f"{a:.0f}%"
    s = f"{a:.1f}"
    return (f"{a:.2f}" if s == "0.0" else s) + "%"


def pp(bp: float) -> str:
    """bp → '0.17%포인트' (말할 땐 %포인트가 bp보다 자연스럽다)"""
    s = f"{abs(bp) / 100:.2f}".rstrip("0").rstrip(".")
    return f"{s}%포인트"


def ylv(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") + "%"


def usd(v: float) -> str:
    return f"{v:,.0f}달러"


def won_lv(v: float) -> str:
    return f"{v:,.0f}원"


_FIG_SKIP = re.compile(r"\d+\s?년물|S&P\s?500|\d+\s?(?:년|월|일|시|분)(?![가-힣]*포인트)|아이폰\s?\d+")
_FIG = re.compile(r"\d[\d,]*(?:\.\d+)?")


def count_figs(text: str) -> int:
    return len(_FIG.findall(_FIG_SKIP.sub(" ", text or "")))


def _sents(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", (text or "").strip()) if s]


def _mask(s: str) -> str:
    return " ".join(re.sub(r"\d[\d,.]*", "N", s).split())


# ── 날짜 ──
def iso(s) -> str | None:
    if s is None:
        return None
    m = re.match(r"^\s*(\d{4})-?(\d{2})-?(\d{2})", str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _d(s: str) -> date:
    return date(int(s[:4]), int(s[5:7]), int(s[8:10]))


def wd(s: str) -> str:
    return WD[_d(s).weekday()] + "요일"


def dd(s: str) -> str:
    return f"{_d(s).day}일"


def md(s: str) -> str:
    x = _d(s)
    return f"{x.month}/{x.day}"


# ── 시계열 요약 ──
def ser(x: dict | None) -> dict | None:
    """{prev_close, days[{d,close,pct,chg_bp}], week_pct, week_chg_bp} → 말하기에 필요한 값. 값 없는 날은 뺀다."""
    if not x:
        return None
    prev = x.get("prev_close")
    days = []
    for r in x.get("days") or []:
        if r and r.get("close") is not None and iso(r.get("d")):
            days.append({"d": iso(r["d"]), "close": float(r["close"]), "pct": r.get("pct"), "bp": r.get("chg_bp")})
    days.sort(key=lambda r: r["d"])
    if not days:
        return None
    lc = prev
    for r in days:
        if r["pct"] is None and lc:
            r["pct"] = (r["close"] / lc - 1) * 100
        if r["bp"] is None and lc is not None:
            r["bp"] = round((r["close"] - lc) * 100)
        lc = r["close"]
    last = days[-1]["close"]
    wp = x.get("week_pct")
    if wp is None and prev:
        wp = (last / prev - 1) * 100
    wbp = x.get("week_chg_bp")
    if wbp is None and prev is not None:
        wbp = round((last - prev) * 100)
    signs = [(1 if (r["pct"] or 0) > 0 else -1 if (r["pct"] or 0) < 0 else 0) for r in days]
    return {"name": x.get("name_ko") or "", "prev": prev, "last": last, "wp": wp or 0.0, "wbp": wbp or 0, "days": days,
            "signs": signs, "n": len(days), "big": max(days, key=lambda r: abs(r["pct"] or 0)),
            "bigbp": max(days, key=lambda r: abs(r["bp"] or 0))}


def cross(prev: float | None, last: float | None, step: float) -> float | None:
    """prev→last 사이에 step 배수 선을 넘었으면 그 선(오르면 가장 높은 선, 내리면 가장 낮은 선)."""
    if prev is None or last is None:
        return None
    lo, hi = sorted((prev, last))
    k = int(hi // step) if last > prev else int(lo // step) + 1
    L = k * step
    if last > prev and prev < L <= last:
        return L
    if last < prev and last < L <= prev:
        return L
    return None


# ── 뉴스 정리 ──
GEO_RE = re.compile(r"전쟁|공습|공격|미사일|드론|휴전|반군|후티|이란|이스라엘|하마스|헤즈볼라|러시아|우크라|중동|호르무즈|사우디|OPEC|제재|분쟁|교전|확전")
POL_RE = re.compile(r"트럼프|백악관|대통령|의회|상원|하원|셧다운|관세|행정명령|대선|선거|국무장관|재무장관|재무부|연준 의장|파월")
CO_RE = re.compile(r"실적|매출|공개|출시|인수|합병|가이던스|계약|수주|ADR|상장")
DATA_RE = re.compile(r"CPI|PPI|소비자물가|생산자물가|고용|실업|소매판매|GDP|PCE|ISM|PMI")
KR_RE = re.compile(r"코스피|코스닥|국고채|기타법인|네 마녀|원·달러|자사주")
US_RE = re.compile(r"미국|미 |美|뉴욕|나스닥|S&P|다우|연준|월가|현지시간|WTI|브렌트|필라델피아|애플|엔비디아|ADR")
OIL_RE = re.compile(r"유가|원유|석유|정유|브렌트|WTI|아람코|OPEC|호르무즈")
RATE_RE = re.compile(r"금리|국채|10년물")


def _first(d: dict, keys) -> object:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


OUTLET_KO = {"reuters": "로이터", "bloomberg": "블룸버그", "associated press": "AP", "ap news": "AP", "afp": "AFP", "yahoo finance": "야후파이낸스",
             "investopedia": "인베스토피디아", "fortune": "포춘", "forbes": "포브스", "euronews": "유로뉴스", "al jazeera": "알자지라",
             "cbs": "CBS", "cnbc": "CNBC", "cnn": "CNN", "motley fool": "모틀리풀", "investing.com": "인베스팅닷컴", "the national": "더내셔널",
             "times of israel": "타임스 오브 이스라엘", "wall street journal": "월스트리트저널", "wsj": "월스트리트저널", "new york times": "뉴욕타임스",
             "financial times": "파이낸셜타임스", "axios": "액시오스", "politico": "폴리티코", "marketwatch": "마켓워치", "barron": "배런스"}
WIRE = ("로이터", "블룸버그", "AP", "AFP")


def _outlet_ko(n: str) -> str:
    low = n.lower()
    return next((v for k, v in OUTLET_KO.items() if k in low), n)


def _outlets(e: dict) -> list[str]:
    """말하기 좋은 순서: 통신사(로이터·블룸버그·AP·AFP) → 한글 매체 → 한글로 옮길 수 있는 외신 → 나머지."""
    out, native = [], set()
    for s in e.get("sources") or e.get("source") or []:
        n0 = (s.get("outlet") or s.get("source") or s.get("name")) if isinstance(s, dict) else str(s)
        n0 = re.sub(r"\s?\([^)]*\)", "", n0 or "").strip()
        n = _outlet_ko(n0)
        if n and n not in out:
            out.append(n)
            if re.search("[가-힣]", n0):
                native.add(n)
    return sorted(out, key=lambda n: (n not in WIRE, n not in native, not re.search("[가-힣]", n), out.index(n)))


def _conf(v) -> str:
    if isinstance(v, (int, float)):
        return "high" if v >= 0.7 else "medium" if v >= 0.4 else "low"
    return str(v or "").strip().lower()


def _ev_date(e: dict, title: str, fact: str, year: int) -> str | None:
    d0 = iso(_first(e, ("date_et", "date_us", "d_us", "date", "d")))
    m = re.search(r"\((\d{1,2})/(\d{1,2})\)\s*$", title or "")          # 제목 끝 '(9/9)' = 현지 날짜 표시
    if m:
        return f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})일\s?\(현지시간\)", fact or "")
    if m and d0:
        return f"{d0[:8]}{int(m.group(1)):02d}"
    return d0


def norm_news(news, w: dict) -> dict:
    ev_raw, rel_raw = [], []
    if isinstance(news, list):
        ev_raw += news
    elif isinstance(news, dict):
        for k in ("events", "items", "news"):
            if isinstance(news.get(k), list):
                ev_raw += news[k]
        for k in ("releases", "data", "data_results", "macro", "indicators"):
            if isinstance(news.get(k), list):
                rel_raw += news[k]
    if isinstance(w.get("news"), list):
        ev_raw += w["news"]
    year = int(str(w.get("week_start") or "2026")[:4])
    events, releases = [], []
    for e in ev_raw + rel_raw:
        if not isinstance(e, dict):
            continue
        conf = _conf(e.get("confidence"))
        if e.get("actual") is not None:
            name = str(_first(e, ("name_ko", "name", "event_ko", "what", "title")) or "")
            releases.append({"name": re.sub(r"\s?\([^)]*\)", "", name).strip(), "d": iso(_first(e, ("date_et", "date", "d"))),
                             "actual": e.get("actual"), "expected": _first(e, ("expected", "consensus", "forecast", "estimate")),
                             "unit": e.get("unit") or "%", "basis": e.get("basis") or e.get("measure") or "", "core": bool(e.get("core")),
                             "outlets": _outlets(e), "conf": conf or "high", "title": ""})
            continue
        title = str(_first(e, ("title", "title_ko", "event_ko", "headline")) or "")
        fact = str(_first(e, ("fact_ko", "spoken_ko", "line_ko", "what", "summary_ko", "summary", "text")) or "")
        kind = " ".join(e.get("tags") or []) if isinstance(e.get("tags"), list) else str(_first(e, ("kind", "category", "type")) or "")
        assets = [str(a) for a in e.get("assets") or []]
        blob = f"{title} {fact} {kind} {' '.join(assets)}"
        if KR_RE.search(title) and not US_RE.search(title):
            continue                                           # 국장 이야기는 미국 주간에서 뺀다
        d0 = _ev_date(e, title, fact, year)
        if e.get("actual_vs_expected") and conf in ("high", "medium"):
            releases += parse_ave(e, d0, conf)
        kl = kind.lower()
        geo = bool(GEO_RE.search(title) or re.search(r"geo|war", kl) or (kl == "oil" and GEO_RE.search(blob)))
        pol = bool(re.search(r"polit|trade|tariff", kl) or POL_RE.search(title))
        prio = 0 if (geo or pol) else 1 if re.search(r"policy", kl) else 2 if (re.search(r"company|earn|corp", kl) or CO_RE.search(title)) \
            else 3 if (kl == "data" or DATA_RE.search(title)) else 4
        events.append({"title": title, "fact": fact, "d": d0, "conf": conf, "prio": prio, "imp": float(e.get("importance") or 0),
                       "cluster": "geo" if geo else "pol" if pol else "co" if prio == 2 else "other", "assets": assets,
                       "politics": pol and not geo, "outlets": _outlets(e), "link": str(e.get("market_link") or ""), "blob": blob})
    return {"events": events, "releases": releases}


REL_NAME = [(r"PPI|생산자물가", "생산자물가"), (r"CPI|소비자물가", "소비자물가"), (r"PCE|개인소비지출", "개인소비지출 물가"), (r"소매판매", "소매판매"),
            (r"GDP", "GDP")]


def parse_ave(e: dict, d0: str | None, conf: str) -> list[dict]:
    """'PPI 전월비 0.4% (예상 0.4%) / 전년비 5.4% (예상 5.3%) / 근원 전월비 0.2% (예상 0.3%)' → 지표 결과 목록. %가 아닌 지표는 건너뛴다."""
    ave, title = str(e.get("actual_vs_expected") or ""), str(e.get("title") or "")
    base = next((nm for rx, nm in REL_NAME if re.search(rx, title) or re.search(rx, ave[:30])), None)
    if not base:
        return []
    m = re.search(r"(\d{1,2})월", title)
    mo = f"{m.group(1)}월 " if m else ""
    title_basis = "전년" if re.search(r"전년", title) else "전월" if re.search(r"전월", title) else ""
    out = []
    for seg in re.split(r"\s*/\s*|\.\s+", ave):
        mm = re.search(r"(근원)?\s*(전월비|전년비|전월 대비|전년 대비)\s*([+-]?\d+(?:\.\d+)?)%\s*\((?:예상|컨센서스|추정치?)\s*(부합|[+-]?\d+(?:\.\d+)?)", seg)
        if not mm:
            continue
        core = bool(mm.group(1)) or seg.strip().startswith("근원")
        act = float(mm.group(3))
        exp = act if mm.group(4) == "부합" else float(mm.group(4))
        out.append({"name": f"{mo}{'근원 ' if core else ''}{base}", "base": base, "core": core, "basis": "전년 대비" if "전년" in mm.group(2) else "전월 대비",
                    "actual": act, "expected": exp, "unit": "%", "d": d0, "outlets": _outlets(e), "conf": conf, "title": title,
                    "headline_pick": (not core) and bool(title_basis) and title_basis in mm.group(2)})
    return out


TIME_RE = re.compile(r"연휴|주말|지난|전날|다음 날|이튿날|\d{1,2}일")


def _cuts(s: str) -> list[tuple[int, str]]:
    """앞 절에서 끊을 수 있는 자리 → (위치, 끊은 문장). ㅆ받침+고 / '…해' / '…하며' / '…돼'."""
    out = []
    for m in re.finditer(r"([가-힣])(고|며)?,?\s", s):
        ch, tail = m.group(1), m.group(2)
        if tail == "고" and _jong(ch) == 20:
            out.append((m.start(), s[:m.start() + 1] + "습니다."))
        elif tail is None and ch == "해" and m.start() > 0:
            out.append((m.start(), s[:m.start()] + "했습니다."))
        elif tail == "며" and ch == "하":
            out.append((m.start(), s[:m.start()] + "했습니다."))
        elif tail is None and ch == "돼" and m.start() > 0:
            out.append((m.start(), s[:m.start()] + "됐습니다."))
    return out


def fact_outlet(fact: str, spoken: str) -> str:
    """사실 문장 원문에서 읽을 절 바로 뒤에 붙은 출처 괄호('…장악했고(유로뉴스)')가 있으면 그 매체."""
    s = _sents(fact)[0] if _sents(fact) else ""
    head = re.sub(r"(습니다\.|했습니다\.|됐습니다\.)$", "", spoken)[:12]
    i = s.find(head[:6]) if head else -1
    for m in re.finditer(r"\(([^)]{2,20})\)", s[max(i, 0):max(i, 0) + len(spoken) + 15]):
        t = m.group(1).strip()
        if len(t) <= 14 and not re.search(r"\d|현지|%|달러|원|종합|기준|추정|예상|전년|전월|잠정|장중|오전|오후|포함", t):
            return _outlet_ko(re.split(r"[·,]", t)[0].strip())
    return ""


def spoken_fact(fact: str, max_figs: int = 2, max_len: int = 58) -> str | None:
    """기사 사실 문장 → 읽는 문장: 첫 문장, 괄호·따옴표 제거, 문장 속 'N일 (N시)' 제거(앞에 날짜를 붙이므로),
    '가·나·다 등의' 같은 지명 나열 제거, 길거나 숫자가 많으면 첫 절까지."""
    s = _sents(fact)[0] if _sents(fact) else ""
    s = re.sub(r"\s?\([^)]*\)", "", s)
    s = re.sub(r"['\"‘’“”]", "", s)
    s = re.sub(r"(?<!월 )(?<!월)(?<![\d])\d{1,2}일\s(?:\d{1,2}시\s)?", "", s)
    s = re.sub(r"\s[가-힣A-Za-z]+(?:·[가-힣A-Za-z]+){2,}\s?등의?(?=\s)", "", s)
    s = s.replace("폭등", "급등").replace("폭락", "급락")
    s = " ".join(s.split())
    if not s.endswith("다."):
        return None
    if len(s) > max_len or count_figs(s) > max_figs:
        cut = next((c for _, c in _cuts(s) if len(c) >= 18), None)
        if cut:
            s = cut
    if count_figs(s) > max_figs or len(s) > 90 or forbidden.find(s) or any(c in s for c in CERTAINTY):
        return None
    return s


def reported(s: str) -> str | None:
    """'…공격했습니다.' → '…공격했다는' (ㅆ받침 과거형만). 이미 '밝혔습니다/전했습니다' 같은 전언이면 None('밝혔다는 보도' 방지)."""
    if re.search(r"(다고|라고)\s?[가-힣]+습니다\.$|(밝혔|전했|말했|주장했|보고했|발표했)습니다\.$", s):
        return None
    m = re.match(r"^(.*[가-힣])습니다\.$", s)
    if m and _jong(m.group(1)[-1]) == 20:
        return m.group(1) + "다는"
    return None


# ── 변형 고르기: ISO 주차 + 지난주 파일 피하기 ──
class Pick:
    def __init__(self, build_date: str, prev: dict | None):
        y, wk, _ = date(int(build_date[:4]), int(build_date[4:6]), int(build_date[6:8])).isocalendar()
        self.base = y * 53 + wk
        self.prev_v = (prev or {}).get("variants") or {}
        texts = [s.get("tts", "") for s in (prev or {}).get("scenes") or []] + [(prev or {}).get("title", "")] + \
                ((prev or {}).get("threads", "") or "").split("\n")
        self.prev_m = {_mask(x) for t in texts for x in _sents(t) if x}
        self.used: dict[str, int] = {}
        self.sizes: dict[str, int] = {}

    def __call__(self, slot: str, bank: list, ok=None, **kw):
        """ok(variant) → False 인 변형(필요한 값이 없는 형식)은 건너뛴다. 뱅크 크기는 선언된 그대로 기록."""
        n = len(bank)
        self.sizes[slot] = n
        start = (self.base + zlib.crc32(slot.encode("utf-8"))) % n
        cands = []
        for k in range(n):
            i = (start + k) % n
            v = bank[i]
            if ok and not ok(v):
                continue
            t = v.format(**kw) if isinstance(v, str) else tuple(x.format(**kw) for x in v)
            cands.append((i, t))
        if not cands:
            return self.__call__(slot, bank, **kw)
        for i, t in cands:
            txt = t if isinstance(t, str) else t[0]
            if self.prev_v.get(slot) == i or any(_mask(x) in self.prev_m for x in _sents(txt)):
                continue
            self.used[slot] = i
            return t
        i, t = next(((i, t) for i, t in cands if self.prev_v.get(slot) != i), cands[0])
        self.used[slot] = i
        return t


SCENE_CAP = {"uw0": 120, "uw1": 215, "uw2": 235, "uw3": 270, "uw4": 210, "uw5": 190, "uw6": 250}
TOTAL_CAP = 1130          # 약 6.6자/초(인준 +20%) → 약 170초. 쇼츠 한도 180초 안.


def assemble_all(sp: dict[str, list]) -> dict[str, list]:
    """sp = {장면: [(우선순위 0=필수, 문장[, 표지])]} 말하는 순서대로.
    ① 장면마다 길이·숫자(5개) 한도를 넘으면 우선순위 큰 것부터 ② 전체 길이가 TOTAL_CAP을 넘으면 전 장면에서 우선순위 큰·긴 것부터 뺀다."""
    keep = {k: [p for p in v if p[1]] for k, v in sp.items()}

    def txt(k):
        return " ".join(p[1] for p in keep[k])
    for k in keep:
        while len(txt(k)) > SCENE_CAP.get(k, 240) or count_figs(txt(k)) > MAX_FIGS:
            opt = [p for p in keep[k] if p[0] > 0]
            if not opt:
                break
            if count_figs(txt(k)) > MAX_FIGS and len(txt(k)) <= SCENE_CAP.get(k, 240):
                opt = [p for p in opt if count_figs(p[1])] or opt
            keep[k].remove(max(opt, key=lambda p: (p[0], keep[k].index(p))))
    while sum(len(txt(k)) for k in keep) > TOTAL_CAP:
        opt = [(p[0], len(p[1]), k, p) for k in keep for p in keep[k] if p[0] > 0]
        if not opt:
            break
        _, _, k, p = max(opt, key=lambda x: (x[0], x[1]))
        keep[k].remove(p)
    return keep


# ── 주간 맥락 ──
IDX_NAME = {"IXIC": "나스닥", "SPX": "S&P500", "DJI": "다우", "SOX": "반도체지수", "VIX": "VIX"}
V_A, V_B, V_C = ("내렸", "올랐"), ("빠졌", "뛰었"), ("밀렸", "상승했")
V_RISE, HL = ("내려", "올라"), ("낮", "높")


def _up(v: float) -> int:
    return 1 if (v or 0) > 0 else 0


def _hol_ko(name: str) -> str:
    n = (name or "").lower()
    return next((v for k, v in HOLIDAY_KO.items() if k in n), name or "휴장")


def context(w: dict) -> dict:
    S = {}
    for grp in ("idx", "rates", "fx", "commod"):
        for k, x in (w.get(grp) or {}).items():
            s = ser(x)
            if s:
                S[k] = s
    sessions = sorted({iso(x) for x in (w.get("sessions") or []) if iso(x)}) or sorted({r["d"] for s in S.values() for r in s["days"]})
    meta = w.get("_meta") or {}
    ws, we = iso(w.get("week_start")) or sessions[0], iso(w.get("week_end")) or sessions[-1]
    mon = _d(ws) - timedelta(days=_d(ws).weekday())
    hol = {}
    for h in meta.get("holidays") or []:
        d0 = iso(h.get("d") or h.get("date")) if isinstance(h, dict) else iso(h)
        if d0:
            hol[d0] = _hol_ko(h.get("name", "")) if isinstance(h, dict) else US_HOLIDAYS.get(d0, "휴장")
    for d0, nm in US_HOLIDAYS.items():
        if mon <= _d(d0) <= _d(we):
            hol.setdefault(d0, nm)
    hol = {d0: nm for d0, nm in hol.items() if mon <= _d(d0) <= _d(we)}
    exp, t = [], _d(ws)
    while t <= _d(we):
        if t.weekday() < 5 and t.isoformat() not in hol:
            exp.append(t.isoformat())
        t += timedelta(days=1)
    miss = sorted({d0 for d0 in exp if d0 not in sessions} |
                  {iso(m.get("d") if isinstance(m, dict) else m) for m in meta.get("missing_sessions") or [] if iso(m.get("d") if isinstance(m, dict) else m)})
    sectors = sorted([x for x in w.get("sectors") or [] if x and x.get("week_pct") is not None], key=lambda x: -x["week_pct"])
    megas = sorted([x for x in w.get("megacaps") or [] if x and x.get("week_pct") is not None], key=lambda x: -x["week_pct"])
    return {"S": S, "sessions": sessions, "ws": ws, "we": we, "hol": hol, "missing": miss, "complete": not miss,
            "sectors": sectors, "megas": megas, "cal": w.get("calendar_next") or [], "build": w.get("build_date") or ""}


def runs(signs: list[int]) -> list[tuple[int, int, int]]:
    out = []
    for i, s in enumerate(signs):
        if out and out[-1][0] == s:
            out[-1] = (s, out[-1][1], i)
        else:
            out.append((s, i, i))
    return out


# ── uw0 훅: 이번 주 가장 두드러진 움직임(데이터로 고름) ──
def hook_cands(C: dict) -> list[dict]:
    S, out = C["S"], []
    for k, (sw, sd, wt) in {"IXIC": (2.0, 1.3, 1.15), "SPX": (1.6, 1.0, 1.0), "DJI": (1.6, 1.0, 0.8), "SOX": (4.0, 2.5, 1.1)}.items():
        s = S.get(k)
        if not s:
            continue
        same = s["n"] >= 3 and len(set(s["signs"])) == 1 and s["signs"][0] != 0
        out.append({"kind": "idx_week", "k": k, "score": (abs(s["wp"]) / sw + (0.35 if same else 0)) * wt, "same": same})
        if s["n"] >= 2:
            out.append({"kind": "idx_day", "k": k, "score": abs(s["big"]["pct"] or 0) / sd * wt * 0.9})
    if S.get("US10Y"):
        r = S["US10Y"]
        L = cross(r["prev"], r["last"], 0.5)
        out.append({"kind": "rate", "k": "US10Y", "score": abs(r["wbp"]) / 14 * 1.1 + (0.4 if L else 0), "L": L})
    if S.get("WTI"):
        o = S["WTI"]
        L = cross(o["prev"], o["last"], 10)
        out.append({"kind": "oil", "k": "WTI", "score": abs(o["wp"]) / 4.5 + ((0.6 if L == 100 else 0.3) if L else 0), "L": L})
    for k, sc, wt, step in (("GOLD", 2.2, 0.9, 500), ("DXY", 0.9, 0.9, None), ("USDJPY", 1.3, 0.9, None), ("USDKRW", 1.0, 1.0, 50)):
        s = S.get(k)
        if s:
            L = cross(s["prev"], s["last"], step) if step else None
            out.append({"kind": k.lower(), "k": k, "score": abs(s["wp"]) / sc * wt + (0.25 if L else 0), "L": L})
    if S.get("VIX"):
        v = S["VIX"]
        L = cross(v["prev"], v["last"], 10)
        out.append({"kind": "vix", "k": "VIX", "score": abs(v["wp"]) / 25 * 0.7 + (0.4 if L else 0), "L": L})
    if C["megas"]:
        m = max(C["megas"], key=lambda x: abs(x["week_pct"]))
        out.append({"kind": "mega", "k": m.get("ticker"), "score": abs(m["week_pct"]) / 8 * 0.8, "m": m})
    return sorted(out, key=lambda x: -x["score"])


Q_GEN = [("그 사이 미국 주식은 어땠을까요?", "그 사이 미국 주식은?"), ("같은 주, 뉴욕 증시는 어땠을까요?", "같은 주, 뉴욕 증시는?"),
         ("그럼 미국 주식의 한 주는 어땠을까요?", "미국 주식의 한 주는?")]
Q_IDX = {0: [("{nd} 동안 무슨 일이 있었을까요?", "{nd} 동안 무슨 일이?"), ("그 한 주는 어떻게 흘러갔을까요?", "그 한 주는 어떻게?"),
             ("어디서부터 밀리기 시작했을까요?", "어디서부터 밀렸나?")],
         1: [("{nd} 동안 무슨 일이 있었을까요?", "{nd} 동안 무슨 일이?"), ("그 한 주는 어떻게 흘러갔을까요?", "그 한 주는 어떻게?"),
             ("어디서부터 오르기 시작했을까요?", "어디서부터 올랐나?")]}
F_IDXW = ["{nm_eun} 이번 주 {p} {va}습니다.", "이번 주 {nm_i_ga} {p} {vb}습니다.", "한 주 동안 {nm_i_ga} {p} {vc}습니다."]
F_SAME = {0: ["문을 연 {nd} 내내 하루도 오르지 못했습니다.", "{nd} 연속으로 내림세였습니다.", "열린 날마다 빠졌습니다."],
          1: ["문을 연 {nd} 내내 하루도 내리지 않았습니다.", "{nd} 연속 오름세였습니다.", "열린 날마다 올랐습니다."]}
F_IDXD = ["{wd} 하루에만 {nm_i_ga} {p} {va}습니다.", "{wd}, {nm_i_ga} 하루 만에 {p} {vb}습니다.",
          "이번 주 {nm}의 가장 큰 하루는 {wd}였습니다. 하루 새 {p} {vc}습니다."]
F_RATE = ["미국 10년물 국채 금리가 한 주 만에 {pp} {vr} {lvl_ga} 됐습니다.", "이번 주 미국 10년물 금리는 {lvl}까지 {va}습니다. 지난주보다 {pp} {hl}습니다.",
          "미국 10년물 금리가 한 주 새 {pp} {vr}, {lvl}입니다."]
F_OIL_X = {1: ["국제유가 WTI가 이번 주 {p} 뛰며 배럴당 {L}달러를 넘었습니다.", "기름값이 한 주 만에 {p} 올라, WTI 기준 배럴당 {L}달러 선을 넘었습니다.",
               "WTI가 배럴당 {L}달러를 넘었습니다. 한 주에만 {p} 올랐습니다."],
           0: ["국제유가 WTI가 이번 주 {p} 내리며 배럴당 {L}달러 아래로 내려왔습니다.", "기름값이 한 주 만에 {p} 내려, WTI 기준 배럴당 {L}달러 밑으로 갔습니다.",
               "WTI가 배럴당 {L}달러 아래로 내려왔습니다. 한 주에만 {p} 내렸습니다."]}
F_OIL = ["국제유가 WTI가 이번 주 {p} {vr} 배럴당 {lvl_ga} 됐습니다.", "기름값이 한 주 만에 {p} {vb}습니다. WTI 기준 배럴당 {lvl}입니다.",
         "이번 주 WTI는 배럴당 {lvl}, 한 주 {p} {va}습니다."]
F_KRW = ["원·달러 환율이 한 주 만에 {won} {vr} {lvl_ga} 됐습니다.", "이번 주 원화 값이 크게 {vk}습니다. 원·달러 환율은 {lvl}로, {won} {va}습니다.",
         "원·달러 환율이 {lvl}로, 한 주 전보다 {won} {hl}습니다."]
F_JPY = ["엔화 값이 한 주 {p} {vk}습니다. 엔·달러 환율은 {lvl}입니다.", "이번 주 엔화가 {p} {vs}습니다.", "엔·달러 환율이 한 주 {p} {va}습니다."]
F_DXY = ["달러 인덱스가 한 주 {p} {va}습니다.", "주요 통화에 견준 달러 값이 이번 주 {p} {vb}습니다.", "이번 주 달러 인덱스는 {p} {vc}습니다."]
F_GOLD = ["금값이 한 주 {p} {va}습니다. 온스당 {lvl}입니다.", "이번 주 금값은 {p} {vb}습니다.", "금값이 온스당 {lvl}로, 한 주 {p} {vc}습니다."]
F_VIX = ["공포지수로 불리는 VIX가 이번 주 {p} {va}습니다.", "시장의 불안을 재는 VIX가 한 주 {p} {vb}습니다.", "이번 주 VIX, 이른바 공포지수는 {p} {vc}습니다."]
F_MEGA = ["{nm_i_ga} 이번 주 {p} {va}습니다. 대형주 {n} 개 가운데 가장 큰 움직임입니다.", "대형주 가운데 이번 주 가장 크게 움직인 건 {nm}입니다. 한 주 {p} {vc}습니다.",
          "이번 주 {nm_eun} {p} {vb}습니다. 대형주 {n} 개 중 가장 큰 폭입니다."]


def build_uw0(C: dict, P: Pick, h: dict) -> tuple[str, list[str]]:
    S, kind = C["S"], h["kind"]
    s = S.get(h["k"]) if h["k"] in S else None
    up = _up(s["wp"]) if s else _up(h.get("m", {}).get("week_pct", 0))
    kw = {"va": V_A[up], "vb": V_B[up], "vc": V_C[up], "vr": V_RISE[up], "hl": HL[up]}
    q = Q_GEN
    if kind == "idx_week":
        nm = IDX_NAME[h["k"]]
        kw.update(nm=nm, nm_eun=eun(nm), nm_i_ga=i_ga(nm), p=pct(s["wp"]), nd=ND.get(s["n"], f"{s['n']}일"))
        fact = P("uw0.idxw", F_IDXW, **kw)
        if h.get("same"):
            fact += " " + P(f"uw0.same{up}", F_SAME[up], **kw)
        q = [(a.format(**kw), b.format(**kw)) for a, b in Q_IDX[up]]
        line1 = f"{nm} 한 주 {pct(s['wp'])} {'상승' if up else '하락'}"
    elif kind == "idx_day":
        nm, b = IDX_NAME[h["k"]], s["big"]
        up = _up(b["pct"])
        kw.update(va=V_A[up], vb=V_B[up], vc=V_C[up], nm=nm, nm_i_ga=i_ga(nm), p=pct(b["pct"]), wd=wd(b["d"]))
        fact = P("uw0.idxd", F_IDXD, **kw)
        line1 = f"{nm} {wd(b['d'])} 하루 {pct(b['pct'])} {'상승' if up else '하락'}"
    elif kind == "rate":
        up = _up(s["wbp"])
        kw.update(va=V_A[up], vr=V_RISE[up], hl=HL[up], pp=pp(s["wbp"]), lvl=ylv(s["last"]), lvl_ga=i_ga(ylv(s["last"])))
        fact = P("uw0.rate", F_RATE, **kw)
        line1 = f"미 10년물 금리 {ylv(s['last'])}"
    elif kind == "oil":
        kw.update(p=pct(s["wp"]), lvl=usd(s["last"]), lvl_ga=i_ga(usd(s["last"])), L=f"{h['L']:.0f}" if h.get("L") else "")
        fact = P(f"uw0.oilx{up}", F_OIL_X[up], **kw) if h.get("L") else P("uw0.oil", F_OIL, **kw)
        line1 = f"유가 한 주 {pct(s['wp'])} {('급등' if up else '급락') if abs(s['wp']) >= 8 else ('상승' if up else '하락')}"
    elif kind == "usdkrw":
        chg = s["last"] - s["prev"]
        kw.update(won=f"{abs(chg):.0f}원", lvl=won_lv(s["last"]), lvl_ga=i_ga(won_lv(s["last"])), vk=("내렸", "올랐")[1 - up])
        fact = P("uw0.krw", F_KRW, **kw)
        line1 = f"원·달러 한 주 {abs(chg):.0f}원 {'상승' if up else '하락'}"
    elif kind == "usdjpy":
        kw.update(p=pct(s["wp"]), lvl=f"{s['last']:.0f}엔", vk=("올랐", "내렸")[up], vs=("강해졌", "약해졌")[up])
        fact = P("uw0.jpy", F_JPY, **kw)
        line1 = f"엔화 한 주 {pct(s['wp'])} {'약세' if up else '강세'}"
    elif kind == "dxy":
        kw.update(p=pct(s["wp"]))
        fact = P("uw0.dxy", F_DXY, **kw)
        line1 = f"달러 인덱스 한 주 {pct(s['wp'])} {'상승' if up else '하락'}"
    elif kind == "gold":
        kw.update(p=pct(s["wp"]), lvl=usd(s["last"]))
        fact = P("uw0.gold", F_GOLD, **kw)
        line1 = f"금값 한 주 {pct(s['wp'])} {'상승' if up else '하락'}"
    elif kind == "vix":
        kw.update(p=pct(s["wp"]))
        fact = P("uw0.vix", F_VIX, **kw)
        line1 = f"공포지수 한 주 {pct(s['wp'])} {'상승' if up else '하락'}"
    else:
        m = h["m"]
        nm = m.get("name_ko") or m.get("ticker")
        kw.update(nm=nm, nm_eun=eun(nm), nm_i_ga=i_ga(nm), p=pct(m["week_pct"]), n=KO_COUNT.get(len(C["megas"]), str(len(C["megas"]))))
        fact = P("uw0.mega", F_MEGA, **kw)
        line1 = f"{nm} 한 주 {pct(m['week_pct'])} {'상승' if up else '하락'}"
    q_tts, q_screen = P("uw0.q." + ("idx" if kind == "idx_week" else "gen"), q)
    return f"{fact} {q_tts}", [line1, q_screen]


# ── uw1 지수가 걸어온 길 ──
OPEN_MON = ["이번 주 미국 증시는 월요일 {hol}로 쉬고 화요일에 문을 열었습니다.", "{hol} 연휴를 보낸 미국 증시는 화요일부터 거래를 시작했습니다.",
            "월요일 {hol} 휴장이 끝나고, 미국 증시는 화요일에 다시 열렸습니다."]
OPEN_OTHER = ["이번 주 미국 증시는 {hwd} {hol}로 하루 쉬었습니다.", "{hwd}엔 {hol}로 미국 증시가 문을 닫았습니다.", "이번 주엔 {hwd} {hol} 휴장이 끼어 있었습니다."]
IX_ALL = {0: ["나스닥은 {first}부터 {last}까지 {nd} 내리 내렸고, 한 주 {p} 밀렸습니다.", "나스닥은 열린 {nd} 동안 하루도 오르지 못한 채 {p} 내렸습니다.",
              "나스닥은 {nd} 연속 내림세로, 한 주 동안 {p} 빠졌습니다."],
          1: ["나스닥은 {first}부터 {last}까지 {nd} 내리 올랐고, 한 주 {p} 상승했습니다.", "나스닥은 열린 {nd} 동안 하루도 내리지 않고 {p} 올랐습니다.",
              "나스닥은 {nd} 연속 오름세로, 한 주 동안 {p} 뛰었습니다."]}
IX_REV = ["나스닥은 {a}까지 {va}다가 {b}{bp} 방향을 바꿔, 한 주 {p} {vw}습니다.", "나스닥은 {a}까지 {va}다가 {b}{bp} 돌아섰고, 한 주로는 {p} {vw}습니다.",
          "나스닥은 초반 {a}까지 {va}다가, {b}{bp} 반대로 움직여 한 주 {p} {vw}습니다."]
IX_MIX = ["나스닥은 오르내림을 거듭하다 한 주 {p} {vw}습니다.", "나스닥은 등락을 주고받은 끝에, 한 주로는 {p} {vw}습니다.",
          "나스닥은 오르고 내리기를 반복한 끝에 한 주 {p} {vw}습니다."]
IX_FLAT = ["나스닥은 한 주 거의 제자리였습니다.", "나스닥은 한 주 동안 큰 변화 없이 마쳤습니다.", "나스닥의 한 주 등락은 거의 없었습니다."]
SD_SAME = ["S&P500은 {p1}, 다우는 {p2} {va}습니다.", "S&P500도 {p1}, 다우는 {p2} {vb}습니다.", "같은 기간 S&P500은 {p1}, 다우는 {p2} {vc}습니다."]
SD_DIFF = ["S&P500은 {p1} {v1}고, 다우는 {p2} {v2}습니다.", "S&P500은 {p1} {v1}지만, 다우는 {p2} {v2}습니다.",
           "같은 기간 S&P500은 {p1} {v1}고, 다우는 {p2} {v2}습니다."]
MOST = ["세 지수 가운데 {nm_i_ga} 가장 크게 {va}습니다.", "셋 중엔 {nm}의 움직임이 가장 컸습니다.", "가장 크게 움직인 건 {nm_ieot}습니다."]
SOX_REV = ["미국 반도체 대형주 지수는 달랐습니다. {a}까지 {va}다가 {b} 하루에 {p} {vb}습니다.",
           "반도체지수만 결이 달랐습니다. {a}까지 {va}다가, {b}에 {p} {vb}습니다.",
           "미국 반도체 대형주를 모은 반도체지수는 {a}까지 {va}다가, {b} 하루 새 {p} {vb}습니다."]
SOX_WEEK = ["미국 반도체 대형주 지수는 한 주 {p} {va}습니다.", "미국 반도체 대형주들의 지수, 반도체지수는 {p} {vb}습니다.",
            "미국 반도체 대형주를 모은 반도체지수는 한 주 {p} {vc}습니다."]
MISSING = ["{mwd} 장은 이 영상을 만들 때 아직 끝나지 않아, 숫자는 {lwd} 종가까지입니다.", "{mwd} 장은 아직 반영되지 않았습니다. 숫자는 {lwd} 종가 기준입니다.",
           "{mwd} 장 결과는 아직 들어오지 않아, {lwd} 종가까지로 셉니다."]
Q12 = ["주식이 {ving} 사이, 금리는 어땠을까요?", "그럼 같은 기간 금리는 어디로 갔을까요?", "이 사이 채권 금리는 어떻게 움직였을까요?"]


def _rev(s: dict) -> dict | None:
    """두 구간(앞 run → 뒤 run)으로 나뉘는 길이면 전환점 정보."""
    rs = [r for r in runs(s["signs"]) if r[0] != 0]
    if len(rs) != 2 or len(runs(s["signs"])) != 2:
        return None
    (s1, a0, a1), (s2, b0, b1) = rs
    days = s["days"]
    return {"a": wd(days[a1]["d"]), "b": wd(days[b0]["d"]), "last": b1 == b0 == len(days) - 1, "va": ("내리", "오르")[_up(s1)],
            "vb": V_A[_up(s2)], "bday": days[b0]}


def build_uw1(C: dict, P: Pick) -> list:
    S, parts = C["S"], []
    for d0, nm in sorted(C["hol"].items()):
        if _d(d0).weekday() == 0:
            parts.append((3, P("uw1.open.mon", OPEN_MON, hol=nm)))
        else:
            parts.append((3, P("uw1.open.other", OPEN_OTHER, hol=nm, hwd=wd(d0))))
        break
    ix = S.get("IXIC")
    if ix:
        up = _up(ix["wp"])
        kw = {"p": pct(ix["wp"]), "vw": V_A[up], "nd": ND.get(ix["n"], f"{ix['n']}일"), "first": wd(ix["days"][0]["d"]), "last": wd(ix["days"][-1]["d"])}
        rv = _rev(ix)
        if abs(ix["wp"]) < 0.2:
            parts.append((0, P("uw1.ix.flat", IX_FLAT)))
        elif ix["n"] >= 2 and len(set(ix["signs"])) == 1 and ix["signs"][0] != 0:
            parts.append((0, P(f"uw1.ix.all{up}", IX_ALL[up], **kw)))
        elif rv:
            parts.append((0, P("uw1.ix.rev", IX_REV, a=rv["a"], b=rv["b"], bp="에" if rv["last"] else "부터", va=rv["va"], **kw)))
        else:
            parts.append((0, P("uw1.ix.mix", IX_MIX, **kw)))
    sp, dj = S.get("SPX"), S.get("DJI")
    if sp and dj:
        u1, u2 = _up(sp["wp"]), _up(dj["wp"])
        if u1 == u2:
            parts.append((1, P("uw1.sd.same", SD_SAME, p1=pct(sp["wp"]), p2=pct(dj["wp"]), va=V_A[u1], vb=V_B[u1], vc=("밀렸", "올랐")[u1])))
        else:
            parts.append((1, P("uw1.sd.diff", SD_DIFF, p1=pct(sp["wp"]), p2=pct(dj["wp"]), v1=V_A[u1], v2=V_A[u2])))
        trio = [(k, S[k]["wp"]) for k in ("IXIC", "SPX", "DJI") if S.get(k)]
        top = max(trio, key=lambda x: abs(x[1]))
        rest = sorted([abs(v) for k, v in trio if k != top[0]])
        if top[0] != "IXIC" and rest and abs(top[1]) - rest[-1] >= 0.5:
            nm = IDX_NAME[top[0]]
            parts.append((3, P("uw1.most", MOST, nm=nm, nm_i_ga=i_ga(nm), nm_ieot=ieot(nm), va=V_B[_up(top[1])])))
    sx = S.get("SOX")
    if sx:
        rv = _rev(sx)
        div = ix and sx["signs"] != ix["signs"] and (abs(sx["big"]["pct"] or 0) >= 2 or abs(sx["wp"] - ix["wp"]) >= 1.5)
        if rv and rv["last"]:
            parts.append((2 if div else 3, P("uw1.sox.rev", SOX_REV, a=rv["a"], b=rv["b"], va=rv["va"], vb=rv["vb"], p=pct(rv["bday"]["pct"])), "sox"))
        else:
            u = _up(sx["wp"])
            parts.append((2 if div else 3, P("uw1.sox.week", SOX_WEEK, p=pct(sx["wp"]), va=V_A[u], vb=V_B[u], vc=("밀렸", "올랐")[u]), "sox"))
    if C["missing"] and C["sessions"]:
        mwd = "·".join(wd(d0) for d0 in C["missing"])
        parts.append((0, P("uw1.missing", MISSING, mwd=mwd, lwd=wd(C["sessions"][-1]))))
    ving = "머무는" if not ix or abs(ix["wp"]) < 0.2 else ("밀리는", "오르는")[_up(ix["wp"])]
    parts.append((0, P("uw1.q", Q12, ving=ving)))
    return parts


# ── uw2 금리 + 지표 결과(실제 vs 추정치) ──
VN = ("내린", "뛴")
R10 = {1: ["미국 10년물 국채 금리는 한 주 동안 {pp} 올라 {lvl_ga} 됐습니다.", "10년물 국채 금리는 한 주 만에 {pp} 뛰어 {lvl}까지 올랐습니다.",
           "채권 쪽에선 10년물 금리가 {pp} 올라, {lvl}로 마쳤습니다."],
       0: ["미국 10년물 국채 금리는 한 주 동안 {pp} 내려 {lvl_ga} 됐습니다.", "10년물 국채 금리는 한 주 만에 {pp} 내려 {lvl}까지 내려왔습니다.",
           "채권 쪽에선 10년물 금리가 {pp} 내려, {lvl}로 마쳤습니다."]}
R10_FLAT = ["10년물 국채 금리는 {lvl}로, 한 주 내내 거의 움직이지 않았습니다.", "10년물 금리는 {lvl} 언저리에서 한 주를 보냈습니다.",
            "채권 쪽 10년물 금리는 {lvl}로 큰 변화가 없었습니다."]
R10_HOOK = ["처음에 본 10년물 금리는 {bwd}에 가장 크게 움직였습니다. 하루에만 {bpp} {va}습니다.", "그 10년물 금리가 가장 크게 움직인 날은 {bwd_ieot}습니다. 하루 새 {bpp} {va}습니다.",
            "앞에서 본 10년물 금리, 한 주 중 가장 크게 {vn} 날은 {bwd_ieot}습니다."]
EXPL10 = ["10년물 금리는 전 세계 주식 값을 매길 때 잣대처럼 쓰이는 이자율입니다.",
          "금리는 돈의 값입니다. 안전한 국채 이자가 오르면 주식을 들고 있을 매력은 줄 수 있습니다.",
          "금리가 오르면 먼 미래 이익의 지금 가치가 작아져, 기술주엔 부담이 될 수 있습니다."]
BIG10 = ["특히 {bwd} 하루에만 {bpp} {vb}습니다.", "그중 {bwd}에 가장 크게 {vb}습니다.", "가장 크게 움직인 날은 {bwd_ieot}습니다."]
R2Y = ["기준금리 기대를 더 빨리 담는 2년물은 {pp} {va}습니다.", "연준 금리 기대에 더 민감한 2년물도 {pp} {va}습니다.",
       "단기 금리인 2년물은 {pp} {va}습니다."]
REL1 = ["{rwd}에 나온 {name_eun} {vp}, 추정치 {exp_eul} {cmp}습니다.", "{rwd} 발표된 {name_eun} {vp}, 시장이 점친 {exp}보다 {cmp2}습니다.",
        "{rwd}엔 {name_i_ga} {vp}, 추정치 {exp_eul} {cmp}습니다."]
REL1_EQ = ["{rwd}에 나온 {name_eun} {vp}, 시장 추정치와 같았습니다.", "{rwd} 발표된 {name_eun} {vp}, 시장 추정치 그대로였습니다.",
           "{rwd}엔 {name_i_ga} {vp}, 추정치와 같았습니다."]
REL1_NOEXP = ["{rwd} 발표된 {name_eun} {vpp}.", "{rwd}에 나온 {name_eun} {vpp}.", "{rwd}엔 {name_i_ga} {vpp}."]
REL2 = ["{rwd} {name}도 추정치를 {cmp}습니다.", "{rwd}에 나온 {name}도 시장 추정치를 {cmp}습니다.", "{rwd} {name} 역시 추정치를 {cmp}습니다."]
REL2_EQ = ["{rwd} {name_eun} 추정치와 같았습니다.", "{rwd}에 나온 {name_eun} 시장 추정치 그대로였습니다.", "{rwd} {name_eun} 추정치와 같은 숫자였습니다."]
REL2_CORE = ["다만 에너지·식품을 뺀 근원 물가는 추정치를 {cmp}습니다.", "그런데 근원 물가는 추정치를 {cmp}습니다.",
             "한편 변동이 큰 에너지·식품을 뺀 근원 물가는 추정치를 {cmp}습니다."]
REL2_CORE_SAME = ["에너지·식품을 뺀 근원 물가도 추정치를 {cmp}습니다.", "근원 물가 역시 추정치를 {cmp}습니다.", "변동이 큰 에너지·식품을 뺀 근원 물가도 추정치를 {cmp}습니다."]
LINK_REL = ["금리가 가장 크게 {vn} {bwd_eun} 이 발표와 겹쳤습니다.", "10년물 금리가 한 주 중 가장 크게 {vn} 날도 이 {bwd_ieot}습니다.",
            "금리가 가장 크게 움직인 날과 이 발표가 나온 날은 같은 {bwd_ieot}습니다."]
LINK_OILDAY = ["금리가 가장 크게 {vn} {bwd_eun} 유가가 크게 오른 날과 겹쳤습니다.", "{bwd}의 금리 오름세는 같은 날 유가 급등과 겹쳤습니다.",
               "10년물 금리가 가장 크게 {vn} {bwd}엔 기름값도 크게 올랐습니다."]
Q23 = ["그럼 달러와 기름값은 어땠을까요?", "이 사이 달러와 원화, 유가는 어디로 갔을까요?", "금리가 {vr2} 사이, 달러와 유가는 어땠을까요?"]
BASIS = {"1년 전보다": ("전년 대비", "전년비", "yoy", "y/y", "전년 동월 대비", "전년동월대비"), "한 달 전보다": ("전월 대비", "전월비", "mom", "m/m")}
REL_TIER = [(r"CPI|소비자물가", 0), (r"고용|비농업|실업률", 0), (r"PCE|개인소비지출", 1), (r"PPI|생산자물가", 1), (r"소매판매", 1), (r"GDP", 1)]


def _rel_tier(name: str) -> int:
    return next((t for rx, t in REL_TIER if re.search(rx, name)), 2)


def _num(v) -> str:
    return f"{abs(float(v)):g}"


def _rel_parts(r: dict) -> dict:
    unit = r["unit"] if r["unit"] not in (None, "") else "%"
    a = float(r["actual"])
    act = _num(a) + unit
    basis = next((k for k, vs in BASIS.items() if str(r["basis"]).strip().lower() in vs), "")
    if basis:
        vp, vpp = f"{basis} {act} {('내려', '올라')[a >= 0]}", f"{basis} {act} {('내렸', '올랐')[a >= 0]}습니다"
    else:
        act = ("-" if a < 0 else "") + act
        vp, vpp = ro(act), ieot(act) + "습니다"
    exp = r.get("expected")
    kw = {"rwd": wd(r["d"]) if r.get("d") else "이번 주", "name": r["name"], "name_eun": eun(r["name"]), "name_i_ga": i_ga(r["name"]),
          "vp": vp, "vpp": vpp}
    if exp is not None:
        e = float(exp)
        ex = ("-" if (e < 0 and not basis) else "") + _num(e) + unit
        kw.update(exp=ex, exp_eul=eul(ex), cmp=("밑돌았", "웃돌았")[a > e], cmp2=("낮았", "높았")[a > e], eq=abs(a - e) < 1e-9)
    return kw


def _surprise(r: dict) -> bool:
    return r.get("expected") is not None and abs(float(r["actual"]) - float(r["expected"])) > 1e-9


def week_releases(C: dict, N: dict) -> list[dict]:
    """[헤드라인, 두 번째] — 헤드라인 = 중요도(CPI·고용 > PPI·소매) → 제목이 짚은 기준 → 추정치와 다른 것. 두 번째 = 같은 발표의 근원(추정치와 다를 때) → 다른 발표."""
    lo, hi = _d(C["ws"]) - timedelta(days=3), _d(C["we"]) + timedelta(days=1)
    rs = [r for r in N["releases"] if r.get("d") and lo <= _d(r["d"]) <= hi and r["conf"] in ("high", "medium", "")]
    if not rs:
        return []
    heads = [r for r in rs if not r.get("core")] or rs
    head = sorted(heads, key=lambda r: (_rel_tier(r["name"]), not r.get("headline_pick"), not _surprise(r), r["d"]))[0]
    rest = [r for r in rs if r is not head]
    core = [r for r in rest if r.get("core") and r.get("base") == head.get("base") and r.get("d") == head.get("d") and _surprise(r)]
    other = sorted([r for r in rest if not r.get("core") and r.get("base") != head.get("base")], key=lambda r: (_rel_tier(r["name"]), r["d"]))
    return [head] + (core[:1] or other[:1])


def build_uw2(C: dict, N: dict, P: Pick, hook: dict) -> tuple[list, list[str]]:
    S, parts = C["S"], []
    r, r2 = S.get("US10Y"), S.get("US2Y")
    big = None
    if r:
        up = _up(r["wbp"])
        big = r["bigbp"]
        bu = _up(big["bp"] or 0)
        bkw = {"bwd": wd(big["d"]), "bwd_eun": eun(wd(big["d"])), "bwd_ieot": ieot(wd(big["d"])), "bpp": pp(big["bp"] or 0),
               "va": V_A[bu], "vb": V_B[bu], "vn": VN[bu]}
        if hook["kind"] == "rate":
            parts.append((0, P("uw2.r10.hook", R10_HOOK, **bkw)))
        elif abs(r["wbp"]) < 3:
            parts.append((0, P("uw2.r10.flat", R10_FLAT, lvl=ylv(r["last"]))))
        else:
            parts.append((0, P(f"uw2.r10.{up}", R10[up], pp=pp(r["wbp"]), lvl=ylv(r["last"]), lvl_ga=i_ga(ylv(r["last"])))))
        parts.append((1, P("uw2.expl", EXPL10)))
        if r2 and abs(r2["wbp"]) >= 5:
            u2 = _up(r2["wbp"])
            parts.append((2, P("uw2.r2y", R2Y, pp=pp(r2["wbp"]), va=V_A[u2])))
        if hook["kind"] != "rate" and abs(big["bp"] or 0) >= 8 and r["n"] >= 2:
            parts.append((3, P("uw2.big", BIG10, **bkw)))
    rels = week_releases(C, N)
    used_rel = []
    if rels:
        kw = _rel_parts(rels[0])
        if kw.get("exp") is None:
            parts.append((0, P("uw2.rel1.noexp", REL1_NOEXP, **kw)))
        else:
            parts.append((0, P("uw2.rel1.eq" if kw["eq"] else "uw2.rel1", REL1_EQ if kw["eq"] else REL1, **kw)))
        used_rel.append(rels[0]["name"])
        if r and big and rels[0].get("d") == big["d"] and abs(big["bp"] or 0) >= 5:
            parts.append((1, P("uw2.link.rel", LINK_REL, **bkw)))
        for r_ in rels[1:2]:
            k2 = _rel_parts(r_)
            if k2.get("exp") is None:
                continue
            if r_.get("core") and r_.get("base") == rels[0].get("base"):
                same = (not kw.get("eq")) and (k2["cmp"] == kw.get("cmp"))
                parts.append((2, P("uw2.core.same" if same else "uw2.core", REL2_CORE_SAME if same else REL2_CORE, **k2)))
            else:
                parts.append((3, P("uw2.rel2.eq" if k2["eq"] else "uw2.rel2", REL2_EQ if k2["eq"] else REL2, **k2)))
            used_rel.append(r_["name"])
    if r and big and "uw2.link.rel" not in P.used:
        wti = S.get("WTI")
        wday = next((x for x in (wti or {}).get("days", []) if x["d"] == big["d"]), None)
        ev_ok = any(e["d"] == big["d"] and OIL_RE.search(e["blob"]) and RATE_RE.search(e["blob"]) and e["conf"] in ("high", "medium")
                    for e in N["events"])
        if ev_ok and wday and (wday["pct"] or 0) >= 3 and (big["bp"] or 0) >= 5:
            parts.append((1, P("uw2.link.oil", LINK_OILDAY, **bkw)))
    vr2 = "머무는" if not r or abs(r["wbp"]) < 3 else ("내리는", "오르는")[_up(r["wbp"])]
    parts.append((0, P("uw2.q", Q23, vr2=vr2)))
    return parts, used_rel


# ── uw3 달러·엔·원·유가·금 — 한국 투자자에게 무슨 뜻인지 한 줄씩 ──
FX_NAME = {"DXY": "달러 인덱스", "USDKRW": "원·달러 환율", "USDJPY": "엔·달러 환율", "GOLD": "금값", "WTI": "유가"}
FX_SCALE = {"DXY": 0.8, "USDKRW": 0.9, "USDJPY": 1.2, "GOLD": 2.0, "WTI": 4.0}
FX_ORDER = ["DXY", "USDKRW", "USDJPY", "GOLD", "WTI"]
K2 = {0: ["원·달러 환율은 {won} 내린 {lvl}, 미국 주식의 원화 평가액은 그만큼 줄었습니다.",
          "원·달러 환율이 {won} 내려 {lvl_ga} 됐고, 원화로 따진 미국 주식 값은 작아졌습니다.",
          "원화가 강해져 환율은 {won} 내린 {lvl}, 미국 주식의 원화 환산 값은 줄었습니다."],
      1: ["원·달러 환율은 {won} 오른 {lvl}, 미국 주식의 원화 평가액은 그만큼 커졌습니다.",
          "원·달러 환율이 {won} 올라 {lvl_ga} 됐고, 새로 달러를 살 땐 원화가 더 듭니다.",
          "원화가 약해져 환율은 {won} 오른 {lvl}, 미국 주식의 원화 환산 값은 커졌습니다."]}
K1 = {0: ["원·달러 환율은 {won} 내렸고, 미국 주식의 원화 평가액은 그만큼 줄었습니다.",
          "원·달러 환율이 {won} 내려, 원화로 따진 미국 주식 값은 작아졌습니다.",
          "원화가 강해져 환율은 {won} 내렸고, 미국 주식의 원화 환산 값은 줄었습니다."],
      1: ["원·달러 환율은 {won} 올랐고, 미국 주식의 원화 평가액은 그만큼 커졌습니다.",
          "원·달러 환율이 {won} 올라, 새로 달러를 살 땐 원화가 더 듭니다.",
          "원화가 약해져 환율은 {won} 올랐고, 미국 주식의 원화 환산 값은 커졌습니다."]}
J1 = {0: ["엔화는 {p} 강해졌습니다. 엔·달러 환율이 내리면 엔화 강세라고 합니다.",
          "엔·달러 환율은 {p} 내렸습니다. 엔화 값이 올랐다는 뜻, 곧 엔화 강세입니다.",
          "엔화 값은 {p} 올랐습니다. 환율이 내려가는 이 움직임이 엔화 강세입니다."],
      1: ["엔화는 {p} 약해졌습니다. 엔·달러 환율이 오르면 엔화 약세라고 합니다.",
          "엔·달러 환율은 {p} 올랐습니다. 엔화 값이 내렸다는 뜻, 곧 엔화 약세입니다.",
          "엔화 값은 {p} 내렸습니다. 환율이 올라가는 이 움직임이 엔화 약세입니다."]}
J_MEAN = {0: ["엔화가 강하면 일본과 경쟁하는 한국 수출기업엔 숨통이 될 수 있습니다.", "엔화 강세는 일본 제품과 겨루는 한국 수출기업엔 부담을 덜어 줄 수 있습니다.",
              "엔화가 비싸지면 한국 수출품의 가격 경쟁력엔 도움이 될 수 있습니다."],
          1: ["엔화가 약하면 일본과 경쟁하는 한국 수출기업엔 부담이 될 수 있습니다.", "엔화 약세는 일본 제품과 겨루는 한국 수출기업엔 부담이 될 수 있습니다.",
              "엔화가 싸지면 한국 수출품의 가격 경쟁력엔 부담이 될 수 있습니다."]}
DX1 = {1: ["주요 통화에 견준 달러 값, 달러 인덱스는 {p} 올랐습니다. 달러가 강하면 신흥국 주식엔 부담이 될 수 있습니다.",
           "달러 인덱스, 유로·엔 같은 주요 통화에 견준 달러 값은 {p} 올랐습니다. 국장 외국인 수급엔 부담이 될 수 있습니다.",
           "달러의 힘을 재는 달러 인덱스는 {p} 올랐습니다. 외국인이 원화 자산을 덜 찾을 수 있는 숫자입니다."],
       0: ["주요 통화에 견준 달러 값, 달러 인덱스는 {p} 내렸습니다. 달러가 약하면 신흥국 주식엔 숨통이 될 수 있습니다.",
           "달러 인덱스, 유로·엔 같은 주요 통화에 견준 달러 값은 {p} 내렸습니다. 국장 외국인 수급엔 숨통이 될 수 있습니다.",
           "달러의 힘을 재는 달러 인덱스는 {p} 내렸습니다. 외국인이 원화 자산을 더 찾을 수 있는 숫자입니다."]}
DX_FLAT = ["주요 통화에 견준 달러 값, 달러 인덱스는 거의 제자리였습니다.", "달러 인덱스, 유로·엔 같은 주요 통화에 견준 달러 값은 거의 그대로였습니다.",
           "달러의 힘을 재는 달러 인덱스는 한 주 내내 비슷했습니다."]
GO_DOWN_RATE = ["금값은 {p} 내렸습니다. 이자가 없는 금은 금리가 뛸 땐 밀리기도 합니다.", "금값은 {p} 내렸는데, 이자 없는 금은 금리가 오를 때 약해지기도 합니다.",
                "금은 {p} 밀렸습니다. 금리가 오르는 주엔 이자 없는 금이 힘을 잃기도 합니다."]
GO_DOWN = ["금값은 {p} 내렸습니다. 불안할 때 찾는 금이 내렸다는 건 걱정이 줄었다는 뜻으로 읽히기도 합니다.",
           "금값은 {p} 내렸습니다. 안전한 곳을 찾는 돈이 줄었다는 뜻으로 읽히기도 합니다.",
           "금은 {p} 밀렸습니다. 불안을 비추는 금값이 내려, 걱정이 누그러졌다는 풀이도 나옵니다."]
GO_UP = ["금값은 {p} 올랐습니다. 불안할 때 찾는 자산이라 걱정이 커졌다는 뜻으로 읽히기도 합니다.",
         "금값은 {p} 올랐는데, 금은 시장의 걱정을 비추는 숫자로 읽힙니다.", "금은 {p} 뛰었습니다. 안전한 곳을 찾는 돈이 늘었다는 뜻으로 읽히기도 합니다."]
GO_KRW_SAME = {0: ["금값은 {p} 내렸습니다. 환율까지 내려, 원화로 따진 국내 금값은 더 크게 내렸습니다.",
                   "금은 {p} 밀렸습니다. 국내 금 시세는 국제 금값과 환율을 함께 따르는데, 이번 주엔 둘 다 내렸습니다.",
                   "금값은 {p} 내렸습니다. 원화로 산 금은 환율 하락까지 겹쳐 더 크게 밀렸습니다."],
               1: ["금값은 {p} 올랐습니다. 환율까지 올라, 원화로 따진 국내 금값은 더 크게 올랐습니다.",
                   "금은 {p} 뛰었습니다. 국내 금 시세는 국제 금값과 환율을 함께 따르는데, 이번 주엔 둘 다 올랐습니다.",
                   "금값은 {p} 올랐습니다. 원화로 산 금은 환율 상승까지 겹쳐 더 크게 올랐습니다."]}
GO_KRW_MIX = {0: ["금값은 {p} 내렸습니다. 다만 환율이 올라, 원화로 따진 국내 금값은 덜 내렸습니다.",
                  "금은 {p} 밀렸습니다. 국내 금 시세는 환율이 반대로 움직여 그보다 덜 빠졌습니다.",
                  "금값은 {p} 내렸는데, 원화로 산 금은 환율이 오른 만큼 덜 밀렸습니다."],
              1: ["금값은 {p} 올랐습니다. 다만 환율이 내려, 원화로 따진 국내 금값은 덜 올랐습니다.",
                  "금은 {p} 뛰었습니다. 국내 금 시세는 환율이 반대로 움직여 그보다 덜 올랐습니다.",
                  "금값은 {p} 올랐는데, 원화로 산 금은 환율이 내린 만큼 덜 올랐습니다."]}
OI2 = {1: ["유가는 WTI 기준 {p} 올라 배럴당 {lvl_ga} 됐습니다. 원유를 거의 다 수입하는 한국엔 물가 부담이 될 수 있습니다.",
           "기름값은 배럴당 {lvl}, 한 주 {p} 올랐습니다. 국내 기름값과 항공·화학 업종 비용으로 이어질 수 있습니다.",
           "WTI는 {p} 뛰어 배럴당 {lvl}입니다. 원유를 사 오는 한국엔 무역수지 부담이 될 수 있습니다."],
       0: ["유가는 WTI 기준 {p} 내려 배럴당 {lvl_ga} 됐습니다. 원유를 거의 다 수입하는 한국엔 비용 부담이 줄 수 있습니다.",
           "기름값은 배럴당 {lvl}, 한 주 {p} 내렸습니다. 국내 기름값과 항공·화학 업종 비용엔 숨통이 될 수 있습니다.",
           "WTI는 {p} 내려 배럴당 {lvl}입니다. 원유를 사 오는 한국엔 무역수지에 숨통이 될 수 있습니다."]}
OI1 = {1: ["유가는 {p} 올랐습니다. 원유를 거의 다 수입하는 한국엔 물가 부담이 될 수 있습니다.",
           "기름값은 {p} 뛰었습니다. 국내 기름값과 항공·화학 업종 비용으로 이어질 수 있습니다.",
           "WTI는 {p} 상승했습니다. 원유를 사 오는 한국엔 무역수지 부담이 될 수 있습니다."],
       0: ["유가는 {p} 내렸습니다. 원유를 거의 다 수입하는 한국엔 비용 부담이 줄 수 있습니다.",
           "기름값은 {p} 내렸습니다. 국내 기름값과 항공·화학 업종 비용엔 숨통이 될 수 있습니다.",
           "WTI는 {p} 하락했습니다. 원유를 사 오는 한국엔 무역수지에 숨통이 될 수 있습니다."]}
OI_HOOK = {1: ["처음에 본 유가 {p} 상승은 원유를 거의 다 수입하는 한국엔 물가 부담이 될 수 있습니다.",
               "유가 {p} 상승은 국내 기름값과 항공·화학 업종 비용으로 이어질 수 있습니다.",
               "기름값 {p} 상승, 원유를 사 오는 한국엔 무역수지 부담이 될 수 있습니다."],
           0: ["처음에 본 유가 {p} 하락은 원유를 거의 다 수입하는 한국엔 비용 부담을 덜어 줄 수 있습니다.",
               "유가 {p} 하락은 국내 기름값과 항공·화학 업종 비용엔 숨통이 될 수 있습니다.",
               "기름값 {p} 하락, 원유를 사 오는 한국엔 무역수지에 숨통이 될 수 있습니다."]}
FL = ["{names} 한 주 거의 제자리였습니다.", "{names} 큰 변화가 없었습니다.", "{names} 한 주 내내 비슷한 자리였습니다."]
Q34_OIL = ["기름값이 뛴 한 주, 시장 밖에선 무슨 일이 있었을까요?", "그 사이 뉴스에선 어떤 일이 있었을까요?", "이 한 주, 기사 속에선 어떤 일들이 있었을까요?"]
Q34 = ["이 사이 시장 밖에선 어떤 일이 있었을까요?", "그 사이 뉴스에선 어떤 일이 있었을까요?", "이 한 주, 기사 속에선 어떤 일들이 있었을까요?"]


def build_uw3(C: dict, P: Pick, hook: dict, q_next: str) -> list:
    """달러·원·엔·금·유가 순서(마지막 유가가 다음 장면 뉴스로 이어진다). 움직인 항목은 숫자 하나 + 한국 투자자에게 무슨 뜻인지,
    제자리 항목은 한 문장. 두드러진 두 항목은 필수, 나머지는 1순위."""
    S = C["S"]
    items = {k: S[k] for k in FX_ORDER if S.get(k)}
    sig = {k: abs(s["wp"]) / FX_SCALE[k] for k, s in items.items()}
    moving = sorted([k for k in items if sig[k] >= 0.35], key=lambda k: -sig[k])
    flats = [k for k in FX_ORDER if k in items and k not in moving]
    figs = {k: 1 for k in moving}
    left = MAX_FIGS - len(moving)
    for k in moving[:2]:
        if left > 0 and k in ("USDKRW", "WTI") and hook.get("k") != k:
            figs[k] += 1
            left -= 1
    rank = {k: i for i, k in enumerate(moving)}
    rates_up = bool(S.get("US10Y")) and S["US10Y"]["wbp"] >= 5
    parts = []
    for k in FX_ORDER:
        if k not in items:
            continue
        s = items[k]
        up = _up(s["wp"])
        if k in flats:
            if k == "DXY":
                parts.append((1, P("uw3.dxy.flat", DX_FLAT)))
            continue
        pr = 0 if rank[k] < 2 else 1
        f = figs.get(k, 1)
        if k == "USDKRW":
            chg = s["last"] - s["prev"]
            kw = {"won": f"{abs(chg):.0f}원", "lvl": won_lv(s["last"]), "lvl_ga": i_ga(won_lv(s["last"]))}
            parts.append((pr, P(f"uw3.krw{min(f, 2)}.{up}", (K2 if f >= 2 else K1)[up], **kw)))
        elif k == "USDJPY":
            parts.append((pr, P(f"uw3.jpy.{up}", J1[up], p=pct(s["wp"]))))
            parts.append((2, P(f"uw3.jpy.mean.{up}", J_MEAN[up])))
        elif k == "DXY":
            parts.append((min(pr, 1), P(f"uw3.dxy.{up}", DX1[up], p=pct(s["wp"]))))
        elif k == "GOLD":
            kr = S.get("USDKRW")
            if kr and abs(kr["wp"]) >= 0.3 and _up(kr["wp"]) == up:
                parts.append((pr, P(f"uw3.gold.krw.same{up}", GO_KRW_SAME[up], p=pct(s["wp"]))))
            elif kr and 0.3 <= abs(kr["wp"]) <= abs(s["wp"]):
                parts.append((pr, P(f"uw3.gold.krw.mix{up}", GO_KRW_MIX[up], p=pct(s["wp"]))))
            else:
                bank = GO_UP if up else (GO_DOWN_RATE if rates_up else GO_DOWN)
                parts.append((pr, P(f"uw3.gold.{up}{int(rates_up)}", bank, p=pct(s["wp"]))))
        elif k == "WTI":
            kw = {"p": pct(s["wp"]), "lvl": usd(s["last"]), "lvl_ga": i_ga(usd(s["last"]))}
            if hook.get("k") == "WTI":
                parts.append((pr, P(f"uw3.oil.hook.{up}", OI_HOOK[up], **kw)))
            else:
                parts.append((pr, P(f"uw3.oil{min(f, 2)}.{up}", (OI2 if f >= 2 else OI1)[up], **kw)))
    rest = [FX_NAME[k] for k in flats if k != "DXY"]
    if rest:
        parts.append((3, P("uw3.flat", FL, names=eun("·".join(rest)))))
    parts.append((0, q_next))
    return parts


# ── uw4 뉴스·정치·전쟁: 기사로 확인된 것만(high/medium), 날짜·출처를 붙여 중립으로 ──
W_FIRST = ["{dd} {wd}엔", "{wd}인 {dd}엔", "현지시간 {dd}엔"]
W_NEXT = ["{dd}엔", "이어 {dd}엔", "{wd}인 {dd}엔"]
E_FORM = ["{when} {rep} 보도가 나왔습니다.", "{when} {fact} {outlet} 보도입니다.", "{outlet}에 따르면, {dd} {fact}"]
E_FORM_OWN = ["{outlet}에 따르면, {fact}", "{fact} {outlet} 보도입니다.", "{outlet} 보도로는, {fact}"]   # 문장에 이미 때가 있을 때
LINK_OIL = {1: ["이번 주 유가 오름세는 이런 소식과 겹쳤습니다.", "기름값이 가파르게 오른 시기는 이 소식이 나온 시기와 겹칩니다.",
                "유가가 뛴 한 주는 이런 소식과 맞물렸습니다."],
            0: ["이번 주 유가 내림세는 이런 소식과 겹쳤습니다.", "기름값이 내린 시기는 이 소식이 나온 시기와 겹칩니다.",
                "유가가 내린 한 주는 이런 소식과 맞물렸습니다."]}
Q45 = ["그럼 돈은 어느 업종에 머물렀을까요?", "그럼 주식시장 안에선 돈이 어디로 움직였을까요?", "업종별로는 어디가 버티고 어디가 밀렸을까요?"]
CLUSTER_CAP = 2


def pick_events(C: dict, N: dict, used_rel: list[str]) -> list[dict]:
    """정치·전쟁·통상 먼저, 그다음 정책·기업. 같은 중요도면 그 자산이 이번 주 가장 크게 움직인 날의 사건을 앞에.
    한 갈래(전쟁/정치/기업)는 최대 둘, 모두 셋까지. 지표 결과는 uw2에서 말했으면 뺀다."""
    lo, hi = _d(C["ws"]) - timedelta(days=3), _d(C["we"]) + timedelta(days=1)
    bigday = {k: s["big"]["d"] for k, s in C["S"].items()}
    evs = []
    for e in N["events"]:
        if e["conf"] not in ("high", "medium") or not e.get("d") or not (lo <= _d(e["d"]) <= hi):
            continue
        if e["prio"] == 3 and used_rel:
            continue
        sp = spoken_fact(e["fact"])
        if sp:
            rel = int(any(bigday.get(a) == e["d"] for a in e.get("assets") or []))
            hint = fact_outlet(e["fact"], sp)
            outs = ([hint] if hint else []) + [o for o in e["outlets"] if o != hint]
            evs.append({**e, "spoken": sp, "rel": rel, "outlets": outs})
    pool = [e for e in evs if e["prio"] <= 2] or evs
    pool.sort(key=lambda e: (e["prio"], -e.get("imp", 0), -e["rel"], e["conf"] != "high", e["d"]))
    seen, cnt, out = set(), {}, []
    for e in pool:
        key = e["spoken"][:12]
        if key in seen or cnt.get(e["cluster"], 0) >= CLUSTER_CAP:
            continue
        seen.add(key)
        cnt[e["cluster"]] = cnt.get(e["cluster"], 0) + 1
        out.append(e)
        if len(out) == 3:
            break
    for i, e in enumerate(out):
        e["rank"] = i
    return sorted(out, key=lambda e: (e["d"], e["rank"]))


def build_uw4(C: dict, N: dict, P: Pick, used_rel: list[str]) -> tuple[list, list[dict]]:
    evs = pick_events(C, N, used_rel)
    if not evs:
        return [], []
    parts, n_dated = [], 0
    for i, e in enumerate(evs):
        d_, w_ = dd(e["d"]), wd(e["d"])
        outlet = e["outlets"][0] if e["outlets"] else ""
        own = bool(TIME_RE.search(e["spoken"]))
        if own and outlet:
            s = P(f"uw4.own{i}", E_FORM_OWN, fact=e["spoken"], outlet=outlet)
        else:
            when = P("uw4.when0" if n_dated == 0 else f"uw4.when{i}", W_FIRST if n_dated == 0 else W_NEXT, dd=d_, wd=w_)
            n_dated += 1
            rep = reported(e["spoken"]) or ""
            avail = (lambda v, rep=rep, outlet=outlet: ("{rep}" not in v or bool(rep)) and ("{outlet}" not in v or bool(outlet)))
            s = P(f"uw4.form{i}", E_FORM, ok=avail, when=when, rep=rep, fact=e["spoken"], outlet=outlet, dd=d_) if (rep or outlet) \
                else f"{when} {e['spoken']}"
        parts.append((min(e["rank"], 2), s))
    oil = C["S"].get("WTI")
    if oil and abs(oil["wp"]) >= 3 and any(OIL_RE.search(e["blob"]) and not e["politics"] for e in evs):
        parts.append((1, P(f"uw4.link.oil{_up(oil['wp'])}", LINK_OIL[_up(oil["wp"])])))
    parts.append((0, P("uw4.q", Q45)))
    return parts, evs


# ── uw5 업종·대형주: 돈이 어디로 갔는지의 흔적(가격 기준) ──
SEC_NONE = ["업종별로 보면 {tot} 업종이 모두 내렸습니다. 가장 크게 밀린 곳은 {bot_ro}, {bp} 내렸습니다.",
            "{tot} 업종 가운데 오른 곳은 한 곳도 없었습니다. 가장 약했던 {bot_eun} {bp} 빠졌습니다.",
            "업종 성적표는 전부 내림이었습니다. 그중 {bot_i_ga} {bp} 내려 가장 크게 밀렸습니다."]
SEC_ONE = ["업종별로는 {tot} 가운데 {top}만 올랐습니다. {tp} 올랐고, 가장 약한 {bot_eun} {bp} 내렸습니다.",
           "{tot} 업종 중 오른 곳은 {top} 하나, {tp}였습니다. 가장 약한 {bot_eun} {bp} 내렸습니다.",
           "오른 업종은 {top} 하나였습니다. {top_eun} {tp} 오른 반면, {bot_eun} {bp} 밀렸습니다."]
SEC_ALL = ["업종별로 보면 {tot} 업종이 모두 올랐습니다. 가장 강한 곳은 {top_ro}, {tp} 올랐습니다.",
           "{tot} 업종 가운데 내린 곳은 한 곳도 없었습니다. 가장 강했던 {top_eun} {tp} 뛰었습니다.",
           "업종 성적표는 전부 오름이었습니다. 그중 {top_i_ga} {tp} 올라 가장 강했습니다."]
SEC_MIX = ["업종별로 보면 가장 강한 곳은 {top_ro} {tp} {tv}고, 가장 약한 곳은 {bot_ro} {bp} {bv}습니다.",
           "{tot} 업종 가운데 {n_up} 곳이 올랐습니다. 맨 위는 {top} {tp} {tn}, 맨 아래는 {bot} {bp} {bn}이었습니다.",
           "업종 성적표 맨 위엔 {top}, 맨 아래엔 {bot_i_ga} 있었습니다. 각각 {tp} {tv}고, {bp} {bv}습니다."]
MEGA = ["대형주 {nmeg} 가운데선 {t_i_ga} {tp} {tr} {tdesc}, {b_eun} {bp} {br} {bdesc}.",
        "대형주 중엔 {t} {tp} {tn}, {b} {bp} {bn}이 양 끝이었습니다.",
        "대형주 {nmeg_eul} 줄 세우면 맨 앞은 {t} {tp} {tn}, 맨 끝은 {b} {bp} {bn}이었습니다."]
SEMI_SPLIT = ["같은 반도체 안에서도 {ups_eun} 오르고 {downs_eun} 내려, 방향이 엇갈렸습니다.", "반도체 대형주끼리도 {ups_eun} 올랐지만 {downs_eun} 내렸습니다.",
              "반도체 안에서도 방향이 갈렸습니다. {ups_eun} 오르고, {downs_eun} 내렸습니다."]
EVID = ["가격으로 보면, 돈이 {top} 쪽에 머물고 {bot} 쪽에선 빠진 한 주로 볼 수 있습니다.", "업종 성적으로 보면, 돈은 {top_ro} 향하고 {bot}에선 물러난 모습으로 볼 수 있습니다.",
        "등락만 놓고 보면, {top_eun} 버티고 {bot_eun} 밀린 한 주로 읽힙니다."]
Q56 = ["그럼 이 한 주를 한 줄로 줄이면 어떨까요?", "이 숫자들을 한데 모으면, 어떤 한 주였을까요?", "그렇다면 이번 주는 어떤 한 주로 볼 수 있을까요?"]
SEMIS = ("NVDA", "AMD", "MU", "AVGO", "INTC", "QCOM", "TSM")


def _and(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-2] + [wa(names[-2]) + " " + names[-1]])


def build_uw5(C: dict, P: Pick) -> list:
    parts = []
    secs, megas = C["sectors"], C["megas"]
    if secs:
        top, bot = secs[0], secs[-1]
        n_up = sum(1 for x in secs if x["week_pct"] > 0)
        tn, bn = top["name_ko"], bot["name_ko"]
        kw = {"tot": f"{KO_COUNT.get(len(secs), len(secs))} 개", "top": tn, "bot": bn, "top_eun": eun(tn), "bot_eun": eun(bn), "top_ro": ro(tn),
              "bot_ro": ro(bn), "top_i_ga": i_ga(tn), "bot_i_ga": i_ga(bn), "top_ieot": ieot(tn), "tp": pct(top["week_pct"]), "bp": pct(bot["week_pct"]),
              "tv": V_A[_up(top["week_pct"])], "bv": V_A[_up(bot["week_pct"])], "tn": ("하락", "상승")[_up(top["week_pct"])],
              "bn": ("하락", "상승")[_up(bot["week_pct"])], "n_up": KO_COUNT.get(n_up, str(n_up))}
        if n_up == 0:
            parts.append((0, P("uw5.sec.none", SEC_NONE, **kw)))
        elif n_up == 1:
            parts.append((0, P("uw5.sec.one", SEC_ONE, **kw)))
        elif n_up == len(secs):
            parts.append((0, P("uw5.sec.all", SEC_ALL, **kw)))
        else:
            parts.append((0, P("uw5.sec.mix", SEC_MIX, **kw)))
    if megas:
        t, b = megas[0], megas[-1]
        tnm, bnm = t.get("name_ko") or t["ticker"], b.get("name_ko") or b["ticker"]
        nmeg = f"{KO_COUNT.get(len(megas), len(megas))} 개"
        tu, bu = _up(t["week_pct"]), _up(b["week_pct"])
        parts.append((0, P("uw5.mega", MEGA, nmeg=nmeg, nmeg_eul=eul(nmeg), t=tnm, b=bnm, t_i_ga=i_ga(tnm), b_eun=eun(bnm),
                           tp=pct(t["week_pct"]), bp=pct(b["week_pct"]), tr=V_RISE[tu], br=V_RISE[bu],
                           tdesc="가장 강했고" if tu else "가장 덜 밀렸고", bdesc="가장 약했습니다" if not bu else "가장 덜 올랐습니다",
                           tn=("하락", "상승")[tu], bn=("하락", "상승")[bu])))
        semis = [x for x in megas if x.get("ticker") in SEMIS]
        ups = [x.get("name_ko") or x["ticker"] for x in semis if x["week_pct"] >= 1]
        downs = [x.get("name_ko") or x["ticker"] for x in semis if x["week_pct"] <= -1]
        if ups and downs and max(x["week_pct"] for x in semis) - min(x["week_pct"] for x in semis) >= 5:
            parts.append((3, P("uw5.semi", SEMI_SPLIT, ups_eun=eun(_and(ups)), downs_eun=eun(_and(downs)))))
    if secs and secs[0]["week_pct"] > 0 > secs[-1]["week_pct"]:
        tn, bn = secs[0]["name_ko"], secs[-1]["name_ko"]
        parts.append((2, P("uw5.evid", EVID, top=tn, bot=bn, top_ro=ro(tn), top_eun=eun(tn), bot_eun=eun(bn))))
    parts.append((0, P("uw5.q", Q56)))
    return parts


# ── uw6 우리 해석 한 줄 + 월요일 국장에서 볼 것 + 다음 주 일정 + 끝 멘트 ──
SYN = {"rates_oil_down": ["한 줄로 줄이면, 유가와 금리가 함께 뛰는 사이 주식이 한발씩 물러선 한 주로 볼 수 있습니다.",
                          "이번 주는 기름값과 금리가 오르는 동안 주식이 버티지 못한 한 주로 볼 수 있습니다.",
                          "숫자로 보면, 유가와 금리가 오를수록 주식은 뒤로 밀린 한 주로 읽힙니다."],
       "rates_down": ["한 줄로 줄이면, 금리가 오르는 사이 주식이 한발씩 물러선 한 주로 볼 수 있습니다.",
                      "이번 주는 금리 오름세와 주식 약세가 나란히 간 한 주로 볼 수 있습니다.",
                      "숫자로 보면, 금리가 오를수록 주식은 뒤로 밀린 한 주로 읽힙니다."],
       "oil_down": ["한 줄로 줄이면, 기름값이 뛰는 사이 주식이 밀린 한 주로 볼 수 있습니다.", "이번 주는 유가 오름세와 주식 약세가 나란히 간 한 주로 볼 수 있습니다.",
                    "숫자로 보면, 기름값이 오를수록 주식은 뒤로 밀린 한 주로 읽힙니다."],
       "riskoff": ["한 줄로 줄이면, 주식과 금리가 함께 내린 한 주로 볼 수 있습니다. 안전한 채권 쪽을 찾는 돈이 늘었다는 풀이가 나올 수 있습니다.",
                   "이번 주는 주식이 밀리고 채권 금리도 내려간, 안전한 쪽을 찾는 한 주로 볼 수 있습니다.",
                   "숫자로 보면, 주식에서 채권으로 돈이 옮겨 간 모습으로 읽힙니다."],
       "relief": ["한 줄로 줄이면, 금리가 내려오는 사이 주식이 숨을 돌린 한 주로 볼 수 있습니다.", "이번 주는 금리 하락과 주식 오름세가 나란히 간 한 주로 볼 수 있습니다.",
                  "숫자로 보면, 금리가 내릴수록 주식은 힘을 얻은 한 주로 읽힙니다."],
       "resilient": ["한 줄로 줄이면, 금리가 올랐는데도 주식이 버틴 한 주로 볼 수 있습니다.", "이번 주는 금리 부담 속에서도 주식이 오른 한 주로 볼 수 있습니다.",
                     "숫자로 보면, 금리가 올라도 주식은 힘을 잃지 않은 한 주로 읽힙니다."],
       "up": ["한 줄로 줄이면, 금리도 유가도 조용한 가운데 주식이 오른 한 주로 볼 수 있습니다.", "이번 주는 큰 부담 없이 주식이 올라선 한 주로 볼 수 있습니다.",
              "숫자로 보면, 바깥 변수는 조용했고 주식은 힘을 낸 한 주로 읽힙니다."],
       "down": ["한 줄로 줄이면, 금리도 유가도 조용한데 주식만 밀린 한 주로 볼 수 있습니다.", "이번 주는 바깥 변수보다 주식 안쪽 사정이 더 크게 보인 한 주로 볼 수 있습니다.",
                "숫자로 보면, 금리와 유가는 잠잠했는데 주식은 뒤로 밀린 한 주로 읽힙니다."],
       "flat": ["한 줄로 줄이면, 지수는 조용했지만 업종 안에선 {top_wa} {bot_i_ga} 엇갈린 한 주로 볼 수 있습니다.",
                "이번 주는 겉으론 잠잠했고, 안쪽에선 {top_wa} {bot_i_ga} 반대로 움직인 한 주로 볼 수 있습니다.",
                "숫자로 보면, 지수는 제자리였지만 업종끼리는 엇갈린 한 주로 읽힙니다."]}
SEMI_CL = ["반도체는 초반엔 버티다 {b}에 밀리며 한 주를 약하게 마쳤습니다.", "반도체만 보면, 주 초엔 버텼지만 {b}에 크게 밀렸습니다.",
           "반도체는 {a}까지 버티다가 {b} 하루에 크게 밀렸습니다."]
WATCH = {"down": ["{why}, 월요일 국장에선 삼성전자와 SK하이닉스를 외국인이 사는지, 파는지부터 봅니다.",
                  "{why}, 월요일엔 삼성전자·SK하이닉스 외국인 수급부터 봅니다.",
                  "{why}, 월요일 국장에서 먼저 볼 곳은 삼성전자와 SK하이닉스입니다."],
         "up": ["{why}, 월요일엔 삼성전자와 SK하이닉스에 외국인 순매수가 들어오는지 봅니다.",
                "{why}, 월요일 국장에선 삼성전자·SK하이닉스 외국인 수급부터 봅니다.",
                "{why}, 월요일 국장에서 먼저 볼 곳은 삼성전자와 SK하이닉스입니다."],
         "flat": ["월요일 국장에선 외국인이 반도체를 사는지, 파는지부터 봅니다.", "월요일 국장에선 삼성전자·SK하이닉스 외국인 수급부터 봅니다.",
                  "월요일 국장에서 먼저 볼 곳은 반도체 외국인 수급입니다."]}
FXW = ["원화가 한 주 {vk} 만큼, 외국인 돈의 방향도 함께 봅니다.", "환율이 크게 움직인 만큼 외국인 수급도 같이 확인합니다.",
       "원·달러 환율 움직임도 외국인 수급과 함께 봅니다."]
CAL_LEAD = ["다음 주 가장 큰 일정은 {when} {ev}입니다.", "다음 주엔 {when}에 {ev_i_ga} 나옵니다.", "다음 주 달력에서 먼저 볼 건 {when} {ev}입니다."]
CAL_2 = ["{when2} {ev2}도 있습니다.", "{when2}엔 {ev2}도 나옵니다.", "{ev2}도 {when2}에 나옵니다."]
CAL_EXPL = {"FOMC": ["미국 기준금리를 정하는 회의입니다.", "FOMC는 미국 기준금리를 정하는 연준의 회의입니다.", "미국 기준금리가 여기서 정해집니다."],
            "DOT": ["이번엔 위원들이 앞으로의 금리 수준을 점으로 찍은 점도표도 함께 나옵니다.", "위원들이 생각하는 금리 수준을 점으로 찍은 점도표도 이번에 공개됩니다.",
                    "이번 회의에선 위원별 금리 점을 모은 점도표도 나옵니다."],
            "RETAIL": ["미국 소비가 얼마나 버티는지 보여 주는 숫자입니다.", "미국 사람들이 지갑을 얼마나 열었는지 보여 줍니다.", "미국 경제의 큰 축인 소비를 재는 지표입니다."],
            "CPI": ["물가가 얼마나 올랐는지 재는 대표 지표입니다.", "미국 물가를 재는 가장 대표적인 숫자입니다.", "금리 방향을 가늠할 때 가장 먼저 보는 물가 지표입니다."],
            "JOBS": ["미국 일자리가 얼마나 늘었는지 보여 주는 지표입니다.", "미국 고용 시장의 온도를 재는 숫자입니다.", "일자리와 실업률이 함께 나오는 지표입니다."]}
CAL_TIER = [(r"FOMC|금리 결정", 0, "FOMC"), (r"CPI|소비자물가", 0, "CPI"), (r"고용보고서|비농업|고용 동향|고용지표", 0, "JOBS"), (r"잭슨홀", 0, ""),
            (r"PCE|개인소비지출", 1, ""), (r"소매판매", 1, "RETAIL"), (r"PPI|생산자물가", 1, ""), (r"GDP", 1, ""), (r"실적", 1, ""),
            (r"만기|위칭", 2, ""), (r"산업생산", 2, "")]


def _cal_info(e: dict) -> tuple[int, str, str]:
    t = str(e.get("event_ko") or e.get("event") or "")
    for rx, tier, key in CAL_TIER:
        if re.search(rx, t):
            m = re.search(r"(\d{1,2})월\s?", t)
            mo = f"{m.group(1)}월 " if m else ""
            name = {"FOMC": "FOMC 금리 결정", "CPI": f"{mo}소비자물가", "JOBS": f"{mo}고용보고서", "RETAIL": f"{mo}소매판매"}.get(key)
            if not name:
                name = "미국 선물·옵션 동시 만기" if re.search(r"만기|위칭", t) else re.sub(r"\s?\([^)]*\)", "", t).strip()
            return tier, name, key
    return 3, re.sub(r"\s?\([^)]*\)", "", t).strip(), ""


def _when_cal(e: dict) -> tuple[str, str]:
    """(말할 때, 같은 날 비교용 키) — 한국 시간이 있으면 한국 시간으로."""
    k = e.get("kst")
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", str(k or ""))
    if m:
        h, mi = int(m.group(2)), int(m.group(3))
        ap = "새벽" if h < 6 else "오전" if h < 12 else "오후" if h < 18 else "밤"
        hh = h if h <= 12 else h - 12
        return f"한국 시간 {_d(m.group(1)).day}일 {ap} {hh}시" + (f" {mi}분" if mi else ""), m.group(1)
    d0 = iso(e.get("date"))
    return (f"현지시간 {_d(d0).day}일 {wd(d0)}", d0) if d0 else ("다음 주", "")


def sox_dir(S: dict) -> str:
    s = S.get("SOX")
    if not s:
        return "flat"
    last = s["days"][-1]["pct"] or 0
    if s["wp"] <= -1 or last <= -2:
        return "down"
    if s["wp"] >= 1 and last >= 0:
        return "up"
    return "flat"


def build_uw6(C: dict, N: dict, P: Pick) -> tuple[list, dict]:
    S, parts = C["S"], []
    ix, r, o = S.get("IXIC"), S.get("US10Y"), S.get("WTI")
    st = 0 if not ix or abs(ix["wp"]) < 0.5 else (1 if ix["wp"] > 0 else -1)
    rt = 0 if not r or abs(r["wbp"]) < 5 else (1 if r["wbp"] > 0 else -1)
    ot = 0 if not o or abs(o["wp"]) < 3 else (1 if o["wp"] > 0 else -1)
    typ = ("rates_oil_down" if (rt > 0 and ot > 0) else "rates_down" if rt > 0 else "oil_down" if ot > 0 else "riskoff" if rt < 0 else "down") \
        if st < 0 else ("resilient" if rt > 0 else "relief" if rt < 0 else "up") if st > 0 else "flat"
    secs = C["sectors"]
    tn, bn = (secs[0]["name_ko"], secs[-1]["name_ko"]) if secs else ("", "")
    if typ == "flat" and not secs:
        typ = "down" if (ix and ix["wp"] < 0) else "up"
    parts.append((0, P(f"uw6.syn.{typ}", SYN[typ], top_wa=wa(tn) if tn else "", bot_i_ga=i_ga(bn) if bn else "")))
    sx = S.get("SOX")
    rv = _rev(sx) if sx else None
    if rv and rv["last"] and rv["vb"] == "내렸":
        parts.append((3, P("uw6.semi", SEMI_CL, a=rv["a"], b=rv["b"]), "semi"))     # uw1에 반도체 문장이 남으면 조립 때 뺀다
    sd = sox_dir(S)
    why = ""
    if sx and sd != "flat":
        if sd == "down" and rv and rv["last"] and rv["vb"] == "내렸":
            why = f"미국 반도체지수가 {rv['b']} 하루 {pct(rv['bday']['pct'])} 내린 만큼"
        else:
            why = f"미국 반도체지수가 한 주 {pct(sx['wp'])} {'오른' if sx['wp'] > 0 else '내린'} 만큼"
    parts.append((0, P(f"uw6.watch.{sd}", WATCH[sd], why=why)))
    k = S.get("USDKRW")
    if k and abs(k["wp"]) >= 1:
        parts.append((3, P("uw6.fx", FXW, vk=("강해진", "약해진")[_up(k["wp"])])))
    cal = sorted([(*_cal_info(e), e) for e in C["cal"]], key=lambda x: (x[0], str(x[3].get("kst") or x[3].get("date"))))
    cal = [c for c in cal if c[0] <= 2]
    if cal:
        t1, n1, k1, e1 = cal[0]
        w1, day1 = _when_cal(e1)
        parts.append((0, P("uw6.cal", CAL_LEAD, when=w1, ev=n1, ev_i_ga=i_ga(n1))))
        if k1 in CAL_EXPL:
            parts.append((2, P(f"uw6.cal.expl.{k1}", CAL_EXPL[k1])))
        if k1 == "FOMC" and "점도표" in str(e1.get("event_ko")):
            parts.append((4, P("uw6.cal.dot", CAL_EXPL["DOT"])))
        if len(cal) > 1:
            t2, n2, k2, e2 = cal[1]
            w2, day2 = _when_cal(e2)
            parts.append((3, P("uw6.cal2", CAL_2, when2="같은 날" if day2 and day2 == day1 else w2, ev2=n2)))
    # ② 시청자에게 묻는다 ③ 좋아요 (2026-09-14 채널 분석)
    parts.append((0, P("uw6.ask", ["이번 주 미국 숫자, 여러분은 어떻게 보셨습니까? 댓글로 남겨 주세요.",
                                   "월요일에 여러분은 무엇을 먼저 보시겠습니까? 댓글로 남겨 주세요.",
                                   "이번 주에서 가장 이상했던 숫자는 무엇이었습니까? 댓글로 알려 주세요."])))
    parts.append((0, P("uw6.cta", ["도움이 되셨다면 좋아요, 다음 주가 궁금하면 구독 눌러 주세요.",
                                   "이 정리가 도움이 됐다면 좋아요와 구독 부탁드립니다.",
                                   "매주 이 자리에서 미국 숫자를 국장으로 옮겨 드립니다. 좋아요와 구독 눌러 주세요."])))
    parts.append((0, SIGN_OFF))
    return parts, {"type": typ, "sox": sd}


# ── 제목 ──
TITLE = ["{a}, {b_back} | {rng} 미국 주간", "{b_front}, {a} | {rng} 미국 주간", "{a2}… {b_back} | {rng} 미국 주간"]
MACRO = ("oil", "rate", "usdkrw", "usdjpy", "dxy", "gold", "vix")


def _heads(C: dict, h: dict) -> tuple[str, str]:
    """제목에 넣을 훅 구절 (기본형, 다른 표현) — 진짜 숫자만."""
    S = C["S"]
    s = S.get(h.get("k"))
    if h["kind"] == "oil":
        up = _up(s["wp"])
        h1 = f"유가 한 주 {pct(s['wp'])} {('급등' if up else '급락') if abs(s['wp']) >= 8 else ('상승' if up else '하락')}"
        h2 = (f"WTI {h['L']:.0f}달러 돌파" if up else f"WTI {h['L']:.0f}달러 아래로") if h.get("L") else h1
        return h1, h2
    if h["kind"] == "rate":
        return f"미 10년물 금리 {ylv(s['last'])}", f"10년물 금리 {ylv(s['last'])}{'까지' if s['wbp'] > 0 else '로 하락'}"
    if h["kind"] in ("idx_week", "idx_day"):
        nm = IDX_NAME[h["k"]]
        if h["kind"] == "idx_week":
            t = f"{nm} 한 주 {pct(s['wp'])} {'상승' if s['wp'] > 0 else '하락'}"
        else:
            t = f"{nm} {wd(s['big']['d'])} 하루 {pct(s['big']['pct'])} {'상승' if (s['big']['pct'] or 0) > 0 else '하락'}"
        return t, t
    if h["kind"] == "mega":
        m = h["m"]
        t = f"{m.get('name_ko') or m['ticker']} 한 주 {pct(m['week_pct'])} {'상승' if m['week_pct'] > 0 else '하락'}"
        return t, t
    if h["kind"] == "usdkrw":
        chg = s["last"] - s["prev"]
        t = f"원·달러 한 주 {abs(chg):.0f}원 {'상승' if chg > 0 else '하락'}"
        return t, f"원·달러 {won_lv(s['last'])}"
    if h["kind"] == "usdjpy":
        t = f"엔화 한 주 {pct(s['wp'])} {'약세' if s['wp'] > 0 else '강세'}"
        return t, t
    if h["kind"] == "gold":
        t = f"금값 한 주 {pct(s['wp'])} {'상승' if s['wp'] > 0 else '하락'}"
        return t, t
    if h["kind"] == "vix":
        t = f"공포지수 한 주 {pct(s['wp'])} {'상승' if s['wp'] > 0 else '하락'}"
        return t, t
    if h["kind"] == "dxy":
        t = f"달러 인덱스 한 주 {pct(s['wp'])} {'상승' if s['wp'] > 0 else '하락'}"
        return t, t
    return "", ""


def build_title(C: dict, P: Pick, hook: dict, cands: list[dict]) -> str:
    """'{훅}, {반대편}' — 훅이 금리·유가·환율이면 반대편은 나스닥, 훅이 지수·종목이면 반대편은 가장 큰 금리·유가 숫자."""
    ix = C["S"].get("IXIC")
    ss = C["sessions"]
    rng = f"{md(C['ws'])}–{md(C['we'])}" if C["complete"] else f"{md(ss[0])}–{md(ss[-1])}"
    a, a2 = _heads(C, hook)
    if hook["kind"] in MACRO or hook.get("k") == "IXIC":
        if hook.get("k") == "IXIC":
            other = next((c for c in cands if c["kind"] in MACRO), None)
            a, a2 = _heads(C, other) if other else (a, a2)
        b_back = f"나스닥은 {pct(ix['wp'])} {'상승' if ix['wp'] > 0 else '하락'}" if ix else ""
        b_front = f"나스닥 한 주 {pct(ix['wp'])} {'상승' if ix['wp'] > 0 else '하락'}" if ix else ""
    else:
        other = next((c for c in cands if c["kind"] in MACRO), None)
        b_back = b_front = _heads(C, other)[0] if other else ""
    if not a or not b_back:
        return f"{a or '미국 증시 한 주 결산'} | {rng} 미국 주간"
    return P("title", TITLE, a=a, a2=a2, b_back=b_back, b_front=b_front, rng=rng)


# ── Threads(반말, 처음 보는 사람 기준) + 첫 답글 ──
# 말투(JJ 2026-09-13): 쓰레드 본문·답글은 **반말**이다. 영상 대본(uw0~uw6)·제목·유튜브 설명은 합니다체 그대로다.
#   유튜브는 채널을 보러 온 사람이고, 쓰레드 피드는 지나가는 사람이다. 피드에서 댓글이 붙는 글은 전부 반말 + 질문이었다.
#   반말이지 줄임말이 아니다 — 음슴체('팜/샀음/오름')·채팅 기호(ㅋㅎㅠ)는 계속 금지다.
#   친한 사람에게 설명하는 말투이지 시비조가 아니고, 독자의 손익·보유를 전제하지 않는다.
# 짜임(JJ 2026-09-12): 이 글만 읽고 이해되게. ① 무슨 일이 있었나 → ② 그래서 돈이 어디로 갔나 → ③ 무슨 뜻일 수 있나 → ④ 질문.
# 마지막 줄은 독자에게 던지는 질문으로 닫는다(TH_ASK) — '그래서 무슨 뜻'은 그 앞줄(TH_MEAN)이 맡는다.
# 금융 용어를 쓰지 않는다(JJ 2026-09-13): 순매수·수급·지수·업종·대형주·국채·유가·증시·국장은 뜻만 남기고 낱말을 버린다.
# 허용: 코스피·나스닥·삼성전자 같은 고유명과 외국인·기관·개인 같은 주체명, 숫자.
TH_IDX_NAME = {"IXIC": "나스닥", "SPX": "S&P500", "DJI": "다우", "SOX": "미국 반도체 주식", "VIX": "시장의 불안을 재는 VIX"}
TH_HOOK = {"oil_x1": ["기름값이 한 주 만에 배럴당 {L}달러를 넘었어.", "이번 주 기름값이 올라 배럴당 {L}달러를 넘겼어.",
                      "미국에서 사고파는 기름이 배럴당 {L}달러 위로 올라섰어."],
           "oil_x0": ["기름값이 한 주 만에 배럴당 {L}달러 아래로 내려왔어.", "이번 주 기름값이 내려 배럴당 {L}달러를 밑돌았어.",
                      "미국에서 사고파는 기름이 배럴당 {L}달러 아래로 내려섰어."],
           "oil1": ["기름값이 이번 주 {p} 올랐어.", "이번 주 기름값이 {p} 올라 배럴당 {lvl}가 됐어.", "미국 기름값은 한 주 동안 {p} 올랐어."],
           "oil0": ["기름값이 이번 주 {p} 내렸어.", "이번 주 기름값이 {p} 내려 배럴당 {lvl}가 됐어.", "미국 기름값은 한 주 동안 {p} 내렸어."],
           "rate1": ["미국이 10년 빌리는 돈에 붙는 이자가 {lvl}까지 올랐어.", "이번 주 미국에서 돈 빌리는 값이 {pp} 올랐어.",
                     "미국 나랏빚에 붙는 이자는 한 주 {pp} 올라 {lvl}가 됐어."],
           "rate0": ["미국이 10년 빌리는 돈에 붙는 이자가 {lvl}까지 내려왔어.", "이번 주 미국에서 돈 빌리는 값이 {pp} 내렸어.",
                     "미국 나랏빚에 붙는 이자는 한 주 {pp} 내려 {lvl}가 됐어."],
           "idx1": ["{nm_i_ga} 이번 주 {p} 올랐어.", "이번 주 미국 시장에서 {nm_i_ga} {p} 올랐어.", "{nm_eun} 한 주 동안 {p} 올랐어."],
           "idx0": ["{nm_i_ga} 이번 주 {p} 내렸어.", "이번 주 미국 시장에서 {nm_i_ga} {p} 내렸어.", "{nm_eun} 한 주 동안 {p} 내렸어."],
           "idxd1": ["{nm_i_ga} {wd} 하루에만 {p} 올랐어.", "{wd} 하루 동안 {nm_i_ga} {p} 올랐어.", "{nm_eun} {wd}에만 {p} 뛰었어."],
           "idxd0": ["{nm_i_ga} {wd} 하루에만 {p} 내렸어.", "{wd} 하루 동안 {nm_i_ga} {p} 내렸어.", "{nm_eun} {wd}에만 {p} 밀렸어."],
           "gen": ["{v}.", "이번 주 {v2}.", "{v3}."]}
TH_SAME = {1: ["문을 연 {nd} 동안 하루도 빠지지 않았어.", "{nd} 내리 오르기만 했어.", "한 주 내내 오르는 날만 이어졌어."],
           0: ["문을 연 {nd} 동안 하루도 오르지 못했어.", "{nd} 내리 내리기만 했어.", "한 주 내내 내리는 날만 이어졌어."]}
TH_BIGGEST = ["이번 주 미국 시장에서 가장 크게 움직인 숫자야.", "한 주 동안 가장 크게 움직인 쪽이 여기야.", "이번 주 숫자 가운데 움직임이 가장 컸어."]
TH_Q = {"macro": ["그럼 주식은 어떻게 움직였을까?", "이 숫자는 주식에 어떻게 닿았을까?", "그 사이 돈은 어디로 갔을까?"],
        "idx": ["그럼 돈은 어디로 움직였을까?", "그 안에서 어디가 오르고 어디가 밀렸을까?", "한 주 동안 무슨 일이 있었을까?"]}
TH_IX = {"all0": ["그 사이 나스닥은 하루도 오르지 못했어.", "나스닥은 {nd} 내리 내렸어.", "나스닥은 {nd} 연속으로 내렸어."],
         "all1": ["그 사이 나스닥은 하루도 내리지 않았어.", "나스닥은 {nd} 내리 올랐어.", "나스닥은 {nd} 연속으로 올랐어."],
         "gen": ["그 사이 나스닥은 한 주 {p} {v}어.", "나스닥은 한 주 동안 {p} {v}어.", "같은 기간 나스닥은 {p} {v}어."]}
TH_RATE = {1: ["미국이 10년 빌리는 돈의 이자도 {lvl}까지 올랐어.", "같은 기간 미국 나랏빚 이자는 {lvl}로 올랐어.", "돈 빌리는 값도 한 주 {pp} 올랐어."],
           0: ["미국이 10년 빌리는 돈의 이자는 {lvl}까지 내려왔어.", "같은 기간 미국 나랏빚 이자는 {lvl}로 내렸어.", "돈 빌리는 값은 한 주 {pp} 내렸어."]}
TH_OIL = {1: ["기름값도 한 주 {p} 올랐어.", "같은 기간 기름값도 {p} 올라 배럴당 {lvl}가 됐어.", "미국 기름값도 한 주 동안 {p} 올랐어."],
          0: ["기름값은 한 주 {p} 내렸어.", "같은 기간 기름값은 {p} 내려 배럴당 {lvl}가 됐어.", "미국 기름값은 한 주 동안 {p} 내렸어."]}
TH_SECTOR = {"mix": ["분야로 보면 {top_i_ga} 오르고 {bot_i_ga} 내렸어.", "가장 많이 오른 곳은 {top}, 가장 많이 내린 곳은 {bot_ieot}어.",
                     "오른 쪽은 {top}, 내린 쪽은 {bot_ieot}어."],
             "one": ["{tot} 분야 가운데 오른 곳은 {top} 하나야.", "오른 곳은 {top} 한 곳뿐이었어.", "{top_eul} 빼면 모든 분야가 내렸어."],
             "none": ["{tot} 분야가 모두 내렸어.", "오른 곳은 한 곳도 없었어.", "분야는 하나도 남김없이 내렸어."],
             "all": ["{tot} 분야가 모두 올랐어.", "내린 곳은 한 곳도 없었어.", "분야는 하나도 빠짐없이 올랐어."]}
TH_MEGA = ["덩치 큰 회사 중에서는 {nm_i_ga} 한 주 {p} {v}어.", "가장 크게 움직인 큰 회사는 {nm}, 한 주 {p} {v}어.",
           "{nm_eun} 한 주 {p} {v}고, 큰 회사 중에 움직임이 가장 컸어."]
TH_FALL = ["이번 주는 숫자가 크게 움직이지 않았어.", "한 주 동안 큰 변화는 없었어.", "이번 주 미국 시장은 조용한 편이었어."]
TH_READ = {"rate_oil": ["이자도 기름값도 함께 올라간 한 주였어.", "이번 주는 이자와 기름값이 나란히 올랐어.", "빌리는 값도 기름값도 위를 본 한 주야."],
           "rate": ["이번 주 시장의 중심은 이자 쪽에 있었어.", "주식보다 돈 빌리는 값이 더 크게 움직인 한 주야.", "한 주 내내 이자가 기준이었어."],
           "oil": ["이번 주는 기름값이 가장 크게 움직였어.", "시장의 눈이 기름값 쪽에 쏠린 한 주야.", "한 주 내내 기름값이 앞에 있었어."],
           "up": ["미국 주식은 오르는 쪽으로 한 주를 마쳤어.", "미국 주식은 위쪽을 보고 한 주를 닫았어.", "주식은 오른 자리에서 한 주를 마무리했어."],
           "down": ["미국 주식은 내리는 쪽으로 한 주를 마쳤어.", "미국 주식은 아래쪽을 보고 한 주를 닫았어.", "주식은 내린 자리에서 한 주를 마무리했어."],
           "flat": ["큰 방향 없이 지나간 한 주였어.", "이번 주 미국 주식은 방향을 정하지 못했어.", "위아래가 섞인 채로 한 주가 지났어."]}
# 첫 문단 두 줄(JJ 2026-09-13) — 1줄은 읽는 사람이 이미 본 것(주말 뉴스에 뜬 미국 주식 방향),
# 2줄은 그것만 보면 놓치는 '숫자가 든' 사실이다. 빈손 예고('확인할 숫자는 따로 있어')는 쓰지 않는다.
# 1줄은 같은 어미만 반복하면 AI 티가 나므로 여섯 가지를 주차로 돌리고, '봤을 거야'는 여섯 중 하나로만 둔다.
TH_OPEN1 = {"down": ["이번 주 미국 주식이 내렸다는 소식은 이미 뉴스에 나왔어.",
                     "주말 뉴스마다 미국 주식이 내렸다는 이야기가 돌았어.",
                     "미국 주식이 한 주 내내 밀렸다는 건 뉴스로 이미 봤을 거야.",
                     "간밤 뉴스에 뜬 미국 주식 하락, 거기까지는 다들 봤어.",
                     "뉴욕 주식이 내렸다는 이야기는 어제오늘 뉴스에 계속 나왔어.",
                     "포털 첫 화면에도 미국 주식이 내렸다고 떠 있었어."],
            "up": ["이번 주 미국 주식이 올랐다는 소식은 이미 뉴스에 나왔어.",
                   "주말 뉴스마다 미국 주식이 올랐다는 이야기가 돌았어.",
                   "미국 주식이 한 주 내내 올랐다는 건 뉴스로 이미 봤을 거야.",
                   "간밤 뉴스에 뜬 미국 주식 상승, 거기까지는 다들 봤어.",
                   "뉴욕 주식이 올랐다는 이야기는 어제오늘 뉴스에 계속 나왔어.",
                   "포털 첫 화면에도 미국 주식이 올랐다고 떠 있었어."],
            "flat": ["이번 주 미국 주식이 잠잠했다는 소식은 뉴스에 나왔어.",
                     "주말 뉴스에도 미국 주식은 이렇다 할 이야기가 없었어.",
                     "미국 주식이 한 주 내내 제자리였다는 건 이미 봤을 거야.",
                     "간밤 뉴스에 뜬 미국 주식, 거기까지는 다들 봤어.",
                     "뉴욕 주식이 방향을 못 잡았다는 이야기는 뉴스에 계속 나왔어.",
                     "포털 첫 화면에도 미국 주식은 거의 그대로 떠 있었어."]}
# 2줄 — 월요일 한국 시장으로 건너오는 숫자. 반도체가 첫째고, 없으면 달러 값·나스닥·이자 순으로 내려간다.
# 여기 쓴 숫자는 아래 답 묶음에서 빼서 같은 말을 두 번 하지 않는다. 한 줄은 한 문장으로 끊는다(한 호흡에 한 줄).
TH_LINE2 = {"SOX": ["그런데 미국 반도체 주식은 한 주 {p} {v}어.",
                    "정작 미국 반도체 주식은 한 주 {p} {v}어.",
                    "한국 반도체가 따라 보는 미국 반도체는 {p} {v}어.",
                    "뉴스에 덜 나온 미국 반도체는 한 주 {p} {v}어."],
            "USDKRW": ["그런데 달러 한 장 값이 한 주 사이 {won} {vk}어.",
                       "정작 크게 움직인 건 달러 값, 한 주 {won} {vk}어.",
                       "같은 기간 달러 한 장 값은 {won} {vk}어.",
                       "뉴스에 덜 나온 달러 값은 한 주 {won} {vk}어."],
            "IXIC": ["그런데 나스닥만 떼어 보면 한 주 {p} {v}어.",
                     "정작 나스닥은 한 주 동안 {p} {v}어.",
                     "숫자로 보면 나스닥은 한 주 {p} {v}어.",
                     "뉴스에 덜 나온 나스닥은 한 주 {p} {v}어."],
            "US10Y": ["그런데 미국이 10년 빌리는 돈의 이자가 {pp} {v}어.",
                      "정작 크게 움직인 건 이자, 한 주 {pp} {v}어.",
                      "같은 기간 미국 나랏빚 이자는 {lvl}가 됐어.",
                      "뉴스에 덜 나온 이자는 한 주 {pp} {v}어."]}
# 2줄에 쓴 숫자가 무엇인지 한 줄로 풀어 준다 — 처음 보는 사람은 '미국 반도체'가 뭘 묶은 숫자인지 모른다.
TH_LINE3 = {"SOX": ["미국에서 반도체 만드는 회사들 주가를 묶은 숫자야.",
                    "미국 반도체 회사들 주가를 한 줄로 모은 숫자야.",
                    "엔비디아처럼 미국에서 반도체 만드는 회사들을 묶은 거야."],
            "USDKRW": ["달러 한 장 사려면 원화를 얼마 내야 하는지 나타낸 값이야.",
                       "달러 한 장을 바꿔 오는 데 드는 원화 값이야.",
                       "우리 돈으로 달러 한 장 사는 데 드는 값이야."]}
# 달러 값 — 미국 숫자가 한국 계산으로 넘어오는 또 하나의 통로(우선순위 4: 자리가 남을 때만 붙는다)
TH_FX = {0: ["달러 한 장 값은 한 주 사이 {won} 내렸어.", "같은 기간 달러 값도 {won} 내려왔어.", "달러를 사는 값이 한 주 동안 {won} 내렸어."],
         1: ["달러 한 장 값은 한 주 사이 {won} 올랐어.", "같은 기간 달러 값도 {won} 올라섰어.", "달러를 사는 값이 한 주 동안 {won} 올랐어."]}
# 끝에서 두 번째 줄 — '그래서 무슨 뜻'. 월요일에 무엇을 확인하겠다는 고지는 답글이 맡는다.
TH_MEAN = {"down": ["미국에서 반도체가 먼저 밀린 채 끝난 한 주야.",
                    "월요일 한국 반도체가 이어받는 숫자는 아래쪽에 있어.",
                    "한국 반도체 앞에 놓인 미국 숫자는 내려간 쪽이야.",
                    "한국 반도체가 건네받을 숫자가 위쪽은 아니었어."],
           "up": ["미국에서 반도체가 먼저 오른 채 끝난 한 주야.",
                  "월요일 한국 반도체가 이어받는 숫자는 위쪽에 있어.",
                  "한국 반도체 앞에 놓인 미국 숫자는 올라간 쪽이야.",
                  "한국 반도체가 건네받을 숫자가 아래쪽은 아니었어."],
           "flat": ["미국에서 반도체는 어느 쪽도 고르지 않고 끝났어.",
                    "월요일 한국 반도체가 이어받는 숫자는 뚜렷하지 않아.",
                    "한국 반도체 앞에 놓인 미국 숫자는 방향이 없어.",
                    "한국 반도체가 건네받을 숫자는 위도 아래도 아니야."]}
# 마지막 줄 — 독자에게 던지는 질문(JJ 2026-09-13). 피드에서 댓글이 붙은 글은 예외 없이 반말 + 질문으로 끝났다.
# 같은 질문이 반복되면 그게 곧 AI 티라, 여덟 가지를 주차·반도체 방향으로 돌린다.
# 독자의 손익·보유를 전제하는 질문('물렸지?')은 쓰지 않는다 — 무엇을 볼지, 어떻게 읽는지만 묻는다.
TH_ASK = ["너네는 월요일에 이 숫자부터 볼 거야?",
          "너희는 이번 주 숫자 중에 뭐가 제일 크게 보였어?",
          "월요일 아침에 제일 먼저 확인할 숫자는 뭐야?",
          "이 숫자 보고 제일 먼저 든 생각이 뭐야?",
          "너네는 이 돈이 어디로 갔다고 봐?",
          "다들 월요일엔 한국 반도체부터 볼 거야?",
          "다들 월요일 9시에 앱 켜서 확인해 볼 거야?",
          "너희는 이번 주 미국 숫자 중에 뭐가 제일 신경 쓰여?"]
REPLY_Q = {"down": ["삼성전자와 SK하이닉스에 외국인 돈이 들어오는지", "외국인이 반도체를 사는 쪽인지 파는 쪽인지",
                    "반도체에서 외국인이 산 돈과 판 돈 중 어느 쪽이 큰지"],
           "up": ["삼성전자와 SK하이닉스를 외국인이 계속 사는지", "외국인이 반도체를 더 사는지", "반도체로 외국인 돈이 더 들어오는지"],
           "flat": ["외국인이 반도체를 사는지 파는지", "삼성전자와 SK하이닉스를 외국인이 사는지 파는지", "외국인 돈이 반도체로 오는지 나가는지"]}
# 채널 고지 — 본문에서 빼고 답글이 맡는다(처음 보는 사람에게 첫 글부터 내부 사정을 들이밀지 않는다).
TH_REPLY_CH = ["주말엔 미국 한 주, 평일엔 오후 4시 30분에 한국 시장 마감 이야기를 해.",
               "주말에는 미국 한 주, 평일에는 오후 4시 30분 한국 시장 마감 이야기야.",
               "평일 오후 4시 30분엔 한국 시장 마감, 주말엔 미국 한 주 이야기야."]
TH_MAX_CHARS, TH_MAX_FIGS, TH_MAX_LINE = 430, 6, 34    # 한 호흡에 한 줄(JJ 2026-09-13): 한 줄 한도를 40 → 34자로 줄였다
TH_MIN_CHARS = 330                                          # 본문 330~430자(JJ 2026-09-13). 반말이 합니다체보다 줄마다 2~3자 짧아 위아래를 함께 맞췄다
TH_MIN_LINES, TH_MAX_LINES = 9, 19                          # 빈 줄 포함 본문 줄 수(태그 줄 제외). 마지막 질문 줄 한 묶음만큼 +2
# 반말 완결형(JJ 2026-09-13) — 끝 글자가 받침 없는 반말 종결(-어/-아/-야/-여/-봐/-와/-워/-해/-돼/-줘/-래)이거나 질문(?)이어야 한다.
# '-습니다/-입니다'는 더 이상 통과하지 않고(TH_FORMAL이 따로 잡는다), ㅁ 받침 축약 종결(음슴체)은 그대로 막는다.
TH_END = "[아어야여봐와워해돼줘래]"
TH_OPEN_END = re.compile(TH_END + r"\.$")                   # 첫 문단 두 줄은 완결형으로 끝난다
TH_END_OK = re.compile(TH_END + r"\.?$|\?$")                # 반말 완결형 또는 질문으로 끝나야 한다
TH_FORMAL = re.compile(r"습니다|입니다|겁니다|까요|셨나요|하세요|보세요|십시오")   # 합니다체가 남아 있으면 잡는다
TH_UM_END = re.compile(r"(?:팜|함|짐|음|봄|옴|뜀|감|김|남|임|삼|킴|섬|밈|림)\s*\.{0,3}$")   # 축약 종결(음슴체) — 반말이지 줄임말이 아니다
TH_CHAT = re.compile(r"[ㅋㅎㅠㅜ]")                            # 채팅 기호
from checks import jargon as _jargon          # 세 편이 같은 목록을 본다(checks/jargon.py)
TH_BAN_WORDS = _jargon.BAN
TH_JARGON = re.compile(r"확인\s*(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|\d+)\s*(?:개|번|건|가지)?\s*(?:중|가운데)|"
                       r"연속\s*\d+\s*일째|예고\s*검증|걸어\s*둔\s*확인")                # 우리끼리 쓰는 카운터
# 금융 용어 — 지나가던 사람이 뜻을 물어야 하는 낱말은 쓰지 않는다(JJ 2026-09-13). 영상 대본에는 적용하지 않는다.
TH_TERM = re.compile(r"순매수|순매도|매매동향|수급|정규장|체결|종가|기준가|시장가|공시|기타법인|자사주|거래대금|변동성|"
                     r"매도 우위|매수 우위|반등|조정|지수|업종|대형주|국장|증시|국채|채권|10년물|금리|유가|등락|약세|강세|호재|악재")
# 영상 대본에서 넘어온 표현을 쓰레드용으로 풀어 쓴다(대본 자체는 건드리지 않는다).
TH_PLAIN = (("공포지수", "시장의 불안을 재는 VIX"), ("달러 인덱스", "여러 나라 돈에 견준 달러 값"), ("원·달러", "달러 한 장 값"),
            ("국제유가", "기름값"), ("유가", "기름값"), ("금리", "이자"), ("지수", ""), ("증시", "주식"))


def _plain(s: str) -> str:
    """쓰레드 문장에서만 쓰는 쉬운 말 치환 — 영상 대본(scenes)에는 부르지 않는다."""
    for a_, b_ in TH_PLAIN:
        s = (s or "").replace(a_, b_)
    return re.sub(r"\s{2,}", " ", s or "").strip()


def _da(phrase: str) -> str:
    """'엔화 한 주 1.3% 약세' → '엔화가 한 주 1.3% 약해졌어' (반말 완결형 끝말 + 주어 조사).
    쓰레드 전용이다 — 영상 대본은 합니다체 그대로이고, 여기로 들어오는 건 훅 숫자 조각뿐이다."""
    head, sep, tail = (phrase or "").partition(" 한 주 ")
    s = f"{i_ga(head)} 한 주 {tail}" if sep else (phrase or "")
    for a_, b_ in (("급등", "크게 올랐어"), ("급락", "크게 내렸어"), ("상승", "올랐어"), ("하락", "내렸어"),
                   ("강세", "강해졌어"), ("약세", "약해졌어")):
        if s.endswith(a_):
            return s[:-len(a_)] + b_
    return s + ("이야" if bat(s) else "야")


def build_threads(C: dict, P: Pick, hook: dict, line1: str) -> tuple[str, str]:
    """(본문+태그, 첫 답글). 반말이다(JJ 2026-09-13) — 영상 대본·제목은 합니다체 그대로. 블록 사이에 빈 줄 —
    ①첫 문단 2줄(뉴스로 이미 본 미국 주식 방향 + 그것만 보면 놓치는 숫자) ②이번 주 숫자 ③질문 ④어디로 갔나 ⑤무슨 뜻 ⑥독자에게 던지는 질문.
    금융 용어는 쓰지 않는다 — 문장 뱅크가 이미 쉬운 말이고, 대본에서 넘어온 조각은 _plain으로 푼다."""
    S = C["S"]
    ix, r, o = S.get("IXIC"), S.get("US10Y"), S.get("WTI")
    k, kind = hook.get("k"), hook["kind"]
    s = S.get(k) if k in S else None
    head: list[str] = []
    ans: list[tuple[int, str]] = []                          # (우선순위, 줄) — 넘치면 뒤(큰 수)부터 뺀다

    def fit(slot, bank, extra_ok=None, **kw):
        """한 줄 TH_MAX_LINE자 이하 변형만(없으면 아무거나). extra_ok = 숫자 한도 등 추가 조건."""
        return P(slot, bank, ok=lambda t: len(t.format(**kw)) <= TH_MAX_LINE and (extra_ok is None or extra_ok(t)), **kw)
    if kind == "oil":
        up = _up(s["wp"])
        key = f"oil_x{up}" if hook.get("L") else f"oil{up}"
        head.append(fit(f"th.hook.{key}", TH_HOOK[key], L=f"{hook['L']:.0f}" if hook.get("L") else "", p=pct(s["wp"]), lvl=usd(s["last"])))
    elif kind == "rate":
        up = _up(s["wbp"])
        head.append(fit(f"th.hook.rate{up}", TH_HOOK[f"rate{up}"], lvl=ylv(s["last"]), pp=pp(s["wbp"])))
    elif kind == "idx_week":
        up, nm = _up(s["wp"]), TH_IDX_NAME[k]
        head.append(fit(f"th.hook.idx{up}", TH_HOOK[f"idx{up}"], nm=nm, nm_eun=eun(nm), nm_i_ga=i_ga(nm), p=pct(s["wp"])))
        if hook.get("same"):
            head.append(fit(f"th.hook2.same{up}", TH_SAME[up], nd=ND.get(s["n"], f"{s['n']}일")))
    elif kind == "idx_day":
        b = s["big"]
        up, nm = _up(b["pct"] or 0), TH_IDX_NAME[k]
        head.append(fit(f"th.hook.idxd{up}", TH_HOOK[f"idxd{up}"], nm=nm, nm_eun=eun(nm), nm_i_ga=i_ga(nm), wd=wd(b["d"]), p=pct(b["pct"])))
    else:
        v = _da(_plain(line1))
        head.append(fit("th.hook.gen", TH_HOOK["gen"], v=v, v2=v.replace(" 한 주 ", " "), v3=v.replace(" 한 주 ", " 일주일 사이 ")))
        head.append(fit("th.hook2.big", TH_BIGGEST))
    # 첫 문단 — ①뉴스로 이미 본 미국 주식 방향을 인정하고 ②그것만 보면 놓치는, 숫자가 든 사실을 바로 준다.
    seen = "flat" if not ix else "up" if ix["wp"] >= 0.5 else "down" if ix["wp"] <= -0.5 else "flat"
    sx, fx = S.get("SOX"), S.get("USDKRW")
    l2k = "SOX" if (sx and k != "SOX") else \
          "USDKRW" if (fx and k != "USDKRW" and abs(fx["last"] - fx["prev"]) >= 1) else \
          "IXIC" if (ix and k != "IXIC") else "US10Y" if (r and k != "US10Y") else ""
    if l2k:
        t2 = S[l2k]
        kw2 = {"p": pct(t2["wp"]), "v": ("내렸", "올랐")[_up(t2.get("wbp", t2["wp"]))], "pp": pp(t2.get("wbp") or 0),
               "lvl": ylv(t2["last"]) if l2k == "US10Y" else "",
               "won": f"{abs(t2['last'] - t2['prev']):.0f}원" if l2k == "USDKRW" else "",
               "vk": ("내렸", "올랐")[_up(t2["wp"])]}
        line2 = fit(f"th.line2.{l2k}", TH_LINE2[l2k], **kw2)
    else:                                                    # 건너올 숫자가 전부 훅이면 훅 문장이 2줄을 맡는다
        line2, head = head[0], head[1:]
    opening = [fit(f"th.open1.{seen}", TH_OPEN1[seen]), line2]
    if l2k in TH_LINE3:                                      # 2줄의 숫자가 무엇인지 곧바로 풀어 준다(숫자를 더 늘리지 않는다)
        opening.append(fit(f"th.line3.{l2k}", TH_LINE3[l2k]))
    qk = "macro" if kind in MACRO else "idx"
    q = fit(f"th.q.{qk}", TH_Q[qk])
    if ix and k != "IXIC" and l2k != "IXIC":
        same = ix["n"] >= 2 and len(set(ix["signs"])) == 1 and ix["signs"][0] != 0
        key = f"all{_up(ix['wp'])}" if same else "gen"
        ans.append((0, fit(f"th.ix.{key}", TH_IX[key], nd=ND.get(ix["n"], f"{ix['n']}일"), p=pct(ix["wp"]), v=("내렸", "올랐")[_up(ix["wp"])])))
    if kind != "rate" and l2k != "US10Y" and r and abs(r["wbp"]) >= 5:
        up = _up(r["wbp"])
        ans.append((2, fit(f"th.rate.{up}", TH_RATE[up], lvl=ylv(r["last"]), pp=pp(r["wbp"]))))
    elif kind != "oil" and o and abs(o["wp"]) >= 3:
        up = _up(o["wp"])
        ans.append((2, fit(f"th.oil.{up}", TH_OIL[up], p=pct(o["wp"]), lvl=usd(o["last"]))))
    secs = C["sectors"]
    if secs:
        n_up = sum(1 for x in secs if x["week_pct"] > 0)
        key = "none" if n_up == 0 else "one" if n_up == 1 else "all" if n_up == len(secs) else "mix"
        top, bot = secs[0]["name_ko"], secs[-1]["name_ko"]
        ans.append((1, fit(f"th.sector.{key}", TH_SECTOR[key], top=top, top_eul=eul(top), top_i_ga=i_ga(top),
                           bot=bot, bot_i_ga=i_ga(bot), bot_ieot=ieot(bot), tot=f"{KO_COUNT.get(len(secs), len(secs))} 개")))
    if fx and k != "USDKRW" and l2k != "USDKRW" and abs(fx["last"] - fx["prev"]) >= 3:
        ans.append((4, fit(f"th.fx.{_up(fx['wp'])}", TH_FX[_up(fx["wp"])], won=f"{abs(fx['last'] - fx['prev']):.0f}원")))
    if C["megas"] and kind != "mega":
        m = max(C["megas"], key=lambda x: abs(x["week_pct"]))
        nm = m.get("name_ko") or m.get("ticker")
        if nm:
            ans.append((3, fit("th.mega", TH_MEGA, nm=nm, nm_eun=eun(nm), nm_i_ga=i_ga(nm), p=pct(m["week_pct"]),
                               v=("내렸", "올랐")[_up(m["week_pct"])])))
    rt = 1 if (r and r["wbp"] >= 5) else 0
    ot = 1 if (o and o["wp"] >= 3) else 0
    rk = "rate_oil" if (rt and ot) else "rate" if rt else "oil" if ot else \
         "up" if (ix and ix["wp"] >= 0.5) else "down" if (ix and ix["wp"] <= -0.5) else "flat"
    sd = sox_dir(S)
    tail = [fit(f"th.read.{rk}", TH_READ[rk]), fit(f"th.mean.{sd}", TH_MEAN[sd])]
    ask = [fit(f"th.ask.{sd}", TH_ASK)]                      # 마지막 한 줄은 독자에게 던지는 질문이다(JJ 2026-09-13)
    if not ans:
        ans.append((0, fit("th.fall", TH_FALL)))

    def lay(items: list[tuple[int, str]]) -> list[str]:
        out: list[str] = []
        for blk in (opening, head, [q], [t for _, t in sorted(items)], tail, ask):
            if not blk:
                continue
            if out:
                out.append("")
            out += blk
        return out
    while len(ans) > 1 and (len("\n".join(lay(ans))) + len(TAG) + 1 > TH_MAX_CHARS
                            or count_figs("\n".join(lay(ans))) > TH_MAX_FIGS
                            or len(lay(ans)) + 1 > TH_MAX_LINES):
        ans.pop(max(range(len(ans)), key=lambda i: ans[i][0]))
    body = "\n".join(lay(ans))
    # 답글이 채널 고지·영상 링크·월요일 확인을 맡는다(본문 첫 글에는 넣지 않는다).
    reply = (f"영상 전체는 여기서 → {YT}\n"
             f"{P('th.reply.ch', TH_REPLY_CH)}\n"
             f"월요일 한국 시장에서는 {P(f'th.reply.{sd}', REPLY_Q[sd])} 볼 거야.")
    return body + "\n" + TAG, reply


# ── 검사 ──
def fixed_fragments() -> set[str]:
    """평일·토요일 대본 파일의 고정 문장 조각(한글 10자 이상) — 여기서 다시 쓰면 안 된다."""
    frags = set()
    for fn in ("narrate.py", "narrate_aplus.py", "threads_v4.py", "narrate_weekly.py", "polish.py"):
        p = os.path.join(JOBS, fn)
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for seg in re.split(r"\{[^}]*\}", node.value):
                    seg = seg.strip()
                    if len(re.findall("[가-힣]", seg)) >= 10:
                        frags.add(seg)
    return frags


def reuse_hits(text: str, frags: set[str] | None = None) -> list[str]:
    frags = fixed_fragments() if frags is None else frags
    t = (text or "").replace(SIGN_OFF, "")
    return sorted(f for f in frags if f in t)


def _threads_bans() -> list[str]:
    try:
        import threads_v4 as tv
        return tv.BAN_NEWS + tv.BAN_INTERP + tv.BAN_PROMO + tv.BAN_REC + tv.BAN_MONEY + tv.BAN_SCORE + tv.BAN_CAUSE + tv.BAN_FORECAST + \
            tv.BAN_CROWD + tv.BAN_PERSONA
    except Exception:                                           # noqa: BLE001 — 없으면 forbidden 검사만
        return []


def run_checks(out: dict) -> list[str]:
    why, total = [], 0
    frags = fixed_fragments()
    for s in out["scenes"]:
        t = s["tts"]
        total += len(t)
        if forbidden.find(t):
            why.append(f"{s['id']} forbidden {forbidden.find(t)}")
        c = [x for x in CERTAINTY if x in t]
        if c:
            why.append(f"{s['id']} certainty {c}")
        if count_figs(t) > MAX_FIGS:
            why.append(f"{s['id']} figures {count_figs(t)} > {MAX_FIGS}")
        if re.search(r"[()\[\]]", t):
            why.append(f"{s['id']} bracket in TTS")
        if s["id"] != "uw6" and not t.rstrip().endswith("?"):
            why.append(f"{s['id']} does not end on a question bridge")
        rh = reuse_hits(t, frags)
        if rh:
            why.append(f"{s['id']} reuses fixed sentence {rh}")
    if not out["scenes"][-1]["tts"].endswith(SIGN_OFF):
        why.append("uw6 sign-off missing")
    core = [t for t in re.sub(r"[?,]", " ", out["hook_parts"][1]).split() if len(t) >= 2]
    if not core or sum(1 for t in core if t in out["scenes"][0]["tts"]) < max(1, len(core) * 2 // 3):
        why.append("uw0 does not speak the screen question")
    if total > 1250:
        why.append(f"script long: {total} chars (~{total / 6.6:.0f}s)")
    ln = out["threads"].split("\n")
    if ln[-1] != TAG:
        why.append("threads tag not last")
    body = ln[:-1]
    live = [x.strip() for x in body if x.strip()]
    if not TH_MIN_LINES <= len(body) <= TH_MAX_LINES or len(ln) > TH_MAX_LINES + 1:
        why.append(f"threads {len(body)} body lines")
    if len(live) < 5:
        why.append(f"threads {len(live)} spoken lines")
    if len(out["threads"]) > TH_MAX_CHARS:
        why.append(f"threads {len(out['threads'])} chars")
    if len(out["threads"]) < TH_MIN_CHARS:                   # 350~420자 목표(JJ 2026-09-13) — 짧으면 읽을 거리가 없다
        why.append(f"threads short {len(out['threads'])} chars < {TH_MIN_CHARS}")
    if len(live) < 2 or not all(TH_OPEN_END.search(x) for x in live[:2]):
        why.append("threads 첫 문단 2줄 아님")
    elif not re.search(r"\d", live[1]):                      # 2줄은 숫자가 든 사실이어야 한다 — 빈손 예고 금지(JJ 2026-09-13)
        why.append(f"threads 2줄에 숫자 없음: {live[1]}")
    ro = reuse_hits("\n".join(live[:2]), frags)              # 평일·토요일 첫 문단과 같은 틀이면 세 편이 한 입에서 나온 티가 난다
    if ro:
        why.append(f"threads 첫 문단이 평일·토요일 문장과 겹침 {ro}")
    if count_figs("\n".join(body)) > TH_MAX_FIGS:
        why.append(f"threads figures {count_figs(chr(10).join(body))}")
    if not any(x.endswith("?") for x in live):
        why.append("threads 질문 줄 없음")
    if live and not live[-1].endswith("?"):                  # 마지막 줄은 독자에게 던지는 질문으로 닫는다(JJ 2026-09-13)
        why.append(f"threads 마지막 줄이 질문 아님: {live[-1]}")
    if len(live) >= 2 and live[-2].endswith("?"):            # 뜻은 질문 앞줄이 맡는다 — 질문 두 줄을 붙여 끝내지 않는다
        why.append(f"threads 끝 두 줄이 모두 질문: {live[-2]}")
    bans = _threads_bans()
    for x in live + [y.strip() for y in out["threads_reply"].split("\n")[1:] if y.strip()]:
        f = forbidden.find_threads(x)
        if f:
            why.append(f"threads forbidden {f}: {x}")
        b = [w for w in bans if w in x]
        if b:
            why.append(f"threads ban {b}: {x}")
        if not TH_END_OK.search(x):                         # 반말 완결형('-어/-야/-아')이나 질문으로 끝나야 한다
            why.append(f"threads 반말 완결형 아님: {x}")
        if TH_FORMAL.search(x):                             # 합니다체 잔재 — 쓰레드는 반말이다(영상 대본은 그대로)
            why.append(f"threads 합니다체: {x}")
        if TH_UM_END.search(x):                             # '팜/오름/봄' 같은 축약 종결 — 반말이지 줄임말이 아니다
            why.append(f"threads 축약 종결: {x}")
        if TH_CHAT.search(x):                               # 'ㅋㅋ' 'ㅎㅎ' 같은 채팅 기호
            why.append(f"threads 채팅 기호: {x}")
        if TH_JARGON.search(x):                             # 우리끼리 쓰는 카운터(확인 N번 중 M번 …)
            why.append(f"threads 내부 장치: {x}")
        tm = TH_TERM.search(x)                              # 금융 용어 — 뜻을 설명해야 하는 낱말은 빼고 뜻만 남긴다
        if tm:
            why.append(f"threads 금융 용어 '{tm.group(0)}': {x}")
        if len(x) > TH_MAX_LINE and x in live:
            why.append(f"threads line > {TH_MAX_LINE}: {x}")
    if forbidden.find(out["title"]) or re.match(r"^\s*\d", out["title"]):
        why.append(f"title: {out['title']}")
    return why


# ── 조립 ──
def prev_doc(build_date: str) -> dict | None:
    root = os.path.join(DATA, "weekly_us")
    if not os.path.isdir(root):
        return None
    for x in sorted((x for x in os.listdir(root) if x.isdigit() and x < build_date), reverse=True):
        p = os.path.join(root, x, OUT_NAME)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


_AUTO = object()


def build_us_weekly(w: dict, news, prev=_AUTO) -> dict:
    C = context(w)
    N = norm_news(news, w)
    bd = str(w.get("build_date") or (_d(C["we"]) + timedelta(days=2)).strftime("%Y%m%d"))
    P = Pick(bd, prev_doc(bd) if prev is _AUTO else prev)
    cands = hook_cands(C)
    if not cands:
        raise ValueError("computed_us_weekly: 말할 숫자가 없습니다")
    hook = cands[0]
    uw0, hook_parts = build_uw0(C, P, hook)
    sp = {"uw0": [(0, uw0)], "uw1": build_uw1(C, P)}
    sp["uw2"], used_rel = build_uw2(C, N, P, hook)
    has_ev = bool(pick_events(C, N, used_rel))
    oil = C["S"].get("WTI")
    if has_ev:
        q34 = P("uw3.q.oil", Q34_OIL) if (oil and oil["wp"] >= 3) else P("uw3.q", Q34)
    else:
        q34 = P("uw4.q", Q45)
    sp["uw3"] = build_uw3(C, P, hook, q34)
    sp["uw4"], evs = build_uw4(C, N, P, used_rel) if has_ev else ([], [])
    sp["uw5"] = build_uw5(C, P)
    sp["uw6"], syn = build_uw6(C, N, P)
    keep = assemble_all(sp)
    if any(len(p) > 2 and p[2] == "sox" for p in keep["uw1"]):           # 반도체 이야기를 uw1에서 했으면 uw6에서 되풀이하지 않는다
        keep["uw6"] = [p for p in keep["uw6"] if not (len(p) > 2 and p[2] == "semi")]
    mins = {"uw0": 5.0, "uw1": 7.0, "uw2": 8.0, "uw3": 8.0, "uw4": 7.0, "uw5": 7.0, "uw6": 8.0}
    scenes = []
    for sid in ("uw0", "uw1", "uw2", "uw3", "uw4", "uw5", "uw6"):
        t = " ".join(p[1] for p in keep.get(sid) or [])
        if t:
            scenes.append({"id": sid, "min": mins[sid], "tts": t, "sub": "" if sid == "uw0" else t})
    u2 = next((x["tts"] for x in scenes if x["id"] == "uw2"), "")
    used_rel = [n for n in used_rel if n.split()[-1] in u2 and ("근원" not in n or "근원" in u2)]
    title = build_title(C, P, hook, cands)
    threads, reply = build_threads(C, P, hook, hook_parts[0])
    total = sum(len(s["tts"]) for s in scenes)
    out = {"scenes": scenes, "title": title, "threads": threads, "threads_reply": reply, "hook_parts": hook_parts,
           "hook": {k: v for k, v in hook.items() if k != "m"}, "synthesis": syn, "complete": C["complete"], "missing": C["missing"],
           "sessions": C["sessions"], "events_used": [{"d": e["d"], "title": e["title"], "outlets": e["outlets"][:2], "conf": e["conf"]} for e in evs
                                                      if any(e["spoken"][:-1] in s["tts"] for s in scenes if s["id"] == "uw4")],
           "releases_used": used_rel, "variants": dict(sorted(P.used.items())), "bank_sizes": dict(sorted(P.sizes.items())),
           "build_date": bd, "total_chars": total, "est_sec": round(total / 7.5)}
    out["checks"] = run_checks(out)
    return out


def save(out: dict, build_date: str) -> str:
    d0 = os.path.join(DATA, "weekly_us", build_date)
    os.makedirs(d0, exist_ok=True)
    p = os.path.join(d0, OUT_NAME)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in out.items() if k != "bank_sizes"}, f, ensure_ascii=False, indent=1)
    return p


# ── 파일이 없을 때 시험용(메모리 안에서만): 일간 raw → 공유 스키마 모양 ──
def _load(p: str):
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def mock_week(build_date: str) -> dict:
    we = _d(f"{build_date[:4]}-{build_date[4:6]}-{build_date[6:]}") - timedelta(days=2)
    ws = we - timedelta(days=4)
    idx, pc = {}, {}
    for d0 in sorted(os.listdir(DATA)):
        j = _load(os.path.join(DATA, d0, "raw", "us_index.json")) if d0.isdigit() else None
        for k, v in ((j or {}).get("index") or {}).items():
            if v.get("close") is None:
                continue
            s = iso(v.get("session"))
            key = {"GSPC": "SPX"}.get(k, k)
            if s < ws.isoformat():
                pc[key] = v["close"]
            elif s <= we.isoformat():
                idx.setdefault(key, {"name_ko": v.get("name"), "days": {}})["days"][s] = v["close"]
    out, sess = {}, set((idx.get("IXIC") or {}).get("days", {}))
    for k, x in idx.items():
        out[k] = {"name_ko": x["name_ko"], "prev_close": pc.get(k),
                  "days": [{"d": d0, "close": c, "pct": None} for d0, c in sorted(x["days"].items()) if not sess or d0 in sess]}
    return {"week_start": ws.isoformat(), "week_end": we.isoformat(), "build_date": build_date, "idx": out, "rates": {}, "fx": {}, "commod": {},
            "sectors": [], "megacaps": [], "calendar_next": [], "news": []}


def mock_news(build_date: str) -> dict:
    """토요일 국장 주간용 기사 조사(data/weekly/<토>/news.json)에서 미국 항목만 + 기사 속 지표 결과(실제 vs 추정치)."""
    sat = (_d(f"{build_date[:4]}-{build_date[4:6]}-{build_date[6:]}") - timedelta(days=1)).strftime("%Y%m%d")
    j = _load(os.path.join(DATA, "weekly", sat, "news.json")) or {}
    events, rels = [], []
    for e in j.get("events") or []:
        t = e.get("title", "")
        if re.search(r"\(\d{1,2}/\d{1,2}\)\s*$", t) or (US_RE.search(t) and not KR_RE.search(t)) or GEO_RE.search(t):
            events.append(e)
        m = re.search(r"미 (\d{1,2})월 (PPI|CPI)는 (전년|전월) 대비 ([\d.]+)%로 시장 추정치\(([\d.]+)%\)", e.get("what", ""))
        dm = re.search(r"\((\d{1,2})/(\d{1,2})\)\s*$", t)
        if m and dm:
            rels.append({"name_ko": f"{m.group(1)}월 {'생산자물가' if m.group(2) == 'PPI' else '소비자물가'}", "actual": float(m.group(4)),
                         "expected": float(m.group(5)), "unit": "%", "basis": f"{m.group(3)} 대비",
                         "date": f"{build_date[:4]}-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}", "sources": e.get("sources"), "confidence": e.get("confidence")})
    return {"events": events, "releases": rels}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    bd = args[0] if args else "20260913"
    base = os.path.join(DATA, "weekly_us", bd)
    w = _load(os.path.join(base, "computed_us_weekly.json"))
    wsrc = os.path.join(base, "computed_us_weekly.json") if w else "in-memory mock (data/<d>/raw/us_index.json)"
    w = w or mock_week(bd)
    news = _load(os.path.join(base, "news.json"))
    nsrc = os.path.join(base, "news.json") if news else f"in-memory mock (data/weekly/*/news.json 미국 항목)"
    news = news if news is not None else mock_news(bd)
    out = build_us_weekly(w, news)
    print(f"data : {wsrc}\nnews : {nsrc}\nsessions {out['sessions']} complete={out['complete']} missing={out['missing']}")
    print(f"hook : {out['hook']}  synthesis: {out['synthesis']}")
    print(f"events used: {out['events_used']}\nreleases used: {out['releases_used']}")
    print("=" * 70)
    print("hook_parts:", out["hook_parts"])
    for s in out["scenes"]:
        print(f"\n[{s['id']}] min {s['min']}s · {len(s['tts'])}자 · 숫자 {count_figs(s['tts'])}개")
        print(s["tts"])
    print("\n" + "=" * 70)
    print("TITLE :", out["title"])
    print("THREADS:\n" + out["threads"])
    print(f"({len(out['threads'])}자)")
    print("REPLY:\n" + out["threads_reply"])
    print("=" * 70)
    print(f"total {out['total_chars']}자 ≈ {out['est_sec']}초 · checks: {out['checks'] or 'none'}")
    small = {k: n for k, n in out["bank_sizes"].items() if n < 3}
    print("slots:", len(out["bank_sizes"]), "| banks < 3 variants:", small or "none")
    out2 = build_us_weekly(w, news, prev=out)
    same = [k for k, v in out2["variants"].items() if out["variants"].get(k) == v and out2["bank_sizes"].get(k, 1) > 1]
    print(f"rotation vs this week as 'previous file': {len(out2['variants']) - len(same)}/{len(out2['variants'])} slots changed; unchanged {same or 'none'}"
          f" · checks: {out2['checks'] or 'none'}")
    print("  next-week title :", out2["title"])
    print("  next-week uw0   :", out2["scenes"][0]["tts"])
    if "--save" in sys.argv:
        print("saved", save(out, bd))
