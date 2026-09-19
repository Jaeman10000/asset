"""대본·영상 자동 점검 — JJ에게 보내기 전에 반드시 통과시킨다.

배경(2026-09-12~13 JJ 지적에서 나온 규칙):
  · 3분을 넘으면 쇼츠 피드에서 빠진다. 평일 2분, 주말 3분.
  · 축약 종결형("팜/오름")·채팅 기호·압축 숫자(9.9조)는 쓰지 않는다.
  · 대본을 고치면 화면이 그대로라 말과 어긋난다 → 렌더 뒤 장면별 프레임을 뽑아 눈으로 대조한다.
  · 마지막 사실 뒤에는 '그래서 무슨 뜻'이 있어야 한다.
  · 최근 편과 문장 뼈대가 겹치면 AI 티가 난다.

헌터 포맷(2026-09-15, docs/SCRIPT_SYSTEM_HUNTER_v1.0.md · docs/HUNTER_FORMAT_DESIGN.md §3·§6.3):
  · 슬롯 9장면(s0 s1 s2 s3a s3b s3c s4 s5 s6)을 체크리스트 11항 + 문장 규칙 10 으로 검사한다 — check_hunter().
  · 하나라도 실패면 compute 가 실패 문장을 avoid 에 넣고 다시 만든다(최대 3회), 그래도 실패면 옛 포맷으로 폴백.
  · 실패 문자열은 "[장면] 규칙 :: 걸린 문장" 꼴 — compute 는 ' :: ' 뒤를 잘라 avoid 에 넣는다.
  · 글자 그대로 겹침(부록 A-1)은 올라간 편 가운데 최근 5편 창(script_memory.OVERLAP_WINDOW)으로 본다. 시그니처와
    장부 문장(script_memory.LEDGER_FORM: '…순매도가 N일째 이어지는지' / '…을 지키는지')은 예외 — 어제 질문을 되읽는 문장이다(B2).
  · 화면 지시어 부족(규칙 6)은 지시어 없는 S4 문장을 ' :: ' 뒤에 붙여 재시도가 그 후보를 바꾸게 한다(B3).

브리핑 포맷(2026-09-15 밤, docs/BRIEF_FORMAT_DESIGN.md §3):
  · 장면 id 는 헌터와 같고 체인 순서가 매일 고정(코스피 수급 → 코스닥+지수 → 빠진 곳 → 들어온 곳 → 종목 둘 → 뉴스 판정 → 내일 포인트).
  · check_brief() = check_hunter() 의 11항·문장 규칙 전부 + 장면마다 '반드시 말해야 하는 내용' 검사 + 시그니처·애프터마켓 고정문 + 총 글자 수.
  · 실패 문자열 꼴은 헌터와 같다("[s3b] 규칙 :: 문장"). 총 900자 미만은 실패가 아니라 경고(warn 목록 또는 stderr).

실행:
  python qa_script.py script --kind us --date 20260913     대본만 점검(렌더 전)
  python qa_script.py frames --kind us --date 20260913     렌더된 영상에서 장면별 프레임 추출
  python qa_script.py all    --kind kr --date 20260912
  python qa_script.py hunter --kind day --date 20260916    헌터 11항만 (--file 로 다른 json 지정 가능; 파일 format 이 brief 면 check_brief)
kind: day(평일) | kr(토 국장 주간) | us(일 미국 주간) | hunter(=day, format 은 파일의 "format" 으로 판단)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FF = Path(r"C:/Users/Jeff/Documents/GitHub/asset/market-close/render/node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe")
CPS = 8.1                                   # 타입캐스트 무열 tempo 1.1 실측 초당 글자수
LIMIT = {"day": 172, "kr": 172, "us": 172}  # 초 상한 = 쇼츠 한계 180초 - 여유 8초.
# 180초를 넘기면 쇼츠가 아니라 일반 영상으로 분류돼 쇼츠 피드에서 빠진다 — 우리 조회수의 96~97%가 거기서 온다.
# 그 아래로는 길이를 재지 않는다(JJ 2026-09-14): "2분 넘어도 3분이 되도 상관없다. 짧아서 끝까지 본다고 좋은 영상이 아니다."
FLOOR = {"day": 75, "kr": 90, "us": 90}     # 초 하한 — 이만큼도 안 되면 할 말이 없었다는 뜻이다
CLOSE_MAX = {"day": 480, "kr": 340, "us": 340}   # 평일 312 = 시청자 질문·좋아요 두 줄이 들어간 20260914 규격   # 마무리 두 장면(s5+s6) 자수 상한. 평일 285 = 20260911 확정본 278 + 여유
# 매 편 똑같이 들어가는 고정문 — 뼈대 중복 검사에서 뺀다(빼지 않으면 매일 '겹침'으로 잡힌다)
FIXED = ("그 답이 궁금하면 구독해 두세요.", "누가샀나였습니다.", "국장 마감은 매일 오후 5시에 올라옵니다.",
         "국장 마감은 매일 저녁 5시에 올라옵니다.", "국장 마감은 내일부터 매일 저녁 5시에 올라옵니다.",
         "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다.", "평일엔 매일 저녁 5시에 국장 마감이 올라옵니다.",
         "누가샀나 주간 결산이었습니다.", "누가샀나 미국 주간 결산이었습니다.",
         "평일엔 매일 오후 5시에 국장 마감이 올라옵니다.")
DIRS = {"day": ("", "kr"), "kr": ("weekly", ""), "us": ("weekly_us", "")}

BAD_END = re.compile(r"(팜|음|함|짐|옴|됨|뜀|빠짐|올림|내림|삼|샀음|팔았음)\s*\.{0,2}$")
CHAT = re.compile(r"[ㅋㅎㅠㅜ]")
TIGHT_NUM = re.compile(r"\d+\.\d+조")
# '그래서 무슨 뜻'으로 인정하는 표현. 해석(앞)이거나 다음 확인점(뒤)이면 통과.
MEANING = re.compile(r"뜻|셈|모습|보입니다|볼 수 있|가까워|남아 있|의미|같은 배|한 주입니다|한 주였|"
                    r"볼 건|볼 것|확인하|확인됩니다|봅니다|보겠습니다|이어지는지|사느냐|사는지|쪽입니다|뒤집히는")


# ══════════════════════════════════════════════════════════════════════════════
# 헌터 포맷 검사 — 정본 §4 문장 규칙 10 · §5 체크리스트 11항 · 설계 §3 을 휴리스틱으로 옮긴 것
# ══════════════════════════════════════════════════════════════════════════════
HUNTER_IDS = ("s0", "s1", "s2", "s3a", "s3b", "s3c", "s4", "s5", "s6")
S3_IDS = ("s3a", "s3b", "s3c")
SCREEN_IDS = ("s2", "s3a", "s3b", "s3c", "s4")       # 화면 지시어를 세는 구간(규칙 6: S2 1 + S3 3 ≥ 4)

_SPLIT = re.compile(r"(?<=[.?!])\s+")
_DAYWORD = r"(?:이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
_HNUM = r"(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|마흔|쉰|백|천)"
_CLS = r"(?:배|개|번째|번|명|곳|종목|업종|건|칸|줄|가지|자리|시간|달|주|장|회|군데|분|초|편|차례)"
_AFTER = r"(?=[\s.,!?]|$|[을를이가은는의도로만에과와씩째]|입니다|였|이었|넘|가까)"
# 숫자 토큰 하나 = 사람이 '숫자 하나'로 듣는 단위. '2조 8천억'·'1조 4,800억'·'3분의 1'·'9월 17일' 은 각각 1개.
# 한글 수사(다섯 배, 닷새째, 한 업종)도 숫자로 센다. 하루·하나·둘 처럼 단위 없이 흔한 말은 세지 않는다('하루째'는 센다).
NUM_TOKEN = re.compile(
    r"\d+분의\s?\d+"                                                                   # 분수
    r"|\d{1,2}월\s?\d{1,2}일"                                                           # 날짜
    r"|\d{1,2}시\s?\d{1,2}분|\d{1,2}:\d{2}"                                             # 시각(15시 30분, 15:30)
    r"|\d[\d,]*(?:\.\d+)?\s?(?:조|억|만|천|백)+(?:\s?\d[\d,]*(?:\.\d+)?\s?(?:조|억|만|천|백)+)*"  # 금액 사슬
    r"|\d[\d,]*(?:\.\d+)?\s?%"                                                           # 비율
    r"|\d[\d,]*(?:\.\d+)?"                                                               # 그 밖의 숫자(12거래일, 3시 …)
    r"|" + _DAYWORD + r"|하루(?=째|치|간|동안|연속|만에)"                                  # 날짜 수사
    r"|절반"
    r"|" + _HNUM + r"\s?" + _CLS + _AFTER)                                               # 수사 + 단위(다섯 배, 한 업종)
# 직접 질문(문장 끝) — '마지막 문장은 질문 금지' 같은 데 쓴다
Q_TAIL = re.compile(r"(?:느냐|냐|는가|은가|인가|일까요|을까요|일까|을까|까요|습니까|입니까|었나|았나|는지|은지|인지)\s*[.!…]*$")
# 문장 안에 박힌 질문('누가 받았느냐가 오늘의 전부입니다', '누가 받았는지 하나만 봅니다')
Q_MID = re.compile(r"(?:느냐|는가|은가|인가|일까|을까|었나|았나|는지|은지|인지)(?=[\s,가는이를도의])")
S0_BANNED = re.compile(r"안녕하세요|안녕하십니까|반갑습니다|누가샀나|국장 ?마감|오늘 시장은|\d{1,2}월\s?\d{1,2}일|\d{4}년|"
                       r"[월화수목금토일]요일입니다|오늘은 \d{1,2}일")
S1_DECL = re.compile(r"하나만 봅니다|전부입니다|하나만 찾습니다|하나만 보겠습니다|따라가 보겠습니다|찾아보겠습니다|과연 누가 샀을까요|답은 수급에 있습니다|하나씩 확인해 보겠습니다")
S2_NAIVE = re.compile(r"생각하기 쉽습니다|보이기 쉽습니다|읽히기 쉽습니다")
S4_OPEN = re.compile(r"직접 열어\s?봤습니다|열어\s?보면|여기 이 칸|직접 확인해\s?봤습니다|종목으로 확인해\s?보면|하나씩 확인해\s?보면")   # 9/17 여는 말 3일째 반복 방지 — 1차 자료 확인 장치는 그대로
S4_CALC = re.compile(r"(?:\d|" + _HNUM + r")\s?배(?!경|당|달|우|추|송|터|급|제|치|후)"       # 29배, 다섯 배
                     r"|\d+분의\s?\d+|며칠치|\d+\s?(?:거래|영업)?일치|\d[\d,.]*\s?%")
S6_THRESH = re.compile(r"(?:\d[\d,.]*|" + _HNUM + r")\s?(?:거래|영업)?(?:천|백)?(?:일째|억|조|%|선)" + r"|" + _DAYWORD + r"째")
SCREEN_DIR = re.compile(r"보세요|여기 이 칸|왼쪽|오른쪽|위 칸|아래 칸|막대|여기 진행률")
# 브리핑(평일편)은 반대로 **화면을 말로 설명하면 실패**한다(JJ 2026-09-16: "오른쪽 도장입니다를 왜 말로 설명해? 이미 화면에 보여주는데").
# 화면은 말에 맞춰 켜진다 — 말은 사람이 시장을 설명하듯 한다. 따옴표 안(뉴스 제목)은 세지 않는다('신용카드'·'디스플레이 화면' 같은 기사 낱말).
SCREEN_TALK = re.compile(r"막대|(?:위|아래|이|그|두|종목|뉴스|판정|왼쪽|오른쪽)\s?칸|왼쪽|오른쪽|카드|도장|종목 칩|보세요|화면|그래프|네 번째")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|‘[^’]*’|“[^”]*”")


def strip_quotes(s: str) -> str:
    return _QUOTED.sub("", s or "")


# S5 판정·뒤집히는 조건 — 브리핑은 "돈 쪽입니다" 같은 딱딱한 틀 대신 사람 말로 한다(JJ 2026-09-16). 옛 틀도 그대로 통과한다.
S5_VERDICT = re.compile(r"돈이 들어온 상승|실제로 들어왔|에 이어 오늘|하루 만에 돌아섰|돈이 먼저 움직인|한쪽 돈만 들어온|끌어올린 상승|큰돈이 만든 상승은 아닙|팔아 값이 밀렸|뉴스로 오른|쪽입니다|움직인 하루|움직였[습고]|만들었[습고]|만든 건|움직인 건|끌었[습고]|때문만이 아니|(?:뉴스|기사)에 올랐|값이 밀렸|값을 받쳤|값을 올렸")
# 브리핑 금지 말투(JJ 2026-09-17) — 사람 입에서 안 나오는 말. 따옴표 안(뉴스 제목)은 세지 않는다.
JARGON = re.compile(r"(?:받은|받는|사는|파는|산|판|한|큰|빠진|돌아선|같은)\s?손(?![실해절])|쪽입니다|묶어 보면|움직인 하루|행방|무게는|정체는 여기|"
                    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)째|(?:두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s배")
S5_FLIP = re.compile(r"뒤집히는 조건|뒤집히려면|바뀌려면|바뀌는 신호|달라지는 조건|바뀌었다고 보려면")
SCREEN_ONLY = re.compile(r"(?:보세요|보시죠)[.!]?$|^여기 (?:이 칸|진행률)입니다[.!]?$")    # 화면만 가리키는 문장(블록 끝 판정에서 뺀다)
BANNED_ALL = re.compile(r"여러분|지난 영상|영상에서|우리 채널|구독하고 알림")
# 종목 추천·매매 판단 표현 — '사라'는 '사라지다/사라졌다' 를 빼고 잡는다
RECO = re.compile(r"사세요|파세요|사라(?![지져졌질짐])|팔아라|비중|관망|전망은|목표가")
_SIG_KEYS = ("누가샀나였습니다", "국장 마감은 매일", "국장 마감은 내일부터", "정규장이 끝나도 저녁 8시까지", "궁금하면 구독", "국장마감, 매일")

# ── 브리핑 포맷 고정 내용(설계 §1 표 · §3 check_brief) ──
BRIEF_TOTAL_MAX = 1300            # 총 글자 수 상한(넘으면 실패)
BRIEF_TOTAL_MIN = 900             # 이 밑이면 경고(실패 아님) — 설계 §0 "길이 950~1,250자"
BRIEF_PARTIES = ("외국인", "기관", "개인")
BRIEF_OTHERS_MIN = 3000           # 기타법인 |순매수| 가 이 밑이면 s2 에서 이름을 빼도 된다(설계 §2 "기타법인 <3,000억")
S3B_OUT = re.compile(r"빠졌|나갔|순매도")
S3C_IN = re.compile(r"들어왔|순매수|들어온 곳이 없었|샀습니다|사들였|샀고|들어간 곳|들어온 곳")
# 시그니처 고정문 — 9/15 편만 '내일부터', 그 뒤로는 '매일 저녁 5시'(CLAUDE.md). 애프터마켓 문장은 9/14~9/18(narrate_aplus.AFTER_MARKET_NOTICE_UNTIL).
SIG_BRAND = "누가샀나였습니다."
SIG_DAILY = "국장 마감은 매일 저녁 5시에 올라옵니다."
SIG_FIRST = "국장 마감은 내일부터 매일 저녁 5시에 올라옵니다."
SIG_FIRST_DATE = "20260915"
AFTER_MARKET = "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다."
AFTER_MARKET_FROM, AFTER_MARKET_UNTIL = "20260914", "20260918"


def _sents(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split((text or "").strip()) if s.strip()]


def _scene_text(scenes: list[dict]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """장면 id → tts 전문 / 문장 목록. 같은 id 가 두 번 오면 첫 것만(check_hunter·check_brief 공용)."""
    by: dict[str, dict] = {}
    for s in scenes or []:
        sid = str(s.get("id") or "")
        if sid and sid not in by:
            by[sid] = s
    txt = {sid: (by[sid].get("tts") or "") for sid in by}
    return txt, {sid: _sents(txt[sid]) for sid in by}


def _hunter_comp(comp: dict | None) -> dict:
    """comp["hunter"](장면별 계약 사전) — 없거나 사전이 아니면 빈 사전."""
    h = (comp or {}).get("hunter")
    return h if isinstance(h, dict) else {}


def _is_sig(s: str) -> bool:
    """시그니처·고정문(매일 같아도 되는 문장)."""
    t = (s or "").strip()
    return t in FIXED or any(k in t for k in _SIG_KEYS)


def num_tokens(s: str) -> list[str]:
    return [m.group(0) for m in NUM_TOKEN.finditer(s or "")]


def is_question(s: str) -> bool:
    """문장 끝이 질문인가(물음표 없이 '…일까요.' 로 끝나도 질문)."""
    t = (s or "").strip()
    return t.endswith("?") or bool(Q_TAIL.search(t))


def has_question(s: str) -> bool:
    """문장 어딘가에 질문이 있는가(끝 질문 + 안에 박힌 '…느냐가/…는지 하나만')."""
    return is_question(s) or bool(Q_MID.search(s or ""))


def _eok_values(s: str) -> list[float]:
    """'2조 8천억' → [28000(억), 2.8(조)], '5,328만' → [5328(만), 0.5328(억)] — 단위 해석을 여러 개 돌려준다."""
    mult = {"조": 10000.0, "억": 1.0, "천억": 1000.0, "백억": 100.0, "만": 1e-4, "천만": 1e-3, "백만": 1e-2, "천": 1e-8, "백": 1e-9}
    total = 0.0
    found = False
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s?((?:조|억|만|천|백)+)", s):
        n = float(m.group(1).replace(",", ""))
        u = m.group(2)
        total += n * mult.get(u, 1.0)
        found = True
    if not found:
        return []
    return [total, total / 10000.0, total * 10000.0]     # 억·조·만 세 가지로 읽은 값


def _stated_candidates(result: str) -> list[float]:
    """calc.result('29배' '33.3%' '3분의 1' '12거래일치' '2조 8천억') 에서 비교할 숫자 후보들."""
    r = (result or "").strip()
    if not r:
        return []
    if m := re.search(r"(\d+)\s?분의\s?(\d+)", r):
        a, b = float(m.group(1)), float(m.group(2))
        return [b / a, b / a * 100.0] if a else []
    if re.search(r"\d\s?(?:조|억|만|천|백)", r):
        return _eok_values(r)
    if m := re.search(r"(\d[\d,]*(?:\.\d+)?)\s?%", r):
        v = float(m.group(1).replace(",", ""))
        return [v, v / 100.0]
    if m := re.search(r"\d[\d,]*(?:\.\d+)?", r):
        return [float(m.group(0).replace(",", ""))]
    return []


def _computed_candidates(lhs: float, rhs: float, kind: str, result: str) -> list[float]:
    k = (kind or "").lower()
    r = result or ""
    if not k:
        k = "share" if ("%" in r or "분의" in r) else "ratio" if "배" in r else "days" if ("치" in r or "일" in r) \
            else "diff" if re.search(r"\d\s?(?:조|억)", r) else "ratio"
    a, b = abs(lhs), abs(rhs)
    if k in ("ratio", "times", "배", "multiple"):
        return [a / b] if b else []
    if k in ("share", "pct", "percent", "%", "비율", "fraction"):
        return [a / b * 100.0, a / b] if b else []
    if k in ("days", "일치", "며칠치", "day"):
        return [a / b] if b else []
    if k in ("diff", "sub", "minus", "차", "차이", "remain", "잔여"):
        return [abs(lhs - rhs), abs(a - b)]
    if k in ("sum", "plus", "합", "add"):
        return [lhs + rhs, a + b]
    return [a / b] if b else []


def _close(c: float, s: float) -> bool:
    """반올림 허용: 29.2→'29'·'30', 5.49→'다섯', 11.8→'12', 27,895억→'2조 8천억'."""
    return abs(c - s) <= max(0.6, 0.03 * abs(c))


def verify_calc(calc: dict, s4_text: str) -> list[str]:
    """S4 계산 검산(체크리스트 ⑦·⑪ '배수/차이 계산을 검산했는가'). 실패 문자열 목록(장면 접두 없이)."""
    out: list[str] = []
    if not isinstance(calc, dict):
        return out
    lhs, rhs = calc.get("lhs"), calc.get("rhs")
    result = str(calc.get("result") or "")
    kind = str(calc.get("kind") or "")
    value = calc.get("value")
    if not isinstance(lhs, (int, float)) or not isinstance(rhs, (int, float)):
        return out
    computed = _computed_candidates(float(lhs), float(rhs), kind, result)
    if not computed:
        out.append(f"계산식 무효 ({calc.get('expr') or f'{lhs}/{rhs}'}) — 0으로 나눔")
        return out
    stated = _stated_candidates(result)
    if stated and not any(_close(c, s) for c in computed for s in stated):
        out.append(f"계산 검산 실패 {calc.get('expr') or f'{lhs}/{rhs}'} = {computed[0]:.2f} ≠ 말한 값 '{result}'")
    if isinstance(value, (int, float)) and not any(_close(c, float(value)) for c in computed):
        out.append(f"calc.value {value} 이 계산값 {computed[0]:.2f} 과 다름")
    # 계산 결과가 대사에 실제로 나오는가(화면·말 대조)
    if result:
        flat = re.sub(r"[,\s]", "", s4_text or "")
        if m := re.search(r"(\d+)\s?분의\s?(\d+)", result):
            if f"{m.group(1)}분의{m.group(2)}" not in flat:
                out.append(f"계산 결과 '{result}' 가 S4 대사에 없음")
        elif m := re.search(r"\d[\d,]*(?:\.\d+)?", result):
            if m.group(0).replace(",", "") not in flat:
                out.append(f"계산 결과 '{result}' 가 S4 대사에 없음")
    return out


def check_hunter(scenes: list[dict], comp: dict, recs: list[dict] | None = None, screen: str = "require") -> list[str]:
    """헌터 포맷 대본 검사. 빈 목록이면 통과.

    실패 문자열: "[장면] 규칙 :: 걸린 문장" — compute 는 ' :: ' 뒤 문장을 avoid 에 넣고 다시 만든다.
    recs 는 전 편 목록(script_memory.editions 형태) — 시험용. None 이면 data/ 의 전 편을 읽는다.
    """
    bad: list[str] = []

    def fail(scene: str, rule: str, sent: str = "") -> None:
        bad.append(f"[{scene}] {rule} :: {sent}")

    txt, sents = _scene_text(scenes)

    # ④ 9장면 다 있어야 한다 — S3 블록은 정확히 3개
    for sid in HUNTER_IDS:
        if not sents.get(sid):
            fail(sid, "장면 없음")
    for sid in txt:
        if re.fullmatch(r"s3[d-z]", sid):
            fail(sid, "S3 블록 4개 이상 — 하나를 내일로 넘길 것", (sents[sid] or [""])[0])

    # ① S0: 첫 두 문장에 숫자 2개 이상, 인사·날짜·채널명·'오늘 시장은' 없음
    if sents.get("s0"):
        head = sents["s0"][:2]
        n = sum(len(num_tokens(x)) for x in head)
        if n < 2:
            fail("s0", f"첫 두 문장 숫자 {n}개 < 2 — 두 숫자가 충돌해야 한다", head[0])
        for x in head:
            if m := S0_BANNED.search(x):
                fail("s0", f"도입부 금지어({m.group(0)})", x)

    # ② S1: 질문 선언 틀 + 질문 정확히 1개
    if sents.get("s1"):
        if not S1_DECL.search(txt["s1"]):
            fail("s1", "질문 선언 틀 없음(하나만 봅니다|전부입니다|하나만 찾습니다|하나만 보겠습니다)", sents["s1"][-1])
        qs = [x for x in sents["s1"] if has_question(x)]
        if len(qs) != 1:
            fail("s1", f"질문 {len(qs)}개 — 정확히 1개여야 한다", qs[1] if len(qs) > 1 else sents["s1"][0])

    # ③ S2: 뻔한 답 대변 + '그런데' 차단
    if sents.get("s2"):
        if screen != "ban" and not S2_NAIVE.search(txt["s2"]):   # 브리핑은 대변 문장을 요구하지 않는다(JJ 2026-09-17: 질문 뒤에 뜬금없이 끼어든다)
            fail("s2", "대변 틀 없음(생각하기 쉽습니다|보이기 쉽습니다|읽히기 쉽습니다)", sents["s2"][0])
        if not re.search(r"그런데|하지만", txt["s2"]):      # 브리핑은 '판 쪽 → 하지만 산 쪽'으로 묶는다(JJ 2026-09-17)
            fail("s2", "그런데 없음", sents["s2"][-1])

    # ⑤ 각 S3 블록은 '그런데' 문장 또는 질문으로 끝난다(그런데 뒤 해석 1문장은 허용, 끝의 화면 지시 문장은 세지 않는다) · '그런데' 블록당 1회
    for sid in S3_IDS:
        ss = sents.get(sid)
        if not ss:
            continue
        core = list(ss)
        while len(core) > 1 and SCREEN_ONLY.search(core[-1]):
            core.pop()
        last = core[-1]
        ok = last.startswith("그런데") or has_question(last) or (len(core) >= 2 and core[-2].startswith("그런데"))
        if not ok:
            fail(sid, "블록 끝이 '그런데' 도 질문도 아님", last)
        if txt[sid].count("그런데") > 1:
            second = [x for x in ss if "그런데" in x]
            fail(sid, f"그런데 {txt[sid].count('그런데')}회 — 블록당 1회", second[1] if len(second) > 1 else second[0])
    # 규칙 5: '그런데' 연속 2문장 금지(어느 장면이든)
    for sid in HUNTER_IDS:
        ss = sents.get(sid) or []
        for i in range(len(ss) - 1):
            if "그런데" in ss[i] and "그런데" in ss[i + 1]:
                fail(sid, "그런데 연속 2문장", ss[i + 1])

    # ⑥⑦ S4: 1차 자료 열람 연출 + 계산 1개(검산)
    if sents.get("s4"):
        if not S4_OPEN.search(txt["s4"]):
            fail("s4", "1차 자료 열람 문장 없음(직접 열어봤습니다|열어보면|여기 이 칸)", sents["s4"][0])
        if not S4_CALC.search(txt["s4"]):
            fail("s4", "계산식 없음(배|분의|며칠치|일치|%)", sents["s4"][-1])
        calc = _hunter_comp(comp).get("s4", {}).get("calc")
        for msg in verify_calc(calc, txt["s4"]):
            hit = next((x for x in sents["s4"] if S4_CALC.search(x)), "")
            fail("s4", msg, hit)

    # ⑧⑨ S5: 판정 문장 + 뒤집히는 조건, 질문으로 끝내지 않는다
    if sents.get("s5"):
        if not S5_VERDICT.search(txt["s5"]):
            fail("s5", "판정 문장 없음('오늘은 ___ 쪽입니다')", sents["s5"][-1])
        if not S5_FLIP.search(txt["s5"]):
            fail("s5", "뒤집히는 조건 없음", sents["s5"][-1])
        if is_question(sents["s5"][-1]):
            fail("s5", "판정 장면이 질문으로 끝남", sents["s5"][-1])

    # ⑩ S6: 내일 관측값에 임계값 숫자(일째|억|조|%|선)
    if sents.get("s6"):
        body = [x for x in sents["s6"] if not _is_sig(x)]
        if not any(S6_THRESH.search(x) for x in body):
            fail("s6", "임계값 숫자 없음(N일째|N억|N조|N%|N선)", body[0] if body else sents["s6"][0])

    # ⑪ 전체: 금지어 · 추천 표현 · 마지막 문장 질문 금지
    reco_hits: dict[str, set[str]] = {}
    for sid in HUNTER_IDS:
        for x in sents.get(sid) or []:
            if _is_sig(x):
                continue
            if ws := BANNED_ALL.findall(x):
                fail(sid, f"금지어({', '.join(dict.fromkeys(ws))})", x)
            if ws := RECO.findall(x):
                reco_hits[x] = set(ws)
                fail(sid, f"종목 추천 표현({', '.join(dict.fromkeys(ws))})", x)
    body_last = ""
    for sid in ("s6", "s5"):
        rest = [x for x in (sents.get(sid) or []) if not _is_sig(x)]
        if rest:
            body_last = rest[-1]
            break
    if body_last and is_question(body_last):
        fail("s6", "시그니처 앞 마지막 문장이 질문 — 판정 또는 관측값으로 끝낼 것", body_last)
    # 집 규칙 금지어(checks/forbidden) — 하드 금지어만 실패, '단정:' 휴리스틱은 compute 경고에 맡긴다
    try:
        sys.path.insert(0, str(ROOT))
        from checks import forbidden as _fb
        for sid in HUNTER_IDS:
            for x in sents.get(sid) or []:
                if _is_sig(x):
                    continue
                hits = [h for h in _fb.find(x) if not h.startswith("단정:") and h not in reco_hits.get(x, set())]
                if hits:
                    fail(sid, f"금지어 {hits}", x)
    except Exception as e:                                   # 검사 모듈이 없으면 건너뛴다(시험 환경)
        print(f"[qa] forbidden 검사 건너뜀: {e}", file=sys.stderr)

    # 규칙 2: 한 문장 한 숫자 — 2개까지 허용, 3개부터 실패
    for sid in HUNTER_IDS:
        for x in sents.get(sid) or []:
            if _is_sig(x):
                continue
            toks = num_tokens(x)
            if len(toks) > 2:
                fail(sid, f"한 문장에 숫자 {len(toks)}개 {toks} — 최대 2개", x)

    # 규칙 6: 화면 지시어 4회 이상(S2~S4, 문장 단위) — 브리핑(screen="ban")은 거꾸로 화면 설명 금지
    n_dir = sum(1 for sid in SCREEN_IDS for x in (sents.get(sid) or []) if SCREEN_DIR.search(x))
    if screen == "ban":
        for sid in HUNTER_IDS:
            for x in sents.get(sid) or []:
                if not _is_sig(x) and SCREEN_TALK.search(strip_quotes(x)):
                    fail(sid, "화면을 말로 설명함(막대·칸·카드·도장·왼쪽·오른쪽·보세요 금지)", x)
                jm = JARGON.search(strip_quotes(x)) if not _is_sig(x) else None
                if jm:
                    fail(sid, f"사람이 안 쓰는 말({jm.group(0)}) — 쉬운 말로, 날짜는 숫자로(6일째)", x)
    elif n_dir < 4:
        # 문장 없는 실패는 compute 가 avoid 를 못 늘려 첫 회에 폴백했다(리뷰 2). 지시어 없는 S4 문장(숫자가 있는 칸 문장 우선)을 붙인다.
        no_dir = [x for x in (sents.get("s4") or []) if not SCREEN_DIR.search(x) and not _is_sig(x)]
        hit = next((x for x in no_dir if num_tokens(x)), no_dir[0] if no_dir else "")
        fail("s2-s4", f"화면 지시어 {n_dir}회 < 4(보세요|여기 이 칸|왼쪽|오른쪽|위 칸|아래 칸|막대|여기 진행률)", hit)

    # 부록 A-1: 전 편과 글자 그대로 겹친 문장 0개 — 올라간 편 가운데 최근 5편 창, 시그니처·장부 문장 예외(B2)
    d = str((comp or {}).get("date") or "")
    if d:
        try:
            sys.path.insert(0, str(ROOT / "jobs"))
            import script_memory
            ov = script_memory.overlaps(d, scenes, recs, window=script_memory.OVERLAP_WINDOW, aired_only=True,
                                        exempt=script_memory.LEDGER_FORM)
        except Exception as e:
            print(f"[qa] 전 편 겹침 검사 건너뜀: {e}", file=sys.stderr)
            ov = []
        for o in ov:
            if o.get("kind") == "exact" and not _is_sig(o.get("sentence") or ""):
                fail(str(o.get("scene") or "all"), f"전 편과 글자 그대로 겹침 ← {', '.join((o.get('seen') or [])[:3])}", o["sentence"])
    return bad


def _first_with(sents: list[str], pred, default: str = "") -> str:
    """조건에 맞는 첫 문장(실패 문자열의 ' :: ' 뒤에 실을 문장) — 없으면 default."""
    return next((x for x in sents if pred(x)), default)


def check_brief(scenes: list[dict], comp: dict, recs: list[dict] | None = None, warn: list[str] | None = None) -> list[str]:
    """브리핑 포맷 대본 검사(설계 docs/BRIEF_FORMAT_DESIGN.md §3). 빈 목록이면 통과.

    = check_hunter 의 11항·문장 규칙 10·겹침 검사 전부 + 체인이 고정이라 장면마다 '반드시 말해야 하는 내용':
      s2  외국인·기관·개인 세 이름 + 숫자 3개 이상(문장별 ≤2 는 헌터 규칙) + 기타법인(|순매수| 3,000억 미만이면 생략 가능)
      s3a 코스닥·코스피 둘 다 · s3b 빠졌|나갔|순매도 · s3c 들어왔|순매수|들어온 곳이 없었
      s4  comp["hunter"]["s4"]["stocks"] 두 종목 이름 + 외국인·기관·개인(brief_stocks 실패 no_indiv 면 개인 제외)
      s5  뉴스(쪽입니다·뒤집히는 조건은 헌터 ⑧⑨) · s6 임계값(헌터 ⑩) + 시그니처 고정문(9/15 는 '내일부터') + 애프터마켓 문장(9/14~9/18)
      총 글자 수 > 1,250 실패, < 900 경고 — 경고는 warn 목록에 담고(없으면 stderr) 실패로 치지 않는다.
    실패 문자열은 헌터와 같다: "[장면] 규칙 :: 걸린 문장" — compute 는 ' :: ' 뒤 문장을 avoid 에 넣고 다시 만든다.
    """
    bad = check_hunter(scenes, comp, recs, screen="ban")

    def fail(scene: str, rule: str, sent: str = "") -> None:
        bad.append(f"[{scene}] {rule} :: {sent}")

    txt, sents = _scene_text(scenes)
    H = _hunter_comp(comp)
    d = str((comp or {}).get("date") or "")

    # s2 코스피 수급 나열 — 외국인 → 기관 → 개인 넷 다 숫자로, 네 번째 막대 기타법인
    if sents.get("s2"):
        missing = [p for p in BRIEF_PARTIES if p not in txt["s2"]]
        if missing:
            fail("s2", f"코스피 수급 주체 빠짐({'·'.join(missing)}) — 외국인·기관·개인을 다 말해야 한다", sents["s2"][0])
        n = sum(len(num_tokens(x)) for x in sents["s2"] if not _is_sig(x))
        if n < 3:
            fail("s2", f"수급 숫자 {n}개 < 3 — 주체마다 숫자를 말해야 한다",
                 _first_with(sents["s2"], lambda x: not num_tokens(x) and any(p in x for p in BRIEF_PARTIES), sents["s2"][0]))
        v = ((H.get("s2") or {}).get("reveal") or {}).get("v")
        small = isinstance(v, (int, float)) and abs(v) < BRIEF_OTHERS_MIN
        if "기타법인" not in txt["s2"] and not small:
            fail("s2", f"기타법인 없음 — 네 번째 막대를 말해야 한다(|순매수| {BRIEF_OTHERS_MIN:,}억 미만이면 생략 가능)", sents["s2"][-1])

    # s3a 코스닥 수급 + 지수 둘
    if sents.get("s3a"):
        for w in ("코스닥", "코스피"):
            if w not in txt["s3a"]:
                fail("s3a", f"{w} 없음 — 코스닥 수급과 지수 둘(코스피·코스닥)을 말해야 한다", sents["s3a"][0])

    # s3b 돈이 빠진 곳 · s3c 돈이 들어온 곳
    if sents.get("s3b") and not S3B_OUT.search(txt["s3b"]):
        fail("s3b", "빠진 돈 표현 없음(빠졌|나갔|순매도)", sents["s3b"][0])
    if sents.get("s3c") and not S3C_IN.search(txt["s3c"]):
        fail("s3c", "들어온 돈 표현 없음(들어왔|순매수|들어온 곳이 없었)", sents["s3c"][0])

    # s4 종목 둘 — comp 의 두 이름 + 주체별 매매
    if sents.get("s4"):
        s4h = H.get("s4") if isinstance(H.get("s4"), dict) else {}
        names = [str(s.get("name")) for s in (s4h.get("stocks") or []) if isinstance(s, dict) and s.get("name")]
        flat4 = re.sub(r"\s", "", txt["s4"])
        for nm in names[:2]:
            if re.sub(r"\s", "", nm) not in flat4:
                fail("s4", f"종목 이름 없음({nm}) — 대장주와 최대 상승 종목 둘을 말해야 한다", sents["s4"][0])
        need = BRIEF_PARTIES[:2] if s4h.get("no_indiv") else BRIEF_PARTIES
        for p in need:
            if p not in txt["s4"]:
                fail("s4", f"주체 없음({p}) — 종목별 {'외국인·기관' if s4h.get('no_indiv') else '외국인·기관·개인'} 매매를 말해야 한다",
                     _first_with(sents["s4"], lambda x: bool(num_tokens(x)) and not S4_OPEN.search(x), sents["s4"][-1]))

    # s5 뉴스와 맞물렸나 — '뉴스' 한 마디는 뉴스가 없는 날("뉴스 없이 수급만 움직인 날")에도 있다
    if sents.get("s5") and not re.search(r"뉴스|이슈|소식|간밤 미국|미국 반도체지수", txt["s5"]):      # 브리핑은 '오늘 주요 이슈를 보겠습니다' 로 연다(JJ 2026-09-17)
        fail("s5", "뉴스 없음 — 뉴스와 맞물렸는지 말해야 한다(없으면 '뉴스 없이 수급만 움직인 날')", sents["s5"][0])

    # s6 시그니처 고정문 + 애프터마켓 문장(임계값 숫자는 헌터 ⑩)
    if sents.get("s6"):
        t6, last = txt["s6"], sents["s6"][-1]
        if SIG_BRAND not in t6:
            fail("s6", f"시그니처 없음('{SIG_BRAND}')", last)
        want = SIG_FIRST if d == SIG_FIRST_DATE else SIG_DAILY
        if d and want not in t6:
            fail("s6", f"끝 멘트 고정문 없음('{want}'){' — 9/15 편만 내일부터' if d == SIG_FIRST_DATE else ''}", last)
        elif not d and SIG_DAILY not in t6 and SIG_FIRST not in t6:
            fail("s6", f"끝 멘트 고정문 없음('{SIG_DAILY}')", last)
        elif last not in (SIG_DAILY, SIG_FIRST):
            fail("s6", "끝 멘트 고정문이 마지막 문장이 아님", last)
        if d and AFTER_MARKET_FROM <= d <= AFTER_MARKET_UNTIL and AFTER_MARKET not in t6:
            fail("s6", f"애프터마켓 문장 없음(9/18까지 시그니처 앞에 넣는다: '{AFTER_MARKET}')", last)
        elif d > AFTER_MARKET_UNTIL and "애프터마켓" in t6:
            fail("s6", "애프터마켓 문장은 9/18까지만", _first_with(sents["s6"], lambda x: "애프터마켓" in x, last))

    # 총 글자 수 — 넘으면 실패(가장 긴 비시그니처 문장을 실어 재시도가 그 후보를 바꾸게), 모자라면 경고
    total = sum(len(txt[sid]) for sid in HUNTER_IDS if sid in txt)
    if total > BRIEF_TOTAL_MAX:
        longest = max((x for sid in HUNTER_IDS for x in sents.get(sid) or [] if not _is_sig(x)), key=len, default="")
        fail("all", f"총 {total:,}자 > {BRIEF_TOTAL_MAX:,}자 — {total - BRIEF_TOTAL_MAX}자 줄여야 한다", longest)
    elif total < BRIEF_TOTAL_MIN:
        msg = f"[all] 경고: 총 {total:,}자 < {BRIEF_TOTAL_MIN}자 — 짧다(950~1,250자 권장), 실패는 아님"
        if warn is not None:
            warn.append(msg)
        else:
            print(f"[qa] {msg}", file=sys.stderr)
    return bad


# ══════════════════════════════════════════════════════════════════════════════
# 공통 검사(평일·주간)
# ══════════════════════════════════════════════════════════════════════════════
def out_dir(kind: str, date: str) -> Path:
    a, b = DIRS[kind]
    return ROOT / "out" / a / date / b if a else ROOT / "out" / date / b


def data_script(kind: str, date: str) -> Path:
    a, _ = DIRS[kind]
    return ROOT / "data" / a / date / "script.json" if a else ROOT / "data" / date / "computed_kr.json"


def _kind(kind: str) -> str:
    return "day" if kind == "hunter" else kind


def load_doc(kind: str, date: str, file: str | None = None) -> dict:
    p = Path(file) if file else data_script(_kind(kind), date)
    return json.loads(p.read_text(encoding="utf-8"))


def load_scenes(kind: str, date: str, file: str | None = None) -> list[dict]:
    kind = _kind(kind)
    d = load_doc(kind, date, file)
    return d["scenes"] if kind in ("kr", "us") else d.get("scenes") or []


def recent_scripts(kind: str, date: str, n: int = 3) -> list[str]:
    """같은 편의 직전 N편 대본(뼈대 비교용)."""
    a, b = DIRS[kind]
    base = ROOT / "out" / a if a else ROOT / "out"
    ds = sorted([x for x in base.iterdir() if x.is_dir() and x.name.isdigit() and x.name < date], reverse=True)
    out = []
    for d in ds[:n]:
        f = (d / b / "script.txt") if b else (d / "script.txt")
        if f.exists():
            out.append(f.read_text(encoding="utf-8"))
    return out


def mask(s: str) -> str:
    """숫자·주체를 가려 문장 뼈대만 남긴다."""
    s = re.sub(r"[\d,.]+%?", "N", s)
    for w in ("외국인", "기관", "개인", "기타법인", "반도체", "에너지", "헬스케어", "코스피", "나스닥", "S&P500", "다우"):
        s = s.replace(w, "X")
    return re.sub(r"\s+", "", s)


def check_script(kind: str, date: str, doc: dict | None = None, file: str | None = None) -> list[str]:
    kind = _kind(kind)
    doc = doc if doc is not None else load_doc(kind, date, file)
    scenes = doc["scenes"] if kind in ("kr", "us") else doc.get("scenes") or []
    fmt = doc.get("format")
    hunter = fmt in ("hunter", "brief")             # 장면 id 가 s0..s6 를 넘어도(s3a·s3b·s3c) 길이 한도는 평일과 같다(브리핑도 같은 9장면)
    bad: list[str] = []
    if not scenes:
        return ["장면 없음"]
    lim, floor, close_max = LIMIT.get(kind, LIMIT["day"]), FLOOR.get(kind, FLOOR["day"]), CLOSE_MAX.get(kind, CLOSE_MAX["day"])
    total = sum(len(s["tts"]) for s in scenes)
    sec = total / CPS + 0.4 * len(scenes)
    if sec > lim:
        bad.append(f"길이 {sec:.0f}초 > 한도 {lim}초 ({total}자, {int(sec - lim) * CPS:.0f}자 줄여야 함)")
    elif sec < floor:
        bad.append(f"길이 {sec:.0f}초 < 하한 {floor}초 — 짧으면 성의 없어 보인다({total}자)")
    close = sum(len(x["tts"]) for x in scenes[-2:])
    if close > close_max:
        bad.append(f"마무리 {close}자 > {close_max}자 — 끝이 길면 이탈한다")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "jobs"))
    from checks import forbidden
    import tts as _tts                        # 실제로 들리는 문장으로 검사한다(2.3조는 '2조 3천억'으로 읽힌다)
    for s in scenes:
        t = _tts.speakable(s["tts"])
        if hits := forbidden.find(t):
            bad.append(f"{s['id']} 금지어 {hits}")
        for line in re.split(r"(?<=[.?!])\s+", t):
            if line and BAD_END.search(line.strip()):
                bad.append(f"{s['id']} 축약 종결형 — {line[:26]}")
            if line and CHAT.search(line):
                bad.append(f"{s['id']} 채팅 기호 — {line[:26]}")
        if TIGHT_NUM.search(t):
            bad.append(f"{s['id']} 압축 숫자(9.9조 형태) — 풀어 쓸 것: {TIGHT_NUM.findall(t)}")
    last = scenes[-2]["tts"] + scenes[-1]["tts"] if len(scenes) > 1 else scenes[-1]["tts"]
    if not MEANING.search(last):
        bad.append("마지막에 '그래서 무슨 뜻'이 없음 — 사실만 나열하고 끝남")
    if hunter:                                 # 헌터 대본은 '…일까요.' 처럼 물음표 없이 묻는다
        qs = sum(1 for s in scenes if any(has_question(x) for x in _sents(s["tts"])))
    else:
        qs = sum(1 for s in scenes if "?" in s["tts"])
    if qs < max(2, len(scenes) // 3):
        bad.append(f"질문이 {qs}개뿐 — 장면마다 다음 질문으로 이어지는지 볼 것")
    def _skel(txt: str) -> set[str]:
        return {mask(x) for x in re.split(r"(?<=[.?!])\s+", txt) if len(x) > 12 and x.strip() not in FIXED}

    mine = set().union(*(_skel(s["tts"]) for s in scenes)) if scenes else set()
    for k, prev in enumerate(recent_scripts(kind, date), 1):
        dup = mine & _skel(prev)
        if len(dup) >= 2:
            bad.append(f"직전 {k}번째 편과 문장 뼈대 {len(dup)}개 겹침 — 표현을 바꿀 것")
    if fmt == "brief":
        bad += check_brief(scenes, doc)
    elif hunter:
        bad += check_hunter(scenes, doc)
    return bad


def frames(kind: str, date: str) -> Path:
    """장면·큐마다 프레임을 뽑아 out/.../frames/ 에 저장. 말과 화면을 눈으로 대조하는 용도."""
    od = out_dir(_kind(kind), date)
    props = json.loads((od / "props.json").read_text(encoding="utf-8"))
    fd = od / "frames"
    fd.mkdir(exist_ok=True)
    for f in fd.glob("*.jpg"):
        f.unlink()
    n = 0
    for sc in props["scenes"]:
        for c in sc.get("cues") or []:
            if len(c["text"]) < 10:
                continue
            t = sc["start"] + c["start"] + min(1.6, (c["end"] - c["start"]) * 0.7)
            safe = re.sub(r"[^0-9A-Za-z가-힣]", "", c["text"])[:16]
            subprocess.run([str(FF), "-y", "-loglevel", "error", "-ss", f"{t:.1f}", "-i", str(od / "video.mp4"),
                            "-frames:v", "1", "-q:v", "5", "-vf", "scale=420:-1",
                            str(fd / f"{n:02d}_{sc['id']}_{safe}.jpg")], check=True)
            n += 1
    print(f"프레임 {n}장 → {fd}\n  각 파일 이름이 그때 나오는 말이다. 화면과 맞는지 눈으로 대조할 것.")
    return fd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["script", "frames", "all", "hunter"])
    ap.add_argument("--kind", required=True, choices=["day", "kr", "us", "hunter"])
    ap.add_argument("--date", help="YYYYMMDD (--file 을 주면 파일의 date 로 대신할 수 있다)")
    ap.add_argument("--file", help="data/<date>/computed_kr.json 대신 검사할 json (오프라인 시험용)")
    a = ap.parse_args()
    if not a.date and not a.file:
        ap.error("--date 또는 --file 이 필요하다")
    doc = load_doc(a.kind, a.date, a.file) if a.cmd in ("script", "all", "hunter") else None
    date = a.date or str(doc.get("date") or "")
    rc = 0
    if a.cmd in ("script", "all"):
        bad = check_script(a.kind, date, doc)
        print("대본 점검:", "통과" if not bad else f"{len(bad)}건")
        for x in bad:
            print("  ✗", x)
        rc = 1 if bad else 0
    if a.cmd == "hunter":
        warn: list[str] = []
        if doc.get("format") == "brief":
            bad = check_brief(doc.get("scenes") or [], doc, warn=warn)
            print("브리핑 검사(헌터 11항 + 고정 내용):", "통과" if not bad else f"{len(bad)}건")
        else:
            bad = check_hunter(doc.get("scenes") or [], doc)
            print("헌터 11항:", "통과" if not bad else f"{len(bad)}건")
        for x in bad:
            print("  ✗", x)
        for x in warn:
            print("  ⚠", x)
        rc = 1 if bad else 0
    if a.cmd in ("frames", "all"):
        frames(a.kind, date)
    sys.exit(rc)


if __name__ == "__main__":
    main()
