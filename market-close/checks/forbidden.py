"""금지어·어조 검사 (SPEC §1-4, v2.4). 화면·자막·TTS·캡션 전부 통과해야 한다.

v2.4 원칙(JJ 지시 2026-09-05):
  - 종목 단위 매매 지시·추천은 절대 금지(HARD).
  - 시장·테마 단위의 '방향 어시스트'는 허용하되 조건문+완곡 표현이어야 한다
    ("이어지면 방향을 잡고, 끊기면 판단은 미뤄도 늦지 않습니다").
  - 원인·전망은 뉴스 근거 + 완곡 표현("~로 꼽혔습니다/풀이됩니다/보입니다/수 있습니다")만. 단정("확실히/반드시/틀림없이") 금지.
"""
from __future__ import annotations

import re

# 절대 금지 — 종목·매매 지시, 화자, 확신 표현
FORBIDDEN = ["추천", "목표가", "사라", "팔아라", "담아라", "유망", "노려", "잡아", "진입", "손절", "비중", "저는", "제 생각", "개인적으로",
             "매수하세요", "매도하세요", "매수해야", "매도해야", "사야", "팔아야", "매수 기회", "매도 기회", "매수 타이밍", "매도 타이밍",
             "확실히", "반드시", "틀림없", "분명히", "무조건", "급등할", "급락할", "폭등", "폭락", "대박", "필승", "주목", "관심 종목",
             "확률이 높", "승률", "부자가", "돈을 벌", "돈 벌", "벌 수 있", "경제적 자유", "수익 인증", "계좌 인증", "리딩방", "단톡", "오픈채팅", "텔레그램",
             "익절", "물타기", "불타기", "몰빵", "풀매수", "존버", "올라타", "같이 담", "따라 담", "떠나지 마", "저희", "지금 매수", "지금 매도"]
# 매수/매도 낱말 자체는 아래 허용 복합어 안에서만 통과(수급 용어·판단 유보 표현)
_BARE = ["매수", "매도"]
_ALLOWED_COMPOUNDS = ["순매수", "순매도", "매수 상위", "매도 상위", "매도 축소", "매도 확대", "매도 지속", "동반 매도", "3주체 매도", "셋이 판", "매도가",
                      "매수 판단", "매도 판단", "매수 결정", "매매 판단", "매수세", "매도세", "매수 우위", "매도 우위", "쌍끌이 매수", "저가 매수", "차익 매도",
                      "매수하며", "매도하며", "매수하다가", "매도하다가", "매수했", "매도했", "매수로", "매도로", "매수는", "매도는",
                      "기관 매수", "기관 매도", "외국인 매수", "외국인 매도", "개인 매수", "개인 매도", "기타법인 매수", "기타법인 매도"]
# 완곡 표지 — 원인·전망 문장에 하나는 있어야 한다
HEDGES = ("꼽혔", "꼽히", "풀이", "보입니다", "보이는", "보였", "수 있", "해석", "읽혔", "읽히", "읽힙", "읽힐", "평가", "분석", "듯", "모습", "배경으로", "것으로 보", "셈")
# 전망·원인 표지 — 이 낱말이 있으면 같은 문장에 완곡 표지가 있어야 한다
FORWARD = ("전망", "예상", "가능성", "것이다", "것입니다", "상승할", "하락할", "오를 것", "내릴 것", "호재", "악재", "때문", "영향", "탓에", "탓으로", "탓이", "덕에", "덕분", "로 인해", "으로 인해", "인한", "여파", "나오자", "힘입어")
# 어시스트 문장에 종목명이 들어가면 안 된다 — compute가 종목명 목록을 넘겨 검사
WATCH_VERB_WHITELIST = ("확인", "본다", "지표")


def _strip_allowed(text: str) -> str:
    t = text
    for c in _ALLOWED_COMPOUNDS:
        t = t.replace(c, "□" * len(c))
    return t


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?。])\s+", (text or "").strip()) if s]


def find(text: str) -> list[str]:
    """절대 금지어 + 허용 복합어 밖의 매수/매도 + 완곡 표지 없는 전망·원인 문장."""
    t = _strip_allowed(text or "")
    hits = [w for w in FORBIDDEN if w in t]
    hits += [w for w in _BARE if w in t]
    for s in _sentences(t):
        if any(k in s for k in FORWARD) and not any(h in s for h in HEDGES):
            hits.append("단정:" + s[:24])
    return hits


_PERSONAL = ("저는", "제 생각", "개인적으로")


def find_threads(text: str) -> list[str]:
    """Threads(JJ 개인 계정)용: 사람 목소리라 1인칭('저는', '제 생각')은 허용, 나머지 금지어·단정 검사는 동일."""
    return [h for h in find(text) if h not in _PERSONAL]


def check_all(texts: dict[str, str]) -> dict[str, list[str]]:
    """{라벨: 문장} → {라벨: [걸린 금지어]} (걸린 것만)."""
    bad = {}
    for k, v in texts.items():
        hits = find(v or "")
        if hits:
            bad[k] = hits
    return bad


def watch_ok(sentence: str) -> bool:
    """「다음에 볼 것」 how 문말 화이트리스트."""
    s = re.sub(r"[\s.。]+$", "", sentence or "")
    return any(s.endswith(w) or (w in s[-6:]) for w in WATCH_VERB_WHITELIST)


def assist_ok(sentence: str, stock_names: list[str] | None = None) -> bool:
    """방향 어시스트 문장: 조건문('~면')이 있고, 종목명이 없고, 금지어가 없어야 한다."""
    s = sentence or ""
    if not s or find(s):
        return False
    if not re.search(r"(면|경우|전까지|뒤에|확인)", s):
        return False
    return not any(n and n in s for n in (stock_names or []))
