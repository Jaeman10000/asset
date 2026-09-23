#!/bin/zsh
# 평일 15:31 — 수집(run_day 가 15:40:45 확정 수급까지 기다린다) 뒤 대본(compute)까지. evening_collect.ps1 의 맥 판.
export PYTHONIOENCODING=utf-8
MC="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$MC/../backend/.venv/bin/python"
LOG="$MC/logs/task_evening-collect.log"
d=$(date +%Y%m%d)
cd "$MC/jobs"
"$PY" run_day.py --edition=kr --stage=collect >> "$LOG" 2>&1
if [[ -f "$MC/data/$d/raw/kiwoom_sum.json" ]]; then
  "$PY" run_day.py --edition=kr --stage=compute >> "$LOG" 2>&1
fi
