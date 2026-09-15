"""qa_script.check_brief 자체 검사 — 순수 파이썬(unittest), 데이터 폴더를 읽지 않는다(recs 를 직접 넣는다).

실행(market-close/jobs 에서):  python test_qa_brief.py
통과 대본 GOOD 은 JJ 승인본 docs/scripts/2026-09-15_brief.md 의 사실·순서(코스피 수급 → 코스닥+지수 → 빠진 곳 → 들어온 곳 → 종목 둘 →
뉴스 판정 → 내일 포인트)에 정본 장치 문장(모순 후킹·질문 선언·대변→차단·그런데·화면 지시어·직접 열어봤습니다·쪽입니다·뒤집히는 조건·
임계값·시그니처)을 얹고 1,150자(공백 포함, len(tts)) 안에 눌러 담은 것. 승인본 문장 그대로는 1,349자라 선택 사실(종목 이름 넷·어제 대비·
나머지 유출 금액·한계 문장)은 뺐다. 규칙마다 실패 사례 하나씩: 설계 docs/BRIEF_FORMAT_DESIGN.md §3.
"""
from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_script as qa  # noqa: E402

D = "20260915"                                                   # 9/15 편 = '내일부터 매일 저녁 5시'
AFTER = qa.AFTER_MARKET                                           # 정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다.
SIG15 = f"{AFTER} {qa.SIG_BRAND} {qa.SIG_FIRST}"                  # 9/15: 내일부터
SIG16 = f"{AFTER} {qa.SIG_BRAND} {qa.SIG_DAILY}"                  # 9/16~9/18: 매일 + 애프터마켓
SIG21 = f"{qa.SIG_BRAND} {qa.SIG_DAILY}"                          # 9/21~: 애프터마켓 문장 없음
S6_BODY = "외국인 순매도가 엿새째 이어지는지. 이차전지 유입이 이틀째인지. 목요일 새벽 3시 미국 금리 결정입니다. "

GOOD = [
    {"id": "s0", "tts": "외국인 1조 5,700억 순매도. 코스피는 0.85%만 내렸습니다."},
    {"id": "s1", "tts": "그 돈이 어디로 갔느냐. 오늘은 이것 하나만 봅니다."},
    {"id": "s2", "tts": "새 돈이라고 생각하기 쉽습니다. 외국인 1조 5,700억 순매도, 닷새째입니다. 기관 9천억 순매도, 개인 8,300억 순매수입니다. "
                        "그런데 네 번째 막대를 보세요. 기타법인 1조 6,400억, 1위입니다. 99%가 삼성전자와 SK하이닉스 자사주입니다. 코스닥은 어땠을까요."},
    {"id": "s3a", "tts": "코스닥은 반대, 위 칸 막대를 보세요. 외국인 240억, 기관 1,100억 순매수였습니다. 개인은 1,400억 팔았습니다. "
                         "코스피 0.85% 하락, 코스닥 0.70% 상승입니다. 그런데 코스닥 큰손은 반대로 샀습니다. 어느 업종에서 나갔을까요."},
    {"id": "s3b", "tts": "빠진 곳은 반도체, 왼쪽 막대를 보세요. 외국인 1조 3,400억, 기관 7,100억이 나갔습니다. 합쳐 2조 400억, 닷새째입니다. "
                         "그런데 삼성전자는 0.2%, SK하이닉스는 0.4%만 내렸습니다. 자사주 1조 6,300억이 값을 붙든 겁니다. 어디로 옮겨 갔을까요."},
    {"id": "s3c", "tts": "이번엔 들어온 쪽, 오른쪽 막대를 보세요. 이차전지에 외국인 480억, 기관 460억이 들어왔습니다. 로봇에는 외국인 260억, 기관 120억입니다. "
                         "반도체에서 나간 돈의 16분의 1입니다. 그 안에서 누가 샀을까요."},
    {"id": "s4", "tts": "9월 15일 키움 종목별 투자자 표를 직접 열어봤습니다. 대장주 LG에너지솔루션은 3.98% 올랐습니다. "
                        "기관 410억 순매수, 개인 320억 순매도입니다. 외국인 8억 순매도, 기관이 올린 겁니다. 최대 상승 삼현은 상한가 29.8%입니다. "
                        "외국인 13억, 기관 26억 순매수입니다. 개인 37억 순매도, 거래대금 548억입니다. 큰손 합 39억은 7.1%뿐입니다."},
    {"id": "s5", "tts": "뉴스는 둘, 이차전지는 미국의 포드 서한, 로봇은 정부 AI 행사입니다. 뉴스가 올린 값이면 큰손 돈이 작고, 돈이 올린 값이면 외국인과 기관이 같이 삽니다. "
                        "이차전지는 돈 쪽, 로봇은 뉴스 쪽입니다. 뒤집히는 조건은 내일 로봇에 큰손 돈 1,000억입니다. 처음 1조 5,700억 중 1조 3,400억이 반도체였습니다."},
    {"id": "s6", "tts": S6_BODY + SIG15},
]
COMP = {"date": D, "format": "brief",
        "hunter": {"s2": {"reveal": {"name": "기타법인", "v": 16431, "days": 0, "top": [["삼성전자", 9800], ["SK하이닉스", 6500]], "share": 0.99}},
                   "s4": {"doc": "키움 종목별 투자자 표 · 9/15 마감 기준", "date": D,
                          "stocks": [{"name": "LG에너지솔루션", "role": "대장주", "theme": "이차전지", "pct": 3.98, "foreign": -8, "inst": 410, "indiv": -320, "value": None},
                                     {"name": "삼현", "role": "최대 상승", "theme": "로봇", "pct": 29.8, "foreign": 13, "inst": 26, "indiv": -37, "value": 548}],
                          "calc": {"expr": "39 ÷ 548", "result": "7.1%", "lhs": 39, "rhs": 548, "value": 7.1, "kind": "share", "verified": True}}}}


def run(scenes=None, comp=None, recs=None, warn=None):
    return qa.check_brief(scenes if scenes is not None else GOOD, comp if comp is not None else COMP,
                          recs=[] if recs is None else recs, warn=warn)


def edit(sid: str, tts: str, base=None) -> list[dict]:
    out = copy.deepcopy(base if base is not None else GOOD)
    for s in out:
        if s["id"] == sid:
            s["tts"] = tts
    return out


def without(tts: str, *sents: str) -> str:
    """문장 몇 개를 빼고 공백을 정리한다(짧은 대본 만들기)."""
    for x in sents:
        assert x in tts, x
        tts = tts.replace(x, " ")
    return re.sub(r"\s+", " ", tts).strip()


def dated(d: str, s6_sig: str, base=None) -> tuple[list[dict], dict]:
    """날짜만 바꾼 대본·comp — s6 의 시그니처 꼬리를 s6_sig 로 갈아 끼운다."""
    comp = copy.deepcopy(COMP)
    comp["date"] = d
    return edit("s6", S6_BODY + s6_sig, base), comp


# 900자 밑으로 내리려고 빼는 선택 문장들 — 규칙(주체 이름·숫자 3개·계산·판정·임계값)은 그대로 남는다
SHORT_DROP = {"s2": ("99%가 삼성전자와 SK하이닉스 자사주입니다.",),
              "s3a": ("개인은 1,400억 팔았습니다.",),
              "s3b": ("합쳐 2조 400억, 닷새째입니다.", "자사주 1조 6,300억이 값을 붙든 겁니다."),
              "s3c": ("로봇에는 외국인 260억, 기관 120억입니다.", "반도체에서 나간 돈의 16분의 1입니다."),
              "s4": ("외국인 8억 순매도, 기관이 올린 겁니다.", "개인 37억 순매도, 거래대금 548억입니다."),
              "s5": ("뉴스는 둘, 이차전지는 미국의 포드 서한, 로봇은 정부 AI 행사입니다.", "처음 1조 5,700억 중 1조 3,400억이 반도체였습니다."),
              "s6": ("이차전지 유입이 이틀째인지.",)}


def short_scenes() -> list[dict]:
    scenes = copy.deepcopy(GOOD)
    for s in scenes:
        if s["id"] in SHORT_DROP:
            s["tts"] = without(s["tts"], *SHORT_DROP[s["id"]])
    return scenes


def has(bad: list[str], scene: str, frag: str) -> bool:
    return any(b.startswith(f"[{scene}]") and frag in b for b in bad)


def total(scenes: list[dict]) -> int:
    return sum(len(s["tts"]) for s in scenes)


class Passing(unittest.TestCase):
    def test_brief_sample_passes(self):
        warn: list[str] = []
        bad = run(warn=warn)
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertEqual(warn, [], warn)
        self.assertTrue(qa.BRIEF_TOTAL_MIN <= total(GOOD) <= qa.BRIEF_TOTAL_MAX, total(GOOD))

    def test_sample_also_passes_hunter(self):
        """브리핑은 헌터 장치 위에 얹은 것 — 헌터 검사만 따로 돌려도 통과."""
        bad = qa.check_hunter(GOOD, COMP, recs=[])
        self.assertEqual(bad, [], "\n".join(bad))

    def test_fixed_chain_facts_in_order(self):
        """승인본 9/15 의 사실이 같은 순서로 들어 있다(문장은 달라도 된다)."""
        order = [("s2", "1조 5,700억"), ("s2", "9천억"), ("s2", "8,300억"), ("s2", "기타법인 1조 6,400억"), ("s2", "99%"),
                 ("s3a", "240억"), ("s3a", "1,100억"), ("s3a", "1,400억"), ("s3a", "0.85%"), ("s3a", "0.70%"),
                 ("s3b", "반도체"), ("s3b", "1조 3,400억"), ("s3b", "7,100억"), ("s3b", "2조 400억"), ("s3b", "0.2%"), ("s3b", "0.4%"), ("s3b", "1조 6,300억"),
                 ("s3c", "이차전지"), ("s3c", "480억"), ("s3c", "460억"), ("s3c", "로봇"), ("s3c", "260억"), ("s3c", "120억"), ("s3c", "16분의 1"),
                 ("s4", "LG에너지솔루션"), ("s4", "3.98%"), ("s4", "410억"), ("s4", "320억"), ("s4", "8억"), ("s4", "삼현"), ("s4", "29.8%"), ("s4", "13억"), ("s4", "26억"), ("s4", "37억"), ("s4", "548억"),
                 ("s5", "포드"), ("s5", "로봇"), ("s5", "쪽입니다"), ("s5", "뒤집히는 조건"),
                 ("s6", "엿새째"), ("s6", "이틀째"), ("s6", "새벽 3시")]
        last, pos = "", 0
        for sid, frag in order:                                       # 같은 장면 안에서는 앞 사실 뒤에서 찾는다
            tts = next(s["tts"] for s in GOOD if s["id"] == sid)
            i = tts.find(frag, pos if sid == last else 0)
            self.assertGreaterEqual(i, 0, f"{sid}: '{frag}' 없음 또는 순서 어긋남")
            last, pos = sid, i + 1

    def test_fail_format(self):
        bad = run(edit("s3b", "반도체가 정체된 자리입니다. 왼쪽 막대를 보세요. 그럼 그 돈은 어디로 들어갔을까요."))
        self.assertTrue(bad)
        for b in bad:
            self.assertTrue(b.startswith("[") and " :: " in b, b)
        self.assertIn("[s3b] 빠진 돈 표현 없음(빠졌|나갔|순매도) :: 반도체가 정체된 자리입니다.", bad)

    def test_hunter_rules_apply_through_brief(self):
        """check_brief 는 check_hunter 의 11항을 그대로 품는다 — 그런데 없는 S2, 임계값 없는 S6, 한 문장 숫자 3개."""
        bad = run(edit("s2", GOOD[2]["tts"].replace("그런데 ", "")))
        self.assertTrue(has(bad, "s2", "그런데 없음"), bad)
        bad = run(edit("s6", "내일은 외국인이 어떻게 하는지 봅니다. " + SIG15))
        self.assertTrue(has(bad, "s6", "임계값 숫자 없음"), bad)
        bad = run(edit("s3a", GOOD[3]["tts"].replace("외국인 240억, 기관 1,100억 순매수였습니다.", "외국인 240억, 기관 1,100억, 개인 1,400억입니다.")))
        self.assertTrue(has(bad, "s3a", "숫자 3개"), bad)


class S2(unittest.TestCase):
    def test_party_missing(self):
        bad = run(edit("s2", GOOD[2]["tts"].replace("기관 9천억 순매도", "큰손 9천억 순매도")))
        self.assertTrue(has(bad, "s2", "코스피 수급 주체 빠짐(기관)"), bad)

    def test_fewer_than_three_numbers(self):
        bad = run(edit("s2", "새 돈이라고 생각하기 쉽습니다. 외국인과 기관은 팔았고 개인은 샀습니다. 그런데 네 번째 막대를 보세요. "
                             "기타법인이 가장 많이 샀습니다. 코스닥은 어땠을까요."))
        self.assertIn("[s2] 수급 숫자 1개 < 3 — 주체마다 숫자를 말해야 한다 :: 외국인과 기관은 팔았고 개인은 샀습니다.", bad)

    def test_others_required_unless_small(self):
        scenes = edit("s2", "새 돈이라고 생각하기 쉽습니다. 외국인 1조 5,700억 순매도, 닷새째입니다. 기관 9천억 순매도, 개인 8,300억 순매수입니다. "
                            "그런데 네 번째 막대를 보세요. 자사주가 그 물량을 받았습니다. 코스닥은 어땠을까요.")
        bad = run(scenes)
        self.assertTrue(has(bad, "s2", "기타법인 없음"), bad)
        small = copy.deepcopy(COMP)
        small["hunter"]["s2"]["reveal"]["v"] = 2400                   # 설계 §2: 3,000억 미만이면 이름을 빼도 된다
        self.assertFalse(has(run(scenes, small), "s2", "기타법인 없음"), run(scenes, small))
        small["hunter"]["s2"]["reveal"]["v"] = -2900                  # 부호가 아니라 크기로 본다
        self.assertFalse(has(run(scenes, small), "s2", "기타법인 없음"), run(scenes, small))
        small["hunter"]["s2"]["reveal"]["v"] = None                   # 값을 모르면 이름은 있어야 한다
        self.assertTrue(has(run(scenes, small), "s2", "기타법인 없음"), run(scenes, small))


class S3(unittest.TestCase):
    def test_s3a_needs_both_indexes(self):
        bad = run(edit("s3a", "다른 시장은 반대였습니다. 위 칸 막대 셋을 보세요. 외국인 240억, 기관 1,100억 순매수였습니다. "
                              "그런데 코스피 지수는 0.85% 내렸습니다. 그럼 빠진 돈은 어느 업종에서 나갔을까요."))
        self.assertTrue(has(bad, "s3a", "코스닥 없음"), bad)
        self.assertFalse(has(bad, "s3a", "코스피 없음"), bad)
        bad = run(edit("s3a", GOOD[3]["tts"].replace("코스피", "큰 시장")))
        self.assertTrue(has(bad, "s3a", "코스피 없음"), bad)

    def test_s3b_needs_outflow(self):
        bad = run(edit("s3b", "돈이 정체된 곳은 반도체입니다. 왼쪽 막대를 보세요. 외국인 1조 3,400억, 기관 7,100억입니다. "
                              "그런데 삼성전자는 0.2% 내리는 데 그쳤습니다. 그럼 그 돈은 어디로 들어갔을까요."))
        self.assertTrue(has(bad, "s3b", "빠진 돈 표현 없음"), bad)

    def test_s3c_needs_inflow_or_none(self):
        bad = run(edit("s3c", "이번엔 반대쪽입니다. 오른쪽 막대 둘을 보세요. 이차전지에 외국인 480억, 기관 460억입니다. "
                              "로봇에는 외국인 260억, 기관 120억입니다. 그럼 그 안에서 누가 샀을까요."))
        self.assertTrue(has(bad, "s3c", "들어온 돈 표현 없음"), bad)
        # 설계 §2 대체 규칙: 유입 업종이 없는 날
        ok = run(edit("s3c", "들어온 곳이 없었습니다. 가장 덜 빠진 곳은 이차전지입니다. 오른쪽 막대를 보세요. "
                             "외국인 480억이 나갔고 기관 460억이 나갔습니다. 전부 유출입니다. 그럼 그 안에서 누가 팔았을까요."))
        self.assertFalse(has(ok, "s3c", "들어온 돈 표현 없음"), ok)


class S4(unittest.TestCase):
    def test_stock_names(self):
        bad = run(edit("s4", GOOD[6]["tts"].replace("삼현", "그 종목")))
        self.assertTrue(has(bad, "s4", "종목 이름 없음(삼현)"), bad)
        self.assertFalse(has(bad, "s4", "종목 이름 없음(LG에너지솔루션)"), bad)
        # 이름 안의 띄어쓰기는 무시한다
        comp = copy.deepcopy(COMP)
        comp["hunter"]["s4"]["stocks"][0]["name"] = "LG 에너지솔루션"
        self.assertFalse(has(run(comp=comp), "s4", "종목 이름 없음"), run(comp=comp))

    def test_parties_and_no_indiv_fallback(self):
        no_indiv = ("9월 15일 키움 종목별 투자자 표를 직접 열어봤습니다. 대장주 LG에너지솔루션은 3.98% 올랐습니다. "
                    "기관 410억 순매수, 외국인 8억 순매도입니다. 기관이 올린 겁니다. 최대 상승 삼현은 상한가 29.8%입니다. "
                    "외국인 13억, 기관 26억 순매수입니다. 거래대금은 548억입니다. 큰손 합 39억은 7.1%뿐입니다.")
        bad = run(edit("s4", no_indiv))
        self.assertTrue(has(bad, "s4", "주체 없음(개인)"), bad)
        comp = copy.deepcopy(COMP)
        comp["hunter"]["s4"]["no_indiv"] = True                      # 설계 §2: brief_stocks 실패 → 개인은 말하지 않는다
        self.assertFalse(has(run(edit("s4", no_indiv), comp), "s4", "주체 없음"), run(edit("s4", no_indiv), comp))
        bad = run(edit("s4", no_indiv.replace("기관", "큰손")), comp)
        self.assertTrue(has(bad, "s4", "주체 없음(기관)"), bad)


class S5(unittest.TestCase):
    def test_news_required(self):
        bad = run(edit("s5", GOOD[7]["tts"].replace("뉴스", "기사")))
        self.assertTrue(has(bad, "s5", "뉴스 없음"), bad)
        self.assertFalse(has(bad, "s5", "판정 문장 없음"), bad)

    def test_verdict_and_condition_still_checked(self):
        bad = run(edit("s5", "뉴스는 둘, 이차전지는 미국의 포드 서한, 로봇은 정부 AI 행사입니다. "
                             "이차전지는 돈이 값을 올렸고, 로봇은 뉴스가 값을 올렸습니다. 주체별 합계라 종목 사이 이동은 안 보입니다."))
        self.assertTrue(has(bad, "s5", "판정 문장 없음"), bad)
        self.assertTrue(has(bad, "s5", "뒤집히는 조건 없음"), bad)


class S6(unittest.TestCase):
    def test_signature_by_date(self):
        scenes, comp = dated("20260915", SIG16)                       # 9/15 인데 '내일부터'가 없다
        bad = run(scenes, comp)
        self.assertTrue(has(bad, "s6", f"끝 멘트 고정문 없음('{qa.SIG_FIRST}')"), bad)
        scenes, comp = dated("20260916", SIG15)                       # 9/16 인데 '내일부터'가 남았다
        bad = run(scenes, comp)
        self.assertTrue(has(bad, "s6", f"끝 멘트 고정문 없음('{qa.SIG_DAILY}')"), bad)
        scenes, comp = dated("20260916", SIG16)
        self.assertEqual(run(scenes, comp), [], run(scenes, comp))

    def test_brand_line_and_order(self):
        scenes, comp = dated("20260915", f"{AFTER} {qa.SIG_FIRST}")
        self.assertTrue(has(run(scenes, comp), "s6", "시그니처 없음"), run(scenes, comp))
        scenes, comp = dated("20260915", SIG15 + " 내일 이 자리에서 다시 셉니다.")
        self.assertTrue(has(run(scenes, comp), "s6", "끝 멘트 고정문이 마지막 문장이 아님"), run(scenes, comp))

    def test_after_market_window(self):
        scenes, comp = dated("20260916", SIG21)                       # 9/18 까지는 있어야 한다
        self.assertTrue(has(run(scenes, comp), "s6", "애프터마켓 문장 없음"), run(scenes, comp))
        scenes, comp = dated("20260918", SIG16)
        self.assertEqual(run(scenes, comp), [], run(scenes, comp))
        scenes, comp = dated("20260921", SIG16)                       # 9/21 부터는 빠져야 한다
        self.assertIn(f"[s6] 애프터마켓 문장은 9/18까지만 :: {AFTER}", run(scenes, comp))
        scenes, comp = dated("20260921", SIG21)
        self.assertEqual(run(scenes, comp), [], run(scenes, comp))


class Length(unittest.TestCase):
    def test_too_long_fails_with_longest_sentence(self):
        filler = "돈의 방향을 다시 짚어 보면 반도체에서 빠진 돈이 이차전지와 로봇으로 일부만 옮겨 갔다는 사실이 남는다는 뜻입니다."
        scenes = edit("s5", filler + " " + GOOD[7]["tts"] + " " + filler.replace("돈의", "값의"))
        self.assertGreater(total(scenes), qa.BRIEF_TOTAL_MAX)
        warn: list[str] = []
        bad = run(scenes, warn=warn)
        hit = [b for b in bad if b.startswith("[all]")]
        self.assertEqual(len(hit), 1, bad)
        self.assertIn(f"총 {total(scenes):,}자 > {qa.BRIEF_TOTAL_MAX:,}자", hit[0])
        self.assertTrue(hit[0].endswith(" :: " + filler), hit)     # 가장 긴 문장을 실어 재시도가 그 후보를 바꾼다
        self.assertEqual(warn, [])

    def test_short_is_warning_not_failure(self):
        scenes = short_scenes()
        self.assertLess(total(scenes), qa.BRIEF_TOTAL_MIN, total(scenes))
        warn: list[str] = []
        bad = run(scenes, warn=warn)
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertEqual(len(warn), 1, warn)
        self.assertIn(f"경고: 총 {total(scenes):,}자 < {qa.BRIEF_TOTAL_MIN}자", warn[0])

    def test_short_warning_goes_to_stderr_without_list(self):
        """warn 목록을 안 주면(compute 처럼) 경고는 stderr 로 가고 실패 목록에는 안 들어간다."""
        import io
        from contextlib import redirect_stderr
        scenes = short_scenes()
        buf = io.StringIO()
        with redirect_stderr(buf):
            bad = run(scenes)
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertIn("[qa] [all] 경고: 총", buf.getvalue())


class Overlap(unittest.TestCase):
    def test_exact_overlap_from_previous_edition(self):
        recs = [{"kind": "kr", "date": "20260914", "folder": "20260914", "draft": False,
                 "scenes": [{"id": "s5", "tts": "이차전지는 돈 쪽, 로봇은 뉴스 쪽입니다. 누가샀나였습니다."}]}]
        bad = run(recs=recs)
        hit = [b for b in bad if "글자 그대로 겹침" in b]
        self.assertEqual(len(hit), 1, bad)
        self.assertTrue(hit[0].startswith("[s5]") and hit[0].endswith(" :: 이차전지는 돈 쪽, 로봇은 뉴스 쪽입니다."), hit)


class CheckScript(unittest.TestCase):
    def test_check_script_routes_brief(self):
        doc = {"date": D, "format": "brief", "scenes": copy.deepcopy(GOOD), "hunter": COMP["hunter"]}
        try:
            bad = qa.check_script("day", D, doc=doc)
        except Exception as e:                       # tts/edge_tts 등 환경 의존 — 없으면 건너뛴다
            self.skipTest(f"환경 의존 모듈 없음: {e}")
        self.assertFalse(any("장면 없음" in b for b in bad), bad)
        self.assertFalse(any("질문이" in b for b in bad), bad)
        self.assertFalse(any("길이" in b for b in bad), bad)
        # 브리핑 고정 내용 검사가 실제로 붙는다
        doc["scenes"] = edit("s3b", "반도체가 정체된 자리입니다. 왼쪽 막대를 보세요. 그럼 그 돈은 어디로 들어갔을까요.")
        bad = qa.check_script("day", D, doc=doc)
        self.assertTrue(has(bad, "s3b", "빠진 돈 표현 없음"), bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
