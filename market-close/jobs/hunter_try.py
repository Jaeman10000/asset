"""헌터 포맷 대본 시험 — 지난 날짜의 데이터로 narrate_hunter.build 를 돌려 대본·화면 사전·전 편 겹침·검사 결과를 본다.
data/ 와 out/ 은 건드리지 않는다(ledger 도 안 쓴다). 결과는 스크래치 폴더에 쓴다.

실행(market-close/jobs 에서):
  python hunter_try.py 20260915                  대본([id] tts) + hunter JSON + overlaps + 자수/초 출력, 파일 저장
  python hunter_try.py 20260915 --out D:/tmp     저장 폴더 바꾸기(기본: 세션 스크래치 hunter/DATE/)
  python hunter_try.py 20260915 --avoid "문장"   검사에 걸린 문장을 피해 다시 만들기(compute 의 재시도와 같은 길)
  python hunter_try.py 20260911 20260914 20260915 --cross   여러 날을 만들고 서로 글자 그대로 겹친 문장까지 본다
  python hunter_try.py 20260915 --props            tts 없이 시간표를 붙인 렌더용 props.json 도 저장(문장 = 자/8.0 초, 장면 +0.6초 여유, 30fps)

입력 c 는 compute.narration_inputs() 로 그날 computed_kr.json + raw/*.json + data/ledger.json 에서 compute 와 똑같이 만든다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA, load_json  # noqa: E402

SCRATCH = Path(r"C:/Users/Jeff/AppData/Local/Temp/claude/C--Users-Jeff-Documents-GitHub-asset/ed61fea3-c63d-4ffd-8a2a-78666bf42e10/scratchpad/hunter")
CPS = 8.0


def inputs_for(d: str) -> tuple[dict, dict]:
    """(c, computed_kr.json) — compute.compute() 가 narrate 에 넘기는 것과 같은 입력을 저장된 파일에서 되살린다."""
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
    return c, c0


def run(d: str, avoid: set[str] | None = None, out_dir: Path | None = None, quiet: bool = False, props: bool = False) -> dict:
    import narrate_hunter
    import script_memory as sm
    c, c0 = inputs_for(d)
    out = narrate_hunter.build(c, avoid or None)
    scenes = out["scenes"]
    lines = [f"[{sc['id']}] {sc['tts']}" for sc in scenes]
    script = "\n".join(lines)
    chars = sum(len(sc["tts"]) for sc in scenes)
    ov = sm.overlaps(d, scenes)
    lint = narrate_hunter.lint(scenes)
    try:
        import qa_script
        qa = qa_script.check_hunter(scenes, {**c0, **out, "date": d})
    except AttributeError:
        qa = ["(qa_script.check_hunter 없음)"]
    if not quiet:
        print(f"===== {d}  훅 {out['hook_id']} · 장치 {out['devices']} · 다음 {out['next_q']}")
        print(script)
        print(f"-- {chars}자 ≈ {chars / CPS:.0f}초 (자/8.0)")
        print("-- overlaps(전 편과 겹침):", "없음" if not ov else "")
        for o in ov:
            print(f"   [{o['kind']}] ({o['scene']}) {o['sentence']}  ← {', '.join(o['seen'][:3])}")
        print("-- lint(자체):", "없음" if not lint else "")
        for w in lint:
            print("   ", w)
        print("-- qa_script.check_hunter:", "통과" if not qa else f"{len(qa)}건")
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
    if props:
        pr = props_from(like)
        (od / "props.json").write_text(json.dumps(pr, ensure_ascii=False, indent=1), encoding="utf-8")
        if not quiet:
            mids = {sc["id"]: int(round((sc["start"] + sc["sec"] / 2) * pr["fps"])) for sc in pr["scenes"]}
            print(f"-- props.json: total_frames={pr['total_frames']} ({pr['total_sec']}s) · 장면 중간 프레임 {mids}")
    if not quiet:
        print(f"-- 저장: {od / 'script.txt'} · hunter.json · computed_like.json" + (" · props.json" if props else ""))
    return {"date": d, "out": out, "script": script, "chars": chars, "overlaps": ov, "lint": lint, "qa": qa}


def props_from(like: dict, cps: float = CPS, gap: float = 0.6, fps: int = 30) -> dict:
    """렌더 시험용 props — tts.py 가 붙이는 것과 같은 모양(scenes[].start/sec/frames/bounds/cues, total_frames, fps).
    문장 하나 = 자/cps 초, bounds 는 문장당 1개, cues 도 문장당 1개(실제 타입캐스트는 55자 넘는 문장을 쪼갠다 — 화면은 bounds 를 먼저 본다)."""
    import copy
    import script_memory as sm
    out = copy.deepcopy(like)
    t = 0.0
    for sc in out["scenes"]:
        ss = sm.sentences(sc["tts"])
        b, u = [], 0.0
        for x in ss:
            dur = max(0.8, len(x) / cps)
            b.append({"start": round(u, 3), "end": round(u + dur, 3), "text": x})
            u += dur
        length = max(float(sc.get("min") or 4.0), u + gap)
        if b:
            b[-1]["end"] = round(max(b[-1]["end"], length - 0.05), 3)
        sc.update({"audio": None, "audio_sec": round(u, 3), "sec": round(length, 2), "start": round(t, 2), "frames": int(round(length * fps)),
                   "bounds": b, "cues": copy.deepcopy(b)})
        t += length
    out.update({"total_frames": int(round(t * fps)), "total_sec": round(t, 2), "fps": fps, "format": "hunter", "visual": "v4"})
    return out


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


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    dates = [a for a in args if a.isdigit() and len(a) == 8]
    avoid = {args[i + 1] for i, a in enumerate(args) if a == "--avoid" and i + 1 < len(args)}
    out_dir = next((Path(args[i + 1]) for i, a in enumerate(args) if a == "--out" and i + 1 < len(args)), None)
    results = [run(d, avoid, out_dir, props="--props" in args) for d in dates]
    if "--cross" in args and len(results) > 1:
        dup = cross(results)
        print("===== 여러 날 사이 글자 그대로 겹친 문장:", "없음" if not dup else f"{len(dup)}건")
        for x in dup:
            print("   ", x)


if __name__ == "__main__":
    main()
