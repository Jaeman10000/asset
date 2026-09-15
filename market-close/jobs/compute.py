"""18:05 compute — raw/*.json → computed.json (장면 데이터 + 문장 + 검증 결과). SPEC §2, §5.
KRX 확정치가 없으면 수급 칸은 비우고(state='pending') 지수는 키움 값으로 채운다(9/3 실측: 키움 고저종 == KRX).
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta

from _common import DATA, day_dir, load_json, log, save_json
sys.path.insert(0, str(DATA.parent))
from checks import forbidden  # noqa: E402

SCENE_MIN = {"s0": 1.2, "s1": 12.0, "s2": 7.0, "s3": 8.0, "s4": 7.0, "s5": 6.0}


# ── 포맷 ──

def _snap_1400(k: dict) -> dict:
    """14:00 잠정치 스냅샷. 장중 ka10059는 개인이 0으로 오므로, 개인 = -(외국인+기관+기타법인+기타외국인)로 역산(indiv_derived=True)."""
    snap = {x: k.get(x) for x in ("indiv", "foreign", "inst", "others")}
    parts = [k.get(x) for x in ("foreign", "inst", "others", "etc_foreign")]
    if not snap.get("indiv") and any(parts) and all(v is not None for v in parts[:3]):
        snap["indiv"] = -round(sum(v or 0 for v in parts))
        snap["indiv_derived"] = True
    return snap

def eok(v: float | None, sign: bool = False) -> str:
    """억원 → '1조 5,936억' / '9,550억'. sign=True면 +/− 접두."""
    if v is None:
        return "—"
    a = abs(round(v))
    s = f"{a // 10000}조 {a % 10000:,}억" if a >= 10000 and a % 10000 else (f"{a // 10000}조" if a >= 10000 else f"{a:,}억")
    if sign:
        return ("＋" if v > 0 else "−" if v < 0 else "") + s
    return s


def eok_tts(v: float | None) -> str:
    if v is None:
        return "미확정"
    a = abs(round(v))
    return f"{a / 10000:.1f}조".replace(".0조", "조") if a >= 10000 else f"{a:,}억"


def pct(v: float | None, plus: str = "＋", minus: str = "−") -> str:
    if v is None:
        return "—"
    return f"{plus if v > 0 else minus if v < 0 else ''}{abs(v):.2f}%"


def pct_tts(v: float | None) -> str:
    if v is None:
        return "미확정"
    return f"{'플러스' if v > 0 else '마이너스' if v < 0 else ''} {abs(v):.2f}".strip()


def idx(v: float | None) -> str:
    return "—" if v is None else f"{v:,.2f}"


def idx_tts(v: float | None) -> str:
    return "미확정" if v is None else f"{int(round(v)):,}"


def josa(w: str, a: str = "은", b: str = "는") -> str:
    """받침 유무로 은/는·이/가 선택."""
    ch = (w or "").strip()[-1:] if w else ""
    if ch and "가" <= ch <= "힣":
        return w + (a if (ord(ch) - 0xAC00) % 28 else b)
    return w + a


def hhmm(t: str) -> str:
    return f"{t[:2]}:{t[2:]}"


def hhmm_tts(t: str) -> str:
    h, m = int(t[:2]), int(t[2:])
    return f"{h}시 {m}분" if m else f"{h}시"


# ── 지수 분석 ──
def analyze_minutes(mins: list[dict], prev_close: float, tkey: str = "t") -> dict:
    if not mins or not prev_close:
        return {}
    pts = [{"t": m[tkey], "pct": round((m["c"] / prev_close - 1) * 100, 3)} for m in mins if m["c"]]
    hi = max(mins, key=lambda m: m["h"]); lo = min(mins, key=lambda m: m["l"])
    # 30분 최대 하락
    best = None
    for i in range(len(mins)):
        j = i
        while j + 1 < len(mins) and _mdiff(mins[i][tkey], mins[j + 1][tkey]) <= 30:
            j += 1
        dp = (mins[j]["c"] / mins[i]["c"] - 1) * 100
        if best is None or dp < best[0]:
            best = (dp, mins[i][tkey], mins[j][tkey])
    first_below = next((m[tkey] for m in mins if m["c"] < prev_close), None)
    return {"points": pts, "open_pct": round((mins[0]["o"] / prev_close - 1) * 100, 2),
            "high": hi["h"], "high_t": hi[tkey], "high_pct": round((hi["h"] / prev_close - 1) * 100, 2),
            "low": lo["l"], "low_t": lo[tkey], "low_pct": round((lo["l"] / prev_close - 1) * 100, 2),
            "close": mins[-1]["c"], "close_pct": round((mins[-1]["c"] / prev_close - 1) * 100, 2),
            "drop30": {"pct": round(best[0], 2), "from": best[1], "to": best[2]} if best else None,
            "first_below_t": first_below}


def _mdiff(a: str, b: str) -> int:
    return (int(b[:2]) * 60 + int(b[2:])) - (int(a[:2]) * 60 + int(a[2:]))


def down_streak(recent: list[dict]) -> int:
    """일봉 recent(최신 우선)에서 연속 하락 일수(+면 연속 상승)."""
    closes = [r["close"] for r in recent]
    if len(closes) < 2:
        return 0
    sign = 1 if closes[0] > closes[1] else -1
    k = 0
    for i in range(len(closes) - 1):
        d = closes[i] - closes[i + 1]
        if (d > 0 and sign > 0) or (d < 0 and sign < 0):
            k += 1
        else:
            break
    return k * sign


# ── 일정 ──
def kr_expiry(d: datetime) -> list[dict]:
    """옵션 만기 = 매월 둘째 목요일, 동시만기 = 3·6·9·12월."""
    out = []
    for k in range(0, 2):
        m = (d.month - 1 + k) % 12 + 1; y = d.year + (d.month - 1 + k) // 12
        first = datetime(y, m, 1); thu = first + timedelta(days=(3 - first.weekday()) % 7 + 7)
        if thu.date() > d.date():
            out.append({"d": thu.strftime("%Y-%m-%d"), "t": "선물·옵션 동시만기" if m in (3, 6, 9, 12) else "옵션 만기"})
    return out


def build_schedule(d: str, us: dict) -> list[dict]:
    dt = datetime.strptime(d, "%Y%m%d")
    items = []
    for e in (us.get("bls") or []):
        k = datetime.strptime(e["kst"], "%Y-%m-%d %H:%M")
        if k > dt.replace(hour=15, minute=30):
            name = e["what"]
            ko = {"Employment Situation": "미국 고용보고서", "Consumer Price Index": "미국 CPI", "Producer Price Index": "미국 PPI",
                  "Productivity and Costs": "미국 생산성", "Real Earnings": "미국 실질임금", "Job Openings and Labor Turnover Survey": "미국 JOLTS"}
            name = next((v for kk, v in ko.items() if kk in name), None)
            if name:
                items.append({"d": k.strftime("%Y-%m-%d %H:%M"), "t": name})
    for f in us.get("fomc_2026") or []:
        s = f.split("/")[0]
        if datetime.strptime(s, "%Y-%m-%d") > dt:
            items.append({"d": f.replace("/", "~"), "t": "FOMC"}); break
    items += kr_expiry(dt)
    tier = {"미국 고용보고서": 0, "미국 CPI": 0, "FOMC": 0, "선물·옵션 동시만기": 0, "미국 PPI": 1, "옵션 만기": 1}
    items.sort(key=lambda x: (tier.get(x["t"], 2), x["d"][:10]))
    top = items[:3]
    top.sort(key=lambda x: x["d"][:10])
    return top


def sched_text(s: dict) -> str:
    dd = s["d"]
    if len(dd) >= 16:
        return f"{int(dd[5:7])}/{int(dd[8:10])} {dd[11:16]} {s['t']}"
    if "~" in dd:
        a, b = dd.split("~"); return f"{int(a[5:7])}/{int(a[8:10])}~{int(b[-2:])} {s['t']}"
    return f"{int(dd[5:7])}/{int(dd[8:10])} {s['t']}"


def _upload_times() -> dict:
    import publish
    return publish.config()["upload_times"]


def _script_format() -> str:
    """대본 형식 스위치: 환경변수 KR_FORMAT 이 있으면 그것, 없으면 data/publish_config.json 의 script_format(기본 aplus).
    값: hunter(경제사냥꾼 7슬롯, 2026-09-16~) · aplus(오늘 누가 샀나) · legacy(구 형식)."""
    env = os.environ.get("KR_FORMAT")
    if env:
        return env
    try:
        import publish
        return str(publish.config().get("script_format") or "aplus")
    except Exception:
        return "aplus"


def narration_inputs(d: str, N: dict, inv: dict, *, raw, fl: dict, kospi: dict, kosdaq: dict, inv_q: dict | None, inv_src: str | None,
                     inv_streak: dict, intraday: dict | None, moves: list, event: dict | None, callback: dict | None,
                     stocks: list, schedule: list) -> dict:
    """narrate_aplus.build_aplus / narrate_hunter.build 에 넘기는 입력 c. hunter_try.py 가 지난 날짜로 재구성할 때도 이 함수를 쓴다.
    (ledger 는 d 이전 항목만 센다 — 제작 시점엔 그 뒤 항목이 없으므로 결과가 같다.)"""
    led = load_json(DATA / "ledger.json") or {}
    done = [x for x in led.get("entries", []) if x.get("result") and (x.get("date") or "") < d]
    ledger_stats = {"n": len(done), "k": sum(1 for x in done if (x.get("result") or {}).get("ok")),
                    "kinds": [(x.get("check") or {}).get("kind") for x in done]}
    _ks = load_json(raw / "kiwoom_sum.json") or {}
    top_others = ((_ks.get("kospi") or {}).get("top_others_buy")
                  or (((load_json(raw / "kiwoom_top_others.json") or {}).get("kospi") or {}).get("top_others_buy")) or [])
    buybacks = (load_json(DATA / "buybacks.json") or {}).get("programs") or []
    top_move = fl.get("top") if fl.get("ready") else None
    if not top_move and fl.get("ready") and fl.get("table_t"):
        _tt, _ty = fl["table_t"], fl.get("table_y") or {}
        _th = max(_tt, key=lambda x: abs(_tt[x].get("net") or 0))
        top_move = next((m for m in moves if m["theme"] == _th), None) or {
            "theme": _th, "t": _tt[_th].get("net"), "y": (_ty.get(_th) or {}).get("net"), "state": "", "streak": 0,
            "spread_names": _tt[_th].get("pos_names") or []}
    prev_inv, prev_date = {}, None
    for i in range(1, 8):
        pdd = (datetime.strptime(d, "%Y%m%d") - timedelta(days=i)).strftime("%Y%m%d")
        pc = load_json(DATA / pdd / "computed_kr.json")
        if pc:
            prev_inv = (pc.get("investors") or {}).get("kospi") or {}
            prev_date = pdd
            break
    kw = load_json(raw / "kiwoom.json") or {}
    recent = (((kw.get("kospi") or {}).get("daily") or {}).get("recent")) or []
    # 헌터 포맷이 더 쓰는 것: 종목별 수급(거래대금 상위 20), 전 업종 순매수표(오늘·전날), FOMC 일정, 합산 종목 수
    sf = kw.get("stock_flows") or {}
    stock_flows = {}
    for s in (kw.get("value_top") or [])[:20]:
        f = sf.get(s.get("code"))
        if f:
            stock_flows[s["code"]] = {"name": s.get("name"), "pct": f.get("pct"), "indiv": f.get("indiv"), "foreign": f.get("foreign"),
                                      "inst": f.get("inst"), "value_mn": s.get("value_mn")}
    theme_table = {th: (row or {}).get("net") for th, row in (fl.get("table_t") or {}).items()} if fl.get("ready") else {}
    theme_table_y = {th: (row or {}).get("net") for th, row in (fl.get("table_y") or {}).items()} if fl.get("ready") else {}
    try:
        upload_times = _upload_times()
    except Exception:
        upload_times = {"kr": "저녁 5시"}
    return {"date": d, "brand": N["brand"], "kospi": kospi, "inv": inv, "inv_streak": inv_streak, "intraday": intraday, "moves": moves,
            "event": event, "prev_inv": prev_inv, "prev_date": prev_date, "recent_closes": recent, "callback": callback,
            "ledger_stats": ledger_stats, "top_others": top_others, "buybacks": buybacks, "top_move": top_move,
            "upload_times": upload_times,
            "stocks": stocks, "kosdaq": inv_q or {}, "kosdaq_index": kosdaq, "schedule": schedule, "inv_src": inv_src,
            "stock_flows": stock_flows, "theme_table": theme_table, "theme_table_y": theme_table_y,
            "fomc_dates": (load_json(raw / "us.json") or {}).get("fomc_2026") or [],
            "n_codes": (_ks.get("kospi") or {}).get("n_codes")}


def _build_hunter(d: str, c: dict, N: dict) -> dict | None:
    """헌터 포맷 제작: 만들고 → qa_script.check_hunter 로 검사 → 실패 문장을 avoid 에 넣고 다시(최대 3회) → 그래도 실패면 None(A+ 폴백)."""
    import narrate_hunter
    avoid: set[str] = set()
    for attempt in range(1, 4):
        try:
            out = narrate_hunter.build(c, avoid or None)
        except Exception as e:
            import traceback
            log(d, "compute", f"헌터 포맷 생성 실패({attempt}회차) → A+ 형식: {e}\n{traceback.format_exc()[-600:]}")
            return None
        try:
            import qa_script
            fails = qa_script.check_hunter(out["scenes"], {**N, **out, "date": d})
        except AttributeError:
            fails = []
        except Exception as e:
            log(d, "compute", f"헌터 검사 자체가 실패({e}) → 검사 없이 통과시킴")
            fails = []
        if not fails:
            log(d, "compute", f"헌터 포맷 통과({attempt}회차): 훅 {out.get('hook_id')} · 장치 {out.get('devices')} · 다음 {out.get('next_q')}")
            return out
        log(d, "compute", f"헌터 검사 실패 {attempt}/3 ({len(fails)}건): " + " | ".join(fails))
        new = {m.group(1).strip() for f in fails for m in [re.search(r"::\s*(.+)$", f)] if m and m.group(1).strip()}
        if new <= avoid:
            log(d, "compute", "헌터 검사: 새로 피할 문장이 없다(문장과 무관한 실패) → 폴백")
            break
        avoid |= new
    log(d, "compute", "⚠ 헌터 포맷 3회 실패 → A+ 형식으로 폴백")
    return None


def _inv_streak(d: str, inv: dict) -> dict:
    """이전 거래일 computed_kr.json을 거슬러 외국인·기관 부호 연속일. streak: 오늘 포함 같은 부호 연속(음수=순매도), turned_after: 오늘 부호가 바뀌었으면 직전 반대 부호 연속일+1."""
    dt = datetime.strptime(d, "%Y%m%d")
    # 1순위: 거래소 집계 최근 10거래일(네이버, 오늘 raw) — computed 파일이 빠진 날(예: 9/3)에도 끊기지 않는다
    kd = ((load_json(DATA / d / "raw" / "krx_investors.json") or {}).get("kospi_days") or [])
    hist = [x for x in sorted(kd, key=lambda x: x.get("date", ""), reverse=True) if x.get("date", "") < d]
    back = 1 if len(hist) < 3 else 99
    if back == 1:
        hist = []
    while len(hist) < 10 and back <= 20:
        pd = (dt - timedelta(days=back)).strftime("%Y%m%d")
        c = load_json(DATA / pd / "computed_kr.json")
        if c and (c.get("investors") or {}).get("kospi"):
            hist.append(c["investors"]["kospi"])
        back += 1
    out = {}
    for key in ("foreign", "inst"):
        today = inv.get(key)
        if today is None:
            continue
        sign = 1 if today > 0 else -1
        streak = 1
        for h in hist:
            v = h.get(key)
            if v is None or (v > 0) != (sign > 0):
                break
            streak += 1
        turned = 0
        if streak == 1:
            for h in hist:
                v = h.get(key)
                if v is None or (v > 0) == (sign > 0):
                    break
                turned += 1
        out[key] = {"streak": streak * sign, "turned_after": turned + 1 if turned else 0}
    return out


# ── 본체 ──
def _unusual(d: str, inv: dict | None) -> dict | None:
    """주체별 오늘 |순매수| ÷ 직전 최대 20거래일 평균 |순매수| — 주인공 선정은 아직 절댓값 1위, 이 값은 비교용 기록(2026-09-11~)."""
    if not inv:
        return None
    try:
        hist = {k: [] for k in ("indiv", "foreign", "inst", "others")}
        base = datetime.strptime(d, "%Y%m%d")
        for i in range(1, 45):
            pi = (((load_json(DATA / (base - timedelta(days=i)).strftime("%Y%m%d") / "computed_kr.json") or {}).get("investors") or {}).get("kospi") or {})
            for k in hist:
                if pi.get(k) is not None and len(hist[k]) < 20:
                    hist[k].append(abs(pi[k]))
        return {k: {"x": round(abs(inv[k]) / (sum(v) / len(v)), 2), "n": len(v)} for k, v in hist.items()
                if v and inv.get(k) is not None and sum(v) > 0}
    except Exception:
        return None


def compute(d: str) -> dict:
    raw = day_dir(d)
    kw = load_json(raw / "kiwoom.json") or {}
    krx = load_json(raw / "krx.json") or {}
    fl = load_json(raw / "flows.json") or {}
    us = load_json(raw / "us.json") or {}
    news = load_json(raw / "news.json") or {"events": []}
    news_kr = load_json(raw / "news_kr.json") or {}
    usi = load_json(raw / "us_index.json") or {}
    wd = datetime.strptime(d, "%Y%m%d").weekday()
    next_label = "다음 주" if wd >= 4 else "내일"
    next_morning = "월요일" if wd >= 4 else "내일"
    warnings: list[str] = []
    date_label = f"{int(d[4:6])}/{int(d[6:])} {'월화수목금토일'[datetime.strptime(d, '%Y%m%d').weekday()]}"

    # 지수: KRX 우선, 없으면 키움
    kd = kw.get("kospi", {}).get("daily") or {}
    qd = kw.get("kosdaq", {}).get("daily") or {}
    kx = (krx.get("kospi") or {}).get("index"); qx = (krx.get("kosdaq") or {}).get("index")
    src_idx = "KRX" if kx else "키움"
    if not kx:
        warnings.append("지수 확정치 KRX 없음 → 키움 일봉 사용")
    kospi = {"prev_close": (kd.get("prev") or {}).get("close"), **({"open": kx["open"], "high": kx["high"], "low": kx["low"], "close": kx["close"], "value_krw": kx.get("value_krw")}
                                                                if kx else {k: (kd.get("today") or {}).get(k) for k in ("open", "high", "low", "close")})}
    kosdaq = {"prev_close": (qd.get("prev") or {}).get("close"), **({"open": qx["open"], "high": qx["high"], "low": qx["low"], "close": qx["close"]}
                                                                 if qx else {k: (qd.get("today") or {}).get(k) for k in ("open", "high", "low", "close")})}
    for m, key in ((kospi, "kospi"), (kosdaq, "kosdaq")):
        pc = m.get("prev_close")
        m["chg_pct"] = round((m["close"] / pc - 1) * 100, 2) if m.get("close") and pc else None
        m["range_pct"] = round((m["high"] - m["low"]) / m["close"] * 100, 1) if m.get("close") and m.get("high") and m.get("low") else None
        m["minutes"] = analyze_minutes(kw.get(key, {}).get("minutes") or [], pc)
        m["streak"] = down_streak((kw.get(key, {}).get("daily") or {}).get("recent") or [])
        m["program_mn"] = ((kw.get(key, {}).get("program") or {}).get("all_mn"))
        m["program_eok"] = round(m["program_mn"] / 100) if m.get("program_mn") is not None else None
    # 검증: 키움 1분봉 고저 vs 확정 고저
    km = kospi["minutes"]
    if km and kospi.get("high") and abs(km["high"] - kospi["high"]) > 0.02:
        warnings.append(f"고가 불일치 키움 {km['high']} vs {src_idx} {kospi['high']}")

    # 수급: KRX 확정치(대량매매 포함) 우선, 없으면 키움 전 종목 합산(정규장 체결 기준)
    ksum = load_json(raw / "kiwoom_sum.json") or {}
    inv = (krx.get("kospi") or {}).get("investors"); inv_q = (krx.get("kosdaq") or {}).get("investors")
    inv_src = "KRX 확정치" if inv else None
    if not inv and ksum.get("kospi") and ksum["kospi"].get("n_got", 0) > 0.95 * ksum["kospi"].get("n_codes", 1):
        inv = {k: ksum["kospi"][k] for k in ("indiv", "foreign", "inst", "others", "etc_foreign")}
        inv_q = {k: ksum["kosdaq"][k] for k in ("indiv", "foreign", "inst", "others", "etc_foreign")} if ksum.get("kosdaq") else None
        inv_src = "키움 전 종목 합산 · 정규장 체결 기준(대량매매 제외)"
        warnings.append("수급 = 키움 전 종목 합산(KRX 확정치 아님, 대량매매·자사주 블록 제외)")
    flows_state = "ready" if inv else "pending"
    # 거래소 집계(네이버)와 대조 — 뉴스 숫자와 다르다는 질문이 나오지 않게 매일 확인
    inv_krx = None
    if inv:
        try:
            import collect_krx_naver
            kx = load_json(raw / "krx_investors.json") or collect_krx_naver.main(d) or {}
            inv_krx = kx.get("kospi")
            if inv_krx:
                for kk, nm in (("indiv", "개인"), ("foreign", "외국인"), ("inst", "기관")):
                    a, b = inv.get(kk), inv_krx.get(kk)
                    if a is None or b is None:
                        continue
                    if kk == "foreign":
                        a = a + (inv.get("etc_foreign") or 0)   # 거래소는 기타외국인을 외국인에 포함
                    if (a > 0) != (b > 0) or abs(a - b) > max(500, 0.05 * abs(b)):
                        warnings.append(f"⚠ 수급 대조: {nm} 우리 {a:+,}억 vs 거래소 {b:+,}억 — 차이 {a - b:+,}억")
                if not any(w.startswith("⚠ 수급 대조") for w in warnings):
                    log(d, "compute", f"수급 대조 OK(거래소 집계와 5% 이내): 개인 {inv['indiv']:+,} vs {inv_krx['indiv']:+,}")
        except Exception as e:
            log(d, "compute", f"수급 대조 생략: {e}")
    # 장중(14:00) 잠정치 vs 마감 — 부호 전환·막판 유입/이탈
    k14 = load_json(raw / "kiwoom_sum_1400.json") or {}
    intraday = None
    if inv and k14.get("kospi") and k14["kospi"].get("n_got", 0) > 0.9 * k14["kospi"].get("n_codes", 1):
        snap = _snap_1400(k14["kospi"])
        turns = []
        for key, name in (("foreign", "외국인"), ("inst", "기관"), ("indiv", "개인")):
            a, b = snap.get(key), inv.get(key)
            if a is None or b is None:
                continue
            diff = b - a
            if a * b < 0 and abs(diff) >= 1000:
                kind = "flip"
            elif a * b > 0 and abs(b) >= abs(a) * 1.3 and abs(diff) >= 1000:
                kind = "more"
            elif a * b > 0 and abs(b) <= abs(a) * 0.7 and abs(diff) >= 1000:
                kind = "less"
            else:
                continue
            turns.append({"key": key, "name": name, "at": k14.get("collected_at") or "14:00", "a": a, "b": b, "diff": diff, "kind": kind})
        # 우선순위: 부호 전환 > 외국인·기관 > 개인, 같은 급이면 변화 큰 순
        turns.sort(key=lambda t: (-(3 if t["kind"] == "flip" else 1) - (2 if t["key"] in ("foreign", "inst") else 0), -abs(t["diff"])))
        intraday = {"at": k14.get("collected_at") or "14:00", "snap": snap, "turns": turns}
        if turns:
            t = turns[0]
            log(d, "compute", f"장중→마감 {t['name']} {t['kind']} {t['a']:+,} → {t['b']:+,}")
    if inv:
        s = sum(inv.get(k, 0) for k in ("indiv", "foreign", "inst", "others", "etc_foreign"))
        if abs(s) > 2:
            warnings.append(f"5주체 합 {s}억 ≠ 0")
    else:
        warnings.append("수급 없음(KRX·키움 합산 모두) → 수급 장면 비움")

    # 미국
    qqq = (kw.get("us") or {}).get("QQQ") or {}; spy = (kw.get("us") or {}).get("SPY") or {}
    us_pts = analyze_minutes(qqq.get("minutes") or [], qqq.get("prev_close") or 0, "t_kst") if qqq.get("minutes") else {}
    if us_pts and qqq.get("session_close"):
        us_pts["points"].append({"t": "0500", "pct": round((qqq["session_close"] / qqq["prev_close"] - 1) * 100, 3)})
    ixic = (usi.get("index") or {}).get("IXIC") or {}
    if ixic and not ixic.get("missing") and ixic.get("pct") is not None:
        us_link = {"name": "나스닥", "pct": ixic["pct"], "close": ixic.get("close"), "session": ixic.get("session"), "src": "야후 ^IXIC",
                   "when": "지난 금요일" if wd == 0 else "간밤"}
    elif qqq.get("session_pct") is not None:
        us_link = {"name": "나스닥100 QQQ", "pct": qqq["session_pct"], "session": us.get("session_et"), "src": "키움 QQQ", "when": "지난 금요일" if wd == 0 else "간밤"}
    else:
        us_link = None
    tre = us.get("treasury") or {}; eia = us.get("eia") or {}
    MAJOR = {"Employment Situation": "고용보고서", "Consumer Price Index": "CPI", "Producer Price Index": "PPI", "Job Openings": "JOLTS",
             "Productivity": "생산성", "Real Earnings": "실질임금", "Employment Cost": "고용비용"}
    us_events = []
    for e in (us.get("bls") or []):
        if e.get("in_session"):
            ko = next((v for k2, v in MAJOR.items() if k2 in e["what"]), None)
            if ko:
                us_events.append({"src": "BLS", "kst": e["kst"], "what": ko})
    us_events += [{"src": "Fed", "kst": "", "what": e["what"]} for e in (us.get("fed") or [])]
    fx = krx.get("fx")

    # 돈의 이동
    moves = fl.get("moves") or [] if fl.get("ready") else []
    if not moves:
        warnings.append("테마 판정 없음")

    # 종목 (거래대금 상위 중 |등락| 큰 것)
    sf = kw.get("stock_flows") or {}
    stocks = []
    for s in (kw.get("value_top") or [])[:10]:
        f = sf.get(s["code"])
        if f:
            stocks.append({"name": s["name"], "pct": f["pct"], "indiv": f["indiv"], "foreign": f["foreign"], "inst": f["inst"], "value_mn": s["value_mn"]})
    stocks = [x for x in stocks if abs(x["pct"]) <= 30 and max(abs(x["indiv"]), abs(x["foreign"]), abs(x["inst"])) >= 100]
    # 슬롯1: 외국인+기관 순매수 합이 가장 큰 종목(들어온 돈). 슬롯2: 거래대금 상위 중 5% 이상 움직인 종목(급등락). 없으면 한 종목만.
    inflow = sorted([x for x in stocks if (x["foreign"] + x["inst"]) > 0], key=lambda x: -(x["foreign"] + x["inst"]))
    picked = inflow[:1] or sorted(stocks, key=lambda x: -abs(x["pct"]))[:1]
    movers = sorted([x for x in stocks if abs(x["pct"]) >= 5 and x not in picked], key=lambda x: -abs(x["pct"]))
    if movers:
        picked.append({**movers[0], "mover": True})
    stocks = picked

    schedule = build_schedule(d, us)

    # ── 다음에 볼 것 (§5-4) ──
    import narrate
    lead = (max(moves, key=lambda m: m["t"]) if any(m["t"] > 0 for m in moves) else moves[0]) if moves else None
    nxt = "다음 주" if wd >= 4 else "내일"
    watch = []
    if lead and lead["state"].startswith("쌓임"):
        watch.append({"q": f"{lead['theme']} 순매수가 {narrate.days_ko(lead['streak'] + 1)} 이어지는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("buy_continue")})
    elif lead and lead["state"] == "이동" and lead.get("moved_to"):
        watch.append({"q": f"{lead['moved_to']}로 옮겨간 돈이 이틀째 이어지는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("moved")})
    elif lead and lead["state"] == "되돌림":
        watch.append({"q": f"{lead['theme']} 순매수가 이틀째 이어지는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("rebound")})
    elif lead and lead["state"] in ("이탈", "매도 확대", "매도 지속"):
        watch.append({"q": f"{lead['theme']} 순매도가 멈추는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("sell")})
    elif lead:
        watch.append({"q": f"{lead['theme']} 순매수가 이틀째 이어지는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("buy_continue")})
    if inv and inv.get("others") is not None and abs(inv["others"]) >= 5000:
        watch.append({"q": f"기타법인 {'순매수' if inv['others'] > 0 else '순매도'}가 이어지는지", "how": "자사주·블록딜 여부 지표", "assist": narrate.assist_for("others")})
    elif inv and inv.get("foreign") is not None:
        watch.append({"q": f"외국인 {'순매수' if inv['foreign'] > 0 else '순매도'}가 이어지는지", "how": f"{nxt} 집계에서 확인", "assist": narrate.assist_for("foreign")})
    elif abs(kosdaq.get("streak") or 0) >= 3:
        n = kosdaq["streak"]
        watch.append({"q": f"코스닥 {abs(n)}일 연속 {'하락' if n < 0 else '상승'}이 끊기는지", "how": f"{nxt} 종가에서 확인", "assist": narrate.assist_for("streak")})
    else:
        rev = next((m for m in moves if m["state"] == "되돌림"), None)
        if rev:
            watch.append({"q": f"{rev['theme']} 순매수가 이틀째 이어지는지", "how": "5일 평균 부호 전환 여부 지표", "assist": narrate.assist_for("rebound")})
        elif len(moves) > 1:
            watch.append({"q": f"{moves[1]['theme']} {'순매수' if moves[1]['t'] > 0 else '순매도'}가 이어지는지", "how": f"{nxt} 15:40 테마 수급에서 확인", "assist": narrate.assist_for("buy_continue")})
    event = load_json(raw / "event.json") or None
    if event and event.get("date") != d:
        event = None
    stock_names = [x["name"] for x in stocks] + [n for m in moves for n in (m.get("spread_names") or [])] + [x["name"] for x in ((event or {}).get("stocks") or [])]
    seen = set()
    watch = [w for w in watch if forbidden.watch_ok(w["how"]) and forbidden.assist_ok(w["assist"], stock_names) and not (w["q"] in seen or seen.add(w["q"]))][:2]
    # 상태별 방향 문장(테마 수준) → s5 맨 앞 + 화면 어시스트 칸. 전날 예고 검증(장부) + 오늘 예고 기록
    import ledger
    if watch:
        st = narrate.stance_for(lead)
        if st and forbidden.assist_ok(st, stock_names):
            watch[0]["stance"] = st
            watch[0]["assist"] = st
        # A+ 형식이면 484행에서 '영상이 실제로 말한 약속'으로 기록한다. 여기서 구형식을 먼저 적어 두면
        # 그쪽 기록이 남아, 다음 날 회수하는 약속이 영상에서 한 말과 어긋날 수 있다(2026-09-14).
        if _script_format() not in ("aplus", "hunter") or not inv:
            ledger.record(d, watch[0]["q"])
    callback = ledger.verify(d, moves, (load_json(raw / "flows.json") or {}).get("moves") or [], inv, kosdaq)

    # 외국인·기관 연속일/전환 (이전 computed_kr 파일에서)
    inv_streak = _inv_streak(d, inv) if inv else {}

    # 배경 문장(데이터 기반, 완곡) — polish가 뉴스 헤드라인으로 대체
    reason_fallback = ""
    if inv:
        buyers = [n for n, kk in (("외국인", "foreign"), ("기관", "inst")) if (inv.get(kk) or 0) > 0]
        hot = lead["theme"] if lead and lead["t"] > 0 else None
        if buyers and hot:
            reason_fallback = f"{narrate._and(buyers)}이 함께 사며 {narrate.ro(hot)} 돈이 들어온 날이었습니다."
        elif buyers:
            reason_fallback = f"{narrate._and(buyers)}이 산 날이었습니다."
        elif hot:
            reason_fallback = f"{narrate.ro(hot)} 돈이 들어온 날이었습니다."

    # ── 대본 (narrate.py) ──
    from app.keychain import get_api_key as _gk
    N = narrate.build({"date": d, "brand": _gk("brand", "name"), "tagline": _gk("brand", "tagline"), "kospi": kospi, "kosdaq": kosdaq, "inv": inv, "inv_src": inv_src, "inv_streak": inv_streak, "intraday": intraday,
                       "upload_times": _upload_times(),
                       "moves": moves, "us_link": us_link, "tre": tre, "fx": fx, "stocks": stocks, "schedule": schedule, "watch": watch,
                       "next_label": next_label, "next_morning": next_morning, "reason_fallback": reason_fallback, "callback": callback, "event": event})
    # ── 형식 스위치(2026-09-15): hunter(경제사냥꾼 7슬롯) / aplus '오늘 누가 샀나'(2026-09-11~) / legacy. KR_FORMAT 이 publish_config 보다 우선 ──
    fmt = _script_format()
    aplus = None
    if fmt in ("aplus", "hunter") and inv:
        try:
            import narrate_aplus
            c_in = narration_inputs(d, N, inv, raw=raw, fl=fl, kospi=kospi, kosdaq=kosdaq, inv_q=inv_q, inv_src=inv_src,
                                    inv_streak=inv_streak, intraday=intraday, moves=moves, event=event, callback=callback,
                                    stocks=stocks, schedule=schedule)
            if fmt == "hunter":
                aplus = _build_hunter(d, c_in, N)        # 검사 3회 실패·예외면 None → 아래에서 A+ 로
            if aplus is None:
                aplus = narrate_aplus.build_aplus(c_in)  # upload_times 도 넘어간다(설계 보고: 전엔 빠져 '저녁 5시' 기본값만 썼다)
            N = {**N, **aplus}
            watch = [{"q": aplus["next_q"], "how": f"{nxt} 15:40 수급에서 확인", "assist": ""}]
            if aplus.get("format") == "hunter" and (aplus.get("watch") or [{}])[0].get("q") == aplus["next_q"]:
                # 헌터 편 S6 는 관측값이 둘(외국인 N일째 + 기타법인 선/유입 이틀째) — 영상이 말한 그대로 남긴다. 장부·스레드·설명문은 watch[0] 만 쓴다
                watch = [{"q": w["q"], "how": w.get("how") or f"{nxt} 15:40 수급에서 확인", "assist": w.get("assist") or ""} for w in aplus["watch"][:2]]
            if not ledger.record(d, aplus["next_q"]):
                log(d, "compute", f"⚠ 오늘 약속이 장부에 안 들어갔다 — 내일 회수가 빈다: {aplus['next_q']}")
            out_root = DATA.parent / "out"
            ep = 1 + sum(1 for x in out_root.iterdir() if x.is_dir() and x.name.isdigit() and "20260907" <= x.name < d and (x / "kr" / "video.mp4").exists())
            aplus["ep"] = ep
            log(d, "compute", f"형식 A+: 주인공 {aplus['protagonist']['name']} {aplus['protagonist']['amount']:+,}억 · 대비 {aplus['contrast']['kind']} · #{ep:03d}")
        except Exception as e:
            import traceback
            log(d, "compute", f"형식 A+ 실패 → 기존 형식: {e}\n{traceback.format_exc()[-600:]}")
            aplus = None
    scenes, title, s3_title, bars = N["scenes"], N["s2_title"], N["s3_title"], N["bars"]
    import glossary
    gloss = glossary.apply(scenes, d) if not aplus else None
    # 길이 사다리 — 실측 TTS 속도(약 6.6자/초) 기준 125초 ≈ 820자. 넘으면 정보 가치가 낮은 문장부터 뺀다.
    CAP = 820 if not aplus else 10 ** 6
    fx_dropped = False

    def _total() -> int:
        return sum(len(sc["tts"]) for sc in scenes)

    def _drop(sid: str, pred, label: str) -> bool:
        sc = next((x for x in scenes if x["id"] == sid), None)
        if not sc:
            return False
        sents = [x for x in re.split(r"(?<=[.!?])\s+", sc["tts"].strip()) if x]
        keep = [x for x in sents if not pred(x)]
        if len(keep) == len(sents):
            return False
        sc["tts"] = " ".join(keep)
        if sc.get("sub"):
            sc["sub"] = sc["tts"]
        log(d, "compute", f"길이 조정: {label} 제거 → {_total()}자")
        return True

    second = [x["name"] for x in stocks[1:2]]
    _lead_t = max((abs(m.get("t") or 0) for m in moves), default=0)
    minor = [m for m in moves if abs(m.get("t") or 0) < 500 and abs(m.get("t") or 0) < _lead_t]
    ladder = [
        ("s4", lambda x: x.startswith("환율은"), "환율 문장"),
        ("s4", lambda x: any(nm in x for nm in second), "두 번째 종목 문장"),
        ((gloss or {}).get("scene") or "", lambda x: bool(gloss) and (gloss.get("text") or "")[:12] in x, "용어 풀이"),
        ("s3", lambda x: "이유가 이겁니다" in x, "예고 검증 꼬리"),
        ("s2", lambda x: x.startswith("기타법인도") and abs((inv or {}).get("others") or 0) < 10000, "기타법인 문장"),
        ("s4", lambda x: x.startswith("이 묶음에서"), "이슈 묶음 수급 문장"),
        ("s3", lambda x: any(m["theme"] in x for m in minor) and ("들어오며" in x or "빠졌습니다" in x or "돌아섰습니다" in x), "작은 테마 문장"),
    ]
    for sid, pred, label in ladder:
        if _total() <= CAP:
            break
        if sid and _drop(sid, pred, label):
            if label == "환율 문장":
                fx_dropped = True
            if label == "용어 풀이":
                gloss = None
    log(d, "compute", f"대본 {_total()}자 (상한 {CAP})")
    threads_text = narrate.build_threads({"date": d, "kospi": kospi, "kosdaq": kosdaq, "inv": inv, "inv_streak": inv_streak,
                                          "moves": moves, "intraday": intraday, "watch": watch, "callback": callback, "event": event})
    k = kospi; km = k["minutes"] or {}; drop = km.get("drop30")

    # ── Threads 캡션 (§5-1) ──
    drop_phrase = f", {drop['from'][:2]}시대 30분 {drop['pct']:.2f}%" if drop and drop["pct"] <= -1 else ""
    q_streak = f" {abs(kosdaq['streak'])}일 연속{'↓' if kosdaq['streak'] < 0 else '↑'}" if abs(kosdaq.get("streak") or 0) >= 2 else ""
    l1 = f"{date_label[:-2]} 마감. 코스피 {pct(k['chg_pct'], '+', '−')} (진폭 {k['range_pct']}%{drop_phrase}), 코스닥 {pct(kosdaq['chg_pct'], '+', '−')}{q_streak}."
    if inv:
        sellers_n = sum(1 for kk in ("indiv", "foreign", "inst") if (inv.get(kk) or 0) < 0)
        tot3 = sum(inv.get(kk) or 0 for kk in ("indiv", "foreign", "inst"))
        l2 = (f"3주체 전부 순매도({eok(tot3, True)})인데 지수 {'상승' if (k['chg_pct'] or 0) > 0 else '하락'} → 기타법인 {eok(inv.get('others'), True)}." if sellers_n == 3
              else f"개인 {eok(inv.get('indiv'), True)} · 외국인 {eok(inv.get('foreign'), True)} · 기관 {eok(inv.get('inst'), True)} · 기타법인 {eok(inv.get('others'), True)}.")
    else:
        l2 = "수급은 집계 뒤 갱신."
    def move_short(m: dict) -> str:
        t, st = m["theme"], m["state"]
        if st.startswith("쌓임"):
            return f"{t} {m['streak']}일째 순매수" + (f"({'·'.join(n[:2] for n in m['spread_names'][:3])} 확산)" if "확산" in st and m.get("spread_names") else "")
        if st == "되돌림":
            return f"{josa(t)} 전날 급락 되돌림"
        if st in ("매도 축소", "매도 확대"):
            return f"{t} 순매도 {eok(abs(m['y']))}→{eok(abs(m['t']))} {st[-2:]}"
        if st == "이동":
            return f"{t}→{m.get('moved_to', '')} 이동"
        return f"{t} {eok(m['t'], True)}"
    l3 = "테마: " + ", ".join(move_short(m) for m in moves) + "." if moves else "테마: 수집 대기."
    l4 = " · ".join(sched_text(s) for s in schedule) + ".  #재테크" if schedule else "#재테크"
    caption = "\n".join([l1, l2, l3, l4])

    texts = {sc["id"]: sc["tts"] for sc in scenes}
    texts.update({"caption": caption, "s2_title": title, "s3_title": s3_title})
    bad = forbidden.check_all(texts)
    if bad:
        warnings.append(f"금지어: {bad}")

    out = {
        "date": d, "date_label": date_label, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {"index": src_idx, "investors": inv_src, "minutes": "키움 ka20005", "us": "키움 usa06011(QQQ·SPY)",
                    "treasury": tre.get("src"), "wti": eia.get("src"), "fx": (fx or {}).get("src"), "themes": "아카이브(ka10059)"},
        "kospi": kospi, "kosdaq": kosdaq, "investors": {"state": flows_state, "src": inv_src, "kospi": inv, "kosdaq": inv_q, "bars": bars, "title": title},
        "us": {"qqq_pct": qqq.get("session_pct"), "spy_pct": spy.get("session_pct"), "qqq_points": (us_pts or {}).get("points"),
               "qqq_open_pct": (us_pts or {}).get("open_pct"), "session_et": us.get("session_et"), "events": us_events,
               "y10": tre.get("y10"), "y10_chg_bp": tre.get("chg_bp"), "y10_date": tre.get("date"), "wti": eia.get("wti"), "wti_chg": eia.get("chg_pct"), "wti_date": eia.get("date")},
        "fx": fx, "moves": moves, "s3_title": s3_title, "stocks": stocks, "news": news.get("events") or [], "brand": N["brand"], "tagline": N["tagline"],
        "watch": watch, "schedule": schedule, "caption": caption, "scenes": scenes, "warnings": warnings, "forbidden": bad,
        "us_link": us_link, "inv_streak": inv_streak, "next_label": next_label, "hook": N.get("hook"), "fx_said": bool(N.get("fx_said")) and not fx_dropped, "intraday": intraday,
        "upload_times": _upload_times(), "threads_text": threads_text,
        "callback": callback, "bonding": N.get("bonding"), "hook_parts": N.get("hook_parts"), "inv_krx": inv_krx, "s3_story": N.get("s3_story"), "event": event,
        "hook_id": N.get("hook_id"), "weekend_watch": N.get("weekend_watch"), "caution_id": N.get("caution_id"), "devices": N.get("devices"),
        "news_items": (news_kr.get("items") or [])[:20], "glossary": gloss,
        "format": ((aplus or {}).get("format") or "aplus") if aplus else "legacy",
        "hunter": (aplus or {}).get("hunter"),
        "protagonist": (aplus or {}).get("protagonist"), "contrast": (aplus or {}).get("contrast"),
        "check": (aplus or {}).get("check"), "ep": (aplus or {}).get("ep"),
        "s2_marks": (aplus or {}).get("s2_marks"), "event_used": (aplus or {}).get("event_used"), "others_top": (aplus or {}).get("others_top"),
        "visual": os.environ.get("KR_VISUAL", "v4") if aplus else "legacy",
        "unusual": _unusual(d, inv),
    }
    out["edition"] = "kr"
    save_json(DATA / d / "computed_kr.json", out)
    try:                                   # 전 편 기억(data/script_history.json) — 문장·사실 색인. 실패해도 제작은 계속(record_history 가 예외를 삼킨다)
        import script_memory
        script_memory.record_history(d, out)
    except Exception as e:
        log(d, "compute", f"script_history 기록 건너뜀: {e}")
    # ── Threads v4(2026-09-11~): 사람 말투 짧은 줄 본문. 이전 본문은 threads_text_legacy로 남긴다 ──
    try:
        import threads_v4
        body, tf, issues = threads_v4.make(d)
        out["threads_text_legacy"] = out.get("threads_text")
        out["threads_text"], out["threads_facts"], out["threads_issues"] = body, tf, issues
        out["threads_reply"] = threads_v4.reply(d, out)
        save_json(DATA / d / "computed_kr.json", out)
        log(d, "compute", f"threads v4: {len(body)}자 {body.count(chr(10)) + 1}줄 hero={tf['hero']}" + (f" ⚠ 검사 {issues}" if issues else " 검사 통과"))
    except Exception as e:
        import traceback
        log(d, "compute", f"threads v4 실패 → 기존 본문 유지: {e}\n{traceback.format_exc()[-500:]}")
    for w in warnings:
        log(d, "compute", "⚠ " + w)
    log(d, "compute", f"저장 computed.json — 수급 {flows_state}, 장면 {len(scenes)}")
    return out


if __name__ == "__main__":
    compute(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"))
