"""Typecast API 음성 엔진 — edge-tts 대신 쓸 수 있는 같은 모양의 synth().

왜 만들었나(JJ 2026-09-14): edge-tts는 기계가 읽는 티가 난다. 타입캐스트는
문맥을 보고 감정을 얹는 스마트 이모션이 있고, 무엇보다 **단어 단위 타임스탬프**를
같이 준다. 지금까지는 edge-tts의 문장 경계(SentenceBoundary)에 화면 전환과 자막을
물려 놨는데, 타입캐스트 쪽이 더 촘촘하고 정확하다.

웹 에디터와 API는 별개 상품이다(요금제도 따로). 웹에서 만든 보이스 클론은 API에서
쓸 수 없고, API로 쓰려면 POST /v1/voices/clone 으로 다시 떠야 한다 — 그건 유료
플랜(커스텀 보이스 슬롯)이 있어야 한다.

키체인:
  typecast:api_key         API 키 (studio.typecast.ai/developers/api/api-key)
  tts:engine               "typecast" 면 이 엔진을 쓴다(기본 edge)
  tts:typecast_voice       보이스 ID(tc_… 기본, uc_… 클론). 없으면 DEFAULT_VOICE
  tts:typecast_tempo       0.5~2.0 말 빠르기(기본 1.0)
"""
from __future__ import annotations

import base64
import re
import time

import requests

from app.keychain import get_api_key

API = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"
MODEL = "ssfm-v30"
# 타입캐스트 규약: 이 연동을 만든 출처와 에이전트를 계속 실어 보낸다
UA = "typecast-direct/1 python typecast-integration/1 (source=api-docs; generated_by=claude-code)"
DEFAULT_VOICE = "tc_67919fb54fd00e0217d2cff0"   # 승재 — 한국어 남성, 뉴스/아나운서
LUFS = -14                                       # 스트리밍 표준 음량
TIMEOUT = 180

# 타임스탬프를 글자에 맞춰 걸을 때 쓰는 정규화(공백·문장부호를 뺀 글자만 센다)
_KEEP = re.compile(r"[^0-9A-Za-z가-힣%]")


def _strip(s: str) -> str:
    return _KEEP.sub("", s)


def sentences(text: str) -> list[str]:
    """문장 나누기 — 마침표·물음표·느낌표 뒤 공백에서만 자른다."""
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def _key() -> str:
    k = get_api_key("typecast", "api_key")
    if not k:
        raise SystemExit("typecast:api_key 없음 — backend/scripts/set_api_key.py typecast api_key")
    return k


def _post(body: dict) -> dict:
    h = {"X-API-KEY": _key(), "Content-Type": "application/json", "User-Agent": UA}
    last = None
    for i in range(4):
        r = requests.post(f"{API}?granularity=word", headers=h, json=body, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
        last = f"{r.status_code} {r.text[:300]}"
        if r.status_code == 402:
            raise SystemExit(f"타입캐스트 크레딧 부족 — {last}")
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 * (i + 1))
            continue
        raise SystemExit(f"타입캐스트 오류 — {last}")
    raise SystemExit(f"타입캐스트 재시도 실패 — {last}")


def bounds_from_words(text: str, words: list[dict], dur: float) -> list[dict]:
    """단어 타임스탬프 → 문장 경계. 단어를 글자 수로 좇아가며 어느 문장에 속하는지 본다."""
    sents = sentences(text)
    if not sents:
        return []
    if not words:
        return [{"start": 0.0, "end": dur, "text": text}]

    ends, acc = [], 0
    for s in sents:
        acc += len(_strip(s))
        ends.append(acc)

    span: list[list[float]] = [[-1.0, -1.0] for _ in sents]
    pos, si = 0, 0
    for w in words:
        n = len(_strip(w.get("text", "")))
        while si < len(sents) - 1 and pos >= ends[si]:
            si += 1
        st, en = float(w.get("start", 0.0)), float(w.get("end", 0.0))
        if span[si][0] < 0:
            span[si][0] = st
        span[si][1] = max(span[si][1], en)
        pos += n

    out, prev_end = [], 0.0
    for i, s in enumerate(sents):
        st = span[i][0] if span[i][0] >= 0 else prev_end
        en = span[i][1] if span[i][1] >= 0 else st
        st = min(st, en)
        out.append({"start": round(max(st, 0.0), 3), "end": round(max(en, st), 3), "text": s})
        prev_end = out[-1]["end"]
    # 마지막 문장 끝은 실제 오디오 끝까지 늘린다(꼬리 여백이 잘려 보이지 않게)
    if out:
        out[-1]["end"] = round(max(out[-1]["end"], dur - 0.05), 3)
    return out


def cues_from_words(text: str, words: list[dict], bounds: list[dict], max_len: int = 55) -> list[dict]:
    """자막 큐 — 긴 문장은 실제 단어 시각에서 자른다(길이 비례 추정이 아니라)."""
    if not words:
        return []
    flat = []
    pos = 0
    for w in words:
        n = len(_strip(w.get("text", "")))
        flat.append({"s": float(w.get("start", 0.0)), "e": float(w.get("end", 0.0)), "a": pos, "b": pos + n})
        pos += n

    cues = []
    base = 0
    for b in bounds:
        s = b["text"]
        L = len(_strip(s))
        lo, hi = base, base + L
        base = hi
        if len(s) <= max_len:
            cues.append({"start": b["start"], "end": b["end"], "text": s})
            continue
        # ', ' 경계로 토막 내고, 각 토막의 글자 구간에 걸치는 단어 시각을 쓴다
        parts, cur = [], ""
        for piece in s.split(", "):
            piece = piece + ", "
            if cur and len(cur) + len(piece) > max_len:
                parts.append(cur.strip().rstrip(","))
                cur = piece
            else:
                cur += piece
        if cur.strip():
            parts.append(cur.strip().rstrip(","))
        off = lo
        for x in parts:
            n = len(_strip(x))
            seg = [w for w in flat if w["b"] > off and w["a"] < off + n and w["a"] >= lo and w["b"] <= hi]
            st = seg[0]["s"] if seg else b["start"]
            en = seg[-1]["e"] if seg else b["end"]
            cues.append({"start": round(st, 3), "end": round(max(en, st + 0.2), 3), "text": x})
            off += n
        if cues:
            cues[-1]["end"] = b["end"]
    return cues


def synth(text: str, path, voice: str | None = None, tempo: float | None = None,
          prev: str = "", nxt: str = "") -> tuple[float, list[dict], list[dict]]:
    """mp3 저장, (총 길이초, 문장 경계, 단어 타임스탬프) 반환.

    prev/nxt 는 스마트 이모션이 앞뒤 맥락을 보고 억양을 정하는 데 쓴다 —
    문장 끝이 뚝 떨어지지 않게 하는 건 이 맥락 정보다(피치를 흔드는 게 아니라).
    """
    body = {
        "model": MODEL,
        "voice_id": voice or get_api_key("tts", "typecast_voice") or DEFAULT_VOICE,
        "text": text,
        "language": "kor",
        "prompt": {"emotion_type": "smart"},
        "output": {"audio_format": "mp3",
                   "audio_tempo": float(tempo if tempo is not None else (get_api_key("tts", "typecast_tempo") or 1.0)),
                   "target_lufs": LUFS},
    }
    if prev:
        body["prompt"]["previous_text"] = prev[-300:]
    if nxt:
        body["prompt"]["next_text"] = nxt[:300]

    d = _post(body)
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["audio"]))
    dur = round(float(d.get("audio_duration") or 0.0), 3)
    words = d.get("words") or []
    return dur, bounds_from_words(text, words, dur), words
