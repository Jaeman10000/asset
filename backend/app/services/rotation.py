"""순환 지도 — "A 다음엔 B" 라는 루트가 우리 데이터에 실제로 있는지 측정한다.

시장에는 '반도체 → 로봇 → 전기' 같은 순환 루트가 통념으로 돌아다닌다. 이걸
믿고 쓸 것인지 아닌지는 **측정해서** 정할 문제다. 그래서 이 모듈은 예측을 하지
않고, 우리가 모은 아카이브에서 관측된 것만 그대로 낸다.

두 가지를 낸다:
  ① 주간 전이 — 어떤 테마가 그 주 1위였을 때, 다음 주 1위는 실제로 무엇이었나.
     주간으로 묶는 이유: 일간은 노이즈가 커서 1위가 하루 만에 튄다.
  ② 선행-후행 상관 — A의 이번 주 강도가 B의 다음 주 강도를 예측하는가(Pearson r).
     1위끼리만 보는 ①과 달리 모든 주·모든 쌍을 쓰므로 표본이 훨씬 크다.

다중비교 보정을 반드시 건다. 19×19=361쌍을 동시에 보면 p<0.05짜리 '우연한
발견'이 18개쯤 저절로 나온다. 본페로니(0.05/쌍수)를 넘긴 것만 유의로 표시한다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any

from . import flow_store

MIN_N = 30          # 상관 계산 최소 표본(주)
MIN_TRANS = 4       # 전이 표를 보여줄 최소 관측 횟수


def _weekly() -> tuple[list[str], list[str], dict[str, list[float | None]], list[str | None]]:
    """(주 목록, 테마 목록, {테마: 주간 강도 시계열}, 주간 1위)"""
    rows = flow_store.sector_series(9999)
    agg: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for date, theme, f, i, v, _s, _leader in rows:
        try:
            y, w, _ = datetime.strptime(date, "%Y%m%d").isocalendar()
        except ValueError:
            continue
        cell = agg[f"{y}-W{w:02d}"][theme]
        cell[0] += f + i
        cell[1] += v

    weeks = sorted(agg)
    themes = sorted({t for w in weeks for t in agg[w]})
    series: dict[str, list[float | None]] = {t: [] for t in themes}
    leaders: list[str | None] = []
    for w in weeks:
        st = {t: (n / v * 100) for t, (n, v) in agg[w].items() if v > 0}
        for t in themes:
            series[t].append(st.get(t))
        leaders.append(max(st, key=st.get) if st else None)
    return weeks, themes, series, leaders


def _pearson(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    n = len(pairs)
    if n < MIN_N:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    if abs(r) >= 1:
        return r, 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return r, math.erfc(abs(t) / math.sqrt(2))  # 양측 p (정규근사, n>100)


def rotation(lag: int = 1) -> dict[str, Any]:
    lag = max(1, min(4, lag))
    weeks, themes, series, leaders = _weekly()
    if len(weeks) < MIN_N:
        return {"ready": False, "reason": f"주간 표본 {len(weeks)}주 — 최소 {MIN_N}주 필요.",
                "weeks": len(weeks)}

    n_theme = max(1, len(themes))
    base = 100 / n_theme

    # ① 주간 전이
    trans: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tot: dict[str, int] = defaultdict(int)
    for a, b in zip(leaders, leaders[lag:]):
        if a and b:
            trans[a][b] += 1
            tot[a] += 1
    changes = sum(1 for a, b in zip(leaders, leaders[1:]) if a and b and a != b)
    pairs_n = sum(1 for a, b in zip(leaders, leaders[1:]) if a and b)

    trans_out = []
    for src in sorted(tot, key=lambda k: -tot[k]):
        if tot[src] < MIN_TRANS:
            continue
        nxt = sorted(trans[src].items(), key=lambda x: -x[1])[:4]
        trans_out.append({
            "from": src,
            "n": tot[src],
            "to": [{"theme": k, "n": v, "pct": round(v / tot[src] * 100, 1), "self": k == src}
                   for k, v in nxt],
        })

    # ② 선행-후행 상관 (자기지속 포함, 플래그로 구분)
    tests = n_theme * n_theme
    alpha = 0.05 / tests
    links = []
    for a in themes:
        for b in themes:
            pairs = [(x, y) for x, y in zip(series[a][:-lag], series[b][lag:])
                     if x is not None and y is not None]
            got = _pearson(pairs)
            if not got:
                continue
            r, p = got
            if p < alpha:
                links.append({
                    "from": a, "to": b, "r": round(r, 3), "p": p,
                    "n": len(pairs), "self": a == b,
                    "sign": "동행" if r > 0 else "경합",
                })
    links.sort(key=lambda x: -abs(x["r"]))

    return {
        "ready": True,
        "lag": lag,
        "weeks": len(weeks),
        "from": weeks[0],
        "to": weeks[-1],
        "themes": n_theme,
        "base": round(base, 1),
        "changeRate": round(changes / pairs_n * 100, 1) if pairs_n else 0.0,
        "alpha": alpha,
        "tests": tests,
        "transitions": trans_out,
        "links": links,
        "selfLinks": len([x for x in links if x["self"]]),
        "crossLinks": len([x for x in links if not x["self"]]),
    }


def check_route(route: list[str], lag: int = 1) -> dict[str, Any]:
    """사용자가 믿는 루트(예: 반도체→로봇→전력/유틸)가 데이터에 있는지 구간별로 검정."""
    weeks, themes, series, _leaders = _weekly()
    alpha = 0.05 / max(1, len(themes) ** 2)
    steps = []
    for a, b in zip(route, route[1:]):
        if a not in series or b not in series:
            steps.append({"from": a, "to": b, "error": "없는 테마"})
            continue
        pairs = [(x, y) for x, y in zip(series[a][:-lag], series[b][lag:])
                 if x is not None and y is not None]
        got = _pearson(pairs)
        if not got:
            steps.append({"from": a, "to": b, "error": "표본 부족"})
            continue
        r, p = got
        steps.append({"from": a, "to": b, "r": round(r, 3), "p": round(p, 4),
                      "n": len(pairs), "significant": p < alpha})
    return {"route": route, "lag": lag, "alpha": alpha, "steps": steps,
            "supported": bool(steps) and all(s.get("significant") for s in steps)}
