#!/bin/zsh
# 누가샀나 자동 실행 등록 (맥미니 launchd) — 윈도우 schedule_tasks.ps1 과 같은 5개.
#   com.nugasatna.morning          월~금 05:40  run_day.py --edition=us
#   com.nugasatna.intraday         월~금 14:00  --edition=kr --stage=intraday
#   com.nugasatna.evening-collect  월~금 15:31  tasks/evening_collect.sh — 수집(15:40:45 까지 기다림) → 대본(compute)
#   com.nugasatna.evening-build    월~금 15:55  tasks/evening_build.sh   — APPROVED 를 16:45 까지 기다렸다 tts·render·review
#   com.nugasatna.publish-evening  월~금 17:00  --edition=kr --stage=publish
# ⚠ 저녁 둘은 run_day.py 를 바로 부르면 안 된다 — 윈도우도 실제로는 tasks/*.ps1 래퍼를 돌렸다.
#   (옛 schedule_tasks.ps1 의 '--stage=krx' 를 그대로 옮기면 승인 없이 음성·렌더까지 가 버린다 — 2026-09-24 이관 때 잡음)
# launchd 는 잠자기 중엔 안 뜬다 — 잠자기 끄기가 전제(MACMINI_MIGRATION.md 2절 8번, JJ가 직접).
# 등록:  zsh jobs/schedule_tasks_mac.sh        해제: zsh jobs/schedule_tasks_mac.sh --remove
# 로그:  market-close/logs/task_<이름>.log
set -e
MC="$(cd "$(dirname "$0")/.." && pwd)"
PY="$MC/../backend/.venv/bin/python"
LA="$HOME/Library/LaunchAgents"
mkdir -p "$LA" "$MC/logs"

jobs=(
  "morning|05:40|--edition=us"
  "intraday|14:00|--edition=kr --stage=intraday"
  "evening-collect|15:31|sh:tasks/evening_collect.sh"
  "evening-build|15:55|sh:tasks/evening_build.sh"
  "publish-evening|17:00|--edition=kr --stage=publish"
)

for j in "${jobs[@]}"; do
  name="${j%%|*}"; rest="${j#*|}"; at="${rest%%|*}"; argv="${rest#*|}"
  label="com.nugasatna.$name"; plist="$LA/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  if [[ "$1" == "--remove" ]]; then rm -f "$plist"; echo "해제: $label"; continue; fi
  h=$((10#${at%%:*})); m=$((10#${at##*:}))
  cal=""
  for wd in 1 2 3 4 5; do
    cal+="<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer></dict>"
  done
  if [[ "$argv" == sh:* ]]; then
    args="<string>/bin/zsh</string><string>$MC/jobs/${argv#sh:}</string>"
  else
    args="<string>$PY</string><string>run_day.py</string>"
    for a in ${=argv}; do args+="<string>$a</string>"; done
  fi
  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>$args</array>
  <key>WorkingDirectory</key><string>$MC/jobs</string>
  <key>EnvironmentVariables</key><dict>
    <key>PYTHONIOENCODING</key><string>utf-8</string>
    <key>PATH</key><string>$HOME/.local/node/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartCalendarInterval</key><array>$cal</array>
  <key>StandardOutPath</key><string>$MC/logs/task_$name.log</string>
  <key>StandardErrorPath</key><string>$MC/logs/task_$name.log</string>
</dict></plist>
EOF
  plutil -lint "$plist" >/dev/null
  launchctl bootstrap "gui/$(id -u)" "$plist"
  echo "등록: $label  월~금 $at  → $argv"
done
launchctl list | grep nugasatna || true
