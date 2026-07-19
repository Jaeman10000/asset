"""
수동입력 보유 종목 — 판매 전략의 핵심 폴백.

거래소 API가 없거나(미지원 증권사) 사용자가 API 키를 안 넣고 싶을 때,
data/holdings.json에 직접 보유 종목을 적으면 그걸 포지션으로 읽는다.
수량·평단만 적으면 현재가는 공개 시세로 채운다 → 어떤 증권사 사용자든
쓸 수 있고, 이게 "상업적 API 이용" 문제를 피해가는 경로이기도 하다.

data/holdings.json 형식 (없으면 그냥 빈 리스트로 취급):
{
  "positions": [
    {
      "exchange": "manual", "assetType": "crypto",
      "symbol": "BTC", "name": "비트코인",
      "qty": 0.1, "avg": 90000000, "market": "upbit"
    },
    {
      "exchange": "manual", "assetType": "stock", "region": "KR",
      "symbol": "005930", "name": "삼성전자",
      "qty": 10, "avg": 70000, "currency": "KRW", "sector": "반도체"
    }
  ]
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..paths import data_path


def _holdings_path() -> Path:
    """항상 현재 데이터 디렉터리 기준 (배포판=%APPDATA%, 개발=backend/data).
    함수로 두어 테스트/실행 중 VITALITY_DATA_DIR 변경도 반영되게 한다."""
    return data_path("holdings.json")


def load_manual_holdings() -> list[dict[str, Any]]:
    """holdings.json을 읽어 raw dict 리스트를 반환. 파일이 없거나
    깨졌으면 빈 리스트 (수동입력을 안 쓰는 사용자는 이게 정상 상태)."""
    path = _holdings_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    positions = payload.get("positions")
    return positions if isinstance(positions, list) else []


def save_manual_holdings(positions: list[dict[str, Any]]) -> None:
    """보유종목 리스트를 holdings.json에 쓴다 (UI 편집 저장용).
    로컬 파일이라 서버로 안 나가고, 다음 스냅샷부터 반영된다.
    원자적 쓰기(tmp→os.replace): 저장 도중 사이드카가 죽어도 반쯤 쓰인 파손
    파일이 남지 않아 다음 로드에서 보유종목이 통째로 사라지는 일을 막는다(QA 지적)."""
    path = _holdings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"positions": positions}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, path)  # 원자적 교체
