"""
SQLite — 스냅샷 이력 저장 (스펙: "거래 이력, 스냅샷").
포트폴리오 스냅샷을 가져올 때마다 1행씩 쌓는다. 나중에 자산 추이 그래프에 쓴다.
"""
import sqlite3

from .paths import data_path

# 상시 위젯이라 캐시 미스마다(≈7초) 1행씩 쌓인다 — 상한을 둬 무한 증가를 막는다.
_MAX_SNAPSHOTS = 5000  # ≈ 하루 남짓치. 초과분은 오래된 것부터 삭제.


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(data_path("vitality.db"))


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
        # 상한 초과 시 오래된 행 정리 (무한 증가 방지). rowid 기준이라 저렴하다.
        conn.execute(
            """
            DELETE FROM snapshots
            WHERE id <= (
                SELECT MAX(id) FROM snapshots
            ) - ?
            """,
            (_MAX_SNAPSHOTS,),
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
