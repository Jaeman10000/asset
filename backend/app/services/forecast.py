"""예상 경로 — 다음 거래일 자금 유입 후보 테마 + 주도주, 그리고 실측 적중률.

원칙: **적중률 없는 예측은 만들지 않는다.** 점수만 보여주면 그 숫자를 믿을 근거가
없어 오히려 해롭다. 그래서 항상 워크포워드 백테스트(예측 시점 이후 데이터 절대 미참조)
결과를 함께 반환하고, 랜덤 기준선(19테마 중 3개 = 15.8%)과 비교해 보여준다.

점수 = 3개 신호의 가중합 (가중치는 손으로 정한 초기값 — 데이터가 쌓이면 튜닝 대상)
  ① 전이확률  오늘 1위 테마 다음날 이 테마가 1위였던 과거 비율   × 0.45
  ② 단기가속  최근 3일 평균 강도 − 10일 평균 강도 (조용한 매집)   × 2.20
  ③ 순환여력  최근 10일 평균 강도의 음수 (소외된 정도)            × 0.80
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .themes import CODE_NAME, THEME_CODES
from . import flow_store

W_TRANS, W_ACCEL, W_ROOM = 0.45, 2.20, 0.80
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


def _score_at(
    dates: list[str], strength: dict[str, dict[str, float]], idx: int
) -> tuple[str | None, list[dict[str, Any]], int]:
    """dates[idx]까지의 정보만으로 다음 거래일 후보를 점수화 (미래 정보 차단)."""
    hist = dates[: idx + 1]
    cur = _leader_at(strength, hist[-1])

    # ① 전이 빈도
    trans: dict[str, int] = defaultdict(int)
    total = 0
    for a, b in zip(hist, hist[1:]):
        if _leader_at(strength, a) == cur:
            nb = _leader_at(strength, b)
            if nb:
                trans[nb] += 1
                total += 1

    recent10 = hist[-10:]
    recent3 = hist[-3:]
    out = []
    for theme, series in strength.items():
        s3 = [series[d] for d in recent3 if d in series]
        s10 = [series[d] for d in recent10 if d in series]
        if not s3 or not s10:
            continue
        avg3, avg10 = sum(s3) / len(s3), sum(s10) / len(s10)
        trans_p = (trans.get(theme, 0) / total * 100) if total else 0.0
        accel = avg3 - avg10
        room = -avg10
        out.append({
            "theme": theme,
            "score": round(trans_p * W_TRANS + max(0.0, accel) * W_ACCEL + max(0.0, room) * W_ROOM, 1),
            "trans": round(trans_p, 1),
            "transN": trans.get(theme, 0),
            "accel": round(accel, 1),
            "room": round(room, 1),
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


def backtest(dates: list[str], strength: dict[str, dict[str, float]], days: int = 60) -> dict[str, Any]:
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
        "weights": {"trans": W_TRANS, "accel": W_ACCEL, "room": W_ROOM},
    }
