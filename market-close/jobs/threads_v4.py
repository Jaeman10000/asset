# -*- coding: utf-8 -*-
"""Threads v4 (2026-09-12~): 우리 채널을 처음 보는 사람이 그 글만 읽고 이해되는 완결형 본문 생성 + 검사.
compute.py가 computed_kr.json 저장 뒤 make(d)를 부른다.

JJ 기준(2026-09-12, 최우선):
  - 완결형 반말(-어/-야/-아/-까?). 음슴체(팜·샀음)는 계속 금지. '팜/오름/샀음' 같은 축약 종결형, 'ㅋㅋ' 같은 채팅 기호 금지.
  - 숫자는 풀어 쓴다(9.9조 → '9조 9천억', 2.3조 → '2조 3천억', 4,700억은 그대로).
  - 내부 장치(예고→검증 '확인 N번 중 M번', 연속 카운터)는 본문에서 뺀다. 넣어야 하면 한 문장으로 풀어 쓴다.
  - 첫 문단 2줄이 전부다(JJ 2026-09-13): 1줄은 독자가 오늘 이미 본 것(앱·뉴스의 코스피 등락)을 인정하고,
    2줄은 그것만 보면 놓치는 사실을 던진다. 2줄에 숫자가 없으면 실패다(T2c). 1줄은 SEEN_UP/SEEN_DOWN 뱅크로 돌린다.
    인정 구간(첫 세 줄)에 코스피 숫자를 두 번 넣지 않는다(T2d).
  - 쓰레드는 금융 용어를 쓰지 않는다(JJ 2026-09-13 두 번째 지시). 스레드 피드는 지나가는 사람이라
    영상보다 한 단계 더 쉽게 쓴다. 순매수·순매도/수급/기타법인/자사주 매입/지수/물량/체결/종가는 BAN_JARGON이 잡는다.
  - 구조: (0) 이미 본 것 → (1) 놓치는 사실 → (2) 누가 받았나/어디로 갔나 → (3) 그게 무슨 뜻일 수 있나. 가운데 질문 한 줄.
  - 채널 고지·영상 링크·다음 거래일에 볼 것은 본문이 아니라 첫 답글(reply)이 맡는다. 본문 마지막 줄은 '그래서 무슨 뜻'.
  - 350~420자, 8~18줄(문단 사이 빈 줄 포함). 350자 미달은 T2e가 잡는다. 해시태그는 publish가 붙인다.
  - 날마다 같은 문장이면 안 된다 — 문장 뱅크 + 이력 기반 회전(pick/mask/bigrams) 유지.

Run:  python threads_v4.py
  - builds the seed for 20260908..20260911 in sequence (history accumulates)
  - asserts seed == SAMPLES[d] and check(sample) == []
  - asserts the old posts fail, and every adversarial variant fails
"""
import io, json, math, os, re, sys
from datetime import datetime

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from checks import forbidden  # noqa: E402

DATA = os.path.join(ROOT, "data")
GROUPS = (("개인", "indiv"), ("외국인", "foreign"), ("기관", "inst"), ("기타법인", "others"))
DAYC = {1: "하루", 2: "이틀째", 3: "사흘째", 4: "나흘째", 5: "닷새째", 6: "엿새째", 7: "이레째"}
DAYN = {2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레"}
CNT = {2: "두 번", 3: "세 번", 4: "네 번", 5: "다섯 번", 6: "여섯 번", 7: "일곱 번", 8: "여덟 번", 9: "아홉 번", 10: "열 번"}
# 새 형식: 문단 사이 빈 줄을 포함한 전체 줄 수 8~20, 본문 500자 이내, 한 줄 36자(첫 줄 32자)
# 반말로 바꾸면서 한 줄이 3~4자씩 짧아졌다 — 한 줄 상한을 36자로 내리고(한 호흡에 한 줄) 줄 수 상한을 20으로 올린다.
MAX_LINES, MIN_LINES, MAX_CHARS, MIN_CHARS, MAX_LINE, MAX_L1 = 20, 8, 500, 110, 36, 32
MIN_BODY_LINES, MAX_FIGS = 6, 5   # 목표 330~430자로 길어지면서 숫자 하나를 더 허용한다(예전 4개는 250자 기준)
TARGET_CHARS_MAX, TARGET_CHARS_MIN = 430, 330   # 상한 500은 그대로. 미달은 T2e가 잡는다(JJ 2026-09-13: 330~430자)
TAG = "#국장"                                    # 해시태그는 정확히 하나(스레드는 주제 태그를 하나만 받는다)


# ── Korean helpers ──
def fin(ch):
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


def jong(ch):
    return (ord(ch) - 0xAC00) % 28 if "가" <= ch <= "힣" else -1


def eun(w):
    return w + ("은" if fin(w[-1]) else "는")


def i_ga(w):
    return w + ("이" if fin(w[-1]) else "가")


def eul(w):
    return w + ("을" if fin(w[-1]) else "를")


def gwa(w):
    return w + ("과" if fin(w[-1]) else "와")


def euro(w):
    return w + ("으로" if jong(w[-1]) not in (0, 8, -1) else "로")


def irang(w):
    return w + ("이랑" if fin(w[-1]) else "랑")


def join_groups(ns):
    if len(ns) == 1:
        return ns[0]
    if len(ns) == 2:
        return irang(ns[0]) + " " + ns[1]
    return irang(ns[0]) + " " + ", ".join(ns[1:])


def join_g(ns):
    """완결형 본문용 나열: '외국인과 기관', '개인과 기관, 회사들'. 이름은 쓰레드 표기(dn)로 바꿔 쓴다."""
    ns = [dn(x) for x in ns]
    if len(ns) == 1:
        return ns[0]
    if len(ns) == 2:
        return gwa(ns[0]) + " " + ns[1]
    return gwa(ns[0]) + " " + ", ".join(ns[1:])


def copula_past(w):  # 1,700억이었 / 2조 5천억이었
    return w + ("이었" if fin(w[-1]) else "였")


def iya(w):  # 반말 계사: 6,600억이야 / 1조 2천억이야 / 반도체야
    return w + ("이야" if fin(w[-1]) else "야")


# ── numbers: the only way a figure enters the text ──
def R(v):
    """억 → (display, rounded value in 억). None under 1,000억 (stays on the card). 주간 대본도 쓴다."""
    a = abs(v)
    if a >= 10000:
        n = int(a / 1000 + 0.5)
        return f"{n / 10:.1f}".rstrip("0").rstrip(".") + "조", n * 1000
    if a >= 1000:
        n = int(a / 100 + 0.5) * 100
        return f"{n:,}억", n
    return None, None


def KR(v):
    """억 → 풀어 쓴 표기와 반올림 값. 9.9조 → '9조 9천억', 6,600억 → '6,600억', 340억 → '340억'."""
    a = abs(v)
    if a >= 10000:
        n = int(a / 1000 + 0.5)                      # 1,000억 단위
        jo, rem = divmod(n, 10)
        return (f"{jo}조 {rem}천억" if rem else f"{jo}조"), n * 1000
    if a >= 1000:
        n = int(a / 100 + 0.5) * 100
        return f"{n:,}억", n
    if a >= 100:
        n = int(a / 10 + 0.5) * 10
        return f"{n:,}억", n
    n = max(int(a + 0.5), 1)
    return f"{n}억", n


def edges(v, rv=None):
    a = abs(v)
    if rv is None:
        _, rv = R(v)
    s = set()
    if not rv:
        return s
    if abs(a - rv) / a <= 0.03:
        s.add("정도")
    if a > rv:
        s.add("넘게")
    if a < rv:
        s.add("가까이")
    return s


FIG_RE = re.compile(r"\d+(?:\.\d+)?조\s?\d천억|\d+(?:\.\d+)?조|\d{1,3}(?:,\d{3})*억|\d+(?:\.\d+)?%|\d천피?(?!억)|\d{1,2},\d{3}(?![\d,]*억)")
GROUP_RE = re.compile(r"회사들|기타법인|외국인|기관|개인")


def load(d):
    with open(os.path.join(DATA, d, "computed_kr.json"), encoding="utf-8") as f:
        return json.load(f)


def prev_days(d, n=6):
    ds = sorted(x for x in os.listdir(DATA) if x.isdigit() and x < d and os.path.exists(os.path.join(DATA, x, "computed_kr.json")))
    return ds[-n:]


def top_buyer(inv):
    return max(GROUPS, key=lambda g: inv.get(g[1]) or 0)[0]


def top_buyer_run(d, inv):
    tb, run = top_buyer(inv), 1
    for pd in reversed(prev_days(d)):
        if top_buyer(load(pd)["investors"]["kospi"]) == tb:
            run += 1
        else:
            break
    return tb, run


def miss_run(d):
    with open(os.path.join(DATA, "ledger.json"), encoding="utf-8") as f:
        L = json.load(f)["entries"]
    run = 0
    for e in sorted([e for e in L if e.get("result") and e["result"]["date"] <= d], key=lambda e: e["date"], reverse=True):
        if e["result"]["ok"]:
            break
        run += 1
    return run


# context lines: juxtaposition only, never a cause. Used when >=2 headlines match and none of them is a question.
# 용어를 그대로 옮기지 않는다 — 만기·금통위는 처음 보는 사람이 모르는 말이라 뜻만 남긴다.
CONTEXT = [
    (r"네 마녀|선물\s?옵션 만기|선물·옵션|동시만기|만기일",
     ["오늘은 미리 걸어 둔 계약을 정리하는 날이었어.", "마침 네 마녀의 날이라 부르는 날이었어.",
      "하필 걸어 둔 계약을 정리하는 날이랑 겹쳤어."]),
    (r"AI 훈풍|AI 모멘텀",
     ["기사 제목에는 AI 훈풍이라는 말이 많았어.", "뉴스 제목은 대부분 AI 훈풍이었어.", "기사들은 오늘을 AI 훈풍이라고 적었어."]),
    (r"금통위", ["오늘은 한국은행이 금리를 정하는 날이었어.", "한국은행이 금리를 정하는 날이랑 겹쳤어.",
                "마침 한국은행이 금리를 발표한 날이었어."]),
]
THEMES = ["반도체", "이차전지", "2차전지", "자동차", "금융", "은행", "증권", "보험", "바이오", "제약", "조선", "방산", "원전", "전력", "화학",
          "철강", "건설", "게임", "엔터", "인터넷", "통신", "유통", "화장품", "음식료", "로봇", "운송", "항공", "해운", "지주"]

# ── 문장 뱅크 (완결형, 슬롯마다 3개 이상. seed는 최근 5개 글에 없는 변형을 먼저 고른다) ──
# JJ 2026-09-13: 쓰레드는 채널을 찾아온 사람이 아니라 피드를 지나가는 사람이 읽는다. 금융 용어를 쓰지 않는다.
#   순매수·순매도 → 샀습니다·팔았습니다 / 산 돈이 판 돈보다 많았습니다
#   수급 → 누가 사고 누가 팔았는지,  마감 집계·종가 → 장이 끝난 뒤·그날 마지막 가격
#   기타법인 → 회사들,  자사주 매입 → 회사가 자기 회사 주식을 사들이는 것
#   지수 → 코스피(낱말 '지수'는 뺀다),  물량 → 주식·그만큼,  주체 → 곳,  금통위 → 한국은행이 금리를 정하는 날
#   남기는 것은 코스피·코스닥·외국인·기관·개인 같은 이름과 숫자뿐이다.
DISP = {"기타법인": "회사들"}


def dn(n):
    """주체 이름을 쓰레드 표기로 바꾼다 — '기타법인'은 처음 보는 사람에게 뜻이 통하지 않는다."""
    return DISP.get(n, n)


# 0) 독자가 이미 본 것 — 첫 줄. 앱·뉴스에서 5초면 보는 코스피 등락을 먼저 인정하고 넘어간다.
#    숫자는 fp(코스피 등락률) 하나만 쓴다. 같은 표현을 매일 반복하지 않도록 여섯 변형을 돌린다.
SEEN_DOWN = ["코스피 {p} 내린 건 이미 봤을 거야.",
             "오늘 코스피 {p} 내린 건 뉴스에서 봤을 거야.",
             "주식 앱 켜면 {p} 하락이 떠 있어.",
             "오늘 {p} 하락은 앱만 켜도 보이는 숫자야.",
             "코스피가 {p} 빠진 것까지는 알 거야.",
             "{p} 내린 코스피는 아마 이미 봤을 거야."]
SEEN_UP = ["코스피 {p} 오른 건 이미 봤을 거야.",
           "오늘 코스피 {p} 오른 건 뉴스에서 봤을 거야.",
           "주식 앱 켜면 {p} 상승이 떠 있어.",
           "오늘 {p} 상승은 앱만 켜도 보이는 숫자야.",
           "코스피가 {p} 오른 것까지는 알 거야.",
           "{p} 오른 코스피는 아마 이미 봤을 거야."]
# 1) 놓치는 사실 — 둘째 줄에는 반드시 숫자가 들어간다(첫 줄에서 본 코스피 숫자는 두 번 쓰지 않는다).
IDX_DOWN = ["코스피는 오늘 {p} 내렸어.", "오늘 코스피는 {p} 내려갔어.", "오늘 코스피는 {p} 내린 자리에서 끝났어."]
IDX_UP = ["코스피는 오늘 {p} 올랐어.", "오늘 코스피는 {p} 올라갔어.", "오늘 코스피는 {p} 오른 자리에서 끝났어."]
HB_MORE_BUY = ["그 시간에 {nm_eun} 오히려 {f_eul} 더 샀어.",
               "코스피가 밀리는 동안 {nm_ga} {f_eul} 샀어.",
               "값이 내려간 그 시간에 {nm_eun} {f_eul} 받았어.",
               "{nm_eun} 내려가는 값을 받아 {f_eul} 샀어."]
HB_BIG_SELL = ["{nm_eun} 오늘 하루에만 {f_eul} 팔았어.",
               "오늘 {nm_ga} 내놓은 돈이 {f_ya}.",
               "{nm_ga} 하루에 판 금액이 {f_ya}.",
               "하루 사이 {nm_ga} 던진 금액이 {f_ya}.",
               "그 아래에서 {nm_ga} {f_eul} 팔았어.",
               "그 시간에 {nm_eun} {f_eul} 내놨어."]
HB_FLIP_A = ["{nm_eun} 오후 2시까지 {f_eul} {vb}고 있었어.",
             "오후 2시까지 {nm_eun} {f_eul} {vb}는 쪽이었어.",
             "오후 2시만 해도 {nm_eun} {f_eul} {vb}고 있었어."]
HB_FLIP_A0 = ["{nm_eun} 아침에는 {f_eul} {vb}는 쪽이었어.",
              "아침만 해도 {nm_eun} {f_eul} {vb}고 있었어.",
              "장이 열릴 때 {nm_eun} {f_eul} {vb}고 있었어."]
HB_FLIP_B = ["그런데 장 끝날 때 {nm_eun} {f_eul} {vb3}.",
             "장이 끝나고 보니 {nm_eun} {f_eul} {vb3}.",
             "끝나고 세어 보니 {nm_eun} {f_eul} {vb3}."]
TP_BEFORE = ["오후 2시까지는 {f_was}어.", "오후 2시에 적힌 숫자는 {f_ya}.", "오후 2시만 해도 {f_was}어.",
             "오후 2시에 세어 보니 {f_was}어."]
TP_TAIL = ["나머지는 전부 장 마지막에 나왔어.", "그 뒤 한 시간 반 사이에 쏟아졌어.",
           "차이는 전부 그 뒤 한 시간 반에서 생겼어."]
TP_GROW = ["나머지는 전부 그 뒤 한 시간 반에 들어왔어.", "차이는 장 끝나기 전 한 시간 반에서 생겼어.",
           "그 뒤 한 시간 반 사이에 그만큼이 더 늘었어."]
SELL_BOTH = ["오늘은 {s0}도 {s1}도 파는 쪽이었어.", "오늘은 {s0_gwa} {s1} 둘 다 팔았어.",
             "{s0_gwa} {s1}이 나란히 파는 쪽에 섰어.", "정작 판 쪽은 {s0_gwa} {s1}이야."]
# 코스피는 내렸는데 외국인과 기관이 받은 날 — 첫 줄(이미 본 것) 뒤에 붙는 '놓치는 사실'
CONTRA_BUY = ["그 아래에서 외국인과 기관은 {f_eul} 샀어.",
              "코스피가 빠지는 동안 외국인과 기관은 {f_eul} 샀어.",
              "값이 내려가는 동안 외국인과 기관이 {f_eul} 받았어.",
              "그 시간에 외국인과 기관은 {f_eul} 사들였어."]
# 2) 질문 한 줄 — 가운데. 마지막 줄 질문(END_Q)과는 다른 뱅크다.
Q_WHO = ["그 주식은 누가 받아 갔을까?", "그럼 그만큼은 누가 받은 걸까?", "팔린 주식은 어디로 간 걸까?",
         "그 자리를 받아 간 쪽은 누구였을까?", "그만큼을 받아 낸 쪽은 어디였을까?", "그걸 다 받아 낸 쪽은 누구였을까?"]
Q_SOLD = ["그럼 그 주식을 판 쪽은 누구였을까?", "그 주식은 누가 내놓은 걸까?", "반대편에서 판 쪽은 어디였을까?",
          "그럼 그만큼을 판 쪽은 누구였을까?"]
Q_WHERE = ["오늘 돈은 어디로 갔을까?", "그럼 돈은 어느 쪽으로 간 걸까?", "오늘 돈이 모인 곳은 어디였을까?",
           "돈이 향한 곳은 어디였을까?"]
# 3) 누가 받았나
WHO_SB = ["{S_ga} 판 주식을 {B_ga} 받았어.", "{S_eun} 팔았고, 그만큼을 {B_ga} 받았어.",
          "{S_ga} 내놓은 주식은 {B_ga} 받아 갔어."]
WHO_TOP = ["그만큼을 받은 쪽은 {tb}이야.", "그 주식을 받아 간 쪽은 {tb}이야.", "받아 낸 곳은 {tb} 한 곳뿐이야.",
           "그걸 다 받아 간 곳도 {tb}이야."]
WHO_TOP_MOST = ["그 주식은 {most} {tb_ga} 받았어.", "받아 간 쪽은 {most} {tb}이야.", "{most} {tb_ga} 받아 갔어.",
                "{tb_ga} {most} 받아 낸 하루야."]
WHO_TWO = ["그만큼을 받은 쪽은 {B2}이야.", "그 주식은 {B2}이 나눠 받았어.", "받아 간 곳은 {B2} 두 곳이야.",
           "{B2}이 그만큼을 나눠서 받았어."]
WHO_BUY2 = ["그 주식을 받아 간 쪽은 {B2}이야.", "오늘 사들인 쪽은 {B2}이야.", "그만큼은 {B2}이 받아 갔어.",
            "그 빈자리를 채운 쪽은 {B2}이야."]
WHO_ONE_BUY = ["가장 많이 산 쪽은 {tb}이야.", "오늘 제일 많이 산 곳은 {tb}이야.", "오늘은 {tb_ga} 제일 많이 샀어.",
               "오늘 산 금액이 가장 큰 쪽은 {tb}이야."]
SOLD_AMT = ["{S_eun} 오늘 하루 {f_eul} 팔았어.", "오늘 {S_ga} 내놓은 돈이 {f_ya}.", "{S_ga} 판 만큼을 돈으로 치면 {f_ya}.",
            "하루 사이 {S_ga} 판 금액이 {f_ya}.", "{S_eun} 하루 만에 {f_eul} 내놨어."]
BUY_AMT = ["{B_eun} 오늘 하루 {f_eul} 샀어.", "{B_ga} 받아 간 만큼이 {f_ya}.", "오늘 {B_ga} 사들인 돈이 {f_ya}.",
           "{B_eun} 하루 만에 {f_eul} 받아 갔어."]
SOLD_ALSO = ["{S_eun} 같은 날 {f_eul} 내놨어.", "{S_ga} 함께 내놓은 돈이 {f_ya}.",
             "{S_ga} 같이 판 금액도 {f_ya}."]
SOLD_SIDE = ["그 주식을 판 쪽은 {S}이야.", "반대편에서 판 쪽은 {S}이야.", "주식을 내놓은 쪽은 {S}이야.",
             "오늘 파는 쪽에 선 곳은 {S}이야."]
RUN_AFTER = ["{tb_eun} {days} 내내 가장 많이 산 쪽이야.", "{tb_eun} {days} 동안 하루도 안 멈췄어.",
             "{days} 내내 가장 많이 산 쪽도 {tb}이야."]
BOTH_BUY = ["둘 다 {dc} 사고 있어.", "둘 다 {dc} 사는 쪽이야.", "둘이 {dc} 함께 사는 중이야."]
# 코스닥 한 줄 — 코스피만 보면 놓치는 쪽(숫자는 쓰지 않는다)
KD_SELL = ["코스닥에서도 {g_eun} 파는 쪽이었어.", "코스닥에서 가장 많이 판 쪽도 {g}이야.",
           "코스닥에서도 {g_ga} 제일 많이 내놨어.", "코스닥에서 주식을 내놓은 쪽도 {g}이야.",
           "코스닥 쪽에서도 {g_eun} 파는 자리에 있었어."]
KD_BUY = ["코스닥에서는 {g_ga} 사는 쪽이었어.", "코스닥에서는 {g_ga} 제일 많이 받았어.",
          "코스닥에서 {g_eun} 받는 쪽이었어.", "코스닥에서 주식을 받아 간 쪽도 {g}이야.",
          "코스닥 쪽에서는 {g_ga} 사는 자리에 있었어."]
# 코스닥이 코스피와 얼마나 달랐나 — 숫자 없이 한 줄
KD_MORE = ["코스닥은 코스피보다 더 크게 {mv}어.", "코스닥은 그보다 더 크게 {mv}어.",
           "코스닥이 움직인 폭은 코스피보다 컸어.", "코스닥 쪽이 더 크게 {mv2} 하루야."]
KD_LESS = ["코스닥도 비슷한 폭으로 {mv}어.", "코스닥은 코스피보다 조금 덜 {mv}어.",
           "코스닥이 움직인 폭은 코스피보다 작았어.", "코스닥도 같은 쪽으로 {mv2} 하루야."]
KD_OPP = ["코스닥은 거꾸로 {mv}어.", "코스닥만 반대쪽으로 {mv}어.",
          "코스닥은 거꾸로 {mv2} 채로 끝났어.", "코스닥 쪽만 거꾸로 가 있었어."]
# 처음 보는 사람을 위한 한 줄 — 오늘 주인공이 누구인지 풀어서 설명한다
INTRO_FOREIGN = ["외국인은 한국 주식을 사고파는 외국 투자자야.", "외국인은 바다 건너에서 들어온 돈이야.",
                 "여기서 외국인은 외국 국적 투자자를 말해.", "외국인은 한국 밖에서 들어온 돈을 뜻해."]
INTRO_INST = ["기관은 연기금이나 자산운용사 같은 큰 투자자야.", "기관은 남의 돈을 모아 굴리는 큰 투자자야.",
              "여기서 기관은 연기금이나 보험사 같은 곳이야.", "기관은 사람이 아니라 회사가 굴리는 돈이야."]
INTRO_INDIV = ["개인은 증권 앱으로 직접 사고파는 사람들이야.", "개인은 회사가 아니라 사람이 낸 돈이야.",
               "여기서 개인은 직접 주문을 내는 사람들이야.", "개인은 흔히 말하는 보통 투자자를 뜻해."]
INTRO_OTHERS = ["회사들은 상장한 기업과 그 계열사를 부르는 말이야.", "여기서 회사들은 상장한 기업 자신을 말해.",
                "회사들은 사람도 기관도 아닌 기업 자신이야.", "회사들은 기업이 직접 낸 돈이야."]
INTRO = {"외국인": INTRO_FOREIGN, "기관": INTRO_INST, "개인": INTRO_INDIV, "회사들": INTRO_OTHERS}
SECOND_BUY = ["그다음으로 많이 산 쪽은 {g}이야.", "그 뒤를 이어 산 쪽은 {g}이야.",
              "{g_ga} 그다음으로 많이 받아 갔어."]
# 하루 안에서 어떻게 움직였나 — 숫자 없이 한 줄(끝난 자리만 보면 놓치는 부분)
DAY_LOWEND = ["코스피는 가장 낮은 자리에서 하루를 끝냈어.", "코스피는 내려간 그 자리 그대로 문을 닫았어.",
              "끝날 때까지 아래에서 못 올라왔어."]
DAY_BOUNCE = ["코스피는 하루 중 더 아래까지 내려갔었어.", "한때는 지금 숫자보다 더 아래에 있었어.",
              "바닥을 찍고 얼마쯤 올라온 채로 문을 닫았어."]
DAY_HIGHEND = ["코스피는 가장 높은 자리에서 하루를 끝냈어.", "코스피는 올라간 그 자리 그대로 문을 닫았어.",
               "끝날 때까지 위에서 안 내려왔어."]
DAY_FADE = ["코스피는 하루 중 더 위까지 올라갔었어.", "한때는 지금 숫자보다 더 위에 있었어.",
            "꼭대기에서 얼마쯤 내려온 채로 문을 닫았어."]
# 며칠째 같은 쪽인지 — 다른 줄에 이미 '며칠째'가 있으면 넣지 않는다
G_RUN = ["{g_ga} {vb4} 건 {dc}야.", "{g_eun} {dc} 같은 쪽에 서 있어.", "{dc} {vb4} 쪽도 {g}이야."]
# 4) 어디로 갔나 — 테마
TH_IN = ["돈이 가장 많이 들어온 곳은 {th_ya}.", "오늘 돈이 가장 많이 간 곳은 {th_ya}.", "{th_ro} 들어온 돈이 가장 많아."]
TH_IN_AMT = ["{th}에는 하루 동안 {f_ga} 들어왔어.", "{th} 한 곳에만 {f_ga} 들어왔어.", "{th_ro} 들어온 돈이 {f_ya}."]
TH_OUT = ["돈이 가장 많이 빠진 곳은 {th_ya}.", "오늘 돈이 가장 많이 나온 곳은 {th_ya}.", "{th}에서 빠진 돈이 가장 많아."]
TH_OUT_AMT = ["{th}에서는 하루 동안 {f_ga} 빠졌어.", "{th} 한 곳에서만 {f_ga} 나왔어.", "{th}에서 빠져나간 돈이 {f_ya}."]
TH_KEEP = ["{th}에는 {dc} 돈이 들어오고 있어.", "{th_ro}는 {dc} 돈이 들어와.", "{th}에 들어오는 돈이 {dc} 이어지고 있어.",
           "{th}에 돈이 들어온 건 {dc}야."]
# 5) 그래서 무슨 뜻 — 앞에서 한 말을 다시 하는 것은 뜻이 아니다. MEAN_*는 풀이, MEAN_*_B가 뜻을 닫는 줄이다.
#    본문 마지막 한 줄은 MEAN_*_B가 아니라 END_Q(독자에게 던지는 질문)가 맡는다.
MEAN_OTHERS = ["회사가 자기 회사 주식을 사들이면 도는 주식이 줄어.",
               "회사들이 받아 간 자리는 대개 자기 회사 주식이야.",
               "회사들이 받아 둔 주식은 한동안 시장 밖에 있어."]
MEAN_OTHERS_B = ["빠져나간 자리를 회사들이 자기 돈으로 메운 하루야.",
                 "판 쪽은 시장 밖에 있고 회사들이 그 자리를 메웠어.",
                 "결국 그 주식을 떠안은 쪽은 회사들이야."]
MEAN_FLIP = ["아침에 본 숫자랑 장 끝난 뒤 숫자가 서로 달랐어.",
             "오전 숫자만 보고 적었으면 거꾸로 읽었을 하루야.",
             "앞뒤가 서로 뒤집힌 하루였어."]
MEAN_FLIP_B = ["하루를 중간에 끊어 보면 거꾸로 읽히는 날이 있어.",
               "숫자는 장이 다 끝난 뒤에 세야 뜻이 맞아.",
               "오늘이 딱 중간에 보면 안 되는 날이었어."]
MEAN_FI = ["외국인과 기관은 서로 다른 쪽에 설 때가 더 많아.",
           "이 두 곳이 같은 쪽에 서는 날은 자주 안 나와.",
           "오늘은 그 드문 날이었어."]
MEAN_FI_B = ["둘이 같은 쪽에 서면 값은 한쪽으로 크게 기울어.",
             "같은 쪽에 선 날은 값이 한 방향으로 크게 움직여.",
             "한쪽으로만 밀리는 날은 대개 이런 날이야."]
MEAN_DEF = ["오늘 숫자로 확인되는 건 여기까지야.",
            "여기까지가 오늘 숫자로 확인된 부분이야.",
            "값보다 사고판 쪽을 먼저 세어 본 하루야."]
MEAN_DEF_B = ["누가 사고 누가 팔았는지만 그대로 적었어.",
              "값이 아니라 사고판 쪽을 센 하루였어.",
              "오늘은 여기까지만 숫자로 말할 수 있어."]
# 6) 본문 마지막 한 줄 — 독자에게 던지는 질문(JJ 2026-09-13). 댓글이 붙는 글은 전부 질문으로 끝났다.
#    숫자·'내일/월요일'은 넣지 않는다(T3 마지막 줄 숫자 금지, T14 예고 줄과 겹침).
END_Q = ["너넨 이 돈 누가 받았다고 봐?",
         "다들 이 돈이 어디로 갔다고 봐?",
         "받아 간 쪽, 너넨 어디라고 봐?",
         "너넨 오늘 숫자에서 뭐가 제일 이상해?",
         "다들 이런 날 어디부터 봐?",
         "너넨 오늘 어느 쪽이 더 이상해 보여?",
         "다들 오늘 누가 제일 크게 움직였다고 봐?",
         "너넨 이 숫자 중에 뭐가 제일 먼저 눈에 걸렸어?"]
WATCH_B = ["{when} {q} 볼게.", "{when} {q} 확인해 볼게.", "{when} {q} 지켜볼게."]
# 어제 예고 검증 — 내부 카운터 대신 풀어 쓴다
CB_OK = ["어제 보자고 한 {th} 쪽 돈은 오늘도 들어왔어.",
         "어제 적어 둔 {th} 쪽 돈은 오늘도 이어졌어.",
         "{th_ro} 더 들어올지 어제 적어 뒀는데, 오늘도 들어왔어."]
CB_MISS = ["어제 보자고 한 {th} 쪽 돈은 오늘 끊겼어.",
           "어제 적어 둔 {th_ro}는 오늘 돈이 들어오지 않았어.",
           "{th_ro} 더 들어올지 어제 적어 뒀는데, 오늘은 끊겼어."]
CB_INV_OK = ["어제 보자고 한 {th}은 오늘도 그대로였어.",
             "어제 적어 둔 {th}은 오늘도 이어졌어.",
             "{th}이 이어질지 어제 적어 뒀는데, 오늘도 그대로였어."]
CB_INV_MISS = ["어제 보자고 한 {th}은 오늘 끊겼어.",
               "어제 적어 둔 {th}은 오늘 이어지지 않았어.",
               "{th}이 이어질지 어제 적어 뒀는데, 오늘은 끊겼어."]


def mask(line, themes=()):
    s = re.sub(r"ㅋ+|ㅎ+|\.{2,}|[,?!~.]", " ", line)
    for g in ("기타법인", "회사들", "외국인", "기관", "개인"):
        s = s.replace(g, "G")
    for t in sorted(set(THEMES) | set(themes), key=len, reverse=True):
        s = s.replace(t, "T")
    s = FIG_RE.sub("N", s)
    s = re.sub(r"\d+", "N", s)
    s = re.sub(r"(하루|이틀|사흘|나흘|닷새|엿새|이레)(째)?", "D", s)
    s = re.sub(r"(두|세|네|다섯|여섯|일곱|여덟|아홉|열) 번", "D번", s)
    return " ".join(s.split())


def bigrams(text, themes=()):
    out = set()
    for ln in text.split("\n"):
        t = mask(ln, themes).split()
        out |= {(t[i], t[i + 1]) for i in range(len(t) - 1)}
    return out


_ROT = 0     # 날짜에서 뽑은 회전 오프셋. 이력이 비어 있어도(첫 배포일·전날 compute 실패) 날마다 다른 변형에서 시작한다.


def _rot_key(bank):
    """뱅크마다 다른 상수 — 모든 슬롯이 한 몸처럼 같이 돌지 않게 한다. hash()는 실행마다 바뀌므로 쓰지 않는다."""
    h = 0
    for ch in (bank[0] if bank else ""):
        h = (h * 131 + ord(ch)) % 1000003
    return h


def pick(bank, hist_masked, **kw):
    """hist_masked: 최근 5개 글의 뼈대 집합, 또는 (최근 5개, 최근 2개) 튜플.
    최근 5개에 없는 변형 → 최근 2개에 없는 변형 → 첫 변형 순. 뱅크가 바닥나도 어제와는 달라진다.
    시작 위치는 날짜로 돌린다: 이력이 없는 날에도 어제와 다른 변형이 나온다(같은 날짜면 늘 같은 결과)."""
    seen, recent = (hist_masked if isinstance(hist_masked, tuple) else (hist_masked, hist_masked))
    outs = [" ".join(v.format(**kw).split()).replace(" ,", ",") for v in bank]
    fit = [x for x in outs if len(x) <= MAX_LINE] or outs          # 한 줄 38자 넘는 변형은 건너뜀
    o = (_ROT + _rot_key(bank)) % len(fit)
    fit = fit[o:] + fit[:o]
    for x in fit:
        if mask(x) not in seen:
            return x
    for x in fit:
        if mask(x) not in recent:
            return x
    return fit[0]


WATCH_LINE_RE = re.compile(r"(내일|월요일).*(볼게|확인해 볼게|지켜볼게)\.?$")
VERDICT_RE = re.compile(r"끊겼|이어졌|들어오지 않|이어지지 않|그대로였")     # 테마 유입 문장('들어왔습니다')과 섞이지 않게 좁게
CB_RE = re.compile(r"어제.*(보자고|지켜보자고|적어 둔|적어 뒀)")


def build(d, hist, rot=0):
    """hist: list of previous posts (oldest→newest) as dicts {date, body, hero}. Returns (seed, tf).
    rot: 문장 뱅크 회전을 한 칸씩 더 미는 값 — build_ok가 검사에 걸린 조합을 피해 갈 때 쓴다."""
    global _ROT
    _ROT = datetime.strptime(d, "%Y%m%d").toordinal() + rot   # 연속된 날은 시작 변형이 반드시 달라진다
    c = load(d)
    k, inv = c["kospi"], c["investors"]["kospi"]
    chg, close, hi, lo = k["chg_pct"], k["close"], k["high"], k["low"]
    heads = [n["title"] for n in (c.get("news_items") or [])]
    H = " || ".join(heads)
    moves = c.get("moves") or []
    themes_today = [m["theme"] for m in moves]
    last5 = hist[-5:]
    hist_masked = ({mask(ln, themes_today) for p in last5 for ln in p["body"].split("\n") if ln.strip()},
                   {mask(ln, themes_today) for p in hist[-2:] for ln in p["body"].split("\n") if ln.strip()})
    allowed, edge_ok, days_ok, keep = {}, {}, set(), []

    def fig(v):
        s, rv = KR(v)
        allowed[s] = True
        edge_ok[s] = edges(v, rv)
        return s

    def fkw(s):
        """숫자 한 덩이를 뱅크 자리표시자로 펼친다 — 6,600억 / 6,600억을 / 6,600억이 / 6,600억이야 / 6,600억이었."""
        return {"f": s, "f_eul": eul(s), "f_ga": i_ga(s), "f_ya": iya(s), "f_was": copula_past(s)}

    # level (round thousand inside the day's range, named in a headline)
    T = next((t for t in range(math.ceil(lo / 1000) * 1000, int(hi) + 1, 1000)), None)
    lvl = None
    if T and re.search(rf"{T // 1000}천|{T}|{T:,}", H):
        lvl = "lost" if hi >= T > close else "held" if lo < T <= close else None
    ms = re.search(r"(\d+)거래일 만에?[^|]*?(탈환|회복|돌파|복귀)", H)
    milestone = ms.group(1) if (ms and T and close >= T and chg > 0) else None
    late_fade = chg < 0 and (close - lo) / max(hi - lo, 1e-9) <= 0.05 and bool(re.search(r"막판|하락 전환|꺾", H))
    if lvl or milestone:
        allowed[f"{T // 1000}천"] = True
        allowed[f"{T // 1000}천피"] = True
        edge_ok[f"{T // 1000}천"] = edge_ok[f"{T // 1000}천피"] = set()
    fp = f"{abs(chg):.2f}%"

    def idx_line():
        allowed[fp] = True
        edge_ok[fp] = set()
        return pick(IDX_UP if chg > 0 else IDX_DOWN, hist_masked, p=fp)

    def seen_line():
        """첫 줄 — 독자가 오늘 이미 본 것. 숫자는 fp 하나뿐이고 allowed/edge_ok에 그대로 등록된다.
        SEEN_UP[i]와 SEEN_DOWN[i]는 같은 틀의 짝이다. 최근 글이 반대쪽 짝을 썼으면 그 번호도 '이미 쓴 것'으로 넘긴다
        — 어제 내림, 오늘 오름이어도 첫 줄 틀이 겹치지 않는다."""
        allowed[fp] = True
        edge_ok[fp] = set()
        bank, twin = (SEEN_UP, SEEN_DOWN) if chg > 0 else (SEEN_DOWN, SEEN_UP)
        firsts = {next((mask(x) for x in p["body"].split("\n") if x.strip()), "") for p in hist[-4:]}
        used = {mask(bank[i].format(p=fp)) for i in range(len(bank)) if mask(twin[i].format(p=fp)) in firsts}
        seen5, seen2 = hist_masked
        return pick(bank, (seen5 | used, seen2 | used), p=fp)

    # hero
    turns = [t for t in ((c.get("intraday") or {}).get("turns") or []) if t["key"] in ("foreign", "inst", "indiv")]
    big = max(turns, key=lambda t: abs(t["b"] - t["a"])) if turns else None
    cands = []
    if milestone or abs(chg) >= 2:
        cands.append("level")
    if big and abs(big["b"] - big["a"]) >= 4000 and (big["kind"] == "flip" or abs(big["b"]) >= 2 * abs(big["a"])):
        cands.append("turn")
    if (chg < 0 and inv["foreign"] > 0 and inv["inst"] > 0) or (chg > 0 and inv["indiv"] < 0 and inv["foreign"] < 0):
        cands.append("contrast")
    if moves and max(abs(m["t"]) for m in moves) >= 1000:
        cands.append("theme")
    cands.append("quiet")
    prev_hero = hist[-1]["hero"] if hist else None
    # rotate the frame only toward another substantive story (never demote a big day to theme/quiet)
    hero = cands[1] if (cands[0] == prev_hero and len(cands) > 1 and cands[1] in ("level", "turn", "contrast")) else cands[0]

    sellers = [n for n, kk in GROUPS if (inv.get(kk) or 0) < 0]
    buyers = [n for n, kk in GROUPS if (inv.get(kk) or 0) > 0]
    if not buyers or not sellers:            # 네 주체가 한쪽으로만 나오는 건 데이터 이상 — 옛 본문으로 되돌린다
        raise ValueError(f"수급 데이터 이상(buyers={buyers}, sellers={sellers})")
    by_amt = sorted([n for n in buyers], key=lambda n: -(inv[dict(GROUPS)[n]]))
    tb, tb_run = top_buyer_run(d, inv)
    two_pm_used = sum(1 for p in hist[-4:] if "2시" in p["body"])
    two_pm_ok = bool(turns) and two_pm_used <= 1

    # 문단 블록: A(무슨 일) / Qb(질문) / W(누가 받았나) / X(어디로 갔나·맥락) / Z(무슨 뜻·다음)
    # 각 줄은 (text, gid). gid=None 이면 필수, 그 외에는 길이가 넘칠 때 DROP_ORDER 순서로 통째로 빠진다.
    A, Qb, W, X, Z = [], [], [], [], []
    hero_tokens, hero_figs = [], []
    A.append((seen_line(), None))       # 1줄: 이미 본 것. 아래에 이어 붙는 줄이 '그것만 보면 놓치는 사실'이다.
    tbd, th_used = dn(tb), set()
    if hero == "turn":
        t = big
        nm, a, b = dn(t["name"]), t["a"], t["b"]
        hero_tokens.append(nm)
        if a > 0 and b > a:                                   # bought more into the close
            fb = fig(b)
            hero_figs.append(fb)
            A.append((pick(HB_MORE_BUY, hist_masked, nm_eun=eun(nm), nm_ga=i_ga(nm), **fkw(fb)), None))
            if two_pm_ok:
                fa = fig(a)
                A.append((pick(TP_BEFORE, hist_masked, **fkw(fa)), "twopm"))
                A.append((pick(TP_GROW, hist_masked), "tail"))
                hero_figs.append(fa)
            S, B = join_g(sellers), join_g(buyers)
            Qb.append((pick(Q_SOLD, hist_masked), "ask"))
            W.append((pick(WHO_SB, hist_masked, S_ga=i_ga(S), B_ga=i_ga(B), S_eun=eun(S)), None))
            keep += [dn(x) for x in sellers + buyers]
            if len(sellers) == 1:
                s0 = dn(sellers[0])
                fs = fig(inv[dict(GROUPS)[sellers[0]]])
                W.append((pick(SOLD_AMT, hist_masked, S_eun=eun(s0), S_ga=i_ga(s0), **fkw(fs)), "amt"))
        elif a < 0 and b < a:                                 # sold more into the close
            fb = fig(b)
            hero_figs.append(fb)
            A.append((pick(HB_BIG_SELL, hist_masked, nm_eun=eun(nm), nm_ga=i_ga(nm), **fkw(fb)), None))
            if two_pm_ok:
                fa = fig(a)
                A.append((pick(TP_BEFORE, hist_masked, **fkw(fa)), "twopm"))
                A.append((pick(TP_TAIL, hist_masked), "tail"))   # '그 뒤'는 오후 2시 줄이 있을 때만
                hero_figs.append(fa)
            tot_b = sum(inv[dict(GROUPS)[n]] for n in buyers) or 1
            share = inv[dict(GROUPS)[tb]] / tot_b
            second = by_amt[1] if len(by_amt) > 1 else None
            Qb.append((pick(Q_WHO, hist_masked), "ask"))
            if share < 0.6 and second and inv[dict(GROUPS)[second]] / tot_b >= 0.3:   # 둘이 비슷하면 둘 다
                W.append((pick(WHO_TWO, hist_masked, B2=join_g([tb, second])), None))
                keep += [tbd, dn(second)]
                ftw = fig(inv[dict(GROUPS)[tb]])
                W.append((pick(BUY_AMT, hist_masked, B_eun=eun(tbd), B_ga=i_ga(tbd), **fkw(ftw)), "amt"))
            else:
                most = "대부분" if share >= 0.6 else "주로"
                W.append(((pick(WHO_TOP, hist_masked, tb=tbd) if share >= 0.9 else
                           pick(WHO_TOP_MOST, hist_masked, tb=tbd, tb_ga=i_ga(tbd), most=most)), None))
                keep.append(tbd)
            if tb_run >= 3:
                W.append((pick(RUN_AFTER, hist_masked, tb_eun=eun(tbd), tb=tbd, days=DAYN[min(tb_run, 7)]), "run"))
                days_ok.add(DAYN[min(tb_run, 7)])
            elif sellers:
                W.append((pick(SOLD_SIDE, hist_masked, S=join_g(sellers)), "side"))
                keep += [dn(x) for x in sellers]
            s2nd = [n3 for n3 in sorted(sellers, key=lambda n4: inv[dict(GROUPS)[n4]]) if dn(n3) != nm][:1]
            if s2nd and abs(inv[dict(GROUPS)[s2nd[0]]]) >= 1000:      # 판 쪽이 둘이면 나머지 한 곳의 금액도 적는다
                sn = dn(s2nd[0])
                fs2 = fig(inv[dict(GROUPS)[s2nd[0]]])
                W.append((pick(SOLD_ALSO, hist_masked, S_eun=eun(sn), S_ga=i_ga(sn), **fkw(fs2)), "amt2"))
                keep.append(sn)
        else:                                                 # flip
            fa, fb = fig(a), fig(b)
            hero_figs += [fa, fb]
            A.append((pick(HB_FLIP_A if two_pm_ok else HB_FLIP_A0, hist_masked, nm_eun=eun(nm), **fkw(fa),
                           vb="사" if a > 0 else "팔"), None))
            A.append((pick(HB_FLIP_B, hist_masked, nm_eun=eun(nm), **fkw(fb),
                           vb3="판 쪽이었어" if b < 0 else "산 쪽이었어"), None))
            Qb.append((pick(Q_WHO if b < 0 else Q_SOLD, hist_masked), "ask"))
            W.append((pick(WHO_BUY2, hist_masked, B2=join_g(by_amt[:2])), None))
            keep += [dn(x) for x in by_amt[:2]]
            if sellers:
                W.append((pick(SOLD_SIDE, hist_masked, S=join_g(sellers)), "side"))
            if by_amt:
                b0 = dn(by_amt[0])
                ft = fig(inv[dict(GROUPS)[by_amt[0]]])
                W.append((pick(BUY_AMT, hist_masked, B_eun=eun(b0), B_ga=i_ga(b0), **fkw(ft)), "amt"))
    elif hero == "level":
        # 인정 구간(첫 세 줄)에 코스피 숫자를 두 번 넣지 않는다 — '몇 거래일 만에 7천' 줄은 뺐다(JJ 2026-09-13).
        s2 = [n for n in sellers if n in ("개인", "외국인")]
        big_s = min(sellers, key=lambda n: inv[dict(GROUPS)[n]])
        s0 = dn(big_s)
        fs = fig(inv[dict(GROUPS)[big_s]])
        hero_figs.append(fs)
        A.append((pick(SOLD_AMT, hist_masked, S_eun=eun(s0), S_ga=i_ga(s0), **fkw(fs)), None))
        keep.append(s0)
        if len(s2) == 2:
            A.append((pick(SELL_BOTH, hist_masked, s0=dn(s2[0]), s1=dn(s2[1]), s0_gwa=gwa(dn(s2[0]))), "both"))
            keep += [dn(x) for x in s2]
        hero_tokens.append(fp)
        Qb.append((pick(Q_WHO, hist_masked), "ask"))
        W.append((pick(WHO_BUY2, hist_masked, B2=join_g(by_amt[:2])), None))
        keep += [dn(x) for x in by_amt[:2]]
    elif hero == "contrast":
        S, B = join_g(sellers), join_g(buyers)
        if chg < 0:                                           # 코스피는 내렸는데 외국인과 기관이 받은 날
            fc = fig((inv.get("foreign") or 0) + (inv.get("inst") or 0))
            hero_figs.append(fc)
            A.append((pick(CONTRA_BUY, hist_masked, **fkw(fc)), None))
            n2 = min((c.get("inv_streak") or {}).get("foreign", {}).get("streak") or 0, (c.get("inv_streak") or {}).get("inst", {}).get("streak") or 0)
            if n2 >= 2:
                A.append((pick(BOTH_BUY, hist_masked, dc=DAYC[min(n2, 7)]), "both"))
            Qb.append((pick(Q_SOLD, hist_masked), "ask"))
            W.append((pick(WHO_SB, hist_masked, S_ga=i_ga(S), B_ga=i_ga(B), S_eun=eun(S)), None))
            hero_tokens.append("외국인")
            keep += [dn(x) for x in sellers + buyers]
            if len(sellers) == 1:
                s0 = dn(sellers[0])
                fs = fig(inv[dict(GROUPS)[sellers[0]]])
                W.append((pick(SOLD_AMT, hist_masked, S_eun=eun(s0), S_ga=i_ga(s0), **fkw(fs)), "amt"))
            ftc = fig(inv[dict(GROUPS)[tb]])
            W.append((pick(BUY_AMT, hist_masked, B_eun=eun(tbd), B_ga=i_ga(tbd), **fkw(ftc)), "amt2"))
            keep.append(tbd)
        else:                                                 # 코스피는 올랐는데 개인과 외국인이 판 날
            fs = fig(inv["indiv"])
            hero_figs.append(fs)
            A.append((pick(SOLD_AMT, hist_masked, S_eun="개인은", S_ga="개인이", **fkw(fs)), None))
            A.append((pick(SELL_BOTH, hist_masked, s0="개인", s1="외국인", s0_gwa="개인과"), "both"))
            Qb.append((pick(Q_WHO, hist_masked), "ask"))
            W.append((pick(WHO_BUY2, hist_masked, B2=join_g(by_amt[:2])), None))
            hero_tokens.append(fp)
            keep += ["개인", "외국인"] + [dn(x) for x in by_amt[:2]]
    elif hero in ("theme", "quiet"):
        fi0 = abs((inv.get("foreign") or 0) + (inv.get("inst") or 0))
        if hero == "theme":
            m = max(moves, key=lambda x: abs(x["t"]))
            if abs(m["t"]) <= fi0:
                fm = fig(m["t"])
                hero_figs.append(fm)
                A.append((pick(TH_IN_AMT if m["t"] > 0 else TH_OUT_AMT, hist_masked, th=m["theme"],
                               th_ro=euro(m["theme"]), th_ya=iya(m["theme"]), **fkw(fm)), None))
                th_used.add(m["theme"])
            else:
                ft0 = fig(inv[dict(GROUPS)[tb]])
                A.append((pick(BUY_AMT, hist_masked, B_eun=eun(tbd), B_ga=i_ga(tbd), **fkw(ft0)), None))
            A.append((pick(TH_IN if m["t"] > 0 else TH_OUT, hist_masked, th=m["theme"], th_ro=euro(m["theme"]),
                       th_ya=iya(m["theme"])), "thq"))
            hero_tokens.append(m["theme"])
            Qb.append((pick(Q_WHERE if m["t"] > 0 else Q_WHO, hist_masked), "ask"))
            W.append((pick(WHO_ONE_BUY, hist_masked, tb=tbd, tb_ga=i_ga(tbd)), None))
        else:
            ft0 = fig(inv[dict(GROUPS)[tb]])
            hero_figs.append(ft0)
            A.append((pick(BUY_AMT, hist_masked, B_eun=eun(tbd), B_ga=i_ga(tbd), **fkw(ft0)), None))
            A.append((pick(WHO_ONE_BUY, hist_masked, tb=tbd, tb_ga=i_ga(tbd)), "who1"))
            Qb.append((pick(Q_SOLD, hist_masked), "ask"))
        W.append(((pick(SOLD_SIDE, hist_masked, S=join_g(sellers)) if sellers
                   else "개인과 외국인, 기관, 회사들이 모두 샀어."), None))
        keep += [tbd] + [dn(x) for x in sellers]
        if sellers:
            ts = dn(min(sellers, key=lambda n: inv[dict(GROUPS)[n]]))      # 가장 많이 판 쪽
            fs = fig(inv[dict(GROUPS)[min(sellers, key=lambda n: inv[dict(GROUPS)[n]])]])
            W.append((pick(SOLD_AMT, hist_masked, S_eun=eun(ts), S_ga=i_ga(ts), **fkw(fs)), "amt2"))
        if tb_run >= 3:
            W.append((pick(RUN_AFTER, hist_masked, tb_eun=eun(tbd), tb=tbd, days=DAYN[min(tb_run, 7)]), "run"))
            days_ok.add(DAYN[min(tb_run, 7)])

    # where money went: theme inflow line — only if it reconciles with the market totals
    fi = abs((inv.get("foreign") or 0) + (inv.get("inst") or 0))
    th_in = [m for m in moves if m["t"] >= 1000 and m["t"] <= fi and m["state"] != "혼조" and m["theme"] not in th_used]
    if hero in ("level", "contrast", "turn") and th_in:
        m = max(th_in, key=lambda x: x["t"])
        fm = fig(m["t"])
        th_used.add(m["theme"])
        X.append((pick(TH_IN_AMT, hist_masked, th=m["theme"], th_ro=euro(m["theme"]), th_ya=iya(m["theme"]), **fkw(fm)), "theme"))
    # 돈이 가장 많이 빠져나간 곳도 한 줄 — 들어온 쪽만 말하면 절반만 말하는 셈이다
    th_out = [m for m in moves if m["t"] <= -1000 and abs(m["t"]) <= fi and m["theme"] not in th_used]
    if th_out:
        m = min(th_out, key=lambda x: x["t"])
        fo = fig(m["t"])
        th_used.add(m["theme"])
        X.append((pick(TH_OUT_AMT, hist_masked, th=m["theme"], th_ro=euro(m["theme"]), th_ya=iya(m["theme"]), **fkw(fo)), "thout"))
    # 코스닥 한 줄 — 코스피만 보면 놓치는 쪽(숫자는 쓰지 않는다)
    kdi = (c.get("investors") or {}).get("kosdaq") or {}
    kd = [(n, kdi.get(kk) or 0) for n, kk in GROUPS if n != "기타법인"]
    kd0 = max(kd, key=lambda x: abs(x[1])) if kd else None
    if kd0 and abs(kd0[1]) >= 1000:
        g0 = dn(kd0[0])
        X.append((pick(KD_SELL if kd0[1] < 0 else KD_BUY, hist_masked, g=g0, g_eun=eun(g0), g_ga=i_ga(g0)), "kd"))
    kdc = (c.get("kosdaq") or {}).get("chg_pct")
    if kdc is not None and abs(kdc) >= 0.1 and abs(chg) >= 0.1:
        kb = (KD_OPP if kdc * chg < 0 else KD_MORE if abs(kdc) > abs(chg) * 1.3 else KD_LESS)
        X.append((pick(kb, hist_masked, mv="올랐" if kdc > 0 else "내렸", mv2="오른" if kdc > 0 else "내린"), "kdc"))
    # 그다음으로 많이 산 쪽 — 아직 이름이 나오지 않은 곳만 한 번
    said = " ".join(x for x, _ in A + W + X)      # X(코스닥 줄)까지 세지 않으면 같은 주체가 연달아 나온다
    for n2 in by_amt[1:]:
        g2 = dn(n2)
        if g2 not in said and (inv[dict(GROUPS)[n2]] or 0) >= 1000:
            X.append((pick(SECOND_BUY, hist_masked, g=g2, g_ga=i_ga(g2)), "2nd"))
            keep.append(g2)
            break
    # 하루 안에서 어떻게 움직였나 — 끝난 자리만 보면 놓치는 부분(숫자는 쓰지 않는다)
    pos = (close - lo) / max(hi - lo, 1e-9)
    dayb = ((DAY_LOWEND if pos <= 0.25 else DAY_BOUNCE if pos >= 0.4 else None) if chg < 0
            else (DAY_HIGHEND if pos >= 0.75 else DAY_FADE if pos <= 0.6 else None))
    if dayb:
        X.append((pick(dayb, hist_masked), "range"))

    # 오늘 주인공이 누구인지 한 줄로 풀어 준다 — 처음 보는 사람은 '기관'이 무엇인지 모른다
    if INTRO.get(tbd) and any(tbd in x for x, _ in W):
        W.append((pick(INTRO[tbd], hist_masked), "intro"))

    # watch (다음 거래일에 볼 것) — 이틀 연속 금지, 최근 4개 중 2번까지
    w = (c.get("watch") or [{}])[0].get("q", "")
    mw = re.match(r"^(.+?) 순매(수|도)가 (\S+째) 이어지는지$", w)
    watch = {"theme": mw.group(1), "nd": mw.group(3)} if mw else None
    lead = max(moves, key=lambda x: x["t"]) if moves else None
    watch_in_body = False      # 다음 거래일에 볼 것은 첫 답글(reply)이 맡는다 — 본문 마지막 줄은 '그래서 무슨 뜻'
    if (lead and lead["t"] > 0 and str(lead["state"]).startswith("쌓임") and lead["streak"] >= 2
            and lead["theme"] not in th_used and (not watch or watch["theme"] != lead["theme"])):
        X.append((pick(TH_KEEP, hist_masked, th=lead["theme"], th_ro=euro(lead["theme"]), th_ya=iya(lead["theme"]),
                       dc=DAYC[min(lead["streak"], 7)]), "keep"))

    # 며칠째 같은 쪽인지 — 이미 '며칠째'를 말한 줄이 있으면 넣지 않는다(겹쳐 쓰면 T17)
    if not any(STREAK_RE.search(x) for x, _ in A + W + X):
        st = c.get("inv_streak") or {}
        cand = [(n3, (st.get(kk) or {}).get("streak") or 0) for n3, kk in (("외국인", "foreign"), ("기관", "inst"))]
        cand = [x for x in cand if abs(x[1]) >= 2]
        if cand:
            gn, sv = max(cand, key=lambda x: abs(x[1]))
            X.append((pick(G_RUN, hist_masked, g=gn, g_eun=eun(gn), g_ga=i_ga(gn),
                           vb4="산" if sv > 0 else "판", dc=DAYC[min(abs(sv), 7)]), "grun"))
            keep.append(gn)

    # context (headline-backed, max 1)
    scored = []
    for rx, bank in CONTEXT:
        hits = [h for h in heads if re.search(rx, h)]
        if len(hits) >= 2 and not any("?" in h for h in hits):
            scored.append((len(hits), bank))
    ctx = [bank for _, bank in sorted(scored, key=lambda x: -x[0])][:1]   # one topic per day
    ctx_lines = ctx[0] if ctx else []
    if ctx_lines:
        X.append((pick(ctx_lines, hist_masked), "ctx"))

    # callback — 내부 카운터 대신 풀어 쓴 한 문장. '순매수/순매도'라는 말은 쓰지 않는다.
    cb = c.get("callback")
    mr = miss_run(d) if cb else 0
    cb_line = None
    if cb and cb["check"].get("kind") == "theme_continue":
        th = cb["check"]["theme"]
        cb_line = pick(CB_OK if cb["ok"] else CB_MISS, hist_masked, th=th, th_ro=euro(th))
    elif cb and cb["check"].get("kind") == "inv_continue":
        ck = cb["check"]
        th = f"{dn(ck['name'])}이 {'사는' if ck.get('sign', 1) > 0 else '파는'} 쪽"
        cb = {**cb, "check": {**ck, "theme": th}}
        cb_line = pick(CB_INV_OK if cb["ok"] else CB_INV_MISS, hist_masked, th=th)
    if cb_line:
        Z.insert(0, (cb_line, None))

    # 그래서 무슨 뜻 — 풀이 한 줄(mean) + 마지막 줄(mean_b). 마지막 줄은 앞에서 한 사실을 되풀이하지 않는다.
    mb, mb2 = MEAN_DEF, MEAN_DEF_B
    if tb == "기타법인" and tb_run >= 2:
        mb, mb2 = MEAN_OTHERS, MEAN_OTHERS_B
    elif big and big["kind"] == "flip":
        mb, mb2 = MEAN_FLIP, MEAN_FLIP_B
    elif (inv.get("foreign") or 0) * (inv.get("inst") or 0) > 0:
        mb, mb2 = MEAN_FI, MEAN_FI_B
    Z.append((pick(mb, hist_masked), "mean"))
    Z.append((pick(mb2, hist_masked), "meanb"))      # 뜻은 이 줄이 맡는다
    Z.append((pick(END_Q, hist_masked), None))       # 본문은 늘 독자에게 던지는 질문으로 닫는다

    # 최소 줄 수 보장: A 2줄, W 2줄
    if len(A) < 2:
        A.append((idx_line(), None))
    if len(W) < 2:
        if sellers and not any(join_g(sellers) in x for x, _ in W):      # 이미 판 쪽을 부른 줄이 있으면 되풀이하지 않는다
            W.append((pick(SOLD_SIDE, hist_masked, S=join_g(sellers)), "side2"))
        else:
            ft2 = fig(inv[dict(GROUPS)[tb]])
            W.append((pick(BUY_AMT, hist_masked, B_eun=eun(tbd), B_ga=i_ga(tbd), **fkw(ft2)), "side2"))

    # assemble: 문단 사이 빈 줄. 길이가 넘치면 DROP_ORDER 순서로 통째로 뺀다.
    DROP_ORDER = ["ctx", "grun", "kdc", "range", "2nd", "kd", "intro", "keep", "thout", "theme", "thq", "who1",
                  "amt2", "amt", "side", "side2", "tail", "both", "run", "twopm", "meanb", "mean", "ask"]
    dropped = set()

    def render():
        segs = [[t for t, g in blk if g not in dropped] for blk in (A, Qb, W, X, Z)]
        segs = [s for s in segs if s]
        out = []
        for i, s in enumerate(segs):
            if i:
                out.append("")
            out += s
        return out

    def cost(out):
        """얼마나 넘쳤나 — 0이면 통과. 어느 묶음을 빼야 실제로 나아지는지 고르는 데 쓴다."""
        txt = "\n".join(out)
        tails = [strip_end(x)[-5:] for x in out if x.strip() and not x.strip().endswith(",")]
        return (max(0, len(out) - MAX_LINES) * 10 + max(0, len(txt) - MAX_CHARS)
                + max(0, len(FIG_RE.findall(txt)) - MAX_FIGS) * 100      # 숫자 초과가 가장 급하다
                + sum(max(0, tails.count(t2) - 2) for t2 in set(tails)) * 10)   # 같은 종결이 세 줄이면 한 줄 뺀다

    def over(out):
        return cost(out) > 0

    # 넘칠 때마다 '가장 많이 나아지는' 묶음 하나만 뺀다(고정 순서로 줄줄이 빼면 아까운 줄까지 날아간다).
    # 가운데 질문 한 줄(ask)과 뜻 풀이(mean)는 정말 더 뺄 게 없을 때만 건드린다.
    for pool in (DROP_ORDER[:-3], DROP_ORDER):
        while True:
            base = cost(render())
            if not base:
                break
            pickg, pickc = None, base
            for gid in pool:
                if gid in dropped:
                    continue
                dropped.add(gid)
                c2 = cost(render())
                dropped.discard(gid)
                if c2 < pickc:
                    pickg, pickc = gid, c2
            if pickg is None:
                break
            dropped.add(pickg)
    for gid in DROP_ORDER:               # 첫 줄이 늘어난 만큼 가운데에서 덜어낸다(목표 350~420자)
        if len("\n".join(render())) <= TARGET_CHARS_MAX:
            break
        if gid in dropped:
            continue
        dropped.add(gid)
        trial = render()
        if (len("\n".join(trial)) < TARGET_CHARS_MIN or len(trial) < MIN_LINES
                or len([x for x in trial if x.strip()]) < MIN_BODY_LINES):
            dropped.discard(gid)         # 덜어내면 너무 짧아진다 — 되돌린다
    lines_out = render()
    if "twopm" in dropped:
        hero_figs = [f for f in hero_figs if any(f in x for x in lines_out)]
    seed = "\n".join(lines_out)
    watch_in_body = watch_in_body and any(WATCH_LINE_RE.search(x) for x in lines_out)

    if cb_line and cb_line in seed:
        keep.append(cb["check"]["theme"])
    keep = [kx for kx in keep if kx in seed]
    stock_names = sorted({s["name"] for s in (c.get("stocks") or [])} | {n for m in moves for n in (m.get("spread_names") or [])}
                         | {s["name"] for s in ((c.get("event") or {}).get("stocks") or [])})
    tf = {
        "date": d, "hero": hero, "hero_tokens": hero_tokens, "hero_figs": hero_figs, "seen_fig": fp,
        "allowed_figures": sorted(allowed), "edges": {k2: sorted(v) for k2, v in edge_ok.items()}, "allowed_days": sorted(days_ok),
        "intraday_ok": bool(turns), "must_keep": list(dict.fromkeys(keep)), "context_lines": ctx_lines,
        "callback": ({"theme": cb["check"]["theme"], "ok": cb["ok"], "miss_run": mr} if (cb and cb_line and cb_line in seed) else None),
        "watch": watch, "watch_in_body": watch_in_body,
        "ask_ok": True,
        "themes": themes_today, "stock_names": stock_names,
        "event_terms": ["애플", "아이폰", "듀오", "폴더블"] if c.get("event") else [],
        "top_buyer": tb, "top_buyer_run": tb_run,
    }
    return seed, tf


# ── validator ──
BAN_NEWS = ["관건", "눈에 띈", "주목", "흐름", "그림이", "그림입니다", "드라마틱", "들여다보", "흘러들어", "반대로", "정리하면", "풀이", "인상적",
            "흥미롭", "의미 있는", "그 돈은", "그 돈이", "강세 속에", "마감했", "마감입니다", "나타났", "것으로", "기록했"]
BAN_INTERP = ["판이 바", "주도주", "대세", "본격", "신호", "시그널", "쌍끌이", "몰리", "몰렸", "매집", "세력"]
BAN_PROMO = ["여러분", "보셨나요", "생각하시", "의견", "댓글", "팔로우", "구독", "저장해", "리포", "공유", "DM", "오픈채팅", "리딩방", "단톡", "텔레그램",
             "링크", "영상", "프로필",
             # 채널 고지·영상 안내는 본문이 아니라 첫 답글(reply) 몫이다 — 본문에 새어 들어오면 잡는다
             "여기서 보실", "기록으로 남깁니다", "매일 확인합니다", "기록으로 남겨", "매일 확인해", "채널"]
BAN_REC = ["사세요", "담아", "담으", "모아가", "모아 가", "기회", "목표가", "추천", "유망", "노려", "관심 종목", "볼 만한", "사도 될", "들어가도", "타이밍"]
BAN_MONEY = ["확률", "승률", "부자", "돈 벌", "돈을 벌", "경제적 자유", "수익", "월급", "파이어", "계좌", "평단", "손실", "익절", "손절", "물렸", "물림",
             "추매", "물타", "불타", "몰빵", "풀매수", "담았", "담음"]
BAN_SCORE = ["빗나", "적중", "맞췄", "맞힘", "맞춤", "틀렸", "성적", "역시", "말한 대로"]
BAN_CAUSE = ["때문", "영향으로", "영향에", "탓에", "탓으로", "덕에", "덕분", "로 인해", "으로 인해", "여파", "힘입어", "나오자", "거든", "니까", "라서",
             "그래서", "해서"]
BAN_FORECAST = ["예상", "전망", "가능성", "듯", "것 같", "거 같", "오를", "내릴", "빠질", "반등", "급등", "급락", "폭등", "폭락", "예정", "할 거", "될 거", "갈 거",
                "올 거"]
BAN_CROWD = ["개미", "호구", "설거지", "내놓는 그림", "받는 그림", "털렸", "털림"]
# 금융 용어 — 쓰레드는 처음 보는 사람이 읽는다. 뜻을 설명해야 하는 낱말이면 낱말을 빼고 뜻만 남긴다(JJ 2026-09-13).
from checks import jargon as _jargon          # 세 편이 같은 목록을 본다(checks/jargon.py)
BAN_JARGON = _jargon.BAN
BAN_PERSONA = ["고수", "전업", "년차", "촉이", "팀원", "형님들", "스치니", "쓰친", "실시간", "보고 있었", "지켜보다", "장중에 봤"]
# 축약 종결형(음슴체) — JJ 2026-09-12 금지. '팜/오름/샀음/끊김/봄' 처럼 ㅁ 받침으로 끝나는 종결.
BAN_CHAT = ["ㅋ", "ㅎ", "ㅠ", "ㅜ", "..", "…", "ㄷㄷ", "ㅇㅇ"]
SPOKEN_END_RE = re.compile(r"(었|았|해|하|네|는데|어|아|지|되)요[.!?]?$|볼게요|할게요|드려요")
FAMILY_RE = re.compile(r"엄마|아빠|부모님|와이프|남편|아내|아들|딸이|딸은|딸도|친구가|동료가")
PRON_TRADE_RE = re.compile(r"(?:^|\s)(나|내가|저|제가|나도|저도|내|제|우리)(?:\s|$).{0,12}(샀|팔았|담|들고 있|벌었|잃었|날렸|비중)")
TRADE_RE = re.compile(r"(?:^|\s)(샀\S*|사고|사는|사들\S*|산|팔았\S*|팔고|파는|판|던졌\S*|던진|받았\S*|받은|받는|받아)(?=\s|$)")
PRONOUN_RE = re.compile(r"(?:^|\s)(얘네\S*|둘이|둘 다|셋 다|이쪽|그쪽|두 쪽)(?=\s|$)")
ASK_RE = re.compile(r"누가|누구|어디|어느")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿]")     # 편당 0~1개까지 허용
SYMBOL_RE = re.compile("[←-⇿•※·▶]")                        # 화살표·가운뎃점 같은 기호는 계속 금지
STREAK_RE = re.compile(r"(이틀|사흘|나흘|닷새|엿새|이레|\d+일)째|내리|연속")
REPEAT_RE = re.compile(r"(?:^|\s)또(?=\s)|연속|내리|만에|만이|다시|계속|(?:이틀|사흘|나흘|닷새|엿새|이레)째?")
REACT_RE = re.compile(r"놀람|놀랐|놀랍|놀라운|웃김|웃겼|웃었|웃깁|의외|신기|궁금|어이없|황당|재밌")
WATCH_PRICE_RE = re.compile(r"가는지|갈지|간다|받는지|오르는지|오를지|반등|버티는지")
Q_BAN_RE = re.compile(r"보셨|생각하|의견|어떻게 보|오를까|내릴까|사야|팔아야|샀어|팔았어|들고|계좌|수익|손실|갈까")


PH_RE = re.compile(r"[GTND](이랑|랑|이|가|은|는|도|엔|에|에선|에는|만|번|째|인지만|과|와|을|를|로|으로|입니다)?")
IDXFIG_RE = re.compile(r"\d+(?:\.\d+)?%|\d천피?(?!억)")     # 코스피 등락률·천 단위 — 인정 구간에서 두 번 쓰지 않는다


def strip_end(s):
    return re.sub(r"[\s.,!?~ㅋㅎ]+$", "", s)


def short_end(line):
    """축약 종결형(음슴체) 여부 — 'ㅁ' 받침으로 끝나면 참. 팜/오름/샀음/끊김/봄/함."""
    s = strip_end(line)
    return bool(s) and jong(s[-1]) == 16


# 반말 종결(JJ 2026-09-13). 음슴체(ㅁ 받침 종결)는 short_end가 따로 막는다 — 둘은 다른 검사다.
#   평서: 샀어 / 회사들이야 / 가장 많아 / 사들였어 / 뜻해 / 봐 / 돼 / 안 나와 / 볼게
#   질문: 받아 갔을까? / 어디라고 봐? / 뭐가 먼저 걸렸어? / 더 이상해 보여?
# '-습니다/-입니다'는 이제 통과하지 못한다. '-요'(구어체)는 SPOKEN_END_RE가 따로 잡는다.
DECL_END_RE = re.compile(r"(어|아|야|와|워|여|려|해|봐|돼|게)$")
QUES_END_RE = re.compile(r"(까|야|어|아|해|봐|지|나|여|려|워)\?$")


def tail_ok(line):
    """반말 종결인지 — 평서는 '-어/-야/-아/-해/-봐/-돼/-게.', 질문은 '-까?/-어?/-봐?', 이어지는 쉼표는 허용."""
    s = line.strip()
    if s.endswith(","):
        return True
    if s.endswith("?"):
        return bool(QUES_END_RE.search(s))
    if not s.endswith("."):
        return False
    return bool(DECL_END_RE.search(s[:-1]))


def history(d, n=5):
    """d 이전, 새 말투(threads_facts 있음)로 만든 날의 본문 — [{date, body, hero}] 오래된→최근. 옛 형식 날은 넣지 않는다."""
    out = []
    for x in prev_days(d, 12):
        c = load(x)
        if c.get("threads_facts") and (c.get("threads_text") or "").strip():
            out.append({"date": x, "body": c["threads_text"].strip(), "hero": c["threads_facts"].get("hero")})
    return out[-n:]


def build_ok(d, hist, tries=6):
    """문장 뱅크 회전을 한 칸씩 밀어 가며 검사를 통과하는 조합을 찾는다. 못 찾으면 위반이 가장 적은 것.
    (T20처럼 조합이 어제 글과 겹칠 때를 스스로 피해 간다. 같은 날짜·같은 이력이면 늘 같은 결과.)"""
    best = None
    for r in range(tries):
        seed, tf = build(d, hist, rot=r)
        issues = check(seed, tf, hist, seed)
        if not issues:
            return seed, tf, issues
        if best is None or len(issues) < len(best[2]):
            best = (seed, tf, issues)
    return best


def make(d):
    """computed_kr.json이 저장된 뒤 호출. (본문, tf, 검사 결과) — 검사 결과가 비어 있어야 정상."""
    return build_ok(d, history(d))


WD = "월화수목금토일"


GROUP_NAMES = tuple(n for n, _ in GROUPS)


def plain_q(q):
    """compute가 넘겨준 '{무엇} 순매수/순매도가 {N}째 이어지는지'를 쉬운 말로 바꾼다.
    답글도 본문과 같은 기준이다 — '순매수/순매도'라는 말은 쓰레드에 나가지 않는다(JJ 2026-09-13)."""
    q = (q or "").strip()
    m = re.match(r"^(.+?) 순매(수|도)가 (\S+째) 이어지는지$", q)
    if not m:
        return q.replace("순매수", "사는 쪽").replace("순매도", "파는 쪽")
    who, sign, nd = m.group(1).strip(), m.group(2), m.group(3)
    if who in GROUP_NAMES:                        # 주체: 외국인이 나흘째 파는지
        return f"{i_ga(dn(who))} {nd} {'사는지' if sign == '수' else '파는지'}"
    if sign == "수":                              # 테마: 금융으로 돈이 이틀째 들어오는지
        return f"{euro(who)} 돈이 {nd} 들어오는지"
    return f"{who}에서 돈이 {nd} 빠지는지"


def reply(d, comp, yt="{YT}"):
    """첫 답글: 채널 고지 + 영상 링크 + 다음 거래일에 볼 것. 가격·종목 없고 금융 용어도 없다.
    본문(첫 글)에는 이 셋을 넣지 않는다 — 처음 보는 사람에게 첫 글부터 내부 사정을 들이밀지 않는다."""
    ck = comp.get("check") or {}
    q = plain_q(ck.get("next_q") or ((comp.get("watch") or [{}])[0].get("q")) or "")
    when = "내일"
    base = datetime.strptime(d, "%Y%m%d")
    nd = ck.get("next_day") or ""
    mm = re.match(r"^(\d{1,2})/(\d{1,2})$", nd)
    if mm:
        nx = base.replace(month=int(mm.group(1)), day=int(mm.group(2)))
        if nx < base:
            nx = nx.replace(year=base.year + 1)
        if (nx - base).days > 1:
            when = WD[nx.weekday()] + "요일"
    elif base.weekday() == 4:
        when = "월요일"
    lines = ["돈이 어디에 머무는지만 매일 확인해. 맞는지는 기록으로 남겨.",
             f"영상 전체는 여기 → {yt}"]
    if q:                                                    # 본문에는 없다 — 다음에 볼 것은 늘 여기로 온다
        v = WATCH_B[datetime.strptime(d, "%Y%m%d").toordinal() % len(WATCH_B)]
        lines.append(v.format(when=f"{when}은", q=q))
    return "\n".join(lines)


def check(text, tf, hist=(), seed="", extra_masked=()):
    """Return list of failed rule ids with detail. [] = pass. `text` is the body (tag excluded)."""
    why = []
    body = text
    lines = body.split("\n")
    themes = tf["themes"]
    # T1 shape — 문단 사이 빈 줄은 허용(앞뒤·연속은 금지)
    ne = [x for x in lines if x.strip()]
    if lines and (not lines[0].strip() or not lines[-1].strip()):
        why.append("T1 leading/trailing blank line")
    for i in range(len(lines) - 1):
        if not lines[i].strip() and not lines[i + 1].strip():
            why.append("T1 double blank line")
    if not MIN_LINES <= len(lines) <= MAX_LINES:
        why.append(f"T1 {len(lines)} lines")
    if len(ne) < MIN_BODY_LINES:
        why.append(f"T1 {len(ne)} body lines")
    if not MIN_CHARS <= len(body) <= MAX_CHARS:
        why.append(f"T1 {len(body)} chars")
    for x in ne:
        if len(x) > MAX_LINE:
            why.append(f"T1 line>{MAX_LINE} ({len(x)}): {x}")
    if not ne:
        return why + ["T1 empty"]
    # T2 opener
    l1 = ne[0]
    if len(l1) > MAX_L1 or re.search(r"^(\d{1,2}월|\d{1,2}/\d{1,2}|오늘\s?(국장|코스피|장)|국장\s?마감|안녕|코스피(는|가)?\s?[\d,]{4,})", l1) \
            or re.search(r"마감했|마감입니다|마감함", l1):
        why.append("T2 opener shape")
    # T2b 첫 줄은 '독자가 이미 본 것' — 지수 등락률 + 이미 봤다는 인정
    sf = tf.get("seen_fig")
    if sf and (sf not in l1 or not re.search(r"봤|알 거|보이는|떠 있", l1)):
        why.append("T2b 첫 줄이 '독자가 이미 본 것'이 아님")
    # T2c 둘째 줄은 '그것만 보면 놓치는, 숫자가 든 사실' — 빈손 예고는 금지
    if len(ne) >= 2 and not FIG_RE.search(ne[1]):
        why.append(f"T2c 둘째 줄에 숫자가 없음: {ne[1]}")
    # T2d 인정 구간(첫 세 줄)에 코스피 숫자를 두 번 넣지 않는다
    if sum(1 for x in ne[:3] if IDXFIG_RE.search(x)) > 1:
        why.append("T2d 첫 세 줄에 코스피 숫자가 두 번")
    # T2e 목표 글자수 미달 — 전에는 하한만 있고 경고가 없었다
    if len(body) < TARGET_CHARS_MIN:
        why.append(f"T2e {len(body)}자 — 목표 {TARGET_CHARS_MIN}~{TARGET_CHARS_MAX}자 미달")
    if not all(any(tok in x for x in ne[:3]) for tok in tf["hero_tokens"]):
        why.append("T2 hero token not in lines 1-3")
    if not all(any(f in x for x in ne[:6]) for f in tf["hero_figs"]):
        why.append("T2 hero figure not in lines 1-6")
    # T3 figures
    figs = [m.group(0) for m in FIG_RE.finditer(body)]
    if len(figs) > MAX_FIGS:
        why.append(f"T3 figures>{MAX_FIGS} {figs}")
    bad = [f for f in figs if f not in tf["allowed_figures"]]
    if bad:
        why.append(f"T3 figure not allowed {bad}")
    for m in re.finditer(r"(" + FIG_RE.pattern + r")\s?(넘게|가까이|정도)", body):
        f, sfx = m.group(1), m.group(2)
        if sfx not in tf["edges"].get(f, []):
            why.append(f"T3 wrong rounding word {f} {sfx}")
    rest = FIG_RE.sub("", body)
    if tf["intraday_ok"]:
        rest = rest.replace("2시", "")
    for dtok in tf["allowed_days"]:
        rest = rest.replace(dtok, "")
    if re.search(r"\d", rest):
        why.append("T3 unlisted digit")
    if re.search(r"\d", ne[-1]):
        why.append("T3 digit in last line")
    if re.search(r"(?:^|\s)약\s?\d", body) or re.search(r"\d{1,2},000선|\d{4}선", body):
        why.append("T3 news number style (약 N / N,000선)")
    if "2시" in body and not re.search(r"오후 2시", body.split("2시")[0] + "2시"):
        why.append("T3 first 2시 mention without 오후")
    if re.search(r"\d+\.\d+조", body):
        why.append("T3 조 단위를 풀어 쓰지 않음 (9.9조 → 9조 9천억)")
    # T4 register — 반말 '-어/-야/-아/-까?'체(JJ 2026-09-13). 축약 종결(음슴체)·구어 종결(-요)은 그대로 금지.
    for x in ne:
        if not tail_ok(x):
            why.append(f"T4 반말 종결 아님: {x}")
        if short_end(x):
            why.append(f"T4 축약 종결형(음슴체): {x}")
        if SPOKEN_END_RE.search(x.strip()):
            why.append(f"T4 구어 종결(-요): {x}")
    tails = [strip_end(x)[-5:] for x in ne if not x.strip().endswith(",")]
    dup = [t for t in set(tails) if tails.count(t) > 2]
    if dup:
        why.append(f"T4 monotone endings {dup}")
    # T5 banned words
    for name, lst in (("news", BAN_NEWS), ("interp", BAN_INTERP), ("promo", BAN_PROMO), ("rec", BAN_REC), ("money", BAN_MONEY),
                      ("score", BAN_SCORE), ("cause", BAN_CAUSE), ("forecast", BAN_FORECAST), ("crowd", BAN_CROWD),
                      ("persona", BAN_PERSONA), ("jargon", BAN_JARGON)):
        hits = [wd for wd in lst if wd in body]
        if hits:
            why.append(f"T5 ban-{name} {hits}")
    # T6 chat markers / symbols / tag
    chat = [wd for wd in BAN_CHAT if wd in body]
    if chat:
        why.append(f"T6 채팅 기호 {chat}")
    if SYMBOL_RE.search(body) or "#" in body:
        why.append("T6 symbol/#")
    if len(EMOJI_RE.findall(body)) > 1:
        why.append("T6 이모지는 편당 0~1개")
    # T7 existing forbidden module, per line
    for x in ne:
        f = forbidden.find_threads(x)
        if f:
            why.append(f"T7 forbidden {f} in: {x}")
    # T8 persona / family / first-person trades
    if FAMILY_RE.search(body) or PRON_TRADE_RE.search(body):
        why.append("T8 persona/family/first-person trade")
    # T9 trade verbs need a group subject (같은 문단 안 앞줄의 주체를 이어받는 건 허용)
    para, pid = [], 0
    for x in lines:
        if not x.strip():
            pid += 1
            continue
        para.append((pid, x))
    for i, (p, x) in enumerate(para):
        if not TRADE_RE.search(x) or GROUP_RE.search(x) or ASK_RE.search(x):
            continue
        prev = [y for j, (q, y) in enumerate(para) if q == p and j < i]
        if not (PRONOUN_RE.search(x) and prev and GROUP_RE.search(prev[-1])):
            why.append(f"T9 trade verb without group: {x}")
    # T10 context lines: any line with a context keyword must be one of tf.context_lines, max 1
    ctx_kw = re.compile(r"만기|네 마녀|훈풍|모멘텀|리스크|지정학|유가|금리|환율|관세|실적|변동성|경계|우려|기대|금통위|CPI|FOMC|리밸런싱")
    ctx_hits = [x for x in ne if ctx_kw.search(x)]
    for x in ctx_hits:
        if x not in tf["context_lines"]:
            why.append(f"T10 context not from headline map: {x}")
    if len(ctx_hits) > 1:
        why.append("T10 more than one context line")
    # T11 repeat words must be backed by the seed
    for m in REPEAT_RE.finditer(body):
        if m.group(0).strip() not in seed:
            why.append(f"T11 unbacked repeat word '{m.group(0).strip()}'")
    mcnt = re.search(r"(두|세|네|다섯|여섯|일곱|여덟|아홉|열) 번 연속", body)
    if mcnt:
        why.append("T11 내부 카운터(N번 연속)는 풀어 써야 한다")
    if re.search(r"(확인|예고)[^\n]{0,8}중", body) or re.search(r"(하나|둘|셋|넷|\d)\s?중\s?(하나|둘|셋|한|두|세)", body):
        why.append("T11 내부 카운터(확인 N 중 M)는 본문에서 금지 — 풀어 쓸 것")
    # T12 must keep
    miss = [kx for kx in tf["must_keep"] if kx not in body]
    if miss:
        why.append(f"T12 must_keep missing {miss}")
    # T13 callback: exactly one verdict line when the ledger has one, none otherwise
    cbt = tf["callback"]
    verdict = [x for x in ne if VERDICT_RE.search(x) or CB_RE.search(x)]
    if not cbt and verdict:
        why.append("T13 callback line without a ledger verdict")
    if cbt:
        mine = [x for x in verdict if cbt["theme"] in x]
        if len(mine) != 1 or len(verdict) != 1:
            why.append("T13 need exactly one callback line naming the theme")
        if mine and not CB_RE.search(mine[0]):
            why.append("T13 검증 줄은 '어제 …보자고 한'처럼 풀어 써야 한다")
        for x in mine:
            if cbt["ok"] and re.search(r"끊|않았", x):
                why.append("T13 ok=true but 끊김")
            if not cbt["ok"] and re.search(r"이어졌|들어왔|그대로", x):
                why.append("T13 ok=false but 이어짐")
        if re.search(r"(?:^|\s)또(?=\s)", body) and cbt["miss_run"] < 2:
            why.append("T13 '또' with miss_run<2")
    # T14 watch: body only when the seed put it there; must name the flow, never a price verb
    wl = [x for x in ne if re.search(r"(내일|월요일)", x)]
    for x in wl:
        if WATCH_PRICE_RE.search(x):
            why.append(f"T14 price verb in watch line: {x}")
    if wl and not tf["watch_in_body"]:
        why.append("T14 watch line not allowed today (goes to first reply)")
    if tf["watch_in_body"]:
        if len(wl) != 1:
            why.append("T14 watch line count")
        for x in wl:
            if not re.search(r"사는지|파는지|들어오는지|빠지는지|돈", x) or not WATCH_LINE_RE.search(x) or (tf["watch"] and tf["watch"]["theme"] not in x):
                why.append(f"T14 watch line must name theme+flow and end '보겠습니다': {x}")
    # T15 questions — 가운데 한 줄(ask) + 마지막 닫는 줄(END_Q). 그 밖의 물음표는 금지.
    qmid = 1 if tf["ask_ok"] else 0
    qn = body.count("?")
    if qn > qmid + 1:
        why.append(f"T15 question count {qn} > {qmid + 1}")
    for x in ne:
        if "?" in x and Q_BAN_RE.search(x):
            why.append("T15 banned question")
    # T21 본문은 독자에게 던지는 질문으로 닫는다(JJ 2026-09-13 — 댓글이 붙는 글은 전부 질문으로 끝났다)
    if not ne[-1].rstrip().endswith("?"):
        why.append(f"T21 마지막 줄이 질문이 아님: {ne[-1]}")
    if sum(1 for x in ne[:-1] if x.rstrip().endswith("?")) > qmid:
        why.append("T21 가운데 질문이 한 줄을 넘음")
    # T16 stock / event names
    sn = [n for n in tf["stock_names"] if n in body]
    if sn:
        why.append(f"T16 stock name {sn}")
    ev = [e for e in tf["event_terms"] if e in body]
    if ev:
        why.append(f"T16 event term {ev}")
    # T17 at most one streak statement, not counting the callback line or the watch line's own target day
    nst = 0
    for x in ne:
        if VERDICT_RE.search(x) or CB_RE.search(x):
            continue
        nst += len(STREAK_RE.findall(x)) - (1 if WATCH_LINE_RE.search(x) else 0)
    if nst > 1:
        why.append(f"T17 stacked streaks ({nst})")
    # T18 rotation claims
    if re.search(r"옮겨|넘어감|넘어갔|갈아탔|로 이동|쪽으로 갔", body):
        why.append("T18 rotation claim (use '{테마}에는 N이 들어왔습니다' instead)")
    # T19 reactions must be anchored to a group/theme/figure on the same line
    for x in ne:
        if REACT_RE.search(x) and not (GROUP_RE.search(x) or any(t in x for t in themes) or FIG_RE.search(x)):
            why.append(f"T19 floating reaction: {x}")
    # T20 novelty vs last 5 posts — 고정 장치(어제 검증 줄·다음에 볼 것 줄)는 비교에서 뺀다
    def free(txt):
        return "\n".join(x for x in txt.split("\n") if x.strip() and not (WATCH_LINE_RE.search(x) or CB_RE.search(x)))

    last5 = list(hist)[-5:]
    prev_masked = {mask(ln, themes) for p in last5 for ln in free(p["body"]).split("\n") if ln.strip()} | set(extra_masked)
    same = [x for x in free(body).split("\n") if mask(x, themes) in prev_masked]
    if same:
        why.append(f"T20 repeated line skeleton {same}")
    bg = bigrams(free(body), themes)
    for p in last5:
        shared = {b for b in bg & bigrams(free(p["body"]), themes) if not all(PH_RE.fullmatch(tok) for tok in b)}
        # 허용치는 두 글의 길이에 맞춘다 — 6은 250자짜리 글 기준이었다(본문이 350~420자로 길어졌다).
        if len(shared) > max(6, (len(body) + len(p["body"])) // 80):
            why.append(f"T20 shares {len(shared)} phrase pairs with {p['date']}: {sorted(shared)}")
    if "2시" in body and sum(1 for p in list(hist)[-4:] if "2시" in p["body"]) > 1:
        why.append("T20 2시 frame used in 2 of the last 4 posts")
    return why


# ── final posts (body; publish appends "\n#국장") ──
SAMPLES = {
    "20260908": "주식 앱 켜면 0.58% 하락이 떠 있어.\n외국인은 내려가는 값을 받아 6,600억을 샀어.\n오후 2시에 세어 보니 1,700억이었어.\n나머지는 전부 그 뒤 한 시간 반에 들어왔어.\n\n그럼 그 주식을 판 쪽은 누구였을까?\n\n개인이 판 주식을 외국인과 기관, 회사들이 받았어.\n오늘 개인이 내놓은 돈이 3조 1천억이야.\n여기서 회사들은 상장한 기업 자신을 말해.\n\n자동차에서 빠져나간 돈이 1,500억이야.\n코스닥에서도 기관은 파는 쪽이었어.\n코스닥 쪽이 더 크게 내린 하루야.\n코스피는 가장 낮은 자리에서 하루를 끝냈어.\n외국인은 사흘째 같은 쪽에 서 있어.\n\n오늘은 그 드문 날이었어.\n같은 쪽에 선 날은 값이 한 방향으로 크게 움직여.\n너넨 이 돈 누가 받았다고 봐?",
    "20260909": "오늘 1.40% 상승은 앱만 켜도 보이는 숫자야.\n하루 사이 개인이 판 금액이 2조 3천억이야.\n오늘은 개인도 외국인도 파는 쪽이었어.\n\n그 주식은 누가 받아 갔을까?\n\n그만큼은 회사들과 기관이 받아 갔어.\n회사들은 기업이 직접 낸 돈이야.\n\n이차전지로 들어온 돈이 2,200억이야.\n코스닥에서 외국인은 받는 쪽이었어.\n코스닥은 그보다 더 크게 올랐어.\n꼭대기에서 얼마쯤 내려온 채로 문을 닫았어.\n기관이 산 건 나흘째야.\n기사들은 오늘을 AI 훈풍이라고 적었어.\n\n반도체로 더 들어올지 어제 적어 뒀는데, 오늘은 끊겼어.\n회사들이 받아 둔 주식은 한동안 시장 밖에 있어.\n판 쪽은 시장 밖에 있고 회사들이 그 자리를 메웠어.\n받아 간 쪽, 너넨 어디라고 봐?",
    "20260910": "코스피가 0.25% 빠진 것까지는 알 거야.\n외국인은 오늘 하루에만 2조 5천억을 팔았어.\n오후 2시까지는 3,500억이었어.\n그 뒤 한 시간 반 사이에 쏟아졌어.\n\n그걸 다 받아 낸 쪽은 누구였을까?\n\n받아 간 쪽은 대부분 회사들이야.\n회사들은 사흘 내내 가장 많이 산 쪽이야.\n회사들은 사람도 기관도 아닌 기업 자신이야.\n\n반도체에서는 하루 동안 1조 5천억이 빠졌어.\n코스닥에서는 기관이 제일 많이 받았어.\n그다음으로 많이 산 쪽은 개인이야.\n코스피는 하루 중 더 아래까지 내려갔었어.\n\n어제 적어 둔 이차전지로는 오늘 돈이 들어오지 않았어.\n회사들이 받아 간 자리는 대개 자기 회사 주식이야.\n빠져나간 자리를 회사들이 자기 돈으로 메운 하루야.\n다들 이 돈이 어디로 갔다고 봐?",
    "20260911": "1.76% 내린 코스피는 아마 이미 봤을 거야.\n외국인이 하루에 판 금액이 2조 3천억이야.\n\n그럼 그만큼은 누가 받은 걸까?\n\n개인과 회사들이 그만큼을 나눠서 받았어.\n개인이 받아 간 만큼이 1조 9천억이야.\n그 주식을 판 쪽은 외국인과 기관이야.\n기관은 같은 날 1조 2천억을 내놨어.\n개인은 증권 앱으로 직접 사고파는 사람들이야.\n\n반도체 한 곳에서만 3조 3천억이 나왔어.\n코스닥에서 주식을 받아 간 쪽도 개인이야.\n한때는 지금 숫자보다 더 아래에 있었어.\n금융에 들어오는 돈이 이틀째 이어지고 있어.\n\n어제 보자고 한 금융 쪽 돈은 오늘도 들어왔어.\n이 두 곳이 같은 쪽에 서는 날은 자주 안 나와.\n둘이 같은 쪽에 서면 값은 한쪽으로 크게 기울어.\n너넨 오늘 숫자에서 뭐가 제일 이상해?",
}
OLD = {
    "20260909": "9월 9일 국장. 코스피가 1.40% 올라 7,052에 마감했습니다. 반도체 강세 속에 33거래일 만에 7000선을 다시 밟았습니다.\n\n눈에 띈 건 시간대였습니다. 오후 2시까지 외국인은 약 2,700억 순매수였는데, 마감엔 약 4,300억 순매도로 돌아섰습니다.\n\n돈은 이차전지로 갔습니다. 오늘 하루 약 2,200억이 들어왔고 외국인과 기관이 둘 다 샀습니다. 반대로 반도체에서는 약 960억이 빠졌습니다.\n\n어제 보자고 한 반도체는 오늘 끊겼습니다.\n\n개인은 약 2.3조를 팔았습니다. 지수가 오른 날 개인이 내놓는 그림입니다.\n\n내일은 이차전지 순매수가 이틀째 이어지는지가 관건입니다.\n\n돈이 어디에 머무는지만 매일 확인합니다. 맞는지는 기록으로 남깁니다.",
    "20260911": "와 외국인 2.3조 던짐..\n오후 2시만 해도 4,700억 정도였음..\n받은 건 개인이랑 기타법인\n어제 보자던 금융 이틀째는 이어짐",
}
# one-line swaps into the newest seed ("first"=첫 줄, "mid"=가운데 줄, "last"=마지막 줄); every one must fail
ADVERSARIAL = [
    ("mid", "나도 오늘 반도체 조금 담았어."),
    ("mid", "외국인 매도 때문에 빠진 걸로 보여."),
    ("mid", "지금이 기회일 수 있어."),
    ("last", "여러분은 오늘 어떻게 보고 있어?"),
    ("mid", "프로그램도 2조 9천억을 팔았어."),
    ("mid", "기타법인은 1조 7천억, 기관은 4,600억을 샀어."),
    ("mid", "#주식 #코스피"),
    ("mid", "받은 건 대부분 기타법인ㅋㅋ"),
    ("mid", "받은 쪽은 기타법인이야 ㅎㅎ"),
    ("first", "9월 11일 국장, 외국인이 2조 3천억을 팔았어."),
    ("first", "오늘 코스피는 이렇게 끝났어."),
    ("last", "내일은 반도체가 반등할 듯해."),
    ("mid", "금융 쪽으로 돈이 몰릴 것 같아."),
    ("mid", "오늘 조금 샀어."),
    ("mid", "하나금융지주는 거의 안 움직였어."),
    ("last", "확인 셋 중 이어진 건 하나야."),
    ("last", "어제 보자던 금융은 두 번 연속 끊겼어."),
    ("last", "내일은 금융이 오를지만 볼게."),
    ("mid", "하루 만에 판이 바뀌었어."),
    ("first", "와 외국인이 약 2조 3천억을 던졌어."),
    ("mid", "코스피는 7,000선을 지켰어."),
    ("mid", "이건 좀 놀랐어."),
    ("mid", "받은 쪽은 기타법인·기관·개인이야."),
    ("mid", "개미들은 또 털렸어."),
    ("mid", "오후 2시만 해도 4,700억 넘게였어."),
    ("mid", "만기라서 막판 물량이 나온 거야."),
    ("first", "외국인이 2.3조를 팔았어."),
    ("mid", "받은 건 개인이랑 기타법인"),
    ("mid", "외국인은 사흘째 팔았고 기관도 이틀째 팔았어."),
    ("last", "내일은 금융 순매수가 이어지는지만 봄"),
    ("last", "내일은 금융 순매수가 이어지는지 볼게ㅋㅋ"),
    ("mid", "외국인이 던진 물량을 개인이 받았어요."),
    # 2026-09-13 새 규칙: 첫 줄은 '독자가 이미 본 것'이어야 하고, 번호 목록·채널 고지·영상 링크는 본문 밖이다
    ("first", "코스피는 오늘 1.76% 내렸어."),
    ("first", "외국인은 오늘 2조 3천억을 팔았어."),
    ("first", "오늘 국장 마감을 정리해."),
    ("mid", "1. 외국인이 팔았어."),
    ("mid", "영상 전체는 여기서 볼 수 있어."),
    ("mid", "구독이랑 알림 설정 부탁해."),
    ("last", "월요일은 금융 순매수가 이어지는지 볼게."),
    # 2026-09-13 두 번째 지시: 쓰레드에 금융 용어를 쓰지 않는다 + 둘째 줄은 숫자가 든 사실이어야 한다
    ("second", "그 아래에서 외국인은 파는 쪽이었어."),
    ("second", "확인할 숫자는 따로 있어."),
    ("second", "코스피는 7천 위에서 끝났어."),
    ("mid", "외국인이 순매도로 돌아섰어."),
    ("mid", "오늘 수급을 그대로 옮기면 이래."),
    ("mid", "기타법인 자리는 자사주 매입일 때가 많아."),
    ("mid", "정규장 체결 기준으로 집계한 숫자야."),
    ("mid", "지수가 흔들린 건 변동성 탓이야."),
    ("mid", "오늘 거래대금은 평소보다 컸어."),
    ("last", "받은 물량은 기타법인이 가져갔어."),
    # 2026-09-13 세 번째 지시(반말 전환): 합니다체·음슴체가 섞이면 안 되고, 마지막 줄은 질문이어야 한다
    ("mid", "그만큼을 받은 쪽은 회사들입니다."),
    ("mid", "받아 간 쪽은 회사들이라고 봅니다."),
    ("mid", "그 주식은 회사들이 다 받아감"),
    ("last", "오늘은 여기까지만 숫자로 말할 수 있어."),
    ("last", "너넨 오늘 얼마나 샀어?"),
    ("last", "너넨 오늘 계좌 봤어?"),
    ("last", "너넨 내일 아침에 앱 켜 볼 거야?"),
    ("mid", "다들 물렸지?"),
    ("mid", "그럼 이건 누가 받았을까?"),
]
DAYS = ("20260908", "20260909", "20260910", "20260911")
# 뱅크 점검용 더미 값 — 모든 변형이 금지어·완결형·길이 검사를 통과하는지 본다
DUMMY = {"p": "1.00%", "T": "7", "n": "33", "nm": "외국인", "nm_eun": "외국인은", "nm_ga": "외국인이",
         "f": "1조 2천억", "f_eul": "1조 2천억을", "f_ga": "1조 2천억이", "f_ya": "1조 2천억이야", "f_was": "1조 2천억이었",
         "vb": "사", "vb3": "판 쪽이었어",
         "s0": "개인", "s1": "외국인", "s0_gwa": "개인과", "S": "개인", "S_ga": "개인이", "S_eun": "개인은",
         "B": "기관", "B_ga": "기관이", "B_eun": "기관은", "B2": "기관과 회사들", "tb": "회사들",
         "tb_eun": "회사들은", "tb_ga": "회사들이", "most": "대부분", "days": "사흘", "dc": "이틀째",
         "g": "외국인", "g_eun": "외국인은", "g_ga": "외국인이", "vb4": "산", "mv": "올랐", "mv2": "오른",
         "th": "이차전지", "th_ro": "이차전지로", "th_ya": "이차전지야",
         "when": "내일은", "q": "이차전지로 돈이 이틀째 들어오는지"}


def audit_banks():
    """문장 뱅크 전수 점검: 금지어·forbidden·완결형 종결·축약 종결·줄 길이."""
    bad = []
    banks = {n: v for n, v in globals().items() if n.isupper() and isinstance(v, list) and v and isinstance(v[0], str)
             and n not in ("THEMES", "BAN_CHAT") and not n.startswith("BAN_")}
    banks["CONTEXT"] = [s for _, b in CONTEXT for s in b]
    for name, bank in banks.items():
        if len(bank) < 3:
            bad.append(f"{name}: 변형 {len(bank)}개 (3개 이상이어야 함)")
        for v in bank:
            try:
                s = v.format(**DUMMY)
            except KeyError as e:
                bad.append(f"{name}: 알 수 없는 자리표시자 {e} in {v}")
                continue
            for nm2, lst in (("news", BAN_NEWS), ("interp", BAN_INTERP), ("promo", BAN_PROMO), ("rec", BAN_REC), ("money", BAN_MONEY),
                             ("score", BAN_SCORE), ("cause", BAN_CAUSE), ("forecast", BAN_FORECAST), ("crowd", BAN_CROWD),
                             ("persona", BAN_PERSONA), ("jargon", BAN_JARGON)):
                hit = [w for w in lst if w in s]
                if hit:
                    bad.append(f"{name}: ban-{nm2} {hit} in {s}")
            if forbidden.find_threads(s):
                bad.append(f"{name}: forbidden {forbidden.find_threads(s)} in {s}")
            if not tail_ok(s):
                bad.append(f"{name}: 반말 종결 아님 — {s}")
            if short_end(s):
                bad.append(f"{name}: 축약 종결형 — {s}")
            if any(ch in s for ch in BAN_CHAT):
                bad.append(f"{name}: 채팅 기호 — {s}")
            if len(s) > MAX_LINE:
                bad.append(f"{name}: {len(s)}자 — {s}")
    return bad


if __name__ == "__main__":
    hist = []
    ok_all = True
    ab = audit_banks()
    print("BANK AUDIT:", "통과" if not ab else "")
    for x in ab:
        print("  -", x)
    ok_all &= not ab
    for d in DAYS:
        seed, tf, s_issues = build_ok(d, hist)
        print("=" * 12, d, "hero", tf["hero"], "| top buyer", tf["top_buyer"], tf["top_buyer_run"], "| cb", tf["callback"], "| watch_in_body", tf["watch_in_body"])
        print(seed)
        print(f"-- seed {len(seed)} chars, {len(seed.split(chr(10)))} lines {[len(x) for x in seed.split(chr(10))]}")
        print("   allowed", tf["allowed_figures"], tf["allowed_days"], "| ctx", bool(tf["context_lines"]), "| keep", tf["must_keep"])
        print("   seed issues:", s_issues or "none", "| matches SAMPLES:", SAMPLES.get(d) == seed)
        ok_all &= not s_issues
        if SAMPLES.get(d) is not None:
            ok_all &= SAMPLES[d] == seed
        if d in OLD:
            o = check(OLD[d], tf, hist, seed)
            print(f"   OLD post fails {len(o)} rules:", sorted({x.split(' ')[0] for x in o}))
            ok_all &= bool(o)
        if d == DAYS[-1]:
            base = seed.split("\n")
            idx = [i for i, x in enumerate(base) if x.strip()]
            for pos, bad in ADVERSARIAL:
                ln = list(base)
                ln[{"first": idx[0], "second": idx[1], "mid": idx[len(idx) // 2], "last": idx[-1]}[pos]] = bad
                r = check("\n".join(ln), tf, hist, seed)
                print(f"   ADV {'FAIL' if r else '!!PASS!!'} [{bad}] -> {[x[:56] for x in r][:2]}")
                ok_all &= bool(r)
        hist.append({"date": d, "body": seed, "hero": tf["hero"]})
        print("   reply:", reply(d, load(d)).replace("\n", " | "))
    # rotation: same data again tomorrow -> seed must pick other variants and still pass
    for d in (DAYS[0], DAYS[-1]):
        seed2, tf2, r2 = build_ok(d, hist)
        print("ROTATION", d, "\n" + seed2, "\n  issues:", r2 or "none")
        ok_all &= not r2
    # cross-day novelty stats
    for i in range(len(hist)):
        for j in range(i + 1, len(hist)):
            sh = {x for x in bigrams(hist[i]["body"]) & bigrams(hist[j]["body"]) if not all(PH_RE.fullmatch(t) for t in x)}
            print("shared phrase pairs", hist[i]["date"], hist[j]["date"], len(sh), sorted(sh)[:6])
    print("ALL OK" if ok_all else "SOMETHING FAILED")
