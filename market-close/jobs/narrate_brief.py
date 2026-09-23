"""국장편 v5 '수급 브리핑' 대본 — 경제사냥꾼 7슬롯 장치(정본 docs/SCRIPT_SYSTEM_HUNTER_v1.0.md) 위에 **수급 순서를 매일 고정**한 것.
설계 docs/BRIEF_FORMAT_DESIGN.md §1(장면↔장치↔데이터) · §2(대체 규칙) · §3(계약). 견본 docs/scripts/2026-09-15_brief.md(승인본 문장 그대로는 1,349자 —
검사 상한 1,250자에 맞춰 같은 사실을 더 짧은 문장으로 말한다).

체인은 매일 같다(헌터 1차가 어지러웠던 이유가 날마다 다른 블록을 골랐기 때문):
  s0 모순 후킹 → s1 질문(항상 돈의 행방) → s2 코스피 수급 넷 나열(대변→차단, 네 번째 막대 = 기타법인·자사주)
  → s3a 코스닥 수급 + 지수 둘 + 한 줄 판정 + 어제 콜백 → s3b 돈이 빠진 곳·정체된 곳 → s3c 돈이 들어온 곳(이동 선언 1회, 비율)
  → s4 종목 둘(직접 열어봤습니다 + 계산 1개 검산) → s5 뉴스와 맞물렸나(양면 프레임 고정 → 판정 → 뒤집히는 조건 → S0 콜백 → 한계)
  → s6 내일 포인트 2~3 + 이벤트 시각 + 애프터마켓 + 시그니처.

코드가 지키는 것:
  - 대사는 매일 새로: 틀 문장마다 후보 3벌 이상, script_memory.pick(문장 단위 회피) + attempt 회전. 시그니처만 고정.
  - 이어지는 사실은 처음 말하듯 하지 않는다: 외국인 '닷새째', 기타법인 '9월 들어 매일/N일째', 유출 업종 'N일째', 유입 '이틀째'(script_memory.continuity).
  - 한 문장 숫자 ≤2(qa_script.num_tokens 기준), 100억 단위(narrate_hunter.hwon), 부호를 말한다. 그런데는 블록당 1회, 화면 지시어 ≥4.
  - 종목 추천·목표주가·전망 없음. '여러분'·자기 영상 언급 없음. 마지막 문장은 관측값. 길이 950~1,250자: 넘치면 선택 문장을 GLOBAL_DROP 순서로 빼고,
    그래도 넘치면 짧은 후보 + 압축 뉴스(이슈 메모 키워드 한 줄)로 한 번 더 만든다.
  - 데이터가 없어도 장면을 비우지 않는다(§2 대체 규칙 — 각 _sX 함수 주석).
BRIEF_FIX_2(JJ 2026-09-16 아침)가 더한 네 가지 — 이 칸들은 길이 예산에서 빼지 않는다(GLOBAL_DROP 에 없다):
  A 어제 숙제의 답을 빠짐없이(s3a) — watch[0] 은 ledger 도장(promise), watch[1] 부터는 _verify_watch 가 오늘 숫자로 직접 판정(promise2·promise3).
    판정할 수 없는 질문 꼴이면 그 문장은 아예 말하지 않는다(틀린 답보다 침묵).
  B 흐름 방향 한 줄(s5 flow, 판정 뒤·조건 앞) — _flow_score 가 −3~+3 으로 재고 등급마다 다른 문장 + 근거 한 마디(이미 말한 숫자만 되쓴다).
    돈의 흐름에 대한 판정이지 매매 판단이 아니다(사라·팔아라·비중·관망·전망 없음, 주어는 돈·흐름·수급).
  C '내일도 같은 자리'(s6 watch_same) — script_memory.continuity 의 promise_days 가 2 이상이면 첫 관측값 앞에 한 줄.
    장부 문장('{주체} {순매수|순매도}가 {N일째} 이어지는지')은 따로 떨어진 한 문장 그대로 둔다 — ledger.parse_q 가 읽는다.
  D 이슈와 수급을 잇는다 — s3c issue(유입 업종 안의 이슈 종목), s4 row(이슈 종목 표시, s3c 가 이미 말했으면 생략), s5 판정(이슈 라벨이 업종과 다르면 둘 다).
헌터의 hwon/hshort/Picker/J/subj/obj/_was/ro/_callback/_s0/_next_event/_ob_word/_calc 는 import 해 재사용한다(복사 금지).
반환은 narrate_hunter.build 와 같은 키(build_aplus 호환) + format="brief" + hunter(화면용 사전, 장면마다 steps).
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from narrate import _and, _bat, _won_screen, ro
import narrate_aplus as na
import narrate_hunter as nh
import script_memory as sm
from narrate_hunter import (J, Picker, _calc, _callback, _choose, _ctx, _day_word, _next_event, _ob_word, _recent_ids, _steps, _text,
                            _was, dko, han, hshort, hwon, obj, pct1, pct1_dir, pct_s, sgn_pct, subj, updn)

try:
    import qa_script as _qa
except Exception:  # noqa: BLE001 — 검사 모듈이 없어도 대본은 나간다
    _qa = None

AFTER_MARKET_NOTICE_UNTIL = na.AFTER_MARKET_NOTICE_UNTIL
NAME_KEY = na.NAME_KEY
TOTAL_MAX, TOTAL_MIN = 1300, 950   # 1,300자 ≈ 177초(브리핑 실측 초당 7.32~7.35자: 9/15 1,241자=169.6초, 9/16 1,183자=161.0초) — 쇼츠 한계 180초, 우리 상한 172초.
                                   # 2026-09-17 1,200→1,300: JJ "시간이 우리에겐 필요 없어, 정보형 쇼츠야" — 내용을 줄이지 않는다. 유튜브 쇼츠 3분(180초) 선만 지킨다
MONEY_MIN = 500     # 억 — 이 아래면 '들어온 큰손 돈은 작았다'(JJ 9/15 판정: 로봇 380억은 뉴스 쪽, 이차전지 940억은 돈 쪽)
COUNT_WORD = {1: "하나", 2: "둘", 3: "셋", 4: "넷"}
# 말할 때 줄이는 업종 이름(화면은 원래 이름)
SPOKEN_THEME = {"원전/에너지": "원전", "바이오/제약": "바이오", "인터넷/게임": "인터넷·게임", "전력/유틸": "전력"}
# 뉴스 문장을 업종에 붙일 때 보는 낱말(업종 이름·구성 종목 이름은 자동으로 더한다)
THEME_KW = {"이차전지": ["배터리", "CATL", "전지", "양극재", "리튬"], "로봇": ["로봇", "AI 전환", "제조업 AI", "제조AI", "휴머노이드", "자동화"],
            "반도체": ["반도체", "HBM", "엔비디아", "메모리", "파운드리"], "방산": ["방산", "무기", "국방", "수출 계약"], "조선": ["조선", "선박", "수주"],
            "금융": ["금융", "은행", "지주"], "바이오/제약": ["바이오", "제약", "신약", "임상"], "자동차": ["자동차", "전기차", "완성차"],
            "원전/에너지": ["원전", "원자력", "에너지"], "건설": ["건설", "주택", "재건축"], "철강": ["철강", "관세", "포스코"], "화장품": ["화장품", "뷰티"],
            "엔터": ["엔터", "아이돌", "음원"], "인터넷/게임": ["게임", "인터넷", "포털"], "통신": ["통신", "요금"], "전력/유틸": ["전력", "변압기", "전선"],
            "해운": ["해운", "운임"], "유통": ["유통", "소비"], "화학": ["화학", "석유화학"]}
_GENERIC_KW = re.compile(r"순매[수도]|금리|FOMC|코스피|코스닥|급락|급등|강세|약세|관련주|외국인|기관|개인")
# 슬롯 자수 예산(적어 두는 값) — 헌터 것을 그대로 쓰되 s3a 는 +40(어제 숙제의 답이 항목 수만큼 들어간다, BRIEF_FIX_2 §A-4).
# 브리핑은 헌터의 슬롯별 _fit 을 부르지 않고 아래 GLOBAL_DROP 으로만 줄인다 — 그래서 §A-4 의 상쇄는 이 표가 아니라
# GLOBAL_DROP 순서로 한다(s3a verdict 를 앞쪽으로, s3c names·s3b sum·s3c move 를 뒤쪽에 더했다). lint() 는 헌터의 예산 경고를 걸러 낸다.
CAPS = {**nh.CAPS, "s3a": nh.CAPS.get("s3a", 150) + 40}
# 선택 단계 — 전체가 1,250자를 넘으면 앞에서부터 뺀다. 뒤쪽 것(콜백·소개)은 마지막 수단
# s3a 한 줄 판정(verdict)은 어제 숙제의 답이 들어온 만큼 앞쪽(먼저 빠지는 자리)으로 옮겼다(BRIEF_FIX_2 §A-4).
GLOBAL_DROP = [("s5", "news_x"), ("s3a", "verdict"), ("s3c", "issue"), ("s3b", "meaning"), ("s3c", "ratio_2"), ("s3b", "others2"), ("s3a", "turn"),
               ("s2", "inst_streak"), ("s3c", "streak"),
               ("s4", "driver"), ("s6", "note"), ("s5", "limit"), ("s3b", "y"), ("s6", "intro"),
               ("s5", "callback"), ("s5", "news:1"), ("s3a", "weekend"), ("s3c", "t2_sum"), ("s2", "week"), ("s5", "ab"), ("s3c", "t1_sum"), ("s2", "top"),
               ("s5", "macro_3"), ("s5", "macro_1"), ("s5", "verdict:1"), ("s5", "issue:1"), ("s4", "open_2"), ("s2", "size"), ("s2", "turn_2"), ("s3c", "names"), ("s3b", "support"), ("s3b", "sum"), ("s3c", "ratio"), ("s2", "reveal"), ("s5", "macro_2"), ("s4", "calc"), ("s5", "b"),
               # 마지막 수단(여기까지 와도 1,300자를 넘는 날만): 금리 금융 연결 → 자사주 조기 종료. 넘치면 검사 실패 → A+ 폴백이라 그보다 낫다
               ("s5", "bond"), ("s5", "macro_link"), ("s3b", "support_2"),
               # 2026-09-24: 9/23·9/24 에 **뺄 수 있는 칸이 0개**라 14~17자 초과로 A+ 폴백이 났다.
               # 위 목록이 옛 단계 이름만 가리켜서 실제 대본과 하나도 안 맞았다. 실제로 나오는 칸을 맨 뒤에 둔다.
               # 순서 = 덜 아픈 것부터: 대장주 반응 → 흐름의 이유 → 콜백의 이유 → 둘째 유입 업종 수급.
               ("s3b", "turn"), ("s5", "flow_2"), ("s3a", "promise2_2"), ("s3c", "t2")]
# JJ 2026-09-15 가 매일 요구한 칸은 예산에서 절대 빼지 않는다(그래서 위 목록에 없다 — BRIEF_FIX_1 §A):
#   코스닥 개인(s3a kosdaq_2) · 종목별 개인·거래대금(s4 row:0_3 · row:1_3) — "외국인 개인 기관 이것도 샀는지 팔았는지 알려주고"
#   둘째 유입 업종 수급(s3c t2) · 자사주 받침(s3b support) · 다음 이벤트(s6 event) — 빼면 s6 이 '…는지.'로 끝나 검사도 실패한다.
#   장면을 잇는 문장 — s3b q(→ s3c), s3c move(그 답), s5 lead('오늘 주요 이슈를 보겠습니다'), s5 verdict_why(영향의 근거) — JJ 2026-09-17:
#   "앞 장면과 지금 장면이 이어지지 않으면 사람들은 끝까지 안 본다."
#   유출 2·3위 업종(s3b others) — JJ 2026-09-16: "왜 반도체만 말해? 다른 것도 나간 걸 어느 정도 말해 줘야지." 
#   양면 프레임 한쪽(s5 b)은 두 쪽이 다 있어야 뜻이 사니 목록 맨 뒤(마지막으로 빠지는 칸)에 둔다.
#   어제 숙제의 답(s3a promise·promise2·promise3) · 흐름 방향(s5 flow) · '내일도 같은 자리'(s6 watch_same) · 이슈-수급 연결(s3c issue)은
#   BRIEF_FIX_2 가 매일 요구한 칸이라 어떤 경우에도 빼지 않는다.
# 한 장면 안에서 같은 낱말이 세 번을 넘지 않게 — 후보를 고를 때 가벼운 벌점을 준다(BRIEF_FIX_1 §C). '왼쪽·오른쪽'의 쪽은 세지 않는다.
GUARD_WORDS = {"오늘": re.compile("오늘"), "막대": re.compile("막대"), "칸": re.compile("칸"), "쪽": re.compile(r"(?<![왼른양])쪽")}
GUARD_MAX = 3
_DG = re.compile(r"\d[\d,]*(?:\.\d+)?")


# ── 작은 도우미 ──
class ScenePick:
    """장면 하나를 만드는 동안 Picker 를 감싼다 — '오늘·막대·칸·쪽'이 그 장면에서 세 번을 넘게 하는 후보는 먼저 뺀다(BRIEF_FIX_1 §C).
    후보가 전부 걸리면 벌점을 무시하고 원래 후보로 고른다(장면을 비우지 않는다)."""

    def __init__(self, pk: Picker):
        self.pk = pk
        self.n: dict[str, int] = {w: 0 for w in GUARD_WORDS}

    @staticmethod
    def _count(s: str) -> dict[str, int]:
        return {w: len(rx.findall(s or "")) for w, rx in GUARD_WORDS.items()}

    def _over(self, s: str) -> bool:
        c = self._count(s)
        return any(self.n[w] + c[w] > GUARD_MAX for w in GUARD_WORDS)

    def __call__(self, cands: list[str], fallback: str = "") -> str:
        cands = [c for c in cands if c and c.strip()]
        ok = [c for c in cands if not self._over(c)]
        r = self.pk(ok or cands, fallback)
        for w, k in self._count(r).items():
            self.n[w] += k
        return r


_NATIVE_DAYS = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6, "이레": 7, "여드레": 8, "아흐레": 9, "열흘": 10}
_NATIVE_N = {"두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_RX_DAYS = re.compile(r"(하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)(째| 연속)")
_RX_TIMES = re.compile(r"(?<![가-힣])(두|세|네|다섯|여섯|일곱|여덟|아홉|열) 배")


def plain(s: str) -> str:
    """JJ 2026-09-17: "엿새째 닷새째 이런 단어들 쓰지 말고 6일 5일 이런 쉬운 단어만." — 우리말 수사를 숫자로."""
    if not s:
        return s
    s = _RX_DAYS.sub(lambda mm: f"{_NATIVE_DAYS[mm.group(1)]}일{mm.group(2)}", s)
    return _RX_TIMES.sub(lambda mm: f"{_NATIVE_N[mm.group(1)]}배", s)


def dko(n: int) -> str:            # narrate_hunter.dko(우리말 수사)를 이 모듈 안에서 덮는다
    return f"{n}일째"


class NoScreenPick:
    """Picker 를 감싼다 — 화면을 말로 설명하는 후보(막대·칸·카드·도장·왼쪽·오른쪽·보세요)는 먼저 뺀다(JJ 2026-09-16).
    화면은 말에 맞춰 알아서 켜지니 말로 가리키지 않는다. 전부 걸리면 원래 후보로 고르고 검사(check_brief)가 잡는다."""

    def __init__(self, pk: Picker):
        self.pk = pk

    def __getattr__(self, k):
        return getattr(self.pk, k)

    def __call__(self, cands: list[str], fallback: str = "") -> str:
        cands = [plain(c) for c in cands if c and c.strip()]
        ok = [c for c in cands if not _qa.SCREEN_TALK.search(_qa.strip_quotes(c)) and not _qa.JARGON.search(_qa.strip_quotes(c))]
        return self.pk(ok or cands, fallback)


def tname(th: str | None) -> str:
    """말하는 업종 이름 — '원전/에너지' → '원전'."""
    return SPOKEN_THEME.get(th or "", th or "")


def pct2(v: float | None) -> str:
    """원문 표의 등락 그대로(소수 2자리, 끝 0은 뗀다): 3.98→'3.98%', 29.8→'29.8%', 0.2→'0.2%'. S4 종목 칸에만 쓴다(1차 자료 = 표 숫자)."""
    if v is None:
        return "미확정"
    return nh.spoken_pct(v)          # 말은 소수 첫째 자리(JJ 2026-09-18) — 화면 표 칸은 원자료 두 자리 그대로


def _ntok(s: str) -> int:
    if _qa is not None:
        try:
            return len(_qa.num_tokens(s))
        except Exception:
            pass
    return len(_DG.findall(s or ""))


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def _word(v: float) -> str:
    return "순매수" if v > 0 else "순매도"


def _verb(v: float) -> str:
    return "샀" if v > 0 else "팔았"


def _sum_stocks(rows: list[dict]) -> dict:
    """flow_day 종목행 → 업종 합(외/기/순·거래대금 가중 등락·순매수 종목 이름·거래대금)."""
    f = sum(_num(r.get("foreign")) or 0 for r in rows)
    i = sum(_num(r.get("inst")) or 0 for r in rows)
    val = sum(_num(r.get("value")) or 0 for r in rows)
    wret = sum((_num(r.get("ret")) or 0) * (_num(r.get("value")) or 0) for r in rows)
    pos = sorted([r for r in rows if (_num(r.get("foreign")) or 0) + (_num(r.get("inst")) or 0) > 0],
                 key=lambda r: -((_num(r.get("foreign")) or 0) + (_num(r.get("inst")) or 0)))
    return {"foreign": round(f), "inst": round(i), "net": round(f + i), "ret": round(wret / val, 2) if val else None, "value": round(val),
            "pos_names": [r.get("name") for r in pos if r.get("name")], "n": len(rows), "stocks": rows}


# ══════════════════════════════════════════════════════════════════════════════
# 어제 숙제의 답 — 어제 편 watch 를 오늘 숫자로 직접 판정한다(BRIEF_FIX_2 §A)
# watch[0] 은 ledger 가 판정한 callback(도장)을 그대로 쓰고, watch[1] 부터가 여기로 온다.
# ══════════════════════════════════════════════════════════════════════════════
_W_KOSDAQ = re.compile(r"^코스닥 (외국인|기관|개인) (순매수|순매도)가")
_W_KEEP = re.compile(r"^(외국인|기관|개인|기타법인) (순매수|순매도)가 (.+?)[을를] 지키는지$")
_W_INV = re.compile(r"^(외국인|기관|개인|기타법인) (순매수|순매도)가 (?:(\S+) )?이어지는지$")
_W_TH = re.compile(r"^(.+?) (순매수|순매도)가 (?:(\S+) )?이어지는지$")
_KQ_KEY = {"외국인": "foreign", "기관": "inst", "개인": "indiv"}


def _won_num(s: str) -> float | None:
    """말로 쓴 금액 → 억 단위 숫자. '1조 4,000억'→14000 · '9천억'→9000 · '940억'→940. 못 읽으면 None."""
    t = (s or "").replace(",", "")
    v, hit = 0.0, False
    if m := re.search(r"(\d+(?:\.\d+)?)\s*조", t):
        v, hit, t = v + float(m.group(1)) * 10000, True, t[m.end():]
    if m := re.search(r"(\d+(?:\.\d+)?)\s*천억", t):
        v, hit = v + float(m.group(1)) * 1000, True
    elif m := re.search(r"(\d+(?:\.\d+)?)\s*억", t):
        v, hit = v + float(m.group(1)), True
    return v if hit else None


def _prev_watch(d: str, prev_date: str | None) -> list[str]:
    """어제 편이 남긴 '내일 볼 것' 질문들(data/<전 거래일>/computed_kr.json 의 watch). 없으면 빈 목록."""
    try:
        from _common import DATA, load_json
    except Exception:  # noqa: BLE001
        return []
    seen: list[str] = []
    for pd in [p for p in (prev_date, nh._prev_weekday(d)) if p]:
        if pd in seen:
            continue
        seen.append(pd)
        try:
            c = load_json(DATA / pd / "computed_kr.json") or {}
        except Exception:  # noqa: BLE001
            continue
        qs = [str(w.get("q")).strip() for w in (c.get("watch") or []) if isinstance(w, dict) and w.get("q")]
        if qs:
            return qs
    return []


def _verify_watch(q: str, c: dict, pk=None) -> tuple[bool | None, str] | None:
    """어제 숙제 한 줄(q)을 오늘 숫자로 판정한다. c 는 bctx() 가 만든 오늘 사실.
    반환 (이어졌나, 말할 문장) — 질문 꼴을 못 읽거나 오늘 숫자가 없으면 None 이고, 그러면 그 문장은 **아예 말하지 않는다**(틀린 답보다 침묵).
    pk 는 ScenePick/Picker — 주면 후보 넷 이상에서 고른다(없으면 첫 후보)."""
    q = (q or "").strip().rstrip(".")
    if not q:
        return None
    ch = pk or (lambda cands, fallback="": next((x for x in cands if x), fallback))
    vals = c.get("vals") or {}
    # ① 코스닥 주체 — investors.kosdaq
    if m := _W_KOSDAQ.match(q):
        who, word = m.group(1), m.group(2)
        v = _num((c.get("kq") or {}).get(_KQ_KEY[who]))
        if v is None or not c.get("kq_ok"):
            return None
        ok, V = (v > 0) == (word == "순매수") and v != 0, hwon(v)
        if ok:
            return ok, ch([f"코스닥 {who} {word}도 오늘 이어졌습니다. {V}입니다.", f"코스닥에서도 {J(who)} 같은 방향입니다. {V} {word}.",
                           f"코스닥 {who}는 오늘도 {word}, {V}입니다.", f"코스닥 쪽 답도 이어짐입니다. {who} {V} {word}."])
        return ok, ch([f"코스닥 {who} {word}는 오늘 끊겼습니다. {V} {_word(v)}입니다.", f"코스닥에선 {J(who)} 방향을 바꿨습니다. {V} {_word(v)}.",
                       f"코스닥 쪽 답은 끊김입니다. {who} {V} {_word(v)}.", f"코스닥 {who}는 오늘 {V} {_word(v)}, 끊겼습니다."])
    # ② 선을 지키는지 — investors.kospi[주체] 와 임계값
    if m := _W_KEEP.match(q):
        who, word, amt = m.group(1), m.group(2), m.group(3)
        thr, v = _won_num(amt), _num(vals.get(who))
        if thr is None or v is None:
            return None
        ok, V = (v >= thr) if word == "순매수" else (v <= -thr), hwon(v)
        if ok:
            return ok, ch([f"{J(who)} {amt} 선을 지켰습니다. 오늘 {V}입니다.", f"{amt} 선은 지켜졌습니다. {who} {V}입니다.",
                           f"{J(who)} {amt} 선 위에 남았습니다. 오늘 {V}입니다.", f"{who} {word}는 {amt} 선을 지켰습니다. {V}입니다."])
        return ok, ch([f"{J(who)} {amt} 선을 내줬습니다. 오늘 {V}입니다.", f"{amt} 선은 무너졌습니다. {who} {V}입니다.",
                       f"{J(who)} {amt} 선 아래로 내려왔습니다. 오늘 {V}입니다.", f"{who} {word}는 {amt} 선을 못 지켰습니다. {V}입니다."])
    # ③ 주체 순매수·순매도가 N일째 이어지는지 — investors.kospi[주체] 부호
    if m := _W_INV.match(q):
        who, word = m.group(1), m.group(2)
        v = _num(vals.get(who))
        if v is None:
            return None
        ok, V = (v > 0) == (word == "순매수") and v != 0, hwon(v)
        st = abs(((c.get("streak") or {}).get(NAME_KEY.get(who, "")) or {}).get("streak") or 0)
        tail = f"{V}, {dko(st)}입니다." if st >= 2 else f"{V}입니다."
        if ok:
            return ok, ch([f"{who} {word}는 오늘도 이어졌습니다. {tail}", f"{J(who)} 오늘도 같은 방향입니다. {tail}",
                           f"{who} {word}, 오늘도 그대로입니다. {tail}", f"그 답은 이어짐입니다. {who} {tail}"])
        return ok, ch([f"{who} {word}는 오늘 끊겼습니다. {V} {_word(v)}입니다.", f"{J(who)} 오늘 방향을 바꿨습니다. {V} {_word(v)}입니다.",
                       f"{who} {word}, 오늘 멈췄습니다. {V} {_word(v)}입니다.", f"그 답은 끊김입니다. {who} {V} {_word(v)}."])
    # ④ 업종 순매수·순매도가 N일째 이어지는지 — 업종 표(flows.table_t) 의 net 부호
    if (m := _W_TH.match(q)) and "·" in m.group(1):
        word, themes = m.group(2), c.get("themes") or {}
        got = []
        for th in m.group(1).split("·"):
            key = th if th in themes else next((t for t in themes if tname(t) == th), None)
            net = _num((themes.get(key) or {}).get("net")) if key else None
            if net is None:
                return None
            got.append((tname(key), net))
        ok = all((n > 0) == (word == "순매수") for _, n in got)
        both = ", ".join(f"{t} {hwon(n)}" for t, n in got)
        if not ok:                                            # 방향이 섞였거나 끊긴 날은 숫자마다 방향을 붙인다(부호 없는 '180억'이 산 돈으로 들린다)
            both = ", ".join(f"{t} {hwon(n)} {_word(n)}" for t, n in got)
        if ok:
            return ok, ch([f"{m.group(1)} {word}는 오늘도 이어졌습니다. {both}입니다.", f"{m.group(1)}에는 하루 더 들어왔습니다. {both}입니다."])
        kept = [t for t, n in got if (n > 0) == (word == "순매수")]
        if kept:
            # v7: '중 방산만 이어졌습니다'는 어제를 본 사람만 안다 — 오늘 사실로 말한다(처음 보는 시청자 99.9%)
            rest = [(t, n) for t, n in got if t not in kept]
            rt = "".join(f" {J(t)} {hwon(n)} {_word(n)}로 돌아섰습니다." for t, n in rest[:1])
            kv = next(n for t, n in got if t == kept[0])
            return ok, ch([f"{kept[0]}에는 오늘도 {hwon(kv)}이 들어왔습니다.{rt}", f"{kept[0]}에는 하루 더 돈이 들어왔습니다, {hwon(kv)}입니다.{rt}"])
        return ok, ch([f"{m.group(1)} {word}는 하루 만에 끊겼습니다. {both}입니다.", f"{m.group(1)}는 오늘 돌아섰습니다. {both}입니다."])
    if m := _W_TH.match(q):
        th, word = m.group(1), m.group(2)
        themes = c.get("themes") or {}
        key = th if th in themes else next((t for t in themes if tname(t) == th), None)
        net = _num((themes.get(key) or {}).get("net")) if key else None
        if net is None:
            return None
        ok, tn, T = (net > 0) == (word == "순매수"), tname(key), hwon(net)
        stk = abs(int((themes.get(key) or {}).get("streak") or 0))
        tail = f"{T}, {dko(stk)}입니다." if stk >= 2 else f"{T}입니다."
        if ok:
            return ok, ch([f"{tn} {word}는 오늘도 이어졌습니다. {tail}", f"{J(tn)} 오늘도 같은 색입니다. {tail}",
                           f"{tn} {word}, 하루 더 갔습니다. {tail}", f"그 답은 이어짐입니다. {tn} {tail}"])
        return ok, ch([f"{tn} {word}는 오늘 끊겼습니다. {T} {_word(net)}입니다.", f"{J(tn)} 오늘 막대 색이 바뀌었습니다. {T} {_word(net)}입니다.",
                       f"{tn} {word}, 오늘 멈췄습니다. {T} {_word(net)}입니다.", f"그 답은 끊김입니다. {tn} {T} {_word(net)}."])
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 오늘 돈이 어느 쪽으로 가고 있나 — 점수 −3~+3(BRIEF_FIX_2 §B). 매매 판단이 아니라 **돈의 흐름**에 대한 판정이다.
#   · 주인공(외국인) 오늘 방향: 순매수 +1 / 순매도 −1(연속 사흘 이상이면 ±2)
#   · 어제 숙제 답: 유입 약속 이어짐 +1 / 끊김 −1, 유출 약속 이어짐 −1 / 끊김 +1
#   · 유입 업종 합 ÷ 유출 1위 절대값: 1/3 이상 +1, 1/10 미만 −1
# ══════════════════════════════════════════════════════════════════════════════
def _flow_score(x: dict) -> tuple[int, list[str]]:
    """(점수 −3~+3, 근거 한 마디 후보들). 근거는 **이미 말한 숫자만** 되쓴다(새 숫자 금지)."""
    score = 0
    why: list[tuple[int, str]] = []          # (방향, 문장) — 마지막에 점수와 같은 방향만 남긴다
    frg = _num(x["vals"].get("외국인"))
    st_f = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
    if frg:
        s = 1 if frg > 0 else -1
        score += s * 2 if st_f >= 3 else s
        why.append((s, f"외국인이 {dko(st_f)} {'사고' if frg > 0 else '팔고'} 있어서입니다." if st_f >= 2 else
                   f"외국인이 오늘 {hwon(frg)} {_word(frg)}라서입니다."))
    cb = x["cb"]
    if cb and cb.get("ok") is not None and isinstance(cb.get("check"), dict):
        kind, sign = cb["check"].get("kind"), cb["check"].get("sign")
        inflow = kind in ("theme_continue", "theme_sell_stop") or (kind == "inv_continue" and (sign or -1) > 0)
        ok = bool(cb["ok"])
        cs = (1 if ok else -1) if inflow else (-1 if ok else 1)
        score += cs
        qn = na._q_noun(cb) or "어제 숫자"
        why.append((cs, f"{J(qn)} 오늘도 {'이어져서' if ok else '끊겨서'}입니다." if ok else f"{J(qn)} 오늘 끊겨서입니다."))
    ins, out_t = x["in_ths"], x["out_t"]
    if ins and out_t:
        in_sum = sum(x["themes"][t]["net"] for t in ins)
        r = in_sum / abs(out_t)
        rs = 1 if r >= 1 / 3 else -1 if r < 0.1 else 0
        score += rs
        frac = _calc("fraction", in_sum, out_t)
        on = tname(x["out_th"])
        why.append((rs, f"들어온 돈이 {on}에서 나간 돈의 {frac['n']}분의 1뿐이라서입니다." if frac else
                   (f"들어온 돈이 {on}에서 나간 돈의 {round(r * 100)}%라서입니다." if r < 2 else f"들어온 돈이 {on}에서 나간 돈의 {round(r)}배라서입니다.")))
    score = max(-3, min(3, score))
    same = [t for sg, t in why if sg and (sg > 0) == (score > 0)] if score else [t for _, t in why]
    return score, same


_FLOW_TXT = {
    2: ["들어오는 돈이 나가는 돈보다 커지고 있습니다.", "사는 돈이 파는 돈을 넘어서고 있습니다.", "돈이 들어오는 힘이 더 셉니다.",
        "사들이는 규모가 점점 커지고 있습니다.", "흐름만 보면 돈은 들어오는 중입니다.", "들어오는 돈이 나간 자리를 채워 가고 있습니다."],
    1: ["조금이지만 들어오는 돈이 더 컸습니다.", "크지는 않아도 사는 돈이 조금 더 많았습니다.", "약하게나마 돈이 들어온 하루였습니다.",
        "들어오는 돈이 아주 조금 더 많았습니다.", "받는 힘이 조금 더 셌습니다.", "흐름은 살짝 들어오는 쪽으로 기울었습니다."],
    0: ["들어온 돈과 나간 돈이 비슷했습니다.", "사는 돈과 파는 돈이 팽팽했습니다.", "아직 어느 한쪽으로 기울지 않았습니다.",
        "들어온 돈과 나간 돈이 서로 지운 하루입니다.", "돈의 방향은 아직 정해지지 않았습니다.", "사는 힘과 파는 힘이 비슷한 하루였습니다."],
    -1: ["들어온 돈이 나간 돈을 다 받아내지는 못했습니다.", "산 돈보다 판 돈이 조금 더 컸습니다.", "나가는 돈이 조금 더 많았던 하루입니다.",
         "들어온 돈만으로는 나간 자리를 다 메우지 못했습니다.", "파는 힘이 아주 조금 더 셌습니다.", "흐름은 살짝 빠져나가는 쪽으로 기울었습니다."],
    -2: ["아직은 나가는 돈이 더 큽니다.", "돈이 빠져나가는 힘이 아직 더 셉니다.", "들어오는 돈보다 나가는 돈이 아직 많습니다.",
         "아직은 판 돈이 산 돈보다 큽니다.", "흐름만 보면 돈은 아직 빠져나가는 중입니다.", "나가는 돈이 들어오는 돈을 아직 누르고 있습니다."],
}


def _effect(x: dict, th: str, r: dict, side: str, has_news: bool, second: bool = False) -> tuple[str, str]:
    """이슈가 시장에 준 영향 — (판정 한 문장, 근거 한 문장). 추상어('돈이 움직인 하루') 대신 누가 얼마를 샀는지 그대로.
    JJ 2026-09-17: "돈이 움직이는 하루? 너무 추상적이고 머리에 직접 오는 단어가 아니야." """
    tn = tname(th)
    fo, io, net = _num(r.get("foreign")) or 0, _num(r.get("inst")) or 0, _num(r.get("net")) or 0
    lead = _leaders(x, th)
    pct = lead[0].get("pct") if lead else None
    if pct is None:
        pct = _num(r.get("ret"))
    up = (pct or 0) > 0
    buyer, bv = ("기관", io) if io >= fo else ("외국인", fo)
    pre = "그리고 " if second else ""
    if side == "b" and up and bv > 0:
        x["verdict_up"] = True
        v = f"{pre}{tn} 상승은 뉴스 때문만이 아니었습니다." if has_news else f"{pre}{J(tn)} 뉴스가 아니라 실제로 사들인 돈이 값을 올렸습니다."
        w = f"앞서 본 대로 {subj(buyer)} {obj(hwon(bv))} 실제로 샀습니다."
        return v, w
    if side == "b":
        v = f"{pre}{J(tn)} 뉴스가 있었지만 값이 밀렸습니다." if has_news else f"{pre}{J(tn)} 값이 밀렸습니다."
        w = f"외국인과 기관이 합쳐 {obj(hwon(abs(net)))} 팔았기 때문입니다." if net < 0 else ""
        return v, w
    v = f"{pre}{J(tn)} 뉴스에 올랐습니다." if up else f"{pre}{J(tn)} 뉴스가 값을 움직였습니다."
    w = f"외국인과 기관이 산 돈은 {hwon(net)}뿐이었습니다." if net > 0 else "외국인과 기관은 오히려 팔았습니다."
    return v, w


def _say_side(tn: str, side: str, ilab: str = "", second: bool = False, same: bool = True, short: str = "") -> list[str]:
    """업종 판정 한 문장 후보 — side 'b' 는 돈이 올린 값, 'a' 는 뉴스가 올린 값.
    **후보 하나 = 한 문장**(화면 단계 steps 가 문장 수와 맞아야 한다). short 는 '…고, {short}.' 로 한 문장 안에 잇는다.
    ilab 이 있으면 이슈 라벨을 앞에 붙이고(BRIEF_FIX_2 §D-3), second 면 둘째 업종 꼴('…도' / '반면 …')."""
    money = side == "b"
    lo = "뉴스" if money else "돈"
    hi_s = "돈이" if money else "뉴스가"
    hi_x = "수급이" if money else "뉴스가"
    first = "기사보다 돈이" if money else "돈보다 기사가"
    # (끝이 '습니다.' 인 꼴, 끝을 '고, {short}.' 로 바꿀 줄기) 짝
    stems = [(f"{J(tn)} {lo}보다 {hi_s} 움직인 하루였습니다.", f"{J(tn)} {lo}보다 {hi_s} 움직였"),
             (f"{tn} 값은 {lo}보다 {hi_x} 만들었습니다.", f"{tn} 값은 {lo}보다 {hi_x} 만들었"),
             (f"{J(tn)} {first} 먼저 움직였습니다.", f"{J(tn)} {first} 먼저 움직였"),
             (f"{tn}에선 {lo}보다 {hi_s} 값을 움직였습니다.", f"{tn}에선 {lo}보다 {hi_s} 값을 움직였"),
             (f"{tn} 흐름은 {lo}보다 {hi_s} 만들었습니다.", f"{tn} 흐름은 {lo}보다 {hi_s} 만들었"),
             (f"결국 {tn} 값을 움직인 건 {lo}보다 {hi_s[:-1]}였습니다." if not money else f"결국 {tn} 값을 움직인 건 뉴스보다 돈이었습니다.",
              f"{J(tn)} {lo}보다 {hi_s} 값을 끌었")]
    if second and same:
        stems = [(f"{tn}도 {lo}보다 {hi_s} 움직였습니다.", f"{tn}도 {lo}보다 {hi_s} 움직였"),
                 (f"{tn} 역시 {lo}보다 {hi_x} 값을 만들었습니다.", f"{tn} 역시 {lo}보다 {hi_x} 값을 만들었"),
                 (f"{tn}도 {hi_s} 먼저 움직였습니다.", f"{tn}도 {hi_s} 먼저 움직였"),
                 (f"{tn}도 같은 모습입니다. {lo}보다 {hi_s} 움직였습니다.", f"{tn}도 {lo}보다 {hi_s} 값을 끌었")]
        stems = [stems[0], stems[1], stems[2], (f"{tn}도 {lo}보다 {hi_s} 값을 끌었습니다.", stems[3][1])]
    elif second:
        stems = [("반면 " + a, "반면 " + b) for a, b in stems[:4]]
    elif ilab:
        stems = [(f"{ilab} 가운데 " + a, f"{ilab} 가운데 " + b) for a, b in stems[:4]]
    if short:
        return [f"{b}고, {short}." for _, b in stems]
    return [a for a, _ in stems]


def _flow_grade(n: int) -> int:
    return 2 if n >= 2 else -2 if n <= -2 else n


# ── 오늘 이슈와 수급을 잇는다(BRIEF_FIX_2 §D) ──
def _issue_names(x: dict) -> list[str]:
    """raw/event.json 의 이슈 종목 이름들."""
    return [str(s.get("name")) for s in (x.get("ev_st") or []) if isinstance(s, dict) and s.get("name")]


def _issue_lab(x: dict, th: str | None) -> str:
    """이슈 라벨이 이 업종과 다르면 그 라벨, 같거나 없으면 빈 문자열 — 다를 때만 s5 판정에 둘 다 붙인다(§D-3)."""
    ev = x.get("ev") or {}
    lab = str(ev.get("group") or ev.get("label") or "").strip()
    if not lab or not th or th in lab or tname(th) in lab:
        return ""
    return lab


# ══════════════════════════════════════════════════════════════════════════════
# 오늘 사실 — 헌터 _ctx 위에 브리핑이 더 쓰는 것(업종 표 전체·종목행·종목 둘·뉴스)
# ══════════════════════════════════════════════════════════════════════════════
def bctx(c: dict) -> dict:
    x = _ctx(c)
    fd = c.get("flow_day") if isinstance(c.get("flow_day"), dict) else {}
    rows_all = [r for r in (fd.get("stocks") or []) if isinstance(r, dict) and r.get("theme")]
    by_theme: dict[str, list[dict]] = {}
    for r in rows_all:
        by_theme.setdefault(r["theme"], []).append(r)
    trows = c.get("theme_rows") if isinstance(c.get("theme_rows"), dict) else {}
    trows_y = c.get("theme_rows_y") if isinstance(c.get("theme_rows_y"), dict) else {}
    moves = {m["theme"]: m for m in x["moves"]}
    themes: dict[str, dict] = {}
    for th in set(x["flows"]) | set(by_theme) | set(trows):
        row = dict(trows.get(th) or {})
        if th in by_theme:
            agg = _sum_stocks(by_theme[th])
            for k in ("foreign", "inst", "net", "ret", "value", "pos_names", "n"):
                row.setdefault(k, agg[k])
            row["value"], row["stocks"] = agg["value"], agg["stocks"]
        m = moves.get(th) or {}
        if "net" not in row:
            row["net"] = x["flows"].get(th, m.get("t"))
        row.setdefault("foreign", m.get("foreign"))
        row.setdefault("inst", m.get("inst"))
        row.setdefault("ret", m.get("ret"))
        row.setdefault("pos_names", m.get("spread_names") or [])
        row["streak"] = m.get("streak")
        row["y"] = (trows_y.get(th) or {}).get("net", (c.get("theme_table_y") or {}).get(th, m.get("y")))
        if _num(row.get("net")) is not None:
            themes[th] = row
    outs = sorted([t for t, r in themes.items() if r["net"] < 0], key=lambda t: themes[t]["net"])
    ins = sorted([t for t, r in themes.items() if r["net"] > 0], key=lambda t: -themes[t]["net"])
    bs = c.get("brief_stocks") if isinstance(c.get("brief_stocks"), dict) else {}
    bstocks = [s for s in (bs.get("stocks") or []) if isinstance(s, dict) and s.get("name")]
    news = [n for n in (c.get("news_items") or []) if isinstance(n, dict) and n.get("title")]
    kq = x["kq"]
    kq_ok = all(isinstance(kq.get(k), (int, float)) for k in ("foreign", "inst", "indiv")) if kq else False
    x.update({"themes": themes, "outs": outs, "ins": ins, "out_th": outs[0] if outs else None, "in_ths": ins[:2],
              "out_t": themes[outs[0]]["net"] if outs else None, "in_t": themes[ins[0]]["net"] if ins else None, "in_th": ins[0] if ins else None,
              "bstocks": bstocks, "btheme": bs.get("theme"), "news": news, "flow_day": fd, "kq_ok": kq_ok,
              "bigcaps": [s for s in (bs.get("bigcaps") or []) if isinstance(s, dict) and s.get("name") and _num(s.get("foreign")) is not None],
              "fomc_prob": _num(c.get("fomc_prob"))})
    return x


# ══════════════════════════════════════════════════════════════════════════════
# S1 단일 질문 — 항상 돈의 행방(틀 5벌 회전, 최근 편 것 제외). 질문 정확히 1개 + '하나만 봅니다' 류 꼬리.
# ══════════════════════════════════════════════════════════════════════════════
# s1 — 훅을 듣고 사람이 실제로 떠올리는 질문 하나(JJ 2026-09-17: "나간 돈을 누가 받았느냐"는 틀린 말 —
# 돈을 받는 게 아니라 판 주식을 누가 샀느냐다). 뒤 꼬리는 '오늘은 이것 하나만 따라가 보겠습니다' → s2 '먼저 코스피부터'로 이어진다.
_Q1_KINDS = ["Q1", "Q2", "Q3"]
_Q1_FIXED = "오늘은 이것 하나만 보겠습니다."     # JJ 2026-09-17: 고정. 다만 한 번씩은 다른 말("과연 누가 샀을까요?")
_Q1_ALT = ["과연 누가 샀을까요?", "답은 수급에 있습니다.", "수급으로 하나씩 확인해 보겠습니다."]


def _q1_tails(d: str, qs: list[str]) -> list[str]:
    """s1 꼬리 후보. 기본은 고정 문장 하나. 최근 올라간 3편의 s1 이 모두 고정 꼬리였으면 이번엔 다른 말(질문에 이미 '누가'가 있으면 그 말은 뺀다)."""
    try:
        from _common import DATA, load_json
        h = load_json(DATA / "script_history.json") or {}
        eds = sorted([e for e in (h.get("editions") or []) if isinstance(e, dict) and str(e.get("date", ""))[:8] < d[:8] and not e.get("draft")],
                     key=lambda e: str(e.get("date")))[-3:]
        s1s = [" ".join(x.get("raw", "") for x in (e.get("sentences") or []) if x.get("scene") == "s1") for e in eds]
        if len(s1s) == 3 and all(_Q1_FIXED[:-1] in t for t in s1s):
            alt = [a for a in _Q1_ALT if not ("누가" in a and any("누가" in q for q in qs))]
            k = sum(ord(ch) for ch in d[:8]) % len(alt)
            return [alt[k]] + [a for a in alt if a != alt[k]]
    except Exception:
        pass
    return [_Q1_FIXED]


_Q1_TAIL = ["오늘은 이것 하나만 따라가 보겠습니다.", "오늘은 이 답 하나만 찾아보겠습니다.", "오늘은 이 질문 하나만 따라가 보겠습니다.",
            "지금부터 이 답을 하나씩 찾아보겠습니다.", "오늘은 이것 하나만 보겠습니다."]


def _q1_cands(kind: str, P: str, sold: bool, chg) -> list[str]:
    if kind == "Q1":
        return ([f"그럼 {subj(P)} 판 주식은 누가 사들였을까요?", f"그렇다면 {subj(P)} 내놓은 주식은 누가 샀을까요?", f"{subj(P)} 이만큼 팔았다면, 산 사람은 누구였을까요?"] if sold else
                [f"그럼 {subj(P)} 산 주식은 누가 내놓았을까요?", f"그렇다면 {subj(P)} 사들인 주식은 누가 팔았을까요?"])
    if kind == "Q2":
        return ([f"그럼 {subj(P)} 판 돈은 어느 업종에서 빠져나갔을까요?", "그렇다면 이 돈은 어느 업종에서 나왔을까요?"] if sold else
                [f"그럼 {subj(P)} 산 돈은 어느 업종으로 들어갔을까요?", "그렇다면 이 돈은 어느 업종으로 갔을까요?"])
    if sold and (chg or 0) > 0:
        return [f"{subj(P)} 이렇게 팔았는데 코스피는 왜 올랐을까요?", "이만큼 팔렸는데도 코스피가 오른 이유는 뭘까요?"]
    if (not sold) and (chg or 0) < 0:
        return [f"{subj(P)} 이렇게 샀는데 코스피는 왜 내렸을까요?", "이만큼 사들였는데도 코스피가 내린 이유는 뭘까요?"]
    return _q1_cands("Q1", P, sold, chg)


def _overnight(d: str) -> dict | None:
    """간밤 미국 금리 결정(FOMC). JJ 2026-09-17: "새벽에 나온 FOMC 금리 인상과 매파 발언, 관련 뉴스를 간단하게 언급 —
    이 여파로 피바람이 불면 같이 엮고, 보합이나 상승이면 훅으로 쓰기 좋은 멘트."
    **지어내지 않는다** — 아침 미국편(05:40)이 모은 raw/news_us.json 제목과 computed_us.json 지수로만 말한다.
    같은 결정(인상·인하·동결)을 말하는 제목이 3건 이상일 때만 이벤트로 본다."""
    from collections import Counter
    from _common import DATA, load_json
    try:
        import collect_macro
        if not collect_macro.fomc_last_night(d):      # 간밤이 FOMC 발표일이 아니면 기사가 남아 있어도 말하지 않는다
            return None
    except Exception:
        return None
    n = load_json(DATA / d / "raw" / "news_us.json") or {}
    titles = [str(it.get("title") or "") for it in (n.get("items") or []) if isinstance(it, dict)]
    mac = load_json(DATA / d / "raw" / "news_macro.json") or {}
    mtitles = [str(it.get("title") or "") for it in (mac.get("items") or []) if isinstance(it, dict)]
    fed = [t for t in titles if re.search(r"연준|Fed|FOMC|금리", t)]
    cnt = {"인상": sum(1 for t in fed if re.search(r"금리\s?인상", t)), "인하": sum(1 for t in fed if re.search(r"금리\s?인하", t)),
           "동결": sum(1 for t in fed if re.search(r"금리\s?동결", t))}
    act, k = max(cnt.items(), key=lambda kv: kv[1])
    if k < 3:
        return None
    yrs = Counter(int(m.group(1)) for t in fed for m in [re.search(r"(\d+)\s?년\s?(?:여\s?)?만", t)] if m)
    y10s = Counter(m.group(1) for t in titles for m in [re.search(r"10년물[^0-9%]{0,10}(\d+(?:\.\d+)?)%\s?(?:돌파|넘)", t)] if m)
    cu = load_json(DATA / d / "computed_us.json") or {}
    idx = cu.get("idx") or {}
    # 오늘 0시 이후 국내 기사(collect_macro) — 여러 매체가 같이 말한 것만(대부분 2건 이상)
    allt = titles + mtitles

    def top(rx: str, need: int = 2, grp=1):
        c = Counter((m.group(grp) if isinstance(grp, int) else tuple(m.group(g) for g in grp))
                    for t in allt for m in [re.search(rx, t)] if m)
        v = c.most_common(1)
        return v[0][0] if v and v[0][1] >= need else None

    bp = top(r"(0\.25|0\.5|0\.50|0\.75)\s?%\s?(?:p|P|포인트)")
    span = top(r"(\d+)\s?년\s?(\d+)\s?개월\s?만", 2, (1, 2))
    gap = top(r"한미\s?금리차[^0-9]{0,12}(\d(?:\.\d+)?)\s?%\s?(?:p|P|포인트)")
    unani = sum(1 for t in allt if "만장일치" in t) >= 2
    quote = sum(1 for t in allt if re.search(r"인플레\S*\s?너무 높고 너무 오래", t)) >= 1
    chair = "워시 의장" if any(re.search(r"워시\s?(?:연준\s?)?의장", t) for t in allt) else "워시"
    fin_up = sum(1 for t in allt if re.search(r"(?:보험|은행|금융)주?\S{0,4}\s?(?:동반\s?)?(?:강세|상승|수혜)", t)) >= 1
    return {"act": act, "years": yrs.most_common(1)[0][0] if yrs else None,
            "bp": bp, "span": (f"{span[0]}년 {span[1]}개월" if span else None), "gap": gap, "unani": unani, "quote": quote, "chair": chair,
            "fin_up": fin_up,
            "more": act == "인상" and sum(1 for t in allt if re.search(r"추가\s?(?:인상|긴축)", t)) >= 2,
            "hawk": sum(1 for t in titles if "매파" in t) >= 2,
            "y10": y10s.most_common(1)[0][0] if y10s and y10s.most_common(1)[0][1] >= 2 else None,
            "dow": _num((idx.get("DJI") or {}).get("pct")), "nasdaq": _num((idx.get("IXIC") or {}).get("pct"))}


def _ov_act(ov: dict) -> str:
    """'3년 만에 금리를 올렸' / '금리를 내렸' / '금리를 그대로 뒀'."""
    v = {"인상": "금리를 올렸", "인하": "금리를 내렸", "동결": "금리를 그대로 뒀"}[ov["act"]]
    return f"{ov['years']}년 만에 {v}" if ov.get("years") and ov["act"] != "동결" else v


def _ov_extra(ov: dict) -> str:
    if ov.get("more"):
        return "추가 인상 신호까지 줬습니다"
    if ov.get("hawk"):
        return "매파 발언까지 나왔습니다"
    return ""


def _macro_hook(x: dict) -> dict | None:
    """코스피가 버티거나 오르면(−0.3% 이상) 부딪히는 훅, 크게 빠지면(−1.5% 이하) 같이 엮는 훅. 그 사이는 s5 에서만 짧게."""
    ov = x.get("ov")
    chg = x.get("chg")
    if not ov or chg is None or ov["act"] == "동결":
        return None
    tight = ov["act"] == "인상"
    verb = {"인상": "올렸", "인하": "내렸"}.get(ov["act"], "")
    if ov.get("bp") and verb:
        l1 = f"간밤 미국 연준이 {'만장일치로 ' if ov.get('unani') else ''}금리를 {ov['bp']}%포인트 {verb}습니다."
    else:
        l1 = f"간밤 미국 연준이 {_ov_act(ov)}습니다."
    if tight and chg >= -0.3:
        mode = "clash"
        l2 = (f"그런데 오늘 코스피는 {pct_s(chg)} 올랐습니다." if chg > 0.05 else f"그런데 오늘 코스피는 {pct_s(chg)}{'밖에 안 내렸' if chg < 0 else ' 그대로였'}습니다.")
    elif tight and chg <= -1.5:
        mode = "hit"
        l2 = f"그리고 다음 날인 오늘, 코스피는 {pct_s(chg)} 빠졌습니다."
    elif (not tight) and chg <= -0.3:
        mode = "clash"
        l2 = f"그런데 오늘 코스피는 {pct_s(chg)} 내렸습니다."
    else:
        return None
    if not re.search(r"\d", l1) and not re.search(r"\d", l2):
        return None
    a = {"label": "미국 금리", "value": (f"{ov['years']}년 만에 {ov['act']}" if ov.get("years") else ov["act"]), "num": -1 if tight else 1, "unit": ""}
    b = {"label": "코스피", "value": sgn_pct(chg), "num": chg, "unit": "%"}
    return {"kind": "MF", "mode": mode, "a": a, "b": b, "pairs": [("a", l1), ("b", l2)], "parts": [l1, l2]}


def _prev_inv(d: str, key: str) -> float | None:
    """직전 거래일 코스피 주체 수급(억) — 저장된 computed_kr.json 에서."""
    from _common import DATA, load_json
    from datetime import datetime, timedelta
    dt = datetime.strptime(d[:8], "%Y%m%d")
    for _ in range(6):
        dt -= timedelta(days=1)
        c = load_json(DATA / dt.strftime("%Y%m%d") / "computed_kr.json")
        if c:
            return _num(((c.get("investors") or {}).get("kospi") or {}).get(key))
    return None


def _week_vals(d: str, key: str) -> list[float]:
    """이번 주 월요일~어제 코스피 주체 수급(억) — 저장된 computed_kr.json 에서. 오늘 값은 부르는 쪽이 더한다.
    주간 누적 합은 말하지 않는다 — 토요일 주간 결산 첫 장면과 같은 얘기가 된다(9/17 밤 검토). 순위(이번 주 가장 적었/많았다)만 쓴다."""
    from _common import DATA, load_json
    from datetime import datetime, timedelta
    dt = datetime.strptime(d[:8], "%Y%m%d")
    out = []
    for k in range(dt.weekday(), 0, -1):
        c = load_json(DATA / (dt - timedelta(days=k)).strftime("%Y%m%d") / "computed_kr.json")
        v = _num(((((c or {}).get("investors") or {}).get("kospi")) or {}).get(key)) if c else None
        if v is not None:
            out.append(v)
    return out


def _said_yesterday(d: str, word: str) -> bool:
    """전 편(가장 최근에 나간 평일편) 대사에 word 가 있었나 — data/script_history.json."""
    try:
        from _common import DATA, load_json
        h = load_json(DATA / "script_history.json") or {}
        eds = [e for e in (h.get("editions") or []) if isinstance(e, dict) and str(e.get("date", ""))[:8] < d[:8]]
        eds.sort(key=lambda e: str(e.get("date")))
        return bool(eds) and word in json.dumps(eds[-1], ensure_ascii=False)
    except Exception:
        return False


def _bb_period(d: str, bb: list) -> dict:
    """자사주 매입 기간(data/buybacks.json) — ends: '11월', early: '삼성전자는 10월 초, SK하이닉스는 10월 중순에'(기사로 확인한 조기 종료 추정이
    오늘 이후일 때만), rows: 화면용 [{name, to, early}]. 한 문장 숫자 2개 이하가 되게 날짜는 '10월 초·중순·말'로 뭉갠다."""
    out = {"ends": "", "early": "", "rows": []}
    try:
        from _common import DATA, load_json
        progs = {pr.get("code"): pr for pr in ((load_json(DATA / "buybacks.json") or {}).get("programs") or [])}
        today = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        months, early = set(), []
        for t in bb:
            pr = progs.get(t.get("code"))
            if not pr or not pr.get("to"):
                continue
            months.add(int(str(pr["to"])[5:7]))
            ee = (pr.get("progress") or {}).get("expected_end")
            ew = ""
            if ee and today <= ee < str(pr["to"]):
                dd = int(ee[8:10])
                ew = f"{int(ee[5:7])}월 {'초' if dd <= 10 else '중순' if dd <= 20 else '말'}"
                early.append(f"{J(pr['name'], '은', '는')} {ew}")
            out["rows"].append({"name": pr["name"], "to": f"{int(str(pr['to'])[5:7])}월 {int(str(pr['to'])[8:10])}일", "early": ew or None})
        out["ends"] = "·".join(f"{m}월" for m in sorted(months))
        if early:
            mons = {e.split()[-2] for e in early}          # '10월' — 두 회사가 같은 달이면 한 번만(길이, 숫자 2개 규칙)
            out["early"] = (f"{mons.pop()} 안에" if len(mons) == 1 and len(early) > 1 else ", ".join(early) + "에")
    except Exception:
        pass
    return out


def _bb_end_months(bb: list) -> str:
    """진행 중 자사주 매입이 끝나는 달(data/buybacks.json) — '11월'. 두 회사가 같은 달이면 한 번만."""
    try:
        from _common import DATA, load_json
        progs = {p.get("code"): p for p in ((load_json(DATA / "buybacks.json") or {}).get("programs") or [])}
        months = sorted({int(str(progs[t["code"]]["to"])[5:7]) for t in bb if t.get("code") in progs and progs[t["code"]].get("to")})
        return "·".join(f"{mm}월" for mm in months)
    except Exception:
        return ""


def _s1(x: dict, pk: Picker, attempt: int) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    kinds = [k for k in _Q1_KINDS if not (k == "Q2" and x.get("s0_names_theme"))]
    kind = _choose(kinds, _recent_ids(d, "devices"), d, attempt)
    qs = _q1_cands(kind, x["P"], x["sold"], x.get("chg"))
    hm = x.get("hook_macro")
    if hm and hm["mode"] == "clash":
        kind = "QM"
        up = (x.get("chg") or 0) > 0
        qs = ([f"미국이 금리를 올렸는데 코스피는 왜 {'올랐' if up else '버텼'}을까요?", f"금리 인상에도 코스피가 {'오른' if up else '버틴'} 이유는 뭘까요?"]
              if hm["a"]["num"] < 0 else [f"미국이 금리를 내렸는데 코스피는 왜 내렸을까요?"])
    elif hm and hm["mode"] == "hit":
        kind = "QM"
        qs = ["그럼 오늘 누가 팔았고, 누가 받아냈을까요?", "그럼 이 하락에 누가 팔고 누가 샀을까요?"]
    elif x.get("hook_mb"):
        kind = "QB"
        qs = ["같은 반도체에서 외국인의 선택이 갈렸습니다. 그럼 오늘 돈은 어디로 갔을까요?",
              "같은 반도체인데 외국인은 한쪽만 샀습니다. 그럼 오늘 돈은 어디로 흘러갔을까요?"]
    tails = _q1_tails(d, qs)
    s = pk([f"{q} {t}" for q in qs for t in tails])
    q = next((q for q in qs if q in s), qs[0])
    tail = next((t for t in tails if t in s), tails[0])
    return [("q", s)], {"q": q, "tail": tail, "text": s, "kind": kind}, kind


# ══════════════════════════════════════════════════════════════════════════════
# S2 대변→차단 + 코스피 수급 나열 — 뻔한 답(N1 개인이 받았다 / N2 기관이 받았다 / N3 외국인이 돌아왔다 / N4 지수 올랐으니 돈이 들어왔다 / N6 새 돈)
# → 외국인(연속일) → 기관·개인, 넷 다 숫자 → '그런데 [화면 지시어] 네 번째 막대' → 기타법인 + 상위 두 종목·자사주 비중 + '9월 들어 매일/N일째'
# → 질문(코스닥은 어땠나). 대체: 기타법인 <3,000억이면 자사주 문장 생략, '기타법인 N억' 한 마디.
# s2 여는 말 — **이 목록에서만 고른다.** 2026-09-23 에 전 편과 겹친다는 검사에 걸리자
# 손으로 "코스피 넷부터 봅니다" 를 지어냈고 JJ가 "이게 뭔 개소리야" 라고 했다. 사람이 안 쓰는 말이었다.
# 겹치면 지어내지 말고 여기에 **자연스러운 한국말**을 더한다(qa_script.S2_OPENS 가 같은 목록을 본다).
S2_OPENS = [
    "먼저 코스피부터 보겠습니다.",
    "코스피부터 하나씩 보겠습니다.",
    "먼저 코스피에서 누가 사고 팔았는지 보겠습니다.",
    "답을 찾으러 코스피부터 보겠습니다.",
    "코스피 수급부터 보겠습니다.",
    "코스피부터 봅니다.",
    "오늘 코스피에선 누가 사고 팔았는지 보겠습니다.",
    "코스피 네 주체부터 보겠습니다.",
    "먼저 코스피 수급을 보겠습니다.",
    "코스피에 들어온 돈부터 보겠습니다.",
    "코스피부터 차례로 보겠습니다.",
    "오늘 코스피 수급부터 보겠습니다.",
]


# ══════════════════════════════════════════════════════════════════════════════
_S2_Q = ["그럼 코스닥은 어땠을까요?", "그럼 코스닥 쪽은 어땠을까요?", "그럼 코스닥도 같은 그림일까요?", "그럼 코스닥에선 누가 샀을까요?",
         "그럼 코스닥 막대는 어느 쪽일까요?", "그럼 코스닥은 어느 쪽일까요?"]


def _s2(x: dict, cont: dict, pk: Picker, attempt: int) -> tuple[list, dict, str]:
    d, P, sold, vals, oth = x["d"], x["P"], x["sold"], x["vals"], x["oth"]
    pk = ScenePick(pk)
    frg, inst, ind = vals.get("외국인"), vals.get("기관"), vals.get("개인")
    st_f = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
    st_i = abs(((x["streak"].get("inst") or {}).get("streak")) or 0)
    # ── 뻔한 답 고르기 ──
    kinds: list[str] = []
    if ind is not None and ind > 0 and sold:
        kinds.append("N1")
    if inst is not None and inst > 0 and sold and P != "기관":
        kinds.append("N2")
    y = cont.get("yesterday") or {}
    if frg is not None and frg > 0 and (y.get("foreign_streak") or 0) < 0:
        kinds.append("N3")
    if x["chg"] > 0 and ((frg or 0) + (inst or 0)) < -1000:
        kinds.append("N4")
    if oth >= 3000 and x["oth_in_bb"] and x["oth_share"] >= 0.6:
        kinds.append("N6")
    if not kinds:
        kinds = ["N1"] if ind is not None else ["N5"]
    kind = _choose(kinds, _recent_ids(d, "devices"), d, attempt)
    pairs: list[tuple[str, str]] = []
    if kind == "N1":
        naive, naive_name = "개인이 받았다", "개인"
        pairs.append(("naive", pk(["개인이 다 받았다고 보이기 쉽습니다.", "받은 쪽은 개인 하나로 읽히기 쉽습니다.", "개인이 받아 낸 날로 보이기 쉽습니다.",
                                   "개인 몫으로만 읽히기 쉽습니다.", "답은 개인이라고 생각하기 쉽습니다.", "판 물량은 개인이 받았다고 보이기 쉽습니다."])))
    elif kind == "N2":
        naive, naive_name = "기관이 받았다", "기관"
        pairs.append(("naive", pk(["기관이 받아 준 날로 보이기 쉽습니다.", "받은 쪽은 기관으로 읽히기 쉽습니다.", "기관이 받쳤다고 읽히기 쉽습니다.", "기관 몫으로 생각하기 쉽습니다.",
                                   "답은 기관이라고 생각하기 쉽습니다.", "기관이 받은 날로 보이기 쉽습니다."])))
    elif kind == "N3":
        naive, naive_name = "외국인이 돌아왔다", "외국인"
        pairs.append(("naive", pk(["외국인이 돌아온 날로 보이기 쉽습니다.", "외국인 매도가 끝났다고 읽히기 쉽습니다.", "외국인 손이 바뀐 날로 읽히기 쉽습니다.",
                                   "외국인이 다시 들어왔다고 보이기 쉽습니다.", "답은 외국인이라고 생각하기 쉽습니다.", "외국인이 돌아섰다고 읽히기 쉽습니다."])))
    elif kind == "N4":
        naive, naive_name = "지수가 올랐으니 돈이 들어왔다", "코스피"
        pairs.append(("naive", pk(["오른 날이니 돈이 들어왔다고 보이기 쉽습니다.", "지수만 보면 큰손이 산 날로 읽히기 쉽습니다.", "올랐으니 돈이 들어왔다고 읽히기 쉽습니다.",
                                   "상승한 날은 받는 손이 컸다고 보이기 쉽습니다.", "답은 지수라고 생각하기 쉽습니다.", "오른 날이니 산 손이 컸다고 읽히기 쉽습니다."])))
    elif kind == "N6":
        naive, naive_name = "새 돈이 들어왔다", "기타법인"
        pairs.append(("naive", pk(["새 돈이 들어온 날로 보이기 쉽습니다.", "기타법인 막대는 바깥 돈으로 보이기 쉽습니다.", "새 돈이 받쳤다고 읽히기 쉽습니다.",
                                   "네 번째 막대가 새 돈으로 보이기 쉽습니다.", "답은 새 돈이라고 생각하기 쉽습니다.", "바깥 돈이 받친 날로 읽히기 쉽습니다."])))
    else:
        naive, naive_name = "한 손이 다 받았다", "개인"
        pairs.append(("naive", pk(["한 손이 다 받았다고 보이기 쉽습니다.", "받은 손이 하나로 읽히기 쉽습니다.", "막대 하나로 끝난 날로 읽히기 쉽습니다.",
                                   "답은 한 손이라고 생각하기 쉽습니다.", "받은 쪽이 하나로 보이기 쉽습니다.", "한 손이 다 받은 날로 보이기 쉽습니다."])))
    # 브리핑은 대변 문장('…보이기 쉽습니다')을 말하지 않는다 — s1 질문 바로 뒤에 뜬금없이 끼어든다(JJ 2026-09-17).
    # 대신 '먼저 코스피부터 보겠습니다'로 질문에 답하러 들어간다. 화면 머리글도 중립 문구로.
    pairs = [("open", pk(S2_OPENS))]
    naive, naive_name = "코스피 누가 샀나", ""
    # ── 코스피 수급: 외국인(어제 약속의 답) → 같은 쪽 → '하지만' 반대쪽(가장 큰 쪽을 마지막에) ──
    # JJ 2026-09-17: "순매도 2개, 순매수 1개 아니냐? 그리고 기타법인 1개." — 판 쪽끼리, 산 쪽끼리 묶어서 논리대로.
    #   "어제 보자고 한 외국인 순매도, 오늘도 이어졌습니다. 6일째 팔고 있고, 오늘만 1조 6,800억을 팔았습니다.
    #    여기에 개인까지 1조 1,900억을 팔았습니다. 하지만 기관이 1조 2,100억을 샀고, 기타법인이 1조 6,600억으로 가장 많이 샀습니다."
    cb = x.get("cb") or {}
    chk = cb.get("check") if isinstance(cb.get("check"), dict) else {}
    cb_frg = bool(cb) and cb.get("ok") is not None and chk.get("kind") == "inv_continue" and chk.get("key") == "foreign"
    obw, ob_capped = _ob_word(cont, d, cont.get("others_buy_days") or 0)
    ob_days = cont.get("others_buy_days") or 0
    top = [{"name": t["name"], "v": t["v"]} for t in x["top_others"]]
    names = _and([t["name"] for t in top]) if top else "두 회사"
    O = hwon(oth)
    is_top = bool(x["buyers"]) and x["buyers"][0][0] == "기타법인"
    days_word = None
    sold_f = frg is not None and frg < 0
    if frg is not None:
        F, act, ing = hwon(frg), _verb(frg), ("팔고" if frg < 0 else "사고")
        if cb_frg:
            x["cb_said"] = True
            # v7(JJ 2026-09-19): 시청자 99.9%가 어제 영상을 안 봤다 — '어제 보자고 한' 대신 처음 보는 사람에게도 사건인 말로.
            if bool(cb["ok"]):
                pairs.append(("bar:외국인", pk([f"외국인은 오늘도 {obj(F)} {act}습니다. {dko(st_f)} {ing} 있습니다.",
                                           f"외국인이 {dko(st_f)} {ing} 있습니다. 오늘만 {obj(F)} {act}습니다.",
                                           f"외국인은 오늘도 {act}습니다. {dko(st_f)}, 오늘만 {F}입니다."])))
            else:
                prev = abs(int(((cont.get("yesterday") or {}).get("foreign_streak")) or 0))
                was = "팔기만" if frg > 0 else "사기만"
                pairs.append(("bar:외국인", pk(([f"{prev}일 동안 {was} 하던 외국인이 오늘은 {obj(F)} {act}습니다.",
                                            f"{prev}일 내내 {was} 하던 외국인이 오늘은 방향을 바꿔 {obj(F)} {act}습니다."] if prev >= 2 else
                                           [f"외국인은 오늘 방향을 바꿔 {obj(F)} {act}습니다."]))))
        elif st_f >= 2:
            pairs.append(("bar:외국인", pk([f"외국인은 오늘도 {obj(F)} {act}습니다. {dko(st_f)} {ing} 있습니다.",
                                       f"외국인은 {dko(st_f)} {ing} 있고, 오늘은 {obj(F)} {act}습니다."])))
        else:
            pairs.append(("bar:외국인", pk([f"외국인은 오늘 {obj(F)} {act}습니다. 방향이 바뀐 첫날입니다.", f"외국인은 방향을 바꿔 오늘 {obj(F)} {act}습니다."])))
    others = [(n, v) for n, v in (("개인", ind), ("기관", inst)) if isinstance(v, (int, float)) and abs(v) >= 0.5]
    same = [(n, v) for n, v in others if (v < 0) == sold_f]
    opp = [(n, v) for n, v in others if (v < 0) != sold_f]
    o_ok = isinstance(oth, (int, float)) and abs(oth) >= 0.5
    if o_ok and (oth < 0) != sold_f:
        opp.append(("기타법인", oth))
    elif o_ok:
        same.append(("기타법인", oth))
    # 이어지는 날 새 관점(JJ·GPT 2026-09-17 "전날과 같은 사실을 새 정보 없이 반복하지 않는다") — 규모(어제 대비) → 이번 주 누적(금요일)
    if frg is not None and st_f >= 2:
        yf = _prev_inv(d, "foreign")
        if yf is not None and (yf < 0) == (frg < 0) and abs(yf) >= 1000:
            r = abs(frg) / abs(yf)
            if r >= 1.2:
                pairs.append(("size", pk([f"어제 {hwon(yf)}보다 {hwon(abs(frg) - abs(yf))} 더 많습니다.", f"어제보다 {hwon(abs(frg) - abs(yf))} 커졌습니다."])))
            elif r <= 0.8:
                pairs.append(("size", pk([f"다만 어제 {hwon(yf)}보다는 {hwon(abs(yf) - abs(frg))} 줄었습니다.", f"그래도 어제보다 {hwon(abs(yf) - abs(frg))} 작아졌습니다."])))
        wk = _week_vals(d, "foreign")
        if len(wk) >= 2 and all((v < 0) == (frg < 0) for v in wk):
            allv = [abs(v) for v in wk] + [abs(frg)]
            if abs(frg) == min(allv):
                pairs.append(("week", pk([f"{len(allv)}일 가운데 이번 주 가장 적게 {_verb(frg)}습니다.", f"이번 주 들어 가장 적은 금액입니다."])))
            elif abs(frg) == max(allv):
                pairs.append(("week", pk([f"{len(allv)}일 가운데 이번 주 가장 많이 {_verb(frg)}습니다.", f"이번 주 들어 가장 큰 금액입니다."])))
    # 같은 쪽(외국인과 같은 방향) — '여기에 개인까지'
    if len(same) == 1:
        n, v = same[0]
        pairs.append((f"bar:{n}", pk([f"여기에 {n}까지 {obj(hwon(v))} {_verb(v)}습니다.", f"{n}도 {obj(hwon(v))} {_verb(v)}습니다."])))
    elif len(same) >= 2:
        (n1, v1), (n2, v2) = same[0], same[1]
        pairs.append((f"bar:{n1}·{n2}", pk([f"여기에 {J(n1, '과', '와')} {n2}까지 각각 {hwon(v1)}, {obj(hwon(v2))} {_verb(v2)}습니다.",
                                   f"{J(n1, '과', '와')} {n2}도 각각 {hwon(v1)}, {obj(hwon(v2))} {_verb(v2)}습니다."])))
        if len(same) >= 3:
            n3, v3 = same[2]
            pairs.append((f"bar:{n3}", pk([f"{n3}도 {obj(hwon(v3))} {_verb(v3)}습니다."])))
    if st_i >= 2 and isinstance(inst, (int, float)) and inst < 0 and any(n == "기관" for n, _ in same):
        pairs.append(("inst_streak", pk([f"기관은 {dko(st_i)} 팔고 있습니다.", f"기관도 {dko(st_i)} 파는 중입니다."])))
    # 반대쪽 — '하지만 기관이 …을 샀고, 기타법인이 …으로 가장 많이 샀습니다' (가장 큰 쪽을 마지막에)
    opp.sort(key=lambda t: abs(t[1]))
    if len(opp) == 1:
        n, v = opp[0]
        most = " 가장 많이" if (n == "기타법인" and is_top) else ""
        pairs.append((f"bar:{n}", pk([f"하지만 {subj(n)} {obj(hwon(v))}{most} {_verb(v)}습니다." if not most else f"하지만 {subj(n)} {ro(hwon(v))} 가장 많이 {_verb(v)}습니다.",
                                  f"그런데 {subj(n)} {obj(hwon(v))} {_verb(v)}습니다." if not most else f"그런데 가장 많이 {_verb(v)[:-1] + '은' if False else ''}{'산' if v > 0 else '판'} 곳은 {n}, {hwon(v)}입니다."])))
    elif len(opp) >= 3:
        # 산 쪽이 셋(9/17: 기관·개인·기타법인) — 한 문장에 숫자 셋은 안 되고, 셋째를 따로 떼면 길이 줄이기에서 빠진다(9/17 기관 누락 → 폴백).
        # JJ 방송 문장 꼴: "하지만 기관이 1,600억, 개인이 4,100억을 샀습니다. 기타법인은 1조 7,000억으로 가장 많이 샀습니다." — 한 칸(turn)에 두 문장.
        (n0, v0), (a_n, a_v), (b_n, b_v) = opp[0], opp[-2], opp[-1]
        most = "가장 많이 " if (b_n != "기타법인" or is_top) else ""
        pairs.append((f"bar:{n0}·{a_n}·{b_n}", pk([f"하지만 {subj(n0)} {hwon(v0)}, {subj(a_n)} {obj(hwon(a_v))} {_verb(a_v)}습니다. {J(b_n)} {ro(hwon(b_v))} {most}{_verb(b_v)}습니다.",
                                  f"하지만 {subj(n0)} {hwon(v0)}, {subj(a_n)} {obj(hwon(a_v))} {_verb(a_v)}습니다. 그리고 {subj(b_n)} {ro(hwon(b_v))} {most}{_verb(b_v)}습니다."])))
    elif len(opp) >= 2:
        # 2026-09-23: 둘을 한 문장에 넣으면 49자가 되어 s2 기타법인 45자 규칙에 걸리고, 세 번 다 같은 문장이 나와
        #             브리핑 포맷이 A+ 로 폴백했다(그날 영상이 684자 다섯 장면으로 떨어졌다).
        #             >=3 갈래처럼 **두 문장으로 나눈다** — 두 번째가 기타법인 막대('top')를 켠다.
        (a_n, a_v), (b_n, b_v) = opp[-2], opp[-1]
        most = "가장 많이 " if (b_n != "기타법인" or is_top) else ""
        pairs.append((f"bar:{a_n}", pk([f"하지만 {subj(a_n)} {obj(hwon(a_v))} {_verb(a_v)}습니다.",
                                  f"그런데 {J(a_n)} {obj(hwon(a_v))} {_verb(a_v)}습니다."])))
        pairs.append((f"bar:{b_n}", pk([f"{J(b_n)} {ro(hwon(b_v))} {most}{_verb(b_v)}습니다.",
                                 f"{subj(b_n)} {ro(hwon(b_v))} {most}{_verb(b_v)}습니다."])))
    # 기타법인 이어짐 — 날마다 달라지는 숫자를 한 문장 안에(겹침 검사)
    if o_ok and oth > 0 and oth >= 3000:
        if is_top and cont.get("top_buyer_days", 1) >= 2:
            n = cont["top_buyer_days"]
            pairs.append(("reveal", pk([f"기타법인은 {dko(n)} 가장 많이 사고 있습니다.", f"가장 많이 산 곳이 기타법인인 것도 {dko(n)}입니다."])))
        elif ob_days >= 2 and not ob_capped:
            days_word = obw
            pairs.append(("reveal", pk([f"기타법인은 {dko(ob_days)} 사고 있습니다.", f"기타법인의 매수는 {dko(ob_days)} 이어졌습니다."[:0] or f"기타법인은 {dko(ob_days)} 사들이고 있습니다."])))
        # 기타법인 얘기는 **한 문장까지**(JJ 2026-09-21 "매일 똑같이 기타법인을 주로 말하면 누가 보겠냐").
        # 위에서 이어짐(reveal) 문장을 이미 냈으면 비중 문장은 내지 않는다 — 9/24 맥 이관 때 두 문장이라 검사에 걸렸다.
        said_oth = any(n in ("reveal",) for n, _ in pairs)
        sh = round(min(1.0, x["oth_share"]) * 100)
        if said_oth:
            pass
        elif top and x["oth_share"] >= 0.5:
            tag = " 자사주" if x["oth_in_bb"] else ""
            if sh >= 98:          # 100%·101% 는 사람이 안 쓰는 말이다 — 숫자 대신 '거의 전부'
                pairs.append(("top_2", pk([f"거의 전부가 {names}{tag}입니다.", f"사실상 {names}{tag} 둘입니다."])))
            else:
                pairs.append(("top_2", pk([f"기타법인이 산 돈의 {sh}%가 {names}{tag}입니다.", f"그중 {sh}%가 {names}{tag}입니다.", f"그 {sh}%는 {names}{tag}였습니다."])))
        elif top:
            pairs.append(("top_2", pk([f"기타법인 돈이 가장 많이 간 곳은 {top[0]['name']}, {hwon(top[0]['v'])}입니다.", f"기타법인이 가장 많이 산 종목은 {top[0]['name']}입니다."])))
    pairs.append(("q", pk(_S2_Q)))
    bars = [{"name": n, "v": vals.get(n), "days": (st_f if n == "외국인" else st_i if n == "기관" else None) or None}
            for n in ("외국인", "기관", "개인") if vals.get(n) is not None]
    s2 = {"naive": naive, "naive_name": naive_name, "naive_v": vals.get(naive_name) if naive_name != "코스피" else x["chg"], "kind": kind, "bars": bars,
          "reveal": {"name": "기타법인", "v": oth, "days": (0 if ob_capped else ob_days), "days_word": days_word, "top": top, "share": round(x["oth_share"] * 100),
                     "kind": "buyback" if x["oth_in_bb"] else "party"},
          "said_share": any(n.startswith("top") and "%" in t for n, t in pairs), "pairs": pairs}
    return pairs, s2, kind


# ══════════════════════════════════════════════════════════════════════════════
# S3a 코스닥 수급 3주체 + 지수 둘 + 한 줄 판정 + 어제 콜백(도장, 월요일은 주말편 것도) + 그런데(크기 변화) + 질문(어느 업종에서 나갔나).
# 대체: 코스닥 수급 없음 → 지수 둘 + 코스피 판정 + 콜백. 어제 약속 없음 → 콜백 대신 외국인 연속일 사실.
# ══════════════════════════════════════════════════════════════════════════════
_S3A_Q = ["그럼 이 돈은 어느 업종에서 빠져나갔을까요?", "그럼 어느 업종에서 가장 많이 팔았을까요?", "그럼 돈은 어느 업종에서 가장 많이 빠졌을까요?",
          "그럼 가장 많이 팔린 업종은 어디였을까요?"]


def _side_words(vals: dict, bb: bool) -> tuple[str, str]:
    sellers = [n for n in ("외국인", "기관", "개인") if (vals.get(n) or 0) < 0]
    buyers = [n for n in ("외국인", "기관", "개인") if (vals.get(n) or 0) > 0]
    if bb:
        buyers.append("자사주")
    return "·".join(sellers), "·".join(buyers)


def _s3a(x: dict, cont: dict, c: dict, pk: Picker) -> tuple[list, dict, list]:
    d, P, sold, amt = x["d"], x["P"], x["sold"], x["amount"]
    kq, kqi, k = x["kq"], x["kqi"], x["k"]
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    kbars = []
    kc0, qc0 = _num(k.get("chg_pct")), _num(kqi.get("chg_pct"))
    if x["kq_ok"] and qc0 is not None:
        # v7: 코스닥은 한 문장 — 가장 크게 움직인 주체 하나 + 지수. 말하지 않는 막대는 화면에도 안 띄운다.
        n_, v_ = max((("외국인", kq["foreign"]), ("기관", kq["inst"]), ("개인", kq["indiv"])), key=lambda t: abs(t[1]))
        kbars = [{"name": n_, "v": round(v_)}]
        V = hwon(v_)
        if v_ < 0 and qc0 > 0:
            s_ = f"코스닥은 {subj(n_)} {obj(V)} 팔아 {pct_s(qc0)} 오르는 데 그쳤습니다."
        elif v_ > 0 and qc0 < 0:
            s_ = f"코스닥은 {subj(n_)} {obj(V)} 샀지만 {pct_s(qc0)} 내렸습니다."
        else:
            s_ = f"코스닥은 {subj(n_)} {obj(V)} {_verb(v_)}고, {pct_s(qc0)} {'올랐' if qc0 > 0 else '내렸' if qc0 < 0 else '제자리였'}습니다."
        pairs.append(("kosdaq", s_))
        if kc0 is not None:
            pairs.append(("index", pk([f"코스피는 {pct_s(kc0)} {'올랐' if kc0 > 0 else '내렸' if kc0 < 0 else '제자리였'}습니다.",
                                       f"코스피는 오늘 {pct_s(kc0)} {'올랐' if kc0 > 0 else '내렸' if kc0 < 0 else '제자리였'}습니다."])))
    if False and x["kq_ok"]:
        fq, iq, dq = kq["foreign"], kq["inst"], kq["indiv"]
        kbars = [{"name": "외국인", "v": round(fq)}, {"name": "기관", "v": round(iq)}, {"name": "개인", "v": round(dq)}]
        opp = isinstance(x["vals"].get("외국인"), (int, float)) and (fq > 0) != (x["vals"]["외국인"] > 0)
        FQ, IQ, DQ = hwon(fq), hwon(iq), hwon(dq)
        rel = "반대로" if opp else "같은 쪽으로"
        if (fq > 0) == (iq > 0):
            pairs.append(("kosdaq", pk([f"코스닥은 외국인이 {FQ}, 기관이 {obj(IQ)} {_verb(fq)}습니다.", f"코스닥에서는 외국인과 기관이 각각 {FQ}, {obj(IQ)} {_verb(fq)}습니다.",
                                        f"코스닥도 외국인이 {FQ}, 기관이 {obj(IQ)} {_verb(fq)}습니다." if not opp else f"코스닥은 반대로 외국인이 {FQ}, 기관이 {obj(IQ)} {_verb(fq)}습니다."])))
        else:
            pairs.append(("kosdaq", pk([f"코스닥은 외국인이 {obj(FQ)} {_verb(fq)}고, 기관은 {obj(IQ)} {_verb(iq)}습니다.",
                                        f"코스닥에서는 외국인이 {obj(FQ)} {_verb(fq)}고, 기관은 {obj(IQ)} {_verb(iq)}습니다.",
                                        f"코스닥은 갈렸습니다. 외국인은 {obj(FQ)} {_verb(fq)}고, 기관은 {obj(IQ)} {_verb(iq)}습니다."])))
        pairs.append(("kosdaq_2", pk([f"개인은 {obj(DQ)} {_verb(dq)}습니다.", f"개인은 {DQ} {_word(dq)}입니다.", f"개인도 {obj(DQ)} {_verb(dq)}습니다." if (dq > 0) == (iq > 0) else f"개인은 {obj(DQ)} {_verb(dq)}습니다."])))
    kc, qc = _num(k.get("chg_pct")), _num(kqi.get("chg_pct"))
    index = [{"name": "코스피", "close": k.get("close"), "chg_pct": kc}, {"name": "코스닥", "close": kqi.get("close"), "chg_pct": qc}]
    if any(t == "index" for t, _ in pairs):
        pass
    elif kc is not None and qc is not None:
        _uv = lambda v: "올랐" if v > 0 else "내렸" if v < 0 else "제자리였"
        pairs.append(("index", pk([f"지수는 코스피가 {pct_s(kc)} {_uv(kc)}고, 코스닥이 {pct_s(qc)} {_uv(qc)}습니다.", f"코스피는 {pct_s(kc)}, 코스닥은 {pct_s(qc)} {_uv(qc)}습니다." if (kc > 0) == (qc > 0) else f"코스피는 {pct_s(kc)} {_uv(kc)}고, 코스닥은 {pct_s(qc)} {_uv(qc)}습니다.",
                                   f"코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}입니다."])))
        if False:
            pairs.append(("index", pk([f"코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}입니다.", f"지수는 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.",
                                   f"코스피 {pct_s(kc)} {updn(kc)}에 코스닥 {pct_s(qc)} {updn(qc)}입니다.", f"지수 둘, 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.",
                                   f"코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}.", f"오늘 코스피 {pct_s(kc)} {updn(kc)}, 코스닥 {pct_s(qc)} {updn(qc)}."])))
    elif kc is not None:
        pairs.append(("index", pk([f"코스피는 {pct_s(kc)} {'내렸' if kc < 0 else '올랐'}습니다.", f"지수는 코스피 {pct_s(kc)} {updn(kc)}입니다.", f"코스피 {pct_s(kc)} {updn(kc)}으로 끝났습니다."])))
    # 한 줄 판정
    bb = x["oth"] > 0 and bool(x["oth_in_bb"]) and x["oth_share"] >= 0.5
    ks, kb = _side_words(x["vals"], bb)
    ks, kb = ks or "큰손", kb or "아무도"
    if x["kq_ok"]:
        qs, qb = _side_words({"외국인": kq["foreign"], "기관": kq["inst"], "개인": kq["indiv"]}, False)
        qs, qb = qs or "아무도", qb or "아무도"
        v_txt = ""
    else:
        v_txt = ""
    # 어제 콜백(도장) — 없으면 외국인 연속일 사실
    cb = x["cb"]
    promise, result, ok, num = "", "", None, None
    wk_rows: list = []
    if x.get("cb_said"):
        pass                                   # s2 외국인 줄에서 이미 답했다 — 되풀이하지 않는다
    elif cb and isinstance(cb.get("check"), dict) and cb.get("ok") is not None:
        chk, ok, t = cb["check"], bool(cb["ok"]), cb.get("t")
        num = t
        qn = na._q_noun(cb) or "어제 숫자"
        when = _day_word(d, cb.get("prev_date"), past=True)
        promise = cb.get("q") or qn
        kind = chk.get("kind")
        n = chk.get("n")
        result = ("끊김" if ok else "이어짐") if kind == "kosdaq_break" else ("이어짐" if ok else "끊김")
        # 화면에 이미 도장이 찍힌다 — 말로 "오른쪽 도장입니다"라고 설명하면 기계처럼 들린다(JJ 2026-09-16).
        # 사람이 말하듯 "어제 우리가 확인하려 했던 …는 오늘도 이어졌습니다."로 끝낸다.
        # 연속일(엿새째)은 s2 에서 이미 말했으니 여기서 되풀이하지 않는다.
        kept = (result == "이어짐")
        v1 = "오늘도 이어졌습니다" if kept else "오늘 끊겼습니다"
        v2 = "오늘도 그대로였습니다" if kept else "오늘은 멈췄습니다"
        v3 = "오늘도 멈추지 않았습니다" if kept else "오늘로 끊겼습니다"
        pairs.append(("promise", pk([f"{J(qn)} {v1}.", f"{J(qn)} {v2}.", f"{J(qn)} {v3}."])))
    # 어제 약속이 없으면 여기서 따로 말하지 않는다 — 외국인 연속일은 s2 에서 이미 말했다(되풀이 금지, JJ 2026-09-17)
    # 어제 숙제가 둘 이상이면 빠짐없이 답한다 — watch[0] 은 위 도장(ledger), watch[1] 부터는 오늘 숫자로 직접 판정(BRIEF_FIX_2 §A).
    # 판정할 수 없는 꼴이면 그 문장은 아예 말하지 않는다. 이 칸은 예산에서 절대 빼지 않는다(GLOBAL_DROP 에 없다).
    answers: list[dict] = []
    for q2 in _prev_watch(d, (cb or {}).get("prev_date") or x["prev_date"])[1:3]:
        r2 = _verify_watch(q2, x, pk)
        if not r2:
            continue
        ok2, txt2 = r2
        if not txt2:
            continue
        pairs.append((f"promise{len(answers) + 2}", txt2))
        answers.append({"q": q2, "ok": ok2, "text": txt2})
    try:
        import weekend_watch
        _also, _said, wk_rows = weekend_watch.block(d, c, done_q=promise)
        for r in ([] if True else wk_rows):     # v7: 주말 숙제 콜백은 말하지 않는다(시청자 99.9% 신규)
            if r.get("a") and not r.get("merged"):
                a = nh._fix_won(r["a"])
                q_raw = str(r["q"]).strip().rstrip(".")
                pairs.append(("weekend", pk([f"주말에 짚어 둔 {q_raw}, {a}", f"주말 숙제 {q_raw}의 답, {a}", f"주말에 보자고 한 {weekend_watch.obj_q(q_raw)} 보면 {a}"])))
                break
    except Exception:
        wk_rows = []
    # 그런데: 주인공 물량이 어제와 크게 다르면(±25%) — 실제 반전만
    changed = None
    yv = x["y_P"]
    wy = _day_word(d, x["prev_date"], past=True)
    if isinstance(yv, (int, float)) and abs(yv) >= 1000 and (yv < 0) == sold and (abs(amt) <= 0.75 * abs(yv) or abs(amt) >= 1.25 * abs(yv)):
        grew = abs(amt) > abs(yv)
        changed = {"label": "크기", "before": f"{P} {hshort(yv)}", "after": f"{P} {hshort(amt)}", "before_label": wy}
        pairs.append(("turn", pk([f"그런데 {P}{'이 판' if sold else '이 산'} 규모는 {wy} {hwon(yv)}에서 오늘 {ro(hwon(amt))} {'불었' if grew else '줄었'}습니다.",
                                  f"그런데 규모는 {'커졌' if grew else '작아졌'}습니다. {wy} {hwon(yv)}, 오늘 {hwon(amt)}입니다."])))
    pairs.append(("q", pk(_S3A_Q)))
    return pairs, {"kosdaq": {"bars": kbars} if kbars else None, "index": index, "verdict": v_txt, "promise": promise, "result": result, "ok": ok, "num": num,
                   "answers": answers, "changed": changed, "head": "오늘의 손", "pairs": pairs}, wk_rows


# ══════════════════════════════════════════════════════════════════════════════
# S3b 돈이 빠진 곳·정체된 곳 — 유출 1위 업종(외/기 분리, N일째, 어제 대비) + '왼쪽 막대' + 대장주 등락(값은 안 빠졌는데 돈은 나감) + 자사주 받침
# + 나머지 유출 2~3개 → 질문(그 돈은 어디로 들어갔나). 대체: 유출 업종이 없으면 '빠진 업종이 없었다' + 가장 덜 들어온 곳.
# ══════════════════════════════════════════════════════════════════════════════
_S3B_Q = ["그럼 반대로 돈이 들어간 업종은 있었을까요?", "그럼 돈이 새로 들어간 업종은 어디였을까요?", "그렇다면 돈이 들어간 업종도 있었을까요?",
          "그럼 이 돈은 다른 업종으로 옮겨 갔을까요?"]


def _leaders(x: dict, th: str, n: int = 2) -> list[dict]:
    """업종의 거래대금 상위 n종목 등락 — flow_day 종목행, 없으면 거래대금 상위 20 종목 수급(stock_flows) 가운데 그 업종 종목."""
    rows = (x["themes"].get(th) or {}).get("stocks") or []
    if rows:
        top = sorted([r for r in rows if _num(r.get("ret")) is not None], key=lambda r: -(_num(r.get("value")) or 0))[:n]
        return [{"name": r["name"], "pct": float(r["ret"]), "code": r.get("code")} for r in top if r.get("name")]
    try:
        from app.services.themes import CODE_THEME
    except Exception:
        return []
    out = [{"name": r.get("name"), "pct": float(r["pct"]), "code": code} for code, r in x["sflows"].items()
           if isinstance(r, dict) and CODE_THEME.get(code) == th and _num(r.get("pct")) is not None and r.get("name")]
    return sorted(out, key=lambda r: -(_num((x["sflows"].get(r["code"]) or {}).get("value_mn")) or 0))[:n]


def _theme_codes(th: str) -> set[str]:
    try:
        from app.services.themes import THEME_CODES
        return set(THEME_CODES.get(th) or [])
    except Exception:
        return set()


def _eoss(w: str) -> str:
    """'반도체' → '반도체였', '조선' → '조선이었' (과거 서술격)."""
    ch = w[-1] if w else ""
    has = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0
    return w + ("이었" if has else "였")


def _again(x: dict, tn: str) -> list[str]:
    """유출 1위가 전 편과 같으면 '이번에도'로 잇는다 — 지난 영상을 본 사람이 '이어지는구나' 알게(JJ 2026-09-17)."""
    n = int((x.get("cont") or {}).get("top_move_days") or 0)
    if n < 2:
        return []
    return [f"답은 이번에도 {tn}, {n}일째 가장 많이 빠졌습니다.", f"{n}일째 같은 답, 이번에도 {_eoss(tn)}습니다.",
            f"답은 여전히 {tn}, {n}일째 돈이 가장 많이 빠졌습니다."]


def _s3b(x: dict, pk: Picker) -> tuple[list, dict]:
    d = x["d"]
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    outs, themes = x["outs"], x["themes"]
    leaders, support = [], None
    if not outs:
        least = min(x["ins"], key=lambda t: themes[t]["net"]) if x["ins"] else None
        pairs.append(("head", pk(["오늘은 빠진 업종이 없었습니다. 왼쪽 막대가 비어 있습니다.", "돈이 빠진 곳은 없었습니다. 업종 표가 전부 순매수입니다.", "나간 곳이 없는 날입니다. 왼쪽 막대를 보세요, 비어 있습니다."])))
        if least:
            pairs.append(("y", pk([f"가장 덜 들어온 곳은 {tname(least)}, {hwon(themes[least]['net'])}입니다.", f"가장 짧은 막대는 {tname(least)} {hwon(themes[least]['net'])}입니다.",
                                   f"{subj(tname(least))} 가장 적게 받았습니다. {hwon(themes[least]['net'])}입니다."])))
        pairs.append(("q", pk(_S3B_Q)))
        return pairs, {"out": [], "leaders": [], "support": None, "pairs": pairs}
    th = outs[0]
    r = themes[th]
    _ag = _again(x, tname(th))
    if _ag:
        pairs.append(("again", pk(_ag)))
    T = hwon(r["net"])
    F = hwon(r["foreign"]) if _num(r.get("foreign")) is not None else None
    I = hwon(r["inst"]) if _num(r.get("inst")) is not None else None
    stk = abs(int(r.get("streak") or 0)) if (r.get("streak") or 0) < 0 else 0
    tn = tname(th)
    if F is not None and I is not None:
        fo, io = r["foreign"], r["inst"]
        if fo < 0 and io < 0:
            # 머리 문장은 어느 후보를 골라도 '빠졌|나갔|순매도'를 달고 나온다 — 합계(sum)가 예산에서 빠져도 s3b 가 뜻을 잃지 않는다(qa_script.S3B_OUT)
            _dd = f" {dko(stk)} 빠졌습니다." if stk >= 2 else ""
            pairs.append(("head", pk([f"외국인과 기관이 합쳐 {obj(T)} 팔았습니다.{_dd}", f"외국인과 기관을 합쳐 {subj(T)} 나갔습니다.{_dd}"] if _ag else
                                     [f"가장 많이 빠진 곳은 {tn}입니다. 외국인과 기관이 합쳐 {obj(T)} 팔았습니다.",
                                      f"돈이 가장 많이 나간 곳은 {tn}, 외국인과 기관을 합쳐 {T}입니다.",
                                      f"오늘 가장 크게 빠진 곳은 {tn}입니다. 외국인과 기관이 합쳐 {obj(T)} 팔았습니다."])))
            stk = 0 if _dd else stk      # 연속일을 머리 문장에서 말했으면 합계 문장(sum)은 되풀이하지 않는다
        else:
            big = ("외국인", fo, "기관", io) if fo < io else ("기관", io, "외국인", fo)
            b0, b1, b2, b3 = big
            pairs.append(("head", pk([f"{b0}은 {obj(hwon(b1))} 팔았고, {b2}은 {obj(hwon(b3))} {_verb(b3)}습니다.",
                                      f"{b0}이 {obj(hwon(b1))} 팔았고, {b2}은 {obj(hwon(b3))} {_verb(b3)}습니다."] if _ag else [f"돈이 가장 많이 빠진 곳은 {tn}입니다. {b0} {hwon(b1)} 순매도, {b2}은 {hwon(b3)} {_word(b3)}입니다.",
                                      f"나간 돈 1위는 {tn}, {b0} {hwon(b1)} 순매도, {b2} {hwon(b3)} {_word(b3)}.",
                                      f"{tn}에서 돈이 빠졌습니다. 판 쪽은 {b0} {hwon(b1)}, {b2}은 {hwon(b3)} {_word(b3)}입니다.",
                                      f"오늘 가장 크게 빠진 곳은 {tn}입니다. {b0} {hwon(b1)} 순매도, {b2}은 {hwon(b3)} {_word(b3)}.",
                                      f"가장 많이 나간 곳은 {tn}입니다. {b0} {hwon(b1)} 순매도에 {b2}은 {hwon(b3)} {_word(b3)}.",
                                      f"답은 {tn}입니다. {b0} {hwon(b1)} 순매도, {b2}은 {hwon(b3)} {_word(b3)}입니다."])))
    else:
        pairs.append(("head", pk([f"{tn}에서 돈이 빠졌습니다.", f"나간 돈 1위는 {tn}, 여기서 빠졌습니다.", f"빠진 자리부터, {tn}에서 나갔습니다.",
                                  f"돈이 가장 많이 빠진 곳, {tn}에서 나갔습니다."])))
    wy = _day_word(d, x["prev_date"], past=True)
    # 외국인·기관이 반대로 간 날(9/16: −9,900억 + 8,100억)은 '합쳐 1,800억이 나갔다'가 오해를 부른다 — 합계를 말하지 않는다
    split = F is not None and I is not None and (r["foreign"] < 0) != (r["inst"] < 0)
    if split:
        pass
    elif stk >= 2:
        pairs.append(("sum", pk([f"둘을 합치면 {T}, {dko(stk)} 빠져나갔습니다.", f"합쳐서 {subj(T)} {dko(stk)} 나갔습니다.", f"외국인과 기관을 더하면 {T}, {dko(stk)} 순매도입니다.",
                                 f"더하면 {T}, {dko(stk)} 이어진 유출입니다.", f"합계로는 {T}, {dko(stk)} 빠졌습니다.", f"둘을 더한 {subj(T)} {dko(stk)} 나갔습니다."])))
    else:
        pairs.append(("sum", pk([f"합치면 {subj(T)} 나갔습니다.", f"둘을 더하면 {T} 순매도입니다.", f"외국인과 기관을 더하면 {subj(T)} 빠졌습니다.", f"합계로는 {subj(T)} 나갔습니다."])))
    yv = _num(r.get("y"))
    if yv is not None and yv < 0 and abs(yv) >= 100:
        Y = hwon(yv)
        if abs(r["net"]) <= 0.8 * abs(yv):
            pairs.append(("y", pk([f"{wy} {Y}보다는 줄었습니다.", f"{wy} {Y}에서 줄어든 크기입니다.", f"{J(wy)} {Y}였으니 짧아진 쪽입니다.", f"{wy} {Y}보다 짧아진 막대입니다."])))
        elif abs(r["net"]) >= 1.25 * abs(yv):
            pairs.append(("y", pk([f"{wy} {Y}보다 늘었습니다.", f"{wy} {Y}에서 불어난 크기입니다.", f"{wy}보다 길어진 막대, {Y}에서입니다."])))
        else:
            pairs.append(("y", pk([f"{wy} {J(Y, '과', '와')} 비슷한 크기입니다.", f"{wy} {Y}, 거의 그대로입니다.", f"{wy} {J(Y, '과', '와')} 같은 길이입니다."])))
    elif yv is not None and yv > 0:
        pairs.append(("y", pk([f"{J(wy)} {hwon(yv)} 순매수였습니다.", f"{J(wy)} 받았던 자리입니다. {hwon(yv)}, 막대 색이 바뀌었습니다.", f"{wy} {hwon(yv)} 순매수에서 오늘 순매도로 돌아섰습니다."])))
    # 나머지 유출 업종은 '그런데' 앞에 둔다 — 블록은 반전이나 질문으로 닫아야 하고(정본 체크리스트 ⑤),
    # 말 순서로도 '반도체가 제일 많이 빠졌고 원전·자동차도 빠졌다 → 그런데 값은 올랐다'가 자연스럽다(JJ 2026-09-16).
    rest = [t for t in outs[1:4] if abs(themes[t]["net"]) >= 100]
    if len(rest) >= 2:
        t2, t3 = rest[0], rest[1]
        V2, V3 = hwon(themes[t2]["net"]), hwon(themes[t3]["net"])
        if V2 == V3:
            pairs.append(("others", pk([f"{J(tname(t2), '과', '와')} {tname(t3)}에서 {V2}씩도 빠졌습니다.", f"{tname(t2)}, {tname(t3)}에서도 {V2}씩 나갔습니다.", f"{J(tname(t2), '과', '와')} {tname(t3)}도 {V2}씩 순매도입니다."])))
        else:
            pairs.append(("others", pk([f"{tname(th)} 말고도 {tname(t2)}에서 {V2}, {tname(t3)}에서 {subj(V3)} 빠졌습니다.",
                                        f"{tname(t2)}에서 {V2}, {tname(t3)}에서도 {subj(V3)} 빠져나갔습니다.",
                                        f"그다음으로 {tname(t2)}에서 {V2}, {tname(t3)}에서 {subj(V3)} 나갔습니다."])))
        if len(rest) >= 3:
            t4 = rest[2]
            pairs.append(("others2", pk([f"{tname(t4)} {hwon(themes[t4]['net'])}도 빠졌습니다.", f"{tname(t4)}에서도 {subj(hwon(themes[t4]['net']))} 나갔습니다.", f"{tname(t4)} {hwon(themes[t4]['net'])}까지 순매도입니다."])))
    elif len(rest) == 1:
        t2 = rest[0]
        pairs.append(("others", pk([f"{tname(t2)}에서도 {subj(hwon(themes[t2]['net']))} 빠졌습니다.", f"그다음은 {tname(t2)}, {hwon(themes[t2]['net'])}입니다.", f"{tname(t2)} {hwon(themes[t2]['net'])}도 나갔습니다."])))
    # 그런데: 대장주 등락 — 값은 안 빠졌는데 돈은 나감 / 값도 같이 밀림
    leaders = _leaders(x, th)
    if leaders:
        a = leaders[0]
        b = leaders[1] if len(leaders) > 1 else None
        small = all(abs(l["pct"]) < 1.0 for l in leaders)
        if b:
            if small:
                pairs.append(("turn", pk([f"그런데 {J(a['name'])} {pct1(a['pct'])}, {J(b['name'])} {pct1(b['pct'])} {'내렸을' if a['pct'] < 0 else '움직였을'} 뿐입니다.",
                                          f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}뿐입니다.",
                                          f"그런데 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}, 값은 버텼습니다.",
                                          f"그런데 {a['name']} {pct1(a['pct'])}, {b['name']} {pct1(b['pct'])} {'하락' if a['pct'] < 0 else '등락'}뿐입니다.",
                                          f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
            elif a["pct"] < 0 and (b["pct"] < 0):
                pairs.append(("turn", pk([f"그런데 값도 같이 밀려 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}, 값까지 같이 빠진 자리입니다.",
                                          f"그런데 돈도 값도 나간 자리, {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩도 같은 색, {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다."])))
            elif a["pct"] > 0 and b["pct"] > 0:
                # 돈은 빠졌는데 값은 오른 날 — 받은 쪽이 따로 있다는 뜻이다(9/16: 외국인이 팔고 기관이 받았다).
                # 까닭을 먼저 말하고 '그런데'로 닫는다 — 블록 끝은 '그런데' 문장이나 질문이어야 한다(정본 체크리스트 ⑤).
                _who = "기관" if (x["themes"].get(th) or {}).get("inst", 0) > 0 else ""
                if _who and not split:        # 머리 문장이 이미 '외국인은 팔고 기관은 샀다'를 말했으면 되풀이하지 않는다
                    pairs.append(("turn_why", pk([
                                                  f"외국인이 판 물량을 {_who}이 사들인 겁니다.",
                                                  f"외국인이 내놓은 주식을 {_who}이 샀습니다."])))
                pairs.append(("turn", pk([f"그런데 값은 올랐습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 반대입니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 값은 거꾸로 갔습니다. {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 판 쪽 값이 올랐습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
            else:
                pairs.append(("turn", pk([f"그런데 값은 갈렸습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}입니다.",
                                          f"그런데 종목 칩은 서로 다릅니다. {a['name']} {pct1_dir(a['pct'])}에 {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 두 종목 값이 엇갈렸습니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}.",
                                          f"그런데 값은 한 방향이 아닙니다. {a['name']} {pct1_dir(a['pct'])}, {b['name']} {pct1_dir(b['pct'])}."])))
        else:
            pairs.append(("turn", pk([f"그런데 {J(a['name'])} {pct1_dir(a['pct'])}{'에 그쳤습니다' if small else '입니다'}.", f"그런데 {a['name']}의 값은 {pct1_dir(a['pct'])}입니다.",
                                      f"그런데 값은 {a['name']} {pct1_dir(a['pct'])}{'뿐입니다' if small else '입니다'}."])))
        codes = _theme_codes(th) | {l.get("code") for l in leaders if l.get("code")}
        bb = [t for t in x["top_others"] if t.get("code") in codes and t.get("code") in x["act"]]
        rep_bb = bool(bb) and (_said_yesterday(d, "자사주") or (x.get("cont") or {}).get("top_buyer_days", 1) >= 3)
        if bb and (small or rep_bb):          # 기타법인 얘기가 며칠째면 값이 밀린 날에도 매입 기간은 알린다(JJ 2026-09-17)
            S = hwon(sum(t["v"] for t in bb))
            support = {"label": "자사주", "v": round(sum(t["v"] for t in bb))}
            two = "두 회사" if len(bb) == 2 else bb[0]["name"]
            nm = "두 종목" if len(bb) == 2 else bb[0]["name"]
            per = _bb_period(d, bb)
            support["label"] = "기타법인"          # 화면도 등식 없이 — 두 종목 기타법인 순매수
            if per["rows"]:
                support["period"] = per["rows"]
            if rep_bb and per["ends"]:
                # JJ 2026-09-17: "기타법인이 샀다를 3~4일 계속 말했다 → 이제 자사주 매입 기간을 말하고 언제까지 할지를 인지시켜야 한다."
                pairs.append(("support", pk([f"자사주 매입은 원래 {per['ends']}까지입니다.", f"자사주 매입 기간은 원래 {per['ends']}까지입니다."])))
                if per["early"]:     # 이 문장만으로도 뜻이 서게(앞 문장은 길이 예산에서 빠질 수 있다)
                    pairs.append(("support_2", f"{'두 회사 ' if len(bb) == 2 else ''}자사주 매입은 지금 속도면 {per['early']} 끝난다는 분석이 나왔습니다."))
            else:
                pairs.append(("support", pk([f"{nm}에선 기타법인이 {obj(S)} 샀습니다.", f"{nm}을 가장 많이 산 건 기타법인, {S}입니다."])))
                pairs.append(("support_2", f"{'두 회사 모두 ' if len(bb) == 2 else ''}자사주를 사들이는 기간입니다."))
            if small:
                pairs.append(("meaning", pk(["돈이 정체된 자리는 여기입니다.", "정체된 돈이 고인 곳이 여기입니다.", "값은 서 있고 돈은 나가는 자리, 정체는 여기입니다.", "돈은 나가는데 값이 안 밀리는 자리, 여기가 정체입니다."])))
        elif small:
            pairs.append(("meaning", pk(["돈은 나갔는데 값은 서 있는 자리입니다.", "값과 돈이 따로 노는 자리, 정체는 여기입니다.", "나간 돈만큼 값이 밀리지 않은 자리입니다."])))
    else:
        rt = _num(r.get("ret"))
        pairs.append(("turn", pk([f"그런데 {tn} 값은 {pct1_dir(rt)}{'에 그쳤습니다' if abs(rt) < 1 else '입니다'}." if rt is not None else "그런데 오늘 유출은 대부분 이 업종 하나에서 나왔습니다.",
                                  f"그런데 업종 등락은 {pct1_dir(rt)}입니다." if rt is not None else "그런데 나머지 업종은 이보다 훨씬 작습니다."])))
    out_rows = [{"theme": t, "v": round(themes[t]["net"]), "foreign": themes[t].get("foreign"), "inst": themes[t].get("inst"), "ret": themes[t].get("ret"),
                 "streak": themes[t].get("streak"), "y": themes[t].get("y")} for t in outs[:4]]
    pairs.append(("q", pk(_S3B_Q)))
    return pairs, {"out": out_rows, "leaders": [{"name": l["name"], "pct": l["pct"]} for l in leaders], "support": support, "pairs": pairs}


# ══════════════════════════════════════════════════════════════════════════════
# S3c 돈이 들어온 곳 — 이동 선언 1회 + 유입 상위 2 업종(외/기 분리, 등락, 순매수 종목 ≤4, N일째) + 유출 1위 대비 비율('16분의 1') → 질문(그 안에서 누가 샀나).
# 대체: 유입 업종 없음 → '들어온 곳이 없었습니다. 가장 덜 빠진 곳은 …' + '전부 유출'.
# ══════════════════════════════════════════════════════════════════════════════
_S3C_Q = ["그럼 오늘 가장 많이 오른 종목은 누가 샀을까요?", "그럼 종목으로 들어가 보면 누가 샀을까요?", "그럼 가장 많이 산 종목과 가장 많이 오른 종목은 어디였을까요?",
          "그럼 실제로 오른 종목은 누가 사들였을까요?"]


def _s3c_q(x: dict) -> list[str]:
    """s3c → s4 다리. '종목 표'가 뭔지 모르는 사람도 알게 — 어느 업종의 어떤 종목을 보는지 붙인다(JJ 2026-09-17)."""
    try:
        _, th4, _ = _pick_stocks(x)
    except Exception:  # noqa: BLE001
        th4 = ""
    t4 = tname(th4) if th4 else ""
    if not t4:
        return list(_S3C_Q)
    return [f"그럼 {t4} 종목은 실제로 누가 샀을까요?", f"그럼 {t4}에서 오른 종목은 누가 사들였을까요?", f"그럼 {t4}에서 어떤 종목들을 샀을까요?"]


def _s3c(x: dict, pk: Picker) -> tuple[list, dict]:
    pk = ScenePick(pk)
    pairs: list[tuple[str, str]] = []
    ins, themes = x["in_ths"], x["themes"]
    in_rows, ratio = [], None
    if not ins:
        # 합계(외국인+기관)가 전 업종 마이너스인 날이 있다 — 한쪽이 업종 전부에서 팔면 그렇게 된다.
        # 그렇다고 '들어온 곳이 없다'로 끝내면 값이 오른 업종을 설명하지 못한다(JJ 2026-09-16:
        # "들어온 게 없었다고? 오늘 오른 종목들의 카테고리가 없었다고?"). 합계 대신 **받은 손**을 보여 준다.
        f_tot = sum(_num(themes[t].get("foreign")) or 0 for t in themes)
        i_tot = sum(_num(themes[t].get("inst")) or 0 for t in themes)
        got_side, gkey = ("기관", "inst") if i_tot > f_tot else ("외국인", "foreign")
        sell_side, skey = ("외국인", "foreign") if got_side == "기관" else ("기관", "inst")
        all_neg = len(themes) >= 5 and all((_num(themes[t].get(skey)) or 0) < 0 for t in themes)
        why = f"{subj(sell_side)} 모든 업종에서 팔았기 때문입니다." if all_neg else f"{sell_side} 매도가 더 컸기 때문입니다."
        pairs.append(("head", pk([f"외국인과 기관을 합쳐 보면 돈이 들어온 곳이 없었습니다. {why}", f"외국인과 기관을 더하면 들어온 곳이 없었습니다. {why}",
                                  f"외국인과 기관 돈을 합치면 들어온 곳이 없었습니다. {why}"])))
        top0 = x["outs"][0] if x["outs"] else None            # 유출 1위는 s3b 에서 이미 말했다 — 되풀이하지 않는다
        got = sorted([(t, _num(themes[t].get(gkey)) or 0) for t in themes
                      if (_num(themes[t].get(gkey)) or 0) > 0 and t != top0], key=lambda r: -r[1])[:2]
        if got:
            n1, v1 = tname(got[0][0]), hwon(got[0][1])
            if len(got) > 1:
                n2, v2 = tname(got[1][0]), hwon(got[1][1])
                pairs.append(("t1", pk([f"대신 {got_side}은 {n1}에서 {v1}, {n2}에서 {obj(v2)} 사들였습니다.",
                                        f"다만 {got_side}은 {n1} {v1}, {n2} {obj(v2)} 샀습니다.",
                                        f"그래도 {got_side}은 {n1}에 {v1}, {n2}에 {obj(v2)} 샀습니다."])))
            else:
                pairs.append(("t1", pk([f"대신 {got_side}은 {n1}에서 {obj(v1)} 사들였습니다.", f"다만 {got_side}은 {n1}에 {obj(v1)} 샀습니다."])))
        elif x["outs"]:
            least = max(x["outs"], key=lambda t: themes[t]["net"])
            pairs.append(("t1", pk([f"그나마 덜 나간 곳이 {tname(least)} {hwon(themes[least]['net'])}입니다.",
                                    f"가장 적게 빠진 곳은 {tname(least)}, {hwon(themes[least]['net'])}입니다.",
                                    f"{subj(tname(least))} 가장 적게 빠졌습니다. {hwon(themes[least]['net'])}입니다."])))
        pairs.append(("q", pk(_s3c_q(x))))
        return pairs, {"in": [], "ratio": None, "got_side": got_side,
                       "got": [{"theme": t, "v": round(v)} for t, v in got], "pairs": pairs}
    a = ins[0]
    b = ins[1] if len(ins) > 1 else None
    ra, rb = themes[a], (themes[b] if b else None)
    ta, tb = tname(a), (tname(b) if b else None)
    if b:
        pairs.append(("move", pk([f"있었습니다. {J(ta, '과', '와')} {tb}입니다.", f"들어온 곳은 {J(ta, '과', '와')} {tb}입니다.", f"돈이 들어간 곳은 {J(ta, '과', '와')} {tb}입니다.",
                                  f"돈이 들어온 업종은 {J(ta, '과', '와')} {tb}입니다.",
                                  f"들어간 곳은 {J(ta, '과', '와')} {tb}{'이었' if _has_batchim(tb) else '였'}습니다."])))
    else:
        pairs.append(("move", pk([f"있었습니다. {ta} 하나입니다.", f"들어온 곳은 {ta} 하나입니다.", f"돈이 들어간 업종은 {ta}뿐입니다."])))
    for tag, th, r, tn in (("t1", a, ra, ta), ("t2", b, rb, tb)):
        if not th:
            continue
        T = hwon(r["net"])
        F = hwon(r["foreign"]) if _num(r.get("foreign")) is not None else None
        I = hwon(r["inst"]) if _num(r.get("inst")) is not None else None
        ret = _num(r.get("ret"))
        RT = f"{pct1(ret)} {'올랐' if ret > 0 else '내렸'}" if ret is not None else None
        RS = f"{pct1(ret)} {updn(ret)}" if ret is not None else None
        if F is not None and I is not None:
            fo, io = r["foreign"], r["inst"]
            if fo > 0 and io > 0:
                if tag == "t1":
                    pairs.append((tag, pk([f"{J(tn)} 외국인이 {F}, 기관이 {obj(I)} 샀습니다.", f"{tn}에는 외국인 {F}, 기관 {subj(I)} 들어왔습니다.",
                                           f"먼저 {J(tn)} 외국인이 {F}, 기관이 {obj(I)} 사들였습니다."])))
                else:
                    pairs.append((tag, pk([f"{tn}에도 외국인이 {F}, 기관이 {obj(I)} 샀습니다.", f"{tn}에는 외국인 {F}, 기관 {subj(I)} 들어왔습니다.",
                                           f"{J(tn)} 외국인이 {F}, 기관이 {obj(I)} 사들였습니다."])))
            else:
                who, wv, other, ov = ("외국인", fo, "기관", io) if fo > io else ("기관", io, "외국인", fo)
                if tag == "t1":
                    pairs.append((tag, pk([f"{J(tn)} {who}이 {obj(hwon(wv))} 샀고, {other}은 {obj(hwon(ov))} {_verb(ov)}습니다.",
                                           f"{tn}에서는 {who}이 {obj(hwon(wv))} 사들였고, {other}은 {obj(hwon(ov))} {_verb(ov)}습니다."])))
                else:
                    pairs.append((tag, pk([f"{tn}에서는 {who}이 {obj(hwon(wv))} 샀고, {other}은 {obj(hwon(ov))} {_verb(ov)}습니다.", f"{J(tn)} {who}이 {obj(hwon(wv))} 샀고, {other}은 {obj(hwon(ov))} {_verb(ov)}습니다."])))
            if RT:
                pairs.append((f"{tag}_sum", pk([f"합쳐 {T} 순매수, {RS}.", f"합쳐 {T}, 업종은 {RT}습니다.", f"둘을 더해 {T}, {RS}입니다.", f"합계 {T}에 값은 {RT}습니다.", f"{subj(T)} 들어왔고 {RT}습니다.", f"합계 {T} 순매수, 업종은 {RS}."])))
            else:
                pairs.append((f"{tag}_sum", pk([f"합쳐 {subj(T)} 들어왔습니다.", f"둘을 더하면 {T}입니다.", f"합계 {T}입니다."])))
        else:
            if RT:
                pairs.append((tag, pk([f"{tn}에는 {subj(T)} 들어왔고, {RT}습니다.", f"{tn}에 {T}, 업종은 {RT}습니다.", f"{J(tn)} {T}, 값은 {RT}습니다."])))
            else:
                pairs.append((tag, pk([f"{tn}에는 {subj(T)} 들어왔습니다.", f"{tn}에 {T}입니다.", f"{J(tn)} {T} 순매수입니다."])))
        names = [n for n in (r.get("pos_names") or []) if n][:4]
        n_all = r.get("n")
        if tag == "t1" and names:
            if n_all and len(names) >= n_all and n_all >= 2:
                pairs.append(("names", pk([f"{_and(names)} {han(len(names))} 종목 모두 순매수였습니다.", f"{_and(names)}, {han(len(names))} 종목 전부 받았습니다.", f"{han(len(names))} 종목 {subj(_and(names))} 다 순매수입니다."])))
            elif len(names) >= 2:
                pairs.append(("names", pk([f"종목은 {_and(names)}입니다.", f"{_and(names)}에 몰렸습니다.", f"{_and(names)} 순매수입니다."])))
            else:
                pairs.append(("names", pk([f"종목은 {names[0]} 하나에 몰렸습니다.", f"받은 종목은 {names[0]}입니다.", f"{names[0]} 한 종목이 받았습니다."])))
        # 오늘 이슈로 꼽힌 종목이 이 업종 안에 있으면 한 마디로 잇는다(BRIEF_FIX_2 §D-1) — 예산에서 빼지 않는다
        if tag == "t1" and not x.get("issue_said"):
            pool = set(names) | {str(s.get("name")) for s in (r.get("stocks") or []) if isinstance(s, dict) and s.get("name")}
            hit = next((n for n in _issue_names(x) if n in pool), None)
            if hit:
                x["issue_said"] = hit
                pairs.append(("issue", pk([f"{J(hit)} 오늘 뉴스가 나온 종목입니다.", f"이 가운데 {J(hit)} 오늘 뉴스에 나온 종목입니다.",
                                           f"{J(hit)} 뒤에서 볼 오늘 이슈와 이어진 종목입니다."])))
        stk = int(r.get("streak") or 0)
        if tag == "t1" and stk >= 2:
            pairs.append(("streak", pk([f"{dko(stk)} 이어진 유입입니다.", f"{dko(stk)} 같은 자리에 돈이 들어오는 중입니다.", f"하루짜리가 아니라 {dko(stk)} 쌓이는 돈입니다."])))
        in_rows.append({"theme": th, "v": round(r["net"]), "foreign": r.get("foreign"), "inst": r.get("inst"), "ret": r.get("ret"), "names": names, "streak": stk})
    # 유출 1위 대비 비율
    if x["out_th"] and x["out_t"]:
        in_sum = sum(themes[t]["net"] for t in ins)
        O, IS = hwon(x["out_t"]), hwon(in_sum)
        on = tname(x["out_th"])
        frac = _calc("fraction", in_sum, x["out_t"])
        two = "둘을 합치면" if b else "여기 들어온 돈은"
        if frac:
            kk = frac["n"]
            ratio = {"out_theme": x["out_th"], "out": round(x["out_t"]), "in": round(in_sum), "text": f"{kk}분의 1"}
            pairs.append(("ratio", pk([f"합쳐 {IS}, {on} 유출의 {kk}분의 1입니다.", f"들어온 {IS}, {on} 유출의 {kk}분의 1입니다.", f"합쳐 {IS}인데 {on} 유출의 {kk}분의 1입니다.",
                                       f"{on}에서 나간 돈에 견주면 {kk}분의 1입니다.", f"{IS}, {on} 유출의 {kk}분의 1 크기입니다.",
                                       f"{two} {IS}, {on} 유출의 {kk}분의 1입니다."])))
            pairs.append(("ratio_2", pk(["옮겨간 돈보다 나간 돈이 훨씬 큽니다.", "돈은 옮겨간 게 아니라 나간 쪽이 큽니다.", "들어온 돈은 나간 돈의 조각입니다.", "나간 막대가 들어온 막대를 압도합니다."])))
        else:
            pct = round(in_sum / abs(x["out_t"]) * 100)
            ratio = {"out_theme": x["out_th"], "out": round(x["out_t"]), "in": round(in_sum), "text": f"{pct}%" if pct < 200 else f"{round(pct / 100)}배"}
            if pct >= 100:
                pairs.append(("ratio", pk([f"{on}에서 나간 {O}보다 들어온 {subj(IS)} 큽니다.", f"들어온 {subj(IS)} {on} 유출 {obj(O)} 넘습니다.", f"나간 {on} {O}보다 들어온 {subj(IS)} 더 큰 날입니다."])))
            else:
                pairs.append(("ratio", pk([f"{on}에서 나간 {O}에 견주면 들어온 돈은 {pct}%입니다.", f"{two} {IS}, {on} 유출의 {pct}%입니다.", f"나간 돈 {O} 가운데 {pct}%만큼이 옮겨 왔습니다."])))
    pairs.append(("q", pk(_s3c_q(x))))
    return pairs, {"in": in_rows, "ratio": ratio, "pairs": pairs}


# ══════════════════════════════════════════════════════════════════════════════
# S4 1차 자료 한 칸 — '직접 열어봤습니다, 키움 종목별 투자자 표, M월 D일 마감 기준' + 대장주 1 + 최대 상승 1(등락·외/기/개·거래대금) + 계산 1개(검산)
# + '누가 밀어 올렸나'. 대체: brief_stocks 없음 → flow_day 종목행(외/기·등락·거래대금만, 개인은 말하지 않음, no_indiv), 계산은 외+기 ÷ 거래대금.
# ══════════════════════════════════════════════════════════════════════════════
def _aw(n: str, v: float) -> str:
    """'기관 150억 순매수' / 0 이면 '기관 순매수 없음'."""
    return f"{n} 순매수 없음" if abs(v) < 0.5 else f"{n} {hwon(v)} {_word(v)}"


def _driver(s: dict) -> tuple[str, float]:
    """가장 많이 산 주체(이름, 값). 셋 다 순매도면 가장 덜 판 쪽."""
    cands = [(n, _num(s.get(k))) for n, k in (("외국인", "foreign"), ("기관", "inst"), ("개인", "indiv")) if _num(s.get(k)) is not None]
    return max(cands, key=lambda t: t[1]) if cands else ("외국인", 0.0)


def _pick_stocks(x: dict) -> tuple[list[dict], str, bool]:
    """(종목 둘, 업종, brief_stocks 에서 왔는가). §2: 유입 업종 없으면 유출 1위 대장주 + 그 업종에서 가장 덜 내린 종목."""
    bs = x["bstocks"]
    big = x.get("bigcaps") or []
    if bs and big:
        # v7(JJ 2026-09-19): SK하이닉스·삼성전자 먼저(외국인+기관이 더 크게 움직인 쪽부터), 그다음 그날 업종에서 크게 오른 종목 하나.
        bigc = {s.get("code") for s in big}
        big = sorted(big, key=lambda s: -abs((_num(s.get("foreign")) or 0) + (_num(s.get("inst")) or 0)))
        rest = [s for s in bs if s.get("code") not in bigc]
        third = next((s for s in rest if s.get("role") == "최대 상승"), None) or (rest[0] if rest else None)
        return big + ([third] if third else []), x["btheme"] or (third or big[0]).get("theme") or "", True
    if bs:
        lead = next((s for s in bs if s.get("role") in ("대장주", "외국인·기관 최다", "거래대금 최대")), bs[0])
        top = next((s for s in bs if s is not lead), None)
        return [lead] + ([top] if top else []), x["btheme"] or lead.get("theme") or "", True
    th = x["in_th"] or x["out_th"]
    if not th:
        return [], "", False
    rows = [r for r in ((x["themes"].get(th) or {}).get("stocks") or []) if r.get("name") and _num(r.get("ret")) is not None]
    if not rows:
        return [], th, False
    leader_code = next((s.get("leader") for s in (x["flow_day"].get("sectors") or []) if s.get("theme") == th), None)
    lead_f = next((r for r in rows if r.get("code") == leader_code), None)
    lead = lead_f or max(rows, key=lambda r: _num(r.get("value")) or 0)
    others = [r for r in rows if r is not lead]
    top = max(others, key=lambda r: r["ret"]) if others else None
    conv = lambda r, role: {"code": r.get("code"), "name": r["name"], "role": role, "theme": th, "pct": float(r["ret"]), "foreign": r.get("foreign"), "inst": r.get("inst"),
                            "indiv": None, "value": r.get("value"), "close": r.get("close")}
    return [conv(lead, "외국인·기관 최다" if lead_f else "거래대금 최대")] + ([conv(top, "최대 상승" if x["in_th"] else "가장 덜 내림")] if top else []), th, False


def _s4(x: dict, pk: Picker) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    day = f"{int(d[4:6])}월 {int(d[6:8])}일"
    doc = f"키움 종목별 투자자 표 · {int(d[4:6])}/{int(d[6:8])} 마감 기준"
    pairs: list[tuple[str, str]] = []
    stocks, th, full = _pick_stocks(x)
    # 여는 말에 개수를 박은 후보("두 종목…")는 실제로 둘일 때만 쓴다 — v7 뒤 _pick_stocks 가 셋을 돌려주는 날이 있는데
    # 9/22 편이 하필 그 후보를 뽑아 "두 종목"이라 해 놓고 셋을 말했다(네 갈래 검토, JJ "개수는 원자료로 다시 센다").
    opens = ["종목마다 누가 사고 팔았는지 직접 확인해 봤습니다.", "종목으로 확인해 보면 이렇습니다.", "종목별로 누가 샀는지 직접 확인해 봤습니다.",
             "종목 하나하나 누가 샀는지 직접 확인해 봤습니다.", "종목마다 외국인, 기관, 개인이 얼마나 샀는지 직접 확인해 봤습니다."]
    if len(stocks) == 2:
        opens.insert(2, "두 종목을 하나씩 확인해 보면 이렇습니다.")
    pairs.append(("open", pk(opens)))
    calc, kind = None, "K0"
    rows_out = []
    if not stocks:
        pairs.append(("row:0", pk(["오늘은 종목별 숫자가 아직 안 나왔습니다. 업종 합계까지만 확정입니다.", "종목별 집계는 아직입니다. 업종 숫자까지가 확정입니다.", "종목별 숫자는 오늘 비어 있어 업종까지만 봅니다."])))
        pairs.append(("calc", pk(["확정치가 나오면 다음 편에서 비율을 다시 셉니다.", "숫자가 오면 그때 비율을 계산합니다.", "계산은 다음 편에서 다시 하겠습니다."])))
        return pairs, {"doc": doc, "date": day, "stocks": [], "calc": None, "kind": kind, "full": full, "no_indiv": True, "pairs": pairs}, kind
    tn = tname(th)
    for i, s in enumerate(stocks):
        name, pct = s["name"], _num(s.get("pct"))
        fo, io, dv, val = _num(s.get("foreign")), _num(s.get("inst")), _num(s.get("indiv")), _num(s.get("value"))
        role = s.get("role") or ("외국인·기관 최다" if i == 0 else "최대 상승")
        if role == "대장주":                      # 옛 brief_stocks — collect_brief 의 대장주는 업종 아카이브 leader(외국인+기관 최다)였다
            role = "외국인·기관 최다"
            s["role"] = role
        P1 = f"{pct2(pct)} {'올랐' if pct > 0 else '내렸'}" if pct is not None else None
        PD = f"{pct2(pct)} {updn(pct)}" if pct is not None else ""
        # 이 종목이 오늘 이슈 종목이면 그 줄에 한 번만 표시한다(BRIEF_FIX_2 §D-2) — s3c 가 이미 이슈를 말했으면 생략
        iss = bool(name in _issue_names(x) and not x.get("issue_said"))
        if iss:
            x["issue_said"] = name
        lim = pct is not None and pct >= 29.5
        P1b = (f"상한가 {pct2(pct)}까지 올랐" if lim else P1) if P1 else None
        if role == "대형주":
            same_dir = (pct or 0) * (_num(stocks[0].get("pct")) or 0) > 0
            if not P1:
                pairs.append((f"row:{i}", f"{name}입니다."))
            elif i == 0:
                pairs.append((f"row:{i}", pk([f"먼저 {J(name)} {P1}습니다.", f"{name}부터 보면, {P1}습니다."])))
            else:
                pairs.append((f"row:{i}", pk([f"{name}도 {P1}습니다.", f"{name}도 오늘 {P1}습니다."] if same_dir else [f"반대로 {J(name)} {P1}습니다."])))
        elif i == 0:
            who = "외국인과 기관이 가장 많이 산" if role == "외국인·기관 최다" else "거래대금이 가장 큰"
            pairs.append((f"row:{i}", pk(([f"먼저 이슈 종목인 {J(name)} {P1}습니다.", f"이슈 종목 {J(name)} {P1}습니다."] if iss else
                                          [f"먼저 {tn}에서 {who} {J(name)} {P1}습니다.", f"{tn}에서 {who} 종목은 {name}, {P1}습니다."])) if P1 else
                          pk([f"{tn}에서 {who} 종목은 {name}입니다."])))
        else:
            rl = "가장 많이 오른 종목" if role == "최대 상승" else "가장 덜 내린 종목" if role == "가장 덜 내림" else "외국인과 기관이 가장 많이 산 종목" if role == "외국인·기관 최다" else "둘째 종목"
            if any((st.get("role") == "대형주") for st in stocks[:i]):
                rl = f"{tn}에서 {rl}"
            if iss and P1b:
                pairs.append((f"row:{i}", pk([f"다음은 이슈 종목인 {J(name)} {P1b}습니다.", f"이슈 종목 {J(name)} {P1b}습니다."])))
            elif P1b:
                pairs.append((f"row:{i}", pk([f"{rl}인 {J(name)} {P1b}습니다.", f"{J(rl)} {name}, {P1b}습니다.", f"다음은 {rl}, {J(name)} {P1b}습니다."])))
            else:
                pairs.append((f"row:{i}", pk([f"{J(rl)} {name}입니다."])))

        def _said(n: str, v: float, topic: bool = False) -> str:          # '기관이 100억을 샀' / '외국인은 62억을 팔았'
            who = J(n) if topic else subj(n)
            return f"{J(n)} 거의 사고팔지 않았" if abs(v) < 0.5 else f"{who} {obj(hwon(v))} {_verb(v)}"

        if fo is not None and io is not None and dv is not None:
            dn, dvv = _driver(s)
            oth = [(n, v) for n, v in (("외국인", fo), ("기관", io), ("개인", dv)) if n != dn]
            (n2, v2), (n3, v3) = oth[0], oth[1]
            if abs(dvv) >= 0.5 and abs(v2) >= 0.5 and (dvv > 0) == (v2 > 0):
                pairs.append((f"row:{i}_2", pk([f"{subj(dn)} {hwon(dvv)}, {subj(n2)} {obj(hwon(v2))} {_verb(v2)}습니다.", f"{J(dn)} {hwon(dvv)}, {J(n2)} {obj(hwon(v2))} {_verb(v2)}습니다."])))
            else:
                pairs.append((f"row:{i}_2", pk([f"{_said(dn, dvv)}고, {_said(n2, v2, True)}습니다.", f"{_said(dn, dvv, True)}고, {_said(n2, v2, True)}습니다."])))
            if val and i > 0:      # 거래대금은 둘째 종목에서(큰손 돈이 작다는 근거). 첫 종목 거래대금은 계산 문장이 말한다
                pairs.append((f"row:{i}_3", pk([f"{_said(n3, v3, True)}고, 거래대금은 {hwon(val)}입니다.", f"거래대금 {hwon(val)} 가운데 {_said(n3, v3, True)}습니다."])))
            else:
                pairs.append((f"row:{i}_3", pk([f"{_said(n3, v3, True)}습니다.", f"그리고 {_said(n3, v3, True)}습니다."])))
            driver = dn
        elif fo is not None and io is not None:
            pairs.append((f"row:{i}_2", pk([f"{_said('외국인', fo, True)}고, {_said('기관', io, True)}습니다." + (f" 거래대금은 {hwon(val)}입니다." if val else ""),
                                            f"{_said('외국인', fo)}고, {_said('기관', io, True)}습니다." + (f" 거래대금은 {hwon(val)}입니다." if val else "")])))
            driver = "외국인" if fo >= io else "기관"
        else:
            driver = None
        rows_out.append({"name": name, "role": role, "theme": s.get("theme") or th, "pct": pct, "foreign": fo, "inst": io, "indiv": dv, "value": val, "driver": driver})
    bg = [s for s in stocks if s.get("role") == "대형주"]
    if len(bg) == 2 and all(_num(s.get("foreign")) is not None for s in bg):
        a_, b_ = bg
        fa, fb = _num(a_["foreign"]), _num(b_["foreign"])
        if fa * fb < 0 and min(abs(fa), abs(fb)) >= 500:
            buy_, sell_ = (a_, b_) if fa > 0 else (b_, a_)
            pairs.append(("bigpair", pk([f"같은 반도체인데 외국인은 {obj(buy_['name'])} 사고 {obj(sell_['name'])} 팔았습니다.",
                                         f"외국인의 선택은 반대였습니다. {J(buy_['name'])} 사고, {J(sell_['name'])} 팔았습니다."])))
    # 계산 1개 — 주도 주체 순매수 ÷ 거래대금(%) → 두 종목 큰손 합 ÷ 개인 순매도(배) → 외+기 ÷ 거래대금(%)
    s0 = stocks[0]
    val0 = _num(s0.get("value"))
    dn, dvv = _driver(s0)
    if full and val0 and dvv > 0 and _num(s0.get("indiv")) is not None:
        r = _calc("share", dvv, val0)
        if r and r["n"] >= 3:
            calc, kind = r, "K-share"
            # 바로 앞 줄이 둘째 종목이라 '거래대금 390억'만 말하면 어느 종목인지 헷갈린다 — 이름을 붙인다.
            _n0 = s0.get("name") or ""
            pairs.append(("calc", pk([f"{J(_n0)} 거래대금 {hwon(val0)} 가운데 {r['n']}%를 {subj(dn)} 샀습니다.",
                                      f"{_n0} 거래대금 {hwon(val0)} 중 {subj(dn)} 산 게 {r['n']}%입니다.",
                                      f"{_n0} 거래대금 {hwon(val0)}에서 {subj(dn)} 사들인 게 {r['n']}%입니다."])))
    if calc is None and len(stocks) == 2 and all(_num(s.get("indiv")) is not None for s in stocks):
        big = sum((_num(s.get("foreign")) or 0) + (_num(s.get("inst")) or 0) for s in stocks)
        ind = sum(_num(s.get("indiv")) or 0 for s in stocks)
        if big > 0 and ind < 0:
            r = _calc("ratio", big, ind)
            if r:
                calc, kind = r, "K-ratio"
                pairs.append(("calc", pk([f"두 종목 큰손 순매수 {obj(hwon(big))} 개인 순매도로 나누면 {r['n']}배입니다.", f"외국인·기관 {hwon(big)} 대 개인, 나누면 {r['n']}배입니다.",
                                          f"두 종목에서 큰손이 산 {J(hwon(big))} 개인이 판 돈의 {r['n']}배입니다."])))
    if calc is None and val0:
        big0 = (_num(s0.get("foreign")) or 0) + (_num(s0.get("inst")) or 0)
        r = _calc("share", abs(big0), val0) if big0 else None
        if r:
            calc, kind = r, "K-fi"
            pairs.append(("calc", pk([f"외국인·기관 순매{'수' if big0 > 0 else '도'}를 거래대금 {ro(hwon(val0))} 나누면 {r['n']}%입니다.", f"거래대금 {hwon(val0)} 가운데 큰손 몫은 {r['n']}%입니다.",
                                      f"큰손 돈을 거래대금 {ro(hwon(val0))} 나눈 값은 {r['n']}%입니다."])))
    if calc is None:
        pairs.append(("calc", pk(["큰손 돈이 거래대금에 견줘 작아 비율은 1%도 안 됩니다.", "거래대금에 견주면 큰손 몫은 1% 아래입니다.", "비율로 재면 큰손 돈은 1%에도 못 미칩니다."])))
    if calc:
        calc = {k: v for k, v in calc.items() if k != "n"}
        calc["verified"] = True
    # 누가 밀어 올렸나
    if len(rows_out) == 2 and rows_out[0]["driver"]:
        a, b = rows_out
        big_b = (_num(b.get("foreign")) or 0) + (_num(b.get("inst")) or 0)
        small_b = (b.get("value") or 0) and big_b < 0.1 * (b.get("value") or 1)
        bd = "큰손 돈이 작은 상승" if (small_b and (b.get("pct") or 0) > 0) else ("외국인과 기관이 같이 산 상승" if ((b.get("foreign") or 0) > 0 and (b.get("inst") or 0) > 0 and (b.get("pct") or 0) > 0)
                                                                              else f"{b['driver']}이 받친 자리" if b.get("driver") else "돈보다 값이 먼저 움직인 자리")
        ad = f"{a['driver']}이 밀어 올린 상승" if (a.get("pct") or 0) > 0 else f"{a['driver']}이 받은 자리"
        pairs.append(("driver", pk([f"{J(a['name'])} {ad}, {J(b['name'])} {bd}입니다.", f"{obj(a['name'])} 밀어 올린 손은 {a['driver']}, {J(b['name'])} {bd}입니다.",
                                    f"정리하면 {J(a['name'])} {ad}이고 {J(b['name'])} {bd}입니다."])))
    elif rows_out and rows_out[0]["driver"]:
        a = rows_out[0]
        pairs.append(("driver", pk([f"{J(a['name'])} {a['driver']}이 {'밀어 올린' if (a.get('pct') or 0) > 0 else '받은'} 자리입니다.", f"{obj(a['name'])} {'밀어 올린' if (a.get('pct') or 0) > 0 else '받친'} 손은 {a['driver']}입니다."])))
    return pairs, {"doc": doc, "date": day, "stocks": rows_out, "calc": calc, "kind": kind, "full": full, "no_indiv": not full, "pairs": pairs}, kind


# ══════════════════════════════════════════════════════════════════════════════
# S5 뉴스와 맞물렸나 — 뉴스 ≤2(이슈 메모 head 문장 → 제목에 업종·종목 이름이 든 기사; 압축 판은 이슈 키워드 한 줄) → 양면 프레임 고정(말은 회전)
# → 업종마다 '오늘 [업종]은 [돈/뉴스] 쪽입니다' → 뒤집히는 조건(임계값) → S0 콜백(계산) → 한계 1문장. 대체: 이슈·기사 없음 → '뉴스 없이 수급만 움직인 날' + 판정은 돈 쪽.
# ══════════════════════════════════════════════════════════════════════════════
_A = ["뉴스만으로 오른 거라면 외국인과 기관은 크게 사지 않습니다.", "기사 힘으로 오른 날엔 큰손 돈이 작습니다.", "뉴스가 끌어올린 값이면 큰손은 별로 안 삽니다.",
      "뉴스 덕에 오른 거라면 외국인·기관 순매수는 작습니다.", "재료만으로 오른 날은 큰손이 따라 사지 않습니다.", "뉴스가 올린 값이면 큰손 매수는 작게 나옵니다."]
_B = ["돈이 끌어올린 값이면 외국인과 기관이 같이 삽니다.", "진짜 돈이 들어온 날엔 큰손이 같이 삽니다.", "수급이 올린 값이면 외국인·기관 순매수가 따라붙습니다.",
      "돈이 만든 상승이면 큰손 매수가 같이 들어옵니다.", "돈이 올린 날엔 외국인이나 기관이 크게 삽니다.", "돈이 올린 값이면 큰손이 먼저 사 둡니다."]
NEWS_MAX = 46      # 말하는 뉴스 문장 상한(글자) — 넘거나 한 업종에 문장이 둘이면 이슈 키워드 한 줄로 줄인다(BRIEF_FIX_1 §B)


def _clauses(head: str) -> list[str]:
    """이슈 메모 head → 문장 조각들('…됐고, …열었습니다. …겹쳤고요.' → 셋). 끝은 '습니다.' 로 맞춘다(문장 하나 = 단계 하나)."""
    out = []
    for sent in re.split(r"(?<=[다요])\.\s*", (head or "").strip()):
        for cl in re.split(r"(?<=[았었됐했겼왔갔])고,?\s+", sent.strip().rstrip(".")):
            cl = cl.strip().rstrip(".,")
            if not cl:
                continue
            if cl.endswith("고요"):
                cl = cl[:-2] + "습니다"
            elif not cl.endswith(("습니다", "입니다")):
                cl += "습니다" if cl[-1] in "았었됐했겼왔갔" else "입니다"
            out.append(cl + ".")
    return out


def _kw_for(th: str) -> list[str]:
    kws = [th, tname(th)] + list(THEME_KW.get(th) or [])
    try:
        from app.services.themes import THEMES
        kws += [n for _, n in THEMES.get(th) or []]
    except Exception:
        pass
    return [k for k in dict.fromkeys(kws) if k]


def _bad(s: str) -> bool:
    try:
        import sys
        from _common import DATA
        sys.path.insert(0, str(DATA.parent))
        from checks import forbidden
        return any(not h.startswith("단정:") for h in forbidden.find(s))
    except Exception:
        return False


def _theme_of(text: str, themes: list[str], kws: dict[str, list[str]]) -> str | None:
    score = {th: sum(1 for k in kws[th] if k and k in text) for th in themes}
    return max(score, key=score.get) if score and max(score.values()) > 0 else None


def _news_for(x: dict, themes: list[str], stock_names: list[str]) -> tuple[list[dict], list[dict]]:
    """(업종별 뉴스 문장 ≤3, 압축 키워드 줄). 문장: [{theme, spoken, title, source, extra}] — 이슈 메모(event.head) 가 그 업종을 말하면 그 문장, 아니면 제목에 이름이 든 기사.
    압축: 이슈 keywords 가운데 업종 이름·종목 이름·수급 낱말이 아닌 것을 업종별로 묶은 [{theme, kws}] — 길이 예산이 모자랄 때 한 문장으로 말한다."""
    out: list[dict] = []
    ev = x["ev"]
    kws = {th: _kw_for(th) + [n for n in stock_names if n] for th in themes}
    ev_names = [s.get("name") for s in x["ev_st"] if s.get("name")]
    ev_group = (ev.get("group") or ev.get("label") or "이슈 종목") if ev else ""
    compact: list[dict] = []
    if ev and ev.get("head"):
        prev = None
        for cl in _clauses(ev["head"]):
            if _ntok(cl) > 2 or _bad(cl):
                continue
            th = _theme_of(cl, themes, kws) or prev or ev_group
            prev = th if th in themes else prev
            k = sum(1 for o in out if o["theme"] == th)
            if k >= 2 or len(out) >= 3:
                continue
            out.append({"theme": th, "spoken": cl, "title": cl.rstrip(".")[:60], "source": "이슈 메모", "extra": k >= 1})
        skip = set(themes) | {tname(t) for t in themes} | set(ev_names) | set(stock_names) | {f"{t}주" for t in themes}
        by: dict[str, list[str]] = {}
        for kw in (ev.get("keywords") or []):
            kw = str(kw).strip()
            if not kw or kw in skip or _GENERIC_KW.search(kw) or len(kw) > 14:
                continue
            th = _theme_of(kw, themes, kws) or ev_group
            if len(by.get(th, [])) < 2:
                by.setdefault(th, []).append(kw)
        compact = [{"theme": t, "kws": v} for t, v in by.items()]
    # 긴 문장(NEWS_MAX 초과)이거나 한 업종에 문장이 둘이면 그 업종은 이슈 키워드 한 줄로 줄인다 — 같은 재료를 절반 길이로(BRIEF_FIX_1 §B)
    kw_by = {k["theme"]: k["kws"] for k in compact if k.get("kws")}
    n_th = {th: sum(1 for o in out if o["theme"] == th) for th in {o["theme"] for o in out}}
    long_th = {o["theme"] for o in out if o["source"] == "이슈 메모" and o["theme"] in kw_by and (len(o["spoken"]) > NEWS_MAX or n_th[o["theme"]] >= 2)}
    if long_th:
        kept, done = [], set()
        for o in out:
            th = o["theme"]
            if th in long_th:
                if th not in done:
                    done.add(th)
                    kept.append({"theme": th, "spoken": "", "kws": kw_by[th], "title": " · ".join(kw_by[th]), "source": "이슈 메모", "extra": False, "kw": True})
                continue
            kept.append(o)
        out = kept
    used = {o["theme"] for o in out}
    for th in themes:
        if th in used or len(out) >= 3:
            continue
        for it in x["news"]:
            title = re.sub(r"\[[^\]]*\]|\([^)]*\)|[\"'“”‘’]", "", str(it.get("title") or "")).strip()
            if not any(k in title for k in kws[th][:3] + [n for n in stock_names if n]) or _ntok(title) > 2 or _bad(title):
                continue
            title = re.split(r"…|\.\.\.|\s[-–—]\s", title)[0].strip()[:48]
            if len(title) < 8:
                continue
            # 매체 이름이 도메인이면(digitaltoday.co.kr) 읽지 않는다 — 소리로 들으면 알아들을 수 없다
            src = (it.get("source") or "").strip()
            say_src = "" if ("." in src or not src) else src
            sp = f"'{title}' 소식이 있었습니다."
            out.append({"theme": th, "spoken": sp, "title": title, "source": src, "extra": False})
            used.add(th)
            break
    return out, compact


def _side(r: dict) -> str:
    """돈 쪽(b): 외국인·기관 둘 다 순매수이고 합이 MONEY_MIN 이상. 아니면 뉴스 쪽(a)."""
    fo, io, net = _num(r.get("foreign")) or 0, _num(r.get("inst")) or 0, _num(r.get("net")) or 0
    return "b" if (fo > 0 and io > 0 and net >= MONEY_MIN) else "a"


# 시황·수급 목록 기사(종목 이슈가 아니다) — 지수 이름이 들어가거나 '[코스닥 기관]'·'[스팟]' 같은 목록 머리. '[특징주]'는 늘 종목 이슈로 본다
_RECAP = re.compile(r"^\[(?:거래소|코스닥|코스피|유가증권)\s?(?:기관|외국인|개인)\]|\[시가총액|\[스팟\]|\[속보\]|코스피|코스닥")


def _has_batchim(w: str) -> bool:
    ch = (w or " ")[-1]
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


# 오른 이유로 쓸 수 있는 제목: 값이 움직였다는 말이 있어야 한다(9/17 '삼성중공업 공정위 제재에 113억원 상생안' 이 '제재 소식에 올랐다'로 뽑혔다)
_MOVE_UP = re.compile(r"강세|상승|급등|↑|오름|올라|뛰|신고가|반등|불기둥|치솟|랠리|껑충")
_MOVE_DN = re.compile(r"약세|하락|급락|↓|내림|떨어|추락|신저가|밀려")
_BAD_REASON = re.compile(r"제재|과징금|벌금|소송|적발|압수수색|기소|징계|사고|화재|파업|리콜|횡령|배임")


_BOND_MARK = ("숫자와 친해", "기분이나 감", "감으로 사고팔", "기분은 매일 바뀌")


def _bond(d: str, x: dict, s4: dict, pk, pairs: list) -> tuple[int, str] | None:
    """채널의 생각 한 줄 — 시청자와의 유대(JJ 2026-09-17: "숫자와 친해져야 합니다. 매수·매도할 때 그 순간의 기분, 감으로 하시면 절대 안 됩니다.
    숫자와 친해져서 그 숫자의 의미를 파악해야 합니다."). 매일 같은 훈계는 설교·AI 티라서 격일(전 편에 있었으면 쉰다).
    숫자를 되풀이하지 않고 바로 앞 문장의 숫자에 '이런·이렇게'로 붙인다. '매수·매도' 낱말은 금지어라 '사고팔'로. 반환: (넣을 자리, 문장)."""
    try:
        from _common import DATA, load_json
        h = load_json(DATA / "script_history.json") or {}
        eds = sorted([e for e in (h.get("editions") or []) if isinstance(e, dict) and str(e.get("date", ""))[:8] < d[:8] and not e.get("draft")],
                     key=lambda e: str(e.get("date")))
        if eds and any(m in " ".join(z.get("raw", "") for z in (eds[-1].get("sentences") or [])) for m in _BOND_MARK):
            return None
    except Exception:
        pass
    tags = [t for t, _ in pairs]
    # ① 돈이 실제로 들어온 종목 판정 바로 뒤
    for k, (t, txt) in enumerate(pairs):
        if t.startswith("verdict:") and re.search(r"실제로 (?:돈이 )?들어온|실제로 들어왔", txt):
            return k + 1, pk(["오른 기분보다, 누가 얼마를 샀는지라는 숫자와 먼저 친해져야 합니다.",
                              "사고팔 때 그 순간의 감으로 하면 안 됩니다. 이렇게 숫자의 뜻을 먼저 읽어야 합니다.",
                              "숫자와 친해져야 합니다. 오른 이유를 기분이 아니라 이런 숫자로 읽어야 합니다."])
    # ② 흐름 근거(외국인 연속 매도 등) 바로 뒤
    if "flow" in tags:
        k = tags.index("flow")
        frg = _num((x.get("vals") or {}).get("외국인"))
        cands = (["감으로 사고팔면 이런 날 겁부터 나지만, 숫자와 친해지면 돈이 어디로 갔는지가 보입니다.",
                  "사고팔 때의 기분은 매일 바뀌지만, 이 숫자는 그대로 남습니다. 숫자와 먼저 친해져야 합니다."] if (frg or 0) < 0 else
                 ["산 날일수록 기분보다, 그 돈이 어디로 갔는지 숫자와 먼저 친해져야 합니다."])
        return k + 1, pk(cands)
    return None


def _big_mover(s4: dict) -> dict | None:
    """이슈 없는 날 — s4 종목 가운데 등락률이 가장 크게 움직인 하나(±3% 이상)를 말하고, 외국인·기관·개인 숫자로 그 뜻을 풀이한다."""
    rows = [r for r in (s4.get("stocks") or []) if _num(r.get("pct")) is not None]
    if not rows:
        return None
    r = max(rows, key=lambda r: abs(_num(r.get("pct"))))
    pct = _num(r.get("pct"))
    if abs(pct) < 3:
        return None
    name, up = r["name"], pct > 0
    fo, io, dv, val = _num(r.get("foreign")), _num(r.get("inst")), _num(r.get("indiv")), _num(r.get("value"))
    say = f"대신 {J(name, '이', '가')} {pct2(pct)} {'올랐' if up else '내렸'}습니다."
    if fo is None or io is None:
        return {"name": name, "theme": r.get("theme") or "", "side": "a", "say": say, "judge": f"{name}은 외국인·기관 숫자가 없어 누가 움직였는지 가르기 어렵습니다."}
    fi = fo + io
    if up:
        if fi >= 50 and (not val or fi >= 0.05 * val):
            side, judge = "b", f"외국인과 기관이 합쳐 {obj(hwon(fi))} 샀으니, 실제로 돈이 들어온 상승입니다."
        elif max(fo, io) > 0 and min(fo, io) < 0:
            bn, bv, sn, sv = ("기관", io, "외국인", fo) if io >= fo else ("외국인", fo, "기관", io)
            side, judge = "a", f"{subj(bn)} {obj(hwon(bv))} 샀지만 {J(sn)} {obj(hwon(abs(sv)))} 팔았으니, 한쪽 돈만 들어온 상승입니다."
        elif (dv or 0) > 0:
            side, judge = "a", f"외국인과 기관은 {'오히려 ' + obj(hwon(abs(fi))) + ' 팔았고' if fi < 0 else obj(hwon(fi)) + '만 샀고'}, 개인이 {obj(hwon(dv))} 사서 끌어올린 상승입니다."
        else:
            side, judge = "a", f"외국인과 기관이 산 돈은 {hwon(fi)}뿐이라, 큰돈이 만든 상승은 아닙니다."
    else:
        if fi <= -50:
            side, judge = "b", f"외국인과 기관이 합쳐 {obj(hwon(abs(fi)))} 팔아 값이 밀렸습니다."
        elif (dv or 0) < 0:
            side, judge = "a", f"개인이 {obj(hwon(abs(dv)))} 팔아 값이 밀렸습니다."
        else:
            side, judge = "a", f"외국인과 기관은 크게 팔지 않았는데 값이 밀렸습니다."
    return {"name": name, "theme": r.get("theme") or "", "side": side, "say": say, "judge": judge}


def _stock_issues(x: dict, s4: dict, kwl: list | None = None) -> list[dict]:
    """s4 두 종목(대장주·가장 많이 오른 종목)에 붙은 이슈 기사 → 말할 문장 + '뉴스로만 올랐나, 진짜 돈이 들어왔나' 판정.
    JJ 2026-09-17: "오늘 오른 종목들 중에 관련된 뉴스와 연관해서, 그 종목들이 오른 게 뉴스 기사로만 오른 건지
    아니면 진짜 돈이 들어온 건지를 같이 말해 줬어야지." — 시황 제목('반도체 반등에 코스피 1.37% 상승')은 쓰지 않는다."""
    out = []
    for r in (s4.get("stocks") or []):
        name = r.get("name")
        if not name:
            continue
        pct = _num(r.get("pct"))
        mv_rx = _MOVE_DN if (pct is not None and pct < 0) else _MOVE_UP
        cands = [it for it in x["news"] if name in (it.get("title") or "") and ("특징주" in (it.get("title") or "") or not _RECAP.search(it.get("title") or ""))
                 and mv_rx.search(it.get("title") or "") and not (pct and pct > 0 and _BAD_REASON.search(it.get("title") or ""))]
        ev = x.get("ev") or {}
        if cands:
            cands.sort(key=lambda it: 0 if "특징주" in it["title"] else 1)
            cands = [c for c in cands if re.search(re.escape(name) + r"[,\s·…]+(.+?)(?:에|으로|로)\s", re.sub(r"^\[[^\]]*\]\s*", "", c["title"]))] or cands[:0]
        if cands:
            it = cands[0]
            title = re.sub(r"^\[[^\]]*\]\s*", "", it["title"]).strip()
            m = re.search(re.escape(name) + r"[,\s·…]+(.+?)(?:에|으로|로)\s", title)
            reason = m.group(1).strip() if (m and 4 <= len(m.group(1)) <= 32) else ""
            if not reason:
                cands = []
            elif not reason.endswith(("소식", "기대", "우려", "전망", "효과")):
                reason += " 소식"
            elif reason.endswith(("기대", "우려", "효과")):
                reason += " 소식"
        elif name in _issue_names(x) and (ev.get("spoken") or ev.get("label")):
            # 이슈 메모 키워드는 여러 업종 것이 섞여 있다(9/15: 포드 CATL·로봇주·삼현) — 이 종목 업종으로 묶인 키워드만 쓴다
            kw_by = {k.get("theme"): k.get("kws") for k in (kwl or []) if isinstance(k, dict)}
            th_r = r.get("theme") or ""
            kws = kw_by.get(th_r) or next((v for k, v in kw_by.items() if k and tname(k) == tname(th_r)), None)
            themes_in_ev = {k for k in kw_by if k}
            if kws:
                reason = _and(kws[:2])
            elif len(themes_in_ev) <= 1:
                reason = str(ev.get("spoken") or ev.get("label")).strip()
            else:
                continue
            it = {"title": str(ev.get("label") or ev.get("spoken")), "source": "이슈 메모"}
            title = it["title"]
            if not reason.endswith("소식"):
                reason += " 소식"
        else:
            continue
        lim = pct is not None and pct >= 29.5
        P = (f"상한가 {pct2(pct)}까지 올랐" if lim else f"{pct2(pct)} {'올랐' if pct > 0 else '내렸'}") if pct is not None else ""
        if reason and P:
            say = f"{J(name)} {reason}에 {P}습니다."
        elif P:
            say = f"{J(name)} '{title[:40]}' 기사가 나온 날 {P}습니다."
        else:
            say = f"{name}에는 '{title[:40]}' 기사가 나왔습니다."
        fo, io, dv, val = _num(r.get("foreign")), _num(r.get("inst")), _num(r.get("indiv")), _num(r.get("value"))
        if fo is None or io is None:
            judge, side = f"{name}은 외국인·기관 숫자가 없어 뉴스로 오른 건지 가르기 어렵습니다.", "a"
        else:
            fi = fo + io
            if fi >= 50 and (not val or fi >= 0.05 * val):
                side = "b"
                judge = f"외국인과 기관이 합쳐 {obj(hwon(fi))} 샀으니, 뉴스만이 아니라 실제로 돈이 들어온 상승입니다."
            elif max(fo, io) > 0 and min(fo, io) < 0:
                side = "a"
                bn, bv, sn, sv = ("기관", io, "외국인", fo) if io >= fo else ("외국인", fo, "기관", io)
                judge = f"{subj(bn)} {obj(hwon(bv))} 샀지만 {J(sn)} {obj(hwon(abs(sv)))} 팔았으니, 큰돈보다 뉴스로 오른 쪽에 가깝습니다."
            elif fi > 0:
                side = "a"
                judge = f"외국인과 기관이 산 돈은 {hwon(fi)}뿐이라, 뉴스로 오른 상승에 가깝습니다."
            else:
                side = "a"
                judge = (f"외국인과 기관은 오히려 {obj(hwon(abs(fi)))} 팔았으니, 뉴스로 오른 상승입니다." if (pct or 0) > 0 else
                         f"외국인과 기관이 {obj(hwon(abs(fi)))} 팔아 뉴스에도 값이 밀렸습니다.")
        out.append({"name": name, "theme": r.get("theme") or "", "title": it["title"], "source": it.get("source") or "", "say": say, "judge": judge,
                    "side": side, "up": (pct or 0) > 0})
    return out


def _s5(x: dict, s0: dict, s4: dict, pk: Picker, compact: bool = False) -> tuple[list, dict, str]:
    d = x["d"]
    pk = ScenePick(pk)
    themes_in = x["in_ths"] or ([x["out_th"]] if x["out_th"] else [])
    stock_names = [s["name"] for s in (s4.get("stocks") or [])]
    news, kwl = _news_for(x, themes_in, stock_names)
    pairs: list[tuple[str, str]] = []
    sis = _stock_issues(x, s4, kwl)
    verdicts = []
    ov = x.get("ov")
    if ov:
        # 주간 미국 브리핑에서 자세히 다룬다 — 여기선 짧게, 여러 매체가 같이 말한 것만(JJ 2026-09-17 "간단하게")
        pairs.append(("lead", pk(["오늘 주요 이슈를 보겠습니다.", "먼저 오늘의 주요 이슈입니다."])))
        verb = {"인상": "올렸", "인하": "내렸"}.get(ov["act"], "")
        head = (f"간밤 미국 연준이 {'만장일치로 ' if ov.get('unani') else ''}금리를 {ov['bp']}%포인트 {verb}습니다." if (ov.get("bp") and verb)
                else f"간밤 미국 연준이 {_ov_act(ov)}습니다.")
        hooked = bool(x.get("hook_macro"))
        if not hooked:
            pairs.append(("macro", head))
        # 훅에서 이미 금리를 말한 날은 주어를 붙여 연다('간밤 연준은 …') — 주어 없이 '…신호도 줬습니다'로 시작하지 않는다
        if ov.get("more"):
            pairs.append(("macro_2", "간밤 연준은 연내 한 번 더 올릴 수 있다는 신호도 줬습니다." if hooked else "연내 한 번 더 올릴 수 있다는 신호도 줬습니다."))
        elif ov.get("quote"):
            pairs.append(("macro_2", f"{J(ov['chair'])} 인플레이션이 너무 높고 너무 오래 이어졌다고 했습니다."))
        if ov.get("span") and ov["act"] != "동결":
            pairs.append(("macro_1", f"{ov['span']} 만의 {ov['act']}이었습니다."))
        if ov.get("gap"):
            pairs.append(("macro_3", f"이제 한미 금리차는 {ov['gap']}%포인트로 벌어졌습니다."))
        elif ov.get("y10"):
            pairs.append(("macro_3", f"미국 10년물 금리는 {ov['y10']}%를 넘었습니다."))
        # 이슈 → 돈: 금리 인상 수혜로 꼽히는 금융에 실제로 돈이 들어갔는지(우리 수급으로 확인한 것만)
        fin = next((t for t in (x.get("themes") or {}) if tname(t) == "금융" or t == "금융"), None)
        fr = (x.get("themes") or {}).get(fin) or {}
        if ov["act"] == "인상" and ov.get("fin_up") and fin:
            fnet, finst, ffor = _num(fr.get("net")) or 0, _num(fr.get("inst")) or 0, _num(fr.get("foreign")) or 0
            if max(finst, ffor) >= 100 and min(finst, ffor) <= -100:
                # 둘이 엇갈린 날은 합계로 뭉개지 않는다(9/17 금융: 기관 +427 · 외국인 −287 → 합 +141 을 '외국인과 기관이 샀다'로 말하면 틀린다)
                bn, bv, sn, sv = ("기관", finst, "외국인", ffor) if finst > ffor else ("외국인", ffor, "기관", finst)
                pairs.append(("macro_link", f"금리 인상 수혜로 꼽히는 금융에는 {subj(bn)} {obj(hwon(bv))} 샀지만, {J(sn)} {obj(hwon(abs(sv)))} 팔았습니다."))
            elif fnet >= 100:
                pairs.append(("macro_link", f"금리 인상 수혜로 꼽히는 금융에는 실제로 외국인과 기관이 {obj(hwon(fnet))} 샀습니다."))
            elif finst >= 100:
                pairs.append(("macro_link", f"금리 인상 수혜로 꼽히는 금융에는 기관이 {obj(hwon(finst))} 샀습니다."))
            elif fnet <= -100:
                pairs.append(("macro_link", f"금리 인상 수혜로 꼽히는 금융에서도 외국인과 기관은 {obj(hwon(abs(fnet)))} 팔았습니다."))
    if sis:
        if not ov:
            pairs.append(("lead", pk(["오늘 주요 이슈를 보겠습니다.", "오늘 오른 종목에 어떤 뉴스가 있었는지 보겠습니다.", "이번엔 오른 종목의 뉴스를 보겠습니다."])))
        for k, o in enumerate(sis[:2]):
            pairs.append((f"issue:{k}", ("종목으로 보면 " + o["say"]) if (ov and k == 0) else o["say"]))
            pairs.append((f"verdict:{k}", o["judge"]))
            verdicts.append({"theme": o["theme"] or (themes_in[0] if themes_in else ""), "name": o["name"], "side": o["side"], "text": o["judge"]})
            if o["side"] == "b" and o["up"]:
                x["verdict_up"] = True
        news = [{"title": o["title"], "source": o["source"], "theme": o["theme"]} for o in sis[:2]]
    if not sis:
        # 기사 제목을 그대로 읽는 뉴스('…' 소식이 있었습니다)는 쓰지 않는다(JJ 9/16 "이걸 왜 말한 거야?") — 이슈 메모·키워드로 요약된 것만.
        # 그런 게 없으면 '큰 이슈는 없었다 + 크게 움직인 종목과 그 뜻'으로 간다(JJ 2026-09-17).
        news = [o for o in news if o.get("kw") or o.get("source") == "이슈 메모"]
        if news and not ov:     # JJ 2026-09-17: "그냥 오늘 주요 이슈 알아보겠습니다 하고 설명하고, 이게 오늘 시장에 어떤 영향을 줬는지"
            pairs.append(("lead", pk(["오늘 주요 이슈를 보겠습니다.", "이번엔 오늘의 주요 이슈입니다.", "오늘 시장에 나온 이슈를 보겠습니다.", "오늘 주요 뉴스를 보겠습니다."])))
        if len(news) >= 2 and all(o.get("kw") for o in news[:2]) and not compact:
            # 두 업종 다 키워드 한 줄이면 한 문장으로 묶는다 — 'news:1' 은 예산에서 먼저 빠지는 칸이라 그대로 두면 둘째 뉴스가 사라진다
            news = news[:2]
            core = ", ".join(f"{tname(o['theme'])}에는 {_and(o['kws'])}" for o in news)
            pairs.append(("news:0", pk([f"{core} 소식이 있었습니다.", f"{core} 뉴스가 나왔습니다."])))
        elif news and compact and kwl:
            # 압축 판: 이슈 키워드를 업종별로 묶어 한 문장 — '이차전지는 포드 CATL 뉴스, 로봇은 제조AI와 중국산 로봇 규제 뉴스였습니다.'
            parts = [(f"{tname(k['theme'])}에는 {_and(k['kws'])}" if k["theme"] in themes_in else f"{k['theme']}에는 {_and(k['kws'])}") for k in kwl[:2]]
            core = ", ".join(parts)
            pairs.append(("news:0", pk([f"{core} 소식이 있었습니다.", f"{core} 뉴스가 나왔습니다."])))
            news = [{"theme": k["theme"], "title": " · ".join(k["kws"]), "source": "이슈 메모", "extra": False} for k in kwl[:2]]
        elif news:
            n_groups = len({o["theme"] for o in news})
            del n_groups
            seen_th: dict[str, int] = {}
            for o in news:
                k = seen_th.get(o["theme"], 0)
                seen_th[o["theme"]] = k + 1
                tn = tname(o["theme"])
                if o.get("kw"):        # 이슈 키워드 한 줄(긴 뉴스 문장을 줄인 판)
                    core = _and(o["kws"])
                    spoken = pk([f"{tn}에는 {core} 소식이 있었습니다.", f"{J(tn)} {core} 뉴스가 나왔습니다.", f"{tn} 관련해서는 {core} 소식이 있었습니다."])
                elif o["source"] == "이슈 메모":
                    spoken = o["spoken"] if k else pk([f"{J(tn)} {o['spoken']}", f"먼저 {tn}입니다. {o['spoken']}"]) if o["theme"] in themes_in else \
                        pk([f"{o['theme']} 소식입니다. {o['spoken']}", f"{o['theme']} 관련 소식입니다. {o['spoken']}"])
                else:
                    spoken = o["spoken"]
                pairs.append(("news_x" if o.get("extra") else f"news:{len([p for p in pairs if p[0].startswith('news:')])}", spoken))
        else:
            # JJ 2026-09-17: "이슈가 없는 날은 굳이 안 넣어도 돼. 오늘 큰 이슈가 없었는데 어떤 주식의 등락률이 크게 있었다고 말해 주고 어떤 의미일지 풀이."
            sox = None
            try:                                             # v7(9/18): 국내 이슈가 없어도 간밤 미국 반도체가 크게 움직였으면 그게 오늘의 배경이다
                from _common import DATA as _D, load_json as _lj
                sox = _num((((_lj(_D / x["d"] / "raw" / "us_index.json") or {}).get("index") or {}).get("SOX") or {}).get("pct"))
            except Exception:
                sox = None
            if not ov and sox is not None and abs(sox) >= 2:
                pairs.append(("news:0", pk([f"국내에선 따로 큰 이슈가 없었습니다. 대신 간밤 미국 반도체지수가 {pct1(sox)} {'올랐' if sox > 0 else '내렸'}습니다.",
                                            f"오늘 배경은 간밤 미국입니다. 미국 반도체지수가 {pct1(sox)} {'올랐' if sox > 0 else '내렸'}습니다."])))
            else:
                pairs.append(("news:0", pk(["종목에선 따로 큰 이슈가 없었습니다."] if ov else ["오늘은 시장을 흔든 큰 뉴스가 없었습니다.", "오늘은 눈에 띄는 이슈가 없었습니다."])))
            mv = _big_mover(s4)
            if mv:
                said_bg = any(t == "news:0" and "미국 반도체지수" in v for t, v in pairs)
                pairs.append(("mover", mv["say"][3:] if (said_bg and mv["say"].startswith("대신 ")) else mv["say"]))
                pairs.append(("verdict:0", mv["judge"]))
                verdicts.append({"theme": mv["theme"], "name": mv["name"], "side": mv["side"], "text": mv["judge"]})
                x["mover_said"] = True
        # '뉴스가 올린 값이면 … / 돈이 올린 값이면 …' 같은 틀 설명은 말하지 않는다 — 한 번 더 생각하게 만든다(JJ 2026-09-17).
        # 바로 '반도체 상승은 뉴스 때문만이 아니었습니다. 앞에서 본 것처럼 기관이 8,100억을 사들였습니다'처럼 영향을 말한다.
        # 업종별 판정(이슈 없는 날 크게 움직인 종목을 풀이했으면 업종 판정은 건너뛴다)
        for i, th in enumerate([] if x.get("mover_said") else themes_in[:2]):
            r = x["themes"].get(th) or {}
            has_news = any(o["theme"] == th for o in news)
            net = r.get("net") or 0
            side = _side(r) if net > 0 else "b"
            if not has_news and net > 0:
                side = "b"
            tn, T = tname(th), hwon(net)
            sw = "돈" if side == "b" else "뉴스"
            # 이슈 라벨과 업종 이름이 다르면 둘 다 붙인다(BRIEF_FIX_2 §D-3)
            ilab = _issue_lab(x, th) if has_news else ""
            if side == "b":
                if net <= 0:
                    _lead = _leaders(x, th)
                    _up = bool(_lead) and (_lead[0].get("pct") or 0) > 0
                    _inst = (r.get("inst") or 0) > 0 and (r.get("foreign") or 0) < 0
                    if _up and _inst:            # 9/16 실측: 외국인이 팔고 기관이 받아 값이 오른 날
                        why = "외국인이 판 물량을 기관이 받아 값이 올랐습니다"
                    elif _up:
                        why = "큰손 돈은 빠졌는데 값이 올랐습니다"
                    else:
                        why = "뉴스보다 외국인·기관 매도가 값을 눌렀습니다" if has_news else "뉴스 없이 외국인과 기관이 같이 팔았습니다"
                else:
                    why = "뉴스와 외국인·기관 순매수가 같이 갔습니다" if has_news else "뉴스 없이 외국인과 기관이 같이 샀습니다"
                txt, why_s = _effect(x, th, r, side, has_news, second=i > 0)
                pairs.append(("verdict:0" if i == 0 else "verdict:1", txt))
                if why_s and i == 0:
                    pairs.append(("verdict_why", why_s))
            else:
                why = f"들어온 큰손 돈은 {ro(T)} 작았습니다" if (r.get("net") or 0) > 0 else "큰손 돈은 오히려 나갔습니다"
                short = f"큰손 돈은 {T}뿐입니다" if (r.get("net") or 0) > 0 else "큰손 돈은 나갔습니다"
                txt, why_s = _effect(x, th, r, side, has_news, second=i > 0)
                pairs.append(("verdict:0" if i == 0 else "verdict:1", txt))
                if why_s and i == 0:
                    pairs.append(("verdict_why", why_s))
            verdicts.append({"theme": th, "side": side, "text": txt})
        if not verdicts:
            txt = pk(["결국 오늘 값을 만든 건 뉴스보다 실제로 사고판 돈이었습니다.", "오늘은 뉴스보다 사고판 돈이 값을 만들었습니다."])
            pairs.append(("verdict", txt))
            verdicts.append({"theme": "", "side": "b", "text": txt})
    verdict = verdicts[0]["side"]
    # 오늘 돈이 어느 쪽으로 가고 있나 — 판정 바로 뒤 한 줄(BRIEF_FIX_2 §B). 매매 판단이 아니라 돈의 흐름에 대한 판정,
    # 주어는 '돈'·'흐름'·'수급'. 근거 한 마디는 이미 말한 숫자만 되쓴다. 예산에서 빼지 않는다.
    f_score, f_why = _flow_score(x)
    _pre = "다만 " if (x.get("verdict_up") and f_score < 0) else ""   # 앞 문장이 '기관이 실제로 샀다'면 '다만 …'
    f_txt = pk([_pre + t for t in _FLOW_TXT[_flow_grade(f_score)]])
    f_reason = pk(f_why) if f_why else ""
    pairs.append(("flow", f"{f_txt} {f_reason}".strip()))
    # 뒤집히는 조건(임계값 하나)
    news_side = verdicts[0] if (verdicts and verdicts[0]["side"] == "a" and verdicts[0]["theme"]) else None
    nxt = _day_word(d, na.next_trading_day(d).strftime("%Y%m%d"), past=False)
    if verdicts and verdicts[0].get("name"):
        _fg = x["vals"].get("외국인")
        cond = (f"{nxt}에도 외국인이 이어서 사는" if (_fg or 0) > 0 else f"{nxt} 외국인이 사는 쪽으로 돌아서는") if _fg is not None else \
            f"{nxt} 외국인이 {'사는' if x['sold'] else '파는'} 쪽으로 돌아서는"
        cond_note = "판정이 뒤집힙니다"
    elif news_side:
        r = x["themes"].get(news_side["theme"]) or {}
        thr = nh.hround(max(2 * (r.get("net") or 0), 500))
        cond = f"{nxt} {tname(news_side['theme'])}에 외국인·기관 돈이 {hwon(thr)} 넘게 들어오는"
        cond_note = f"{tname(news_side['theme'])}도 돈 쪽으로 넘어갑니다"
    elif verdicts[0]["theme"] and (x["themes"].get(verdicts[0]["theme"]) or {}).get("net", 0) <= 0:
        r = x["themes"].get(verdicts[0]["theme"]) or {}
        thr = nh.hround(max(abs(r.get("net") or 0) / 2, 500))
        cond = f"{nxt} {tname(verdicts[0]['theme'])}에 외국인·기관 돈이 {hwon(thr)} 넘게 돌아오는"
        cond_note = "나가는 돈이 멈춘 겁니다"
    elif verdicts[0]["theme"]:
        r = x["themes"].get(verdicts[0]["theme"]) or {}
        thr = nh.hround(max((r.get("net") or 0) / 2, 100))
        cond = f"{nxt} {tname(verdicts[0]['theme'])}에서 외국인·기관이 {hwon(thr)} 넘게 되파는"
        cond_note = "돈이 아니라 뉴스가 올린 값이 됩니다"
    else:
        _fg = x["vals"].get("외국인")
        cond = (f"{nxt}에도 외국인이 이어서 사는" if (_fg or 0) > 0 else f"{nxt} 외국인이 사는 쪽으로 돌아서는") if _fg is not None else \
            f"{nxt} 외국인이 {'사는' if x['sold'] else '파는'} 쪽으로 돌아서는"
        cond_note = "판정이 뒤집힙니다"
    cond_k = cond.replace("외국인·기관 돈이", "큰손 돈이").replace("외국인·기관이", "큰손이")
    # '팔아야'·'사야'는 추천처럼 들린다(금지어) — '…는 모습이 보여야'로 말한다
    pairs.append(("condition", pk([f"흐름이 바뀌려면 {cond} 모습이 보여야 합니다.", f"흐름이 바뀌는 신호는 하나, {cond} 겁니다.", f"이 흐름이 바뀌려면 {cond} 모습이 나와야 합니다."])))
    # S0 콜백(계산)
    cb_text, cb = _callback(s0, x, said_frac=False, pk=pk)
    if cb_text:
        pairs.append(("callback", cb_text))
    # 한계 1문장
    limit = pk(["주체별 합계라 종목 사이 이동은 이 표에 안 보입니다.", "정규장 체결만 더한 값이라 대량매매는 빠져 있습니다.", "업종 합계는 종목 안의 손바뀜까지는 말해 주지 않습니다.",
                "합산표라 한 종목 안에서 누가 누구에게 넘겼는지는 안 보입니다.", "시간외 거래는 이 합산에 들어 있지 않습니다.", "업종 합계는 그날 손바뀜의 결과일 뿐 이유까지는 말하지 않습니다."])
    pairs.append(("limit", limit))
    # 누가샀나의 생각 한 줄(JJ 2026-09-17: "숫자와 친해져야 합니다. 매수·매도할 때 그 순간의 기분, 감으로 하시면 절대 안 됩니다.") — 격일, 그날 숫자 하나에 묶는다
    bond = _bond(d, x, s4, pk, pairs)
    if bond:
        at, txt = bond                       # 판정 바로 뒤(돈이 들어온 종목) 또는 흐름 근거 바로 뒤(외국인 연속 매도) — 앞 얘기로 되돌아가지 않게
        pairs.insert(at, ("bond", txt))
    first = verdicts[0]
    r0 = x["themes"].get(first["theme"]) or {}
    support = {"label": f"{tname(first['theme'])} 외국인·기관", "value": hwon(r0.get("net") or 0)} if first["theme"] else None
    return pairs, {"news": [{"title": o["title"], "source": o["source"], "theme": o["theme"]} for o in news][:2], "a": "뉴스가 올린 값", "b": "돈이 올린 값",
                   "flow": {"score": f_score, "grade": _flow_grade(f_score), "text": f_txt, "why": f_reason},
                   "verdicts": verdicts, "verdict": verdict, "condition": cond + " 것", "limit": limit, "support": support, "callback": cb or None,
                   "callback_num": (cb or {}).get("a") or None, "pairs": pairs}, "V-" + ("money" if verdict == "b" else "news")


# ══════════════════════════════════════════════════════════════════════════════
# S6 내일 포인트 2~3 + 이벤트 시각 + 애프터마켓 + 시그니처. watch[0] 은 ledger.parse_q 형태.
# 관측값: 외국인(주인공) 순매도 N+1일째 → 유입 업종 이틀째(없으면 기타법인 선) → 이벤트 시각(있으면 셋째 포인트).
# ══════════════════════════════════════════════════════════════════════════════
def _s6(x: dict, c: dict, cont: dict, brand: str, pk: Picker, attempt: int, compact: bool = False) -> tuple[list, dict, str, list]:
    d, P, sold, st = x["d"], x["P"], x["sold"], x["st_p"]
    pk = ScenePick(pk)
    word = _word(x["amount"] if x["amount"] else -1)
    nd = na.next_trading_day(d)
    nxt = _day_word(d, nd.strftime("%Y%m%d"), past=False)
    # '무엇을 보나' 뒤에는 **왜 그게 중요하고 어떤 값이면 의미가 있는지**(why)를 반드시 붙인다.
    # JJ 2026-09-22: "그냥 뭘 봐야할지만 딱 말하지말고 그 이유와 어떤 기준으로 봐야하는지도 알려줘야해."
    # 나열만 하면 시청자가 내일 무엇을 근거로 판단할지 모른다 — 검사기(qa_script S6_CRITERION)가 없으면 실패시킨다.
    if P in ("외국인", "기관"):
        n = (st + 1) if st >= 1 else 2
        next_q = f"{P} {word}가 {dko(n)} 이어지는지"
        w1 = {"q": next_q, "threshold": f"{n}거래일째", "spoken": next_q,
              "why": (f"오늘까지 {dko(st)}라, 하루 더 이어져야 흐름으로 굳어진 것으로 봅니다." if st >= 2
                      else "오늘 하루 만에 방향을 바꾼 자리라, 이틀 연속이라야 방향이 바뀐 것으로 봅니다.")}
    else:
        frg = x["vals"].get("외국인")
        stf = abs(((x["streak"].get("foreign") or {}).get("streak")) or 0)
        wf = "순매도" if (frg or 0) < 0 else "순매수"
        next_q = f"외국인 {wf}가 {dko(stf + 1)} 이어지는지" if stf else f"외국인 {wf}가 이어지는지"
        w1 = {"q": next_q, "threshold": f"{stf + 1}거래일째" if stf else "같은 부호", "spoken": next_q,
              "why": (f"오늘까지 {dko(stf)}라, 하루 더 이어져야 흐름으로 굳어진 것으로 봅니다." if stf >= 2
                      else "오늘 방향을 바꾼 자리라, 이틀 연속이라야 방향이 바뀐 것으로 봅니다.")}
    watch = [w1]
    in_th = x["in_th"]
    oth, ob = x["oth"], cont.get("others_buy_days") or 0
    if in_th and (x["in_t"] or 0) >= 100:
        stk = max(int((x["themes"].get(in_th) or {}).get("streak") or 0), 1)
        q2 = f"{in_th} 순매수가 {dko(stk + 1)} 이어지는지"
        ins = [t for t in (x.get("in_ths") or []) if t != in_th and (_num((x["themes"].get(t) or {}).get("net")) or 0) >= 100]
        if ins and max(int((x["themes"].get(ins[0]) or {}).get("streak") or 0), 1) == stk:
            q2 = f"{tname(in_th)}·{tname(ins[0])} 순매수가 {dko(stk + 1)} 이어지는지"     # 9/17 조선·방산 같은 날 첫 유입
        w2 = {"q": q2, "threshold": dko(stk + 1), "spoken": q2,   # 장부 문장 그대로 말한다 — 짧고, 겹침 검사 예외(BRIEF_FIX_1 §B)
              "why": f"오늘 {hwon(abs(_num(x.get('in_t')) or 0))}이 들어온 자리라, 내일도 들어와야 이어지는 것으로 봅니다."}
    elif oth >= 3000 and ob >= 1:
        obw, _cap = _ob_word(cont, d, ob)
        thr = int(oth // 1000 * 1000)
        w2 = {"q": f"기타법인 순매수가 {obj(hwon(thr))} 지키는지", "threshold": hwon(thr), "spoken": f"기타법인 순매수가 {obj(hwon(thr))} 지키는지", "note": f"{obw} 지켜온 선입니다.",
              "why": f"{hwon(thr)}을 밑돌면 받쳐 주던 힘이 빠진 것으로 봅니다."}
    else:
        w2 = None
    if w2:
        watch.append(w2)
    ev = _next_event(d, c.get("schedule") or [], c.get("fomc_dates") or [])
    n_pts = len(watch) + (1 if ev else 0)
    cw = COUNT_WORD.get(n_pts, str(n_pts))
    pairs: list[tuple[str, str]] = []
    pairs.append(("intro", pk([f"{nxt} 볼 포인트는 {cw}입니다.", f"{nxt} 확인할 건 {cw}입니다.", f"{nxt} 마감에서 볼 건 {cw}입니다.", f"{nxt} 볼 숫자는 {cw}입니다."])))
    # 같은 질문을 이틀 넘게 던지는 중이면 '내일도 같은 자리'로 말한다(BRIEF_FIX_2 §C).
    # 장부 문장(ledger.parse_q 가 읽는 '{주체} {순매수|순매도}가 {N일째} 이어지는지')은 앞말과 따로 떨어진 한 문장으로 그대로 둔다.
    try:
        promise_days = sm.continuity(d, {"watch_family": [sm.q_family(next_q)]}).get("promise_days") or 0
    except Exception:  # noqa: BLE001
        promise_days = 0
    if False and promise_days >= 2:          # v7(JJ 2026-09-19): 시리즈 문장은 구독자가 생길 때까지 쉰다
        pairs.append(("watch_same", f"{nxt}도 우리는 같은 것을 봅니다."))
    pairs.append(("watch:0", plain(f"{w1['spoken']}.").replace("이어지는지.", "이어질 것인지.")))
    if w1.get("why"):
        pairs.append(("watch:0_why", w1["why"]))       # 왜·어떤 기준이면 의미가 있나(JJ 2026-09-22)
    if w2:
        pairs.append(("watch:1", plain(f"{w2['spoken']}.").replace("이어지는지.", "이어질 것인지.")))
        if w2.get("why"):
            pairs.append(("watch:1_why", w2["why"]))
        if w2.get("note"):
            pairs.append(("note", w2["note"]))
    if ev:
        when, lab = ev["when"], ev["label"]
        prob = x.get("fomc_prob")
        third = n_pts == 3
        if prob is not None and "금리" in lab:
            pairs.append(("event", pk([f"그리고 {when} {lab}, 인상 확률 {prob:.0f}%입니다.", f"셋째는 {when} {lab}입니다. 인상 확률은 {prob:.0f}%입니다.", f"{when} {lab}까지 겹칩니다, 인상 확률 {prob:.0f}%."] if third else
                                      [f"그 전에 {when} {lab}, 인상 확률 {prob:.0f}%입니다.", f"{when} {subj(lab)} 먼저입니다. 인상 확률 {prob:.0f}%.", f"시계는 {when} {lab}, 인상 확률 {prob:.0f}%에 맞춰 둡니다."])))
        else:
            pairs.append(("event", pk([f"그리고 {when} {lab}입니다.", f"셋째는 {when} {lab}입니다.", f"{when} {lab}까지 겹칩니다.", f"거기에 {when} {subj(lab)} 있습니다.", f"마지막은 {when} {lab}입니다.", f"셋째 칸은 {when} {lab}입니다."] if third else
                                      [f"그 전에 {when} {subj(lab)} 있습니다.", f"{when} {subj(lab)} 먼저입니다.", f"시계는 {when} {lab}에 맞춰 둡니다.", f"그 앞에 {when} {subj(lab)} 놓여 있습니다.", f"{when} {lab}까지가 시간표입니다."])))
    when_up = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    after = "20260914" <= d <= AFTER_MARKET_NOTICE_UNTIL
    if after:
        pairs.append(("after", "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다."))
    since = "내일부터 " if d == "20260915" else ""
    pairs.append(("sig", f"{na._ieot(brand)} 국장 마감은 {since}매일 {when_up}에 올라옵니다."))
    note = f"인상 확률 {x['fomc_prob']:.0f}%" if (ev and x.get("fomc_prob") is not None and "금리" in ev["label"]) else None
    return pairs, {"watch": watch, "promise_days": promise_days, "event": ({"label": ev["label"], "when": ev["when"], "note": note} if ev else None),
                   "after_market": after, "when": when_up, "pairs": pairs}, next_q, watch


# ══════════════════════════════════════════════════════════════════════════════
# 조립
# ══════════════════════════════════════════════════════════════════════════════
def build(c: dict, avoid: set[str] | None = None, attempt: int = 0) -> dict:
    """수급 브리핑 대본. c 는 compute.narration_inputs() 입력(+ brief_stocks · news_items · flow_day · theme_rows).
    avoid 는 검사에서 걸린 문장 집합(문장 단위로 후보에서 뺀다), attempt 는 회전 오프셋. 전체가 1,250자를 넘으면 선택 문장을 빼고, 그래도 넘으면
    짧은 후보 + 압축 뉴스로 한 번 더 만든다. 어떤 키가 없어도 예외를 내지 않는다(§2 대체 규칙)."""
    out = _build_once(c, avoid, attempt, compact=False)
    if sum(len(sc["tts"]) for sc in out["scenes"]) > TOTAL_MAX:
        out2 = _build_once(c, avoid, attempt, compact=True)
        if sum(len(sc["tts"]) for sc in out2["scenes"]) < sum(len(sc["tts"]) for sc in out["scenes"]):
            out = out2
    return out


def _bigcap_hook(x: dict) -> dict | None:
    """v7(JJ 2026-09-19): 시청자가 가진 종목(SK하이닉스·삼성전자)에서 외국인 선택이 갈린 날 — 두 문장 훅.
    둘 다 외국인 |순매수| ≥ 1,000억이고 부호가 반대일 때만. 금리 훅(MF)이 있는 날은 그쪽이 먼저."""
    big = [s for s in (x.get("bigcaps") or []) if _num(s.get("foreign")) is not None]
    if len(big) < 2:
        return None
    a, b = sorted(big[:2], key=lambda s: -(_num(s["foreign"]) or 0))       # a = 외국인이 산 쪽
    fa, fb = _num(a["foreign"]), _num(b["foreign"])
    if not (fa > 0 > fb and min(abs(fa), abs(fb)) >= 1000):
        return None
    A, B = hwon(fa), hwon(abs(fb))
    pairs = [("a", f"외국인이 오늘 {obj(a['name'])} {A} 샀습니다."), ("b", f"그런데 {J(b['name'])} {obj(B)} 팔았습니다.")]
    return {"kind": "MB", "a": {"label": f"외국인 · {a['name']}", "value": f"+{A}", "num": fa, "unit": "억"},
            "b": {"label": f"외국인 · {b['name']}", "value": f"−{B}", "num": fb, "unit": "억"}, "pairs": pairs,
            "buy": a["name"], "sell": b["name"]}


def _build_once(c: dict, avoid: set[str] | None, attempt: int, compact: bool) -> dict:
    brand = c.get("brand") or "누가샀나"
    attempt = max(0, int(attempt or 0))
    x = bctx(c)
    d = x["d"]
    try:
        exact, masked = sm.seen(d)
    except Exception:
        exact, masked = {}, {}
    comp_like = {"investors": {"kospi": x["inv"]}, "protagonist": {"name": x["P"], "amount": x["amount"]}, "moves": x["moves"],
                 "top_move": c.get("top_move"), "event": x["ev"] or None, "inv_streak": c.get("inv_streak") or {}, "kospi": x["k"],
                 "callback": x["cb"], "others_top": na._others_top({**c, "date": d})}
    try:
        cont = sm.continuity(d, sm.facts(comp_like))
    except Exception:
        cont = {"top_buyer_days": 1, "others_buy_days": 1 if x["oth"] > 0 else 0, "protagonist_days": 1, "yesterday": None}
    x["cont"] = cont
    # 압축 판은 숫자만 다른 문장(masked)을 피하지 않는다 — 검사는 글자 그대로 겹침만 실패로 보고, 짧은 후보가 연일 소진되면 길이가 늘어난다
    pk = NoScreenPick(Picker(d, exact, {} if compact else masked, avoid, attempt, compact=compact))

    hook_kind, hook_parts, s0 = nh._s0(x, pk, attempt)
    x["ov"] = _overnight(d)
    hm = _macro_hook(x)
    if hm:
        x["hook_macro"] = hm
        hook_kind, hook_parts = "MF", hm["parts"]
        s0 = {"kind": "MF", "mode": hm["mode"], "a": hm["a"], "b": hm["b"], "pairs": hm["pairs"]}
    else:
        mb = _bigcap_hook(x)
        if mb:
            x["hook_mb"] = mb
            hook_kind, hook_parts = "MB", [mb["a"]["value"], mb["b"]["value"]]
            s0 = {k: v for k, v in mb.items() if k not in ("buy", "sell")}
    _s0txt = json.dumps(s0, ensure_ascii=False) + json.dumps(hook_parts, ensure_ascii=False)
    x["s0_names_theme"] = any(tname(t) and tname(t) in _s0txt for t in (x.get("themes") or {}))
    p1, s1, q_kind = _s1(x, pk, attempt)
    p2, s2, n_kind = _s2(x, cont, pk, attempt)
    p3a, s3a, wk_rows = _s3a(x, cont, c, pk)
    p3b, s3b = _s3b(x, pk)
    p3c, s3c = _s3c(x, pk)
    p4, s4, k_kind = _s4(x, pk)
    p5, s5, v_kind = _s5(x, s0, s4, pk, compact=compact)
    p6, s6, next_q, watch = _s6(x, c, cont, brand, pk, attempt, compact=compact)

    slots: dict[str, tuple[list, dict]] = {"s0": (s0["pairs"], s0), "s1": (p1, s1), "s2": (p2, s2), "s3a": (p3a, s3a), "s3b": (p3b, s3b),
                                           "s3c": (p3c, s3c), "s4": (p4, s4), "s5": (p5, s5), "s6": (p6, s6)}
    drops = list(GLOBAL_DROP)
    while sum(len(_text(p)) for p, _ in slots.values()) > TOTAL_MAX and drops:
        sid, step = drops.pop(0)
        pairs, info = slots[sid]
        slots[sid] = ([p for p in pairs if p[0] != step], info)
    # JJ 검토 반영(data/<날짜>/script_edit.json) — 장면별 (태그, 문장)을 통째로 바꾼다. 화면 데이터는 생성기 것 + hunter 덮어쓰기.
    # 확인한 사실만 쓴다. 검사(check_brief)는 똑같이 돈다 — 통과 못 하면 폴백된다.
    try:
        from _common import DATA as _D, load_json as _lj
        ed = _lj(_D / d / "script_edit.json") or {}
    except Exception:
        ed = {}
    for sid, prs in (ed.get("pairs") or {}).items():
        if sid in slots and isinstance(prs, list) and prs:
            slots[sid] = ([(str(t), str(v)) for t, v in prs], slots[sid][1])
    for sid, kv in (ed.get("hunter") or {}).items():
        if sid in slots and isinstance(kv, dict):
            slots[sid][1].update(kv)
    scenes = []
    mins = {"s0": 4.0, "s1": 2.5, "s2": 7.0, "s3a": 7.0, "s3b": 7.0, "s3c": 7.0, "s4": 7.0, "s5": 8.0, "s6": 5.0}
    for sid, (pairs, info) in slots.items():
        pairs = [(n, plain(t)) for n, t in pairs]
        tts, steps = _steps(pairs)
        info["tts"], info["steps"] = tts, steps
        scenes.append({"id": sid, "min": mins[sid], "tts": tts, "sub": "" if sid in ("s0", "s6") else tts, "steps": steps})
    if s3b.get("support") and not any(st in ("support", "support_2") for st in s3b["steps"]):      # 말하지 않은 자사주 카드는 화면에도 안 띄운다
        s3b["support"] = None
    if s5.get("callback") and "callback" not in s5["steps"]:                        # 말하지 않은 S0 콜백 칩·한계 문장·어제 대비 칩도 화면에서 뺀다(말마다 화면 반응)
        s5["callback"], s5["callback_num"] = None, None
    if s5.get("limit") and "limit" not in s5["steps"]:
        s5["limit"] = None
    if s4.get("calc") and "calc" not in s4["steps"]:      # 계산 문장이 예산에서 빠졌으면 화면 칩도 검산 대상도 아니다(말한 것만 검산한다)
        s4["calc"] = None
    if "y" not in s3b["steps"]:
        for row in s3b.get("out") or []:
            row["y"] = None
    hunter = {k: {kk: vv for kk, vv in v.items() if kk not in ("tts", "pairs")} for k, v in
              (("s0", s0), ("s1", s1), ("s2", s2), ("s3a", s3a), ("s3b", s3b), ("s3c", s3c), ("s4", s4), ("s5", s5), ("s6", s6))}
    P, amount, sold = x["P"], x["amount"], x["sold"]
    ct = na.contrast(x["k"], c.get("recent_closes") or [], sold) if x["k"] else {"kind": "pct", "text": "", "short": "", "line": None, "n_days": None, "opposite": False}
    opp = [(n, v) for n, v in x["opp"] if n != P]
    bars = [{"name": P, "v": amount}] + [{"name": n, "v": v} for n, v in opp] + [{"name": n, "v": v} for n, v in x["same"]]
    seen_n = {b["name"] for b in bars}
    bars += [{"name": n, "v": v} for n, v in x["vals"].items() if n not in seen_n]
    s2_title = f"{P} {_won_screen(amount, True)},<br>{'·'.join(n for n, _ in opp) or '—'}{'이' if opp else ''} {'받았다' if sold else '팔았다'}"
    lead_th = x["out_th"] if (x["out_th"] and x["out_t"] and (not x["in_t"] or abs(x["out_t"]) >= x["in_t"])) else x["in_th"]
    story_lead = {"theme": lead_th, "t": (x["themes"].get(lead_th) or {}).get("net"), "who": "외국인+기관 합산",
                  "names": (x["themes"].get(lead_th) or {}).get("pos_names") or []} if lead_th else None
    cb = x["cb"]
    cbv = None
    if cb and isinstance(cb.get("check"), dict):
        ch = cb["check"]
        cbv = {"q": cb.get("q"), "kind": ch.get("kind"), "theme": ch.get("theme") or ch.get("name") or "", "n": ch.get("n"), "sign": ch.get("sign"),
               "when": _day_word(d, cb.get("prev_date"), past=True), "ok": cb.get("ok"), "amount": cb.get("t")}
    nd = na.next_trading_day(d)
    tag_when = (c.get("upload_times") or {}).get("kr") or "저녁 5시"
    return {
        "format": "brief", "brand": brand, "tagline": f"오늘 국장, 누가 샀나? · 평일 {tag_when}",
        "hook": hook_parts[0], "hook_parts": hook_parts, "hook_id": hook_kind,
        "devices": sorted({q_kind, n_kind, k_kind, v_kind}), "caution_id": None,
        "next_q": next_q, "watch": [{"q": w["q"], "how": f"{_day_word(d, nd.strftime('%Y%m%d'), past=False)} 15:40 수급에서 확인", "assist": "", "spoken": w.get("spoken") or w["q"]} for w in watch],
        "protagonist": {"name": P, "amount": amount, "sold": sold}, "contrast": ct,
        "check": {"verdict": cbv, "record": c.get("ledger_stats"), "next_q": next_q, "next_day": f"{nd.month}/{nd.day}"},
        "bars": bars, "s2_title": s2_title, "s3_title": lead_th or "", "s3_story": ({"verdict": None, "lead": story_lead, "summary": ""} if story_lead else None),
        "s2_marks": {"answer": "기타법인", "counter": None, "bars": None, "snap": None, "prev": x["prev_inv"].get("others")},
        "event_used": (bool(x["ev"]) and any(o.get("source") == "이슈 메모" for o in (s5.get("news") or []))) or hook_kind == "M4",
        "others_top": na._others_top({**c, "date": d}), "weekend_watch": wk_rows,
        "fx_said": False, "bonding": "", "attempt": attempt, "compact": compact,
        "scenes": scenes, "hunter": hunter,
    }


def lint(scenes: list[dict]) -> list[str]:
    """자체 점검(정식 검사는 qa_script.check_brief) — 숫자 3토큰 이상 · 그런데 2회/연속 · 화면 지시어 <4 · 길이 950~1,150."""
    out = [w for w in nh.lint(scenes) if not w.startswith("[전체]") and "> 예산" not in w]
    total = sum(len(sc.get("tts") or "") for sc in scenes)
    if total > TOTAL_MAX:
        out.append(f"[전체] {total}자 > {TOTAL_MAX}자")
    elif total < TOTAL_MIN:
        out.append(f"[전체] {total}자 < {TOTAL_MIN}자(경고)")
    return out


def check_brief(scenes: list[dict], comp: dict, recs: list[dict] | None = None) -> list[str]:
    """브리핑 검사 — qa_script.check_brief 가 있으면 그것(정식), 없으면 check_hunter 11항 + 설계 §3 고정 내용을 여기서. 실패 '[장면] 규칙 :: 문장'."""
    if _qa is not None and hasattr(_qa, "check_brief"):
        return _qa.check_brief(scenes, comp, recs)
    bad: list[str] = []
    if _qa is not None:
        try:
            bad += _qa.check_hunter(scenes, comp, recs)
        except Exception as e:  # noqa: BLE001
            bad.append(f"[all] 검사 예외 {e!r} :: ")
    by = {str(s.get("id")): (s.get("tts") or "") for s in scenes or []}
    sent = {k: sm.sentences(v) for k, v in by.items()}

    def fail(sid: str, rule: str, s: str = "") -> None:
        bad.append(f"[{sid}] {rule} :: {s}")

    if not all(n in by.get("s2", "") for n in ("외국인", "기관", "개인")):
        fail("s2", "외국인·기관·개인 세 이름이 다 없음", (sent.get("s2") or [""])[0])
    if sum(_ntok(s) for s in sent.get("s2", [])) < 3:
        fail("s2", "숫자 3개 미만", (sent.get("s2") or [""])[0])
    if "코스피" not in by.get("s3a", "") or "코스닥" not in by.get("s3a", ""):
        fail("s3a", "코스닥·코스피 없음", (sent.get("s3a") or [""])[0])
    if not re.search(r"빠졌|나갔|순매도", by.get("s3b", "")):
        fail("s3b", "빠졌|나갔|순매도 없음", (sent.get("s3b") or [""])[0])
    if not re.search(r"들어왔|순매수|들어온 곳이 없었", by.get("s3c", "")):
        fail("s3c", "들어왔|순매수|들어온 곳이 없었 없음", (sent.get("s3c") or [""])[0])
    h = (comp or {}).get("hunter") or {}
    s4h = h.get("s4") or {}
    names = [s.get("name") for s in (s4h.get("stocks") or []) if s.get("name")]
    if names and not all(n in by.get("s4", "") for n in names):
        fail("s4", "두 종목 이름이 다 없음", (sent.get("s4") or [""])[0])
    for p in (("외국인", "기관") if s4h.get("no_indiv") else ("외국인", "기관", "개인")):
        if names and p not in by.get("s4", ""):
            fail("s4", f"주체 없음({p})", (sent.get("s4") or [""])[-1])
    s5 = by.get("s5", "")
    if "뉴스" not in s5:
        fail("s5", "뉴스 없음", (sent.get("s5") or [""])[0])
    if "쪽입니다" not in s5 or "뒤집히는 조건" not in s5:
        fail("s5", "판정(쪽입니다)·뒤집히는 조건 없음", (sent.get("s5") or [""])[-1])
    if "누가샀나였습니다" not in by.get("s6", "") or "국장 마감은" not in by.get("s6", ""):
        fail("s6", "시그니처 없음", (sent.get("s6") or [""])[-1])
    total = sum(len(v) for v in by.values())
    if total > TOTAL_MAX:
        fail("all", f"총 {total}자 > {TOTAL_MAX}자", "")
    return bad
