"""미국 주간(일요일 12:00 KST 영상) 데이터 — 이번 주 세션 종가 vs 직전 주 마지막 세션 종가.

build(week_end_iso, build_date) -> dict  → data/weekly_us/<build_date>/computed_us_weekly.json

소스(전부 무키·공공 또는 공개 API):
  지수·ETF·개별주·환율·원자재  Yahoo Finance chart API (collect_us_index 와 같은 BASE/헤더)
  금리 2년·10년              U.S. Treasury 일별 par yield curve XML (collect_us 와 같은 소스, 일간 영상과 같은 숫자)
                             · 10년물은 Yahoo ^TNX 로 교차검증/폴백. 2년물은 Yahoo 에 현물 지수가 없다(^UST2Y 없음,
                               2YY=F 는 마이크로 선물이라 체결이 드물어 며칠씩 같은 값 → 쓰지 않음).
  다음 주 일정               Fed FOMC 캘린더, BLS .ics, Census 지표 캘린더, Fed G.17 발표일, BEA 발표일 JSON,
                             TreasuryDirect 입찰 예정, Nasdaq 실적 캘린더(시총 1,000억달러 이상), 만기·청구건수 규칙

규칙
  - 세션 달력 = ^GSPC 의 '확정' 일봉(세션일+1일 07:00 KST 이후). 월요일 휴장(노동절 등)은 holidays 로 빠진다.
  - prev_close = 주 시작 전 마지막 세션(예: 금 2026-09-04) 종가. 일봉이 휴장일에도 있는 시리즈(환율·VIX)는
    세션 달력에 없는 날을 버린다 → days[0].pct 는 직전 금요일 종가 대비(월요일 움직임 포함).
  - 아직 확정 안 된 세션(예: 금요일 장이 안 끝난 상태)은 빼고 _meta.missing_sessions 에 표시. 일요일 재실행 시 자동으로 채워진다.
  - week_high/week_low = 이번 주 '종가' 기준 최고/최저(장중 고저 아님).
  - 스키마 밖 정보(출처·결측·교차검증)는 _meta 하나에만 넣는다. 금리 days 에는 chg_bp 를 추가.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from _common import DATA, save_json
from collect_us import FOMC_2026, _et_offset
from collect_us_index import BASE as YF_BASE, KST, UA as YF_UA

OUT_ROOT = DATA / "weekly_us"
TIMEOUT = 25.0
GOV_UA = {"User-Agent": "market-close-brief/0.1 (jeff.gadget10000@gmail.com)"}   # collect_us 와 동일
WEB_UA = {"User-Agent": YF_UA["User-Agent"], "Accept": "text/html,application/json,*/*", "Accept-Language": "en-US,en;q=0.9"}

# ── 심볼 ────────────────────────────────────────────────────────────────────────
IDX = [("SPX", "^GSPC", "S&P500"), ("IXIC", "^IXIC", "나스닥 종합"), ("DJI", "^DJI", "다우"),
       ("SOX", "^SOX", "필라델피아 반도체"), ("VIX", "^VIX", "VIX(변동성지수)")]
FX = [("DXY", "DX-Y.NYB", "달러인덱스"), ("USDJPY", "JPY=X", "엔·달러 환율"), ("USDKRW", "KRW=X", "원·달러 환율")]
COMMOD = [("WTI", "CL=F", "WTI 유가"), ("GOLD", "GC=F", "금값")]
# 섹터 이름은 collect_us_kiwoom.SECTOR_ETF 와 같은 표기(키움 모듈은 백엔드 의존이라 임포트하지 않음)
SECTORS = [("XLK", "기술"), ("XLF", "금융"), ("XLE", "에너지"), ("XLV", "헬스케어"), ("XLY", "경기소비재"),
           ("XLI", "산업재"), ("XLU", "유틸리티"), ("XLP", "필수소비재"), ("XLB", "소재"), ("XLRE", "부동산"),
           ("XLC", "통신·미디어")]
MEGACAPS = [("NVDA", "엔비디아"), ("AAPL", "애플"), ("MSFT", "마이크로소프트"), ("GOOGL", "알파벳"), ("AMZN", "아마존"),
            ("META", "메타"), ("TSLA", "테슬라"), ("AVGO", "브로드컴"), ("AMD", "AMD"), ("MU", "마이크론")]
RATES = [("US2Y", "BC_2YEAR", None, "미국 2년물 국채금리"), ("US10Y", "BC_10YEAR", "^TNX", "미국 10년물 국채금리")]
CAL_SYMS = ["^GSPC", "^IXIC", "^DJI"]          # 세션 달력 후보(앞에서부터)

# NYSE 휴장일(공식 공표). 데이터로도 추론하지만(뒤에 봉이 있는데 그날만 없으면 휴장), 미래 요일 분류용으로 둔다.
NYSE_HOLIDAYS = {
    "2026-01-01": "New Year's Day", "2026-01-19": "Martin Luther King Jr. Day", "2026-02-16": "Presidents' Day",
    "2026-04-03": "Good Friday", "2026-05-25": "Memorial Day", "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)", "2026-09-07": "Labor Day", "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
    "2027-01-01": "New Year's Day", "2027-01-18": "Martin Luther King Jr. Day", "2027-02-15": "Presidents' Day",
    "2027-03-26": "Good Friday", "2027-05-31": "Memorial Day", "2027-06-18": "Juneteenth (observed)",
    "2027-07-05": "Independence Day (observed)", "2027-09-06": "Labor Day", "2027-11-25": "Thanksgiving Day",
    "2027-12-24": "Christmas Day (observed)",
}
HOLIDAY_KO = {"Labor Day": "노동절", "Thanksgiving Day": "추수감사절", "Good Friday": "성금요일", "Memorial Day": "메모리얼데이",
              "Juneteenth": "준틴스", "Juneteenth (observed)": "준틴스(대체)", "Independence Day (observed)": "독립기념일(대체)",
              "Christmas Day": "성탄절", "Christmas Day (observed)": "성탄절(대체)", "New Year's Day": "새해 첫날",
              "Martin Luther King Jr. Day": "마틴 루서 킹 데이", "Presidents' Day": "대통령의 날"}


# ── 날짜 유틸 ──────────────────────────────────────────────────────────────────
def _d(s: str) -> date:
    return date.fromisoformat(s[:10]) if "-" in s else datetime.strptime(s, "%Y%m%d").date()


def _iso(x: date) -> str:
    return x.isoformat()


def _final_at(d: date, kind: str) -> datetime:
    """해당 날짜 일봉이 확정되는 KST 시각. eq: 16:00 ET 마감 + 여유(= 다음날 07:00 KST, 겨울엔 17:00 ET),
    fut: CME/ICE 17:00 ET 세션 끝 + 여유, fx: 야후 환율 일봉은 런던 자정에 닫힘(08:00~09:00 KST) + 여유."""
    hour = {"eq": 7, "fut": 8, "fx": 10}[kind]
    return datetime(d.year, d.month, d.day, hour, tzinfo=KST) + timedelta(days=1)


def _kind(meta: dict) -> str:
    it = (meta.get("instrumentType") or "").upper()
    if it == "CURRENCY":
        return "fx"
    if it == "FUTURE" or (meta.get("exchangeName") or "") == "NYB":   # DX-Y.NYB 는 ICE 선물 시간대
        return "fut"
    return "eq"


# ── Yahoo ──────────────────────────────────────────────────────────────────────
def _bars(res: dict) -> list[tuple[date, float]]:
    """Yahoo result → [(현지 날짜, close)] 오름차순. collect_us_index._rows 와 같지만 날짜를 '가장 가까운 자정'으로
    반올림한다: gmtoffset 은 '현재' 오프셋이라 서머타임 경계를 넘는 창에서 런던 자정(23:00 UTC) 봉이 하루 밀리는 걸 막는다."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    closes = q.get("close") or [None] * len(ts)
    off = int((res.get("meta") or {}).get("gmtoffset") or 0)
    out: dict[date, float] = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        local = datetime.fromtimestamp(t, timezone.utc) + timedelta(seconds=off)
        day = local.date() + (timedelta(days=1) if local.hour >= 12 else timedelta(0))
        out[day] = float(c)                       # 같은 날짜 중복이면 마지막 것
    return sorted(out.items())


def _yf(hc: httpx.Client, sym: str, start: date, end: date) -> tuple[list[tuple[date, float]], dict]:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp())
    last_err = None
    for attempt in range(3):
        try:
            r = hc.get(f"{YF_BASE}{sym}", params={"period1": p1, "period2": p2, "interval": "1d"})
            if r.status_code == 429:
                raise RuntimeError("429 too many requests")
            r.raise_for_status()
            chart = r.json().get("chart") or {}
            if chart.get("error"):
                raise RuntimeError(f"yahoo error: {chart['error']}")
            res = (chart.get("result") or [None])[0]
            if not res:
                raise RuntimeError("empty result")
            return _bars(res), res.get("meta") or {}
        except Exception as e:  # 429·일시 오류는 잠깐 쉬고 재시도
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"{type(last_err).__name__}: {last_err}"[:200])


# ── 시리즈 계산 ────────────────────────────────────────────────────────────────
def _series(bars: list[tuple[date, float]], sessions: list[date], prev_d: date, name_ko: str, nd: int = 2,
            bp: bool = False) -> dict:
    """bars(확정분만) → 스키마 한 칸. pct 는 반올림 전 값으로 계산."""
    by = dict(bars)
    prev_c = None
    cands = [d for d in by if d <= prev_d and (prev_d - d).days <= 5]
    if cands:
        prev_c = by[max(cands)]
    days, last = [], prev_c
    for s in sessions:
        c = by.get(s)
        if c is None:
            continue
        row = {"d": _iso(s), "close": round(c, nd), "pct": round((c / last - 1) * 100, 2) if last else None}
        if bp:
            row["chg_bp"] = round((c - last) * 100) if last is not None else None
        days.append(row)
        last = c
    closes = [by[_d(x["d"])] for x in days]
    out = {"name_ko": name_ko, "prev_close": round(prev_c, nd) if prev_c is not None else None, "days": days,
           "week_pct": round((closes[-1] / prev_c - 1) * 100, 2) if closes and prev_c else None,
           "week_high": round(max(closes), nd) if closes else None,
           "week_low": round(min(closes), nd) if closes else None}
    if bp:
        out["week_chg_bp"] = round((closes[-1] - prev_c) * 100) if closes and prev_c is not None else None
    return out


# ── 금리: U.S. Treasury par yield curve ───────────────────────────────────────
def _treasury(months: list[str]) -> dict[str, list[tuple[date, float]]]:
    """{'BC_2YEAR': [(date, %)], 'BC_10YEAR': [...]} — 월별 XML (collect_us._treasury 와 같은 URL)."""
    out: dict[str, dict[date, float]] = {"BC_2YEAR": {}, "BC_10YEAR": {}}
    for ym in months:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
               f"?data=daily_treasury_yield_curve&field_tdr_date_value_month={ym}")
        r = httpx.get(url, headers=GOV_UA, timeout=TIMEOUT)
        r.raise_for_status()
        for e in re.findall(r"<entry>(.*?)</entry>", r.text, flags=re.S):
            nd = re.search(r"NEW_DATE[^>]*>([\d\-T:]+)<", e)
            if not nd:
                continue
            day = date.fromisoformat(nd.group(1)[:10])
            for f in out:
                m = re.search(rf"{f}[^>]*>([\d.]+)<", e)
                if m:
                    out[f][day] = float(m.group(1))
    return {f: sorted(v.items()) for f, v in out.items()}


# ── 다음 주 일정 ───────────────────────────────────────────────────────────────
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def _kst(d: date, hhmm: str) -> str:
    dt = datetime.strptime(f"{d.isoformat()} {hhmm}", "%Y-%m-%d %H:%M")
    return (dt + timedelta(hours=_et_offset(dt))).strftime("%Y-%m-%d %H:%M")


def _ev(d: date, hhmm: str | None, event_ko: str, src: str) -> dict:
    return {"date": _iso(d), "event_ko": event_ko, "kst": _kst(d, hhmm) if hhmm else None, "src": src}


def _cal_fomc(lo: date, hi: date, errs: list) -> list[dict]:
    meetings: list[tuple[date, date, bool]] = []
    try:
        r = httpx.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=WEB_UA, timeout=TIMEOUT)
        r.raise_for_status()
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
        for y in sorted({lo.year, hi.year}):
            i = t.find(f"{y} FOMC Meetings")
            if i < 0:
                continue
            j = t.find("FOMC Meetings", i + 20)
            seg = t[i: j if j > 0 else len(t)]
            mp = "|".join(MONTHS)
            for m in re.finditer(rf"\b({mp})(?:/({mp}))? (\d{{1,2}})-(\d{{1,2}})(\*?)", seg):
                m1 = MONTHS.index(m.group(1)) + 1
                m2 = MONTHS.index(m.group(2)) + 1 if m.group(2) else m1
                meetings.append((date(y, m1, int(m.group(3))), date(y, m2, int(m.group(4))), m.group(5) == "*"))
    except Exception as e:
        errs.append(f"fomc page: {type(e).__name__}: {e}"[:160])
    src = "Federal Reserve FOMC calendar"
    if not meetings:  # 폴백: collect_us.FOMC_2026 ("2026-09-15/16"), SEP 는 3·6·9·12월
        src = "collect_us.FOMC_2026"
        for s in FOMC_2026:
            a = date.fromisoformat(s[:10])
            b = a.replace(day=int(s.split("/")[1])) if int(s.split("/")[1]) > a.day else a + timedelta(days=1)
            meetings.append((a, b, a.month in (3, 6, 9, 12)))
    out = []
    for a, b, sep in meetings:
        if lo <= b <= hi:
            span = f"{a.month}/{a.day}~{b.day}" if a.month == b.month else f"{a.month}/{a.day}~{b.month}/{b.day}"
            txt = f"FOMC 금리 결정 발표({span} 회의)" + (" · 경제전망(점도표) 공개" if sep else "")
            out.append(_ev(b, "14:00", txt, src))
    return out


BLS_KO = [("Employment Situation", "고용보고서(비농업 고용·실업률)"), ("Consumer Price Index", "소비자물가지수(CPI)"),
          ("Producer Price Index", "생산자물가지수(PPI)"), ("Job Openings and Labor Turnover", "구인·이직 보고서(JOLTS)"),
          ("Import and Export Price", "수입·수출 물가지수"), ("Employment Cost Index", "고용비용지수(ECI)"),
          ("Productivity and Costs", "생산성·단위노동비용")]


def _cal_bls(lo: date, hi: date, errs: list) -> list[dict]:
    try:
        r = httpx.get("https://www.bls.gov/schedule/news_release/bls.ics", headers=GOV_UA, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        errs.append(f"bls ics: {type(e).__name__}: {e}"[:160])
        return []
    out = []
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", r.text, flags=re.S):
        m = re.search(r"DTSTART[^:]*:(\d{8})T?(\d{4})?", ev)
        s = re.search(r"SUMMARY:(.*)", ev)
        if not m or not s:
            continue
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        name = s.group(1).strip().replace("\\,", ",")
        ko = next((k for en, k in BLS_KO if en in name), None)
        if ko and lo <= d <= hi:
            tm = m.group(2) or "0830"
            out.append(_ev(d, f"{tm[:2]}:{tm[2:]}", ko, "BLS release calendar"))
    return out


CENSUS_KO = [("Advance Monthly Sales for Retail", "소매판매"), ("New Residential Construction", "주택 착공·건축허가"),
             ("New Residential Sales", "신규 주택 판매"), ("Advance Report on Durable Goods", "내구재 주문")]


def _cal_census(lo: date, hi: date, errs: list) -> list[dict]:
    try:
        r = httpx.get("https://www.census.gov/economic-indicators/calendar-listview.html", headers=WEB_UA,
                      timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        errs.append(f"census: {type(e).__name__}: {e}"[:160])
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, flags=re.S):
        key = re.search(r'sorttable_customkey="(\d{12})"', tr)
        if not key:
            continue
        tds = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if not tds:
            continue
        ko = next((k for en, k in CENSUS_KO if tds[0].startswith(en)), None)
        d = datetime.strptime(key.group(1)[:8], "%Y%m%d").date()
        if ko and lo <= d <= hi:
            per = tds[3] if len(tds) > 3 else ""
            pm = re.match(rf"({'|'.join(MONTHS)}) \d{{4}}", per)
            label = f"{MONTHS.index(pm.group(1)) + 1}월 {ko}" if pm else ko
            out.append(_ev(d, f"{key.group(1)[8:10]}:{key.group(1)[10:]}", label, "U.S. Census economic indicator calendar"))
    return out


def _cal_g17(lo: date, hi: date, errs: list) -> list[dict]:
    try:
        r = httpx.get("https://www.federalreserve.gov/releases/g17/release_dates.htm", headers=WEB_UA, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        errs.append(f"g17: {type(e).__name__}: {e}"[:160])
        return []
    t = re.sub(r"<[^>]+>", " ", r.text)
    days = {date(int(y), MONTHS.index(mo) + 1, int(dd))
            for dd, mo, y in re.findall(rf"(\d{{1,2}})-({'|'.join(MONTHS)})-(\d{{4}})", t)}
    return [_ev(d, "09:15", "산업생산(연준 G.17)", "Federal Reserve G.17 release dates") for d in sorted(days) if lo <= d <= hi]


def _cal_bea(lo: date, hi: date, errs: list) -> list[dict]:
    want = {"Gross Domestic Product": "GDP(국내총생산)", "Personal Income and Outlays": "개인소득·소비지출(PCE 물가)"}
    try:
        j = httpx.get("https://apps.bea.gov/API/signup/release_dates.json", headers=WEB_UA, timeout=TIMEOUT).json()
    except Exception as e:
        errs.append(f"bea: {type(e).__name__}: {e}"[:160])
        return []
    out = []
    for k, ko in want.items():
        v = j.get(k)
        for s in (v.get("release_dates") or []) if isinstance(v, dict) else []:
            utc = datetime.fromisoformat(s).replace(tzinfo=None)
            # _et_offset = ET→KST 시차(EDT 13 / EST 14) → ET = UTC + (9 - 시차)
            et = utc + timedelta(hours=9 - _et_offset(utc - timedelta(hours=4)))
            if lo <= et.date() <= hi:
                out.append(_ev(et.date(), et.strftime("%H:%M"), ko, "BEA release schedule"))
    return out


def _cal_auctions(lo: date, hi: date, errs: list) -> list[dict]:
    try:
        rows = httpx.get("https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json", headers=WEB_UA,
                         timeout=TIMEOUT).json()
    except Exception as e:
        errs.append(f"treasurydirect: {type(e).__name__}: {e}"[:160])
        return []
    out = []
    for x in rows or []:
        term = x.get("originalSecurityTerm") or x.get("securityTerm") or ""
        if x.get("securityType") == "Bill" or term not in ("10-Year", "20-Year", "30-Year"):
            continue
        d = date.fromisoformat((x.get("auctionDate") or "")[:10])
        if not lo <= d <= hi:
            continue
        yrs = term.split("-")[0]
        kind = "물가연동국채(TIPS)" if (x.get("tips") == "Yes") else "국채"
        tm = datetime.strptime(x.get("closingTimeCompetitive") or "01:00 PM", "%I:%M %p").strftime("%H:%M")
        out.append(_ev(d, tm, f"미 {yrs}년물 {kind} 입찰" + ("(재발행)" if x.get("reopening") == "Yes" else ""),
                       "TreasuryDirect upcoming auctions"))
    return out


EARN_KO = {t: k for t, k in MEGACAPS} | {"ORCL": "오라클", "ADBE": "어도비", "AVGO": "브로드컴", "COST": "코스트코",
                                          "NFLX": "넷플릭스", "JPM": "JP모건", "LLY": "일라이릴리", "WMT": "월마트",
                                          "FDX": "페덱스", "NKE": "나이키", "MU": "마이크론", "TSM": "TSMC"}


def _cal_earnings(lo: date, hi: date, errs: list, min_cap: float = 100e9) -> list[dict]:
    out = []
    d = lo
    while d <= hi:
        try:
            j = httpx.get(f"https://api.nasdaq.com/api/calendar/earnings?date={d.isoformat()}", headers=WEB_UA,
                          timeout=TIMEOUT).json()
            for x in ((j.get("data") or {}).get("rows")) or []:
                try:
                    cap = float((x.get("marketCap") or "0").replace("$", "").replace(",", ""))
                except ValueError:
                    cap = 0
                if cap < min_cap:
                    continue
                sym = x.get("symbol") or ""
                when = {"time-pre-market": "개장 전", "time-after-hours": "마감 후"}.get(x.get("time") or "", "")
                name = EARN_KO.get(sym) or (x.get("name") or sym)
                out.append({"date": d.isoformat(), "event_ko": f"{name} 실적 발표" + (f"({when})" if when else ""),
                            "kst": None, "src": "Nasdaq earnings calendar"})
        except Exception as e:
            errs.append(f"nasdaq earnings {d}: {type(e).__name__}: {e}"[:160])
        d += timedelta(days=1)
    return out


def _cal_rules(lo: date, hi: date) -> list[dict]:
    """정해진 규칙: 주간 실업수당 청구(목 08:30 ET, 목요일 휴장이면 수요일), 분기 선물·옵션 동시 만기(3·6·9·12월 셋째 금요일), 휴장."""
    out = []
    thu = lo + timedelta(days=(3 - lo.weekday()) % 7)
    if thu <= hi:
        day = thu - timedelta(days=1) if _iso(thu) in NYSE_HOLIDAYS else thu
        out.append(_ev(day, "08:30", "주간 신규 실업수당 청구건수", "U.S. DOL weekly claims (매주 목요일)"))
    d = lo
    while d <= hi:
        if d.weekday() == 4 and d.month in (3, 6, 9, 12) and 15 <= d.day <= 21:
            day = d - timedelta(days=1) if _iso(d) in NYSE_HOLIDAYS else d
            out.append(_ev(day, None, "분기 선물·옵션 동시 만기(쿼드러플 위칭)", "만기 규칙: 3·6·9·12월 셋째 금요일"))
        if _iso(d) in NYSE_HOLIDAYS:
            nm = NYSE_HOLIDAYS[_iso(d)]
            out.append(_ev(d, None, f"미국 증시 휴장({HOLIDAY_KO.get(nm, nm)})", "NYSE holiday calendar"))
        d += timedelta(days=1)
    return out


def calendar_next(week_end: date, errs: list) -> list[dict]:
    lo = week_end - timedelta(days=week_end.weekday()) + timedelta(days=7)      # 다음 주 월요일
    hi = lo + timedelta(days=4)
    evs: list[dict] = []
    for fn in (_cal_fomc, _cal_bls, _cal_census, _cal_g17, _cal_bea, _cal_auctions, _cal_earnings):
        try:
            evs += fn(lo, hi, errs)
        except Exception as e:
            errs.append(f"{fn.__name__}: {type(e).__name__}: {e}"[:160])
    evs += _cal_rules(lo, hi)
    seen, uniq = set(), []
    for e in sorted(evs, key=lambda x: (x["date"], x["kst"] or "99")):
        k = (e["date"], e["event_ko"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


# ── 교차검증: 일간 raw(us_index.json / us.json) ───────────────────────────────
def _crosscheck(out: dict, lo: date, hi: date) -> dict:
    keymap = {"GSPC": "SPX", "IXIC": "IXIC", "DJI": "DJI", "SOX": "SOX", "VIX": "VIX"}
    diffs, y10 = [], []
    d = lo
    while d <= hi + timedelta(days=4):
        raw = DATA / d.strftime("%Y%m%d") / "raw"
        try:
            ui = json.loads((raw / "us_index.json").read_text(encoding="utf-8")) if (raw / "us_index.json").exists() else None
            if ui and ui.get("session"):
                s_iso = _iso(_d(ui["session"]))
                for rk, k in keymap.items():
                    it = (ui.get("index") or {}).get(rk) or {}
                    row = next((x for x in out["idx"].get(k, {}).get("days", []) if x["d"] == s_iso), None)
                    if row and it.get("close") is not None:
                        diffs.append({"d": s_iso, "k": k, "weekly": row["close"], "daily_raw": it["close"],
                                      "diff": round(row["close"] - it["close"], 2)})
            us = json.loads((raw / "us.json").read_text(encoding="utf-8")) if (raw / "us.json").exists() else None
            tre = (us or {}).get("treasury") or {}
            if tre.get("date") and tre.get("y10") is not None:
                row = next((x for x in out["rates"]["US10Y"]["days"] if x["d"] == tre["date"]), None)
                if row:
                    y10.append({"d": tre["date"], "weekly": row["close"], "daily_raw": tre["y10"]})
        except Exception:
            pass
        d += timedelta(days=1)
    return {"idx_vs_daily_raw": diffs, "idx_max_abs_diff": max((abs(x["diff"]) for x in diffs), default=None),
            "us10y_vs_daily_raw": y10}


# ── 본체 ──────────────────────────────────────────────────────────────────────
def build(week_end_iso: str, build_date: str) -> dict:
    now = datetime.now(KST)
    we = _d(week_end_iso)
    mon = we - timedelta(days=we.weekday())
    start = mon - timedelta(days=14)
    end = min(we + timedelta(days=2), now.date() + timedelta(days=1))
    errs: list[str] = []
    notes: dict[str, str] = {}
    sym_meta: dict[str, dict] = {}

    fetched: dict[str, list[tuple[date, float]]] = {}
    with httpx.Client(headers=YF_UA, timeout=httpx.Timeout(TIMEOUT), follow_redirects=True) as hc:
        allsyms = ([s for _, s, _ in IDX] + ["^TNX"] + [s for _, s, _ in FX] + [s for _, s, _ in COMMOD]
                   + [s for s, _ in SECTORS] + [s for s, _ in MEGACAPS])
        for sym in allsyms:
            try:
                bars, meta = _yf(hc, sym, start, end)
                kind = _kind(meta)
                fetched[sym] = [(d, c) for d, c in bars if now >= _final_at(d, kind)]   # 확정 봉만
                sym_meta[sym] = {"kind": kind, "exchange": meta.get("exchangeName"), "type": meta.get("instrumentType"),
                                 "currency": meta.get("currency")}
            except Exception as e:
                fetched[sym] = []
                errs.append(f"yahoo {sym}: {e}"[:200])
            time.sleep(0.15)

    # 세션 달력
    cal_sym = next((s for s in CAL_SYMS if fetched.get(s)), None)
    cal = [d for d, _ in fetched.get(cal_sym or "", [])]
    sessions = [d for d in cal if mon <= d <= we]
    prior = [d for d in cal if d < mon]
    prev_d = max(prior) if prior else None
    holidays, expected, missing = [], [], []
    d = mon
    while d <= we:
        if d.weekday() < 5:
            later = any(x > d for x in cal)
            if _iso(d) in NYSE_HOLIDAYS or (later and d not in cal):
                holidays.append({"d": _iso(d), "name": NYSE_HOLIDAYS.get(_iso(d), "no session (inferred)")})
            else:
                expected.append(d)
                if d not in sessions:
                    fa = _final_at(d, "eq")
                    missing.append({"d": _iso(d), "reason": (f"pending: not final until {fa.strftime('%Y-%m-%d %H:%M')} KST"
                                                             if now < fa else "no bar from Yahoo")})
        d += timedelta(days=1)
    week_start = sessions[0] if sessions else (expected[0] if expected else mon)
    if prev_d is None:
        errs.append("prev session not found in calendar window")
        prev_d = mon - timedelta(days=3)

    def ser(sym: str, name: str, nd: int = 2) -> dict:
        s = _series(fetched.get(sym, []), sessions, prev_d, name, nd)
        if s["days"] and s["days"][-1]["d"] != (_iso(sessions[-1]) if sessions else None):
            notes[sym] = f"last final bar {s['days'][-1]['d']} (behind session calendar)"
        return s

    idx = {k: ser(s, n) for k, s, n in IDX}
    fx = {k: ser(s, n) for k, s, n in FX}
    commod = {k: ser(s, n) for k, s, n in COMMOD}
    for s in [s for _, s, _ in IDX + FX + COMMOD]:     # 휴장일에도 봉이 있는 시리즈(환율·VIX 등) 기록
        extra = [x for x, _ in fetched.get(s, []) if mon <= x <= we and x not in sessions]
        if extra:
            notes[s] = f"bars on non-session days ignored: {[_iso(x) for x in extra]}"

    # 금리: Treasury 우선(일간 영상과 같은 숫자), 10년물은 ^TNX 폴백·교차검증
    months = sorted({prev_d.strftime("%Y%m"), we.strftime("%Y%m")})
    try:
        tre = _treasury(months)
    except Exception as e:
        tre = {"BC_2YEAR": [], "BC_10YEAR": []}
        errs.append(f"treasury: {type(e).__name__}: {e}"[:200])
    rates, rate_src = {}, {}
    for k, field, ysym, name in RATES:
        s = _series(tre.get(field, []), sessions, prev_d, name, 2, bp=True)
        rate_src[k] = "U.S. Treasury daily par yield curve"
        if (not s["days"] or s["prev_close"] is None) and ysym and fetched.get(ysym):
            s = _series(fetched[ysym], sessions, prev_d, name, 3, bp=True)
            rate_src[k] = f"Yahoo {ysym} (fallback)"
        rates[k] = s
    tnx = dict(fetched.get("^TNX", []))
    tnx_diff = [round(abs(x["close"] - tnx[_d(x["d"])]) * 100, 1) for x in rates["US10Y"]["days"] if _d(x["d"]) in tnx]
    if rates["US10Y"]["days"] and rates["US10Y"]["days"][-1]["d"] != (_iso(sessions[-1]) if sessions else None):
        notes["US10Y"] = f"Treasury last date {rates['US10Y']['days'][-1]['d']}"

    sectors = []
    for s, n in SECTORS:
        x = ser(s, n)
        sectors.append({"etf": s, "name_ko": n, "week_pct": x["week_pct"]})
    megacaps = []
    for s, n in MEGACAPS:
        x = ser(s, n)
        megacaps.append({"ticker": s, "name_ko": n, "week_pct": x["week_pct"],
                         "close": x["days"][-1]["close"] if x["days"] else None})
    key = lambda r: (r["week_pct"] is None, -(r["week_pct"] or 0))  # noqa: E731
    sectors.sort(key=key)
    megacaps.sort(key=key)

    cal_errs: list[str] = []
    cal_next = calendar_next(we, cal_errs)
    errs += cal_errs

    out = {
        "week_start": _iso(week_start), "week_end": _iso(we), "build_date": build_date,
        "sessions": [_iso(x) for x in sessions],
        "idx": idx, "rates": rates, "fx": fx, "commod": commod,
        "sectors": sectors, "megacaps": megacaps,
        "calendar_next": cal_next,
        "news": [],
    }
    out["_meta"] = {
        "fetched_at": now.isoformat(timespec="seconds"),
        "prev_session": _iso(prev_d),
        "expected_sessions": [_iso(x) for x in expected],
        "missing_sessions": missing,
        "complete": not missing and bool(sessions),
        "holidays": holidays,
        "week_pct_through": _iso(sessions[-1]) if sessions else None,
        "high_low_basis": "close (week_high/week_low = max/min of this week's daily closes)",
        "pct_basis": "days[i].pct vs previous session close in this list; days[0] vs prev_close (prior week's last session)",
        "calendar_basis": "date = US Eastern date; kst = Korea time (None = all day / time not published)",
        "sort": "sectors, megacaps sorted by week_pct desc",
        "sources": {"idx/fx/commod/sectors/megacaps": "Yahoo Finance chart API",
                    "rates": rate_src, "calendar_session": cal_sym},
        "symbols": {"idx": {k: s for k, s, _ in IDX}, "fx": {k: s for k, s, _ in FX}, "commod": {k: s for k, s, _ in COMMOD},
                    "note": "WTI=CL=F, GOLD=GC=F front-month futures (roll gaps possible near expiry); "
                            "USDKRW=Yahoo KRW=X (London-day close), not the Seoul 15:30 close"},
        "checks": {"us10y_treasury_vs_tnx_bp": tnx_diff},
        "series_notes": notes,
        "errors": errs,
    }
    out["_meta"]["checks"].update(_crosscheck(out, week_start, we))
    dst = OUT_ROOT / build_date
    dst.mkdir(parents=True, exist_ok=True)
    save_json(dst / "computed_us_weekly.json", out)
    return out


def summary(o: dict) -> str:
    f = lambda v, nd=2: "-" if v is None else f"{v:+.{nd}f}"  # noqa: E731
    L = [f"US weekly {o['week_start']}~{o['week_end']} build {o['build_date']} sessions {o['sessions']} "
         f"prev {o['_meta']['prev_session']} missing {[m['d'] for m in o['_meta']['missing_sessions']]}"]
    for grp in ("idx", "fx", "commod"):
        for k, v in o[grp].items():
            L.append(f"  {k:7s} prev {v['prev_close']} -> " + " ".join(f"{x['d'][5:]}:{x['close']}({f(x['pct'])})" for x in v["days"])
                     + f" | week {f(v['week_pct'])}% hi {v['week_high']} lo {v['week_low']}")
    for k, v in o["rates"].items():
        L.append(f"  {k:7s} prev {v['prev_close']} -> " + " ".join(f"{x['d'][5:]}:{x['close']}({x['chg_bp']:+d}bp)" for x in v["days"] if x.get("chg_bp") is not None)
                 + f" | week {v['week_chg_bp']}bp")
    L.append("  sectors " + " ".join(f"{s['etf']}{f(s['week_pct'])}" for s in o["sectors"]))
    L.append("  mega    " + " ".join(f"{s['ticker']}{f(s['week_pct'])}@{s['close']}" for s in o["megacaps"]))
    L.append("  next    " + " | ".join(f"{e['date'][5:]} {e['event_ko']}" for e in o["calendar_next"]))
    c = o["_meta"]["checks"]
    L.append(f"  checks  idx vs daily raw max|diff| {c.get('idx_max_abs_diff')} (n={len(c.get('idx_vs_daily_raw') or [])}); "
             f"US10Y vs daily raw {[(x['d'][5:], x['weekly'], x['daily_raw']) for x in c.get('us10y_vs_daily_raw') or []]}; "
             f"treasury vs ^TNX bp {c.get('us10y_treasury_vs_tnx_bp')}")
    if o["_meta"]["errors"]:
        L.append(f"  errors  {o['_meta']['errors']}")
    if o["_meta"]["series_notes"]:
        L.append(f"  notes   {o['_meta']['series_notes']}")
    return "\n".join(L)


def _default_week_end() -> str:
    t = datetime.now(KST).date()
    return _iso(t - timedelta(days=(t.weekday() - 4) % 7))     # 토·일 → 직전 금요일, 금 → 오늘


if __name__ == "__main__":
    we_arg = sys.argv[1] if len(sys.argv) > 1 else _default_week_end()
    bd_arg = sys.argv[2] if len(sys.argv) > 2 else datetime.now(KST).strftime("%Y%m%d")
    res = build(we_arg, bd_arg)
    print(summary(res))
    print(f"saved: {OUT_ROOT / bd_arg / 'computed_us_weekly.json'}")
