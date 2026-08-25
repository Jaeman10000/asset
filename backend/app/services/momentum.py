"""지금 주도 — 최근 N거래일 동안 실제로 돈이 들어간 테마 순위.

`forecast.py`와 **일부러 반대 방향을 본다**:
  forecast : 아직 안 들어왔는데 들어오기 시작한 곳 (순환·전이·여력)
  momentum : 이미 들어와서 지금 끌고 가는 곳 (누적 순매수)

둘을 같이 놓는 이유 — 실측 사례: 해운은 60일 넘게 순매수가 이어졌는데
forecast 점수는 13위였다(10일평균 강도 +8.4 → 여력 -8.4 → 0점, 가속도 +2.8뿐).
"이미 오래 사들여진 것"이 순환 모델에선 감점이기 때문이다. 그건 모델 설계상
맞는 동작이지만, 추세를 보고 싶은 사람에겐 답이 안 된다. 그래서 별도 순위로 낸다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .themes import CODE_NAME, THEME_CODES
from . import flow_store

LEADERS_N = 5
MAX_DAYS = 120


def momentum(days: int = 20) -> dict[str, Any]:
    days = max(3, min(MAX_DAYS, days))
    rows = flow_store.sector_series(MAX_DAYS)
    if not rows:
        return {"ready": False, "reason": "아카이브가 비어 있습니다.", "days": 0}

    all_dates = sorted({r[0] for r in rows})
    win = all_dates[-days:]
    win_set = set(win)

    # 테마별 창 내 집계 + 일별 순매수(연속 유입일 계산용)
    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"f": 0.0, "i": 0.0, "v": 0.0, "n": 0, "pos": 0})
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    for date, theme, f, i, v, _s, _leader in rows:
        if date not in win_set:
            continue
        a = agg[theme]
        a["f"] += f
        a["i"] += i
        a["v"] += v
        a["n"] += 1
        net = f + i
        daily[theme][date] = net
        if net > 0:
            a["pos"] += 1

    if not agg:
        return {"ready": False, "reason": f"최근 {days}거래일 데이터가 없습니다.", "days": len(all_dates)}

    # 창 안의 종목별 누적 순매수 → 테마별 주도주 5
    leaders: dict[str, list[dict[str, Any]]] = {}
    if win:
        per_code: dict[str, dict[str, float]] = defaultdict(lambda: {"net": 0.0, "ret": 0.0})
        code_theme: dict[str, str] = {}
        last = win[-1]
        for date, code, theme, f, i, _v, ret in flow_store.stock_series(win[0]):
            if date not in win_set:
                continue
            per_code[code]["net"] += f + i
            code_theme[code] = theme
            if date == last:
                per_code[code]["ret"] = ret
        by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for code, v in per_code.items():
            theme = code_theme.get(code, "")
            if not theme:
                continue
            by_theme[theme].append(
                {"code": code, "name": CODE_NAME.get(code, code), "net": round(v["net"]), "ret": v["ret"]}
            )
        for theme, items in by_theme.items():
            items.sort(key=lambda x: -x["net"])
            leaders[theme] = items[:LEADERS_N]

    out = []
    for theme, a in agg.items():
        net = a["f"] + a["i"]
        # 최근부터 거꾸로 세는 연속 순매수일 — "해운 N일째" 같은 추세 길이
        streak = 0
        for d in reversed(win):
            v = daily[theme].get(d)
            if v is None or v <= 0:
                break
            streak += 1
        out.append({
            "theme": theme,
            "net": round(net),
            "foreign": round(a["f"]),
            "inst": round(a["i"]),
            "value": round(a["v"]),
            # 강도% — 아카이브·실시간 카드와 같은 정의((외+기)/거래대금×100)
            "strength": round(net / a["v"] * 100, 2) if a["v"] > 0 else None,
            "streak": streak,
            "posDays": int(a["pos"]),
            "nDays": int(a["n"]),
            "slots": len(THEME_CODES.get(theme, [])),
            "leaders": leaders.get(theme, []),
        })
    out.sort(key=lambda x: -x["net"])
    return {
        "ready": True,
        "days": days,
        "from": win[0],
        "to": win[-1],
        "archiveDays": len(all_dates),
        "themes": out,
    }
