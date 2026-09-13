"""저녁 8시 이후 수급을 다시 받아, 우리가 16:30에 말한 숫자와 얼마나 벌어졌는지 잰다.

배경(2026-09-14 시행): 한국거래소가 16:00~20:00 애프터마켓(접속매매)을 열고 기존 시간외단일가(16~18시)를 없앴다.
정규장(09:00~15:30)·공식 종가·익일 기준가는 그대로다. 우리 수집은 15:41(collect)·15:55(build)라 애프터마켓이
열리기 전에 끝나므로, 영상 속 숫자는 여전히 '정규장 체결 기준'으로 깨끗하다.

문제는 시청자 쪽이다. KRX 정보데이터시스템 안내문이 "시간외 등이 포함된 최종 매매내역은 당일자 마감 이후
(오후 8시 예정) 제공"으로 바뀌었고(전에는 오후 6시), 애프터마켓이 2시간 단일가에서 4시간 접속매매로 커졌다.
밤에 포털에서 같은 항목을 보는 사람은 우리와 다른 숫자를 볼 수 있다.

이 스크립트는 그 차이를 재기만 한다. 며칠 쌓아 보고 차이가 작으면 16:30 그대로 가고, 커지면 그때
대본에 '정규장 기준'을 못 박거나 업로드 시각을 다시 의논한다. **판단은 숫자를 본 뒤에 한다.**

실행(거래일 20:10 이후):
  python check_final_flows.py                 오늘
  python check_final_flows.py 20260914        특정일
결과: data/flow_gap.csv 에 한 줄 추가. 코스피 주권 전 종목 재합산이라 3~4분 걸린다.
"""
from __future__ import annotations

import asyncio
import csv
import sys
from datetime import datetime

import httpx

from _common import DATA, load_json, log

FIELDS = ["foreign", "inst", "indiv", "others"]
NAMES = {"foreign": "외국인", "inst": "기관", "indiv": "개인", "others": "기타법인"}
OUT = DATA / "flow_gap.csv"


async def _resum(d: str) -> dict | None:
    """영상에 쓴 것과 똑같은 방법(ka10059 전 종목 합산)으로 지금 한 번 더 합산한다."""
    import collect_kiwoom_sum as ks
    from app.services.kiwoom_client import KiwoomClient
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await KiwoomClient()._ensure_token(hc)
        return await ks.market_sum(hc, tok, "0", d)


def main(d: str) -> None:
    early = (load_json(DATA / d / "raw" / "kiwoom_sum.json") or {}).get("kospi") or {}
    if not early:
        log(d, "gap", "그날 16:30 숫자가 없다(raw/kiwoom_sum.json) — 비교 대상 없음")
        return
    late = asyncio.run(_resum(d))
    if not late:
        log(d, "gap", "재합산 실패")
        return
    row = {"date": d, "checked_at": datetime.now().strftime("%H:%M")}
    msg = []
    for k in FIELDS:
        a, b = early.get(k), late.get(k)
        row[f"{k}_1600"], row[f"{k}_final"] = a, b
        if a is None or b is None:
            continue
        gap = round(b - a)
        row[f"{k}_gap"] = gap
        pct = abs(gap) / abs(a) * 100 if a else 0
        msg.append(f"{NAMES[k]} {round(a):+,}→{round(b):+,} ({gap:+,}억 · {pct:.1f}%)")
    cols = ["date", "checked_at"] + [f"{k}_{s}" for k in FIELDS for s in ("1600", "final", "gap")]
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)
    log(d, "gap", " · ".join(msg) or "비교할 값 없음")
    log(d, "gap", f"→ {OUT}  (차이가 주체별 3% 안쪽이면 16:30 그대로 가도 된다)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
