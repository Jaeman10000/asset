"""검색 수요 지도 — 유튜브 자동완성을 씨앗말에서 넓혀 '사람들이 실제로 치는 질문'을 모은다.

왜 이게 필요한가 (2026-09-23 스튜디오 실측):
    한전 기업해부  검색 88.7% / 피드  9.8%  조회 2.2천, 사흘 뒤에도 계속 들어옴
    배당 해설      검색 80.4% / 피드 18.3%  조회 3.4천, 계속 시청 65.9%
    추석 연휴      검색 16.1% / 피드 82.0%  조회 1.5천, 하루에 끝
→ **우리 정보형은 피드가 아니라 검색으로 큰다.** 그러면 주제는 '우리가 하고 싶은 말'이 아니라
   **사람들이 검색창에 치는 말**에서 골라야 한다. 이 파일이 그 말을 모은다.

실행(jobs/):
    python demand_map.py                     기본 씨앗말로 2단계까지
    python demand_map.py --depth=1           1단계만(빠름)
    python demand_map.py --seed=공매도,배당   씨앗말 직접

만드는 것: data/demand_map.json  (+ 화면에 상위 목록)
    { "at": "20260923", "rows": [ {"q": "배당락 이란", "n": 14, "seed": "배당", "depth": 1}, … ] }
    n = 그 말로 다시 물었을 때 돌아오는 자동완성 개수(0~14). **14면 만석 = 수요가 크다.**

읽는 법:
    - n 이 10 이상이면 그 말은 검색창에서 실제로 쓰인다 → 제목·훅에 그 말 그대로 쓴다
    - n 이 0~4 면 사람들이 안 친다 → 아무리 좋은 주제여도 검색으로는 안 들어온다(피드 운에 맡기는 편이 된다)
    - 이미 만든 편과 겹치는 말은 `made` 로 표시 — 겹치면 다시 만들지 말고 각도를 바꾼다
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import httpx

MC = pathlib.Path(__file__).resolve().parent.parent
OUT = MC / "data" / "demand_map.json"
URL = "https://suggestqueries.google.com/complete/search"

SEEDS = ["주식", "코스피", "삼성전자", "sk하이닉스", "배당", "공매도", "외국인", "기관", "수급",
         "etf", "연금저축", "irp", "실적발표", "목표주가", "환율", "금리", "주식 세금", "시가총액",
         "옵션만기", "자사주", "코스닥", "주식 초보"]


def suggest(c: httpx.Client, q: str) -> list[str]:
    try:
        r = c.get(URL, params={"client": "youtube", "ds": "yt", "hl": "ko", "gl": "kr", "q": q})
        t = r.text
        data = json.loads(t[t.index("(") + 1: t.rindex(")")])
        return [x[0] for x in data[1]]
    except Exception:
        return []


def made_titles() -> list[str]:
    """이미 만든 편 제목 — 겹치는 주제를 다시 만들지 않으려고."""
    out = []
    for p in sorted((MC / "data").glob("2026*/info*_script.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")).get("title", ""))
        except Exception:
            pass
    return out


def run(seeds: list[str], depth: int = 2) -> dict:
    rows: dict[str, dict] = {}
    titles = made_titles()
    with httpx.Client(timeout=12.0) as c:
        level = list(seeds)
        for d in range(1, depth + 1):
            nxt = []
            for q in level:
                sug = suggest(c, q)
                time.sleep(0.2)
                for s in sug:
                    if s in rows or s == q:
                        continue
                    rows[s] = {"q": s, "n": None, "seed": q, "depth": d}
                    nxt.append(s)
            # 이 단계에서 나온 말의 '수요'를 잰다 = 그 말로 다시 물어 몇 개가 돌아오나
            for s in nxt:
                rows[s]["n"] = len(suggest(c, s))
                time.sleep(0.2)
            if d < depth:
                level = [s for s in nxt if (rows[s]["n"] or 0) >= 10][:40]   # 수요 큰 말만 더 넓힌다
            print(f"{d}단계: {len(nxt)}개 (누적 {len(rows)})", flush=True)

    for r in rows.values():
        r["made"] = any(w and w in " ".join(titles) for w in r["q"].split()[:2])
    data = {"at": time.strftime("%Y%m%d"), "seeds": seeds, "rows": sorted(rows.values(), key=lambda x: -(x["n"] or 0))}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    dep = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--depth=")), "2"))
    sd = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--seed=")), "")
    seeds = [x.strip() for x in sd.split(",") if x.strip()] or SEEDS
    data = run(seeds, dep)
    full = [r for r in data["rows"] if (r["n"] or 0) >= 13 and not r["made"]]
    print(f"\n저장 {OUT}  ·  총 {len(data['rows'])}개  ·  만석(13+)이면서 아직 안 만든 것 {len(full)}개\n")
    for r in full[:60]:
        print(f"  {r['n']:2d}  {r['q']}   ← {r['seed']}")
