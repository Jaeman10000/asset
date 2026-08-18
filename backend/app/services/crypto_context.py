"""크립토 시장 지표 — 호버 카드에 '왜 오르내리는지' 맥락을 준다.

전부 무료·무키 공개 API (실측 확인):
  - CoinGecko /global        : BTC·ETH 도미넌스 (전체 시총 중 비중)
  - alternative.me /fng      : 공포·탐욕 지수 (0=극공포, 100=극탐욕)
  - CoinGecko /simple/price  : 코인별 글로벌 시세(USD·KRW) → 김치 프리미엄 계산용
      김프(%) = 국내(업비트/빗썸) KRW가 ÷ 글로벌 KRW 환산가 − 1

레이트리밋(코인게코 무료 ~10-30콜/분) 대비 캐시: 도미넌스 5분·공포탐욕 30분·시세 2분.
실패 시 이전 값 유지(stale-on-error) — 지표는 없는 것보다 낡은 게 낫다.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

# 업비트·빗썸 상장 심볼 → 코인게코 id (주요 코인만 — 없는 심볼은 김프 생략)
_GECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple", "SOL": "solana",
    "DOGE": "dogecoin", "ADA": "cardano", "TRX": "tron", "AVAX": "avalanche-2",
    "LINK": "chainlink", "DOT": "polkadot", "POL": "polygon-ecosystem-token",
    "BCH": "bitcoin-cash", "LTC": "litecoin", "ETC": "ethereum-classic",
    "XLM": "stellar", "ATOM": "cosmos", "NEAR": "near", "APT": "aptos",
    "ARB": "arbitrum", "OP": "optimism", "SUI": "sui", "SEI": "sei-network",
    "STX": "blockstack", "HBAR": "hedera-hashgraph", "SHIB": "shiba-inu",
    "PEPE": "pepe", "USDT": "tether", "USDC": "usd-coin", "ONDO": "ondo-finance",
    "WLD": "worldcoin-wld", "IMX": "immutable-x", "SAND": "the-sandbox",
    "MANA": "decentraland", "AXS": "axie-infinity", "EOS": "eos", "NEO": "neo",
    "QTUM": "qtum", "VET": "vechain", "ALGO": "algorand", "FLOW": "flow",
    "GRT": "the-graph", "AAVE": "aave", "UNI": "uniswap", "ENA": "ethena",
    "TIA": "celestia", "JUP": "jupiter-exchange-solana", "KAIA": "kaia",
    "CRO": "crypto-com-chain", "RENDER": "render-token", "INJ": "injective-protocol",
}

_g_cache: dict[str, Any] = {"at": 0.0, "data": None}  # 도미넌스 (5분)
_f_cache: dict[str, Any] = {"at": 0.0, "data": None}  # 공포탐욕 (30분)
_p_cache: dict[str, Any] = {"at": 0.0, "data": {}}  # 코인 시세 (2분)


async def get_context(symbols: list[str]) -> dict[str, Any]:
    now = time.time()
    async with httpx.AsyncClient(timeout=8) as h:
        # 도미넌스
        if not _g_cache["data"] or now - _g_cache["at"] > 300:
            try:
                g = (await h.get("https://api.coingecko.com/api/v3/global")).json()
                pct = g["data"]["market_cap_percentage"]
                _g_cache.update(
                    at=now,
                    data={"btcDominance": round(float(pct.get("btc", 0)), 1),
                          "ethDominance": round(float(pct.get("eth", 0)), 1)},
                )
            except Exception:
                pass  # stale-on-error
        # 공포·탐욕
        if not _f_cache["data"] or now - _f_cache["at"] > 1800:
            try:
                f = (await h.get("https://api.alternative.me/fng/?limit=1")).json()
                v = f["data"][0]
                _f_cache.update(
                    at=now,
                    data={"value": int(v["value"]),
                          "label": str(v["value_classification"])},
                )
            except Exception:
                pass
        # 코인별 글로벌 시세 (요청된 심볼 중 매핑 있는 것만)
        ids = {s.upper(): _GECKO_IDS[s.upper()] for s in symbols if s.upper() in _GECKO_IDS}
        missing = [i for i in ids.values() if i not in _p_cache["data"]]
        if ids and (missing or now - _p_cache["at"] > 120):
            try:
                p = (
                    await h.get(
                        "https://api.coingecko.com/api/v3/simple/price",
                        params={"ids": ",".join(sorted(set(ids.values()))),
                                "vs_currencies": "usd,krw"},
                    )
                ).json()
                if isinstance(p, dict) and p:
                    _p_cache["data"].update(p)
                    _p_cache["at"] = now
            except Exception:
                pass

    coins: dict[str, Any] = {}
    for sym, gid in ids.items():
        q = _p_cache["data"].get(gid)
        if isinstance(q, dict) and q.get("krw"):
            coins[sym] = {"usd": q.get("usd"), "krw": q.get("krw")}
    return {
        "global": _g_cache["data"],
        "fearGreed": _f_cache["data"],
        "coins": coins,
    }
