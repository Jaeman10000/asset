"""
모의 시장 데이터 — 키움/KRX 연동 전까지 UI를 완성하기 위한 자리표시.

프로토타입(full-dashboard-v2.html)이 보여주던 정보를 전부 공급한다:
  - KR 12개 섹터의 투자자별(외국인/기관/개인) 순매수 강도 + 전일 등락률
  - 오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관 탭이 정렬해서 씀)
  - 종목별 수급 (외국인/기관/개인/프로그램, 단위: 억원)

값은 (날짜, 심볼) 시드의 결정적 의사난수 — 하루 동안은 폴링해도 안 흔들리고,
날마다 자연스럽게 바뀐다. 실제 어댑터(키움 REST/KRX)가 연동되면 이 모듈 호출부를
대체하면 된다. UI에는 '모의 데이터'임이 표시된다.
"""
from __future__ import annotations

import hashlib
from datetime import date

from ..schemas import InvestorFlow, InvestorPeriod, MarketStock, SectorFlow


def _rand(seed: str) -> float:
    """[0,1) 결정적 의사난수 (md5 기반)."""
    h = hashlib.md5(seed.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def _signed(seed: str, scale: float) -> float:
    """[-scale, +scale] 결정적 값."""
    return (_rand(seed) * 2 - 1) * scale


def _today() -> str:
    return date.today().isoformat()


# 프로토타입의 한국 섹터 구성 (12개)
KR_SECTORS = [
    "반도체", "이차전지", "자동차", "바이오", "인터넷", "게임",
    "금융", "지주", "화학", "조선", "로봇", "방산",
]


def kr_sector_flows() -> list[SectorFlow]:
    """KR 12개 섹터 — 투자자별 당일 순매수(억원, 부호 있음) + 전일 등락률(모의).

    부호 있는 순매수(억원)라야 매도(음수) 흐름을 표현할 수 있다. 프론트는
    '외국인+기관' 스마트머니 순매수로 정렬하고 같은 값을 화면에 찍는다
    (정렬 기준 == 표시 값). 종목별 investors_for()와 단위(억원)를 맞췄다.
    """
    day = _today()
    flows: list[SectorFlow] = []
    for name in KR_SECTORS:
        s = f"{day}:{name}"
        foreign = round(_signed(s + ":f", 2400))  # 외국인 ±2400억
        inst = round(_signed(s + ":i", 1100))  # 기관 ±1100억
        # 개인은 외국인+기관의 반대쪽으로 흐르는 경향 (수급은 대체로 제로섬)
        individual = round(-(foreign + inst) * 0.85 + _signed(s + ":p", 300))
        flows.append(
            SectorFlow(
                region="KR",
                id=name,
                name=name,
                foreign=float(foreign),
                inst=float(inst),
                individual=float(individual),
                ret=round(_signed(s + ":r", 3.5), 2),
            )
        )
    return flows


def investors_for(symbol: str) -> InvestorFlow:
    """종목별 당일 수급 (억원). 개인은 외국인+기관+프로그램의 반대쪽으로 흐르는 경향."""
    day = _today()
    s = f"{day}:{symbol}"
    foreign = round(_signed(s + ":f", 180))
    inst = round(_signed(s + ":i", 90))
    program = round(_signed(s + ":g", 40))
    individual = round(-(foreign + inst + program) * 0.9)
    return InvestorFlow(foreign=foreign, inst=inst, individual=individual, program=program)


def investor_periods_for(symbol: str) -> list[InvestorPeriod]:
    """기간 누적 순매수 (억원) 모의 — 당일보다 큰 20일/60일 누적. 키움 표준 프리셋.

    실 키움/KRX 연동 시 일자별 순매수 누적으로 대체된다. 여기선 당일과 별도 시드의
    결정적 값(기간이 길수록 스케일 큼)으로 채운다.
    """
    day = _today()
    out: list[InvestorPeriod] = []
    for label, fs, is_, ps in (("20일", 1400, 700, 320), ("60일", 3800, 1900, 760)):
        s = f"{day}:{symbol}:{label}"
        foreign = round(_signed(s + ":f", fs))
        inst = round(_signed(s + ":i", is_))
        program = round(_signed(s + ":g", ps))
        individual = round(-(foreign + inst + program) * 0.9)
        out.append(
            InvestorPeriod(
                label=label, foreign=foreign, inst=inst, individual=individual, program=program
            )
        )
    return out


# 시장 랭킹 풀 (이름, 심볼, 기준가). 가격/등락/거래량은 날마다 모의 변동.
_RANK_POOL: list[tuple[str, str, float]] = [
    ("삼성전자", "005930", 255000),
    ("SK하이닉스", "000660", 1842000),
    ("한미반도체", "042700", 227000),
    ("KODEX 레버리지", "122630", 98400),
    ("두산에너빌리티", "034020", 65200),
    ("한화에어로스페이스", "012450", 1198000),
    ("HD현대중공업", "329180", 484000),
    ("현대차", "005380", 292000),
    ("NAVER", "035420", 206500),
    ("카카오", "035720", 58900),
    ("LG에너지솔루션", "373220", 328000),
    ("셀트리온", "068270", 198700),
    ("POSCO홀딩스", "005490", 289500),
    ("에코프로비엠", "247540", 142300),
]


def market_ranking() -> list[MarketStock]:
    """오늘의 시장 랭킹 풀 — 프론트가 탭(상승/하락/거래량/외국인/기관)별로 정렬."""
    day = _today()
    out: list[MarketStock] = []
    for name, symbol, base in _RANK_POOL:
        s = f"{day}:{symbol}"
        ret = round(_signed(s + ":ret", 14), 2)  # ±14% 범위 (상한가 근처까지)
        price = round(base * (1 + ret / 100), -2 if base >= 10000 else 0)
        volume = int(_rand(s + ":v") * 18_000_000) + 200_000
        out.append(
            MarketStock(
                symbol=symbol,
                name=name,
                price=price,
                ret=ret,
                volume=volume,
                investors=investors_for(symbol),
                investorPeriods=investor_periods_for(symbol),
            )
        )
    return out
