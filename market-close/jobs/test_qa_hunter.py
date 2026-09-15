"""qa_script.check_hunter 자체 검사 — 순수 파이썬(unittest), 데이터 폴더를 읽지 않는다(recs 를 직접 넣는다).

실행(market-close/jobs 에서):  python test_qa_hunter.py
통과 대본은 정본 docs/SCRIPT_SYSTEM_HUNTER_v1.0.md §7(2026-09-14 예시)을 습니다체·우리 시그니처로 옮긴 것.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_script as qa  # noqa: E402
import ledger  # noqa: E402
import script_memory as sm  # noqa: E402

D = "20260916"
SIG = "정규장이 끝나도 저녁 8시까지 애프터마켓에서 거래됩니다. 누가샀나였습니다. 국장 마감은 매일 저녁 5시에 올라옵니다."

GOOD = [
    {"id": "s0", "tts": "오늘 오후 2시까지 외국인이 판 건 5,100억이었습니다. 장 마감 한 시간 반 동안 2조 8천억을 더 팔았습니다. 다섯 배 넘는 물량입니다."},
    {"id": "s1", "tts": "이 물량을 누가 받았느냐. 오늘은 이것 하나만 봅니다."},
    {"id": "s2", "tts": "개인이 받았다고 생각하기 쉽습니다. 개인 2조 9,700억. 맞습니다. 그런데 막대가 하나 더 있습니다. 오른쪽 끝을 보세요. "
                        "기타법인 1조 4,800억. 이 돈은 밖에서 새로 들어온 돈이 아닙니다."},
    {"id": "s3a", "tts": "삼성전자와 SK하이닉스가 자기 주식을 산 겁니다. 삼성전자 15조, 하이닉스 40조. 둘 다 8월에 시작해 11월까지입니다. "
                         "그런데 이건 시장의 돈이 아니라 회사가 미리 정해둔 예산입니다. 예산에는 바닥이 있습니다."},
    {"id": "s3b", "tts": "그럼 파는 쪽은 어떨까요. 왼쪽부터 보세요. 외국인은 9일부터 4거래일 연속 팔았습니다. 오늘 빠진 건 전기·전자 한 업종, 3.93%입니다. "
                         "그런데 여기엔 기한이 없습니다."},
    {"id": "s3c", "tts": "받는 쪽 기한은 얼마나 남았을까요. 여기 진행률입니다. 삼성전자는 11일까지 예정 물량의 55.9%를 썼습니다. "
                         "15거래일 만에 절반 넘게 쓴 셈입니다. 그럼 남은 건 며칠치일까요."},
    {"id": "s4", "tts": "공시 원문을 직접 열어봤습니다. 여기 이 칸, 취득 예정 5,328만 주. 그중 2,980만 주가 11일까지 나갔습니다. 남은 건 2,348만 주. "
                        "하루 평균 199만 주씩 사고 있으니, 12거래일치입니다."},
    {"id": "s5", "tts": "정리합니다. 오늘은 파는 쪽이 멈춰서 덜 빠진 게 아니라, 받는 쪽이 버텨서 덜 빠진 날입니다. "
                        "외국인과 기관이 던진 4조 4,700억을 받아낸 돈의 3분의 1이 이 예산이었습니다. 외국인이 먼저 멈추면, 예산이 남은 동안 바닥이 다져집니다. "
                        "예산이 먼저 바닥나면, 오늘 같은 방어는 없습니다. 지금 시간표는 뒤쪽이 빠릅니다. 예산은 12거래일, 외국인은 기한이 없습니다. "
                        "오늘은 받는 쪽입니다. 이 판정이 뒤집히는 조건은 하나, 외국인이 내일 순매수로 돌아서는 겁니다."},
    {"id": "s6", "tts": "내일은 두 숫자만 봅니다. 외국인 순매도가 5거래일째 이어지는지. 기타법인 순매수가 1조 5천억을 지키는지. "
                        "9월 들어 3일 하루 빼고 매일 지켜온 선입니다. 목요일 새벽 3시 미국 금리 결정 전까지, 이 둘입니다. " + SIG},
]
COMP = {"date": D, "format": "hunter",
        "hunter": {"s4": {"doc": "DART 자기주식 취득 결정 공시 · KRX 일별 취득 집계 9/11",
                          "calc": {"expr": "2,348만 ÷ 199만", "result": "12거래일치", "lhs": 2348, "rhs": 199, "value": 11.8, "kind": "days"}}}}


def run(scenes=None, comp=None, recs=None):
    return qa.check_hunter(scenes if scenes is not None else GOOD, comp if comp is not None else COMP, recs=[] if recs is None else recs)


def edit(sid: str, tts: str) -> list[dict]:
    out = copy.deepcopy(GOOD)
    for s in out:
        if s["id"] == sid:
            s["tts"] = tts
    return out


def has(bad: list[str], scene: str, frag: str) -> bool:
    return any(b.startswith(f"[{scene}]") and frag in b for b in bad)


class Tokens(unittest.TestCase):
    def test_numeric_tokens(self):
        n = lambda s: len(qa.num_tokens(s))
        self.assertEqual(n("2조 8천억을 더 팔았습니다"), 1)
        self.assertEqual(n("기타법인 1조 4,800억"), 1)
        self.assertEqual(n("돈의 3분의 1이 예산"), 1)
        self.assertEqual(n("9월 17일 목요일 새벽 3시"), 2)
        self.assertEqual(n("다섯 배 넘는 물량"), 1)
        self.assertEqual(n("외국인이 닷새째, 오늘만 1.6조를 팔았습니다"), 2)
        self.assertEqual(n("하루 평균 199만 주씩"), 1)          # '하루 평균'은 단위, 숫자가 아니다
        self.assertEqual(n("코스피는 0.85%밖에 안 내렸습니다"), 1)
        self.assertEqual(n("백분율로 보면"), 0)
        self.assertEqual(n("한 업종, 3.93%입니다"), 2)
        self.assertEqual(n("이 판정이 뒤집히는 조건은 하나"), 0)
        self.assertEqual(n("정규장 체결 기준 15시 30분입니다"), 1)     # 시각은 숫자 하나
        self.assertEqual(n("키움 943종목 합산표, 정규장 체결 기준 15:30"), 2)
        # B8: hwon 100억 정밀도 — '조+억' 한 덩어리는 숫자 1개
        for s in ("1조 5,700억", "기타법인 1조 6,400억을 샀습니다", "2조 400억", "3조 3,000억이었습니다", "8,300억", "1.6조"):
            self.assertEqual(n(s), 1, s)
        self.assertEqual(n("외국인 몫 1조 5,700억, 기타법인 1조 6,400억"), 2)
        self.assertEqual(n("2조 400억 ÷ 937억 = 22배"), 3)

    def test_block_end_ignores_trailing_screen_pointer(self):
        ok = edit("s3a", "어제 보자고 한 외국인 순매도, 닷새째 이어졌습니다. 그런데 받은 쪽이 바뀌었습니다. "
                         "어제는 개인 2조 9,700억, 오늘은 기타법인 1조 6,400억입니다. 왼쪽 막대와 오른쪽 막대를 보세요.")
        self.assertFalse(any("블록 끝이" in b for b in run(ok)), run(ok))
        bad = edit("s3a", "어제 보자고 한 외국인 순매도, 닷새째 이어졌습니다. 그런데 받은 쪽이 바뀌었습니다. "
                          "어제는 개인 2조 9,700억이었습니다. 오늘은 기타법인 1조 6,400억입니다. 왼쪽 막대를 보세요.")
        self.assertTrue(has(run(bad), "s3a", "블록 끝이"), run(bad))

    def test_questions(self):
        self.assertTrue(qa.is_question("그럼 남은 건 며칠치일까요."))
        self.assertTrue(qa.is_question("누가 받았을까요?"))
        self.assertFalse(qa.is_question("외국인 순매도가 엿새째 이어지는지 봅니다."))
        self.assertTrue(qa.has_question("외국인 순매도가 엿새째 이어지는지 봅니다."))
        self.assertTrue(qa.has_question("이 돈이 어디로 갔느냐가 오늘의 전부입니다."))
        self.assertFalse(qa.has_question("오늘은 받는 쪽입니다."))

    def test_verify_calc(self):
        ok = lambda c, t: qa.verify_calc(c, t)
        self.assertEqual(ok({"expr": "38,339 ÷ 1,313", "result": "29배", "lhs": 38339, "rhs": 1313, "value": 29.2, "kind": "ratio"}, "나간 돈이 들어온 돈의 29배입니다."), [])
        self.assertEqual(ok({"result": "3분의 1", "lhs": 14868, "rhs": 44589, "kind": "share"}, "받아낸 돈의 3분의 1이 예산이었습니다."), [])
        self.assertEqual(ok({"result": "2조 8천억", "lhs": 33000, "rhs": 5100, "kind": "diff"}, "마감까지 2조 8천억을 더 팔았습니다."), [])
        self.assertEqual(ok({"result": "33.3%", "lhs": 14868, "rhs": 44589}, "예산이 33.3%였습니다."), [])
        bad = ok({"expr": "2,348 ÷ 199", "result": "20거래일치", "lhs": 2348, "rhs": 199, "kind": "days"}, "20거래일치입니다.")
        self.assertTrue(any("검산 실패" in b for b in bad), bad)
        bad = ok({"result": "12거래일치", "lhs": 2348, "rhs": 199, "value": 30, "kind": "days"}, "12거래일치입니다.")
        self.assertTrue(any("calc.value" in b for b in bad), bad)
        bad = ok({"result": "12거래일치", "lhs": 2348, "rhs": 199, "kind": "days"}, "열이틀치입니다.")
        self.assertTrue(any("대사에 없음" in b for b in bad), bad)


class Passing(unittest.TestCase):
    def test_bible_example_passes(self):
        bad = run()
        self.assertEqual(bad, [], "\n".join(bad))

    def test_fail_format(self):
        for b in run(edit("s2", "개인이 받았습니다. 끝.")):
            self.assertIn(" :: ", b)
            self.assertTrue(b.startswith("["), b)


class Failing(unittest.TestCase):
    def test_missing_block(self):
        bad = run([s for s in GOOD if s["id"] != "s3c"])
        self.assertTrue(has(bad, "s3c", "장면 없음"), bad)

    def test_fourth_block(self):
        bad = run(GOOD + [{"id": "s3d", "tts": "코스닥도 봅니다. 그런데 여기도 빠졌습니다."}])
        self.assertTrue(has(bad, "s3d", "4개 이상"), bad)

    def test_s0_greeting_and_no_numbers(self):
        bad = run(edit("s0", "안녕하세요, 누가샀나입니다. 오늘 시장은 조용했습니다."))
        self.assertTrue(has(bad, "s0", "숫자 0개"), bad)
        self.assertTrue(has(bad, "s0", "도입부 금지어"), bad)

    def test_s1_two_questions_and_no_frame(self):
        bad = run(edit("s1", "누가 받았을까요? 얼마나 받았을까요? 오늘은 이것 하나만 봅니다."))
        self.assertTrue(has(bad, "s1", "질문 2개"), bad)
        bad = run(edit("s1", "이 물량을 누가 받았느냐. 오늘은 이것을 봅니다."))
        self.assertTrue(has(bad, "s1", "질문 선언 틀 없음"), bad)

    def test_s2_missing_naive_or_turn(self):
        bad = run(edit("s2", "개인이 받았습니다. 개인 2조 9,700억. 막대가 하나 더 있습니다. 오른쪽 끝을 보세요."))
        self.assertTrue(has(bad, "s2", "대변 틀 없음"), bad)
        self.assertTrue(has(bad, "s2", "그런데 없음"), bad)

    def test_s3_ending_and_double_turn(self):
        bad = run(edit("s3a", "삼성전자와 SK하이닉스가 자기 주식을 산 겁니다. 삼성전자 15조, 하이닉스 40조. 둘 다 11월까지입니다."))
        self.assertTrue(has(bad, "s3a", "블록 끝이"), bad)
        bad = run(edit("s3b", "그럼 파는 쪽은 어떨까요. 왼쪽부터 보세요. 그런데 외국인은 4거래일 연속 팔았습니다. 그런데 여기엔 기한이 없습니다."))
        self.assertTrue(has(bad, "s3b", "그런데 2회"), bad)
        self.assertTrue(has(bad, "s3b", "그런데 연속 2문장"), bad)

    def test_s4_open_and_calc(self):
        bad = run(edit("s4", "공시를 보면 취득 예정 5,328만 주입니다. 그중 2,980만 주가 나갔습니다. 남은 건 2,348만 주입니다."))
        self.assertTrue(has(bad, "s4", "1차 자료 열람 문장 없음"), bad)
        self.assertTrue(has(bad, "s4", "계산식 없음"), bad)
        comp = copy.deepcopy(COMP)
        comp["hunter"]["s4"]["calc"] = {"expr": "2,348만 ÷ 199만", "result": "20거래일치", "lhs": 2348, "rhs": 199, "value": 20, "kind": "days"}
        bad = run(edit("s4", GOOD[6]["tts"].replace("12거래일치", "20거래일치")), comp)
        self.assertTrue(has(bad, "s4", "계산 검산 실패"), bad)
        self.assertIn("20거래일치", [b.split(" :: ")[1] for b in bad if "검산" in b][0])

    def test_s5_verdict_condition_question(self):
        bad = run(edit("s5", "정리합니다. 외국인이 먼저 멈추면 바닥이 다져집니다. 예산이 먼저 바닥나면 방어는 없습니다. 어느 쪽일까요?"))
        self.assertTrue(has(bad, "s5", "판정 문장 없음"), bad)
        self.assertTrue(has(bad, "s5", "뒤집히는 조건 없음"), bad)
        self.assertTrue(has(bad, "s5", "질문으로 끝남"), bad)

    def test_s6_threshold_and_last_question(self):
        bad = run(edit("s6", "내일은 외국인이 어떻게 하는지 지켜보겠습니다. " + SIG))
        self.assertTrue(has(bad, "s6", "임계값 숫자 없음"), bad)
        bad = run(edit("s6", "내일은 외국인 순매도가 6거래일째 이어지는지 봅니다. 답은 어디에 있을까요? " + SIG))
        self.assertTrue(has(bad, "s6", "마지막 문장이 질문"), bad)

    def test_banned_words_and_reco(self):
        bad = run(edit("s5", GOOD[7]["tts"] + " 여러분, 지난 영상에서 본 대로 삼성전자 비중을 늘리고 사세요."))
        self.assertTrue(has(bad, "s5", "금지어(여러분, 지난 영상)"), bad)
        self.assertTrue(has(bad, "s5", "종목 추천 표현(비중, 사세요)"), bad)
        self.assertEqual(sum("비중" in b.split(" :: ")[0] for b in bad), 1, bad)   # checks/forbidden 과 이중 보고하지 않는다
        # '사라졌습니다' 는 추천 표현이 아니다
        bad = run(edit("s3a", "삼성전자와 SK하이닉스가 자기 주식을 산 겁니다. 이 돈은 밖에서 사라졌습니다. 그런데 이건 회사가 미리 정해둔 예산입니다."))
        self.assertFalse(any("종목 추천 표현" in b for b in bad), bad)

    def test_three_numbers_in_one_sentence(self):
        bad = run(edit("s3a", "삼성전자 15조, 하이닉스 40조, 합쳐 55조입니다. 그런데 이건 회사가 미리 정해둔 예산입니다."))
        self.assertTrue(has(bad, "s3a", "숫자 3개"), bad)

    def test_screen_directions(self):
        scenes = edit("s2", "개인이 받았다고 생각하기 쉽습니다. 개인 2조 9,700억. 그런데 기타법인 1조 4,800억이 더 있습니다.")
        for s in scenes:
            if s["id"] == "s3b":
                s["tts"] = "그럼 파는 쪽은 어떨까요. 외국인은 9일부터 4거래일 연속 팔았습니다. 그런데 여기엔 기한이 없습니다."
        bad = run(scenes)
        self.assertTrue(has(bad, "s2-s4", "화면 지시어"), bad)

    def test_overlap_exact_only_and_signature_ignored(self):
        recs = [{"kind": "kr", "date": "20260914", "folder": "20260914", "draft": False,
                 "scenes": [{"id": "s2", "tts": "이 돈은 밖에서 새로 들어온 돈이 아닙니다. 누가샀나였습니다."},
                            {"id": "s5", "tts": "외국인과 기관이 던진 3조 9,700억을 받아낸 돈의 3분의 1이 이 예산이었습니다."}]}]
        bad = run(recs=recs)
        hit = [b for b in bad if "글자 그대로 겹침" in b]
        self.assertEqual(len(hit), 1, bad)
        self.assertTrue(hit[0].startswith("[s2]"), hit)
        self.assertTrue(hit[0].endswith(" :: 이 돈은 밖에서 새로 들어온 돈이 아닙니다."), hit)
        self.assertFalse(any("누가샀나였습니다" in b for b in bad), bad)      # 시그니처는 겹쳐도 된다

    def test_overlap_window_aired_and_ledger_exempt(self):
        """B2: 올라간 편 가운데 최근 5편만 보고, 초안(_v8)은 안 보며, 장부 문장(…이어지는지/…을 지키는지)은 예외."""
        mk = lambda dt, folder, sid, tts, aired=None: {"kind": "kr", "date": dt, "folder": folder, "draft": "_" in folder, "aired": aired,
                                                       "scenes": [{"id": sid, "tts": tts}], "facts": {}}
        recs = [mk("20260901", "20260901", "s2", "개인이 받았다고 생각하기 쉽습니다."),                       # 6편 전 — 창 밖
                mk("20260911", "20260911_v8", "s2", "개인 2조 9,700억."),                                    # 안 올라간 초안
                mk("20260909", "20260909", "s6", "외국인 순매도가 5거래일째 이어지는지. 기타법인 순매수가 1조 5천억을 지키는지.", {"youtube_id": "a"}),
                mk("20260910", "20260910", "s2", "x"), mk("20260911", "20260911", "s2", "x"), mk("20260914", "20260914", "s2", "x"),
                mk("20260915", "20260915", "s5", "예산이 먼저 바닥나면, 오늘 같은 방어는 없습니다.", {"youtube_id": "b"})]
        bad = run(recs=recs)
        hit = [b for b in bad if "글자 그대로 겹침" in b]
        self.assertEqual(len(hit), 1, bad)
        self.assertTrue(hit[0].startswith("[s5]") and hit[0].endswith(" :: 예산이 먼저 바닥나면, 오늘 같은 방어는 없습니다."), hit)
        # 같은 recs 를 창 없이 보면(CLI 기본) 6편 전 문장도 잡힌다 — 창이 실제로 좁힌 것
        ov = sm.overlaps(D, GOOD, recs)
        self.assertIn("개인이 받았다고 생각하기 쉽습니다.", [o["sentence"] for o in ov if o["kind"] == "exact"], ov)
        self.assertIn("외국인 순매도가 5거래일째 이어지는지.", [o["sentence"] for o in ov if o["kind"] == "exact"], ov)

    def test_screen_direction_fail_carries_s4_sentence(self):
        """B3: 화면 지시어 부족 실패는 지시어 없는 S4 문장(숫자 있는 칸 문장)을 ' :: ' 뒤에 싣는다 — compute 가 avoid 에 넣을 수 있게."""
        scenes = edit("s2", "개인이 받았다고 생각하기 쉽습니다. 개인 2조 9,700억. 그런데 기타법인 1조 4,800억이 더 있습니다.")
        for s in scenes:
            if s["id"] == "s3b":
                s["tts"] = "그럼 파는 쪽은 어떨까요. 외국인은 9일부터 4거래일 연속 팔았습니다. 그런데 여기엔 기한이 없습니다."
            if s["id"] == "s4":
                s["tts"] = "공시 원문을 직접 열어봤습니다. 취득 예정 5,328만 주입니다. 그중 2,980만 주가 11일까지 나갔습니다. 하루 평균 199만 주씩 사고 있으니, 12거래일치입니다."
        bad = run(scenes)
        hit = [b for b in bad if b.startswith("[s2-s4]")]
        self.assertEqual(len(hit), 1, bad)
        self.assertTrue(hit[0].endswith(" :: 취득 예정 5,328만 주입니다."), hit)


class Ledger(unittest.TestCase):
    def test_parse_q_days_eight_plus(self):
        """B4: 헌터 next_q(여드레째·아흐레째·열흘째·11일째)가 장부에서 n 을 잃지 않는다."""
        for q, n in (("외국인 순매도가 여드레째 이어지는지", 8), ("외국인 순매도가 아흐레째 이어지는지", 9), ("기타법인 순매수가 열흘째 이어지는지", 10),
                     ("외국인 순매도가 11일째 이어지는지", 11), ("외국인 순매도가 12거래일째 이어지는지", 12), ("외국인 순매도가 닷새째 이어지는지", 5)):
            chk = ledger.parse_q(q)
            self.assertIsNotNone(chk, q)
            self.assertEqual(chk["kind"], "inv_continue", q)
            self.assertEqual(chk["n"], n, q)
        self.assertEqual(ledger.parse_q("외국인 순매도가 이어지는지")["n"], None)
        self.assertEqual(ledger.parse_q("이차전지 순매수가 여드레째 이어지는지"), {"kind": "theme_continue", "theme": "이차전지", "n": 8})
        self.assertEqual(ledger.days_n("11일째"), 11)
        self.assertEqual(ledger.days_n("여드레째"), 8)
        self.assertIsNone(ledger.days_n("같은 부호"))
        try:
            import narrate_hunter as nh
        except Exception as e:                                # 환경 의존(키움 모듈 등) — 없으면 dko 왕복은 건너뛴다
            self.skipTest(f"narrate_hunter 못 불러옴: {e}")
        for n in range(2, 16):
            q = f"외국인 순매도가 {nh.dko(n)} 이어지는지"
            self.assertEqual(ledger.parse_q(q)["n"], n, q)
            self.assertEqual(sm.q_family(q), "inv_continue:foreign:-1", q)


class Memory(unittest.TestCase):
    def test_pick_sentence_level(self):
        """B1: 후보의 한 문장만 exact/masked/avoid 에 있어도 그 후보는 겹친 것."""
        two = "그런데 막대 밑을 보세요. 이름이 둘 붙습니다."
        self.assertEqual(sm.pick([two, "C 문장입니다 셋"], D, {}, {}, avoid={"이름이 둘 붙습니다."}), "C 문장입니다 셋")
        self.assertEqual(sm.pick([two, "C 문장입니다 셋"], D, {sm.norm("이름이 둘 붙습니다"): ["x"]}, {}), "C 문장입니다 셋")
        two_n = "그런데 막대 밑을 보세요. 기타법인 1조 6천억을 샀습니다."
        self.assertEqual(sm.pick([two_n, "C 문장입니다 셋"], D, {}, {sm.mask("기타법인 9천억을 샀습니다"): ["x"]}), "C 문장입니다 셋")
        self.assertEqual(sm.pick([two], D, {sm.norm("이름이 둘 붙습니다"): ["x"]}, {}), two)          # 다 겹치면 그래도 하나
        self.assertEqual(sm.pick([two], D, {}, {}, avoid={"이름이 둘 붙습니다."}), "")                # avoid 로 다 빠지면 빈 문자열
        a, b = "A 문장입니다 하나", "B 문장입니다 둘"
        self.assertNotEqual(sm.pick([a, b], D, {}, {}, offset=0), sm.pick([a, b], D, {}, {}, offset=1))

    def test_continuity_capped(self):
        """B6: 기타법인 연속이 이력 첫 편(또는 수급 없는 편)까지 닿으면 capped, 부호가 끊기면 아니다."""
        def fake(dates_others):
            return [{"kind": "kr", "date": dt, "folder": dt, "draft": False, "aired": None, "scenes": [{"id": "s0", "tts": ""}],
                     "facts": {"others": v, "watch_family": []}} for dt, v in dates_others]
        orig = sm.editions
        try:
            sm.editions = lambda before=None, kinds=("kr",): [r for r in fake([("20260903", None), ("20260904", 100), ("20260905", 200)])
                                                              if not before or r["date"] < before]
            c = sm.continuity("20260908", {"others": 300})
            self.assertEqual((c["others_buy_days"], c["others_buy_days_capped"], c["history_first_date"], c["others_first_date"]),
                             (3, True, "20260903", "20260904"))
            sm.editions = lambda before=None, kinds=("kr",): [r for r in fake([("20260903", -50), ("20260904", 100), ("20260905", 200)])
                                                              if not before or r["date"] < before]
            c = sm.continuity("20260908", {"others": 300})
            self.assertEqual((c["others_buy_days"], c["others_buy_days_capped"]), (3, False))
            sm.editions = lambda before=None, kinds=("kr",): []
            c = sm.continuity("20260908", {"others": 300})
            self.assertEqual((c["others_buy_days"], c["others_buy_days_capped"], c["history_first_date"]), (1, True, None))
            c = sm.continuity("20260908", {"others": -300})
            self.assertEqual((c["others_buy_days"], c["others_buy_days_capped"]), (0, False))
        finally:
            sm.editions = orig


class CheckScript(unittest.TestCase):
    def test_check_script_tolerates_nine_scenes(self):
        doc = {"date": D, "format": "hunter", "scenes": copy.deepcopy(GOOD), "hunter": COMP["hunter"]}
        try:
            bad = qa.check_script("day", D, doc=doc)
        except Exception as e:                       # tts/edge_tts 등 환경 의존 — 없으면 건너뛴다
            self.skipTest(f"환경 의존 모듈 없음: {e}")
        self.assertFalse(any("장면 없음" in b for b in bad), bad)
        self.assertFalse(any("질문이" in b for b in bad), bad)
        self.assertFalse(any("길이" in b for b in bad), bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
