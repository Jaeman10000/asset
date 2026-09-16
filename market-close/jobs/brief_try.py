"""수급 브리핑 대본 시험 — 지난 날짜의 데이터로 narrate_brief.build 를 돌려 대본·화면 사전·전 편 겹침·검사 결과를 본다(hunter_try.py 와 같은 길).
data/ 와 out/ 은 건드리지 않는다. raw/brief_stocks.json 이 없으면 collect_brief 를 **스크래치 출력으로** 그 자리에서 돌린다(data/ 에는 쓰지 않는다).

실행(market-close/jobs 에서):
  python brief_try.py 20260915                       대본([id] tts) + hunter JSON + overlaps + 검사 + 자수, 스크래치 brief/DATE/ 에 저장
  python brief_try.py 20260911 20260914 20260915 --cross   여러 날을 제작 순서대로 잇고(앞 날 결과 = 뒷날의 전 편 이력) 서로 겹친 문장까지 본다
  python brief_try.py 20260915 --attempt 1           회전 오프셋(compute 재시도 k회차와 같은 길)
  python brief_try.py 20260915 --avoid "문장"         검사에 걸린 문장을 피해 다시 만들기
  python brief_try.py --selftest                     §2 대체 규칙을 가짜 입력으로 검사(유입 없음 / 이슈 없음 / 코스닥 없음 / 콜백 없음 / brief_stocks 없음 / 16시 이후 스냅)
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, load_json  # noqa: E402

SCRATCH = Path(r"C:/Users/Jeff/AppData/Local/Temp/claude/C--Users-Jeff-Documents-GitHub-asset/ed61fea3-c63d-4ffd-8a2a-78666bf42e10/scratchpad/brief")
CPS = 8.0


def _qa_check(scenes: list[dict], comp: dict, recs=None) -> list[str]:
    import narrate_brief
    try:
        import qa_script
        if hasattr(qa_script, "check_brief"):
            return qa_script.check_brief(scenes, comp) if recs is None else qa_script.check_brief(scenes, comp, recs)
    except Exception as e:  # noqa: BLE001
        return [f"(qa_script 실패 {e!r})"]
    return narrate_brief.check_brief(scenes, comp, recs)


def inputs_for(d: str, out_dir: Path | None = None) -> tuple[dict, dict]:
    """(c, computed_kr.json) — compute.compute() 가 narrate 에 넘기는 입력을 저장된 파일에서 되살린다. brief_stocks 가 없으면 스크래치로 수집."""
    import compute
    c0 = load_json(DATA / d / "computed_kr.json")
    if not c0:
        raise SystemExit(f"{d}: computed_kr.json 없음")
    raw = DATA / d / "raw"
    fl = load_json(raw / "flows.json") or {}
    invs = c0.get("investors") or {}
    inv = invs.get("kospi") or {}
    if not inv:
        raise SystemExit(f"{d}: 수급 없음(investors.kospi)")
    N = {"brand": c0.get("brand") or "누가샀나"}
    c = compute.narration_inputs(d, N, inv, raw=raw, fl=fl, kospi=c0.get("kospi") or {}, kosdaq=c0.get("kosdaq") or {},
                                 inv_q=invs.get("kosdaq"), inv_src=invs.get("src"), inv_streak=c0.get("inv_streak") or {},
                                 intraday=c0.get("intraday"), moves=c0.get("moves") or [], event=c0.get("event"),
                                 callback=c0.get("callback"), stocks=c0.get("stocks") or [], schedule=c0.get("schedule") or [])
    if not (c.get("brief_stocks") or {}).get("stocks"):
        sp = (out_dir or SCRATCH) / d / "brief_stocks.json"
        bs = load_json(sp) if sp.exists() else None
        if not bs:
            import collect_brief
            sp.parent.mkdir(parents=True, exist_ok=True)
            bs = asyncio.run(collect_brief.main(d, out_path=sp))
        c["brief_stocks"] = bs or {}
    return c, c0


def run(d: str, avoid: set[str] | None = None, out_dir: Path | None = None, quiet: bool = False, attempt: int = 0) -> dict:
    import narrate_brief
    import script_memory as sm
    c, c0 = inputs_for(d, out_dir)
    out = narrate_brief.build(c, avoid or None, attempt=attempt)
    scenes = out["scenes"]
    lines = [f"[{sc['id']}] {sc['tts']}" for sc in scenes]
    script = "\n".join(lines)
    chars = sum(len(sc["tts"]) for sc in scenes)
    ov = sm.overlaps(d, scenes)
    lint = narrate_brief.lint(scenes)
    qa = _qa_check(scenes, {**c0, **out, "date": d})
    if not quiet:
        print(f"===== {d}  훅 {out['hook_id']} · 장치 {out['devices']} · 다음 {out['next_q']} · attempt {attempt}")
        print(script)
        per = " · ".join(f"{sc['id']} {len(sc['tts'])}" for sc in scenes)
        print(f"-- {chars}자(공백 포함, 장면 사이 제외) ≈ {chars / CPS:.0f}초 (자/8.0) · 슬롯별 {per}")
        print("-- overlaps(전 편과 겹침):", "없음" if not ov else "")
        for o in ov:
            print(f"   [{o['kind']}] ({o['scene']}) {o['sentence']}  ← {', '.join(o['seen'][:3])}")
        print("-- lint(자체):", "없음" if not lint else "")
        for w in lint:
            print("   ", w)
        print("-- 검사(check_brief):", "통과" if not qa else f"{len(qa)}건")
        for f in qa:
            print("   ✗", f)
        print("-- hunter JSON:")
        print(json.dumps(out["hunter"], ensure_ascii=False, indent=1))
    od = (out_dir or SCRATCH) / d
    od.mkdir(parents=True, exist_ok=True)
    (od / "script.txt").write_text(script + "\n", encoding="utf-8")
    (od / "hunter.json").write_text(json.dumps(out["hunter"], ensure_ascii=False, indent=1), encoding="utf-8")
    like = {k: v for k, v in c0.items() if k not in ("voice", "total_frames", "total_sec", "fps", "script_edit")}
    like.update({k: v for k, v in out.items()})
    like["scenes"] = [{k: v for k, v in sc.items() if k not in ("audio", "audio_parts", "audio_sec", "sec", "start", "frames", "bounds", "cues")} for sc in scenes]
    like["investors"] = {**(c0.get("investors") or {}), "bars": out["bars"], "title": out["s2_title"]}
    like["watch"] = out["watch"]
    like["visual"] = "v4"
    (od / "computed_like.json").write_text(json.dumps(like, ensure_ascii=False, indent=1), encoding="utf-8")
    if not quiet:
        print(f"-- 저장: {od / 'script.txt'} · hunter.json · computed_like.json")
    return {"date": d, "out": out, "script": script, "chars": chars, "overlaps": ov, "lint": lint, "qa": qa}


def cross(results: list[dict]) -> list[str]:
    """여러 날 대본이 서로 글자 그대로 겹친 문장(시그니처 제외)."""
    import script_memory as sm
    seen: dict[str, list[str]] = {}
    for r in results:
        for sc in r["out"]["scenes"]:
            for s in sm.sentences(sc["tts"]):
                if sm.is_signature(s) or len(sm.norm(s)) < 8:
                    continue
                seen.setdefault(sm.norm(s), []).append(f"{r['date']}/{sc['id']}: {s}")
    return [" == ".join(v) for v in seen.values() if len({x.split('/')[0] for x in v}) >= 2]


# ── §2 대체 규칙 자체 검사(가짜 입력, data/ 는 읽기만) ──
def _synthetic() -> dict:
    stocks_in = [{"code": "373220", "name": "LG에너지솔루션", "theme": "이차전지", "foreign": 8, "inst": 413, "value": 1215, "ret": 3.98, "close": 400000},
                 {"code": "006400", "name": "삼성SDI", "theme": "이차전지", "foreign": 353, "inst": -24, "value": 2181, "ret": 2.82, "close": 547000},
                 {"code": "247540", "name": "에코프로비엠", "theme": "이차전지", "foreign": 43, "inst": 28, "value": 243, "ret": 2.98, "close": 106400},
                 {"code": "003670", "name": "포스코퓨처엠", "theme": "이차전지", "foreign": 36, "inst": 158, "value": 763, "ret": 5.59, "close": 188900},
                 {"code": "277810", "name": "레인보우로보틱스", "theme": "로봇", "foreign": 83, "inst": 32, "value": 343, "ret": 2.97, "close": 433000},
                 {"code": "058610", "name": "에스피지", "theme": "로봇", "foreign": 168, "inst": 51, "value": 1567, "ret": 13.89, "close": 103300},
                 {"code": "005930", "name": "삼성전자", "theme": "반도체", "foreign": -2911, "inst": -5595, "value": 41333, "ret": -0.2, "close": 248500},
                 {"code": "000660", "name": "SK하이닉스", "theme": "반도체", "foreign": -10024, "inst": -1558, "value": 65060, "ret": -0.47, "close": 1689000},
                 {"code": "009540", "name": "HD한국조선해양", "theme": "조선", "foreign": -400, "inst": -500, "value": 3000, "ret": -5.0, "close": 300000},
                 {"code": "034020", "name": "두산에너빌리티", "theme": "원전/에너지", "foreign": -500, "inst": -236, "value": 4000, "ret": -3.0, "close": 60000}]
    table = {"이차전지": {"net": 937, "foreign": 479, "inst": 458, "ret": 3.1, "pos_names": ["LG에너지솔루션", "삼성SDI", "포스코퓨처엠", "에코프로비엠"]},
             "로봇": {"net": 376, "foreign": 260, "inst": 115, "ret": 5.07, "pos_names": ["에스피지", "레인보우로보틱스"]},
             "반도체": {"net": -20429, "foreign": -13373, "inst": -7056, "ret": -0.24, "pos_names": []},
             "조선": {"net": -1258, "foreign": -610, "inst": -647, "ret": -5.35, "pos_names": []},
             "원전/에너지": {"net": -736, "foreign": -500, "inst": -236, "ret": -3.0, "pos_names": []}}
    return {"date": "20260916", "brand": "누가샀나", "kospi": {"close": 6627.26, "chg_pct": -0.85, "prev_close": 6684.37},
            "inv": {"indiv": 8324, "foreign": -15736, "inst": -9044, "others": 16431, "etc_foreign": 25},
            "inv_streak": {"foreign": {"streak": -5, "turned_after": 0}, "inst": {"streak": -3, "turned_after": 0}},
            "intraday": {"at": "14:00", "snap": {"indiv": 1000, "foreign": -4000, "inst": -3000, "others": 6000}, "turns": []},
            "moves": [{"theme": "반도체", "y": -38339, "t": -20429, "state": "매도 지속", "streak": -5, "foreign": -13373, "inst": -7056, "ret": -0.24, "spread_names": []},
                      {"theme": "이차전지", "y": -621, "t": 937, "state": "혼조", "streak": 1, "foreign": 479, "inst": 458, "ret": 3.1, "spread_names": ["LG에너지솔루션", "삼성SDI", "포스코퓨처엠", "에코프로비엠"]}],
            "event": {"label": "이차전지·로봇에 몰린 돈", "group": "이차전지·로봇 관련주", "keywords": ["이차전지", "로봇주", "삼현", "포드 CATL", "제조AI", "중국산 로봇 규제", "외국인 순매도"], "date": "20260916",
                      "head": "미국 교통부가 포드에 공개서한을 보내 중국 CATL과의 배터리 협력을 정리하라고 요구한 일이 다시 부각됐고, 정부는 제조업 AI 전환을 전국으로 넓히는 콘퍼런스를 열었습니다. 미국이 중국산 로봇 규제를 강화한다는 움직임까지 겹쳤고요.",
                      "stocks": [{"code": "437730", "name": "삼현", "pct": 29.8, "foreign": 13, "inst": 26, "indiv": -37, "value": 548}], "avg_pct": 7.7},
            "prev_inv": {"indiv": 29722, "foreign": -32996, "inst": -11716, "others": 14868}, "prev_date": "20260915", "recent_closes": [],
            "callback": {"prev_date": "20260915", "q": "외국인 순매도가 엿새째 이어지는지", "check": {"kind": "inv_continue", "key": "foreign", "name": "외국인", "sign": -1, "n": 6}, "ok": True, "t": -15736},
            "ledger_stats": {"n": 3, "k": 1}, "top_others": [{"code": "000660", "name": "SK하이닉스", "v": 11182}, {"code": "005930", "name": "삼성전자", "v": 5084}],
            "buybacks": [{"code": "005930", "name": "삼성전자", "from": "2026-08-24", "to": "2026-11-21", "size": "약 15조"}, {"code": "000660", "name": "SK하이닉스", "from": "2026-08-20", "to": "2026-11-19", "size": "약 40조"}],
            "top_move": None, "upload_times": {"kr": "저녁 5시"}, "stocks": [], "kosdaq": {"indiv": -1398, "foreign": 241, "inst": 1107, "others": 52},
            "kosdaq_index": {"close": 812.41, "chg_pct": 0.7, "prev_close": 806.79}, "schedule": [{"d": "2026-10-08", "t": "옵션 만기"}], "inv_src": "키움 전 종목 합산",
            "stock_flows": {}, "theme_table": {k: v["net"] for k, v in table.items()}, "theme_table_y": {"반도체": -38339, "이차전지": -621}, "theme_rows": table, "theme_rows_y": {},
            "fomc_dates": ["2026-09-15/16", "2026-10-27/28"], "n_codes": 943,
            "brief_stocks": {"theme": "이차전지", "stocks": [{"code": "373220", "name": "LG에너지솔루션", "role": "대장주", "theme": "이차전지", "pct": 3.98, "foreign": 8, "inst": 413, "indiv": -324, "value": 1215},
                                                       {"code": "437730", "name": "삼현", "role": "최대 상승", "theme": "이차전지", "pct": 29.8, "foreign": 13, "inst": 26, "indiv": -37, "value": 548}]},
            "news_items": [{"title": "이차전지주 강세…LG에너지솔루션 4% 상승", "source": "테스트뉴스", "pub_kst": "2026-09-16 16:00"}],
            "flow_day": {"date": "20260916", "stocks": stocks_in, "sectors": [{"theme": "이차전지", "leader": "373220"}, {"theme": "반도체", "leader": "039030"}]},
            "fomc_prob": 92.0}


def selftest() -> None:
    import narrate_brief
    import script_memory as sm
    base = _synthetic()

    def go(name: str, c: dict, must: dict[str, str] | None = None, must_not: dict[str, str] | None = None, attempt: int = 0) -> dict:
        out = narrate_brief.build(c, attempt=attempt)
        sc = {s["id"]: s["tts"] for s in out["scenes"]}
        assert list(sc) == ["s0", "s1", "s2", "s3a", "s3b", "s3c", "s4", "s5", "s6"], f"{name}: 장면 id {list(sc)}"
        for s in out["scenes"]:
            assert len(s["steps"]) == len(sm.sentences(s["tts"])), f"{name}: [{s['id']}] steps {len(s['steps'])} ≠ 문장 {len(sm.sentences(s['tts']))}"
        qa = _qa_check(out["scenes"], {**out, "date": c["date"]})
        qa = [q for q in qa if "글자 그대로 겹침" not in q]
        assert not qa, f"{name}: 검사 실패 {qa}"
        total = sum(len(v) for v in sc.values())
        assert total <= narrate_brief.TOTAL_MAX, f"{name}: {total}자 > {narrate_brief.TOTAL_MAX}"
        for sid, frag in (must or {}).items():
            assert frag in sc[sid], f"{name}: [{sid}] '{frag}' 없음 :: {sc[sid]}"
        for sid, frag in (must_not or {}).items():
            assert frag not in sc[sid], f"{name}: [{sid}] '{frag}' 있으면 안 됨 :: {sc[sid]}"
        assert out["format"] == "brief" and out["hunter"]["s4"] is not None
        import ledger
        assert ledger.parse_q(out["next_q"]), f"{name}: next_q 장부 형식 아님 {out['next_q']}"
        print(f"  ok  {name:22} {total}자 · 훅 {out['hook_id']} · {out['devices']} · 다음 {out['next_q']}")
        return out

    o = go("base", base, must={"s2": "닷새째", "s3a": "코스닥", "s3b": "반도체", "s3c": "16분의 1", "s4": "삼현", "s5": "쪽입니다", "s6": "엿새째"})
    # 계산 1칸(s4 calc)은 GLOBAL_DROP 의 끝에서 두 번째 — 사실이 꽉 찬 날엔 밀린다.
    # JJ 가 매일 요구한 칸(유출 2·3위 업종, 코스닥 개인, 종목별 개인·거래대금)이 먼저고, 계산은 그다음이다.
    # 그래서 '들어갔으면 검산이 맞아야 한다'로만 본다(안 들어간 날은 화면 칩도 안 뜬다 — narrate_brief 1542행).
    _calc = o["hunter"]["s4"]["calc"]
    assert _calc is None or (_calc["verified"] and _calc["result"] == "34%"), _calc
    assert o["hunter"]["s5"]["verdicts"][0]["side"] == "b" and o["hunter"]["s5"]["verdicts"][1]["side"] == "a", o["hunter"]["s5"]["verdicts"]
    assert "92%" in o["scenes"][8]["tts"], o["scenes"][8]["tts"]
    # 유입 업종 없음
    c = copy.deepcopy(base)
    for th in ("이차전지", "로봇"):
        c["theme_rows"][th]["net"], c["theme_rows"][th]["foreign"], c["theme_rows"][th]["inst"] = -300, -200, -100
        c["theme_table"][th] = -300
    for r in c["flow_day"]["stocks"]:
        if r["theme"] in ("이차전지", "로봇"):
            r["foreign"], r["inst"] = -50, -30
    c["moves"] = [c["moves"][0]]
    c["brief_stocks"] = {}
    o = go("no_inflow", c, must={"s3c": "들어온 곳이 없었", "s4": "반도체 대장주"})
    assert o["hunter"]["s3c"]["in"] == [] and o["hunter"]["s3c"]["ratio"] is None
    # 이슈 없음 → 제목에 업종·종목 이름이 든 기사만 / 그것도 없으면 '뉴스 없이'
    c = copy.deepcopy(base)
    c["event"] = None
    o = go("no_event_news", c, must={"s5": "이차전지 쪽 기사는"})
    c["news_items"] = []
    o = go("no_event_no_news", c, must={"s5": "뉴스 없이"})
    assert all(v["side"] == "b" for v in o["hunter"]["s5"]["verdicts"]), o["hunter"]["s5"]["verdicts"]
    # 코스닥 수급 없음 → 지수 둘 + 코스피 판정 + 콜백
    c = copy.deepcopy(base)
    c["kosdaq"] = {}
    o = go("no_kosdaq", c, must={"s3a": "코스닥 0.70% 상승"}, must_not={"s3a": "코스닥 외국인"})
    assert o["hunter"]["s3a"]["kosdaq"] is None
    # 어제 약속 없음 → 콜백 문장 생략, 외국인 연속일 사실
    c = copy.deepcopy(base)
    c["callback"] = None
    o = go("no_callback", c, must={"s3a": "닷새째"}, must_not={"s3a": "도장"})
    # brief_stocks 수집 실패 → flow_day 의 외/기·등락·거래대금만(개인은 말하지 않음), 계산은 외+기 ÷ 거래대금
    c = copy.deepcopy(base)
    c["brief_stocks"] = {}
    o = go("no_brief_stocks", c, must={"s4": "LG에너지솔루션"}, must_not={"s4": "개인"})
    _calc = o["hunter"]["s4"]["calc"]                       # 위와 같은 이유로 예산에서 밀릴 수 있다
    assert _calc is None or _calc["kind"] == "share", _calc
    assert not o["hunter"]["s4"]["full"]
    assert o["hunter"]["s4"]["stocks"][1]["name"] == "포스코퓨처엠", o["hunter"]["s4"]["stocks"]
    # 오후 2시 스냅이 16시 이후 수집 → M2 제외
    c = copy.deepcopy(base)
    c["intraday"] = {"at": "16:44", "snap": {"indiv": 8324, "foreign": -15736, "inst": -9044, "others": 16431}, "turns": []}
    for k in range(3):
        o = go(f"snap_after_16 a{k}", c, attempt=k)
        assert o["hook_id"] != "M2", o["hook_id"]
    # 기타법인 3,000억 미만 → 자사주 문장 생략, '기타법인 N억' 한 마디
    c = copy.deepcopy(base)
    c["inv"]["others"], c["inv"]["indiv"] = 1200, 23555
    c["top_others"] = [{"code": "000660", "name": "SK하이닉스", "v": 600}]
    o = go("small_others", c, must={"s2": "1,200억"}, must_not={"s2": "자사주"})
    assert "기타법인" in o["scenes"][2]["tts"]
    # 회전: attempt 1·2 도 통과하고 문장이 달라진다
    o0 = go("attempt0", base, attempt=0)
    o1 = go("attempt1", base, attempt=1)
    diff = sum(1 for a, b in zip(o0["scenes"], o1["scenes"]) if a["tts"] != b["tts"])
    assert diff >= 3, f"attempt 회전이 문장을 바꾸지 않는다({diff}장면)"
    print("selftest ok")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == "--selftest":
        selftest()
        return
    dates = [a for a in args if a.isdigit() and len(a) == 8]
    avoid = {args[i + 1] for i, a in enumerate(args) if a == "--avoid" and i + 1 < len(args)}
    out_dir = next((Path(args[i + 1]) for i, a in enumerate(args) if a == "--out" and i + 1 < len(args)), None)
    attempt = next((int(args[i + 1]) for i, a in enumerate(args) if a == "--attempt" and i + 1 < len(args) and args[i + 1].isdigit()), 0)
    dates = [a for a in dates if not any(args[i - 1] == "--attempt" for i, b in enumerate(args) if b == a and i > 0)]
    results = []
    if "--cross" in args and len(dates) > 1:
        import script_memory as sm
        orig = sm.editions
        fakes: list[dict] = []

        def patched(before=None, kinds=("kr", "weekly", "weekly_us", "notice")):
            base = orig(before, kinds)
            extra = [f for f in fakes if (not before or f["date"] < before) and f["kind"] in kinds]
            return sorted(base + extra, key=lambda r: (r["date"], r["folder"]))
        sm.editions = patched
        try:
            for d in sorted(dates):
                r = run(d, avoid, out_dir, attempt=attempt)
                results.append(r)
                like = json.loads((Path(out_dir or SCRATCH) / d / "computed_like.json").read_text(encoding="utf-8"))
                fakes.append(sm._record("kr", d, d + "_try", like, like["scenes"]))
        finally:
            sm.editions = orig
    else:
        results = [run(d, avoid, out_dir, attempt=attempt) for d in dates]
    if "--cross" in args and len(results) > 1:
        dup = cross(results)
        print("===== 여러 날 사이 글자 그대로 겹친 문장:", "없음" if not dup else f"{len(dup)}건")
        for x in dup:
            print("   ", x)


if __name__ == "__main__":
    main()
