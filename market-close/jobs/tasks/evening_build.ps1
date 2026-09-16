# 평일 15:55 — 15:40 에 JJ에게 보낸 그 대본으로 음성·영상·검토·썸네일만 만든다(대본을 다시 뽑지 않는다).
# 다시 뽑으면 그사이 늘어난 뉴스 때문에 JJ가 본 대본과 영상 대사가 달라질 수 있다.
# JJ가 대본을 고치라고 하면 compute 를 손으로 다시 돌린 뒤 tts·render·review 를 다시 한다.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$root = 'C:\Users\Jeff\Documents\GitHub\asset\market-close'
$py = 'C:\Users\Jeff\Documents\GitHub\asset\backend\.venv\Scripts\python.exe'
$log = Join-Path $root 'logs\task_EveningBuild.log'
$d = Get-Date -Format 'yyyyMMdd'
Set-Location (Join-Path $root 'jobs')
if (-not (Test-Path (Join-Path $root "data\$d\computed_kr.json"))) {
    "$(Get-Date -Format 'HH:mm:ss') [build] 오늘 대본 없음(휴장 또는 수집 실패) → 건너뜀" | Out-File -Append -Encoding utf8 $log
    exit 0
}
foreach ($st in 'tts', 'render', 'review') {
    & $py run_day.py --edition=kr --stage=$st 2>&1 | Out-File -Append -Encoding utf8 $log
}
