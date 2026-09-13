"""미국편 compute — raw/us_kiwoom.json + raw/us.json + 환율 → data/D/computed_us.json (장면·대본·검증).
실행일 D(KST 아침), 세션 = 직전 미국 영업일(ET).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from _common import DATA, day_dir, load_json, log, save_json
sys.path.insert(0, str(DATA.parent))
from checks import forbidden  # noqa: E402
import narrate  # noqa: E402
from compute import kr_expiry  # noqa: E402
from app.keychain import get_api_key  # noqa: E402

MAJOR = {"Employment Situation": "미국 고용보고서", "Consumer Price Index": "미국 소비자물가 CPI", "Producer Price Index": "미국 생산자물가 PPI",
         "Job Openings": "미국 구인건수 JOLTS", "Productivity": "미국 생산성 지표", "Real Earnings": "미국 실질임금", "Employment Cost": "미국 고용비용지수"}
SECTOR_TO_KR = {"반도체": "반도체", "기술": "반도체", "금융": "금융", "헬스케어": "바이오/제약", "산업재": "조선", "에너지": "원전/에너지",
                "경기소비재": "자동차", "통신·미디어": "인터넷/게임"}


def kst_spoken(kst: str) -> str:
    h, m = int(kst[11:13]), int(kst[14:16])
    when = "밤" if h >= 18 else "오후" if h >= 12 else "새벽" if h < 6 else "오전"
    return f"{when} {h - 12 if h > 12 else h}시" + (f" {m}분" if m else "")


def _pct_at(mins: list[dict], t_et: str) -> float | None:
    row = next((m for m in mins if m["t_et"] >= t_et), None)
    return row["c"] if row else None


def compute_us(d: str) -> dict:
    raw = day_dir(d)
    kw = load_json(raw / "us_kiwoom.json") or {}
    us = load_json(raw / "us.json") or {}
    krx = load_json(raw / "krx.json") or {}
    usi = load_json(raw / "us_index.json") or {}
    news_us = load_json(raw / "news_us.json") or {}
    sess = kw.get("session_et") or us.get("session_et", "").replace("-", "")
    warnings: list[str] = []
    # 공식 지수(야후 ^IXIC 등) — 세션이 맞는 것만. ETF(QQQ)는 화면 보조·분봉용.
    idx = {k: v for k, v in (usi.get("index") or {}).items() if v and not v.get("missing") and v.get("session") == sess}
    if "IXIC" not in idx:
        warnings.append("나스닥 종합지수(야후) 없음 → QQQ 기준으로 서술")
    index, sectors = kw.get("index") or {}, kw.get("sectors") or {}
    q = index.get("QQQ") or {}
    mins = q.get("minutes") or []
    if not q or q.get("missing"):
        warnings.append("QQQ 세션 데이터 없음")
    if q and not q.get("complete"):
        warnings.append("QQQ 정규장 분봉 미완성")
    if mins:
        hi_t = max(mins, key=lambda m: m["h"])["t_et"]; lo_t = min(mins, key=lambda m: m["l"])["t_et"]
        q["order"] = "low_first" if lo_t < hi_t else "high_first"

    # 이벤트 + 반응(발표 시각 ET 기준, 개장 전이면 09:30부터 30분)
    events = []
    for e in us.get("bls") or []:
        if not e.get("et", "").startswith(sess[:4] + "-" + sess[4:6] + "-" + sess[6:]):
            continue
        ko = next((v for k, v in MAJOR.items() if k in e["what"]), None)
        if not ko:
            continue
        ev = {"kst": e["kst"], "kst_spoken": kst_spoken(e["kst"]), "what": ko, "et": e["et"]}
        if mins and q.get("prev_close"):
            t_et = e["et"][11:16].replace(":", "")
            t0 = max(t_et, "0930")
            h, m = int(t0[:2]), int(t0[2:])
            t1 = f"{(h * 60 + m + 30) // 60:02d}{(h * 60 + m + 30) % 60:02d}"
            p0 = q["prev_close"] if t_et < "0930" else _pct_at(mins, t0)
            p1 = _pct_at(mins, t1)
            if p0 and p1:
                ev["react30"] = round((p1 / p0 - 1) * 100, 2)
                ev["react_close"] = round((q["close"] / p1 - 1) * 100, 2)
        events.append(ev)
    fomc = [f for f in us.get("fomc_2026") or [] if f.split("/")[0].replace("-", "") == sess or (f.split("/")[0][:8] + f.split("/")[1]).replace("-", "") == sess]
    if fomc:
        events.insert(0, {"kst": "", "kst_spoken": "새벽 3시", "what": "FOMC 결과 발표", "et": ""})

    stocks = [v for v in (kw.get("stocks") or {}).values() if v and not v.get("missing")]
    MOVER_MIN = 3.0
    movers = sorted([x for x in stocks if x.get("pct") is not None and abs(x["pct"]) >= MOVER_MIN], key=lambda x: -abs(x["pct"]))
    if len(stocks) < 20:
        warnings.append(f"미국 종목 후보 {len(stocks)}/36만 수집")
    links = {k: v for k, v in (kw.get("links") or {}).items() if v and not v.get("missing")}
    btc = kw.get("btc")
    tre = us.get("treasury") or {}
    eia = us.get("eia") or {}
    wti = {"wti": eia.get("wti"), "chg_pct": eia.get("chg_pct"), "date": eia.get("date"),
           "fresh": eia.get("date", "").replace("-", "") == sess} if eia else {}
    fx = krx.get("fx")

    # 일정: 오늘 국장(만기) + 오늘 밤 미국(BLS) + FOMC. 월요일(주말 뒤)이면 이번 주 전체.
    dt = datetime.strptime(d, "%Y%m%d")
    weekend = (dt - datetime.strptime(sess, "%Y%m%d")).days >= 2
    horizon = 8
    span = {(dt + timedelta(days=i)).strftime("%Y%m%d") for i in range(horizon)}
    sched_us = [{"d": e["kst"], "t": v} for e in (us.get("bls") or []) for k, v in MAJOR.items()
                if k in e["what"] and e["kst"][:10].replace("-", "") in span]
    sched_kr = [x for x in kr_expiry(dt - timedelta(days=1)) if x["d"].replace("-", "") in span]
    for f in us.get("fomc_2026") or []:
        s0 = f.split("/")[0]
        if 0 <= (datetime.strptime(s0, "%Y-%m-%d") - dt).days <= 10:
            sched_us.append({"d": f.replace("/", "~"), "t": "FOMC"})
    sched_us.sort(key=lambda x: x["d"][:10])

    # 오늘 국장에서 볼 것: 직전 국장편의 watch 재사용, 없으면 섹터→테마 매핑
    watch = []
    prev_kr = None
    for back in range(1, 5):
        pd = (dt - timedelta(days=back)).strftime("%Y%m%d")
        c = load_json(DATA / pd / "computed_kr.json") or load_json(DATA / pd / "computed.json")
        if c and c.get("watch"):
            prev_kr = c; break
    if prev_kr:
        watch = [{"q": w["q"], "how": w["how"].replace("다음 거래일", "오늘").replace("다음 주", "오늘").replace("내일", "오늘"),
                  "assist": w.get("assist") or narrate.assist_for("us_link")} for w in prev_kr["watch"][:2]]
    secs = [v for v in sectors.values() if v and not v.get("missing")]
    if not watch and secs:
        top = max(secs, key=lambda x: x["pct"])
        kr_theme = SECTOR_TO_KR.get(top["name"])
        if kr_theme:
            watch = [{"q": f"미국 {top['name']} 강세가 국장 {kr_theme} 수급으로 이어지는지", "how": "15:40 테마 수급에서 확인", "assist": narrate.assist_for("us_link")}]
    stock_names = [x["name"] for x in stocks]
    watch = [w for w in watch if forbidden.watch_ok(w["how"]) and forbidden.assist_ok(w["assist"], stock_names)][:2]

    # 배경 문장(데이터 기반, 완곡) — polish가 뉴스 헤드라인으로 대체
    reason_fallback_us = ""
    if secs:
        top = max(secs, key=lambda x: x["pct"]); bot = min(secs, key=lambda x: x["pct"])
        nas_pct = (idx.get("IXIC") or q or {}).get("pct")
        if nas_pct is not None:
            reason_fallback_us = (f"{top['name']}가 올랐지만 나머지 대부분 섹터가 밀린 하루였습니다." if nas_pct < 0 and top["pct"] > 0
                                  else f"{top['name']}가 앞장서고 {bot['name']}가 뒤처진 하루였습니다.")

    # 전날 국장 외국인 확정 수급(연결 지표)
    prev_foreign = None
    if prev_kr and (prev_kr.get("investors") or {}).get("kospi"):
        prev_foreign = {"date": prev_kr["date"], "foreign": prev_kr["investors"]["kospi"].get("foreign"), "src": prev_kr["investors"].get("src")}
    bls_values = us.get("bls_values")
    from compute import _upload_times
    N = narrate.build_us({"brand": get_api_key("brand", "name"), "session_et": sess, "run_date": d, "weekend": weekend, "index": index, "idx": idx, "sectors": sectors,
                          "stocks": stocks, "movers": movers, "links": links, "btc": btc, "prev_foreign": prev_foreign, "bls_values": bls_values, "reason_fallback_us": reason_fallback_us,
                          "has_news": bool(news_us.get("items")), "upload_times": _upload_times(),
                          "events": events, "tre": tre, "wti": wti, "fx": fx, "schedule_kr": sched_kr, "schedule_us": sched_us, "watch": watch})
    scenes = N["scenes"]
    import glossary
    gloss = glossary.apply(scenes, d)
    texts = {sc["id"]: sc["tts"] for sc in scenes}
    bad = forbidden.check_all(texts)
    if bad:
        warnings.append(f"금지어: {bad}")

    sess_dt = datetime.strptime(sess, "%Y%m%d")
    idx_line = [idx[k] for k in ("IXIC", "GSPC", "DJI", "SOX") if k in idx] or [v for v in index.values() if v and not v.get("missing")]
    ev_line = ""
    if events:
        e = events[0]
        vs = narrate.event_values_spoken(bls_values).rstrip(".")
        ev_line = f"{e['what']}: " + (vs + ". " if vs else "") + (f"발표 뒤 30분 {'+' if e.get('react30', 0) > 0 else ''}{e.get('react30', 0):.2f}%, 마감까지 {'+' if e.get('react_close', 0) > 0 else ''}{e.get('react_close', 0):.2f}%" if e.get("react30") is not None else "")
    gates = narrate.pick_gates(sched_kr + sched_us, 3)
    bot3 = [x for x in sorted(secs, key=lambda x: x['pct'])[:2] if x['pct'] < 0]
    caption = "\n".join(x for x in [
        f"{sess_dt.month}/{sess_dt.day} 미국장 마감 — {N['headline']}",
        " · ".join(f"{v['name']} {'+' if v['pct'] > 0 else ''}{v['pct']:.2f}%" for v in idx_line),
        ev_line or "예정 지표 없음.",
        ("돈의 흐름: " + ", ".join(f"{x['name']} {'+' if x['pct'] > 0 else ''}{x['pct']:.2f}%" for x in sorted(secs, key=lambda x: -x['pct'])[:3]) + " 유입"
         + (" / " + ", ".join(f"{x['name']} {x['pct']:.2f}%" for x in bot3) + " 유출" if bot3 else "")) if secs else "",
        (f"오늘 국장 체크: {watch[0]['q']}" if watch else ""),
        ("다음 관문: " + " · ".join(narrate.gate_spoken(g) for g in gates) + ".") if gates else "",
    ] if x)
    out = {
        "edition": "us", "date": d, "session_et": sess, "date_label": f"{sess_dt.month}/{sess_dt.day} {'월화수목금토일'[sess_dt.weekday()]}",
        "generated_at": datetime.now().isoformat(timespec="seconds"), "brand": N["brand"], "tagline": N["tagline"],
        "index": {k: ({kk: vv for kk, vv in v.items() if kk != "minutes"} if v else None) for k, v in index.items()},
        "qqq_points": [{"t": m["t_kst"], "pct": round((m["c"] / q["prev_close"] - 1) * 100, 3)} for m in mins] if mins and q.get("prev_close") else [],
        "sectors": sorted([{k: v for k, v in x.items() if k != "minutes"} for x in secs], key=lambda x: -x["pct"]),
        "events": events, "tre": tre, "wti": wti, "fx": fx, "schedule": narrate.pick_gates(sched_kr + sched_us, 4), "watch": watch, "weekend": weekend,
        "u3_title": N["u3_title"], "headline": N["headline"], "hook": N.get("hook"), "idx": idx, "bls_values": bls_values,
        "news_items": (news_us.get("items") or [])[:20], "glossary": gloss,
        "movers": [{k: v for k, v in x.items() if k != "minutes"} for x in movers][:8], "mover_min": MOVER_MIN, "stocks": sorted([{k: v for k, v in x.items() if k != "minutes"} for x in stocks], key=lambda x: -abs(x["pct"])),
        "links": {k: {kk: vv for kk, vv in v.items() if kk != "minutes"} for k, v in links.items()}, "btc": btc, "prev_foreign": prev_foreign,
        "caption": caption, "scenes": scenes, "warnings": warnings, "forbidden": bad,
        "sources": {"idx": usi.get("src"), "us": "키움 usa06011/usa06012 (QQQ·SPY·DIA·섹터 ETF 12)", "events": "BLS·Fed", "treasury": tre.get("src"), "fx": (fx or {}).get("src"), "news": "Google News RSS"},
    }
    save_json(DATA / d / "computed_us.json", out)
    for w in warnings:
        log(d, "compute_us", "⚠ " + w)
    log(d, "compute_us", f"저장 computed_us.json — 세션 {sess}, 이벤트 {len(events)}, 섹터 {len(secs)}")
    return out


if __name__ == "__main__":
    compute_us(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
