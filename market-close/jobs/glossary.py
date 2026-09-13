"""초보자용 용어 한 줄 풀이 — 경제사냥꾼 벤치마크에서 가져온 습관("이건 ~를 보여주는 숫자인데").
영상마다 딱 하나, 대본에 처음 등장하는 용어를 고르되 최근 7일 안에 설명한 용어는 건너뛴다(data/glossary_log.json).
문장은 40자 안팎(약 5초). 추천·전망 표현 없음.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from _common import DATA, load_json, save_json

LOG = DATA / "glossary_log.json"

TERMS: list[tuple[str, str]] = [
    ("기타법인", "기타법인은 자사주를 사는 회사처럼 개인·외국인·기관에 안 들어가는 법인 돈입니다."),
    ("프로그램 매매", "프로그램 매매는 컴퓨터가 지수를 따라 여러 종목을 한꺼번에 사고파는 거래입니다."),
    ("동시만기", "동시만기는 선물과 옵션 계약이 같은 날 끝나 장 막판에 큰돈이 움직이는 날입니다."),
    ("비농업 고용", "비농업 고용은 농업을 뺀 미국 일자리가 한 달에 얼마나 늘었는지 보여주는 숫자입니다."),
    ("실업률", "실업률이 오르면 경기 걱정이, 내리면 금리를 못 내린다는 걱정이 커집니다."),
    ("CPI", "CPI는 소비자물가로, 이 숫자가 높으면 금리를 내리기 어려워집니다."),
    ("PPI", "PPI는 생산자물가로, 몇 달 뒤 소비자물가에 미리 반영되는 숫자입니다."),
    ("FOMC", "FOMC는 미국 금리를 정하는 회의로, 함께 나오는 점도표가 앞으로의 금리 방향을 보여줍니다."),
    ("거래대금", "거래대금이 평소의 몇 배인지는 그 자리에 실제로 돈이 얼마나 몰렸는지를 보여줍니다."),
    ("EWY", "EWY는 미국에 상장된 한국 주식 ETF로, 밤사이 외국인이 한국을 어떻게 봤는지 미리 보여줍니다."),
    ("순매수", "순매수는 산 금액에서 판 금액을 뺀 것으로, 플러스면 그 주체가 돈을 넣었다는 뜻입니다."),
    ("되돌림", "되돌림은 전날 급락한 만큼 다음 날 돈이 다시 들어와 메운 것을 말합니다."),
    ("레버리지", "레버리지 ETF는 지수 움직임의 세 배로 오르내려서 단기 자금이 몰렸는지 보는 지표입니다."),
    ("10년물", "미국 10년물 금리는 전 세계 돈값의 기준이라, 오르면 주식이 부담을 받습니다."),
]


def pick(scenes: list[dict], d: str) -> tuple[str, str, str] | None:
    """(장면 id, 용어, 풀이) — 대본에 등장하는 첫 용어 중 최근 7일 미설명 용어."""
    log = load_json(LOG) or {}
    cutoff = (datetime.strptime(d, "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
    for sc in scenes:
        for term, expl in TERMS:
            last = log.get(term, "00000000")
            if term in sc["tts"] and (last < cutoff or last == d):
                return sc["id"], term, expl
    return None


def apply(scenes: list[dict], d: str) -> dict | None:
    """용어가 나온 문장 바로 뒤에 풀이 한 문장을 끼워 넣고 로그에 기록. {"scene","term","text"} 반환."""
    got = pick(scenes, d)
    if not got:
        return None
    sid, term, expl = got
    for sc in scenes:
        if sc["id"] != sid:
            continue
        import re
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", sc["tts"].strip()) if x.strip()]
        for i, s in enumerate(sents):
            if term in s:
                sents.insert(i + 1, expl if expl.endswith(".") else expl + ".")
                break
        sc["tts"] = " ".join(sents)
        if sc.get("sub"):
            sc["sub"] = sc["tts"]
    mark(term, d)
    return {"scene": sid, "term": term, "text": expl}


def mark(term: str, d: str) -> None:
    log = load_json(LOG) or {}
    log[term] = d
    save_json(LOG, log)
