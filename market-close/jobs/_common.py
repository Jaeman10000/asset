"""공통: 경로, 백엔드 임포트, 숫자 파싱, 키움 호출 래퍼."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent          # market-close/
REPO = ROOT.parent                                      # asset/
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

DATA = ROOT / "data"
OUT = ROOT / "out"
LOGS = ROOT / "logs"

KIWOOM_BASE = "https://api.kiwoom.com"
KIWOOM_PATHS = {
    "chart": "/api/dostk/chart",
    "sect": "/api/dostk/sect",
    "mrkcond": "/api/dostk/mrkcond",
    "stkinfo": "/api/dostk/stkinfo",
    "rkinfo": "/api/dostk/rkinfo",
    "frgnistt": "/api/dostk/frgnistt",
    "us_chart": "/api/us/chart",
}


def day_dir(d: str) -> Path:
    p = DATA / d / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(d: str, ed: str = "kr") -> Path:
    p = OUT / d / ed
    (p / "voice").mkdir(parents=True, exist_ok=True)
    return p


def computed_path(d: str, ed: str = "kr") -> Path:
    return DATA / d / f"computed_{ed}.json"


def log(d: str, stage: str, msg: str) -> None:
    LOGS.mkdir(exist_ok=True)
    line = f"{datetime.now().strftime('%H:%M:%S')} [{stage}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:  # cp949 콘솔
        print(line.encode("utf-8", "replace").decode("cp949", "replace"), flush=True)
    with open(LOGS / f"{d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def num(v: Any, default: float = 0.0) -> float:
    """키움 문자열 숫자 → float. '+123', '-45', '--45'(이중 마이너스), '1,234' 처리."""
    if v is None:
        return default
    s = str(v).replace(",", "").strip()
    if not s:
        return default
    neg = s.startswith("-")
    s = s.lstrip("+-")
    try:
        x = float(s)
    except ValueError:
        return default
    return -x if neg else x


def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


async def kiwoom_call(hc, token: str, cat: str, api_id: str, body: dict, cont: str = "N", nk: str = ""):
    """카테고리+TR 호출. (json, cont-yn, next-key) 반환. 429(초당 제한)는 1.2s·2.4s·4.8s 대기 후 재시도.
    실측: 연속조회를 쉼 없이 부르면 해외 차트에서 429가 난다. 모든 호출 뒤 0.25s 쉰다."""
    import asyncio
    for attempt in range(4):
        r = await hc.post(
            f"{KIWOOM_BASE}{KIWOOM_PATHS[cat]}",
            headers={"authorization": f"Bearer {token}", "api-id": api_id, "cont-yn": cont, "next-key": nk},
            json=body,
        )
        if r.status_code == 429 and attempt < 3:
            await asyncio.sleep(1.2 * (2 ** attempt))
            continue
        r.raise_for_status()
        await asyncio.sleep(0.25)
        return r.json(), r.headers.get("cont-yn", "N"), r.headers.get("next-key", "")
    raise RuntimeError("unreachable")


def prev_trading_day(d: str) -> str:
    """아카이브 저장 날짜 기준 직전 거래일(없으면 달력 하루 전)."""
    try:
        from app.services import flow_store  # noqa
        dates = [x.replace("-", "") for x in flow_store.saved_dates()]
        prior = [x for x in dates if x < d]
        if prior:
            return max(prior)
    except Exception:
        pass
    from datetime import timedelta
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


# 제목 끝 날짜(JJ 2026-09-19 "내일부터"): 날짜는 제목 맨 뒤에 붙인다 — 쇼츠 피드는 앞 40자만 보이니 훅이 먼저, 날짜는 검색용.
# 앞에 붙은 날짜("9월 18일 …")는 떼어 뒤로 옮기고, 이미 뒤에 날짜가 있으면 그대로 둔다.
_DATE_RE = r"(\d{1,2}월\s*\d{1,2}일|\d{1,2}/\d{1,2})"


def date_tail(title: str, tail: str) -> str:
    import re
    t = (title or "").strip()
    t = re.sub(r"^\s*" + _DATE_RE + r"\s*", "", t).strip()
    t = re.sub(r"\s*#\d{2,4}(?=\s|$)", "", t).strip()          # 회차 번호(#010)는 넣지 않는다(SCRIPT_GUIDE §8)
    if re.search(r"\|\s*[^|]*" + _DATE_RE + r"[^|]*$", t):
        return t[:100]
    return f"{t} | {tail}"[:100]
