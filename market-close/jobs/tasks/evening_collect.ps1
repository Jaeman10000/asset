# 평일 15:31 — 수집(약 8분) 뒤 바로 대본까지(compute). 음성·영상은 만들지 않는다.
# 왜(JJ 2026-09-16 밤): "대본을 최대한 빨리 나에게 먼저 보여줘. 3시 40분 정도에."
#   수집 8분 = 업종 80초 + 코스피 전 종목 127초 + 코스닥 전 종목 240초 → 15:39 수집 끝, 15:40 대본.
# 15:40 에 Claude 예약 작업(nugasatna-script-preview)이 이 대본을 JJ에게 보낸다.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$root = 'C:\Users\Jeff\Documents\GitHub\asset\market-close'
$py = 'C:\Users\Jeff\Documents\GitHub\asset\backend\.venv\Scripts\python.exe'
$log = Join-Path $root 'logs\task_EveningCollect.log'
$d = Get-Date -Format 'yyyyMMdd'
Set-Location (Join-Path $root 'jobs')
& $py run_day.py --edition=kr --stage=collect 2>&1 | Out-File -Append -Encoding utf8 $log
# 휴장이면 collect 가 kiwoom_sum 을 만들지 않는다 — 그날은 대본도 만들지 않는다
if (Test-Path (Join-Path $root "data\$d\raw\kiwoom_sum.json")) {
    & $py run_day.py --edition=kr --stage=compute 2>&1 | Out-File -Append -Encoding utf8 $log
}
