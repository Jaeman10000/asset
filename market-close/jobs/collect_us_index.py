"""미국 공식 지수 종가 — Yahoo Finance chart API(ETF 대용 아님).
나스닥 종합(^IXIC)·S&P500(^GSPC)·다우(^DJI)·필라델피아 반도체(^SOX)·VIX(^VIX).
결과: data/D/raw/us_index.json
  {"date","session","fetched_at","src","index":{"IXIC":{...},...},"error":null}
세션 = D 하루 전 미국 영업일(주말 건너뜀). 세션+1일 06:00 KST 이전 수집이면 provisional=True.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import httpx

from _common import day_dir, log, save_json

SRC = "Yahoo Finance chart API"
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
SYMBOLS = [
    ("IXIC", "^IXIC", "나스닥"),
    ("GSPC", "^GSPC", "S&P500"),
    ("DJI", "^DJI", "다우"),
    ("SOX", "^SOX", "필라델피아 반도체"),
    ("VIX", "^VIX", "VIX"),
]
KST = timezone(timedelta(hours=9))
TIMEOUT = 20.0


def us_session_date(d: str) -> str:
    """D 하루 전, 주말이면 금요일까지 되돌림. 공휴일은 행 부재(missing)로 드러난다."""
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def is_provisional(session: str, now_kst: datetime | None = None) -> bool:
    """세션 다음날 06:00 KST(= 종가 확정·정정 반영 여유) 이전이면 잠정치."""
    now_kst = now_kst or datetime.now(KST)
    cutoff = (datetime.strptime(session, "%Y%m%d") + timedelta(days=1)).replace(hour=6, tzinfo=KST)
    return now_kst < cutoff


def _rows(res: dict) -> list[dict]:
    """Yahoo result → [{date, open, high, low, close}] (null 봉 제거, 날짜 오름차순).
    봉 타임스탬프는 세션 개장(09:30 ET). 거래소 gmtoffset으로 현지 날짜를 얻는다(없으면 UTC)."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    off = int((res.get("meta") or {}).get("gmtoffset") or 0)
    out = []
    for i, t in enumerate(ts):
        c = (q.get("close") or [None] * len(ts))[i]
        if c is None:
            continue
        local = datetime.fromtimestamp(t, timezone.utc) + timedelta(seconds=off)
        row = {"date": local.strftime("%Y%m%d"), "close": float(c)}
        for k in ("open", "high", "low"):
            v = (q.get(k) or [None] * len(ts))[i]
            row[k] = float(v) if v is not None else None
        out.append(row)
    out.sort(key=lambda r: r["date"])
    # 같은 날짜가 중복되면 마지막 것을 채택
    dedup: dict[str, dict] = {}
    for r in out:
        dedup[r["date"]] = r
    return list(dedup.values())


def _streak(closes: list[float]) -> int:
    """closes[0]=세션, 뒤로 갈수록 과거. 연속 상승(+)/하락(-) 일수."""
    if len(closes) < 2 or closes[0] == closes[1]:
        return 0
    sign = 1 if closes[0] > closes[1] else -1
    n = 0
    for i in range(len(closes) - 1):
        diff = closes[i] - closes[i + 1]
        if (diff > 0 and sign > 0) or (diff < 0 and sign < 0):
            n += 1
        else:
            break
    return n * sign


def fetch_symbol(hc: httpx.Client, sym: str, session: str) -> dict:
    r = hc.get(f"{BASE}{sym}", params={"range": "10d", "interval": "1d"})
    r.raise_for_status()
    body = r.json()
    chart = body.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"yahoo error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError("empty result")
    rows = _rows(results[0])
    if not rows:
        raise RuntimeError("no bars")
    idx = next((i for i, r_ in enumerate(rows) if r_["date"] == session), None)
    if idx is None:
        latest = rows[-1]["date"]
        return {"missing": True, "reason": f"session {session} bar not found (latest {latest}; holiday or lag)", "latest": latest}
    cur = rows[idx]
    prev = rows[idx - 1] if idx > 0 else None
    closes = [rows[i]["close"] for i in range(idx, -1, -1)]  # 세션부터 과거로
    r2 = lambda v: round(v, 2) if v is not None else None  # noqa: E731
    return {
        "open": r2(cur["open"]), "high": r2(cur["high"]), "low": r2(cur["low"]), "close": r2(cur["close"]),
        "prev_close": r2(prev["close"]) if prev else None,
        "pct": round((cur["close"] / prev["close"] - 1) * 100, 2) if prev and prev["close"] else None,
        "streak": _streak(closes),
        "pct5": round((closes[0] / closes[5] - 1) * 100, 2) if len(closes) > 5 and closes[5] else None,
        "bars": len(rows),
    }


def main(d: str) -> dict:
    raw = day_dir(d)
    session = us_session_date(d)
    now = datetime.now(KST)
    provisional = is_provisional(session, now)
    out: dict = {"date": d, "session": session, "fetched_at": now.isoformat(timespec="seconds"), "src": SRC,
                 "provisional": provisional, "index": {}, "error": None}
    fetch_errors: list[str] = []
    try:
        with httpx.Client(headers=UA, timeout=httpx.Timeout(TIMEOUT), follow_redirects=True) as hc:
            for key, sym, name in SYMBOLS:
                item: dict = {"symbol": sym, "name": name, "session": session}
                try:
                    item.update(fetch_symbol(hc, sym, session))
                except Exception as e:  # 심볼 하나 실패해도 나머지는 계속
                    reason = f"{type(e).__name__}: {e}"[:200]
                    fetch_errors.append(f"{key} {reason}")
                    item.update({"missing": True, "reason": reason, "fetch_error": True})
                if not item.get("missing"):
                    item["provisional"] = provisional
                    log(d, "us_index", f"{key} {name}: close {item['close']} ({item['pct']:+.2f}%) streak {item['streak']} pct5 {item['pct5']}"
                                       + (" [잠정]" if provisional else ""))
                else:
                    log(d, "us_index", f"{key} {name}: 없음 — {item.get('reason')}")
                out["index"][key] = item
    except Exception as e:  # 클라이언트 생성 등 전체 실패
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        for key, sym, name in SYMBOLS:
            out["index"].setdefault(key, {"symbol": sym, "name": name, "session": session, "missing": True, "reason": out["error"]})
        log(d, "us_index", f"전체 실패: {out['error']}")
    out["missing"] = [k for k, v in out["index"].items() if v.get("missing")]
    if fetch_errors and not out["error"]:  # 휴장/지연(bar 없음)은 error 아님, 통신·파싱 실패만
        out["error"] = f"{len(fetch_errors)}/{len(SYMBOLS)} fetch failed: {fetch_errors[0]}"
    try:
        save_json(raw / "us_index.json", out)
    except Exception as e:
        log(d, "us_index", f"저장 실패: {e}")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
