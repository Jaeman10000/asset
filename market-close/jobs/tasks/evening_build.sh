#!/bin/zsh
# 평일 15:55 — JJ 승인(data/<날짜>/APPROVED)을 16:45 까지 기다렸다 음성·렌더·리뷰. MANUAL 이 있으면 손 제작이니 비킨다.
# evening_build.ps1 의 맥 판. **APPROVED 없이는 절대 만들지 않는다.**
export PYTHONIOENCODING=utf-8
MC="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$MC/../backend/.venv/bin/python"
LOG="$MC/logs/task_evening-build.log"
d=$(date +%Y%m%d)
say() { echo "$(date +%H:%M:%S) [build] $1" >> "$LOG"; }
cd "$MC/jobs"
[[ -f "$MC/data/$d/computed_kr.json" ]] || { say '오늘 대본 없음(휴장 또는 수집 실패) → 건너뜀'; exit 0; }
OK="$MC/data/$d/APPROVED"; MANUAL="$MC/data/$d/MANUAL"
deadline=$(date -j -f "%Y%m%d%H%M%S" "${d}164500" +%s)
say "JJ 승인 대기($OK)"
while [[ ! -f "$OK" ]]; do
  [[ -f "$MANUAL" ]] && { say '세션이 손으로 제작(MANUAL) → 이 작업은 끝냄'; exit 0; }
  (( $(date +%s) > deadline )) && { say '16:45 까지 승인 없음 → 제작하지 않고 끝냄'; exit 0; }
  sleep 20
done
[[ -f "$MANUAL" ]] && { say '세션이 손으로 제작(MANUAL) → 이 작업은 끝냄'; exit 0; }
say '승인 확인 → 제작 시작'
for st in tts render review; do
  [[ -f "$MANUAL" ]] && { say "세션이 손으로 제작(MANUAL) → $st 부터 멈춤"; exit 0; }
  "$PY" run_day.py --edition=kr --stage=$st >> "$LOG" 2>&1
done
say '제작 끝'
