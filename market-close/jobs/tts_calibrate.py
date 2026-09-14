"""보이스 말 속도 보정 — 목소리를 바꾸면 반드시 돌린다.

왜 필요한가(2026-09-14): 김건에 맞춰 둔 tempo 0.78을 무열에 그대로 썼더니
6.3자/초로 축 처졌다. 보이스마다 기본 속도가 다르다 — 같은 tempo가 같은 속도가 아니다.

  김건  tempo 1.0 → 9.3자/초   (0.82에서 7.5자/초)
  무열  tempo 1.0 → 7.8자/초   (0.78이면 6.3자/초 — 너무 느리다)

사용법 (market-close/jobs 에서):
  python tts_calibrate.py                      # 지금 채널 보이스를 잰다
  python tts_calibrate.py tc_648aaee9248bcd…   # 특정 보이스를 잰다
  python tts_calibrate.py tc_… 7.5             # 목표 자/초를 정해서 tempo 를 뽑는다

두 문장(약 100자)을 tempo 1.0으로 한 번 만들어 재므로 100크레딧쯤 든다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import tts_typecast as tc
from app.keychain import get_api_key

# 실제 대본에서 뽑은 문장 — 숫자·영문이 섞여 있어야 체감 속도가 맞는다
SAMPLE = ("가장 많이 산 쪽은 개인입니다. 약 1조 9천억을 샀습니다. "
          "그런데 외국인은 하루 내내 팔았을까요? 오후 2시까진 5천억이 안 됐습니다.")
TARGET_CPS = 7.5      # 평일편 기준. 7.2는 edge 시절 속도, 7.8은 무열 기본


def measure(voice: str, tempo: float = 1.0) -> float:
    """그 보이스·그 속도의 초당 글자 수."""
    with tempfile.TemporaryDirectory() as d:
        dur, _b, _w = tc.synth(SAMPLE, Path(d) / "cal.mp3", voice, tempo=tempo)
    return len(SAMPLE) / dur


def main() -> None:
    voice = sys.argv[1] if len(sys.argv) > 1 else (get_api_key("tts", "typecast_voice") or tc.DEFAULT_VOICE)
    target = float(sys.argv[2]) if len(sys.argv) > 2 else TARGET_CPS
    base = measure(voice)
    tempo = round(base / target, 2)
    now = get_api_key("tts", "typecast_tempo") or "1.0"
    print(f"보이스     {voice}")
    print(f"기본 속도  tempo 1.0 에서 {base:.1f}자/초")
    print(f"목표 {target:.1f}자/초 → tempo {tempo}")
    print(f"지금 설정  tempo {now} (= 약 {base / float(now):.1f}자/초)")
    if abs(float(now) - tempo) > 0.05:
        print()
        print("  ⚠ 지금 설정이 이 보이스에 안 맞는다. 바꾸려면:")
        print(f"  backend/.venv/Scripts/python.exe backend/scripts/set_api_key.py tts typecast_tempo {tempo}")
    print()
    print(f"평일편 778자 기준 말하는 시간 약 {778 / target:.0f}초 (+ 문장 쉼·장면 여유)")


if __name__ == "__main__":
    main()
