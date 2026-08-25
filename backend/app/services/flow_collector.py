"""자금 흐름 수집기 — 과거 소급 백필 + 장 마감 후 매일 자동 저장.

핵심 발견(실측): ka10059 한 번 호출이 종목당 **100거래일치**를 통째로 준다
(날짜·종가·등락률·거래대금·외국인·기관). 조회 기준일(dt)을 과거로 밀면 그 이전
100일이 또 나온다 → 몇 년치든 소급 재구성 가능. 95종목 × 5페이지 ≈ 475콜로 2년치.

이 성질 덕분에 **앱을 며칠 꺼놔도 데이터에 구멍이 안 생긴다** — 다음 실행 때 최근
100일을 받아 빠진 날짜만 채우면 되기 때문이다(daily 수집도 사실상 백필의 축소판).
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from .kiwoom_client import KiwoomClient
from .market_hours import kr_session, now_kst
from .themes import ALL_CODES, CODE_NAME, CODE_THEME, THEME_CODES
from . import flow_store

# ka10059 금액 단위: 백만원 → 억원
_TO_EOK = 100.0
# 동시 호출 — 실측상 4 초과 시 스로틀링으로 오히려 느려짐
_CONC = 3

_state: dict[str, Any] = {"running": False, "phase": "", "done": 0, "total": 0, "lastError": None}


def status() -> dict[str, Any]:
    return {**_state, "archive": flow_store.archive_stats()}


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return 0.0


async def _fetch_page(client: KiwoomClient, code: str, base_dt: str) -> dict[str, tuple]:
    """한 종목의 base_dt 기준 과거 100거래일. {date: (외억, 기억, 거래대금억, 등락%, 종가)}"""
    try:
        data = await client.call(
            "stkinfo", "ka10059",
            {"dt": base_dt, "stk_cd": code, "amt_qty_tp": "1", "trde_tp": "0", "unit_tp": "1000"},
        )
        rows = data.get("stk_invsr_orgn") or []
    except Exception:
        return {}
    out = {}
    for r in rows:
        d = str(r.get("dt") or "").strip()
        if len(d) != 8:
            continue
        out[d] = (
            _num(r.get("frgnr_invsr")) / _TO_EOK,
            _num(r.get("orgn")) / _TO_EOK,
            _num(r.get("acc_trde_prica")) / _TO_EOK,
            _num(r.get("flu_rt")) / 100.0,   # ka10059 flu_rt는 1/100 단위
            abs(_num(r.get("cur_prc"))),
        )
    return out


def _build_day(date: str, per_code: dict[str, dict[str, tuple]]) -> tuple[list[dict], list[dict]]:
    """하루치 종목행 + 테마 집계를 만든다."""
    stocks = []
    for code, series in per_code.items():
        v = series.get(date)
        if not v:
            continue
        stocks.append({
            "code": code, "name": CODE_NAME.get(code, code), "theme": CODE_THEME.get(code, ""),
            "foreign": round(v[0], 1), "inst": round(v[1], 1), "value": round(v[2], 1),
            "ret": round(v[3], 2), "close": v[4],
        })
    sectors = []
    for theme, codes in THEME_CODES.items():
        f = i = val = 0.0
        best = None
        for code in codes:
            v = per_code.get(code, {}).get(date)
            if not v:
                continue
            f += v[0]; i += v[1]; val += v[2]
            net = v[0] + v[1]
            if best is None or net > best[1]:
                best = (code, net)
        if val <= 0:
            continue
        sectors.append({
            "theme": theme, "foreign": round(f, 1), "inst": round(i, 1), "value": round(val, 1),
            # 집중도(%) — 절대금액만 쓰면 삼성전자 규모에 다른 테마가 전부 묻힌다(실측:
            # 60일 누적 반도체 -56.8조 vs 나머지 ±1.2조). 거래대금 대비로 정규화한다.
            "strength": round((f + i) / val * 100, 2),
            "leader": best[0] if best else None,
        })
    return stocks, sectors


async def collect(pages: int = 1, only_missing: bool = True) -> dict[str, Any]:
    """수집 실행.

    pages=1  → 최근 100거래일 (매일 수집·구멍 메우기용)
    pages=5  → 약 2년치 소급 백필
    only_missing=True면 이미 저장된 날짜는 건너뛴다(재저장 비용 0).
    """
    if _state["running"]:
        return {"skipped": "이미 수집 중", **status()}

    # 장중 헛수고 차단 — 오늘치는 마감 전이라 어차피 저장하지 않는다(아래 저장 루프).
    # 그런데 가드가 없으면 95종목 × 1페이지 ≈ 95콜(실측 80초)을 다 쓰고 saved=0으로
    # 끝나면서, 그동안 대시보드 실시간 조회와 레이트리밋을 나눠 쓰게 된다.
    # 마지막 저장일이 최근 4일(주말 포함 금→월 간격) 안이면 빠진 날은 '오늘'뿐이므로 건너뛴다.
    if only_missing and kr_session():
        saved_all = flow_store.saved_dates()
        today = now_kst().strftime("%Y%m%d")
        if saved_all and today not in set(saved_all):
            last = max(saved_all)
            gap = (datetime.strptime(today, "%Y%m%d") - datetime.strptime(last, "%Y%m%d")).days
            if gap <= 4:
                return {"skipped": "장중 — 오늘치는 마감 후(15:40) 자동 저장됩니다",
                        "saved": 0, **status()}

    client = KiwoomClient()
    if not client.configured:
        return {"error": "키움 API 키 미설정"}

    _state.update(running=True, phase="수집", done=0, total=len(ALL_CODES) * pages, lastError=None)
    started = time.time()
    per_code: dict[str, dict[str, tuple]] = {c: {} for c in ALL_CODES}
    sem = asyncio.Semaphore(_CONC)

    try:
        base_dt = now_kst().strftime("%Y%m%d")
        for page in range(pages):
            async def one(code: str) -> None:
                async with sem:
                    got = await _fetch_page(client, code, base_dt)
                    per_code[code].update(got)
                    _state["done"] += 1

            await asyncio.gather(*(one(c) for c in ALL_CODES), return_exceptions=True)
            # 다음 페이지 기준일 = 이번에 받은 가장 오래된 날짜의 하루 전
            oldest = min((min(v) for v in per_code.values() if v), default=None)
            if not oldest:
                break
            nxt = (datetime.strptime(oldest, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
            if nxt >= base_dt:
                break  # 더 이상 과거로 못 감 — 무한루프 방지
            base_dt = nxt
            _state["phase"] = f"소급 {page + 2}/{pages}페이지"

        # 날짜별로 쪼개 저장
        _state["phase"] = "저장"
        all_dates = sorted({d for v in per_code.values() for d in v})
        have = set(flow_store.saved_dates()) if only_missing else set()
        today = now_kst().strftime("%Y%m%d")
        saved = 0
        flow_store.init_flow_db()
        for date in all_dates:
            if date in have:
                continue
            # 장중인 오늘은 확정 전이므로 저장하지 않는다(마감 후 수집이 원칙)
            if date == today and kr_session():
                continue
            stocks, sectors = _build_day(date, per_code)
            if not sectors:
                continue
            flow_store.save_day(date, stocks, sectors)
            flow_store.upsert_day(date, stocks, sectors)
            saved += 1
        return {
            "saved": saved, "scanned": len(all_dates), "pages": pages,
            "seconds": round(time.time() - started, 1), **status(),
        }
    except Exception as exc:  # noqa: BLE001
        _state["lastError"] = str(exc)[:200]
        return {"error": _state["lastError"], **status()}
    finally:
        _state.update(running=False, phase="")


# ── 장 마감 후 자동 수집 스케줄러 ──────────────────────────────

_task: asyncio.Task | None = None


async def _loop() -> None:
    """평일 장 마감(15:30) 이후 그날치가 없으면 수집. 앱이 꺼져 있던 날도 자동 보충."""
    while True:
        try:
            now = now_kst()
            today = now.strftime("%Y%m%d")
            # 마감 10분 후부터 시도. 주말은 kr_session이 False라 어차피 저장 안 됨.
            after_close = now.weekday() < 5 and now.hour * 60 + now.minute >= 15 * 60 + 40
            if after_close and today not in set(flow_store.saved_dates()):
                await collect(pages=1, only_missing=True)
        except Exception:
            pass
        await asyncio.sleep(600)  # 10분마다 확인


def start_scheduler() -> None:
    global _task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _task is None or _task.done():
        _task = loop.create_task(_loop())
