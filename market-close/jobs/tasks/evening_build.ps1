# 평일 15:55 — JJ가 대본에 OK 하면 그 대본으로 음성·영상·검토·썸네일을 만든다.
# 왜(JJ 2026-09-16 밤): "내일 장 끝나면 대본부터 나한테 보여주고 내가 ok 하면 영상 제작하는거야."
#   15:40 대본 발송 → JJ OK → Claude 세션이 data\<날짜>\APPROVED 를 만든다 → 이 작업이 그걸 보고 제작.
#   JJ가 고칠 곳을 말하면 Claude 가 compute 를 다시 돌려 새 대본을 보여 주고, OK 가 오면 그때 APPROVED.
# 대본은 여기서 다시 뽑지 않는다(뽑으면 JJ가 본 대본과 달라질 수 있다).
# 16:45 까지 OK 가 없으면 만들지 않고 끝낸다(17:00 업로드에 못 맞춘다 — Claude 세션이 손으로 이어서 한다).
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$root = 'C:\Users\Jeff\Documents\GitHub\asset\market-close'
$py = 'C:\Users\Jeff\Documents\GitHub\asset\backend\.venv\Scripts\python.exe'
$log = Join-Path $root 'logs\task_EveningBuild.log'
$d = Get-Date -Format 'yyyyMMdd'
function Say($m) { "$(Get-Date -Format 'HH:mm:ss') [build] $m" | Out-File -Append -Encoding utf8 $log }
Set-Location (Join-Path $root 'jobs')
if (-not (Test-Path (Join-Path $root "data\$d\computed_kr.json"))) { Say '오늘 대본 없음(휴장 또는 수집 실패) → 건너뜀'; exit 0 }
$ok = Join-Path $root "data\$d\APPROVED"
# 세션이 손으로 제작하는 날(JJ가 대본을 직접 고쳐 확정한 날 등)은 data\<날짜>\MANUAL 을 먼저 만든다 → 이 작업은 손을 뗀다.
# 9/18: 세션이 APPROVED 를 만들고 바로 손으로 음성·렌더를 돌렸는데 이 작업도 APPROVED 를 보고 같이 돌아 렌더가 겹쳤다.
$manual = Join-Path $root "data\$d\MANUAL"
$deadline = (Get-Date).Date.AddHours(16).AddMinutes(45)
Say "JJ 승인 대기($ok)"
while (-not (Test-Path $ok)) {
    if (Test-Path $manual) { Say '세션이 손으로 제작(MANUAL) → 이 작업은 끝냄'; exit 0 }
    if ((Get-Date) -gt $deadline) { Say '16:45 까지 승인 없음 → 제작하지 않고 끝냄'; exit 0 }
    Start-Sleep -Seconds 20
}
if (Test-Path $manual) { Say '세션이 손으로 제작(MANUAL) → 이 작업은 끝냄'; exit 0 }
Say "승인 확인 → 제작 시작"
foreach ($st in 'tts', 'render', 'review') {
    if (Test-Path $manual) { Say "세션이 손으로 제작(MANUAL) → $st 부터 멈춤"; exit 0 }
    & $py run_day.py --edition=kr --stage=$st 2>&1 | Out-File -Append -Encoding utf8 $log
}
Say '제작 끝'
