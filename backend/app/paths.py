"""데이터 디렉터리 경로 해석 — 배포판에서 사용자 데이터 소실 방지.

⚠️ 왜 필요한가: PyInstaller onefile 배포판에서 `__file__`은 실행 시 임시로 풀리는
추출 폴더(`sys._MEIPASS`, 예: %TEMP%\\_MEIxxxx)를 가리키고, 그 폴더는 앱 종료 시
삭제된다. 따라서 사용자 데이터(holdings.json, SQLite, clientlog)를 `__file__` 기준
경로에 쓰면 **재시작마다 소실**된다(리뷰 보드 블로커 #1).

해석 우선순위:
  1. 환경변수 VITALITY_DATA_DIR — Tauri가 사이드카 기동 시 app_data_dir을 주입
  2. 개발 모드(소스 직접 실행, 미동결): 리포의 backend/data/ (기존 동작 유지)
  3. 폴백: OS 사용자 데이터 디렉터리(Windows %APPDATA%\\vitality-nexus 등)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "vitality-nexus"


def _user_data_fallback() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def data_dir() -> Path:
    """쓰기 가능한 데이터 디렉터리를 반환하고 없으면 만든다."""
    env = os.environ.get("VITALITY_DATA_DIR")
    if env:
        p = Path(env)
    elif not getattr(sys, "frozen", False):
        # 소스에서 직접 실행(개발) — 기존 backend/data 유지
        p = Path(__file__).resolve().parent.parent / "data"
    else:
        p = _user_data_fallback()
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_path(name: str) -> Path:
    """데이터 디렉터리 아래의 파일 경로."""
    return data_dir() / name
