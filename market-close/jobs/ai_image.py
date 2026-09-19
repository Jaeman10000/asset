"""AI 배경·썸네일 이미지 — 이슈 해설편 전용(JJ 2026-09-19 "배경화면과 썸네일에 AI를 이용해서 다른 느낌으로").

키는 Windows 자격증명 관리자에만(backend/scripts/set_api_key.py). 먼저 있는 쪽을 쓴다:
  openai:api_key  → gpt-image-1 (1024x1536 세로)
  gemini:api_key  → imagen-4.0-generate-001 (9:16)
키가 없으면 None 을 돌려주고, 호출한 쪽은 기본 배경(도시·차트)으로 만든다(영상은 나간다).

규칙: 사람 얼굴·실제 회사 로고·상표·글자는 넣지 않는다(프롬프트 끝에 붙인다). 화면 글자는 우리가 위에 얹는다.
사용: python ai_image.py "프롬프트" 출력.png
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

TAIL = (" Vertical 9:16 composition, cinematic, dark moody background with deep navy and black tones, soft neon accent light,"
        " lots of empty dark space in the upper half for large overlaid text, no text, no letters, no numbers, no logos, no brand marks,"
        " no real people's faces, no watermark.")


def _key(provider: str) -> str | None:
    try:
        from app.keychain import get_api_key
        k = get_api_key(provider, "api_key")
        return k.strip() if k else None
    except Exception:
        return None


def _post(url: str, body: dict, headers: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def generate(prompt: str, out: Path) -> Path | None:
    """이미지 하나를 만들어 out 에 쓴다. 키가 없거나 실패하면 None."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    full = prompt.strip() + TAIL
    k = _key("openai")
    if k:
        try:
            j = _post("https://api.openai.com/v1/images/generations",
                      {"model": "gpt-image-1", "prompt": full, "size": "1024x1536", "n": 1}, {"Authorization": f"Bearer {k}"})
            out.write_bytes(base64.b64decode(j["data"][0]["b64_json"]))
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[ai_image] openai 실패: {e}", file=sys.stderr)
    k = _key("gemini")
    if k:
        try:
            j = _post(f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={k}",
                      {"instances": [{"prompt": full}], "parameters": {"sampleCount": 1, "aspectRatio": "9:16"}}, {})
            out.write_bytes(base64.b64decode(j["predictions"][0]["bytesBase64Encoded"]))
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[ai_image] gemini 실패: {e}", file=sys.stderr)
    return None


def available() -> str | None:
    return "openai" if _key("openai") else "gemini" if _key("gemini") else None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용: python ai_image.py \"프롬프트\" 출력.png   (키:", available() or "없음", ")")
        sys.exit(1)
    r = generate(sys.argv[1], Path(sys.argv[2]))
    print(r or "실패/키 없음")
