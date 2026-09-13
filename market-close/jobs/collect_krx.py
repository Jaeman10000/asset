"""KRX 확정치 — 투자자별 거래실적(주식) + 지수 OHLCV·거래대금. pykrx(로그인 필요).
우리는 15:55(build 단계)에 부르므로 받아오는 건 '정규시장 마감 반영분'(KRX 안내: 오후 3시45분 예정)이다.
시간외·애프터마켓까지 포함한 최종치는 2026-09-14 애프터마켓(16:00~20:00) 시행에 맞춰 18시 → **20시**로 밀렸다.
둘의 차이는 jobs/check_final_flows.py 로 잰다.
자격증명: 키체인 krx:id / krx:pw (backend/scripts/set_api_key.py krx id ... 로 저장).
환율: ECOS 731Y001 (키체인 ecos:key). 없으면 비움.
결과: data/D/raw/krx.json
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from _common import day_dir, log, save_json
from app.keychain import get_api_key  # noqa: E402

INVESTORS = {"개인": "indiv", "외국인": "foreign", "기관합계": "inst", "기타법인": "others", "기타외국인": "etc_foreign",
             "금융투자": "sec", "보험": "ins", "투신": "trust", "사모": "private", "은행": "bank", "기타금융": "etc_fin", "연기금": "pension"}


def _investors(stock, d: str, mkt: str) -> dict | None:
    df = stock.get_market_trading_value_by_investor(d, d, mkt)  # 원 단위, index=투자자구분
    if df is None or df.empty:
        return None
    col = "순매수" if "순매수" in df.columns else df.columns[-1]
    out = {}
    for k, key in INVESTORS.items():
        if k in df.index:
            out[key] = round(float(df.loc[k, col]) / 1e8)  # 억원
    return out


def _index(stock, d: str, code: str) -> dict | None:
    df = stock.get_index_ohlcv(d, d, code)
    if df is None or df.empty:
        return None
    r = df.iloc[-1]
    return {"open": float(r["시가"]), "high": float(r["고가"]), "low": float(r["저가"]), "close": float(r["종가"]),
            "volume": float(r["거래량"]), "value_krw": float(r["거래대금"]) if "거래대금" in df.columns else None}


def _fx_naver(d: str) -> dict | None:
    """네이버 시장지표 일별 매매기준율(하나은행 고시). 서울외국환중개 15:30 종가와는 1원 안팎 차이 — 라벨에 출처 표기."""
    import re
    import httpx
    r = httpx.get("https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd=FX_USDKRW&page=1",
                  headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    t = r.content.decode("euc-kr", "ignore")
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t, flags=re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 3 and re.match(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
            rows.append((cells[0].replace(".", ""), float(cells[1].replace(",", ""))))
    rows = [x for x in rows if x[0] <= d]
    if not rows:
        return None
    last, prev = rows[0], (rows[1] if len(rows) > 1 else None)
    return {"date": last[0], "close": last[1], "chg": round(last[1] - prev[1], 2) if prev else None,
            "src": "하나은행 매매기준율(네이버)", "is_today": last[0] == d}


def _fx(d: str) -> dict | None:
    key = get_api_key("ecos", "key")
    if not key:
        try:
            return _fx_naver(d)
        except Exception as e:
            log(d, "krx", f"네이버 환율 실패: {e}")
            return None
    import httpx
    start = (datetime.strptime(d, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d")
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/20/731Y001/D/{start}/{d}/0000001"
    r = httpx.get(url, timeout=20)
    rows = (r.json().get("StatisticSearch") or {}).get("row") or []
    rows = [x for x in rows if x.get("TIME") <= d]
    if not rows:
        return None
    rows.sort(key=lambda x: x["TIME"])
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else None
    close = float(last["DATA_VALUE"])
    return {"date": last["TIME"], "close": close, "chg": round(close - float(prev["DATA_VALUE"]), 1) if prev else None,
            "src": "ECOS 731Y001", "is_today": last["TIME"] == d}


def main(d: str) -> None:
    raw = day_dir(d)
    out: dict = {"date": d, "fetched_at": datetime.now().isoformat(timespec="seconds"), "ready": False}
    kid, kpw = get_api_key("krx", "id"), get_api_key("krx", "pw")
    if not (kid and kpw):
        out["reason"] = "KRX 로그인 없음 — 키체인 krx:id / krx:pw 등록 필요 (data.krx.co.kr 회원가입)"
        log(d, "krx", out["reason"])
    else:
        os.environ["KRX_ID"], os.environ["KRX_PW"] = kid, kpw
        try:
            from pykrx import stock  # 로그인은 import 시점/첫 호출 시
            out["kospi"] = {"investors": _investors(stock, d, "KOSPI"), "index": _index(stock, d, "1001")}
            out["kosdaq"] = {"investors": _investors(stock, d, "KOSDAQ"), "index": _index(stock, d, "2001")}
            out["ready"] = bool(out["kospi"]["investors"] and out["kospi"]["index"])
            log(d, "krx", f"KOSPI 투자자별 {out['kospi']['investors']}")
        except Exception as e:
            out["reason"] = f"pykrx 실패: {e}"
            log(d, "krx", out["reason"])
    try:
        out["fx"] = _fx(d)
        log(d, "krx", f"환율 {out['fx']}")
    except Exception as e:
        out["fx"] = None
        log(d, "krx", f"ECOS 실패: {e}")
    save_json(raw / "krx.json", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
