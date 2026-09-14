"""Typecast API 음성 엔진 — edge-tts 대신 쓸 수 있는 같은 모양의 synth().

왜 만들었나(JJ 2026-09-14): edge-tts는 기계가 읽는 티가 난다. 타입캐스트는
문맥을 보고 감정을 얹는 스마트 이모션이 있고, 무엇보다 **단어 단위 타임스탬프**를
같이 준다. 지금까지는 edge-tts의 문장 경계(SentenceBoundary)에 화면 전환과 자막을
물려 놨는데, 타입캐스트 쪽이 더 촘촘하고 정확하다.

웹 에디터와 API는 별개 상품이다(요금제도 따로). 웹에서 만든 보이스 클론은 API에서
쓸 수 없고, API로 쓰려면 POST /v1/voices/clone 으로 다시 떠야 한다 — 그건 유료
플랜(커스텀 보이스 슬롯)이 있어야 한다.

여기서 죽을 때는 반드시 TypecastError(=RuntimeError)를 던진다. SystemExit을 던지면
BaseException이라 부르는 쪽의 `except Exception` 폴백을 그냥 통과해 버려서, 무인으로
도는 15:55 작업이 그대로 끝나고 그날 영상이 안 나간다.

키체인:
  typecast:api_key         API 키 (studio.typecast.ai/developers/api/api-key)
  tts:engine               "typecast" 면 이 엔진을 쓴다(기본 edge)
  tts:typecast_voice       보이스 ID(tc_… 기본, uc_… 클론). 없으면 DEFAULT_VOICE
  tts:typecast_tempo       0.5~2.0 말 빠르기. 보이스마다 기본 속도가 다르다 —
                           김건은 0.82에서 7.5자/초(평일편 778자 → 1:46), 승재는 0.93에서 7.2자/초
"""
from __future__ import annotations

import base64
import re
import time

import requests

from app.keychain import get_api_key

API = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"
SUBSCRIPTION = "https://api.typecast.ai/v1/users/me/subscription"
MODEL = "ssfm-v30"
# 타입캐스트 규약: 이 연동을 만든 출처와 에이전트를 계속 실어 보낸다
UA = "typecast-direct/1 python typecast-integration/1 (source=api-docs; generated_by=claude-code)"
DEFAULT_VOICE = "tc_61c2f7741330d213c238cba6"   # 김건 — 한국어 남성, 오디오북/다큐 (JJ 2026-09-14 선택)
LUFS = -14                                       # 스트리밍 표준 음량
TIMEOUT = 60          # 장면 하나에 60초를 넘기면 16:30 게시가 위험하다
RETRIES = 3
CTX = 300             # 스마트 이모션에 넘기는 앞뒤 문맥 길이

# 타임스탬프를 글자에 맞춰 걸을 때 쓰는 정규화(공백·문장부호를 뺀 글자만 센다)
_KEEP = re.compile(r"[^0-9A-Za-z가-힣%]")


class TypecastError(RuntimeError):
    """타입캐스트 쪽 실패. 부르는 쪽은 이걸 잡아 edge-tts로 넘어가면 된다."""


def _strip(s: str) -> str:
    return _KEEP.sub("", s)


def sentences(text: str) -> list[str]:
    """문장 나누기 — 마침표·물음표·느낌표 뒤 공백에서만 자른다."""
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def _key() -> str:
    k = get_api_key("typecast", "api_key")
    if not k:
        raise TypecastError("typecast:api_key 없음 — backend/scripts/set_api_key.py typecast api_key")
    return k


def _post(body: dict) -> dict:
    """200이 나올 때까지 재시도. 네트워크 예외도 재시도 대상이다(여기서 안 잡으면 그날 작업이 죽는다)."""
    h = {"X-API-KEY": _key(), "Content-Type": "application/json", "User-Agent": UA}
    last = ""
    for i in range(RETRIES):
        try:
            r = requests.post(f"{API}?granularity=word", headers=h, json=body, timeout=TIMEOUT)
        except requests.RequestException as e:                 # 타임아웃·연결 끊김·SSL
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:                                  # 200인데 JSON이 아님(프록시·CDN 오류면)
                last = f"200이지만 JSON이 아님: {r.text[:200]}"
                time.sleep(2 * (i + 1))
                continue
        last = f"{r.status_code} {r.text[:200]}"
        if r.status_code == 402:
            raise TypecastError(f"크레딧 부족 — {last}")
        if r.status_code in (401, 403, 404, 400, 422):           # 재시도해도 같은 답이 온다
            raise TypecastError(last)
        time.sleep(2 * (i + 1))                                  # 429·5xx
    raise TypecastError(f"{RETRIES}번 시도했지만 실패 — {last}")


def remaining_credits() -> tuple[int, int] | None:
    """(남은 크레딧, 월 한도). 조회 자체가 실패하면 None — 이걸로 제작을 막지는 않는다."""
    try:
        r = requests.get(SUBSCRIPTION, headers={"X-API-KEY": _key(), "User-Agent": UA}, timeout=15)
        c = r.json()["credits"]
        return int(c["plan_credits"]) - int(c["used_credits"]), int(c["plan_credits"])
    except Exception:
        return None


def _even(sents: list[str], t0: float, t1: float) -> list[dict]:
    """글자 수 비례로 문장 시간을 나눈다 — 단어 정렬을 믿을 수 없을 때 쓰는 안전판."""
    tot = sum(len(_strip(s)) for s in sents) or 1
    out, t = [], t0
    span = max(t1 - t0, 0.1)
    for s in sents:
        dt = span * len(_strip(s)) / tot
        out.append({"start": round(t, 3), "end": round(t + dt, 3), "text": s})
        t += dt
    return out


def _drifted(text: str, words: list[dict]) -> bool:
    """타입캐스트가 '읽은 형태'로 단어를 돌려주면(7,000→칠천, %→퍼센트, SK→에스케이)
    글자 수가 안 맞아 문장 경계가 밀린다. 어긋남이 크면 글자 추적을 포기한다."""
    a = len(_strip(text))
    b = sum(len(_strip(w.get("text", ""))) for w in words)
    return a == 0 or abs(a - b) > max(6, a * 0.10)


def _seal(rows: list[dict], dur: float) -> list[dict]:
    """큐를 서로 맞닿게 만든다. 문장 사이 호흡(0.5~1.1초)을 그대로 두면 화면에서
    자막이 통째로 사라지거나(ScenesV4 유예 0.5초) 엉뚱한 문장이 뜬다(Scenes.tsx 폴백)."""
    for i in range(len(rows) - 1):
        rows[i]["end"] = rows[i + 1]["start"] = round(max(rows[i]["end"], rows[i]["start"]), 3)
    for i in range(len(rows) - 1):
        rows[i]["end"] = rows[i + 1]["start"]
    if rows:
        rows[-1]["end"] = round(max(rows[-1]["end"], rows[-1]["start"], dur - 0.05), 3)
    return rows


def bounds_from_words(text: str, words: list[dict], dur: float) -> list[dict]:
    """단어 타임스탬프 → 문장 경계. 단어를 글자 수로 좇아가며 어느 문장에 속하는지 본다."""
    sents = sentences(text)
    if not sents:
        return []
    if not words or _drifted(text, words):
        t0 = float(words[0].get("start", 0.0)) if words else 0.0
        return _seal(_even(sents, t0, dur), dur)

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

    # 단어가 한 톨도 안 걸린 문장이 있으면 정렬을 믿을 수 없다 — 비례 배분으로 간다
    if any(x[0] < 0 for x in span):
        return _seal(_even(sents, float(words[0].get("start", 0.0)), dur), dur)

    out, prev_end = [], 0.0
    for i, s in enumerate(sents):
        st = max(span[i][0], prev_end)
        en = max(span[i][1], st)
        out.append({"start": round(st, 3), "end": round(en, 3), "text": s})
        prev_end = out[-1]["end"]
    return _seal(out, dur)


def cues_from_words(text: str, words: list[dict], bounds: list[dict], max_len: int = 55) -> list[dict]:
    """자막 큐 — 긴 문장은 실제 단어 시각에서 자른다(길이 비례 추정이 아니라).

    정렬을 믿을 수 없으면 빈 리스트를 준다. 부르는 쪽(tts.py)이 make_cues(bounds)로
    넘어가는데, bounds는 이미 맞닿아 있으니 구멍은 생기지 않는다."""
    if not words or _drifted(text, words):
        return []
    flat, pos = [], 0
    for w in words:
        n = len(_strip(w.get("text", "")))
        flat.append({"s": float(w.get("start", 0.0)), "e": float(w.get("end", 0.0)), "a": pos, "b": pos + n})
        pos += n

    cues: list[dict] = []
    base = 0
    for b in bounds:
        s = b["text"]
        lo, hi = base, base + len(_strip(s))
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
        off, prev = lo, b["start"]
        for j, x in enumerate(parts):
            n = len(_strip(x))
            seg = [w for w in flat if w["b"] > off and w["a"] < off + n and w["a"] >= lo and w["b"] <= hi]
            # 단어가 안 걸리면 문장 전체 시간을 주면 안 된다 — 순서가 뒤집힌다. 직전 큐 끝을 쓴다
            st = seg[0]["s"] if seg else prev
            en = seg[-1]["e"] if seg else b["end"]
            st = max(st, prev)
            cues.append({"start": round(st, 3), "end": round(max(en, st), 3), "text": x})
            prev = cues[-1]["end"]
            off += n
        if cues:
            cues[-1]["end"] = b["end"]

    for i in range(len(cues) - 1):                       # 장면 안에서도 맞닿게
        cues[i]["end"] = cues[i + 1]["start"] = round(max(cues[i]["start"], min(cues[i]["end"], cues[i + 1]["start"])), 3)
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
        body["prompt"]["previous_text"] = prev[-CTX:]
    if nxt:
        body["prompt"]["next_text"] = nxt[:CTX]

    d = _post(body)

    # 응답 모양을 믿지 않는다 — 조용히 0초짜리 장면이 나가는 게 제일 나쁘다
    audio = d.get("audio")
    if not isinstance(audio, str) or not audio:
        raise TypecastError(f"audio 없음 — 응답 키 {sorted(d)[:8]}")
    try:
        raw = base64.b64decode(audio)
    except Exception as e:
        raise TypecastError(f"audio 디코드 실패: {e}") from e
    if len(raw) < 1024:
        raise TypecastError(f"오디오가 {len(raw)}바이트뿐")
    dur = float(d.get("audio_duration") or 0.0)
    if not 0.3 <= dur <= 600:
        raise TypecastError(f"audio_duration 이상 — {d.get('audio_duration')!r}")
    words = d.get("words")
    if not isinstance(words, list):
        words = []
    words = [w for w in words if isinstance(w, dict) and "start" in w and "end" in w]

    with open(path, "wb") as f:
        f.write(raw)
    dur = round(dur, 3)
    return dur, bounds_from_words(text, words, dur), words


def billed_chars(text: str, prev: str = "", nxt: str = "") -> int:
    """이번 호출로 나갈 글자 수(1크레딧 = 1글자). 문맥이 과금 대상인지는 확인되지 않아
    보수적으로 함께 센다 — 예산을 실제보다 넉넉히 잡는 쪽이 안전하다."""
    return len(text) + len(prev[-CTX:]) + len(nxt[:CTX])
