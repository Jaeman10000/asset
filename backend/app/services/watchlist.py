"""★ 관심종목 저장 — holdings.json과 같은 데이터 디렉터리(watchlist.json).

검색으로 찾은 종목을 고정해두는 목록. 코드+이름만 저장하고 시세는 조회 시점에
키움에서 받는다(파일에 가격을 저장하면 낡은 값이 진짜인 척 보이므로 저장 안 함).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import data_path

_MAX = 20  # 개인용 위젯 — 이 이상은 폴링 부담(레이트리밋)과 UI 페이지네이션이 무의미


def _path() -> Path:
    return data_path("watchlist.json")


def load_watchlist() -> list[dict[str, str]]:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
        items = raw.get("items") or []
        out = []
        for it in items:
            code = str(it.get("code") or "").strip()
            name = str(it.get("name") or "").strip()
            if code and name:
                out.append({"code": code, "name": name})
        return out[:_MAX]
    except Exception:
        return []


def save_watchlist(items: list[dict[str, str]]) -> list[dict[str, str]]:
    clean = []
    seen: set[str] = set()
    for it in items:
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        if not code or not name or code in seen:
            continue
        seen.add(code)
        clean.append({"code": code, "name": name})
    clean = clean[:_MAX]
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": clean}, ensure_ascii=False, indent=1), encoding="utf-8")
    return clean
