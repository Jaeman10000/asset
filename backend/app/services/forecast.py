"""예상 경로 — 다음 거래일 자금 유입 후보 테마 + 주도주, 그리고 실측 적중률.

원칙: **적중률 없는 예측은 만들지 않는다.** 점수만 보여주면 그 숫자를 믿을 근거가
없어 오히려 해롭다. 그래서 항상 워크포워드 백테스트(예측 시점 이후 데이터 절대 미참조)
결과를 함께 반환하고, 랜덤 기준선(19테마 중 3개 = 15.8%)과 비교해 보여준다.

── v2에서 모델을 갈아엎은 이유 ──────────────────────────────────
초기 모델은 '순환'을 가정했다: 전이확률 + 단기가속 + 순환여력(소외된 정도).
503거래일(2024-08 ~ 2026-08)이 쌓인 뒤 검증해보니 그 가정이 틀렸다.

  튜닝 구간과 검증 구간을 분리한 워크포워드 (검증 200일, 랜덤 Top3 = 15.8%)
    현재 모델(전이·가속·여력)          Top1 10.5%  Top3 25.0%
    지속만 (최근 5일 평균 강도 상위)     Top1 18.5%  Top3 36.0%   ← 압도
    가속만                          Top1  9.5%  Top3 23.0%
    여력만 (소외된 곳)                Top1  4.0%  Top3 12.0%   ← 랜덤보다 나쁨

  주간 선행-후행 상관 전수검정(109주, 361쌍 × 시차 1~4주, 본페로니 보정)
    통과한 쌍: 자기지속 6쌍 + 타 테마 1쌍(이차전지→전력/유틸 r=-0.38, 경합)
    '반도체 → 로봇' 같은 고정 순환 루트: r=+0.005 (p=0.96) — 근거 없음

즉 이 시장에서 실제로 관측되는 건 순환이 아니라 **지속(모멘텀)**이다.
'소외된 곳이 다음 차례'라는 직관은 데이터상 랜덤보다도 못했다. 그래서 여력을 버리고
지속을 주신호로 삼는다. 가중치는 검증 구간을 보지 않은 과거 구간에서만 골랐다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .themes import CODE_NAME, THEME_CODES
from . import flow_store

# 튜닝 구간(검증 200일과 겹치지 않는 과거 184일)에서 격자탐색으로 고른 값.
# 가속·여력은 어떤 가중치를 줘도 성능이 떨어져 0으로 수렴했다.
W_HOLD, W_TRANS = 1.0, 0.1
HOLD_DAYS = 5      # 지속 = 최근 5거래일 평균 강도
TOP_N = 3
LEADERS_N = 5


def _load() -> tuple[list[str], dict[str, dict[str, float]]]:
    """(날짜 오름차순, {theme: {date: strength}})"""
    rows = flow_store.sector_series(400)
    strength: dict[str, dict[str, float]] = defaultdict(dict)
    dates: set[str] = set()
    for date, theme, _f, _i, _v, s, _l in rows:
        strength[theme][date] = s
        dates.add(date)
    return sorted(dates), strength


def _leader_at(strength: dict[str, dict[str, float]], date: str) -> str | None:
    best, bv = None, None
    for theme, series in strength.items():
        v = series.get(date)
        if v is not None and (bv is None or v > bv):
            best, bv = theme, v
    return best


def _avg(series: dict[str, float], hist: list[str], k: int) -> float | None:
    v = [series[d] for d in hist[-k:] if d in series]
    return sum(v) / len(v) if v else None


def _score_at(
    dates: list[str], strength: dict[str, dict[str, float]], idx: int
) -> tuple[str | None, list[dict[str, Any]], int]:
    """dates[idx]까지의 정보만으로 다음 거래일 후보를 점수화 (미래 정보 차단)."""
    hist = dates[: idx + 1]
    cur = _leader_at(strength, hist[-1])

    # 전이 빈도 — 오늘 1위가 cur였을 때, 다음날 1위가 무엇이었나
    trans: dict[str, int] = defaultdict(int)
    total = 0
    for a, b in zip(hist, hist[1:]):
        if _leader_at(strength, a) == cur:
            nb = _leader_at(strength, b)
            if nb:
                trans[nb] += 1
                total += 1

    out = []
    for theme, series in strength.items():
        hold = _avg(series, hist, HOLD_DAYS)
        if hold is None:
            continue
        a3 = _avg(series, hist, 3)
        a10 = _avg(series, hist, 10)
        trans_p = (trans.get(theme, 0) / total * 100) if total else 0.0
        out.append({
            "theme": theme,
            "score": round(hold * W_HOLD + trans_p * W_TRANS, 1),
            "hold": round(hold, 1),
            "trans": round(trans_p, 1),
            "transN": trans.get(theme, 0),
            # 아래 둘은 점수에 안 들어간다 — 참고용 진단값(위 docstring의 검증 결과 참고)
            "accel": round(a3 - a10, 1) if (a3 is not None and a10 is not None) else 0.0,
            "room": round(-a10, 1) if a10 is not None else 0.0,
        })
    out.sort(key=lambda x: -x["score"])
    return cur, out, total


def _leaders(theme: str, dates: list[str]) -> list[dict[str, Any]]:
    """테마 내 최근 5거래일 누적 순매수 상위 — '돈이 들어올 때 누가 먼저 받나'."""
    if not dates:
        return []
    win = dates[-5:]
    rows = flow_store.stock_series(win[0])
    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"net": 0.0, "ret": 0.0})
    codes = set(THEME_CODES.get(theme, []))
    last = dates[-1]
    for date, code, th, f, i, _v, ret in rows:
        if th != theme or code not in codes:
            continue
        agg[code]["net"] += f + i
        if date == last:
            agg[code]["ret"] = ret
    out = [{"code": c, "name": CODE_NAME.get(c, c), "net5d": round(v["net"]), "ret": v["ret"]}
           for c, v in agg.items()]
    out.sort(key=lambda x: -x["net5d"])
    return out[:LEADERS_N]


def backtest(dates: list[str], strength: dict[str, dict[str, float]], days: int = 200) -> dict[str, Any]:
    """워크포워드 검증 — 각 시점에서 그 이전 데이터만으로 예측하고 다음날 실제와 대조."""
    n = hit1 = hit3 = 0
    start = max(15, len(dates) - days - 1)  # 최소 15일은 학습 구간으로 남김
    for idx in range(start, len(dates) - 1):
        _cur, ranked, _t = _score_at(dates, strength, idx)
        actual = _leader_at(strength, dates[idx + 1])
        if not actual or not ranked:
            continue
        n += 1
        names = [r["theme"] for r in ranked[:TOP_N]]
        if names and actual == names[0]:
            hit1 += 1
        if actual in names:
            hit3 += 1
    themes = max(1, len(strength))
    return {
        "n": n,
        "top1": hit1,
        "top3": hit3,
        "top1pct": round(hit1 / n * 100, 1) if n else 0.0,
        "top3pct": round(hit3 / n * 100, 1) if n else 0.0,
        "base1": round(100 / themes, 1),
        "base3": round(TOP_N / themes * 100, 1),
        "themes": themes,
    }


def forecast() -> dict[str, Any]:
    dates, strength = _load()
    if len(dates) < 12:
        return {
            "ready": False,
            "reason": f"데이터 {len(dates)}일 — 최소 12거래일 필요. 자금 흐름 수집을 먼저 실행하세요.",
            "days": len(dates),
        }
    cur, ranked, sample = _score_at(dates, strength, len(dates) - 1)
    cands = []
    for r in ranked[:TOP_N]:
        cands.append({**r, "leaders": _leaders(r["theme"], dates),
                      "slots": len(THEME_CODES.get(r["theme"], []))})
    return {
        "ready": True,
        "asOf": dates[-1],
        "curLeader": cur,
        "sampleN": sample,
        "candidates": cands,
        "backtest": backtest(dates, strength),
        "days": len(dates),
        "weights": {"hold": W_HOLD, "trans": W_TRANS, "holdDays": HOLD_DAYS},
    }
