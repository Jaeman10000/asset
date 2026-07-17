"""
SQLite — 스냅샷 이력 저장 (스펙: "거래 이력, 스냅샷").
포트폴리오 스냅샷을 가져올 때마다 1행씩 쌓는다. 나중에 자산 추이 그래프에 쓴다.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "vitality.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_fetched_at ON snapshots(fetched_at)"
        )
        conn.commit()
    finally:
        conn.close()


def save_snapshot(fetched_at: int, payload_json: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO snapshots (fetched_at, payload) VALUES (?, ?)",
            (fetched_at, payload_json),
        )
        conn.commit()
    finally:
        conn.close()


def recent_snapshots(limit: int = 100) -> list[tuple[int, str]]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT fetched_at, payload FROM snapshots ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()
    finally:
        conn.close()
