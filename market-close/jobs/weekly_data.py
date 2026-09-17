"""주간 영상용 데이터 집계(월~금 한 주) → data/weekly/<build_date>/computed_weekly.json

새로 수집하는 건 없다(아래 빈칸 채우기만 예외). 전부 일별 파일을 더하고 고른다.
  - data/<d>/computed_kr.json      kospi(전일종가·종가·등락·고저), investors.kospi(개인·외국인·기관·기타법인, 억원)
  - data/<d>/raw/flows.json        table_t = 그날 테마별 외국인+기관 순매수(억원) → 주간 합
  - data/<d>/raw/krx_investors.json kospi_days = 거래소 집계 투자자별(최근 10거래일) → 주말 기준 연속 일수
  - data/<d>/raw/kiwoom_sum.json   kospi.top_others_buy(종목별 기타법인 상위), 없으면 kiwoom_top_others.json
      둘 다 없으면 collect_kiwoom_sum.market_sum()(키움 ka10099·ka10059 조회 전용, 하루 약 2분)으로 채워
      data/<d>/raw/kiwoom_top_others.json(새 파일만, 덮어쓰지 않음)에 저장
  - 한 주 동안 상위 5에 한 번이라도 든 종목 + 자사주 종목은 ka10059 일별 이력(종목당 1콜, 100거래일)으로
      상위 5 밖이던 날 값을 채운다 → 주간 합이 '상위 5에 든 날만의 합'으로 줄어들지 않게.
      이력은 data/weekly/<build_date>/others_codes.json에 캐시.
  - data/buybacks.json(자사주 매입 프로그램), data/ledger.json(예고→검증 전적), data/<d>/raw/us_index.json(나스닥·SOX)
단위: 억원(+ = 순매수), 지수 포인트, 등락 %. buyback_share는 비율(0~1, 기타법인 주간 합 대비).

실행: python weekly_data.py 20260911 20260912      (week_end, build_date)
      python weekly_data.py 20260911 20260912 --no-fetch   (키움 조회 없이 있는 파일로만)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

from _common import DATA, day_dir, load_json, save_json

WEEKLY = DATA / "weekly"
WD = "월화수목금토일"


# ───────────────────────── 기본 ─────────────────────────

def _lbl(d: str) -> str:
    dt = datetime.strptime(d, "%Y%m%d")
    return f"{dt.month}/{dt.day}({WD[dt.weekday()]})"


def _ck(d: str) -> dict:
    return load_json(DATA / d / "computed_kr.json") or {}


def _raw(d: str, name: str):
    return load_json(DATA / d / "raw" / name)


def week_days(week_end: str) -> list[str]:
    """week_end가 속한 주의 월~금 중 computed_kr.json이 있는 날(휴장일은 빠진다)."""
    end = datetime.strptime(week_end, "%Y%m%d")
    mon = end - timedelta(days=end.weekday())
    out = []
    for i in range(5):
        d = (mon + timedelta(days=i)).strftime("%Y%m%d")
        if d <= week_end and (DATA / d / "computed_kr.json").exists():
            out.append(d)
    return out


def _prior_day(d: str) -> str | None:
    """d 직전의 데이터 있는 거래일(computed_kr.json 기준)."""
    prior = sorted(p.name for p in DATA.iterdir()
                   if p.is_dir() and p.name.isdigit() and len(p.name) == 8 and p.name < d and (p / "computed_kr.json").exists())
    return prior[-1] if prior else None


def _streak(vals: list[float]) -> int:
    """최근값부터(내림차순) 같은 부호 연속 일수. +면 순매수 연속, -면 순매도 연속."""
    if not vals or not vals[0]:
        return 0
    s = 1 if vals[0] > 0 else -1
    n = 0
    for v in vals:
        if v and (v > 0) == (s > 0):
            n += 1
        else:
            break
    return s * n


def _in_window(d: str, prog: dict) -> bool:
    f = (prog.get("from") or "").replace("-", "")
    t = (prog.get("to") or "").replace("-", "")
    return (not f or d >= f) and (not t or d <= t)


# ───────────────────────── 코스피 ─────────────────────────

def _kospi(days: list[str], cks: dict, warn: list[str]) -> dict:
    first = cks[days[0]].get("kospi") or {}
    prev_close = first.get("prev_close")
    pd = _prior_day(days[0])
    if pd:
        pc = (_ck(pd).get("kospi") or {}).get("close")
        if pc is not None and prev_close is not None and abs(pc - prev_close) > 0.005:
            warn.append(f"전주 종가 불일치: {days[0]} prev_close {prev_close} vs {pd} close {pc}")
        if prev_close is None:
            prev_close = pc
    rows = []
    for d in days:
        k = cks[d].get("kospi") or {}
        rows.append({"d": d, "close": k.get("close"), "chg_pct": k.get("chg_pct"), "high": k.get("high"), "low": k.get("low")})
    last = rows[-1]["close"]
    week_chg = round((last / prev_close - 1) * 100, 2) if (last and prev_close) else None
    week_high = max(r["high"] for r in rows)
    week_low = min(r["low"] for r in rows)

    # 이벤트: 종가가 1,000단위 선을 넘나든 날 + 주간 장중 고점·저점
    events = []
    pc = prev_close
    for r in rows:
        c = r["close"]
        if pc and c:
            lo, hi = sorted((pc, c))
            for line in range(int(lo // 1000 + 1) * 1000, int(hi) + 1, 1000):
                cs = f"{c:,.2f}"
                ro = "으로" if cs[-1] in "036" else "로"   # 영·삼·육 받침 → 으로
                if pc < line <= c:
                    events.append({"d": r["d"], "kind": "regained", "line": line,
                                   "text": f"{_lbl(r['d'])} 코스피는 {cs}{ro} {line:,}선 위에서 마감했습니다."})
                elif c < line <= pc:
                    events.append({"d": r["d"], "kind": "lost", "line": line,
                                   "text": f"{_lbl(r['d'])} 코스피는 {cs}{ro} {line:,}선을 내줬습니다."})
        pc = c
    hd = next(r["d"] for r in rows if r["high"] == week_high)
    ld = next(r["d"] for r in rows if r["low"] == week_low)
    events.append({"d": hd, "kind": "high", "line": week_high, "text": f"이번 주 장중 고점은 {_lbl(hd)}의 {week_high:,.2f}입니다."})
    events.append({"d": ld, "kind": "low", "line": week_low, "text": f"이번 주 장중 저점은 {_lbl(ld)}의 {week_low:,.2f}입니다."})
    order = {"regained": 0, "lost": 0, "high": 1, "low": 1}
    events.sort(key=lambda e: (e["d"], order[e["kind"]]))
    return {"prev_close": prev_close, "days": rows, "week_chg_pct": week_chg,
            "week_high": week_high, "week_low": week_low, "events": events}


# ───────────────────────── 투자자 ─────────────────────────

KEYS = ("indiv", "foreign", "inst", "others")


def _krx_days(week_end: str, days: list[str]) -> list[dict]:
    """주말(없으면 그 전) krx_investors.json의 kospi_days — 가장 늦게 받은 파일이 확정치에 가장 가깝다."""
    for d in sorted(days, reverse=True):
        j = _raw(d, "krx_investors.json")
        if j and j.get("kospi_days"):
            return sorted((r for r in j["kospi_days"] if r.get("date") <= week_end), key=lambda r: r["date"], reverse=True)
    return []


def _inv(days: list[str], cks: dict, week_end: str, warn: list[str]) -> dict:
    rows = []
    for d in days:
        k = (cks[d].get("investors") or {}).get("kospi") or {}
        if any(k.get(x) is None for x in KEYS):
            warn.append(f"{d} investors.kospi 결측: {k}")
        rows.append({"d": d, **{x: int(k.get(x) or 0) for x in KEYS}})
    week = {x: sum(r[x] for r in rows) for x in KEYS}
    kd = _krx_days(week_end, days)
    streak = {}
    if kd and kd[0]["date"] == week_end:
        for x in ("foreign", "inst"):
            s = _streak([r.get(x) or 0 for r in kd])
            if abs(s) >= len(kd):
                warn.append(f"{x} 연속 {s}일 = 창({len(kd)}일) 끝까지 — 실제로는 더 길 수 있음")
            streak[x] = s
    else:
        warn.append(f"krx_investors kospi_days에 {week_end} 없음 → computed_kr inv_streak 사용")
        ist = cks[week_end].get("inv_streak") or {}
        for x in ("foreign", "inst"):
            streak[x] = int((ist.get(x) or {}).get("streak") or 0)
    return {"days": rows, "week": week, "streak_end": streak}


# ───────────────────────── 테마 ─────────────────────────

def _themes(days: list[str], warn: list[str]) -> dict:
    tables = {}
    for d in days:
        f = _raw(d, "flows.json") or {}
        t = f.get("table_t")
        if not t:
            warn.append(f"{d} flows.json table_t 없음")
            t = {}
        tables[d] = t
    names = []
    for d in days:
        for n in tables[d]:
            if n not in names:
                names.append(n)
    out = []
    for n in names:
        per = []
        fo = ins = 0
        for d in days:
            r = tables[d].get(n)
            if r is None:
                warn.append(f"{d} 테마 '{n}' 없음 → 0")
                r = {}
            per.append({"d": d, "net": int(r.get("net") or 0)})
            fo += int(r.get("foreign") or 0)
            ins += int(r.get("inst") or 0)
        out.append({"theme": n, "net": sum(p["net"] for p in per), "foreign": fo, "inst": ins,
                    "days": per, "pos_days": sum(1 for p in per if p["net"] > 0)})
    out.sort(key=lambda r: -r["net"])
    need = 4 if len(days) >= 5 else max(len(days) - 1, 1)
    return {"week": out,
            "top_out": dict(min(out, key=lambda r: r["net"])) if out else None,
            "top_in": dict(max(out, key=lambda r: r["net"])) if out else None,
            "stayed": [r["theme"] for r in out if r["pos_days"] >= need]}


# ───────────────────────── 기타법인 종목 ─────────────────────────

def _saved_tops(d: str) -> tuple[list[dict] | None, dict, str | None]:
    """그날 저장된 종목별 기타법인 상위(매수 5·매도 5). (top_buy, {code: v}, 파일명). 우선순위: kiwoom_sum → kiwoom_top_others."""
    for name in ("kiwoom_sum.json", "kiwoom_top_others.json"):
        k = ((_raw(d, name) or {}).get("kospi") or {})
        if k.get("top_others_buy") is not None:
            vals = {r["code"]: int(r["v"]) for r in (k.get("top_others_buy") or []) + (k.get("top_others_sell") or [])}
            return k["top_others_buy"], vals, name
    return None, {}, None


async def _kiwoom_fill(missing_days: list[str], codes_fn, week_end: str) -> dict:
    """키움 조회 전용(ka10099·ka10059). (1) 상위 목록 없는 날 market_sum() → kiwoom_top_others.json 새 파일(있으면 건너뜀),
    (2) 백필 뒤 codes_fn()이 돌려준 종목의 ka10059 이력(dt=week_end, 100거래일) → {code: {d: 억원}}."""
    import httpx

    from _common import kiwoom_call, num
    from app.services.kiwoom_client import KiwoomClient
    from collect_kiwoom_sum import market_sum

    hist = {}
    c = KiwoomClient()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        for d in missing_days:
            p = day_dir(d) / "kiwoom_top_others.json"
            if p.exists():
                continue
            print(f"  [backfill] {d} market_sum(kospi) … (약 2분)", flush=True)
            s = await market_sum(hc, tok, "0", d)
            if not s.get("n_got"):
                print(f"  [backfill] {d} 응답 없음 — 저장 안 함", flush=True)
                continue
            save_json(p, {"date": d, "unit": "억원", "definition": "주권 전 종목 ka10059 합산(ETF·ETN·ELW 제외)",
                          "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "backfill": "weekly_data.py", "kospi": s})
            print(f"  [backfill] {d} 기타법인 {s['others']:+,} | 상위 {[(r['name'], r['v']) for r in s['top_others_buy']]} "
                  f"| {s['n_got']}/{s['n_codes']} {s['seconds']}s", flush=True)
        for code in codes_fn():
            dd, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059",
                                         {"dt": week_end, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
            hist[code] = {r["dt"]: num(r.get("etc_corp")) / 100 for r in dd.get("stk_invsr_orgn") or [] if r.get("dt")}
    return hist


def _others_stocks(days: list[str], week_start: str, week_end: str, build_date: str, programs: list[dict],
                   others_week: int, fetch: bool, warn: list[str], diag: dict) -> dict:
    tops = {d: _saved_tops(d) for d in days}
    missing = [d for d in days if tops[d][0] is None]
    active = [p for p in programs if any(_in_window(d, p) for d in days)]
    names = {p["code"]: p["name"] for p in programs}
    for d in days:
        for r in tops[d][0] or []:
            names.setdefault(r["code"], r["name"])

    cache_p = WEEKLY / build_date / "others_codes.json"
    cache = load_json(cache_p) or {}
    hist = {c: v for c, v in (cache.get("codes") or {}).items()} if cache.get("dt") == week_end else {}

    def union() -> list[str]:
        cs = [p["code"] for p in active]
        for d in days:
            for r in tops[d][0] or []:
                if r["code"] not in cs:
                    cs.append(r["code"])
        return cs

    def need_codes() -> list[str]:
        nonlocal tops
        tops = {d: _saved_tops(d) for d in days}     # 백필로 상위 목록이 늘었을 수 있다
        for d in days:
            for r in tops[d][0] or []:
                names.setdefault(r["code"], r["name"])
        return [c for c in union() if c not in hist or not all(d in hist[c] for d in days)]

    if fetch and (missing or need_codes()):
        h = asyncio.run(_kiwoom_fill(missing, need_codes, week_end))
        if h:
            for c, v in h.items():
                hist[c] = {d: x for d, x in v.items() if week_start <= d <= week_end}
            (WEEKLY / build_date).mkdir(parents=True, exist_ok=True)
            save_json(cache_p, {"dt": week_end, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "src": "키움 ka10059 etc_corp(억원)", "names": {c: names.get(c, c) for c in hist}, "codes": hist})
        need_codes()
    for d in days:
        if tops[d][0] is None:
            warn.append(f"{d} 종목별 기타법인 상위 없음(백필 안 됨)")

    # (code, d) 값: 그날 저장된 상위 목록 값 우선(일간 영상과 같은 숫자), 없으면 ka10059 이력
    codes = union()
    per = {}
    drift = []
    for c in codes:
        per[c] = {}
        for d in days:
            sv = tops[d][1].get(c)
            hv = (hist.get(c) or {}).get(d)
            if sv is not None:
                per[c][d] = sv
                if hv is not None and abs(sv - hv) > 1.0:
                    drift.append((c, d, sv, round(hv)))
            elif hv is not None:
                per[c][d] = round(hv)
            else:
                per[c][d] = None
                warn.append(f"{names.get(c, c)} {d} 기타법인 값 없음(주간 합에서 0 처리)")
    diag["others_per"] = per
    diag["others_drift"] = drift

    week = [{"code": c, "name": names.get(c, c), "v": sum(v or 0 for v in per[c].values())} for c in codes]
    week = sorted([r for r in week if r["v"] > 0], key=lambda r: -r["v"])
    daily = [{"d": d, "top": [{"code": r["code"], "name": r["name"], "v": int(r["v"])} for r in (tops[d][0] or [])]} for d in days]
    num_ = 0
    for p in active:
        for d in days:
            if _in_window(d, p):
                num_ += per.get(p["code"], {}).get(d) or 0
    diag["buyback_num"] = num_
    share = round(num_ / others_week, 3) if others_week else None
    return {"week": week, "days": daily, "buyback_share": share}


# ───────────────────────── 전적·미국·뉴스 ─────────────────────────

def _checks(days: list[str]) -> list[dict]:
    j = load_json(DATA / "ledger.json") or {}
    out = []
    for e in j.get("entries") or []:
        r = e.get("result") or {}
        if r.get("date") in days and r.get("ok") is not None:
            out.append({"d": r["date"], "q": e.get("q"), "ok": bool(r["ok"])})
    return sorted(out, key=lambda x: x["d"])


def _us(week_start: str, week_end: str, build_date: str, diag: dict) -> dict:
    """나스닥·SOX 주간 등락 = (week_start 이전 마지막 미국 세션 종가) → (week_end 이하 마지막 세션 종가). 세션은 미국 날짜."""
    files = sorted(p for p in DATA.glob("2*/raw/us_index.json") if p.parent.parent.name <= build_date)
    sess = {"IXIC": {}, "SOX": {}}
    holes = set()
    for p in files:
        j = load_json(p) or {}
        for sym in sess:
            r = (j.get("index") or {}).get(sym) or {}
            s = r.get("session")
            if not s:
                continue
            if r.get("missing") or r.get("close") is None:
                if week_start <= s <= week_end:
                    holes.add(s)
                continue
            sess[sym][s] = {"close": r["close"], "prev_close": r.get("prev_close"), "pct": r.get("pct"),
                            "provisional": bool(r.get("provisional"))}
    notes, out = [], {}
    for sym, key in (("IXIC", "nasdaq_week_pct"), ("SOX", "sox_week_pct")):
        m = sess[sym]
        base = max((s for s in m if s < week_start), default=None)
        end = max((s for s in m if s <= week_end), default=None)
        if not base or not end or end <= base:
            out[key] = None
            continue
        out[key] = round((m[end]["close"] / m[base]["close"] - 1) * 100, 2)
        chain = 1.0
        for s in sorted(x for x in m if base < x <= end):
            chain *= 1 + (m[s]["pct"] or 0) / 100
        diag[f"us_{sym}"] = {"base": base, "base_close": m[base]["close"], "end": end, "end_close": m[end]["close"],
                             "chain_pct": round((chain - 1) * 100, 2), "provisional": m[end]["provisional"]}
    ix = diag.get("us_IXIC")
    if ix:
        notes.append(f"주간 등락 = 미국 {_lbl(ix['base'])} 종가 → {_lbl(ix['end'])} 종가(야후 ^IXIC·^SOX)")
        if ix["end"] < week_end:
            notes.append(f"미국 {_lbl(week_end)} 장은 {build_date} 빌드 시점 파일에 없어 빠짐")
        if ix["provisional"]:
            notes.append("마지막 세션 값이 잠정치")
    for h in sorted(holes):
        if not any(h in sess[s] for s in sess):
            dt = datetime.strptime(h, "%Y%m%d")
            tag = "노동절 휴장" if dt.month == 9 and dt.weekday() == 0 and dt.day <= 7 else "휴장 또는 지연"
            notes.append(f"미국 {_lbl(h)} 세션 봉 없음({tag})")
    return {"nasdaq_week_pct": out.get("nasdaq_week_pct"), "sox_week_pct": out.get("sox_week_pct"), "notes": notes}


def _news(build_date: str) -> list:
    j = load_json(WEEKLY / build_date / "news.json")
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        return j.get("items") or j.get("news") or j.get("events") or []
    return []




# ───────────────────────── 요일별 돈의 자리(v2, JJ 2026-09-17) ─────────────────────────
# JJ: "월화수목금토일 표로 — 월~금 돈이 나간 업종(외국인·개인·기관 전부)과 들어온 업종·종목을 요일마다, 금요일에 돈이 어디 정체해 있는지,
#      요일마다 오른 종목은 뉴스·이슈와 엮어 이벤트로 오른 건지 진짜 돈이 들어온 건지."
# 업종·종목 외국인·기관 = 업종 아카이브(flow_store, 15:40 확정), 개인 = 키움 ka10059 종목별 이력(종목당 1콜, 100거래일) 합.

def _archive_day(d: str) -> dict:
    try:
        from app.services import flow_store
        return flow_store.load_day(d) or {}
    except Exception:
        return {}


async def _fetch_hist(codes: list[str], week_end: str) -> dict:
    import httpx

    from _common import kiwoom_call, num
    from app.services.kiwoom_client import KiwoomClient
    out = {}
    c = KiwoomClient()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as hc:
        tok = await c._ensure_token(hc)
        for code in codes:
            try:
                dd, _, _ = await kiwoom_call(hc, tok, "stkinfo", "ka10059",
                                             {"dt": week_end, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"})
            except Exception as e:  # noqa: BLE001
                print(f"  [hist] {code} 실패: {e}", flush=True)
                continue
            out[code] = {r["dt"]: {"indiv": round(num(r.get("ind_invsr")) / 100), "foreign": round(num(r.get("frgnr_invsr")) / 100),
                                   "inst": round(num(r.get("orgn")) / 100), "others": round(num(r.get("etc_corp")) / 100)}
                         for r in dd.get("stk_invsr_orgn") or [] if r.get("dt")}
            await asyncio.sleep(0.2)
    return out


def _stock_hist(days: list[str], build_date: str, fetch: bool, warn: list[str]) -> dict:
    """{code: {d: {indiv, foreign, inst, others}}} — 그 주 아카이브 종목 전부. data/weekly/<build>/stock_hist.json 캐시(dt=주말)."""
    codes = sorted({r["code"] for d in days for r in (_archive_day(d).get("stocks") or []) if r.get("code")})
    cache_p = WEEKLY / build_date / "stock_hist.json"
    cache = load_json(cache_p) or {}
    hist = cache.get("codes") or {} if cache.get("dt") == days[-1] else {}
    need = [c for c in codes if c not in hist or not all(d in hist[c] for d in days)]
    if need and fetch:
        print(f"  [hist] 종목 {len(need)}개 ka10059 (약 {len(need) * 0.4:.0f}초)", flush=True)
        got = asyncio.run(_fetch_hist(need, days[-1]))
        for c, v in got.items():
            hist[c] = {d: x for d, x in v.items() if days[0] <= d <= days[-1]}
        (WEEKLY / build_date).mkdir(parents=True, exist_ok=True)
        save_json(cache_p, {"dt": days[-1], "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "src": "키움 ka10059(억원)", "codes": hist})
    miss = [c for c in codes if c not in hist]
    if miss:
        warn.append(f"종목별 개인 이력 없음 {len(miss)}개(업종 개인 합계에서 빠짐)")
    return hist


def _verdict(fo: float, io: float, dv: float | None, val: float | None, pct: float) -> dict:
    """오른 종목: 진짜 돈이 들어왔나(평일편 s5 와 같은 기준)."""
    fi = fo + io
    if pct > 0:
        if fi >= 50 and (not val or fi >= 0.05 * val):
            return {"side": "money", "fi": round(fi)}
        if max(fo, io) > 0 and min(fo, io) < 0:
            return {"side": "half", "fi": round(fi)}
        if (dv or 0) > 0:
            return {"side": "indiv", "fi": round(fi)}
        return {"side": "small", "fi": round(fi)}
    return {"side": "down", "fi": round(fi)}


def _days_detail(days: list[str], cks: dict, inv: dict, hist: dict, warn: list[str]) -> list[dict]:
    out = []
    invd = {r["d"]: r for r in inv["days"]}
    for d in days:
        a = _archive_day(d)
        if not a:
            warn.append(f"{d} 업종 아카이브 없음")
        stocks = a.get("stocks") or []
        by_th: dict[str, dict] = {}
        for r in stocks:
            th = r.get("theme")
            if not th:
                continue
            t = by_th.setdefault(th, {"theme": th, "foreign": 0.0, "inst": 0.0, "indiv": 0.0, "indiv_n": 0, "n": 0, "stocks": []})
            fo, io = float(r.get("foreign") or 0), float(r.get("inst") or 0)
            t["foreign"] += fo
            t["inst"] += io
            t["n"] += 1
            hv = (hist.get(r.get("code")) or {}).get(d)
            if hv is not None and (abs(hv["foreign"] - fo) > max(500, 0.3 * abs(fo)) or abs(hv["inst"] - io) > max(500, 0.3 * abs(io))):
                # 장 마감 뒤 대량매매 등으로 이력의 외국인·기관이 15:40 아카이브와 크게 다르면 그 종목 개인은 합에서 뺀다(9/17 넷마블 외국인 −2.8억 vs −3,744억)
                warn.append(f"{d} {r.get('name')} 이력 외국인·기관이 아카이브와 다름({hv['foreign']:+,}/{hv['inst']:+,} vs {fo:+,.0f}/{io:+,.0f}) — 개인 합에서 뺌")
                hv = None
                t["indiv_skip"] = t.get("indiv_skip", 0) + 1
            if hv is not None:
                t["indiv"] += hv["indiv"]
                t["indiv_n"] += 1
            t["stocks"].append({"code": r.get("code"), "name": r.get("name"), "foreign": round(fo), "inst": round(io), "ret": r.get("ret"),
                                "value": r.get("value"), "indiv": hv["indiv"] if hv else None})
        rows = []
        for t in by_th.values():
            net = t["foreign"] + t["inst"]
            rows.append({"theme": t["theme"], "net": round(net), "foreign": round(t["foreign"]), "inst": round(t["inst"]),
                         "indiv": round(t["indiv"]) if t["n"] and t["indiv_n"] + t.get("indiv_skip", 0) == t["n"] and t["indiv_n"] else None,
                         "ret": round(sum((s["ret"] or 0) for s in t["stocks"]) / max(len(t["stocks"]), 1), 2),
                         "stocks": sorted(t["stocks"], key=lambda s: -((s["foreign"] or 0) + (s["inst"] or 0)))})
        outs = sorted([r for r in rows if r["net"] < 0], key=lambda r: r["net"])[:2]
        ins = sorted([r for r in rows if r["net"] > 0], key=lambda r: -r["net"])[:2]
        inst_ins = []
        if not ins:
            inst_ins = [{"theme": r["theme"], "inst": r["inst"], "foreign": r["foreign"]} for r in sorted(rows, key=lambda r: -r["inst"]) if r["inst"] > 0 and r["theme"] not in {o["theme"] for o in outs}][:2]
        for r in ins:
            r["top_stocks"] = [{"name": s["name"], "fi": s["foreign"] + s["inst"], "ret": s["ret"]} for s in r["stocks"] if s["foreign"] + s["inst"] > 0][:2]
        for r in outs + ins:
            r.pop("stocks", None)
        risers = []
        for s in sorted([s for s in stocks if (s.get("ret") or 0) >= 5], key=lambda s: -(s.get("ret") or 0))[:3]:
            hv = (hist.get(s.get("code")) or {}).get(d)
            fo, io = float(s.get("foreign") or 0), float(s.get("inst") or 0)
            risers.append({"code": s.get("code"), "name": s.get("name"), "theme": s.get("theme"), "ret": s.get("ret"), "foreign": round(fo), "inst": round(io),
                           "indiv": hv["indiv"] if hv else None, "value": s.get("value"),
                           "verdict": _verdict(fo, io, hv["indiv"] if hv else None, s.get("value"), s.get("ret") or 0)})
        k = cks[d].get("kospi") or {}
        q = cks[d].get("kosdaq") or {}
        out.append({"d": d, "wd": WD[datetime.strptime(d, "%Y%m%d").weekday()], "kospi_pct": k.get("chg_pct"), "kosdaq_pct": q.get("chg_pct"),
                    "inv": {x: invd.get(d, {}).get(x) for x in KEYS}, "outs": outs, "ins": ins, "inst_ins": inst_ins, "risers": risers})
    return out


def _parked(dd: list[dict]) -> dict:
    """금요일(그 주 마지막 날) 장이 끝났을 때 돈이 머문 곳: 마지막 날 유입 1위 + 그 업종이 그 주에 돈이 들어온 날 수."""
    if not dd or not dd[-1]["ins"]:
        return {}
    top = dd[-1]["ins"][0]
    th = top["theme"]
    days_in = sum(1 for x in dd if any(r["theme"] == th for r in x["ins"]))
    streak = 0
    for x in reversed(dd):
        if any(r["theme"] == th for r in x["ins"]):
            streak += 1
        else:
            break
    return {"theme": th, "net": top["net"], "foreign": top["foreign"], "inst": top["inst"], "indiv": top.get("indiv"),
            "top_stocks": top.get("top_stocks") or [], "days_in": days_in, "streak": streak, "last_wd": dd[-1]["wd"]}


def _history(theme: str, before: str) -> dict:
    """과거 기록(전망 아님, JJ 2026-09-17): 이 업종에 돈이 가장 많이 들어간 채 끝난 금요일(적으면 모든 거래일) 다음 거래일에 돈이 어디로 갔나."""
    try:
        from app.services import flow_store
        dates = [x for x in flow_store.saved_dates() if x < before]
    except Exception:
        return {}
    if len(dates) < 30 or not theme:
        return {}

    def topin(d: str):
        secs = (flow_store.load_day(d) or {}).get("sectors") or []
        nets = {s["theme"]: float(s.get("foreign") or 0) + float(s.get("inst") or 0) for s in secs if s.get("theme")}
        pos = {k: v for k, v in nets.items() if v > 0}
        return (max(pos, key=pos.get) if pos else None), nets

    tops = {d: topin(d) for d in dates}

    def stats(pred) -> dict:
        n, cont, nxt = 0, 0, {}
        for i, d in enumerate(dates[:-1]):
            if not pred(d) or tops[d][0] != theme:
                continue
            nd = dates[i + 1]
            t2, nets2 = tops[nd]
            n += 1
            cont += 1 if (nets2.get(theme) or 0) > 0 else 0
            if t2:
                nxt[t2] = nxt.get(t2, 0) + 1
        return {"n": n, "cont": cont, "next_top": sorted(nxt.items(), key=lambda kv: -kv[1])[:3]}

    fri = stats(lambda d: datetime.strptime(d, "%Y%m%d").weekday() == 4)
    basis = "금요일"
    if fri["n"] < 5:
        fri = stats(lambda d: True)
        basis = "거래일"
    since = dates[0]
    return {"theme": theme, "basis": basis, "since": since, "since_label": f"{since[:4]}년 {int(since[4:6])}월", **fri}


# ───────────────────────── 빌드 ─────────────────────────

def build(week_end: str, build_date: str, fetch: bool = True, _diag: dict | None = None) -> dict:
    days = week_days(week_end)
    if not days:
        raise SystemExit(f"{week_end} 주에 computed_kr.json 있는 날이 없음")
    warn: list[str] = []
    diag = _diag if _diag is not None else {}
    cks = {d: _ck(d) for d in days}
    kospi = _kospi(days, cks, warn)
    inv = _inv(days, cks, days[-1], warn)
    themes = _themes(days, warn)
    programs = (load_json(DATA / "buybacks.json") or {}).get("programs") or []
    others = _others_stocks(days, days[0], days[-1], build_date, programs, inv["week"]["others"], fetch, warn, diag)
    out = {
        "week_start": days[0], "week_end": days[-1], "build_date": build_date, "days": days,
        "kospi": kospi, "inv": inv, "themes": themes, "others_stocks": others,
        "buybacks": [dict(p) for p in programs],
        "checks": _checks(days),
        "us": _us(days[0], days[-1], build_date, diag),
        "news": _news(build_date),
    }
    # v2: 요일별 돈의 자리 · 금요일 머문 곳 · 과거 기록
    try:
        hist = _stock_hist(days, build_date, fetch, warn)
        out["days_detail"] = _days_detail(days, cks, inv, hist, warn)
        out["parked"] = _parked(out["days_detail"])
        out["history"] = _history((out["parked"] or {}).get("theme"), days[0])
    except Exception as e:  # noqa: BLE001
        warn.append(f"요일별 상세 실패: {e}")
    diag["warn"] = warn
    p = WEEKLY / build_date / "computed_weekly.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    save_json(p, out)
    diag["path"] = str(p)
    return out


# ───────────────────────── 검산·요약 ─────────────────────────

def sanity(w: dict, diag: dict) -> list[str]:
    """주간 = 일간 합 검산 + 원천 파일 대조. 문제 줄은 'FAIL'로 시작."""
    days = w["days"]
    res = []

    def ok(cond: bool, msg: str):
        res.append(("ok   " if cond else "FAIL ") + msg)

    # 코스피
    k = w["kospi"]
    pc = k["prev_close"]
    for r in k["days"]:
        c = (_ck(r["d"]).get("kospi") or {})
        ok(abs((c.get("prev_close") or 0) - pc) < 0.005, f"kospi {r['d']} prev_close {c.get('prev_close')} = 전날 종가 {pc}")
        pc = r["close"]
    chain = 1.0
    for r in k["days"]:
        chain *= 1 + r["chg_pct"] / 100
    ok(abs((chain - 1) * 100 - k["week_chg_pct"]) < 0.05, f"kospi 주간 {k['week_chg_pct']}% ≈ 일간 등락 연쇄 {round((chain - 1) * 100, 2)}%")
    # 투자자: 주간 = 일간 합, 일간 = computed_kr = kiwoom_sum
    inv = w["inv"]
    for x in KEYS:
        ok(inv["week"][x] == sum(r[x] for r in inv["days"]), f"inv.week.{x} {inv['week'][x]:+,} = 일간 합")
    for r in inv["days"]:
        c = (_ck(r["d"]).get("investors") or {}).get("kospi") or {}
        s = ((_raw(r["d"], "kiwoom_sum.json") or {}).get("kospi") or {})
        ok(all(r[x] == c.get(x) for x in KEYS), f"inv {r['d']} = computed_kr")
        if s:
            ok(all(r[x] == s.get(x) for x in KEYS), f"inv {r['d']} = kiwoom_sum.json")
    # 거래소 확정치(최신 krx_investors) 대비 — 참고
    kd = {r["date"]: r for r in _krx_days(days[-1], days)}
    if all(d in kd for d in days):
        kw = {x: sum(kd[d][x] for d in days) for x in ("indiv", "foreign", "inst")}
        res.append("info krx 확정(최신 krx_investors) 주간: " + ", ".join(f"{x} {kw[x]:+,} (차 {inv['week'][x] - kw[x]:+,})" for x in kw))
        for d in days:
            dif = {x: inv["days"][days.index(d)][x] - kd[d][x] for x in ("indiv", "foreign", "inst")}
            if any(abs(v) >= 500 for v in dif.values()):
                res.append(f"info {d} computed_kr − krx 확정: {dif}")
    # 백필 파일 합계 vs computed(같은 날 다른 시각)
    for d in days:
        b = ((_raw(d, "kiwoom_top_others.json") or {}).get("kospi") or {})
        if b:
            dif = {x: b.get(x, 0) - inv["days"][days.index(d)][x] for x in KEYS}
            res.append(f"info {d} kiwoom_top_others − computed_kr: {dif}")
    # 테마: 주간 = 일간 합, 일간 테마 합 = flows total_t
    th = w["themes"]
    for r in th["week"]:
        if r["net"] != sum(p["net"] for p in r["days"]):
            ok(False, f"theme {r['theme']} 주간≠일간 합")
    tot_w = sum(r["net"] for r in th["week"])
    tot_d = sum((_raw(d, "flows.json") or {}).get("total_t") or 0 for d in days)
    ok(tot_w == tot_d, f"테마 주간 합 {tot_w:+,} = flows total_t 합 {tot_d:+,}")
    for d in days:
        f = _raw(d, "flows.json") or {}
        s = sum(v["net"] for v in (f.get("table_t") or {}).values())
        ok(s == f.get("total_t"), f"flows {d} 테마 합 {s:+,} = total_t {f.get('total_t'):+,}")
        worst = max((abs(v["net"] - v["foreign"] - v["inst"]) for v in (f.get("table_t") or {}).values()), default=0)
        ok(worst <= 1, f"flows {d} 테마 net = foreign+inst (반올림 오차 최대 {worst})")
    # 기타법인 종목: 주간 = 일간 해소값 합, 자사주 몫
    per = diag.get("others_per") or {}
    for r in w["others_stocks"]["week"]:
        ok(r["v"] == sum(v or 0 for v in per.get(r["code"], {}).values()), f"others {r['name']} 주간 {r['v']:+,} = 일간 합")
    dr = diag.get("others_drift") or []
    res.append(f"info 저장 상위값 vs ka10059 이력 차이(>1억): {dr if dr else '없음'}")
    ow = inv["week"]["others"]
    res.append(f"info 자사주 종목 기타법인 주간 {diag.get('buyback_num', 0):+,} / 기타법인 주간 {ow:+,} = {w['others_stocks']['buyback_share']}")
    # 미국: 주간 = 일간 연쇄
    for sym in ("IXIC", "SOX"):
        u = diag.get(f"us_{sym}")
        if u:
            key = "nasdaq_week_pct" if sym == "IXIC" else "sox_week_pct"
            ok(abs(u["chain_pct"] - w["us"][key]) < 0.05, f"us {sym} {w['us'][key]}% ≈ 일간 연쇄 {u['chain_pct']}% ({u['base']}→{u['end']})")
    # 문구 금지어
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "checks"))
        from forbidden import find
        for e in w["kospi"]["events"]:
            h = find(e["text"])
            ok(not h, f"event 문구 금지어 {h if h else '없음'}: {e['text']}")
    except Exception as ex:  # noqa: BLE001
        res.append(f"info forbidden 검사 생략: {ex}")
    for x in diag.get("warn") or []:
        res.append("WARN " + x)
    return res


def summary(w: dict) -> str:
    k, inv, th, o = w["kospi"], w["inv"], w["themes"], w["others_stocks"]
    L = [f"주간 {w['week_start']}~{w['week_end']} (빌드 {w['build_date']}) days={w['days']}",
         f"코스피 {k['prev_close']:,.2f} → {k['days'][-1]['close']:,.2f}  주간 {k['week_chg_pct']:+.2f}%  고 {k['week_high']:,.2f} 저 {k['week_low']:,.2f}",
         "  일별: " + "  ".join(f"{r['d'][4:]} {r['close']:,.2f}({r['chg_pct']:+.2f})" for r in k["days"]),
         "  이벤트: " + " | ".join(f"{e['d'][4:]} {e['kind']} {e['line']}" for e in k["events"]),
         "수급(억): " + "  ".join(f"{x} {inv['week'][x]:+,}" for x in KEYS) + f"  | 주말 연속 외국인 {inv['streak_end']['foreign']:+d} 기관 {inv['streak_end']['inst']:+d}",
         "  일별: " + "  ".join(f"{r['d'][4:]} 개{r['indiv']:+,}/외{r['foreign']:+,}/기{r['inst']:+,}/법{r['others']:+,}" for r in inv["days"]),
         f"테마 유입 1위 {th['top_in']['theme']} {th['top_in']['net']:+,} ({th['top_in']['pos_days']}일+) · 유출 1위 {th['top_out']['theme']} {th['top_out']['net']:+,} · 머문 곳 {th['stayed']}",
         "  주간: " + ", ".join(f"{r['theme']} {r['net']:+,}" for r in th["week"]),
         "  " + th["top_in"]["theme"] + " 일별: " + " ".join(f"{p['d'][4:]} {p['net']:+,}" for p in th["top_in"]["days"]),
         "기타법인 종목 주간: " + ", ".join(f"{r['name']} {r['v']:+,}" for r in o["week"]) + f"  | 자사주 몫 {o['buyback_share']}",
         "  일별 상위: " + " / ".join(f"{x['d'][4:]} " + ",".join(f"{t['name']} {t['v']:,}" for t in x["top"][:2]) for x in o["days"]),
         "전적: " + " | ".join(f"{c['d'][4:]} {c['q']} → {'이어짐' if c['ok'] else '끊김'}" for c in w["checks"]),
         f"미국: 나스닥 {w['us']['nasdaq_week_pct']}%  SOX {w['us']['sox_week_pct']}%  notes={w['us']['notes']}",
         f"news {len(w['news'])}건"]
    return "\n".join(L)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    we = a[0] if a else datetime.now().strftime("%Y%m%d")
    bd = a[1] if len(a) > 1 else (datetime.strptime(we, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    dg: dict = {}
    wk = build(we, bd, fetch="--no-fetch" not in sys.argv, _diag=dg)
    print(summary(wk))
    print("── 검산")
    for line in sanity(wk, dg):
        print(line)
    print("저장:", dg.get("path"))
