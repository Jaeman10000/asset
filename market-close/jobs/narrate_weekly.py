# -*- coding: utf-8 -*-
"""누가샀나 주간 결산(토요일) 대본 + Threads.

입력: data/weekly/<build>/computed_weekly.json (SHARED SCHEMA) + data/weekly/<build>/news.json
출력: build_weekly(w, news) -> {"scenes": [{"id": "w0".."w6", "min", "tts", "sub", "ask"}], "title", "threads", "threads_reply",
                                "hook_parts", "hook_type", "picks"(문형 번호 — 다음 주가 피한다), "est_sec", "issues"(비어 있어야 정상)}

장면
  w0 훅: 그 주 가장 센 대비(데이터로 고름: 가장 많이 판 주체 vs 가장 많이 산 주체 / 주 중 방향을 바꾼 주체 / 지수) + 질문
  w1 답: 코스피 한 주 길(그 주 등락을 만든 날 → 천 단위 선을 넘나든 날 → 종가)
  w2 질문→답: 첫날과 마지막 날의 사는 쪽·파는 쪽, 방향을 바꾼 주체의 앞·뒤 금액, 한 주 합계(숫자 5개까지)
  w3 질문→답: 주 중 돈의 방향이 뒤집힌 테마(없으면 가장 많이 빠진 테마) → 끝까지 머문 테마 → 기타법인 종목별 매수와 자사주 매입
  w4 질문→답: 뉴스(confidence high/medium만), 날짜를 붙여 '같은 날 …'로 나란히 놓고 연결은 완곡하게만
  w5 우리 해석: 한 문장 정리 + 완곡한 '그래서 뭔데'
  w6 이번 주 확인 기록 + 다음 주 볼 것 하나 + 고정 끝 멘트

원칙(JJ)
  - 합니다체, 묻고 답하는 사슬(w0 끝 질문 → w1 첫 문장이 답, w2~w4는 질문으로 열고 바로 답). '국장 수급입니다' 같은 꼬리표·괄호 없음.
  - 일간 영상의 고정 문장은 쓰지 않는다('그렇다면 누가 샀을까요?', '가장 많이 산 쪽은 X입니다', '그럼 가장 큰 돈이 빠진 곳은 어디였을까요?',
    '어제 …보자고 했죠', '지금까지 N 번 확인했고' …) → DAILY_FIXED + 그 주 일간 대본과 유사도 검사.
  - 모든 자리(slot)는 문형 3개 이상. ISO 주 번호로 고르고, 지난주 결산이 쓴 문형은 피한다(picks, 없으면 문구 대조).
    같은 장면 안에서 같은 서술어(끝났습니다 …)가 겹치지 않는 문형을 먼저 고른다.
  - 숫자는 전부 w(우리 데이터)에서. 반올림은 '약'(TTS) / 넘게·가까이·정도(Threads). 지수는 'N,N00선'(밴드 표기).
  - 원인 단정 금지. 종목명은 기타법인 돈이 간 곳(자사주 매입 연결)에만. 추천·매매 지시 없음. checks/forbidden 통과 필수.
  - 길이: 한 음절 약 1/5.1초(일간 음성 실측). TARGET_SEC를 넘으면 덜 중요한 문장(우선순위 번호가 큰 것)부터 뺀다.

Run:  python narrate_weekly.py [build_date]
  data/weekly/<build>/computed_weekly.json 이 있으면 그걸로, 없으면 일간 파일로 메모리 초안을 만들어(파일은 쓰지 않음) 대본을 출력하고 검사한다.
"""
from __future__ import annotations

import copy
import difflib
import glob
import io
import json
import math
import os
import re
import sys
import zlib
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(os.path.dirname(ROOT), "backend"), ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from checks import forbidden  # noqa: E402
from narrate import _and, _bat, obj, ro, subj, won  # noqa: E402
import threads_v4 as tv4  # noqa: E402  (Threads 금지어 목록·숫자 반올림·뼈대 비교만 빌려 쓴다)

try:
    from app.services.themes import CODE_NAME, CODE_THEME  # 95종목: 코드 -> 이름/테마
except Exception:  # pragma: no cover
    CODE_NAME, CODE_THEME = {}, {}

DATA = os.path.join(ROOT, "data")
WD = "월화수목금토일"
DAYN = {1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레"}
DAYC = {2: "이틀째", 3: "사흘째", 4: "나흘째", 5: "닷새째", 6: "엿새째", 7: "이레째"}
CNT = {1: "한 번", 2: "두 번", 3: "세 번", 4: "네 번", 5: "다섯 번", 6: "여섯 번", 7: "일곱 번"}
HAN = {1: "하나", 2: "둘", 3: "셋", 4: "넷", 5: "다섯", 6: "여섯", 7: "일곱"}
GROUPS = (("개인", "indiv"), ("외국인", "foreign"), ("기관", "inst"), ("기타법인", "others"))
GNAMES = tuple(n for n, _ in GROUPS)
MAIN3 = ("외국인", "기관", "개인")          # 동률이면 이 순서
SIGNOFF = "누가샀나 주간 결산이었습니다. 평일엔 매일 오후 4시 30분에 국장 마감이 올라옵니다."
TAG = "#국장"
NEUTRAL = 300          # 억: 이보다 작은 날은 방향 판단에서 어느 쪽으로도 센다
MIN_PART = 5000        # 억: 주 중 방향 전환으로 인정하는 앞·뒤 최소 금액
MAX_NEWS = 2
SYL_PER_SEC = 5.1      # 일간 영상 음성 실측(음절+숫자 1.5 가중)
TARGET_SEC = 150.0     # 일간(약 110초)보다 길다 — 주간은 장면이 7개. 줄이려면 이 값만 낮추면 PRIO 순서로 빠진다.
MIN_SEC = {"w0": 5.0, "w1": 8.0, "w2": 8.0, "w3": 8.0, "w4": 6.0, "w5": 5.0, "w6": 6.0}
# 덜 중요한 문장부터 뺀다(큰 번호 먼저). 여기 없는 문장은 필수. 기록의 '그래서 뭔데'(w6.mean)는 JJ가 요청한 것이라 맨 마지막에 뺀다.
PRIO = {"w1.near": 6, "w1.held": 6, "w6.cond": 5, "w3.stay_small": 5, "w1.touched": 4, "w3.link": 4, "w6.fails": 3, "w6.mean": 1}

# 일간 A+ 영상(narrate_aplus)과 그 주 실제 대본에 박혀 있는 문장 조각 — 주간 대본엔 나오면 안 된다
DAILY_FIXED = [
    "누가 샀을까요", "누가 팔았을까요", "누가 이 물량을 받았을까요", "그렇다면", "가장 많이 산 쪽은", "가장 많이 판 쪽은",
    "다음으로 많이 산", "다음으로 많이 판", "처음부터 이렇게", "언제 이렇게 많이", "마감까지 계속", "오후 2시",
    "가장 큰 돈이 빠진 곳", "가장 큰 돈이 들어간 곳", "외국인과 기관을 합친", "외국인과 기관을 합쳐", "간밤", "발표도 있었습니다",
    "보자고 했죠", "결과는 끊겼습니다", "지금까지", "번 확인했고", "한번 들어온 돈이", "오래 머물지 않았다는 뜻", "옮겨 다니는 장",
    "방향이 자주 바뀌는 장", "한쪽으로 보긴", "방향을 단정하긴", "이것 하나만 봅니다", "테마 대신", "이어질까요", "잠깐이 아니라는 뜻",
    "한고비", "한 번 사고 멈춘 돈", "회사가 자기 주식을 사면", "기타법인으로 잡힙니다", "기타법인으로 잡히는데", "자사주를 사들이는 중이라",
    "자사주 매입이 섞인 것으로", "어느 회사가", "국장 마감은 매일", "국장 수급입니다", "돈은 어디로 갔을까요", "정리하면",
    "옮겨갔습니다", "그 돈은 어디로", "하루짜리일 때가 많아", "이틀째 확인이 먼저", "머무는지만 매일", "선을 되찾았습니다",
    "선을 내줬습니다", "선을 지켰습니다", "매도의 중심에는", "사는 쪽에서 파는 쪽으로", "파는 쪽에서 사는 쪽으로", "거의 전부가",
    "자사주를 사들이고 있습니다",
]


# ── 말 다듬기 ──
def eun(w: str) -> str:
    return w + ("은" if _bat(w) else "는")


def wa(w: str) -> str:
    return w + ("과" if _bat(w) else "와")


def ieot(w: str) -> str:
    """'반도체였' / '약 1,600억이었' / '수요일이었'"""
    return w + ("이었" if _bat(w) else "였")


def ira(w: str) -> str:
    return w + ("이라" if _bat(w) else "라")


def amt(v: float) -> str:
    return won(abs(v))                               # TTS: '약 9.9조'


def amt_s(v: float) -> str:
    return won(abs(v)).replace("약 ", "")            # 제목·화면: '9.9조'


def pc(v: float) -> str:
    return f"{abs(v):.2f}%"


def band(v: float, step: int = 100) -> str:
    return f"{int(v // step * step):,}선"


def _dt(d: str) -> datetime:
    return datetime.strptime(str(d), "%Y%m%d")


def wdn(d: str) -> str:
    return WD[_dt(d).weekday()] + "요일"


def span(ds: list[str]) -> str:
    """['20260907','20260908'] -> '월요일과 화요일' / 3일 이상 -> '수요일부터 금요일까지'"""
    if len(ds) == 1:
        return wdn(ds[0])
    if len(ds) == 2:
        return f"{wa(wdn(ds[0]))} {wdn(ds[1])}"
    return f"{wdn(ds[0])}부터 {wdn(ds[-1])}까지"


def span_en(ds: list[str]) -> str:
    """'월요일과 화요일엔' / '수요일부터 금요일까지는'"""
    s = span(ds)
    return s + ("는" if s.endswith("까지") else "엔")


def short_days(ds: list[str]) -> str:
    """Threads용 '월화' / '수목금'"""
    return "".join(WD[_dt(d).weekday()] for d in ds)


def tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s.replace(" ,", ",").replace(" .", ".").replace(",,", ",").replace(" ?", "?")


def sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.?!])\s+", (text or "").strip()) if x]


def est_sec(text: str) -> float:
    return (len(re.findall(r"[가-힣]", text or "")) + 1.5 * len(re.findall(r"\d", text or ""))) / SYL_PER_SEC


def stems(text: str) -> set[str]:
    """서술어 줄기: '끝났습니다'·'끝났고,' -> '끝났'"""
    return set(re.findall(r"(\S+?)(?:습니다[.?]?|고,)", text or ""))


def tail(text: str) -> str:
    """마지막 절의 뼈대(숫자·요일 가림) — 한 장면에서 같은 꼴의 절이 되풀이되지 않게."""
    s = re.sub(r"\d[\d,.]*", "N", text or "")
    s = re.sub(r"[월화수목금토일]요일", "W", s)
    return s.split(", ")[-1]


def _won_th(v: float) -> str:
    """Threads 금액은 풀어 쓴다(JJ 2026-09-12): 9.9조 -> '9조 9천억', 5,000억 -> '5천억', 4,700억 -> '4,700억'."""
    a = abs(float(v or 0))
    if a >= 10000:
        n = int(a / 1000 + 0.5)                      # 1,000억(=0.1조) 단위로 반올림
        jo, ch = divmod(n, 10)
        return f"{jo}조" if ch == 0 else f"{jo}조 {ch}천억"
    if a >= 1000:
        h = int(a / 100 + 0.5) * 100
        if h >= 10000:
            return "1조"
        return f"{h // 1000}천억" if h % 1000 == 0 else f"{h:,}억"
    return f"{int(a / 10 + 0.5) * 10:,}억"


def _pc_th(v: float) -> str:
    """Threads 등락률: '3.3%' (소수 한 자리, 끝의 0은 뗀다)."""
    return f"{abs(v):.1f}".rstrip("0").rstrip(".") + "%"


# ── 문형 고르기: 주 번호로 돌리고, 지난주 결산이 쓴 문형은 피한다 ──
class Picker:
    def __init__(self, week_no: int, prev: dict | None, reuse=None):
        self.week_no = week_no
        self.reuse = reuse or (lambda t: False)      # 일간 대본과 겹치는 문형이면 True
        self.prev_picks = (prev or {}).get("picks") or {}
        self.prev_text = _prev_text(prev)
        self.picks: dict[str, int] = {}
        self.starts: set[str] = set()
        self.scene_stems: set[str] = set()

    def new_scene(self) -> None:
        self.scene_stems = set()

    @staticmethod
    def _fragments(tpl) -> list[str]:
        tpl = " ".join(tpl) if isinstance(tpl, tuple) else tpl
        return [f.strip(" ,.?") for f in re.split(r"\{[^{}]*\}", tpl) if len(f.strip(" ,.?")) >= 6]

    def used_last_week(self, slot: str, i: int, tpl) -> bool:
        if self.prev_picks:
            return self.prev_picks.get(slot) == i
        return bool(self.prev_text) and any(f in self.prev_text for f in self._fragments(tpl))

    def __call__(self, slot: str, bank: list, *, threads: bool = False, question: bool = False, unlike: tuple = (), ok=None, **kw):
        n = len(bank)
        start = (self.week_no + zlib.crc32(slot.encode("utf-8"))) % n
        order = [(start + j) % n for j in range(n)]
        chk = forbidden.find_threads if threads else forbidden.find

        def render(i):
            b = bank[i]
            return tuple(tidy(x.format(**kw)) for x in b) if isinstance(b, tuple) else tidy(b.format(**kw))

        out = [(i, render(i)) for i in order]
        flat = lambda t: " ".join(t) if isinstance(t, tuple) else t  # noqa: E731

        def head(t):
            t = flat(t)
            return t.split(" ")[0] if t else ""

        clean = lambda t: not chk(flat(t)) and (threads or not any(self.reuse(s) for s in sentences(flat(t))))  # noqa: E731
        fresh = lambda i, t: not self.used_last_week(slot, i, bank[i])  # noqa: E731
        varied = lambda t: not (stems(flat(t)) & self.scene_stems) and not any(tail(flat(t)) == tail(u) for u in unlike)  # noqa: E731
        uniq = lambda t: not (question and head(t) in self.starts)  # noqa: E731
        fits = ok or (lambda t: True)                # 길이 같은 추가 조건(Threads 줄 길이)
        tiers = [lambda i, t: clean(t) and fits(t) and fresh(i, t) and varied(t) and uniq(t),
                 lambda i, t: clean(t) and fits(t) and fresh(i, t) and varied(t),
                 lambda i, t: clean(t) and fits(t) and fresh(i, t),
                 lambda i, t: clean(t) and fits(t),
                 lambda i, t: clean(t)]
        for ok in tiers:
            for i, t in out:
                if ok(i, t):
                    return self._take(slot, i, t, question, head)
        return self._take(slot, out[0][0], out[0][1], question, head)

    def _take(self, slot, i, t, question, head):
        self.picks[slot] = i
        self.scene_stems |= stems(" ".join(t) if isinstance(t, tuple) else t)
        if question:
            self.starts.add(head(t))
        return t


def _prev_text(prev: dict | None) -> str:
    if not prev:
        return ""
    parts = [s.get("tts") or "" for s in prev.get("scenes") or []]
    parts += [prev.get("title") or "", prev.get("threads") or ""]
    return "\n".join(parts)


PREV_OVERRIDE: dict | None = None      # 시험용: 지난주 결산을 직접 넣는다


def _prev_week(w: dict) -> dict | None:
    """직전 주 결산(computed_weekly.json)이 scenes를 가지고 있으면 돌려준다."""
    if PREV_OVERRIDE is not None:
        return PREV_OVERRIDE or None
    b = str(w.get("build_date") or w.get("week_end") or "")
    paths = sorted(p for p in glob.glob(os.path.join(DATA, "weekly", "*", "computed_weekly.json"))
                   if os.path.basename(os.path.dirname(p)) < b)
    if not paths:
        return None
    try:
        with open(paths[-1], encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return None
    return j if j.get("scenes") else None


# ── 사실 뽑기 ──
def _split(vals: list[float], days: list[str], min_part: float = MIN_PART) -> dict | None:
    """주 중 한 번 방향이 바뀐 자리: 앞 k일과 뒤 날들의 합이 반대 부호이고 각 구간이 한 방향(작은 날은 무시)."""
    best = None
    for k in range(1, len(vals)):
        a, b = vals[:k], vals[k:]
        sa, sb = sum(a), sum(b)
        if sa * sb >= 0 or min(abs(sa), abs(sb)) < min_part:
            continue
        if not (all(x * sa > 0 or abs(x) < NEUTRAL for x in a) and all(x * sb > 0 or abs(x) < NEUTRAL for x in b)):
            continue
        sc = min(abs(sa), abs(sb))
        if best is None or sc > best["score"]:
            best = {"k": k, "early": sa, "late": sb, "score": sc, "early_days": days[:k], "late_days": days[k:]}
    return best


def _norm_date(x, year: int) -> str | None:
    s = str(x or "").strip()
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    m = re.match(r"^(\d{1,2})/(\d{1,2})", s)
    if m:
        return f"{year}{int(m.group(1)):02d}{int(m.group(2)):02d}"
    return None


# 뉴스 이름: 짧게 소리 내 읽을 수 있는 사건 명사구만(시황 요약·수급 문장·숫자 목적어는 버림)
_EVENT_END = ("공개", "인수", "공격", "돌파", "급등", "급락", "상승", "하락", "상회", "하회", "발표", "날", "만기", "정기변경", "변경", "전환",
              "회복", "최대", "최고", "최고가", "보도", "결정", "인상", "인하", "동결", "개막", "출시", "합의", "타결", "충돌", "긴장", "우려",
              "부담", "훈풍", "쇼크", "경계", "강세", "약세", "매입", "리스크", "반등", "편입", "실적", "지표", "회의", "연설", "서프라이즈",
              "관세", "제재", "소식")
_THRESH = ("돌파", "회복", "상회", "하회", "넘어", "붕괴", "도달", "경신")
_BAD_LABEL = re.compile(r"%|코스피|코스닥|마감|속보|\?|순매수|순매도|" + "|".join(GNAMES))
_DAY_LIKE = ("날", "만기", "발표", "공개", "결정", "회의", "지표", "소식", "행사", "개막", "출시", "이벤트", "분석", "보도", "변경", "인수",
             "공격", "합의", "타결", "연설", "매입")


def _label_from_title(title: str) -> str:
    """'후티, 사우디 석유시설 공격… 7,171까지 갔던 코스피 하락 전환' -> '후티의 사우디 석유시설 공격'
       '유가 6%대 급등·미 10년물 4.95%·PPI 추정치 상회(9/10)' -> '유가 급등' / '네 마녀의 날 + KRX …' -> '네 마녀의 날'"""
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]|【[^】]*】|<[^>]*>", " ", title or "")
    t = re.sub(r"[\"'‘’“”`]", "", t)
    segs = []
    for s in re.split(r"\s*(?:…|\.\.\.|\s\+\s|,\s|\s[-—|]\s)\s*", t):
        parts = s.split("·")
        segs += parts if len(parts) > 1 and all(" " in p.strip() for p in parts) else [s]   # 원·달러, 유가·금리는 두고
    segs = [re.sub(r"\s+", " ", x).strip(" ,.") for x in segs if x.strip(" ,.")]
    good = []
    for i, s in enumerate(segs):
        toks, keep, bad = s.split(), [], False
        for j, tok in enumerate(toks):
            if re.search(r"\d", tok) and not re.fullmatch(r"\d+달러", tok):
                if j == len(toks) - 2 and toks[-1].startswith(_THRESH):      # '4.85% 돌파'처럼 숫자가 목적어면 버림
                    bad = True
                continue
            keep.append(tok)
        lab = " ".join(keep)
        if bad or len(keep) < 2 or not lab.endswith(_EVENT_END) or _BAD_LABEL.search(lab) or len(lab) > 18:
            continue
        if i > 0 and len(segs[i - 1].split()) == 1 and not re.search(r"\d", segs[i - 1]) and not _BAD_LABEL.search(segs[i - 1]):
            lab = f"{segs[i - 1]}의 {lab}"                                 # '후티, 사우디 …' -> '후티의 사우디 …'
        good.append(lab)
    if not good:
        return ""
    if len(good) >= 2 and len(good[0]) + len(good[1]) + 2 <= 14:
        return f"{wa(good[0])} {good[1]}"
    return good[0]


def _clean_short(s: str) -> str:
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s or "")
    s = re.sub(r"[\"'‘’“”`]", "", s)
    return re.sub(r"\s+", " ", s).strip(" ,.·-|")


def news_events(w: dict, news) -> list[dict]:
    """news.json(+ w['news'])에서 이번 주 날짜·confidence high/medium·짧은 이름이 나오는 사건만. 하루 하나(관련도 높은 것)."""
    raw = []
    for src in (news, w.get("news")):
        if isinstance(src, dict):
            src = src.get("events") or src.get("items") or src.get("news") or []
        if isinstance(src, list):
            raw += [x for x in src if isinstance(x, dict)]
    days = [str(d) for d in w["days"]]
    year = int(days[0][:4])
    conf_map = {"상": "high", "높음": "high", "중": "medium", "보통": "medium", "하": "low", "낮음": "low"}
    stock_names = set(CODE_NAME.values()) | {x.get("name") for x in ((w.get("others_stocks") or {}).get("week") or []) if x.get("name")}
    by_day: dict[str, dict] = {}
    for n, e in enumerate(raw):
        conf = conf_map.get(str(e.get("confidence") or e.get("conf") or "").strip().lower(),
                            str(e.get("confidence") or e.get("conf") or "").strip().lower())
        if conf not in ("high", "medium"):
            continue
        d = _norm_date(e.get("d") or e.get("date") or e.get("day"), year)
        if d not in days:
            continue
        label = ""
        for key in ("spoken", "label", "event", "topic"):
            c = _clean_short(str(e.get(key) or ""))
            if c and len(c) <= 18 and not _BAD_LABEL.search(c) and not re.search(r"\d[\d,.]*\s?(조|억|원|선|포인트)", c):
                label = c
                break
        if not label:
            label = _label_from_title(str(e.get("title") or e.get("headline") or ""))
        if not label:
            continue
        link = str(e.get("market_link") or "")
        rel = (2 if conf == "high" else 1) + (1 if "외국인" in link else 0) + (0.5 if re.search(r"배경|풀이|분석|꼽", link) else 0) \
            - (1.5 if any(nm and nm in label for nm in stock_names) else 0)
        who = e.get("who") or e.get("actor")
        item = {"d": d, "label": label, "conf": conf, "rel": rel, "order": n, "who": who if who in GNAMES else None,
                "src": e.get("sources") or e.get("source") or e.get("src")}
        cur = by_day.get(d)
        if cur is None or rel > cur["rel"]:
            by_day[d] = item
    return [by_day[d] for d in days if d in by_day]


def _line_events(kd: list[dict], prev_close: float, extra: list[dict] | None) -> list[dict]:
    """천 단위 선을 넘나든 날: regained(종가로 넘음)/lost(종가로 내줌)/touched(장중만 넘음)/held(장중만 내줌).
    가장 많이 넘나든 선 하나만 쓴다. 데이터 쪽 events에 n_days나 'N거래일'이 있으면 붙인다."""
    if not kd or not prev_close:
        return []
    lo_all = min([x["low"] for x in kd] + [prev_close])
    hi_all = max([x["high"] for x in kd] + [prev_close])
    best: list[dict] = []
    for L in range(int(math.ceil(lo_all / 1000.0)) * 1000, int(hi_all) + 1, 1000):
        ev, p = [], prev_close
        for x in kd:
            c, h, lo = x["close"], x["high"], x["low"]
            kind = ("regained" if p < L <= c else "lost" if c < L <= p else
                    "touched" if (p < L and c < L and h >= L) else "held" if (p >= L and c >= L and lo < L) else None)
            if kind:
                ev.append({"d": str(x["d"]), "kind": kind, "line": L, "high": h, "low": lo, "close": c})
            p = c
        if len(ev) > len(best) or (ev and len(ev) == len(best) and abs(L - kd[-1]["close"]) < abs(best[0]["line"] - kd[-1]["close"])):
            best = ev
    for e in best:
        for x in extra or []:
            if str(x.get("d")) == e["d"] and x.get("kind") == e["kind"]:
                m = re.search(r"(\d+)\s*거래일", str(x.get("text") or ""))
                nd = x.get("n_days") or (int(m.group(1)) if m else None)
                if nd:
                    e["n_days"] = int(nd)
    return best


def _checks(w: dict) -> list[dict]:
    out = []
    for c in w.get("checks") or []:
        q = (c.get("q") or "").strip()
        m = re.match(r"^(.+?) (순매수|순매도)가 (\S+째) 이어지는지$", q)
        if not m:
            continue
        name, word, nth = m.groups()
        item = f"{name} {word} {nth}" if name in GNAMES else f"{name} {nth}"
        out.append({"d": str(c.get("d") or ""), "ok": bool(c.get("ok")), "item": item, "name": name, "theme": name not in GNAMES})
    return sorted(out, key=lambda x: x["d"])


def _next_q(w: dict, streak_end: dict) -> str:
    """다음 주 볼 것 하나: 금요일 일간 영상의 check.next_q를 그대로. 없으면 streak_end로 만든다."""
    if w.get("next_q"):
        return w["next_q"]
    p = os.path.join(DATA, str(w.get("week_end") or w["days"][-1]), "computed_kr.json")
    try:
        with open(p, encoding="utf-8") as f:
            q = ((json.load(f).get("check") or {}).get("next_q")) or ""
        if q:
            return q
    except Exception:
        pass
    for n, key in (("외국인", "foreign"), ("기관", "inst")):
        st = int(streak_end.get(key) or 0)
        if abs(st) >= 2:
            return f"{n} {'순매수' if st > 0 else '순매도'}가 {DAYC.get(abs(st) + 1, str(abs(st) + 1) + '일째')} 이어지는지"
    return ""


def facts(w: dict) -> dict:
    days = [str(d) for d in w["days"]]
    n_days = len(days)
    k = w.get("kospi") or {}
    krow = {str(x["d"]): x for x in k.get("days") or []}
    kd = [dict(krow[d], d=d) for d in days if d in krow]
    prev_close = k.get("prev_close")
    C = k.get("week_chg_pct")
    if C is None and prev_close and kd:
        C = round((kd[-1]["close"] / prev_close - 1) * 100, 2)
    inv = w.get("inv") or {}
    invd = {str(x["d"]): x for x in inv.get("days") or []}
    ser = {n: [float((invd.get(d) or {}).get(key) or 0) for d in days] for n, key in GROUPS}
    wk = inv.get("week") or {}
    tot = {n: float(wk[key]) if wk.get(key) is not None else sum(ser[n]) for n, key in GROUPS}
    steady = {n: n_days >= 3 and (all(x > 0 for x in ser[n]) or all(x < 0 for x in ser[n])) for n in GNAMES}
    S = min(GNAMES, key=lambda n: tot[n])
    B = max(GNAMES, key=lambda n: tot[n])
    flips = {n: _split(ser[n], days) for n in MAIN3}
    fl = [(n, f) for n, f in flips.items() if f]
    G = max(fl, key=lambda x: (x[1]["score"], -MAIN3.index(x[0])))[0] if fl else None
    opposite = n_days >= 2 and all(ser[n][0] * ser[n][-1] < 0 and abs(ser[n][0]) >= NEUTRAL and abs(ser[n][-1]) >= NEUTRAL for n in MAIN3)

    th = w.get("themes") or {}
    tweek = []
    for t in th.get("week") or []:
        dm = {str(x["d"]): float(x.get("net") or 0) for x in t.get("days") or []}
        tweek.append(dict(t, vals=[dm.get(d, 0.0) for d in days]))
    rev = None
    for t in tweek:
        sp = _split(t["vals"], days)
        if sp and (rev is None or sp["score"] > rev["score"]):
            rev = dict(sp, theme=t["theme"], net=float(t.get("net") or sum(t["vals"])))
    stayed = [t for nm in (th.get("stayed") or []) if nm != (rev or {}).get("theme") for t in tweek if t["theme"] == nm]
    stayed.sort(key=lambda t: (-int(t.get("pos_days") or sum(1 for v in t["vals"] if v > 0)), -(t.get("net") or 0)))
    top_out = th.get("top_out") or (min(tweek, key=lambda t: t.get("net") or 0) if tweek else None)

    os_ = w.get("others_stocks") or {}
    ostk = [x for x in os_.get("week") or [] if (x.get("v") or 0) > 0]
    covered = [str(x["d"]) for x in os_.get("days") or [] if x.get("top")]
    share = os_.get("buyback_share")
    ws, we = f"{days[0][:4]}-{days[0][4:6]}-{days[0][6:]}", f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}"
    progs = {p["code"]: p for p in (w.get("buybacks") or []) if p.get("from", "") <= we and p.get("to", "9999") >= ws}
    top2 = ostk[:2]
    bb = [x for x in top2 if x.get("code") in progs]
    if share is None and ostk and tot["기타법인"] > 0:
        share = sum(x["v"] for x in ostk if x.get("code") in progs) / tot["기타법인"]
    bb_ok = bool(bb) and (share or 0) >= 0.5 and tot["기타법인"] >= 10000 and len(bb) == len(top2)

    return {
        "days": days, "n_days": n_days, "N": DAYN.get(n_days, f"{n_days}일"), "kd": kd, "prev_close": prev_close, "C": C or 0.0,
        "events": _line_events(kd, prev_close, k.get("events")), "ser": ser, "tot": tot, "steady": steady,
        "S": S, "B": B, "flips": flips, "G": G, "opposite": opposite,
        "tweek": tweek, "rev": rev, "stayed": stayed, "top_out": top_out,
        "ostk": ostk, "covered": covered, "share": float(share or 0.0),
        "bb": bb if bb_ok else [], "bb_progs": [progs[x["code"]] for x in bb] if bb_ok else [],
        "bb_themes": {CODE_THEME.get(x["code"]) for x in bb}, "checks": _checks(w), "next_q": _next_q(w, inv.get("streak_end") or {}),
        "week_no": date(int(days[0][:4]), int(days[0][4:6]), int(days[0][6:])).isocalendar()[1],
    }


def hook_type(F: dict) -> str:
    S, B, tot = F["S"], F["B"], F["tot"]
    pair_ok = tot[S] <= -MIN_PART and tot[B] >= MIN_PART
    pair_sc = min(-tot[S], tot[B]) if pair_ok else 0
    G = F["G"]
    flip_sc = (abs(F["flips"][G]["early"]) + abs(F["flips"][G]["late"])) / 2 if G else 0
    if pair_ok and pair_sc >= flip_sc:
        return "pair"
    if G and flip_sc >= 10000:
        return "flip"
    return "pair" if pair_ok else "index"


def _flip_kw(F: dict, n: str) -> dict:
    f = F["flips"][n]
    e_buy = f["early"] > 0
    return {
        "early_span": span(f["early_days"]), "late_span": span(f["late_days"]), "early_span_en": span_en(f["early_days"]),
        "late_span_en": span_en(f["late_days"]), "late_start": wdn(f["late_days"][0]), "late_start_eul": obj(wdn(f["late_days"][0])),
        "early_n": DAYN.get(len(f["early_days"])), "late_n": DAYN.get(len(f["late_days"])),
        "E": amt(f["early"]), "E_eul": obj(amt(f["early"])), "L": amt(f["late"]), "L_eul": obj(amt(f["late"])),
        "e_word": "순매수" if e_buy else "순매도", "l_word": "순매도" if e_buy else "순매수",
        "e_past": "샀" if e_buy else "팔았", "l_past": "팔았" if e_buy else "샀", "e_did": "순매수한" if e_buy else "순매도한",
        "e_noun": "매수" if e_buy else "매도", "l_noun": "매도" if e_buy else "매수",
        "l_start_verb": "팔기" if e_buy else "사기",
    }


# ── 장면: 각 장면은 [(문장, slot)] — slot이 PRIO에 있으면 길이가 넘칠 때 뺄 수 있다 ──
def scene_w0(F: dict, pk: Picker, htype: str) -> tuple[list, list[str], set[str]]:
    S, B, tot, N, C = F["S"], F["B"], F["tot"], F["N"], F["C"]
    Cs = pc(C)
    said: set[str] = set()
    kw = {"S": S, "S_eun": eun(S), "S_iga": subj(S), "B": B, "B_eun": eun(B), "B_iga": subj(B),
          "X": amt(tot[S]), "X_eul": obj(amt(tot[S])), "X_ieot": ieot(amt(tot[S])), "Y": amt(tot[B]), "Y_eul": obj(amt(tot[B])),
          "Xs": amt_s(tot[S]), "Ys": amt_s(tot[B]), "N": N, "C": Cs}
    P = []
    if htype == "pair":
        said |= {S, B}
        bank = (["이번 주 {S_eun} {X_eul} 팔았고, {B_eun} {N} 내내 사서 {Y_eul} 순매수했습니다.",
                 "한 주 동안 {S} 순매도는 {X}, {N} 내내 산 {B} 순매수는 {Y}입니다.",
                 "{S_iga} 이번 주 판 돈은 {X}, 그 {N} 동안 하루도 쉬지 않고 산 {B} 돈은 {Y}입니다.",
                 "이번 주 {S} 순매도는 {X_ieot}고, {B_eun} 매일 사서 {Y_eul} 순매수했습니다."] if F["steady"][B] else
                ["이번 주 {S_eun} {X_eul} 팔았고, {B_eun} {Y_eul} 순매수했습니다.",
                 "한 주 동안 {S} 순매도는 {X}, {B} 순매수는 {Y}입니다.",
                 "{S_iga} 이번 주 판 돈은 {X}, 그 사이 {B_iga} 사들인 돈은 {Y}입니다."])
        P.append((pk("w0.lead", bank, **kw), "w0.lead"))
        line1 = pk("hook.l1", ["{S} {Xs} 팔 때 {B} {Ys} 샀다", "{S} {Xs} 팔고 {B} {Ys} 샀다", "한 주 {S} {Xs} 순매도, {B} {Ys} 순매수"], **kw)
    elif htype == "flip":
        G = F["G"]
        said.add(G)
        kw.update(_flip_kw(F, G), G=G, G_eun=eun(G), Es=amt_s(F["flips"][G]["early"]), Ls=amt_s(F["flips"][G]["late"]))
        P.append((pk("w0.lead", [
            "{G_eun} {early_span} {E_eul} {e_word}했습니다. 그런데 {late_start}부터는 {late_n} 동안 {L_eul} {l_word}했습니다.",
            "{early_span}만 해도 {G_eun} {E_eul} {e_past}습니다. {late_start}부터는 달랐습니다. {late_n} 동안 {L_eul} {l_past}습니다.",
            "{G_eun} 이번 주 도중에 방향을 바꿨습니다. {early_span} {E_eul} {e_word}했고, {late_start}부터 {L_eul} {l_word}했습니다."], **kw),
            "w0.lead"))
        line1 = pk("hook.l1", ["{G} {Es} {e_word} 뒤 {Ls} {l_word}", "{G}, {early_n} {e_word} 뒤 {late_n} {l_word}",
                               "{G} 한 주 새 {e_word} {Es}, {l_word} {Ls}"], **kw)
    else:
        P.append((pk("w0.lead", ["코스피가 이번 주 {C} {v}습니다.", "이번 주 코스피는 {C} {v}습니다.", "한 주 동안 코스피는 {C} {v}습니다."],
                      C=Cs, v="올랐" if C > 0 else "내렸"), "w0.lead"))
        line1 = pk("hook.l1", ["코스피 한 주 {C} {w}", "이번 주 코스피 {C} {w}", "한 주 새 코스피 {C} {w}"], C=Cs, w="상승" if C > 0 else "하락")

    if htype != "index":
        if abs(C) < 0.3:
            bank = ["그 사이 코스피는 {C} {v}습니다.", "코스피는 주간으로 {C} {v}습니다.", "코스피는 닷새를 합쳐 {C} {v}습니다.".replace("닷새", N)]
        elif C > 0 and tot[S] < 0:
            bank = ["코스피는 오히려 {C} {v}습니다.", "그런데도 코스피는 {C} {v}습니다.", "그래도 코스피는 {C} {v}습니다."]
        elif C > 0:
            bank = ["코스피도 {C} {v}습니다.", "코스피는 주간으로 {C} {v}습니다.", "그 사이 코스피는 {C} {v}습니다."]
        else:
            bank = ["그런데도 코스피는 {C} {v}습니다.", "코스피는 그 사이 {C} {v}습니다.", "그래도 코스피는 {C} 밀렸습니다."]
        P.append((pk("w0.idx", bank, C=Cs, v="올랐" if C > 0 else "내렸"), "w0.idx"))
    if abs(C) < 0.3:
        qb = [("그 사이 어디까지 올랐다가 어디까지 밀렸을까요?", "코스피는 어디까지 갔나?"),
              ("그렇게 사고파는 동안, 지수는 어디까지 흔들렸을까요?", "코스피는 어디까지 흔들렸나?"),
              ("이 {N}, 지수의 위아래는 어디였을까요?", "한 주의 고점과 저점은?")]
    elif C > 0:
        qb = [("이 상승은 {N} 중 언제 나왔을까요?", "{C} 상승, 언제 나왔나?"),
              ("이 {C}, 어느 날 나왔을까요?", "{C}는 어느 날 나왔나?"),
              ("코스피가 오른 건 {N} 중 어느 날이었을까요?", "오른 날은 언제였나?")]
    else:
        qb = [("이 하락은 {N} 중 언제 나왔을까요?", "{C} 하락, 언제 나왔나?"),
              ("이 {C}, 어느 날 빠졌을까요?", "{C}는 어느 날 빠졌나?"),
              ("코스피가 밀린 건 {N} 중 어느 날이었을까요?", "밀린 날은 언제였나?")]
    q, line2 = pk("w0.q", qb, question=True, N=N, C=Cs)
    P.append((q, "w0.q"))
    return P, [line1, line2], said


def scene_w1(F: dict, pk: Picker) -> list:
    kd, C, N, n = F["kd"], F["C"], F["N"], F["n_days"]
    chg = [x["chg_pct"] for x in kd]
    P = []
    di, decisive = None, False
    if abs(C) < 0.3:
        hi_i = max(range(len(kd)), key=lambda i: kd[i]["high"])
        lo_i = min(range(len(kd)), key=lambda i: kd[i]["low"])
        kwf = {"C": pc(C), "v": "올랐" if C > 0 else "내렸", "hi_wd": wdn(kd[hi_i]["d"]), "hi": band(kd[hi_i]["high"]),
               "lo_wd": wdn(kd[lo_i]["d"]), "lo": band(kd[lo_i]["low"]), "lo_ieot": ieot(band(kd[lo_i]["low"]))}
        P.append((pk("w1.open", ["위로는 {hi_wd} 장중 {hi}까지, 아래로는 {lo_wd} {lo}까지였습니다. 그러고도 한 주로는 {C} {v}습니다.",
                                 "{hi_wd}엔 장중 {hi}까지 올랐고, {lo_wd}엔 {lo}까지 밀렸습니다. 끝만 보면 {C} {v}습니다.",
                                 "고점은 {hi_wd} 장중 {hi}, 저점은 {lo_wd} {lo_ieot}습니다. 종가만 이으면 {C} {v}습니다."], **kwf), "w1.open"))
    else:
        up = C > 0
        di = max(range(len(chg)), key=lambda i: chg[i]) if up else min(range(len(chg)), key=lambda i: chg[i])
        decisive = (up and chg[di] > C) or ((not up) and chg[di] < C)
        kw = {"wd": wdn(kd[di]["d"]), "wd_ieot": ieot(wdn(kd[di]["d"])), "x": pc(chg[di]), "C": pc(C), "rest_n": DAYN.get(n - 1, f"{n - 1}일"),
              "N": N, "k_n": DAYN.get(sum(1 for x in chg if x != 0 and (x > 0) == up), "")}
        if decisive:
            bank = (["{wd_ieot}습니다. 그날 하루에만 {x} 올랐고, 나머지 {rest_n}은 합치면 오히려 내렸습니다.",
                     "답은 {wd}입니다. {wd} 하루 상승 폭이 {x}로, 한 주 전체 {C}보다 컸습니다.",
                     "거의 {wd} 하루에 다 나왔습니다. {wd}에만 {x} 올랐고, 남은 {rest_n}은 더하면 오히려 내렸습니다."] if up else
                    ["{wd_ieot}습니다. 그날 하루에만 {x} 내렸고, 나머지 {rest_n}은 합치면 오히려 올랐습니다.",
                     "답은 {wd}입니다. {wd} 하루 하락 폭이 {x}로, 한 주 전체 {C}보다 컸습니다.",
                     "거의 {wd} 하루에 다 나왔습니다. {wd}에만 {x} 내렸고, 남은 {rest_n}은 더하면 오히려 올랐습니다."])
        else:
            bank = (["하루에 몰리지 않았습니다. {N} 중 {k_n}이 올랐고, 가장 크게 오른 {wd}도 {x}였습니다.",
                     "조금씩 쌓였습니다. 오른 날이 {k_n}이었고, 하루 최대 상승은 {wd}의 {x}였습니다.",
                     "한 번에 나오지 않았습니다. {N} 가운데 {k_n}이 올랐고, 가장 큰 날은 {wd} {x}였습니다."] if up else
                    ["하루에 몰리지 않았습니다. {N} 중 {k_n}이 내렸고, 가장 크게 내린 {wd}도 {x}였습니다.",
                     "조금씩 밀렸습니다. 내린 날이 {k_n}이었고, 하루 최대 하락은 {wd}의 {x}였습니다.",
                     "한 번에 빠지지 않았습니다. {N} 가운데 {k_n}이 내렸고, 가장 큰 날은 {wd} {x}였습니다."])
        P.append((pk("w1.open", bank, **kw), "w1.open"))
        L0 = F["events"][0]["line"] if F["events"] else None
        if decisive and L0 and kd[di]["close"] < L0 and (L0 - kd[di]["close"]) / L0 < 0.002:
            P.append((pk("w1.near", ["그날 종가는 {L} 바로 아래였습니다.", "그날은 {L_eul} 코앞에 두고 멈췄습니다.", "그날 종가는 {L}에 조금 못 미쳤습니다."],
                          L=f"{L0:,}선", L_eul=obj(f"{L0:,}선")), "w1.near"))

    # 천 단위 선을 넘나든 날: 종가로 넘은 날(regained/lost)은 필수, 장중에만 넘나든 날(touched/held)은 길이가 넘치면 뺀다.
    # 필수 문장끼리는 '그 선'으로 이어 받고(뺄 수 있는 문장은 선을 직접 말함), 마지막 날 절은 종가와 한 문장으로 잇는다.
    B_EV = {
        "touched": ["{wd}엔 장중 {hi_eul} 넘었다가 {Lw} 아래에서 끝났습니다.", "{wd}엔 장중 {hi}까지 올랐지만, 종가는 {Lw} 밑이었습니다.",
                    "{wd}엔 장중 {hi} 위까지 갔다가 {Lw} 아래로 밀려났습니다."],
        "regained": ["{wd}엔 {nd}{Lw} 위로 올라섰습니다.", "{wd}엔 {nd}{Lw} 위에서 장을 마쳤습니다.", "{wd}엔 {nd}{Lw_eul} 넘어 끝났습니다."],
        "held": ["{wd}엔 장중 {Lw} 아래로 밀렸다가도 그 위에서 버텼습니다.", "{wd}엔 장중 한때 {Lw} 밑으로 내려갔지만, 종가는 다시 그 위였습니다.",
                 "{wd}엔 장중 흔들렸어도 {Lw} 위를 지켜 냈습니다."],
        "lost": ["{wd}엔 다시 {Lw} 아래로 내려왔습니다.", "{wd}엔 {Lw} 밑으로 다시 밀렸습니다.", "{wd}엔 {Lw} 아래로 되돌아갔습니다."],
    }
    last = kd[-1]
    cl = pk("w1.close", ["코스피는 {cl}에서 한 주를 마쳤습니다.", "한 주의 마지막 종가는 {cl_ieot}습니다.", "그렇게 {cl}에서 한 주가 끝났습니다."],
            cl=band(last["close"]), cl_ieot=ieot(band(last["close"])))
    evs = list(F["events"])
    if any(e["kind"] in ("regained", "lost") for e in evs):
        evs = [e for e in evs if e["kind"] in ("regained", "lost") or e["kind"] == "touched" and len(evs) <= 4 or len(evs) <= 2]
    prev_kind, mentioned, closed = None, False, False
    for e in evs:
        must = e["kind"] in ("regained", "lost") or len(evs) <= 1
        Lw = "그 선" if (mentioned and must) else f"{e['line']:,}선"
        mentioned |= must
        hi = band(e["high"]) if int(e["high"] // 100 * 100) > e["line"] else f"{e['line']:,}선"
        s = pk(f"w1.{e['kind']}", B_EV[e["kind"]], wd=wdn(e["d"]), Lw=Lw, Lw_eul=obj(Lw), hi=hi, hi_eul=obj(hi),
               nd=f"{e['n_days']}거래일 만에 " if e.get("n_days") else "")
        if e["kind"] == "lost" and prev_kind in ("regained", "held"):
            s = "하지만 " + s
        if e["d"] == last["d"] and s.endswith("습니다."):
            s, closed = s[:-4] + "고, " + cl, True
        P.append((s, "w1.path" if must or e["d"] == last["d"] else f"w1.{e['kind']}"))
        if must:
            prev_kind = e["kind"]
    if not closed:
        P.append((cl, "w1.close"))
    return P


def scene_w2(F: dict, pk: Picker, said: set[str], htype: str) -> list:
    ser, tot, N, days = F["ser"], F["tot"], F["N"], F["days"]
    G = F["G"]
    P = []
    first_wd, last_wd = wdn(days[0]), wdn(days[-1])
    if F["opposite"]:
        who = lambda i, s: _and([n for n in MAIN3 if ser[n][i] * s > 0])  # noqa: E731
        kw = {"first_wd": first_wd, "first_wd_wa": wa(first_wd), "last_wd": last_wd, "N": N, "b1": who(0, 1), "b5_ieot": ieot(who(-1, 1)),
              "b1_iga": subj(who(0, 1)), "s1_iga": subj(who(0, -1)), "b5_iga": subj(who(-1, 1)), "s5_iga": subj(who(-1, -1))}
        P.append((pk("w2.q", ["그런데 {first_wd}에 산 쪽이 {last_wd}에도 샀을까요?", "{first_wd_wa} {last_wd}, 사고판 쪽은 같았을까요?",
                              "이 {N} 사이, 사는 쪽과 파는 쪽은 그대로였을까요?"], question=True, **kw), "w2.q"))
        P.append((pk("w2.a", ["정반대였습니다.", "완전히 뒤집혔습니다.", "거꾸로였습니다."]), "w2.a"))
        P.append((pk("w2.opp", ["{first_wd}엔 {b1_iga} 사고 {s1_iga} 팔았는데, {last_wd}엔 {b5_iga} 사고 {s5_iga} 팔았습니다.",
                                "{first_wd}엔 {s1_iga} 팔고 {b1_iga} 샀는데, {last_wd}엔 {s5_iga} 팔고 {b5_iga} 샀습니다.",
                                "{first_wd}에 사던 {b1_iga} {last_wd}엔 팔았고, {first_wd}에 팔던 {s1_iga} {last_wd}엔 샀습니다.",
                                "{first_wd}의 사는 쪽은 {b1}, {last_wd}의 사는 쪽은 {b5_ieot}습니다."], **kw), "w2.opp"))
    elif G and htype != "flip":
        P.append((pk("w2.q", ["이 {N} 동안 {G_eun} 한 방향이었을까요?", "{G}의 방향은 {N} 내내 같았을까요?", "그 사이 {G_eun} 줄곧 같은 쪽이었을까요?"],
                      question=True, N=N, G=G, G_eun=eun(G)), "w2.q"))
        P.append((pk("w2.a", ["아니었습니다.", "그렇지 않았습니다.", "중간에 바뀌었습니다."]), "w2.a"))
    else:
        pending = [n for n in GNAMES if n not in said and abs(tot[n]) >= MIN_PART]
        if not pending:
            return []                      # 말할 합계가 없으면 장면을 통째로 뺀다(질문만 남기지 않음)
        if htype == "flip":
            P.append((pk("w2.q", ["{G_iga} 방향을 바꾸는 사이, 다른 주체들은 어땠을까요?", "그 사이 나머지 주체들의 한 주는 어땠을까요?",
                                  "{G} 말고 다른 쪽은 한 주 동안 어떻게 움직였을까요?"], question=True, G=G, G_iga=subj(G)), "w2.q"))
        else:
            P.append((pk("w2.q", ["이 {N} 동안 사고판 쪽은 한결같았을까요?", "{N} 내내 같은 쪽이 샀을까요?", "사는 쪽과 파는 쪽은 {N} 내내 그대로였을까요?"],
                          question=True, N=N), "w2.q"))
            P.append((pk("w2.a", ["대체로 그랬습니다.", "크게 바뀌지 않았습니다.", "방향은 거의 그대로였습니다."]), "w2.a"))
    if G and htype != "flip":
        kw = _flip_kw(F, G)
        kw.update(G=G, G_eun=eun(G))
        P.append((pk("w2.flip", [
            "{G_eun} {early_span} {E_eul} {e_word}했다가, {late_start}부터 {late_n} 동안 {L_eul} {l_word}했습니다.",
            "{G}만 보면 {early_span_en} {E_eul} {e_past}고, {late_start}부터 {late_n} 동안 {L_eul} {l_past}습니다.",
            "{G_eun} {early_span} {E_eul} {e_did} 뒤, {late_start}부터 {late_n} 동안 {L_eul} {l_past}습니다."], **kw), "w2.flip"))
    # 한 주 합계: 훅에서 말하지 않은 주체만(방향을 바꾼 주체 먼저), 두 명까지 한 문장에
    rest = [n for n in ([G] if G else []) + [x for x in ("외국인", "기관", "개인", "기타법인") if x != G]
            if n and n not in said and abs(tot[n]) >= MIN_PART][:2]
    if rest:
        ws = [(n, amt(tot[n]), "순매수" if tot[n] > 0 else "순매도") for n in rest]
        if len(ws) == 2:
            (a, Wa, wa_), (b, Wb, wb_) = ws
            P.append((pk("w2.total2", ["한 주로는 {a} {Wa} {wa}, {b} {Wb} {wb}입니다.", "{N_eul} 더하면 {a_eun} {Wa} {wa}, {b_eun} {Wb} {wb_ieot}습니다.",
                                       "한 주 합계는 {a} {Wa} {wa}, {b} {Wb} {wb_ro} 끝났습니다."],
                          a=a, a_eun=eun(a), Wa=Wa, wa=wa_, b=b, b_eun=eun(b), Wb=Wb, wb=wb_, wb_ieot=ieot(wb_), wb_ro=ro(wb_), N_eul=obj(N)), "w2.total"))
        else:
            (a, Wa, wa_), = ws
            P.append((pk("w2.total1", ["한 주로는 {a} {Wa} {wa}입니다.", "{N_eul} 더하면 {a_eun} {Wa} {wa_ieot}습니다.", "한 주 합계는 {a} {Wa} {wa_ro} 끝났습니다."],
                          a=a, a_eun=eun(a), Wa=Wa, wa=wa_, wa_ieot=ieot(wa_), wa_ro=ro(wa_), N_eul=obj(N)), "w2.total"))
        said |= set(rest)
    return P


def scene_w3(F: dict, pk: Picker) -> list:
    P = []
    rev, N = F["rev"], F["N"]
    if rev:
        R = rev["theme"]
        e_in = rev["early"] > 0
        kw = {"R": R, "R_ieot": ieot(R), "R_en": R + "엔", "early_span": span(rev["early_days"]), "late_span": span(rev["late_days"]),
              "early_span_en": span_en(rev["early_days"]), "late_span_en": span_en(rev["late_days"]),
              "late_start": wdn(rev["late_days"][0]), "late_n": DAYN.get(len(rev["late_days"])),
              "E": amt(rev["early"]), "E_iga": subj(amt(rev["early"])), "L": amt(rev["late"]), "L_iga": subj(amt(rev["late"]))}
        kw.update(early_n=DAYN.get(len(rev["early_days"])))
        P.append((pk("w3.q", ["{late_start}부터 {moved} 돈은 어느 테마였을까요?", "이 돈은 어느 테마에서 크게 움직였을까요?",
                              "테마로 보면, 돈이 크게 {inout} 곳은 어디였을까요?"], question=True, moved="빠진" if e_in else "들어온",
                     inout="들어왔다 나간" if e_in else "나갔다 들어온", **kw), "w3.q"))
        P.append((pk("w3.a", ["{R_ieot}습니다.", "{R} 쪽이었습니다.", "바로 {R}입니다."], **kw), "w3.a"))
        P.append((pk("w3.rev_in" if e_in else "w3.rev_out", [
            "외국인과 기관 몫으로 {early_n} 동안 {E_iga} 들어왔다가, 이후 {late_n} 동안 {L_iga} 빠졌습니다.",
            "외국인과 기관 합계로 앞의 {early_n}은 {E_iga} 들어왔고, 뒤의 {late_n}은 {L_iga} 나갔습니다.",
            "외국인과 기관이 {R}에 넣은 돈은 {early_n} {E}, 이후 {late_n} 뺀 돈은 {L}입니다."] if e_in else [
            "외국인과 기관 몫으로 {early_n} 동안 {E_iga} 빠졌다가, 이후 {late_n} 동안 {L_iga} 들어왔습니다.",
            "외국인과 기관 합계로 앞의 {early_n}은 {E_iga} 나갔고, 뒤의 {late_n}은 {L_iga} 들어왔습니다.",
            "외국인과 기관이 {R}에서 뺀 돈은 {early_n} {E}, 이후 {late_n} 넣은 돈은 {L}입니다."], **kw), "w3.rev"))
    elif F["top_out"] and (F["top_out"].get("net") or 0) <= -3000:
        to = F["top_out"]
        kw = {"TO": to["theme"], "TO_ieot": ieot(to["theme"]), "net": amt(to["net"]), "net_iga": subj(amt(to["net"])), "N": N}
        P.append((pk("w3.q", ["그럼 이 {N} 동안 돈이 가장 크게 나간 테마는 어디였을까요?", "이 돈은 어느 테마에서 가장 많이 나갔을까요?",
                              "한 주 합계로 보면, 돈은 어디서 가장 많이 빠졌을까요?"], question=True, **kw), "w3.q"))
        P.append((pk("w3.top_out", ["{TO_ieot}습니다. 외국인과 기관 몫으로 한 주 {net_iga} 빠졌습니다.",
                                    "{TO}에서 외국인과 기관 몫으로 한 주 {net_iga} 나갔습니다.",
                                    "{TO}입니다. 한 주 동안 외국인과 기관이 {net_eul} 뺐습니다."], net_eul=obj(amt(to["net"])), **kw), "w3.rev"))
    st = F["stayed"][:2]
    if st:
        pdays = [int(t.get("pos_days") or sum(1 for v in t["vals"] if v > 0)) for t in st]
        cnt = f"{N} 내내" if min(pdays) >= F["n_days"] else f"{N} 중 {DAYN.get(min(pdays))}"
        names = _and([t["theme"] for t in st])
        P.append((pk("w3.stay", ["반면 {cnt} 순매수가 들어온 곳은 {names_ieot}습니다.", "끝까지 돈이 머문 쪽은 {names_ieot}습니다. {cnt} 순매수였습니다.",
                                 "{names_en} {cnt} 순매수가 들어왔습니다."], names=names, names_ieot=ieot(names), names_en=names + "엔", cnt=cnt), "w3.stay"))
        fnet = float(st[0].get("net") or sum(st[0]["vals"]))
        if 0 < fnet < 3000:
            f0 = st[0]["theme"]
            P.append((pk("w3.stay_small", ["다만 {f0}도 한 주 합계가 {fnet_ira} 금액은 크지 않았습니다.", "다만 한 주 합계는 {f0_iga} {fnet_ro} 크지 않았습니다.",
                                           "금액으로는 {f0}도 {fnet}에 그쳤습니다."],
                          f0=f0, f0_iga=subj(f0), fnet=amt(fnet), fnet_ira=ira(amt(fnet)), fnet_ro=ro(amt(fnet))), "w3.stay_small"))
    if F["bb"]:
        bb = F["bb"]
        names = _and([x["name"] for x in bb])
        most = "대부분" if F["share"] >= 0.6 else "절반 이상"
        scope = f"종목별 숫자가 있는 {span(F['covered'])}만 보면, " if F["covered"] and len(F["covered"]) < F["n_days"] else ""
        m0 = min(int(p["from"][5:7]) for p in F["bb_progs"])
        two = len(bb) == 2
        kw = {"N": N, "Y_eun": eun(amt(F["tot"]["기타법인"])), "names": names, "names_ieot": ieot(names), "names_iga": subj(names),
              "most": most, "most_iga": subj(most), "scope": scope, "M": m0, "who": "두 회사" if two else bb[0]["name"],
              "who_all": "두 회사 모두" if two else eun(bb[0]["name"]), "whose": "두 회사의" if two else bb[0]["name"] + "의"}
        steady_o = F["steady"]["기타법인"] and F["tot"]["기타법인"] > 0
        P.append((pk("w3.bq", ["{N} 내내 산 기타법인은 무엇을 샀을까요?" if steady_o else "기타법인은 무엇을 샀을까요?",
                               "기타법인이 산 종목은 어디였을까요?", "그럼 기타법인은 어느 종목을 샀을까요?"], question=True, **kw), "w3.bq"))
        P.append((pk("w3.ba", ["{scope}{most} {names_ieot}습니다.", "{scope}{names_iga} {most}이었습니다.", "{scope}{most_iga} {names}에 들어갔습니다."], **kw), "w3.ba"))
        P.append((pk("w3.concl", ["{who}가 {M}월부터 해 온 자사주 매입이 기타법인으로 잡힌 것으로 보입니다.",
                                  "자사주 매입은 기타법인으로 집계되는데, {who_all} {M}월부터 매입 중이라 {most} 자사주 매입으로 풀이됩니다.",
                                  "{M}월부터 이어진 {whose} 자사주 매입이 기타법인 순매수로 찍힌 것으로 볼 수 있습니다."], **kw), "w3.concl"))
        if rev and rev["early"] > 0 and rev["theme"] in F["bb_themes"]:
            R = rev["theme"]
            P.append((pk("w3.link", ["외국인과 기관이 {R}에서 돈을 빼는 동안, 같은 {R} 종목을 회사들이 사들인 셈입니다.",
                                     "{late_start}부터 {R}에서 돈이 빠지는 동안에도, 그 {R} 종목을 회사들은 계속 사들인 셈입니다.",
                                     "{R}에서 빠진 외국인과 기관의 돈 맞은편에, 자사주를 사는 회사들이 있었던 셈입니다."],
                          R=R, late_start=wdn(rev["late_days"][0])), "w3.link"))
    return P


def scene_w4(F: dict, pk: Picker, events: list[dict]) -> list:
    if not events:
        return []
    # 뉴스와 나란히 놓을 주체: 방향을 바꾼 주체가 외국인·기관이면 그쪽, 아니면 외국인·기관 중 한 주 금액이 큰 쪽
    ser, tot = F["ser"], F["tot"]
    G = F["G"] if F["G"] in ("외국인", "기관") else None
    actor_default = G or max(("외국인", "기관"), key=lambda n: abs(tot[n]))
    story_buy = (F["flips"][G]["late"] > 0) if G else tot[actor_default] > 0
    di = {d: i for i, d in enumerate(F["days"])}
    late = set(F["flips"][G]["late_days"]) if G else set()
    weight = lambda e: (e["d"] in late, e["rel"], abs(ser[e.get("who") or actor_default][di[e["d"]]]))  # noqa: E731
    chosen = sorted(sorted(events, key=weight, reverse=True)[:MAX_NEWS], key=lambda e: e["d"])
    P = []
    if G:
        P.append((pk("w4.q", ["{G_iga} {l_start_verb} 시작한 뒤, 어떤 소식들이 있었을까요?", "그 사이 기사엔 어떤 소식이 올랐을까요?",
                              "그 {late_n} 동안 시장엔 무슨 일이 있었을까요?"], question=True, G_iga=subj(G), late_n=DAYN.get(len(F["flips"][G]["late_days"])),
                     l_start_verb="사기" if story_buy else "팔기"), "w4.q"))
    else:
        P.append((pk("w4.q", ["이 {N} 동안 어떤 소식들이 있었을까요?", "그 사이 기사엔 어떤 소식이 올랐을까요?", "이 {N}, 시장엔 무슨 일이 있었을까요?"],
                      question=True, N=F["N"]), "w4.q"))
    signs, said_ev = [], []
    for j, e in enumerate(chosen):
        a = e.get("who") or actor_default
        v = ser[a][di[e["d"]]]
        label = e["label"]
        kw = {"wd": wdn(e["d"]), "wd_eun": eun(wdn(e["d"])), "label": label, "label_iga": subj(label), "label_ieot": ieot(label),
              "actor": a, "actor_eun": eun(a), "amt": amt(v), "amt_eul": obj(amt(v)), "amt_ieot": ieot(amt(v)), "verb": "순매수" if v > 0 else "순매도"}
        if abs(v) < NEUTRAL:
            P.append((pk(f"w4.ev_small{j}", ["{wd}엔 {label_iga} 있었습니다.", "{wd} 기사엔 {label_iga} 등장했습니다.", "{label} 소식은 {wd}에 나왔습니다."], **kw),
                      "w4.ev"))
            continue
        signs.append(v > 0)
        if label.endswith("날"):
            bank = ["{wd_eun} {label_ieot}고, 그날 {actor} {verb}는 {amt_ieot}습니다.",
                    "{wd}엔 {label_iga} 있었고, 같은 날 {actor_eun} {amt_eul} {verb}했습니다.",
                    "{label_iga} 겹친 {wd}, {actor_eun} {amt_eul} {verb}했습니다."]
        elif label.endswith(_DAY_LIKE):
            bank = ["{wd}엔 {label_iga} 있었고, 같은 날 {actor_eun} {amt_eul} {verb}했습니다.",
                    "{label_iga} 나온 {wd}, {actor_eun} {amt_eul} {verb}했습니다.",
                    "{wd}엔 {label_iga} 나왔고, 그날 {actor} {verb}는 {amt_ieot}습니다."]
        else:
            bank = ["{wd} 기사엔 {label_iga} 등장했고, 같은 날 {actor_eun} {amt_eul} {verb}했습니다.",
                    "{wd}엔 {label} 이야기가 나왔고, 그날 {actor} {verb}는 {amt_ieot}습니다.",
                    "{label_iga} 기사에 오른 {wd}, {actor_eun} {amt_eul} {verb}했습니다."]
        said_ev.append(pk(f"w4.ev{j}", bank, unlike=tuple(said_ev), **kw))
        P.append((said_ev[-1], "w4.ev"))
    if not signs:
        return P
    these = "이 소식들" if len(signs) > 1 else "이 소식"
    if all(s == story_buy for s in signs) and not any(e.get("who") for e in chosen):
        A = actor_default
        word = "순매수" if story_buy else "순매도"
        P.append((pk("w4.close_link", ["{A} {word_iga} {these}과 날짜가 겹친 만큼, 그 배경 가운데 하나로 볼 수 있습니다.",
                                       "{A} {word_eun} {these}과 겹쳤고, 그 소식이 매매에 섞였을 수 있습니다.",
                                       "{A} {word_iga} {these}과 맞물린 것으로 풀이됩니다."],
                      A=A, word_iga=subj(word), word_eun=eun(word), these=these), "w4.close"))
    else:
        P.append((pk("w4.close", ["소식과 매매가 같은 날 겹쳤다는 점까지만 숫자로 확인됩니다.",
                                  "어느 소식이 어느 매매로 이어졌는지는, 날짜가 겹쳤다는 것 이상으로 말하기 어렵습니다.",
                                  "소식이 나온 날과 수급이 움직인 날이 겹친 것으로 볼 수 있지만, 그 이상은 숫자로 가를 수 없습니다."]), "w4.close"))
    return P


def scene_w5(F: dict, pk: Picker, htype: str) -> list:
    G, S, B, tot = F["G"], F["S"], F["B"], F["tot"]
    steadyB = B if (F["steady"][B] and tot[B] > 0) else None
    P = []
    if G and steadyB and steadyB != G:
        kw = _flip_kw(F, G)
        kw.update(G=G, G_ieot=ieot(G), G_iga=subj(G), B=steadyB, B_ieot=ieot(steadyB), B_iga=subj(steadyB), B_eun=eun(steadyB), N=F["N"],
                  early_n_ro=ro(DAYN.get(len(F["flips"][G]["early_days"]))))
        P.append((pk("w5.syn", ["{G}의 {e_noun}는 {early_n_ro} 끝났고, {B}의 매수는 {N} 내내 이어졌습니다.",
                                "한 줄로 줄이면, 방향을 바꾼 건 {G_ieot}고 끝까지 같은 쪽에 선 건 {B_ieot}습니다.",
                                "이번 주는 {G_iga} 돌아서는 동안, {B_eun} 한 번도 멈추지 않은 한 주였습니다."], **kw), "w5.syn"))
    elif G:
        kw = _flip_kw(F, G)
        kw.update(G=G, G_iga=subj(G), late_n_ieot=ieot(DAYN.get(len(F["flips"][G]["late_days"]))))
        P.append((pk("w5.syn", ["이번 주는 {G_iga} {late_start_eul} 기점으로 돌아선 한 주였습니다.",
                                "한 줄로 줄이면, {G}의 방향이 {late_start}에 바뀐 한 주였습니다.",
                                "{G}의 {e_noun}는 {early_n}, {l_noun}는 {late_n_ieot}습니다."], **kw), "w5.syn"))
    elif htype == "pair":
        P.append((pk("w5.syn", ["{S_iga} 판 물량을 {B_iga} 받아 낸 한 주였습니다.", "한 줄로 줄이면, 파는 쪽은 {S}, 받는 쪽은 {B_ieot}습니다.",
                                "이번 주 물량은 {S}에서 {B_ro} 넘어갔습니다."], S=S, S_iga=subj(S), B=B, B_iga=subj(B), B_ieot=ieot(B), B_ro=ro(B)), "w5.syn"))
    else:
        P.append((pk("w5.syn", ["주체마다 방향이 엇갈린 한 주였습니다.", "사는 쪽과 파는 쪽이 날마다 달랐던 한 주였습니다.",
                                "한 줄로 줄이면, 어느 한쪽이 끌고 간 한 주는 아니었습니다."]), "w5.syn"))
    g_late_sell = bool(G) and F["flips"][G]["late"] < 0
    if F["bb"] and g_late_sell:
        endm = max(int(p["to"][5:7]) for p in F["bb_progs"])
        P.append((pk("w5.mean", ["이 돈이 자사주 매입이라면, 매입 기간이 남은 {M}월까지는 {G_iga} 파는 날에도 받아 줄 쪽이 있다는 뜻일 수 있습니다.",
                                 "자사주 매입이 {M}월까지 이어지는 만큼, {G} 매도가 나와도 받아 낼 돈이 당분간 시장에 남아 있다고 볼 수 있습니다.",
                                 "매입 기간이 {M}월까지인 만큼, {G_iga} 파는 날의 맞은편 자리는 당분간 비지 않을 수 있습니다."],
                      M=endm, G=G, G_iga=subj(G)), "w5.mean"))
    elif g_late_sell:
        kw = _flip_kw(F, G)
        kw.update(G=G, G_iga=subj(G))
        P.append((pk("w5.mean", ["{G} 매도가 다음 주에도 이어지면, 이번 주 초의 매수는 짧게 끝난 것으로 볼 수 있습니다.",
                                 "{G}의 순매도가 주를 넘겨 이어진다면, 이번 주 초 매수는 한때였던 셈이 될 수 있습니다.",
                                 "다음 주 {G_iga} 다시 사는 쪽으로 오지 않는다면, 이번 주 초 매수는 {early_n}짜리였다고 볼 수 있습니다."], **kw), "w5.mean"))
    elif G:
        kw = _flip_kw(F, G)
        kw.update(G=G, G_iga=subj(G))
        P.append((pk("w5.mean", ["{G} 매수가 다음 주에도 이어지면, 방향이 바뀐 것으로 볼 수 있습니다.",
                                 "{G}의 순매수가 주를 넘겨 이어진다면, 이번 주가 방향이 바뀐 자리였다고 볼 수 있습니다.",
                                 "다음 주에도 {G_iga} 사는 쪽에 선다면, {late_start}가 방향이 바뀐 날로 남을 수 있습니다."], **kw), "w5.mean"))
    else:
        P.append((pk("w5.mean", ["사고파는 쪽이 이만큼 자주 바뀐 만큼, 방향을 하나로 정하기엔 이른 한 주로 볼 수 있습니다.",
                                 "주체마다 방향이 엇갈려, 한쪽으로 기울었다고 말하긴 어려운 한 주로 보입니다.",
                                 "받는 쪽이 있는 한 지수는 버틸 수 있지만, 그 돈이 계속될지는 다음 주 숫자로 확인할 부분입니다."]), "w5.mean"))
    return P


def scene_w6(F: dict, pk: Picker) -> list:
    P = []
    ch = F["checks"]
    if ch:
        n, k = len(ch), sum(1 for c in ch if c["ok"])
        oks = _and([c["item"] for c in ch if c["ok"]])
        fails = _and([c["item"] for c in ch if not c["ok"]])
        kw = {"n_cnt": CNT.get(n, f"{n}번"), "n_cnt_ieot": ieot(CNT.get(n, f"{n}번")), "k_cnt": CNT.get(k, f"{k}번"),
              "n_han": HAN.get(n, str(n)), "n_han_ieot": ieot(HAN.get(n, str(n))), "k_han_ieot": ieot(HAN.get(k, str(k))),
              "oks": oks, "oks_eun": eun(oks) if oks else "", "fails": fails, "fails_eun": eun(fails) if fails else ""}
        kw["n_han_eun"] = eun(HAN.get(n, str(n)))
        if k and k < n:
            P.append((pk("w6.rec", ["이번 주 걸어 둔 확인 {n_han} 중 이어진 건 {oks} {k_han_ieot}습니다.",
                                    "이번 주 다음 날 확인은 {n_cnt_ieot}고, 이어진 건 {oks}뿐이었습니다.",
                                    "이번 주 영상에서 다음 날 확인하자고 한 게 {n_cnt_ieot}고, 그중 {oks}만 이어졌습니다."], **kw), "w6.rec"))
            P.append((pk("w6.fails", ["{fails_eun} 끊겼습니다.", "{fails_eun} 거기서 멈췄습니다.", "나머지 {fails_eun} 이어지지 않았습니다."], **kw),
                      "w6.fails"))
        elif k == n:
            P.append((pk("w6.rec", ["이번 주 영상에서 다음 날 확인하자고 한 게 {n_cnt_ieot}고, {n_cnt} 다 이어졌습니다.",
                                    "이번 주 걸어 둔 확인 {n_han_eun} 모두 이어졌습니다. {oks}입니다.",
                                    "매일 하나씩 걸어 둔 확인이 이번 주엔 {n_cnt} 모두 이어졌습니다."], **kw), "w6.rec"))
        else:
            P.append((pk("w6.rec", ["이번 주 영상에서 다음 날 확인하자고 한 게 {n_cnt_ieot}고, 모두 끊겼습니다.",
                                    "이번 주 걸어 둔 확인 {n_han_eun} 모두 끊겼습니다. {fails}입니다.",
                                    "매일 하나씩 걸어 둔 확인이 이번 주엔 {n_cnt} 모두 끊겼습니다."], **kw), "w6.rec"))
        if n >= 2:
            theme_only = all(c["theme"] for c in ch)
            if k == 0:
                bank = ["걸어 둔 확인이 모두 끊겼다는 건, 돈이 한자리에 오래 있지 않은 한 주였다는 뜻으로 볼 수 있습니다.",
                        "하나도 이어지지 않은 만큼, 수급이 날마다 자리를 바꾼 한 주로 풀이됩니다.",
                        "모두 끊긴 만큼, 들어온 돈이 오래 자리를 지키지 않은 한 주로 볼 수 있습니다."]
            elif k / n <= 0.34 and theme_only:
                bank = ["걸어 둔 테마가 대부분 끊긴 만큼, 테마 돈이 자리를 자주 바꾼 한 주로 볼 수 있습니다.", "테마 쪽 돈은 자리를 자주 바꾼 한 주로 풀이됩니다.",
                        "끊긴 확인이 더 많았다는 건, 테마 돈이 쉽게 자리를 바꿨다는 뜻으로 볼 수 있습니다."]
            elif k / n <= 0.34:
                bank = ["걸어 둔 흐름이 하루를 넘기기 어려웠던 한 주로 볼 수 있습니다.", "수급이 날마다 방향을 바꾼 한 주로 풀이됩니다.",
                        "끊긴 확인이 더 많았다는 건, 돈의 방향이 짧게 바뀌었다는 뜻으로 볼 수 있습니다."]
            elif k == n:
                bank = ["걸어 둔 확인이 모두 이어졌다는 건, 들어온 돈이 자리를 지켰다는 뜻으로 볼 수 있습니다.",
                        "한번 잡힌 방향이 쉽게 꺾이지 않은 한 주로 풀이됩니다.", "이어진 확인이 많았다는 건, 수급의 방향이 오래 유지됐다는 뜻으로 볼 수 있습니다."]
            else:
                bank = ["이어진 것과 끊긴 것이 비슷해, 어느 쪽으로 기울었다고 보긴 어렵습니다.",
                        "반은 이어지고 반은 끊긴 한 주라, 흐름을 한 방향으로 묶기는 어렵습니다.", "이어진 확인과 끊긴 확인이 엇비슷한 한 주로 볼 수 있습니다."]
            P.append((pk("w6.mean", bank), "w6.mean"))
    q = F["next_q"]
    if q:
        P.append((pk("w6.next", ["다음 주엔 {q}부터 봅니다.", "다음 주 월요일엔 {q} 확인합니다.", "월요일 국장 마감에선 {q}부터 짚습니다."], q=q), "w6.next"))
        m = re.match(r"^(외국인|기관|개인) (순매수|순매도)가 (\S+)째 이어지는지$", q)
        if m:
            name, word, nth = m.groups()
            prev_n = {v: kk for kk, v in DAYN.items()}.get(nth)
            prev_txt = DAYN.get(prev_n - 1) if prev_n else None
            if prev_txt:
                noun = "매도" if word == "순매도" else "매수"
                P.append((pk("w6.cond", ["{nth}째로 이어지면 이번 {word}는 주를 넘긴 셈이고, 멈추면 이번 주 {prev_ro} 끝난 {noun_ro} 볼 수 있습니다.",
                                         "월요일에도 {word}가 나오면 {name} {noun}가 주말을 건넌 셈이고, 멈추면 금요일까지 {prev_ro} 일단락된 것으로 볼 수 있습니다.",
                                         "이어진다면 이번 {word}가 주를 넘긴다는 뜻이고, 멈춘다면 이번 주 {prev_iga} 한 묶음이었다고 볼 수 있습니다."],
                              name=name, word=word, nth=nth, prev_ro=ro(prev_txt), prev_iga=subj(prev_txt), noun=noun, noun_ro=ro(noun)), "w6.cond"))
    P.append((SIGNOFF, "w6.signoff"))
    return P


# ── 제목 · Threads ──
def build_title(F: dict, pk: Picker, htype: str) -> str:
    d0, d1 = _dt(F["days"][0]), _dt(F["days"][-1])
    rng = f"{d0.month}/{d0.day}–{d1.month}/{d1.day}"
    S, B, tot, C = F["S"], F["B"], F["tot"], F["C"]
    kw = {"S": S, "S_eun": eun(S), "B": B, "X": amt_s(tot[S]), "Y": amt_s(tot[B]), "C": pc(C), "cw": "상승" if C > 0 else "하락",
          "rng": rng, "N": F["N"]}
    if htype == "pair":
        bank = ["이번 주 {S} {X} 팔았는데 누가 받았나 | {rng} 주간 결산",
                "{S} {X} 팔 때 {B} {Y} 샀다, 코스피 한 주 {C} {cw} | {rng} 주간 결산",
                "한 주 {S} {X} 순매도, 받은 건 {B} {Y} | {rng} 주간 결산"]
        if F["steady"][B]:
            bank.append("{B} {N} 내내 {Y} 샀다, {S_eun} {X} 팔았다 | {rng} 주간 결산")
    elif htype == "flip":
        G = F["G"]
        f = F["flips"][G]
        kw.update(G=G, Es=amt_s(f["early"]), Ls=amt_s(f["late"]), e=short_days(f["early_days"]), l=short_days(f["late_days"]),
                  ew="샀다가" if f["early"] > 0 else "팔았다가", lw="팔았다" if f["early"] > 0 else "샀다")
        bank = ["{G} {e} {Es} {ew} {l} {Ls} {lw} | {rng} 주간 결산", "이번 주 {G}, {Es} {ew} {Ls} {lw} | {rng} 주간 결산",
                "{G} 한 주 새 방향 바꿨다, {Es}에서 {Ls}로 | {rng} 주간 결산"]
    else:
        bank = ["코스피 한 주 {C} {cw}, 누가 샀나 | {rng} 주간 결산", "이번 주 코스피 {C} {cw}, 산 쪽은 누구 | {rng} 주간 결산",
                "한 주 코스피 {C} {cw}의 주인공 | {rng} 주간 결산"]
    return pk("title", bank, **kw)[:100]


# ── Threads(새 형식) 한도와 검사 ──
TH_MAX_CHARS = 430          # 태그까지 포함한 한 편(상한)
TH_AIM_CHARS = 350          # 목표 하한(JJ 2026-09-13) — 350~420자. 못 채워도 막지는 않는다.
TH_MAX_LINES = 21           # 빈 줄·태그 포함
TH_MAX_LIVE = 14            # 빈 줄·태그를 뺀 실제 문장 줄(run_weekly._check_threads와 같은 한도)
TH_MIN_LINES = 8
TH_MAX_LINE = 34            # 한 줄 — 반말은 어미가 짧다. 한 호흡에 한 줄(JJ 2026-09-13).
TH_MAX_FIGS = 4             # 본문에 들어가는 숫자
TH_MAX_EMOJI = 1            # 편당 0~1개. 우리는 숫자를 다루니 절제한다.
# '9조 9천억'을 한 덩이로 센다(threads_v4.FIG_RE는 '9조'만 잡는다)
TH_FIG_RE = re.compile(r"\d+조(?:\s\d천억)?|\d{1,3}(?:,\d{3})*억|\d천억|\d+(?:\.\d+)?%|\d{1,3},\d{3}선?")
TH_CLIP_RE = re.compile(r"(?:팜|삼|봄|줌|옴|감|남|짐|김|림|름|춤|함|됨|음)[.·…!?]*$")  # 축약 종결형(음슴체)
TH_CHAT_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]|~|\.{2,}|…")                                  # ㅋㅋ·ㅎㅎ·물결·말줄임
# 반말 완결형(JJ 2026-09-13) — '-어/-아/-야/-여'(보여), 질문 '-까?/-지?/-어?/-야?', 숫자로 끝나는 짧은 절, 다음 줄로 이어지는 쉼표.
# 음슴체(ㅁ 받침 종결)는 TH_CLIP_RE가 따로 막는다. 이 둘은 다른 검사다 — 반말이지 줄임말이 아니다.
TH_END_RE = re.compile(r"(?:[아어야여]|해|돼|봐)[.?!]?$|[까지나][?]$|[억조%][.]?$|,$")
TH_JONDAE_RE = re.compile(r"(?:습니다|입니다|ㅂ니다|니다|까요|세요|십시오|셨|시죠)")   # 본문·답글에 존댓말이 남으면 실패
TH_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U0001F004-\U0001F0CF☀-➿⬀-⯿️]")
TH_SHORT_FIG_RE = re.compile(r"\d+\.\d+\s?조")                                        # '9.9조' 같은 압축 표기 금지
TH_MIN_CHARS = 330          # 이보다 짧으면 검사 실패(목표는 TH_AIM_CHARS 350~420)
# 피드에서 뜻이 안 통하는 금융 용어 — Threads 본문·답글에 하나도 나오면 안 된다(JJ 2026-09-13).
# 허용: 코스피·코스닥·나스닥·외국인·기관·개인·종목명 같은 고유명·주체명, 그리고 숫자.
from checks import jargon as _jargon          # 세 편이 같은 목록을 본다(checks/jargon.py)
TH_JARGON = _jargon.BAN
# 첫 줄에 있어야 하는 '이미 봤다'는 인정(반말)
TH_SEEN_RE = re.compile(r"(봤을|봤지|봤어|알 거야|알잖|보는 숫자|보이는 숫자|이미|누구나|기사 제목)")
# 사실 없이 다음을 예고만 하는 빈손 문장 — 첫 문단에 있으면 실패
TH_TEASE = ["확인할 숫자", "따로 있어", "따로 있었어", "말해 줄", "알려 줄", "밑에 적", "아래에 적"]


def th_name(n: str) -> str:
    """Threads 전용 주체 이름 — 처음 보는 사람 기준(JJ 2026-09-13).
    '기타법인'은 회계 분류 용어라 피드에서는 뜻이 안 통한다. 나머지(개인·외국인·기관)는 그대로 쓴다.
    영상 대본은 이 함수를 쓰지 않는다 — 대본은 '기타법인'을 그대로 읽는다."""
    return "회사들" if n == "기타법인" else n


def _th_iya(w: str) -> str:
    """반말 서술격 '-이야/-야' — '9조 9천억이야' / '회사들이야' / '바이오/제약이야'.
    영상 대본은 쓰지 않는다(대본은 '-입니다')."""
    return w + ("이야" if _bat(w) else "야")


def _flip_bank(F: dict, G: str, mate: str = "") -> tuple[list, dict]:
    """방향을 바꾼 주체 — 반말 완결형 문장 뱅크. mate가 있으면 '그쪽만 멈추지 않았다'로 대비를 준다."""
    f = F["flips"][G]
    e_buy = f["early"] > 0
    G, mate = th_name(G), th_name(mate) if mate else mate
    kw = {"G_eun": eun(G), "G_iga": subj(G), "start": wdn(f["late_days"][0]),
          "late": "파는" if e_buy else "사는", "early": "사다가" if e_buy else "팔다가",
          "M_man": (mate + "만") if mate else "", "M_iga": subj(mate) if mate else ""}
    solo = ["{G_eun} {start}부터 {late} 쪽으로 돌아섰어.",
            "{G_eun} 주 초반엔 {early} {start}부터 {late} 쪽이었어.",
            "{G_iga} {late} 쪽으로 돌아선 건 {start}부터야."]
    if not mate:
        return solo, kw
    # mate가 있으면 두 줄짜리(대비) 문형만 쓴다 — 한 줄짜리 solo를 섞으면 편 길이가 300자 아래로 내려간다.
    # 그래서 solo를 빼는 대신 두 줄 문형을 여섯 개로 늘렸다(문형 수는 그대로 6).
    return [("{G_eun} {start}부터 {late} 쪽으로 돌아섰는데,", "그 사이 {M_man} 하루도 멈추지 않았어."),
            ("{G_eun} {start}부터 {late} 쪽으로 돌아섰어.", "그 사이 {M_man} 자리를 지켰어."),
            ("{start}부터는 {G_iga} {late} 쪽으로 바뀌었는데,", "{M_iga} 멈춘 날은 하루도 없었어."),
            ("{G_eun} 주 초반엔 {early} {start}부터 {late} 쪽이었어.", "{M_man} 끝까지 자리를 안 옮겼어."),
            ("{G_iga} {late} 쪽으로 돌아선 건 {start}부터야.", "그때도 {M_man} 하던 걸 안 바꿨어."),
            ("{start}부터 {G_eun} {late} 쪽으로 손을 바꿨어.", "{M_iga} 그 자리를 계속 받아 줬어.")], kw


def _th_lines(t) -> list[str]:
    return [x for x in (t if isinstance(t, tuple) else (t,)) if x]


def _th_fit(t) -> bool:
    """Threads 한 줄 길이 — 뱅크에서 긴 변형을 걸러 낸다."""
    return all(len(x) <= TH_MAX_LINE for x in _th_lines(t))


def _th_fit_new(seen_txt: str, key: str):
    """첫 문단 2줄이 같은 낱말('오른 주')을 두 번 말하지 않게 — 길이 조건에 얹는다."""
    return lambda t: _th_fit(t) and not (key in seen_txt and key in " ".join(_th_lines(t)))


TH_MIN_SIDE = 5000          # 억: 첫 문단에서 '어긋남'의 주인공으로 세울 최소 금액
TH_Q_RE = re.compile(r"^(.+?) (순매수|순매도)가 (\S+째) 이어지는지$")


def _q_plain(q: str) -> str:
    """다음에 볼 것(next_q)을 피드 말투로 푼다 — 답글에만 쓴다. 영상 대본(w6)은 원래 문장을 그대로 쓴다.
    '외국인 순매도가 나흘째 이어지는지' → '외국인이 나흘째 파는지'
    '반도체 순매수가 사흘째 이어지는지' → '반도체에 돈이 사흘째 들어오는지'"""
    q = (q or "").strip()
    if not q:
        return ""
    m = TH_Q_RE.match(q)
    if not m:
        return q.replace("순매수가", "사는 쪽이").replace("순매도가", "파는 쪽이").replace("순매수", "사는 쪽").replace("순매도", "파는 쪽")
    name, word, nth = m.groups()
    buy = word == "순매수"
    if name in GNAMES:
        return f"{subj(th_name(name))} {nth} {'사는지' if buy else '파는지'}"
    return f"{name}에 돈이 {nth} {'들어오는지' if buy else '빠지는지'}"


def _seen_bank(C: float) -> list:
    """1줄: 읽는 사람이 주말에 이미 본 것 = 그 주 코스피 등락.
    여섯 가지 전부 '이미 봤다'는 인정을 담는다(JJ 2026-09-13 — 시장 보고서로 시작하면 안 된다).
    평일 글(threads_v4.SEEN_UP/SEEN_DOWN)과 같은 문장은 하나도 두지 않는다 — 주말 말투로만 쓴다."""
    if C >= 0.1:
        return [("한 주가 어떻게 끝났는지는 이미 봤을 거야.", "코스피는 한 주 동안 {C} 올랐어."),
                "코스피가 {C} 오른 한 주였다는 건 알 거야.",
                ("한 주를 마치고 앱을 열면 코스피가 {C} 올라 있어.", "여기까지는 누구나 보는 숫자야."),
                "이번 주 코스피 {C} 상승까지는 뉴스에서 봤을 거야.",
                ("주말에 뜬 기사 제목은 다 비슷해.", "코스피 {C} 상승, 오른 한 주였다는 얘기야."),
                ("코스피가 {C} 올라 한 주를 끝냈어.", "여기까지는 앱에 다 보이는 숫자야.")]
    if C <= -0.1:
        return [("한 주가 어떻게 끝났는지는 이미 봤을 거야.", "코스피는 한 주 동안 {C} 내렸어."),
                "코스피가 {C} 내린 한 주였다는 건 알 거야.",
                ("한 주를 마치고 앱을 열면 코스피가 {C} 내려 있어.", "여기까지는 누구나 보는 숫자야."),
                "이번 주 코스피 {C} 하락까지는 뉴스에서 봤을 거야.",
                ("주말 기사 제목은 다 비슷해.", "코스피 {C} 하락, 내린 한 주였다는 얘기야."),
                ("코스피가 {C} 내려 한 주를 끝냈어.", "여기까지는 다 보이는 숫자야.")]
    return [("한 주가 어떻게 끝났는지는 이미 봤을 거야.", "코스피는 한 주 내내 제자리였어."),
            "코스피가 제자리로 끝난 한 주였다는 건 알 거야.",
            ("한 주를 마치고 앱을 열어도 코스피는 그대로야.", "여기까지는 누구나 보는 숫자야."),
            "이번 주 코스피가 거의 안 움직인 건 봤을 거야.",
            ("주말 기사 제목은 다 비슷해.", "코스피는 시작한 자리 근처, 조용한 한 주였다는 얘기야."),
            ("코스피가 제자리에서 한 주를 끝냈어.", "여기까지는 다 보이는 숫자야.")]


# 마지막 한 줄 — 독자에게 던지는 질문(JJ 2026-09-13: 댓글이 붙는 글은 전부 질문으로 끝났다).
# 뜻은 바로 앞 줄이 맡고, 이 줄은 물어보기만 한다. 매번 같으면 AI 티가 나니 여덟 가지로 돌린다.
# 금지: 독자의 손익·보유를 전제하는 말('물렸지?'), 추측 조장('~할 거 같아?' — BAN_FORECAST),
#       원인 접속(니까·라서·그래서 — BAN_CAUSE), '댓글·의견'(BAN_PROMO).
TH_YOU_BANK = ["너네는 이 돈 어디로 갔다고 봐?",
               "이 숫자 보고 무슨 생각 들어?",
               "다들 월요일에 앱 켜 볼 거야?",
               "이 한 주, 너네는 어떻게 봤어?",
               "이 중에 제일 이상한 건 뭐라고 봐?",
               "너네 눈엔 이 한 주가 어떻게 보여?",
               "너네가 본 이번 주는 어땠어?",
               "이 돈이 어디에 남았다고 봐?"]


def _week_words(C: float) -> dict:
    """어긋남 문장이 쓰는 그 주 이름. '지수'라는 낱말은 쓰지 않는다 — 이름(코스피)만 남긴다."""
    if C >= 0.1:
        return {"WKN": "오른 주", "WDUR": "코스피가 오르는 동안"}
    if C <= -0.1:
        return {"WKN": "내린 주", "WDUR": "코스피가 내리는 동안"}
    return {"WKN": "제자리 한 주", "WDUR": "코스피가 멈춰 선 동안"}


def _gap_side(F: dict, htype: str) -> str:
    """첫 문단 2줄의 주인공. 오른 주면 '그런데 판 쪽'(S), 내린 주면 '그런데 산 쪽'(B)이 어긋남이다."""
    S, B, tot, C = F["S"], F["B"], F["tot"], F["C"]
    sell_ok, buy_ok = tot[S] <= -TH_MIN_SIDE, tot[B] >= TH_MIN_SIDE
    if C >= 0.1 and sell_ok:
        return "S"
    if C <= -0.1 and buy_ok:
        return "B"
    if htype == "flip" and F["G"]:
        return "G"
    if sell_ok or buy_ok:
        return "S" if (sell_ok and (not buy_ok or -tot[S] >= tot[B])) else "B"
    if F["G"]:
        return "G"
    # 아무도 5천억을 넘기지 않은 주 — 그래도 2줄에는 숫자가 들어가야 한다(JJ). 더 큰 쪽을 세운다.
    if max(-tot[S], tot[B]) >= 1000:
        return "S" if -tot[S] >= tot[B] else "B"
    return "N"


def build_threads(F: dict, pk: Picker, htype: str) -> tuple[str, str]:
    """Threads 본문 + 첫 답글. 반환 계약은 그대로 (본문+'\\n#국장', 답글 3줄).

    새 기준(JJ 2026-09-13): 첫 문단 두 줄이 전부다.
      1줄 — 읽는 사람이 이미 본 것을 먼저 인정한다(주간편에서는 그 주 코스피 등락).
      2줄 — 그것만 보면 놓치는 사실 하나(우리 수급 데이터). 오른 주에 판 쪽, 내린 주에 산 쪽.
    그 뒤는 (2) 그럼 반대편은 누구였나 → (3) 그래서 무슨 뜻 → (4) 독자에게 던지는 질문 한 줄. 중간에도 질문 한 줄.

    말투(JJ 2026-09-13): **반말**이다. 피드는 지나가는 사람이 보고, 반응이 붙은 글은 전부 반말 + 질문이었다.
      - 완결형 '-어/-야/-아'로 닫는다. 음슴체('팜/샀음')는 그대로 금지 — 반말이지 줄임말이 아니다.
      - 친한 사람에게 설명하는 말투이지 시비조가 아니다. 독자의 손익·보유는 전제하지 않는다.
      - 마지막 줄은 반드시 질문(TH_YOU_BANK). 뜻은 그 앞 줄이 맡는다.
    영상 대본(w0~w6)은 합니다체 그대로다 — 유튜브는 보러 온 사람이라 규격이 다르다.
    숫자는 풀어 쓰고(9조 9천억), 우리만 아는 카운터는 말로 푼다.
    채널 고지와 영상 링크는 본문에 넣지 않는다 — 첫 답글로 뺀다.
    """
    S, B, tot, C = F["S"], F["B"], F["tot"], F["C"]
    Sn, Bn = th_name(S), th_name(B)              # 피드에 나가는 이름(기타법인 → 회사들). 금액·판정은 원래 키(S/B)로 본다.
    X, Y = _won_th(tot[S]), _won_th(tot[B])
    kw = {"S": Sn, "S_eun": eun(Sn), "S_iga": subj(Sn), "S_ieot": ieot(Sn), "X": X, "X_eul": obj(X), "X_ieot": ieot(X),
          "B": Bn, "B_eun": eun(Bn), "B_iga": subj(Bn), "B_ieot": ieot(Bn), "Y": Y, "Y_eul": obj(Y),
          "X_iya": _th_iya(X), "Y_iya": _th_iya(Y), "S_iya": _th_iya(Sn), "B_iya": _th_iya(Bn),
          "N": F["N"], "Nd": f"{F['n_days']}일", "C": _pc_th(C), **_week_words(C)}
    side = _gap_side(F, htype)
    steady_b = F["steady"][B] and tot[B] > 0
    steady_s = F["steady"][S] and tot[S] < 0
    flip_used = side == "G"

    # (1) 첫 문단 — 이미 본 것, 그리고 그것만 보면 놓치는 것
    lead = _th_lines(pk("th.seen", _seen_bank(C), threads=True, ok=_th_fit, **kw))
    if side == "S":
        bank = ["그런데 그 {WKN}에 {S_eun} {X_eul} 팔았어.",
                "그 {WKN}에 가장 많이 판 쪽은 {S}, {X_iya}.",
                "그런데 {WDUR} {S_iga} 판 돈이 {X_iya}.",
                "그 한 주 안에서 {S_eun} {X_eul} 내다 팔았어.",
                "그런데 같은 기간 {S_eun} {X_eul} 팔고 나갔어.",
                "{WKN}였는데, {S_eun} 그 사이 {X_eul} 팔았어."]
    elif side == "B":
        bank = ["그런데 그 {WKN}에 {B_eun} {Y_eul} 사들였어.",
                "그 {WKN}에 가장 많이 산 쪽은 {B}, {Y_iya}.",
                "그런데 {WDUR} {B_iga} 산 돈이 {Y_iya}.",
                "그 한 주 안에서 {B_eun} {Y_eul} 받아 갔어.",
                "그런데 같은 기간 {B_eun} {Y_eul} 사 모았어.",
                "{WKN}였는데, {B_eun} 그 사이 {Y_eul} 샀어."]
    elif side == "G":
        kw = {**kw, **_flip_bank(F, F["G"])[1]}
        bank = [("그런데 그 {WKN} 안에서,", "{G_eun} {start}부터 {late} 쪽으로 돌아섰어."),
                ("그 {WKN}의 한가운데서 방향이 한 번 바뀌었어.", "{G_iga} {start}부터야."),
                ("그런데 {WDUR} 방향을 바꾼 쪽이 있어.", "{G_eun} {start}부터 {late} 쪽이었어."),
                ("{WKN}였는데, 그 안은 한 방향이 아니었어.", "{G_eun} {start}부터 {late} 쪽으로 돌아섰어."),
                ("그런데 그 한 주가 내내 한 방향이지는 않았어.", "{G_iga} {start}부터 {late} 쪽으로 바뀌었어."),
                ("그 {WKN} 안에서 {G_eun} 중간에 손을 바꿨어.", "{start}부터야.")]
    else:
        bank = ["그런데 그 {WKN} 안에서는 사는 쪽과 파는 쪽이 갈렸어.",
                "그 {WKN} 안을 열어 보면 한쪽으로 기운 곳이 없어.",
                "그런데 {WDUR} 크게 사거나 판 쪽은 안 보여.",
                "그 한 주 안에서는 어느 쪽도 크게 움직이지 않았어.",
                "{WKN}였는데, 산 쪽과 판 쪽이 서로 엇갈렸어.",
                "그런데 같은 기간 돈은 한쪽으로 모이지 않았어."]
    gap_ok = _th_fit_new(" ".join(lead), "오른" if C >= 0.1 else "내린" if C <= -0.1 else "제자리")
    lead += _th_lines(pk("th.gap", bank, threads=True, ok=gap_ok, **kw))

    # (2) 그래서 반대편은 누구였나
    if side == "S":
        qbank = ["그 주식은 누가 받았을까?", "그럼 그 주식은 누가 넘겨받았을까?", "판 쪽이 있으면 받은 쪽도 있어. 어디였을까?"]
    elif side == "B":
        qbank = ["그 주식은 누가 넘긴 걸까?", "그럼 판 쪽은 어디였을까?", "산 쪽이 있으면 판 쪽도 있어. 어디였을까?"]
    else:
        qbank = ["그 사이 돈은 어디로 움직였을까?", "그럼 돈은 어디로 갔을까?", "이 한 주에 무슨 일이 있었을까?"]
    ask = _th_lines(pk("th.q", qbank, threads=True, ok=_th_fit))
    if side == "B":                                  # 첫 문단이 산 쪽을 말했으니 여기는 판 쪽
        mate = S
        if steady_s:
            bank = ["{Nd} 내내 판 곳이 하나 있었어. {S}, {X}.",
                    "하루도 쉬지 않고 내놓은 곳이 있어. {S}, {X}.",
                    "{N} 내내 판 쪽은 {S_ieot}어. 한 주 {X}."]
        elif tot[S] < 0:
            bank = ["그 주식을 내놓은 곳은 {S}, 한 주 {X_iya}.",
                    "넘긴 쪽은 {S_ieot}어. 한 주 합계 {X}.",
                    "한 주 동안 가장 많이 판 곳은 {S}, {X_iya}."]
        else:
            bank = ["이번 주에는 네 곳 모두 산 쪽에 가까웠어.", "한 주 동안 크게 내놓은 쪽은 안 보여.",
                    "이번 주에는 어느 쪽도 크게 팔지 않았어."]
    else:
        mate = B
        if steady_b:
            bank = ["{Nd} 내내 산 곳이 하나 있었어. {B}, {Y}.",
                    "하루도 쉬지 않고 산 곳이 있어. {B}, 한 주 {Y}.",
                    "{N} 내내 사들인 쪽은 {B_ieot}어. 한 주 {Y}."]
        elif tot[B] > 0:
            bank = ["그 주식을 가장 많이 받은 곳은 {B}, 한 주 {Y_iya}.",
                    "받아 간 쪽은 {B_ieot}어. 한 주 합계 {Y}.",
                    "한 주 동안 가장 많이 산 곳은 {B}, {Y_iya}."]
        else:                                        # 네 주체가 모두 판 쪽 — 금액을 붙이면 거꾸로 읽힌다
            bank = ["이번 주에는 네 곳 모두 판 쪽에 가까웠어.", "한 주 동안 크게 받아 간 쪽은 안 보여.",
                    "이번 주에는 어느 쪽도 크게 받아 가지 않았어."]
    who = _th_lines(pk("th.who", bank, threads=True, ok=_th_fit, **kw))
    stock = []
    if F["bb"]:
        names = _and([x["name"] for x in F["bb"]])
        two = len(F["bb"]) == 2
        skw = {"names": names, "names_ieot": ieot(names), "most": "대부분" if F["share"] >= 0.6 else "절반 이상",
               "who_ga": "두 회사가" if two else subj(F["bb"][0]["name"]),
               "who_all": "두 회사 모두" if two else eun(F["bb"][0]["name"]),
               "M": min(int(p["from"][5:7]) for p in F["bb_progs"])}
        # '자사주 매입'은 피드에서 뜻이 안 통한다 — 회사가 자기 회사 주식을 사들이는 것으로 풀어 쓴다(JJ 2026-09-13).
        stock = _th_lines(pk("th.stock", [
            ("가장 많이 산 주식은 {most} {names_ieot}고,", "{who_ga} 자기 회사 주식을 사 모으는 중이야."),
            ("{most} {names}에 들어간 돈이야.", "{who_all} {M}월부터 자기 회사 주식을 사고 있어."),
            ("사들인 주식은 {most} {names_ieot}어.", "{who_ga} 자기 회사 주식을 사들이고 있어.")], threads=True, ok=_th_fit, **skw))

    # (2-2) 그 돈이 어느 분야에 머물렀나 — 금액은 붙이지 않는다(본문 숫자 한도)
    sector = []
    stay = [t["theme"] for t in F["stayed"][:2]]
    out_th = (F["top_out"] or {}).get("theme") if (F["top_out"] or {}).get("net", 0) <= -1000 else ""
    if stay:
        snames = _and(stay)
        tkw = {"TS": snames, "TS_ieot": ieot(snames), "TS_en": snames + "엔", "TO": out_th, "TO_eun": eun(out_th or ""),
               "TO_iya": _th_iya(out_th or "")}
        # 빠져나간 분야(out_th)가 있으면 두 줄짜리 대비 문형만 쓴다 — 한 줄짜리를 섞으면 편 길이가 300자 아래로 내려간다.
        pair = [("외국인과 기관 돈이 한 주 내내 머문 곳은 {TS_ieot}어.", "{TO_eun} 거꾸로 한 주 내내 빠지는 쪽이었어."),
                ("분야로 보면 {TS_en} 돈이 계속 들어왔어.", "{TO}에서는 거꾸로 돈이 계속 나갔어."),
                ("끝까지 돈이 남아 있던 분야는 {TS_ieot}어.", "가장 많이 빠져나간 분야는 {TO_iya}."),
                ("돈이 한 주 내내 들어온 분야는 {TS_ieot}어.", "같은 기간 {TO_eun} 계속 빠지는 쪽이었어."),
                ("분야를 갈라 보면 {TS_en} 돈이 남았어.", "{TO}에서는 거꾸로 돈이 줄었어."),
                ("한 주 내내 돈이 쌓인 쪽은 {TS_ieot}어.", "거꾸로 {TO_eun} 내내 돈이 빠졌어.")]
        solo = ["외국인과 기관 돈이 한 주 내내 머문 곳은 {TS_ieot}어.",
                "분야로 보면 {TS_en} 돈이 계속 들어왔어.",
                "끝까지 돈이 남아 있던 분야는 {TS_ieot}어."]
        sector = _th_lines(pk("th.sector", pair if out_th else [(s,) for s in solo],
                              threads=True, ok=_th_fit, **tkw))
    elif out_th:
        sector = _th_lines(pk("th.sector_out", ["분야로 보면 돈이 가장 많이 빠진 곳은 {TO_iya}.",
                                                "외국인과 기관 돈이 가장 크게 나간 분야는 {TO_iya}.",
                                                "한 주 동안 돈이 가장 많이 빠져나간 곳은 {TO_iya}."],
                              threads=True, ok=_th_fit, TO=out_th, TO_iya=_th_iya(out_th)))

    # (3) 그게 무슨 뜻일 수 있나
    flip = []
    if F["G"] and not flip_used and F["G"] != mate:
        steady_mate = steady_s if mate == S else steady_b
        bank, fkw = _flip_bank(F, F["G"], mate if steady_mate else "")
        flip = _th_lines(pk("th.flip", bank, threads=True, ok=_th_fit, **fkw))
    rec = []
    if F["checks"]:
        n, k = len(F["checks"]), sum(1 for c in F["checks"] if c["ok"])
        # 처음 보는 사람도 그대로 읽히게 — '우리가 보자고 했던'이라는 내부 맥락 없이 사실만 남긴다.
        if k == 0:
            bank = ["하루 들어온 돈이 다음 날까지 남은 자리는 없었어.", "한 번 잡힌 방향은 이번 주 전부 하루로 끝났어.",
                    "이번 주엔 다음 날까지 이어진 방향이 하나도 없었어."]
        elif k < n:
            bank = ["하루 만에 끊긴 자리도 있고, 다음 날까지 간 자리도 있어.", "한 번 잡힌 방향이 다음 날까지 간 자리는 일부뿐이야.",
                    "이번 주엔 다음 날까지 이어진 방향이 일부만 있었어."]
        else:
            bank = ["하루 들어온 돈이 다음 날까지 남은 자리가 이번 주엔 전부야.", "한 번 잡힌 방향은 이번 주 모두 다음 날까지 갔어.",
                    "이번 주엔 잡힌 방향이 전부 다음 날에도 그대로였어."]
        rec = _th_lines(pk("th.record", bank, threads=True, ok=_th_fit))
    # 마지막 문단: 뜻 한 줄 → 독자에게 던지는 질문 한 줄로 닫는다(JJ 2026-09-13).
    # 뜻은 앞 줄이 맡고, 마지막 한 줄은 물어보기만 한다. 다음에 볼 것·채널 고지는 답글 몫이라 여기서 예고하지 않는다.
    if F["bb"] and steady_b:
        bank = [("회사가 자기 회사 주식을 사들이는 동안에는,", "파는 주식을 받아 줄 곳이 하나 있다는 뜻이야."),
                ("이 돈은 값이 싸 보여서 들어온 돈이 아니야.", "회사가 미리 정해 둔 기간 동안 사는 돈이야."),
                ("파는 쪽이 내내 나와도 받아 준 곳이 있었어.", "한쪽으로만 기울지 않은 한 주였다는 뜻이야.")]
    else:
        bank = [("{WKN}라는 한 줄 뒤에 가려진 게 있어.", "서로 다른 쪽으로 움직인 돈이 있었다는 뜻이야."),
                ("코스피 숫자 하나만 보면 여기까지야.", "그 안에서 돈의 주인이 바뀐 한 주였다는 뜻이야."),
                ("숫자 한 줄로는 오른 주, 내린 주만 남아.", "누가 사고 누가 팔았는지는 그 안에 있어.")]
    close = _th_lines(pk("th.close", bank, threads=True, ok=_th_fit, **kw))
    close += _th_lines(pk("th.you", TH_YOU_BANK, threads=True, ok=_th_fit))

    # 조립: 필수(우선순위 0)를 먼저 넣고, 나머지는 줄 수·글자 수·숫자 한도 안에서만 붙인다.
    parts = [(0, lead, True), (2, ask, True), (0, who, True), (1, stock, False), (3, sector, True), (4, flip, True), (5, rec, True),
             (0, close, True)]

    def render(keep: set) -> list[str]:
        out: list[str] = []
        for i, (_, lines, brk) in enumerate(parts):
            if not lines or i not in keep:
                continue
            if out and brk:
                out.append("")
            out += lines
        return out

    def ok_budget(keep: set) -> bool:
        t = render(keep)
        txt = "\n".join(t)
        return (len(t) + 1 <= TH_MAX_LINES and len([x for x in t if x.strip()]) <= TH_MAX_LIVE
                and len(txt) + len(TAG) + 1 <= TH_MAX_CHARS and len(TH_FIG_RE.findall(txt)) <= TH_MAX_FIGS)

    keep = {i for i, (p, lines, _) in enumerate(parts) if p == 0 and lines}
    for i in sorted((i for i, (p, lines, _) in enumerate(parts) if p and lines), key=lambda i: parts[i][0]):
        if ok_budget(keep | {i}):
            keep.add(i)
    body = "\n".join(render(keep))

    q_full = _q_plain(F["next_q"])
    # 채널 고지·링크·다음 주에 볼 것은 전부 이 답글이 맡는다(본문에는 넣지 않는다).
    reply = ("영상 전체는 여기서 → {YT}\n"
             "평일엔 매일 오후 4시 30분, 그날 한국 시장에서 누가 샀는지 올려."
             + (f"\n다음 주엔 {q_full} 볼게." if q_full else ""))
    return body + "\n" + TAG, reply


# ── 길이 맞추기 ──
def fit(parts: dict[str, list]) -> tuple[dict[str, list], list[str]]:
    """TARGET_SEC를 넘으면 PRIO 큰 문장부터 뺀다(같은 번호면 뒤 장면 먼저)."""
    parts = {k: list(v) for k, v in parts.items()}
    total = lambda: sum(est_sec(t) for v in parts.values() for t, _ in v)  # noqa: E731
    dropped = []
    cands = sorted(((PRIO[s], sid, i, s) for sid, v in parts.items() for i, (_, s) in enumerate(v) if s in PRIO),
                   key=lambda x: (-x[0], -int(x[1][1:])))
    for _, sid, _, slot in cands:
        if total() <= TARGET_SEC:
            break
        parts[sid] = [(t, s) for t, s in parts[sid] if s != slot]
        dropped.append(slot)
    return parts, dropped


# ── 검사 ──
def _mask(s: str, extra: tuple = ()) -> str:
    t = re.sub(r"약\s?", "", s or "")
    t = re.sub(r"\d[\d,.]*\s?(조|천억|억|%|선|포인트|거래일|월)?", "N", t)
    for g in ("기타법인", "회사들", "외국인", "기관", "개인"):
        t = t.replace(g, "G")
    for x in sorted(set(extra), key=len, reverse=True):
        if x:
            t = t.replace(x, "T")
    t = re.sub(r"[월화수목금토일]요일", "W", t)
    return re.sub(r"(하루|이틀|사흘|나흘|닷새)(째)?", "D", t)


def daily_corpus(days: list[str]) -> tuple[list[str], list[str]]:
    """그 주 일간 영상 대본 문장과 Threads 본문(새 말투로 만든 날만)."""
    sents, posts = [], []
    for d in days:
        p = os.path.join(DATA, d, "computed_kr.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        for s in c.get("scenes") or []:
            sents += sentences(s.get("tts") or "")
        if c.get("threads_facts") and (c.get("threads_text") or "").strip():
            posts.append(c["threads_text"].strip())
    return sents, posts


def reuse_checker(F: dict):
    """문장 하나가 일간 영상 고정 문장(DAILY_FIXED)이거나 그 주 일간 대본 문장과 뼈대가 비슷하면 사유 문자열, 아니면 None."""
    names = tuple({t["theme"] for t in F["tweek"]} | {x.get("name", "") for x in F["ostk"]})
    daily_sents, _ = daily_corpus(F["days"])
    dm = [(s, _mask(s, names)) for s in daily_sents if len(s) >= 10]

    def hit(s: str) -> str | None:
        if not s or s in SIGNOFF:
            return None
        for fx in DAILY_FIXED:
            if fx in s:
                return f"일간 고정 문장 '{fx}'"
        ms = _mask(s, names)
        if len(ms) >= 12:
            for ds, dmask in dm:
                r = difflib.SequenceMatcher(None, ms, dmask).ratio()
                if r >= 0.72:
                    return f"일간 대본과 비슷({r:.2f}) ~ {ds}"
        return None
    return hit


def validate(out: dict, F: dict, hit=None) -> list[str]:
    issues = []
    names = tuple({t["theme"] for t in F["tweek"]} | {x.get("name", "") for x in F["ostk"]})
    _, daily_posts = daily_corpus(F["days"])
    hit = hit or reuse_checker(F)
    for sc in out["scenes"]:
        tts = sc["tts"]
        for label, txt in (("tts", tts), ("sub", sc.get("sub") or "")):
            h = forbidden.find(txt)
            if h:
                issues.append(f"{sc['id']} {label} forbidden {h}")
        if re.search(r"[()\[\]]", tts):
            issues.append(f"{sc['id']} 괄호")
        for s in sentences(tts):
            if not re.search(r"(니다|까요)[.?]$", s):
                issues.append(f"{sc['id']} 합니다체 아님: {s}")
            why = hit(s)
            if why:
                issues.append(f"{sc['id']} {why}: {s}")
    w2 = next((s["tts"] for s in out["scenes"] if s["id"] == "w2"), "")
    n2 = len(re.findall(r"약 [\d.,]+(?:조|천억|억)|\d+(?:\.\d+)?%", w2))
    if n2 > 5:
        issues.append(f"w2 숫자 {n2}개")
    if not out["scenes"][-1]["tts"].endswith(SIGNOFF):
        issues.append("w6 끝 멘트 없음")
    allt = " ".join(s["tts"] for s in out["scenes"])
    for word in ("방향", "한 주였습니다"):
        if allt.count(word) > 4:
            issues.append(f"'{word}' {allt.count(word)}번")
    t = out["title"]
    if forbidden.find(t) or re.match(r"^\s*(\d|오늘)", t) or "주간 결산" not in t or len(t) > 100:
        issues.append(f"title {forbidden.find(t)} {t}")
    th = out["threads"]
    lines = th.split("\n")
    if lines[-1] != TAG:
        issues.append("threads 끝 태그 없음")
    if not TH_MIN_LINES <= len(lines) <= TH_MAX_LINES:
        issues.append(f"threads {len(lines)}줄")
    if len(th) > TH_MAX_CHARS:
        issues.append(f"threads {len(th)}자")
    if len(th) < TH_MIN_CHARS:
        issues.append(f"threads {len(th)}자 — 최소 {TH_MIN_CHARS}자(목표 {TH_AIM_CHARS}~420)")
    if th.count("#") != 1:
        issues.append(f"threads 해시태그 {th.count('#')}개")
    body = [x for x in lines[:-1] if x.strip()]
    for x in body:
        h = forbidden.find_threads(x)
        if h:
            issues.append(f"threads forbidden {h}: {x}")
        if len(x) > TH_MAX_LINE:
            issues.append(f"threads 줄 {len(x)}자: {x}")
        if TH_CHAT_RE.search(x):
            issues.append(f"threads 채팅 기호(ㅋ·ㅎ·..): {x}")
        if TH_CLIP_RE.search(x.rstrip()):
            issues.append(f"threads 축약 종결형(팜/음/함/짐): {x}")
        elif not TH_END_RE.search(x.rstrip()):
            issues.append(f"threads 반말 완결형 아님(-어/-야/-아/-까?): {x}")
        if TH_JONDAE_RE.search(x):
            issues.append(f"threads 존댓말 남음(반말로): {x}")
        if re.match(r"^\s*\d+\s*[.)]\s", x):
            issues.append(f"threads 번호 목록: {x}")
    # 마지막 줄은 독자에게 던지는 질문으로 닫는다(JJ 2026-09-13 — 댓글이 붙는 글은 전부 질문으로 끝났다)
    if not body:
        issues.append("threads 본문 없음")
    elif not body[-1].rstrip().endswith("?"):
        issues.append(f"threads 마지막 줄이 질문이 아님: {body[-1]}")
    n_emoji = len(TH_EMOJI_RE.findall("\n".join(body)))
    if n_emoji > TH_MAX_EMOJI:
        issues.append(f"threads 이모지 {n_emoji}개(편당 {TH_MAX_EMOJI}개까지)")
    jd_r = [x for x in (out.get("threads_reply") or "").split("\n") if TH_JONDAE_RE.search(x)]
    if jd_r:
        issues.append(f"threads_reply 존댓말 남음(반말로): {jd_r}")
    btxt = "\n".join(body)
    # 금융 용어 — 하나라도 있으면 다시 쓴다(본문·답글 모두)
    jar = [w for w in TH_JARGON if w in btxt]
    if jar:
        issues.append(f"threads 금융 용어 {jar}")
    jar_r = [w for w in TH_JARGON if w in (out.get("threads_reply") or "")]
    if jar_r:
        issues.append(f"threads_reply 금융 용어 {jar_r}")
    # 첫 문단 — 1) 읽는 사람이 이미 본 것(코스피 등락 + 인정) 2) 그것만 보면 놓치는, 숫자가 든 사실
    blocks = [b for b in re.split(r"\n\s*\n", "\n".join(lines[:-1])) if b.strip()]
    head = blocks[0] if blocks else ""
    cfig = _pc_th(F["C"])
    seen_ok = cfig in head if abs(F["C"]) >= 0.1 else bool(re.search(r"(제자리|그대로|안 움직|시작한 자리)", head))
    if not seen_ok:
        issues.append(f"threads 첫 문단에 그 주 코스피 등락이 없음: {head!r}")
    if not TH_SEEN_RE.search(head):
        issues.append(f"threads 첫 문단에 '이미 보셨다'는 인정이 없음: {head!r}")
    rest_figs = TH_FIG_RE.findall(head)
    if cfig in rest_figs:
        rest_figs.remove(cfig)
    if not rest_figs and _gap_side(F, out.get("hook_type") or "") != "N":
        issues.append(f"threads 첫 문단 2줄에 숫자가 없음(빈손 예고 금지): {head!r}")
    tease = [w for w in TH_TEASE if w in head]
    if tease:
        issues.append(f"threads 첫 문단 빈손 예고 {tease}")
    # 마지막 문단은 '그래서 무슨 뜻' — 다음에 볼 것 예고는 답글 몫이다.
    # 맨 끝 질문 줄은 독자에게 던지는 말이라 이 검사에서 뺀다(질문 안의 '월요일'은 예고가 아니다).
    tail_blk = "\n".join(blocks[-1].split("\n")[:-1]) if blocks else ""
    if re.search(r"(다음 주|월요일|볼게|보려고|확인해 보)", tail_blk):
        issues.append(f"threads 마지막 문단이 뜻이 아니라 예고: {blocks[-1]!r}")
    if TH_SHORT_FIG_RE.search(btxt):
        issues.append("threads 숫자 압축 표기(9.9조 → 9조 9천억)")
    for nm, lst in (("news", tv4.BAN_NEWS), ("interp", tv4.BAN_INTERP), ("promo", tv4.BAN_PROMO), ("rec", tv4.BAN_REC), ("money", tv4.BAN_MONEY),
                    ("score", tv4.BAN_SCORE), ("cause", tv4.BAN_CAUSE), ("forecast", tv4.BAN_FORECAST), ("crowd", tv4.BAN_CROWD), ("persona", tv4.BAN_PERSONA)):
        hits = [wd for wd in lst if wd in btxt]
        if hits:
            issues.append(f"threads ban-{nm} {hits}")
    figs = TH_FIG_RE.findall(btxt)
    if len(figs) > TH_MAX_FIGS:
        issues.append(f"threads 숫자 {figs}")
    if re.search(r"(?:^|\s)약\s?\d", btxt):
        issues.append("threads '약 N'")
    # 종목명은 자사주 매입을 설명하는 문단(기타법인 매수 상위 + 매입 프로그램 확인)에서만 쓴다.
    bb_names = {x.get("name") for x in F["bb"] if x.get("name")}
    for blk in re.split(r"\n\s*\n", "\n".join(lines[:-1])):
        sn = [x["name"] for x in F["ostk"] if x.get("name") and x["name"] in blk]
        if sn and not (set(sn) <= bb_names and re.search(r"자기 회사 주식|자기 주식", blk)):
            issues.append(f"threads 종목명 {sn}")
    tm = set(tv4.THEMES) | set(names)
    for p in daily_posts:
        pm = {tv4.mask(ln, tm) for ln in p.split("\n")}
        same = [x for x in body if tv4.mask(x, tm) in pm]
        if same:
            issues.append(f"threads 일간 글과 같은 뼈대 {same}")
        shared = {b for b in tv4.bigrams(btxt, tm) & tv4.bigrams(p, tm) if not all(tv4.PH_RE.fullmatch(tok) for tok in b)}
        if len(shared) > 3:
            issues.append(f"threads 일간 글과 겹치는 말 {len(shared)}쌍 {sorted(shared)}")
    for x in out["threads_reply"].split("\n"):
        h = forbidden.find_threads(x)
        if h:
            issues.append(f"threads_reply forbidden {h}")
    for x in out["hook_parts"]:
        if forbidden.find(x):
            issues.append(f"hook_parts forbidden {x}")
    return issues


# ── 본체 ──
def build_weekly(w: dict, news=None) -> dict:
    F = facts(w)
    hit = reuse_checker(F)
    pk = Picker(F["week_no"], _prev_week(w), reuse=lambda s: bool(hit(s)))
    htype = hook_type(F)
    parts = {}
    pk.new_scene()
    parts["w0"], hook_parts, said = scene_w0(F, pk, htype)
    for sid, fn in (("w1", lambda: scene_w1(F, pk)), ("w2", lambda: scene_w2(F, pk, said, htype)), ("w3", lambda: scene_w3(F, pk)),
                    ("w4", lambda: scene_w4(F, pk, news_events(w, news))), ("w5", lambda: scene_w5(F, pk, htype)), ("w6", lambda: scene_w6(F, pk))):
        pk.new_scene()
        parts[sid] = fn()
    parts, dropped = fit(parts)
    scenes = []
    for sid in ("w0", "w1", "w2", "w3", "w4", "w5", "w6"):
        P = parts.get(sid) or []
        if not P:
            continue
        tts = tidy(" ".join(t for t, _ in P))
        sub = "" if sid == "w0" else tidy(" ".join(t for t, s in P if s != "w6.signoff"))
        ask = next((x for x in sentences(tts) if x.endswith("?")), "")
        scenes.append({"id": sid, "min": MIN_SEC[sid], "tts": tts, "sub": sub, "ask": ask})
    title = build_title(F, pk, htype)
    threads, reply = build_threads(F, pk, htype)
    picks = {k: v for k, v in pk.picks.items() if k not in dropped}
    out = {"scenes": scenes, "title": title, "threads": threads, "threads_reply": reply, "hook_parts": hook_parts,
           "hook_type": htype, "picks": picks, "dropped": dropped, "est_sec": round(sum(est_sec(s["tts"]) for s in scenes), 1)}
    out["issues"] = validate(out, F, hit)
    return out


# ── 시험용: 일간 파일로 메모리 초안(파일은 쓰지 않는다) ──
def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def draft_from_daily(week_end: str) -> dict:
    """data/weekly/<build>/computed_weekly.json 이 아직 없을 때 시험용. SHARED SCHEMA 모양으로 메모리에만 만든다."""
    end = _dt(week_end)
    mon = end - timedelta(days=end.weekday())
    days = [d for d in ((mon + timedelta(days=i)).strftime("%Y%m%d") for i in range(5)) if os.path.exists(os.path.join(DATA, d, "computed_kr.json"))]
    C = {d: _load(os.path.join(DATA, d, "computed_kr.json")) for d in days}
    prev_close = C[days[0]]["kospi"]["prev_close"]
    kdays = [{"d": d, **{k: C[d]["kospi"][k] for k in ("close", "chg_pct", "high", "low")}} for d in days]
    inv_days = [{"d": d, **{k: C[d]["investors"]["kospi"][k] for k in ("indiv", "foreign", "inst", "others")}} for d in days]
    T: dict[str, dict] = {}
    for d in days:
        for th, v in (_load(os.path.join(DATA, d, "raw", "flows.json")).get("table_t") or {}).items():
            t = T.setdefault(th, {"theme": th, "net": 0, "foreign": 0, "inst": 0, "days": []})
            t["net"] += v["net"]; t["foreign"] += v["foreign"]; t["inst"] += v["inst"]; t["days"].append({"d": d, "net": v["net"]})
    for t in T.values():
        t["pos_days"] = sum(1 for x in t["days"] if x["net"] > 0)
    tw = sorted(T.values(), key=lambda t: t["net"])
    o_days, o_week = [], {}
    for d in days:
        top = [{"code": x["code"], "name": x["name"], "v": x["v"]} for x in (_load(os.path.join(DATA, d, "raw", "kiwoom_sum.json"))["kospi"].get("top_others_buy") or [])]
        o_days.append({"d": d, "top": top})
        for x in top:
            o_week.setdefault(x["code"], {"code": x["code"], "name": x["name"], "v": 0})["v"] += x["v"]
    bbj = _load(os.path.join(DATA, "buybacks.json"))["programs"]
    cov_tot = sum(C[x["d"]]["investors"]["kospi"]["others"] for x in o_days if x["top"])
    share = (sum(v["v"] for v in o_week.values() if v["code"] in {p["code"] for p in bbj}) / cov_tot) if cov_tot else None
    checks = [{"d": e["result"]["date"], "q": e["q"], "ok": e["result"]["ok"]} for e in _load(os.path.join(DATA, "ledger.json"))["entries"]
              if e.get("result") and e["result"]["date"] in days]
    return {
        "week_start": days[0], "week_end": days[-1], "build_date": (end + timedelta(days=1)).strftime("%Y%m%d"), "days": days,
        "kospi": {"prev_close": prev_close, "days": kdays, "week_chg_pct": round((kdays[-1]["close"] / prev_close - 1) * 100, 2),
                  "week_high": max(x["high"] for x in kdays), "week_low": min(x["low"] for x in kdays), "events": []},
        "inv": {"days": inv_days, "week": {k: sum(x[k] for x in inv_days) for k in ("indiv", "foreign", "inst", "others")},
                "streak_end": {k: (C[days[-1]].get("inv_streak") or {}).get(k, {}).get("streak") or 0 for k in ("foreign", "inst")}},
        "themes": {"week": tw, "top_out": tw[0], "top_in": tw[-1], "stayed": [t["theme"] for t in tw if t["pos_days"] >= 4]},
        "others_stocks": {"week": sorted(o_week.values(), key=lambda x: -x["v"]), "days": o_days, "buyback_share": share},
        "buybacks": bbj, "checks": checks, "us": {"nasdaq_week_pct": None, "sox_week_pct": None, "notes": []}, "news": [],
    }


def print_script(out: dict) -> None:
    print("제목:", out["title"])
    print("첫 화면:", " / ".join(out["hook_parts"]), f"  (훅 유형 {out['hook_type']})")
    for s in out["scenes"]:
        print(f"\n[{s['id']}] 약 {est_sec(s['tts']):.0f}초 (min {s['min']}s)  ask: {s['ask'] or '-'}")
        print(s["tts"])
    print(f"\n예상 길이 약 {out['est_sec']:.0f}초 (목표 {TARGET_SEC:.0f}초, 뺀 문장 {out['dropped'] or '없음'})")
    print("\n── Threads ──")
    print(out["threads"])
    print(f"({len(out['threads'])}자" + ("" if len(out["threads"]) >= TH_AIM_CHARS else f", 목표 {TH_AIM_CHARS}자보다 짧음 — 붙일 문단이 없는 주") + ")")
    print("── 첫 답글 ──")
    print(out["threads_reply"])


def _selftest(W: dict, NEWS) -> bool:
    """문형 돌리기(다음 몇 주 가정)와 다른 모양의 주(하락 주·뉴스 없음·4일 주)에서도 검사가 비는지."""
    global PREV_OVERRIDE
    ok = True
    prev = None
    for k in range(4):
        w2 = copy.deepcopy(W)
        d0 = _dt(w2["days"][0]) + timedelta(days=7 * k)
        shift = lambda d: (_dt(d) + timedelta(days=7 * k)).strftime("%Y%m%d")  # noqa: E731
        w2["days"] = [shift(d) for d in w2["days"]]
        for sec in (w2["kospi"]["days"], w2["inv"]["days"], [x for t in w2["themes"]["week"] for x in t["days"]], w2["others_stocks"]["days"], w2["checks"]):
            for x in sec:
                x["d"] = shift(x["d"])
        w2["week_start"], w2["week_end"], w2["build_date"] = w2["days"][0], w2["days"][-1], shift(W["build_date"])
        w2["next_q"] = _next_q(W, W["inv"].get("streak_end") or {})
        n2 = copy.deepcopy(NEWS)
        for e in (n2.get("events") if isinstance(n2, dict) else n2) or []:
            e["d"] = shift(str(e.get("d")))
        PREV_OVERRIDE = prev or {}
        o = build_weekly(w2, n2)
        same = [s for s, i in o["picks"].items() if prev and prev["picks"].get(s) == i]
        print(f"  주 +{k} (ISO {d0.isocalendar()[1]}): issues {len(o['issues'])} | 지난주와 같은 문형 {len(same)}개 {same[:6]}")
        for x in o["issues"]:
            print("     ", x)
        ok &= not o["issues"] and (k == 0 or len(same) <= 2)
        prev = o
    # 다른 모양: 부호를 뒤집은 하락 주, 뉴스·자사주·확인 없음, 4일짜리 주
    variants = []
    w3 = copy.deepcopy(W)
    for x in w3["inv"]["days"]:
        for kk in ("indiv", "foreign", "inst", "others"):
            x[kk] = -x[kk]
    w3["inv"]["week"] = {kk: -v for kk, v in w3["inv"]["week"].items()}
    pcl = w3["kospi"]["prev_close"]
    for x in w3["kospi"]["days"]:
        x["chg_pct"] = -x["chg_pct"]
        x["close"], x["high"], x["low"] = 2 * pcl - x["close"], 2 * pcl - x["low"], 2 * pcl - x["high"]
    w3["kospi"]["week_chg_pct"] = -w3["kospi"]["week_chg_pct"]
    for t in w3["themes"]["week"]:
        t["net"] = -t["net"]
        for x in t["days"]:
            x["net"] = -x["net"]
    w3["others_stocks"] = {"week": [], "days": [], "buyback_share": None}
    w3["checks"] = [dict(c, ok=True) for c in w3["checks"]]
    variants.append(("하락 주·자사주 없음", w3, None))
    w4 = copy.deepcopy(W)
    w4["checks"] = []
    variants.append(("뉴스·확인 없음", w4, {"events": []}))
    w5 = copy.deepcopy(W)
    drop = w5["days"][2]
    w5["days"] = [d for d in w5["days"] if d != drop]
    w5["kospi"]["days"] = [x for x in w5["kospi"]["days"] if x["d"] != drop]
    w5["inv"]["days"] = [x for x in w5["inv"]["days"] if x["d"] != drop]
    w5["inv"]["week"] = {kk: sum(x[kk] for x in w5["inv"]["days"]) for kk in ("indiv", "foreign", "inst", "others")}
    variants.append(("4일짜리 주", w5, NEWS))
    for name, wx, nx in variants:
        PREV_OVERRIDE = {}
        o = build_weekly(wx, nx)
        print(f"  {name}: 훅 {o['hook_type']} | 약 {o['est_sec']:.0f}초 | issues {len(o['issues'])}")
        print("     W0:", o["scenes"][0]["tts"])
        print("     제목:", o["title"])
        for x in o["issues"]:
            print("     ", x)
        ok &= not o["issues"]
    PREV_OVERRIDE = None
    return ok


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    build = next((a for a in sys.argv[1:] if a.isdigit()), "20260912")
    wp = os.path.join(DATA, "weekly", build, "computed_weekly.json")
    np_ = os.path.join(DATA, "weekly", build, "news.json")
    if os.path.exists(wp):
        W = _load(wp)
        print(f"# 입력: {wp}")
    else:
        W = draft_from_daily((_dt(build) - timedelta(days=1)).strftime("%Y%m%d"))
        print("# 입력: computed_weekly.json 없음 → 일간 파일로 만든 메모리 초안(시험용, 파일 안 씀)")
    NEWS = _load(np_) if os.path.exists(np_) else {"events": []}
    print(f"# 뉴스: {np_ if os.path.exists(np_) else '없음'}")
    OUT = build_weekly(W, NEWS)
    print_script(OUT)
    print("\n── 검사 ──")
    print("issues:", OUT["issues"] or "없음")
    print("picks:", OUT["picks"])
    ok = not OUT["issues"]
    if "--selftest" in sys.argv:
        print("\n── 자체 시험 ──")
        ok &= _selftest(W, NEWS)
        print("ALL OK" if ok else "SOMETHING FAILED")
    sys.exit(0 if ok else 1)
