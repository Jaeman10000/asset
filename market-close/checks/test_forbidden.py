"""고정 문장 회귀 검사 — narrate 의 어시스트·방향 문장은 forbidden.assist_ok 를 통과해야 한다.

통과 못 하면 compute 가 「다음에 볼 것」 항목을 소리 없이 버린다
(2026-09-09: 'moved' 어시스트의 '잡아도'가 금지어 '잡아'에 걸려 이동 상태 예고가 늘 빠졌던 사고).
실행: market-close 폴더에서  python -m pytest checks -q
"""
from __future__ import annotations

import pytest

from checks import forbidden
from jobs import narrate

ASSIST_KINDS = sorted(narrate.ASSIST) + ["__unknown__"]  # 마지막은 기본 문장(ASSIST_DEFAULT)


@pytest.mark.parametrize("kind", ASSIST_KINDS)
def test_assist_for_passes_assist_ok(kind: str) -> None:
    s = narrate.assist_for(kind)
    assert not forbidden.find(s), f"{kind}: 금지어 {forbidden.find(s)} — {s}"
    assert forbidden.assist_ok(s), f"{kind}: 조건 표지(면/경우/전까지/뒤에/확인) 없음 — {s}"


# compute 가 stance_for 에 넣는 lead 상태 전부(쌓임은 streak 3 이상/미만 두 갈래). 같은 assist_ok 관문을 지난다.
STANCE_LEADS = {
    "stack3": {"state": "쌓임", "streak": 3, "t": 1},
    "stack2": {"state": "쌓임", "streak": 2, "t": 1},
    "rebound": {"state": "되돌림", "streak": 1, "t": 1},
    "moved": {"state": "이동", "streak": 0, "t": 0, "moved_to": "반도체"},
    "exit": {"state": "이탈", "streak": 0, "t": -1},
    "sell_up": {"state": "매도 확대", "streak": 0, "t": -1},
    "sell_on": {"state": "매도 지속", "streak": 0, "t": -1},
    "sell_down": {"state": "매도 축소", "streak": 0, "t": -1},
}


@pytest.mark.parametrize("lead", STANCE_LEADS.values(), ids=list(STANCE_LEADS))
def test_stance_for_passes_assist_ok(lead: dict) -> None:
    s = narrate.stance_for(lead)
    assert s, f"{lead['state']}: 방향 문장이 비어 있음"
    assert forbidden.assist_ok(s), f"{lead['state']}: {forbidden.find(s) or '조건 표지 없음'} — {s}"
