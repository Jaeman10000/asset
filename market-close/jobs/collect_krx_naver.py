"""거래소 집계 투자자별 매매동향(네이버 금융 일별 페이지, 억원) — 우리 키움 합산과 매일 대조하기 위한 참조값.
raw/krx_investors.json: {"date": d, "kospi": {"indiv","foreign","inst"}, "kosdaq": {...}, "src": "네이버 금융(거래소 집계)"}
당일 행이 아직 없으면(잠정치 발표 전) 저장하지 않는다.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime

import httpx

from _common import day_dir, log, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}


def _num(s: str) -> int | None:
    s = s.replace(",", "").replace("+", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def fetch(d: str) -> dict:
    out = {"date": d, "src": "네이버 금융(거래소 집계)"}
    want = f"{d[2:4]}.{d[4:6]}.{d[6:8]}"
    for sosok, key in (("01", "kospi"), ("02", "kosdaq")):
        r = httpx.get("https://finance.naver.com/sise/investorDealTrendDay.naver", params={"bizdate": d, "sosok": sosok}, headers=UA, timeout=20)
        x = re.sub(r"\s+", " ", r.content.decode("euc-kr", "ignore"))
        days = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", x):
            cells = [html.unescape(re.sub(r"<.*?>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row)]
            if cells and re.match(r"\d{2}\.\d{2}\.\d{2}$", cells[0]) and len(cells) >= 4:
                rec = {"date": "20" + cells[0].replace(".", ""), "indiv": _num(cells[1]), "foreign": _num(cells[2]), "inst": _num(cells[3])}
                if cells[0] == want:
                    out[key] = {k: rec[k] for k in ("indiv", "foreign", "inst")}
                if rec["date"] <= d:
                    days.append(rec)
                if len(days) >= 10:
                    break
        out[key + "_days"] = days
    return out


def main(d: str) -> dict:
    try:
        j = fetch(d)
    except Exception as e:
        log(d, "krx_naver", f"실패(무시): {e}")
        return {}
    if not j.get("kospi"):
        log(d, "krx_naver", "당일 행 아직 없음(잠정치 발표 전)")
        return {}
    save_json(day_dir(d) / "krx_investors.json", j)
    k = j["kospi"]
    log(d, "krx_naver", f"거래소 집계 코스피 개인 {k['indiv']:+,} 외국인 {k['foreign']:+,} 기관 {k['inst']:+,}")
    return j


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")))
