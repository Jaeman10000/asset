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
from pathlib import Path
from typing import Any

HOLDINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "holdings.json"


def load_manual_holdings() -> list[dict[str, Any]]:
    """data/holdings.json을 읽어 raw dict 리스트를 반환. 파일이 없거나
    깨졌으면 빈 리스트 (수동입력을 안 쓰는 사용자는 이게 정상 상태)."""
    if not HOLDINGS_PATH.exists():
        return []
    try:
        payload = json.loads(HOLDINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    positions = payload.get("positions")
    return positions if isinstance(positions, list) else []


def save_manual_holdings(positions: list[dict[str, Any]]) -> None:
    """보유종목 리스트를 data/holdings.json에 쓴다 (UI 편집 저장용).
    로컬 파일이라 서버로 안 나가고, 다음 스냅샷부터 반영된다."""
    HOLDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"positions": positions}
    HOLDINGS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
