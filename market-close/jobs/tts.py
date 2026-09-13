"""18:06 TTS — computed.json 장면별 문장 → out/D/voice/sN.mp3 (edge-tts), 길이 측정 → 장면 길이 확정, subs.srt.
음성: 키체인 tts:voice 없으면 ko-KR-SunHiNeural. 확인 모드 임시 벤더(SPEC §10).
mp3 길이는 edge-tts의 SentenceBoundary(offset+duration)로 계산(ffprobe 불필요).
"""
from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime

import edge_tts

from _common import DATA, computed_path, load_json, log, out_dir, save_json
from app.keychain import get_api_key  # noqa: E402

GAP = 0.4           # 장면 끝 여유(초)
FPS = 30


def _srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


RATE_BY_VOICE = {"ko-KR-InJoonNeural": "+20%", "ko-KR-HyunsuMultilingualNeural": "+15%", "ko-KR-SunHiNeural": "+15%"}


def speakable(text: str) -> str:
    """읽기용 텍스트: 괄호는 쉼표로(괄호에서 TTS가 길게 끊김), 물결·슬래시 정리."""
    t = re.sub(r"\s*\(([^)]*)\)", r", \1", text)
    # '2.5조를' → '2조 5천억을'('이 점 오 조' 대신). 받침이 생기므로 바로 뒤 조사도 고친다
    JOSA = {"를": "을", "가": "이", "는": "은", "로": "으로", "와": "과", "였": "이었", "라": "이라", "야": "이야"}
    t = re.sub(r"(\d+)\.([1-9])조(를|가|는|로|와|였|라|야)?",
               lambda m: f"{m.group(1)}조 {m.group(2)}천억" + (JOSA[m.group(3)] if m.group(3) else ""), t)
    t = re.sub(r"(\d+)\.0조", lambda m: m.group(1) + "조", t)
    t = re.sub(r"(\d+)\.(\d*?)0+%", lambda m: f"{m.group(1)}.{m.group(2)}%" if m.group(2) else f"{m.group(1)}%", t)   # 끝자리 0은 읽지 않음
    return re.sub(r"\s*,\s*,", ",", t)


async def synth(text: str, path, voice: str, rate: str | None = None) -> tuple[float, list[dict]]:
    """mp3 저장, (총 길이초, 문장 경계[{start,end,text}]) 반환. 속도는 음성별 기본값(인준은 느려서 +20%)."""
    c = edge_tts.Communicate(text, voice, rate=rate or RATE_BY_VOICE.get(voice, "+15%"))
    bounds = []
    with open(path, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "SentenceBoundary":
                bounds.append({"start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7, "text": ch["text"]})
    dur = max((b["end"] for b in bounds), default=0.0) + 0.15
    return round(dur, 3), bounds


def make_cues(bounds: list[dict], max_len: int = 55) -> list[dict]:
    """TTS 문장 경계 → 화면 자막 큐. 긴 문장은 ', ' 경계에서 나눠 길이 비례로 시간을 배분한다(자막 벽 방지)."""
    cues = []
    for b in bounds:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if len(text) <= max_len:
            cues.append({"start": b["start"], "end": b["end"], "text": text})
            continue
        parts, cur = [], ""
        for piece in text.split(", "):
            piece = piece + ", "
            if cur and len(cur) + len(piece) > max_len:
                parts.append(cur.strip().rstrip(","))
                cur = piece
            else:
                cur += piece
        if cur.strip():
            parts.append(cur.strip().rstrip(","))
        total = sum(len(x) for x in parts) or 1
        t0, span = b["start"], b["end"] - b["start"]
        for x in parts:
            dt = span * len(x) / total
            cues.append({"start": round(t0, 3), "end": round(t0 + dt, 3), "text": x})
            t0 += dt
    return cues


async def main(d: str, ed: str = "kr") -> None:
    comp = load_json(computed_path(d, ed))
    if not comp:
        raise SystemExit(f"computed_{ed}.json 없음 — compute 먼저")
    voice = get_api_key("tts", "voice") or "ko-KR-InJoonNeural"
    od = out_dir(d, ed)
    # 대본: JJ가 직접 녹음할 때 읽을 파일. 녹음본은 out/D/voice/manual/s0.mp3 … s5.mp3(또는 .wav)로 두면 합성 대신 그것을 쓴다.
    (od / "script.txt").write_text("\n\n".join(f"[{sc['id']}] {sc['tts']}" for sc in comp["scenes"]), encoding="utf-8")
    manual_dir = od / "voice" / "manual"
    t = 0.0
    srt = []
    n = 1
    for sc in comp["scenes"]:
        p = od / "voice" / f"{sc['id']}.mp3"
        rec = next((f for ext in ("mp3", "wav", "m4a") for f in [manual_dir / f"{sc['id']}.{ext}"] if f.exists()), None)
        if rec:
            import shutil
            from mutagen import File as MFile
            p = od / "voice" / f"{sc['id']}{rec.suffix}"
            shutil.copy(rec, p)
            dur = round(float(MFile(str(rec)).info.length), 3)
            bounds = [{"start": 0.0, "end": dur, "text": sc["tts"]}]
            voice = "manual"
        else:
            dur, bounds = await synth(speakable(sc["tts"]), p, voice)
        length = max(sc["min"], dur + GAP)
        if sc["id"] in ("s0", "u0") and dur > 10.5:
            log(d, "tts", f"⚠ 인트로 {dur}s > 10s — 대본을 줄여야 함")
        sc.update({"audio": f"voice/{p.name}", "audio_sec": dur, "sec": round(length, 2), "start": round(t, 2),
                   "frames": int(round(length * FPS)), "bounds": bounds})
        for b in bounds:
            srt.append(f"{n}\n{_srt_time(t + b['start'])} --> {_srt_time(t + b['end'])}\n{b['text']}\n")
            n += 1
        sc["cues"] = make_cues(bounds)
        t += length
        log(d, "tts", f"{sc['id']}: 음성 {dur}s → 장면 {length:.1f}s ({sc['tts'][:40]}…)")
    comp["total_sec"] = round(t, 2)
    comp["total_frames"] = int(round(t * FPS))
    comp["fps"] = FPS
    comp["voice"] = voice
    (od / "subs.srt").write_text("\n".join(srt), encoding="utf-8")
    (od / "caption.txt").write_text(comp["caption"], encoding="utf-8")
    save_json(computed_path(d, ed), comp)
    save_json(od / "props.json", comp)
    log(d, "tts", f"총 {t:.1f}s, {voice}, subs.srt {n - 1}줄")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"), sys.argv[2] if len(sys.argv) > 2 else "kr"))
