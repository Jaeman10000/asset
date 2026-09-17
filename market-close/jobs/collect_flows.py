"""15:40 테마 수급 — flow_collector로 오늘치 아카이브를 채우고, 「돈의 이동」 3줄을 판정한다 (SPEC §5-3).
결과: data/D/raw/flows.json
"""
from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from datetime import datetime

from _common import day_dir, log, save_json
from app.services import flow_collector, flow_store  # noqa: E402
from app.services.themes import CODE_NAME  # noqa: E402


def _iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _theme_table(day: dict) -> dict[str, dict]:
    """테마별 {net, foreign, inst, ret(거래대금 가중), pos_stocks, leader_share, stocks[]}"""
    per: dict[str, dict] = defaultdict(lambda: {"net": 0.0, "foreign": 0.0, "inst": 0.0, "wret": 0.0, "wval": 0.0,
                                                "pos": [], "stocks": []})
    for s in day["stocks"]:
        t = s["theme"]
        n = s["foreign"] + s["inst"]
        p = per[t]
        p["net"] += n; p["foreign"] += s["foreign"]; p["inst"] += s["inst"]
        p["wret"] += s["ret"] * s["value"]; p["wval"] += s["value"]
        p["stocks"].append({"code": s["code"], "name": s["name"], "net": round(n), "ret": s["ret"]})
        if n > 0:
            p["pos"].append(s["name"])
    out = {}
    for t, p in per.items():
        stocks = sorted(p["stocks"], key=lambda x: -x["net"])
        top = stocks[0]["net"] if stocks else 0
        pos_sum = sum(x["net"] for x in stocks if x["net"] > 0)
        out[t] = {"net": round(p["net"]), "foreign": round(p["foreign"]), "inst": round(p["inst"]),
                  "ret": round(p["wret"] / p["wval"], 2) if p["wval"] else 0.0,
                  "pos_count": len(p["pos"]), "pos_names": [x["name"] for x in stocks if x["net"] > 0][:4],
                  "leader_share": round(top / pos_sum, 2) if pos_sum > 0 else 0.0, "stocks": stocks}
    return out


def _streak(series: list[tuple[str, float]], upto: str) -> int:
    """upto(포함)에서 거꾸로 센 연속 순매수(>0) 일수. 순매도면 음수로 연속 순매도 일수."""
    vals = [n for d, n in series if d <= upto]
    if not vals:
        return 0
    sign = 1 if vals[-1] > 0 else -1
    k = 0
    for n in reversed(vals):
        if (n > 0 and sign > 0) or (n < 0 and sign < 0):
            k += 1
        else:
            break
    return k * sign


def judge(d: str) -> dict:
    # JSON이 원본, SQLite는 인덱스. 앱이 안 떠 있으면 인덱스가 뒤처지므로(실측: 8/28에서 멈춤) 먼저 맞춘다.
    filled = flow_store.reconcile()
    if filled:
        log(d, "flows", f"SQLite 인덱스 보충 {filled}일")
    dates_c = [x.replace("-", "") for x in flow_store.saved_dates()]
    if d not in dates_c:
        return {"ready": False, "reason": f"{d} 아카이브 없음", "have": dates_c[-3:]}
    i = dates_c.index(d)
    if i == 0:
        return {"ready": False, "reason": "전일 없음"}
    y = dates_c[i - 1]
    today = flow_store.load_day(d)
    yday = flow_store.load_day(y)
    if not today or not yday:
        return {"ready": False, "reason": "로드 실패"}
    T, Y = _theme_table(today), _theme_table(yday)

    # 테마별 일별 net 시계열(최근 30일) → streak, 5일 평균 강도
    rows = flow_store.sector_series(40)
    ser: dict[str, list[tuple[str, float]]] = defaultdict(list)
    strength: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for date, theme, f, inst, v, s, _l in rows:
        dd = date.replace("-", "")
        ser[theme].append((dd, f + inst)); strength[theme].append((dd, s))
    for t in ser:
        ser[t].sort(); strength[t].sort()

    def avg5(t: str) -> float:
        xs = [s for dd, s in strength[t] if dd <= d][-5:]
        return round(sum(xs) / len(xs), 2) if xs else 0.0

    def state(t: str) -> dict:
        ty, tt = Y.get(t, {"net": 0, "pos_count": 0, "leader_share": 0}), T.get(t, {"net": 0, "pos_count": 0, "leader_share": 0})
        ny, nt = ty["net"], tt["net"]
        st = _streak(ser[t], d)
        a5 = avg5(t)
        s = "혼조"
        if nt > 0 and st >= 2:
            s = "쌓임"
            if tt["pos_count"] >= ty["pos_count"] + 2 or (ty["leader_share"] - tt["leader_share"]) >= 0.20:
                s = "쌓임+확산"
        if ny < 0 < nt and a5 < 0:
            s = "되돌림"
        if ny < 0 and nt < 0:
            if abs(nt) < 0.5 * abs(ny):
                s = "매도 축소"
            elif abs(nt) > 1.5 * abs(ny):
                s = "매도 확대"
            else:
                s = "매도 지속"
        if ny > 0 > nt:
            s = "이탈"
        return {"theme": t, "y": ny, "t": nt, "delta": nt - ny, "state": s, "streak": st, "avg5_strength": a5,
                "foreign": tt.get("foreign", 0), "inst": tt.get("inst", 0), "ret": tt.get("ret", 0.0),
                "spread_names": tt.get("pos_names", []), "pos_count_y": ty["pos_count"], "pos_count_t": tt["pos_count"]}

    lead_y = max(Y, key=lambda t: Y[t]["net"])
    lead_t = max(T, key=lambda t: T[t]["net"])
    rows_out = [state(lead_y)]
    if lead_t != lead_y and Y.get(lead_t, {"net": 0})["net"] < 0 < T[lead_t]["net"]:
        rows_out.append(state(lead_t))
    else:
        rev = [t for t in T if Y.get(t, {"net": 0})["net"] < 0 < T[t]["net"] and t != lead_y]
        if rev:
            rows_out.append(state(max(rev, key=lambda t: T[t]["net"])))
    used = {r["theme"] for r in rows_out}
    big = max((t for t in T if t not in used), key=lambda t: abs(T[t]["net"] - Y.get(t, {"net": 0})["net"]), default=None)
    if big:
        rows_out.append(state(big))
    if rows_out[0]["state"] == "이탈" and lead_t != lead_y:
        rows_out[0]["state"] = "이동"; rows_out[0]["moved_to"] = lead_t
    total_t = sum(v["net"] for v in T.values()); total_y = sum(v["net"] for v in Y.values())
    missing = 95 - len(today["stocks"])
    top = state(max(T, key=lambda t: abs(T[t]["net"])))   # '가장 큰 돈이 빠진/들어간 곳'은 전체 테마 기준(영상 s3)
    return {"ready": True, "date": d, "prev": y, "moves": rows_out[:3], "top": top, "leader_y": lead_y, "leader_t": lead_t,
            "total_t": round(total_t), "total_y": round(total_y), "missing_stocks": missing,
            "table_t": {t: {k: v for k, v in x.items() if k != "stocks"} for t, x in T.items()},
            "table_y": {t: {k: v for k, v in x.items() if k != "stocks"} for t, x in Y.items()}}


async def main(d: str) -> None:
    raw = day_dir(d)
    flow_store.init_flow_db()
    have = {x.replace("-", "") for x in flow_store.saved_dates()}
    if d not in have:
        # flow_collector 는 15:40 까지(kr_session)는 오늘치를 저장하지 않는다 — 15:31 수집이 빈손으로 끝났던 일(2026-09-17)
        import time as _t
        from app.services.market_hours import kr_session, now_kst
        if d == now_kst().strftime("%Y%m%d") and kr_session():
            n = now_kst()
            wait = (n.replace(hour=15, minute=40, second=45, microsecond=0) - n).total_seconds()
            if 0 < wait <= 900:
                log(d, "flows", f"장 마감 정리 시간(~15:40) — {wait:.0f}초 기다렸다 수집")
                _t.sleep(wait)
        log(d, "flows", "아카이브에 오늘치 없음 → flow_collector.collect() 실행 (약 80초)")
        res = await flow_collector.collect(pages=1, only_missing=True)
        log(d, "flows", f"collect: {res.get('saved', res)}")
    j = judge(d)
    save_json(raw / "flows.json", j)
    if j.get("ready"):
        for m in j["moves"]:
            log(d, "flows", f"{m['theme']}: {m['y']} → {m['t']} [{m['state']}] streak={m['streak']} avg5={m['avg5_strength']}")
    else:
        log(d, "flows", f"판정 불가: {j}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")))
