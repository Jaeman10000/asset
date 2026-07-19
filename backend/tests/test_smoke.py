"""출시 전 스모크 테스트 (네트워크 불필요·결정적).

블로커 수정(부분실패 방어·데이터 경로·부호 있는 수급)과 핵심 계산(총합·0나눗셈)을
회귀로 고정한다. 실행: backend/ 에서  `python -m pytest`
"""
import os
import tempfile

# 데이터 디렉터리를 임시로 격리 — 실제 holdings.json/DB를 건드리지 않게 (import 전 설정).
# data_dir()은 호출 시점에 env를 읽으므로 import 순서와 무관하지만 명시적으로 먼저 둔다.
os.environ["VITALITY_DATA_DIR"] = tempfile.mkdtemp(prefix="vitality_test_")

from app.adapters.manual import ManualAdapter  # noqa: E402
from app.paths import data_dir  # noqa: E402
from app.routes.portfolio import _bucket, _compute_totals  # noqa: E402
from app.schemas import Position  # noqa: E402
from app.services import mock_market  # noqa: E402
from app.services.holdings import load_manual_holdings, save_manual_holdings  # noqa: E402

adapter = ManualAdapter()


def _pos(**kw) -> Position:
    base = dict(
        id="t", exchange="manual", assetType="crypto", symbol="X", name="X",
        qty=1, avg=1, price=1, currency="KRW", value=1, cost=1, ret=0, lastUpdated=0,
    )
    base.update(kw)
    return Position(**base)


# ── 준블로커: 손상된 holdings 행은 건너뛰고 정상만 통과 (전체 500 방지) ──
def test_to_position_skips_bad_rows():
    bad = [
        {"assetType": "etf", "symbol": "X", "qty": 1, "avg": 1},               # 잘못된 assetType
        {"assetType": "stock", "region": "JP", "symbol": "Y", "qty": 1, "avg": 1},
        {"assetType": "stock", "region": "kr", "symbol": "Z", "qty": 1, "avg": 1},  # 소문자
        {"assetType": "stock", "currency": "EUR", "symbol": "W", "qty": 1, "avg": 1},
        {"assetType": "crypto", "qty": 1, "avg": 1},                            # symbol 누락
        {"assetType": "crypto", "symbol": "BTC", "qty": "abc", "avg": 1},       # qty 파싱 실패
    ]
    for r in bad:
        assert adapter._to_position(r, {}, {}, {}, 1350.0, 0) is None
    good = {"assetType": "stock", "region": "KR", "symbol": "005930", "qty": 10, "avg": 50000}
    pos = adapter._to_position(good, {}, {}, {}, 1350.0, 0)
    assert pos is not None and pos.symbol == "005930"


# ── division-by-zero 방어 (빈 포트폴리오·cost=0) ──
def test_totals_empty_and_zero_cost():
    t = _compute_totals([])
    assert t.total.value == 0 and t.total.pnlPct == 0.0
    b = _bucket([_pos(cost=0, value=0)], lambda p: True)
    assert b.pnlPct == 0.0  # cost=0 → 0으로 나누지 않음


# ── mock 시장데이터: 같은 날 결정적 + 부호 있는 억원(순매도 표현 가능) ──
def test_mock_sectors_signed_deterministic():
    a = mock_market.kr_sector_flows()
    b = mock_market.kr_sector_flows()
    assert len(a) == 12
    assert [s.name for s in a] == [s.name for s in b]
    assert [round(s.foreign or 0, 2) for s in a] == [round(s.foreign or 0, 2) for s in b]
    assert any((s.foreign or 0) < 0 for s in a)  # 음수(순매도) 존재 = 부호 있음


def test_mock_ranking_has_investors_and_periods():
    rank = mock_market.market_ranking()
    assert len(rank) == 14
    for m in rank:
        assert m.investors is not None
        assert [p.label for p in m.investorPeriods] == ["20일", "60일"]


# ── 데이터 경로 해석(env override) + 원자적 저장(tmp 잔여 없음) ──
def test_data_dir_env_override_and_atomic_save():
    d = data_dir()
    assert str(d) == os.environ["VITALITY_DATA_DIR"]
    save_manual_holdings([{"assetType": "crypto", "symbol": "BTC", "qty": 0.1, "avg": 9}])
    assert not (d / "holdings.json.tmp").exists()
    loaded = load_manual_holdings()
    assert len(loaded) == 1 and loaded[0]["symbol"] == "BTC"
