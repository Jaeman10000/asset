"""18:03 미국 밤 칸 — BLS 캘린더(.ics), 연준 RSS, Treasury 10년물 XML, EIA WTI. 전부 공공영역.
결과: data/D/raw/us.json  (이벤트는 ET→KST 환산, 세션 창 22:30~05:00 안이면 in_session=True)
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone

import httpx

from _common import day_dir, log, save_json

UA = {"User-Agent": "market-close-brief/0.1 (jeff.gadget10000@gmail.com)"}
FOMC_2026 = ["2026-01-27/28", "2026-03-17/18", "2026-04-28/29", "2026-06-16/17", "2026-07-28/29", "2026-09-15/16", "2026-10-27/28", "2026-12-08/09"]


def _et_offset(dt: datetime) -> int:
    """ET(EDT/EST) → KST 시차(시간). 미국 DST: 3월 둘째 일요일 ~ 11월 첫째 일요일."""
    y = dt.year
    mar = datetime(y, 3, 8); mar += timedelta(days=(6 - mar.weekday()) % 7)
    nov = datetime(y, 11, 1); nov += timedelta(days=(6 - nov.weekday()) % 7)
    return 13 if mar <= dt < nov else 14


def _us_session_date(d: str) -> datetime:
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt


def _bls(session: datetime) -> list[dict]:
    r = httpx.get("https://www.bls.gov/schedule/news_release/bls.ics", headers=UA, timeout=30)
    r.raise_for_status()
    out = []
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", r.text, flags=re.S):
        m = re.search(r"DTSTART[^:]*:(\d{8})T?(\d{4})?", ev)
        s = re.search(r"SUMMARY:(.*)", ev)
        if not m or not s:
            continue
        day = m.group(1); tm = m.group(2) or "0830"
        dt = datetime.strptime(day + tm, "%Y%m%d%H%M")
        if session.date() <= dt.date() <= (session + timedelta(days=8)).date():
            off = _et_offset(dt)
            kst = dt + timedelta(hours=off)
            out.append({"src": "BLS", "et": dt.strftime("%Y-%m-%d %H:%M"), "kst": kst.strftime("%Y-%m-%d %H:%M"),
                        "what": s.group(1).strip().replace("\\,", ","), "in_session": dt.date() == session.date() and dt.hour >= 9})
    return out


def _fed_rss(session: datetime) -> list[dict]:
    out = []
    for feed in ("https://www.federalreserve.gov/feeds/press_monetary.xml", "https://www.federalreserve.gov/feeds/speeches_and_testimony.xml"):
        try:
            r = httpx.get(feed, headers=UA, timeout=30)
            for item in re.findall(r"<item>(.*?)</item>", r.text, flags=re.S):
                t = re.search(r"<title>(.*?)</title>", item, flags=re.S)
                p = re.search(r"<pubDate>(.*?)</pubDate>", item)
                if not (t and p):
                    continue
                try:
                    dt = datetime.strptime(p.group(1).strip()[:25], "%a, %d %b %Y %H:%M:%S")
                except ValueError:
                    continue
                if dt.date() == session.date():
                    out.append({"src": "Fed", "et": dt.strftime("%Y-%m-%d %H:%M"), "what": re.sub(r"<.*?>", "", t.group(1)).strip()[:120]})
        except Exception:
            continue
    return out


def _treasury(session: datetime) -> dict | None:
    ym = session.strftime("%Y%m")
    url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month={ym}"
    r = httpx.get(url, headers=UA, timeout=30)
    rows = []
    for e in re.findall(r"<entry>(.*?)</entry>", r.text, flags=re.S):
        nd = re.search(r"NEW_DATE[^>]*>([\d\-T:]+)<", e); y10 = re.search(r"BC_10YEAR[^>]*>([\d.]+)<", e)
        if nd and y10:
            rows.append((nd.group(1)[:10], float(y10.group(1))))
    rows.sort()
    rows = [x for x in rows if x[0] <= session.strftime("%Y-%m-%d")]
    if not rows:
        return None
    last = rows[-1]; prev = rows[-2] if len(rows) > 1 else None
    return {"date": last[0], "y10": last[1], "chg_bp": round((last[1] - prev[1]) * 100) if prev else None, "src": "U.S. Treasury"}


def _eia() -> dict | None:
    url = ("https://api.eia.gov/v2/petroleum/pri/spt/data/?frequency=daily&data[0]=value&facets[series][]=RWTC"
           "&sort[0][column]=period&sort[0][direction]=desc&length=3&api_key=DEMO_KEY")
    r = httpx.get(url, headers=UA, timeout=30)
    data = (r.json().get("response") or {}).get("data") or []
    if not data:
        return None
    last, prev = data[0], (data[1] if len(data) > 1 else None)
    v = float(last["value"]); pv = float(prev["value"]) if prev else None
    return {"date": last["period"], "wti": v, "chg_pct": round((v / pv - 1) * 100, 2) if pv else None, "src": "EIA RWTC"}


# ── 지표 실제값(BLS API v1, 키 없음, 하루 25회) — 발표 당일 세션이면 헤드라인 숫자를 뽑는다 ──
_BLS_SERIES = {
    "Employment Situation": {"nfp": "CES0000000001", "unemp": "LNS14000000", "ahe": "CES0500000003"},
    "Consumer Price Index": {"cpi_sa": "CUSR0000SA0", "cpi_nsa": "CUUR0000SA0", "core_sa": "CUSR0000SA0L1E"},
    "Producer Price Index": {"ppi_sa": "WPSFD4"},
    "Job Openings": {"jolts": "JTS000000000000000JOL"},
}


def _bls_values(events: list[dict], session: datetime) -> dict | None:
    """세션 당일 발표된 BLS 지표의 실제값. {'what','period','values':{...}} — 최신 기간이 직전 달이 아니면(아직 미갱신) None."""
    todays = [e for e in events if e.get("et", "")[:10] == session.strftime("%Y-%m-%d")]
    key = next((k for e in todays for k in _BLS_SERIES if k in e["what"]), None)
    if not key:
        return None
    ids = list(_BLS_SERIES[key].values())
    r = httpx.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", json={"seriesid": ids},
                   headers={**UA, "Content-Type": "application/json"}, timeout=30)
    data = {s["seriesID"]: s["data"] for s in (r.json().get("Results") or {}).get("series") or []}
    inv = {v: k for k, v in _BLS_SERIES[key].items()}
    out, period = {}, None
    for sid, rows in data.items():
        rows = [x for x in rows if x.get("period", "").startswith("M")]
        if len(rows) < 13:
            continue
        cur, prev, yago = rows[0], rows[1], rows[12]
        period = period or f"{cur['year']}-{cur['period'][1:]}"
        name = inv[sid]
        v, pv, yv = float(cur["value"]), float(prev["value"]), float(yago["value"])
        if name == "nfp":
            out["nfp_k"] = round(v - pv)
        elif name == "unemp":
            out["unemp"] = v; out["unemp_prev"] = pv
        elif name == "ahe":
            out["ahe_mm"] = round((v / pv - 1) * 100, 1); out["ahe_yy"] = round((v / yv - 1) * 100, 1)
        elif name == "cpi_sa":
            out["cpi_mm"] = round((v / pv - 1) * 100, 1)
        elif name == "cpi_nsa":
            out["cpi_yy"] = round((v / yv - 1) * 100, 1)
        elif name == "core_sa":
            out["core_mm"] = round((v / pv - 1) * 100, 1)
        elif name == "ppi_sa":
            out["ppi_mm"] = round((v / pv - 1) * 100, 1)
        elif name == "jolts":
            out["jolts_k"] = round(v); out["jolts_prev_k"] = round(pv)
    if not out or not period:
        return None
    # 발표 당일이면 최신 기간 = 직전 달(고용·CPI) — 두 달 이상 오래됐으면 미갱신으로 본다
    y, m = int(period[:4]), int(period[5:])
    lag = (session.year - y) * 12 + session.month - m
    return {"what": key, "period": period, "values": out, "stale": lag > 2}


def main(d: str) -> None:
    raw = day_dir(d)
    session = _us_session_date(d)
    out = {"date": d, "session_et": session.strftime("%Y-%m-%d"), "fetched_at": datetime.now().isoformat(timespec="seconds")}
    for name, fn in (("bls", lambda: _bls(session)), ("fed", lambda: _fed_rss(session)), ("treasury", lambda: _treasury(session)), ("eia", _eia)):
        try:
            out[name] = fn()
            log(d, "us", f"{name}: {str(out[name])[:160]}")
        except Exception as e:
            out[name] = None
            log(d, "us", f"{name} 실패: {e}")
    out["fomc_2026"] = FOMC_2026
    try:
        out["bls_values"] = _bls_values(out.get("bls") or [], session)
        log(d, "us", f"bls_values: {out['bls_values']}")
    except Exception as e:
        out["bls_values"] = None
        log(d, "us", f"bls_values 실패: {e}")
    save_json(raw / "us.json", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
