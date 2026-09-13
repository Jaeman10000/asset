# 밤낮장 자동 실행 등록 (Windows 작업 스케줄러). 한 번 실행하면 아래 3개 작업이 생긴다.
#   BamNatJang-Morning   월~금 05:40 (검색 피크 05~07시 대비, 06시 업로드용)  직전 미국 세션 (월=금요일 세션+주간 일정, 토·일 없음). 미국 휴장이면 코드가 스스로 건너뜀.
#   BamNatJang-Intraday  월~금 14:00  코스피 전 종목 장중 잠정 수급(마감과 비교해 '장중 대비 마감' 문장)
#   BamNatJang-EveningCollect 월~금 15:41  국내 1분봉·전종목 수급·테마 아카이브. 국내 휴장이면 건너뜀.
#   BamNatJang-EveningBuild 월~금 15:55  마감시황 헤드라인 수집 → 계산 → 다듬기 → TTS → 렌더 → review.html (16:10쯤 완성)
#   BamNatJang-PublishEvening 월~금 16:30  국장편 게시(auto 모드일 때만; 유튜브는 제작 직후 publishAt 17:00 예약). 미국편은 개인 확인용이라 게시 없음.
# 삭제: schtasks /Delete /TN "BamNatJang-Morning" /F  (나머지도 같은 식)
# 토요일을 빼려면: schtasks /Change 대신 이 파일의 아침편 -DaysOfWeek 에서 Saturday 제거 후 재실행.
$ErrorActionPreference = "Stop"
$py   = "C:\Users\Jeff\Documents\GitHub\asset\backend\.venv\Scripts\python.exe"
$jobs = "C:\Users\Jeff\Documents\GitHub\asset\market-close\jobs"
$logs = "C:\Users\Jeff\Documents\GitHub\asset\market-close\logs"
New-Item -ItemType Directory -Force $logs | Out-Null

function Register-Job($name, $argv, $days, $time) {
    $cmd = "`$env:PYTHONIOENCODING='utf-8'; Set-Location '$jobs'; & '$py' run_day.py $argv 2>&1 | Out-File -Append -Encoding utf8 '$logs\task_$($name.Replace('BamNatJang-','')).log'"
    $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $time
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "밤낮장 자동 제작 ($argv)" -Force | Out-Null
    "등록: $name  $($days -join ',')  $time  → run_day.py $argv"
}

Register-Job "BamNatJang-Morning"   "--edition=us"                  @("Monday","Tuesday","Wednesday","Thursday","Friday") "05:40"
Register-Job "BamNatJang-Intraday" "--edition=kr --stage=intraday"    @("Monday","Tuesday","Wednesday","Thursday","Friday") "14:00"
Register-Job "BamNatJang-EveningCollect" "--edition=kr --stage=collect"  @("Monday","Tuesday","Wednesday","Thursday","Friday") "15:41"
Register-Job "BamNatJang-EveningBuild" "--edition=kr --stage=krx"      @("Monday","Tuesday","Wednesday","Thursday","Friday") "15:55"
Register-Job "BamNatJang-PublishEvening" "--edition=kr --stage=publish" @("Monday","Tuesday","Wednesday","Thursday","Friday") "16:30"
Get-ScheduledTask -TaskName "BamNatJang-*" | Select-Object TaskName, State | Format-Table -AutoSize
