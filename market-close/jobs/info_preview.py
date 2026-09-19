"""음성 전 화면 미리 보기(기업 해부·정보편) — 문장 길이로 가짜 시간을 매겨 장면마다 스틸. 사용(jobs/): python info_preview.py <d> <ed> <outdir> [scene...]"""
import json, re, subprocess, sys
from pathlib import Path
MC = Path(__file__).resolve().parents[1]
d, ed, outd = sys.argv[1], sys.argv[2], Path(sys.argv[3]); only = sys.argv[4:]
comp = json.loads((MC / "data" / d / f"computed_{ed}.json").read_text(encoding="utf-8"))
fps, t0, shots = 30, 0.0, []
for sc in comp["scenes"]:
    sents = [x for x in re.split(r"(?<=[.?!])\s+", sc["tts"].strip()) if x]
    cues, t = [], 0.3
    for s in sents:
        dur = max(1.2, len(s) / 7.35); cues.append({"start": round(t, 2), "end": round(t + dur, 2), "text": s}); t += dur + 0.25
    sc["cues"], sc["start"], sc["frames"] = cues, t0, int((t + 0.3) * fps)
    if not only or sc["id"] in only:
        for c in cues:
            shots.append((sc["id"], int((t0 + c["start"] + min(1.6, (c["end"] - c["start"]) * 0.7)) * fps), c["text"][:14]))
    t0 += (t + 0.3)
comp["total_frames"] = int(t0 * fps)
props = MC / "render" / f"props_{ed}_preview.json"; props.write_text(json.dumps(comp, ensure_ascii=False), encoding="utf-8")
outd.mkdir(parents=True, exist_ok=True)
items = ",".join(f"{fr}:{sid}_{fr:05d}" for sid, fr, tx in shots)
r = subprocess.run(["node", "stills.mjs", str(props), str(outd), "Video", items], cwd=str(MC / "render"), capture_output=True, text=True, encoding="utf-8")
print(r.stdout[-2000:], r.stderr[-1500:])
