"""자금 흐름 영구 저장소 — 로컬 파일 + SQLite 이중화.

유저 요구: "앱을 끄면 사라지니까, 실질 데이터를 로컬에 모아두면 가치가 어마어마하다."
그래서 두 층으로 저장한다:

  1) **일자별 JSON 아카이브** (data/flow/YYYY-MM-DD.json)
     사람이 읽을 수 있고, 백업·이동·다른 도구로 분석이 자유롭다. 이게 '유저가 소유하는
     데이터'다. 앱을 지워도 이 폴더만 있으면 전부 복원된다.
  2) **SQLite 인덱스** (vitality.db의 flow_daily / sector_daily)
     히트맵·전이통계처럼 수백 일을 훑는 질의를 빠르게 하기 위한 사본.
     JSON이 원본(source of truth)이고 SQLite는 언제든 재구축 가능하다(rebuild_from_files).

일자별 파일로 나눈 이유: 하나의 큰 파일이면 매일 전체를 다시 쓰다가 중간에 앱이 죽으면
누적분이 통째로 날아간다. 하루치는 쓰다 실패해도 그날 것만 잃는다.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable

from ..paths import data_path


def flow_dir() -> Path:
    d = data_path("flow")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _db() -> sqlite3.Connection:
    return sqlite3.connect(data_path("vitality.db"))


def init_flow_db() -> None:
    conn = _db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flow_daily (
                date TEXT NOT NULL,        -- YYYYMMDD
                code TEXT NOT NULL,
                theme TEXT NOT NULL,
                foreign_eok REAL NOT NULL, -- 외국인 순매수(억원)
                inst_eok REAL NOT NULL,    -- 기관 순매수(억원)
                value_eok REAL NOT NULL,   -- 거래대금(억원)
                ret REAL NOT NULL,         -- 등락률(%)
                close REAL NOT NULL,
                PRIMARY KEY (date, code)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sector_daily (
                date TEXT NOT NULL,
                theme TEXT NOT NULL,
                foreign_eok REAL NOT NULL,
                inst_eok REAL NOT NULL,
                value_eok REAL NOT NULL,
                strength REAL NOT NULL,    -- (외+기)/거래대금 × 100 = 집중도(%)
                leader_code TEXT,
                PRIMARY KEY (date, theme)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_date ON flow_daily(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sector_date ON sector_daily(date)")
        conn.commit()
    finally:
        conn.close()


# ── 파일 아카이브 ─────────────────────────────────────────────

def _file_for(date: str) -> Path:
    """date=YYYYMMDD → data/flow/YYYY-MM-DD.json"""
    return flow_dir() / f"{date[:4]}-{date[4:6]}-{date[6:]}.json"


def save_day(date: str, rows: list[dict[str, Any]], sectors: list[dict[str, Any]]) -> Path:
    """하루치를 JSON으로 원자적 저장(임시파일 → rename). 중간에 죽어도 파일이 안 깨진다."""
    payload = {
        "date": date,
        "schema": 1,
        "stocks": rows,     # [{code,name,theme,foreign,inst,value,ret,close}]
        "sectors": sectors, # [{theme,foreign,inst,value,strength,leader}]
    }
    p = _file_for(date)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, p)  # 원자적 교체
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return p


def load_day(date: str) -> dict[str, Any] | None:
    p = _file_for(date)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None  # 손상 파일은 없는 것으로 취급 → 재수집 대상


def saved_dates() -> list[str]:
    """아카이브에 있는 날짜(YYYYMMDD) 오름차순."""
    out = []
    for p in flow_dir().glob("????-??-??.json"):
        out.append(p.stem.replace("-", ""))
    return sorted(out)


def archive_stats() -> dict[str, Any]:
    dates = saved_dates()
    total_bytes = sum(p.stat().st_size for p in flow_dir().glob("*.json"))
    return {
        "days": len(dates),
        "first": dates[0] if dates else None,
        "last": dates[-1] if dates else None,
        "bytes": total_bytes,
        "dir": str(flow_dir()),
    }


# ── SQLite 반영 ───────────────────────────────────────────────

def upsert_day(date: str, rows: Iterable[dict[str, Any]], sectors: Iterable[dict[str, Any]]) -> None:
    conn = _db()
    try:
        conn.executemany(
            """INSERT OR REPLACE INTO flow_daily
               (date, code, theme, foreign_eok, inst_eok, value_eok, ret, close)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(date, r["code"], r["theme"], r["foreign"], r["inst"], r["value"], r["ret"], r["close"])
             for r in rows],
        )
        conn.executemany(
            """INSERT OR REPLACE INTO sector_daily
               (date, theme, foreign_eok, inst_eok, value_eok, strength, leader_code)
               VALUES (?,?,?,?,?,?,?)""",
            [(date, s["theme"], s["foreign"], s["inst"], s["value"], s["strength"], s.get("leader"))
             for s in sectors],
        )
        conn.commit()
    finally:
        conn.close()


def rebuild_from_files() -> int:
    """JSON 아카이브(원본)로 SQLite를 통째로 재구축. DB가 깨져도 복구 가능."""
    init_flow_db()
    n = 0
    for date in saved_dates():
        day = load_day(date)
        if not day:
            continue
        upsert_day(date, day.get("stocks", []), day.get("sectors", []))
        n += 1
    return n


def sector_series(limit_days: int = 400) -> list[tuple]:
    """(date, theme, foreign, inst, value, strength, leader) 최근 N일 — 히트맵·전이통계용."""
    conn = _db()
    try:
        return conn.execute(
            """SELECT date, theme, foreign_eok, inst_eok, value_eok, strength, leader_code
               FROM sector_daily
               WHERE date IN (SELECT DISTINCT date FROM sector_daily ORDER BY date DESC LIMIT ?)
               ORDER BY date""",
            (limit_days,),
        ).fetchall()
    finally:
        conn.close()


def stock_series(date_from: str) -> list[tuple]:
    """(date, code, theme, foreign, inst, value, ret) — 주도주 계산용."""
    conn = _db()
    try:
        return conn.execute(
            """SELECT date, code, theme, foreign_eok, inst_eok, value_eok, ret
               FROM flow_daily WHERE date >= ? ORDER BY date""",
            (date_from,),
        ).fetchall()
    finally:
        conn.close()
