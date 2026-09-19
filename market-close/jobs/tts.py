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

GAP = 0.6           # 장면 끝 여유(초). 말이 끝나고 다음 장면이 바로 뜨면 받아들일 틈이 없다(JJ 2026-09-14)
FPS = 30


def _srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


RATE_BY_VOICE = {"ko-KR-InJoonNeural": "+20%", "ko-KR-HyunsuMultilingualNeural": "+15%", "ko-KR-SunHiNeural": "+15%"}


def speakable(text: str) -> str:
    """읽기용 텍스트: 괄호는 쉼표로(괄호에서 TTS가 길게 끊김), 물결·슬래시 정리."""
    t = re.sub(r"\s*\(([^)]*)\)", r", \1", text)
    t = t.replace("누가샀나", "누가 샀나")   # 붙여 쓰면 '누가샜나'처럼 들린다(JJ 9/19) — 읽기만 띄우고 자막은 그대로
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


EDGE_DEFAULT = "ko-KR-InJoonNeural"


def _engine(d: str, ed: str):
    """(타입캐스트 모듈|None, 보이스 이름). 엔진은 키체인 tts:engine 으로 고른다.

    미장 평일편(us)은 data/publish_config.json 의 editions.us=false 라 아무 데도 안 올라간다.
    거기에 크레딧을 쓰면 국장편이 월 중순에 말라붙는다 — 그래서 기본은 edge로 만든다."""
    if (get_api_key("tts", "engine") or "edge").lower() != "typecast":
        return None, get_api_key("tts", "voice") or EDGE_DEFAULT
    if ed == "us" and (get_api_key("tts", "typecast_us") or "0") != "1":
        log(d, "tts", "미장편은 게시 대상이 아니라 크레딧을 아껴 edge로 만든다(바꾸려면 키체인 tts:typecast_us=1)")
        return None, get_api_key("tts", "voice") or EDGE_DEFAULT
    import tts_typecast as tc
    return tc, get_api_key("tts", "typecast_voice") or tc.DEFAULT_VOICE


async def _build(d: str, ed: str, od, scenes: list[dict], tc, voice: str) -> tuple[float, list[str], int, str]:
    """장면을 순서대로 음성으로 만든다. 같은 대본·같은 보이스면 이미 만든 mp3를 다시 쓴다(재실행해도 크레딧을 또 안 쓴다)."""
    (od / "voice").mkdir(parents=True, exist_ok=True)
    manual_dir = od / "voice" / "manual"
    cache_p = od / ".tts_cache.json"
    cache = (load_json(cache_p) or {}) if tc else {}
    tempo = str(get_api_key("tts", "typecast_tempo") or 1.0)
    pause = f'{get_api_key("tts", "typecast_pause") or ""}/{get_api_key("tts", "typecast_qpause") or ""}'
    t, srt, n = 0.0, [], 1
    manual_ids: list[str] = []
    billed = reused = 0
    for i, sc in enumerate(scenes):
        p = od / "voice" / f"{sc['id']}.mp3"
        cues = None
        rec = next((f for ext in ("mp3", "wav", "m4a") for f in [manual_dir / f"{sc['id']}.{ext}"] if f.exists()), None)
        if rec:
            import shutil
            from mutagen import File as MFile
            p = od / "voice" / f"{sc['id']}{rec.suffix}"
            shutil.copy(rec, p)
            dur = round(float(MFile(str(rec)).info.length), 3)
            bounds = [{"start": 0.0, "end": dur, "text": sc["tts"]}]
            manual_ids.append(sc["id"])          # voice 를 덮지 않는다 — 덮으면 다음 장면이 voice_id="manual" 로 API를 친다
        elif tc:
            txt = speakable(sc["tts"])
            prev = speakable(scenes[i - 1]["tts"]) if i else ""
            nxt = speakable(scenes[i + 1]["tts"]) if i + 1 < len(scenes) else ""
            key = f"{voice}|{tempo}|{pause}|{txt}"
            hit = cache.get(sc["id"])
            files_ok = hit and all((od / "voice" / x["file"]).exists() for x in (hit.get("parts") or []))
            if hit and hit.get("k") == key and files_ok:
                dur, bounds, cues, parts = hit["dur"], hit["bounds"], hit["cues"], hit["parts"]
                reused += 1
            else:
                dur, bounds, cues, parts, n_ch = tc.synth_parts(txt, od / "voice", sc["id"], voice, prev=prev, nxt=nxt)
                billed += n_ch
                cache[sc["id"]] = {"k": key, "dur": dur, "bounds": bounds, "cues": cues, "parts": parts}
                save_json(cache_p, cache)
            sc["audio_parts"] = [{"file": f"voice/{x['file']}", "at": x["at"]} for x in parts]
            if p.exists():          # 통짜로 만들던 시절의 파일이 남아 public/voice 로 딸려 가지 않게
                p.unlink()
        else:
            dur, bounds = await synth(speakable(sc["tts"]), p, voice)
        length = max(sc.get("min") or 4.0, dur + GAP)
        if sc["id"] in ("s0", "u0", "w0", "uw0", "n0") and dur > 10.5:
            log(d, "tts", f"⚠ 인트로 {dur}s > 10s — 대본을 줄여야 함")
        cues = cues or make_cues(bounds)
        if bounds:                       # 장면 끝 여유 동안 자막이 사라지지 않게 마지막 줄을 늘린다
            bounds[-1]["end"] = round(max(bounds[-1]["end"], length - 0.05), 3)
        if cues:
            cues[-1]["end"] = round(max(cues[-1]["end"], length - 0.05), 3)
        sc.update({"audio": None if sc.get("audio_parts") else f"voice/{p.name}",
                   "audio_sec": dur, "sec": round(length, 2), "start": round(t, 2),
                   "frames": int(round(length * FPS)), "bounds": bounds})
        for b in bounds:
            srt.append(f"{n}\n{_srt_time(t + b['start'])} --> {_srt_time(t + b['end'])}\n{b['text']}\n")
            n += 1
        sc["cues"] = cues
        t += length
        log(d, "tts", f"{sc['id']}: 음성 {dur}s → 장면 {length:.1f}s ({sc['tts'][:40]}…)")
    name = tc.voice_name(voice) if tc else voice
    label = (f"{name}({voice})" if tc and name != voice else voice) + (f" (수동 {','.join(manual_ids)})" if manual_ids else "")
    if tc:
        spoken = sum((s.get("audio_sec") or 0) for s in scenes)
        chars = sum(len(speakable(s["tts"])) for s in scenes)
        if spoken:      # 보이스를 바꾸면 같은 tempo라도 속도가 달라진다 — 눈에 보이게 남긴다
            log(d, "tts", f"말 속도 {chars / spoken:.1f}자/초 (보정: python tts_calibrate.py)")
        left = tc.remaining_credits()
        log(d, "tts", f"타입캐스트 {billed}자 청구" + (f", {reused}장면 재사용" if reused else "")
            + (f" — 남은 크레딧 {left[0]:,}/{left[1]:,}" if left else ""))
        if left and left[0] < 3000:
            log(d, "tts", f"⚠ 남은 크레딧 {left[0]:,} — 곧 바닥난다. 플랜을 올리거나 edge로 되돌려야 한다")
    return t, srt, n, label


async def main(d: str, ed: str = "kr") -> None:
    comp = load_json(computed_path(d, ed))
    if not comp:
        raise SystemExit(f"computed_{ed}.json 없음 — compute 먼저")
    od = out_dir(d, ed)
    # 대본: JJ가 직접 녹음할 때 읽을 파일. 녹음본은 out/D/voice/manual/s0.mp3 … s5.mp3(또는 .wav)로 두면 합성 대신 그것을 쓴다.
    (od / "script.txt").write_text("\n\n".join(f"[{sc['id']}] {sc['tts']}" for sc in comp["scenes"]), encoding="utf-8")
    scenes = comp["scenes"]
    tc, voice = _engine(d, ed)
    try:
        t, srt, n, label = await _build(d, ed, od, scenes, tc, voice)
    except Exception as e:
        # 무인으로 도는 15:55 작업이다. 타입캐스트가 어떤 이유로든 안 되면 그날을 통째로 버리지 않고
        # 처음부터 edge-tts로 다시 만든다(중간부터 바꾸면 한 영상에 목소리가 둘 섞인다).
        if tc is None:
            raise
        log(d, "tts", f"⚠ 타입캐스트 실패 — 전부 edge-tts로 다시 만든다: {e}")
        edge_voice = get_api_key("tts", "voice") or EDGE_DEFAULT
        t, srt, n, label = await _build(d, ed, od, scenes, None, edge_voice)
        label += " ← 타입캐스트 실패 대체"
    comp["total_sec"] = round(t, 2)
    comp["total_frames"] = int(round(t * FPS))
    comp["fps"] = FPS
    comp["voice"] = label
    (od / "subs.srt").write_text("\n".join(srt), encoding="utf-8")
    (od / "caption.txt").write_text(comp["caption"], encoding="utf-8")
    save_json(computed_path(d, ed), comp)
    save_json(od / "props.json", comp)
    log(d, "tts", f"총 {t:.1f}s, {label}, subs.srt {n - 1}줄")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"), sys.argv[2] if len(sys.argv) > 2 else "kr"))
