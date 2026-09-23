# 맥미니(M4)로 옮기기 — 준비와 순서 (2026-09-24)

JJ: *"이제부터 집에서 맥미니를 안 끄고 계속 돌릴 거고 핸드폰이나 노트북으로 원격으로 시킬 수 있어.
시간이 오래 걸려도 계속 수정할 수 있게 됐다. 그걸 위해서 뭘 해야 하냐?"*

## 0. 결론 — **설치 지시는 맥미니에서 친다**

내가 그 기계 안에서 돌아야 설치하고, 돌려 보고, 틀린 걸 고칠 수 있다.
윈도우에서 치면 나는 맥미니 파일에 손을 못 대고 **안내문만** 쓸 수 있다.

**순서: ① 윈도우에서 여기까지 푸시(JJ 승인 필요) → ② 맥미니에서 Claude Code 열고 이 문서를 가리키며 시작.**

## 1. 옮기기 전에 윈도우에서 할 것

- [ ] **푸시** — 지금 로컬에만 있는 변경이 많다(9/20~9/24 작업 전부). 푸시 안 하면 맥미니가 옛 코드를 받는다.
- [ ] `data/` 가 저장소에 들어가는지 확인 — 수급 원자료·ledger·buybacks 는 맥미니에도 있어야 한다.
      (용량이 크면 따로 복사. **`ledger.json`·`buybacks.json`·`script_history.json` 은 반드시 옮긴다** — 채점과 '전 편과 겹침' 검사가 이걸 본다.)

## 2. 맥미니에서 설치

| 순서 | 할 것 | 확인 |
|---|---|---|
| 1 | Xcode CLT · Homebrew · git + **깃허브 자격증명**(`git push` 용, JJ가 직접) | `git --version` · 빈 커밋 push 테스트 |
| 1b | `gh auth login` — **PR 패널 쓸 때만**. 지금은 master 직접 푸시라 없어도 된다(JJ가 직접) | `gh auth status` |
| 2 | Python 3.12+ → `backend/.venv` 만들고 requirements 설치 | `python -c "import httpx, PIL"` |
| 3 | Node 20+ → `market-close/render` 에서 `npm ci` | `@remotion/compositor-darwin-arm64` 가 깔린다 |
| 4 | **한글 폰트** | `_common.korean_font()` 가 애플고딕을 찾는다. 없으면 나눔고딕 설치 |
| 5 | **키움·타입캐스트 키** — JJ가 **직접** 넣는다(`backend/scripts/set_api_key.py`). 키는 대화에 절대 안 넣는다 | macOS 키체인 |
| 6 | 크롬 + Claude in Chrome 확장, **JJ가 직접** 누가샀나(cjm8905) 로그인 | 업로드용. 비밀번호·본인인증은 내가 안 한다 |
| 7 | 예약 작업 이식(아래 3절) | |
| 8 | **안 꺼지게** — 시스템 설정 > 에너지에서 잠자기 끄기. **JJ가 직접**(전원 설정은 내가 안 건드린다) | |

### 이미 해 둔 것 (2026-09-24)
윈도우 전용 경로 5곳을 OS 무관으로 바꿔 뒀다 — 맥미니에서 그대로 돈다.

| 파일 | 전 | 후 |
|---|---|---|
| `frame_check.py` | `compositor-win32-x64-msvc/ffmpeg.exe` | `_common.ffmpeg_path()` — `compositor-*` 아무거나 찾는다 |
| `frame_check.py` | `C:/Windows/Fonts/malgunbd.ttf` | `_common.korean_font()` — 윈도우/맥/리눅스 |
| `qa_script.py` | 같은 ffmpeg 절대경로 | `_common.ffmpeg_path()` |
| `collect_refs.py` | `.venv/Scripts/yt-dlp.exe` | `_common.venv_bin("yt-dlp")` |
| `brief_try.py`·`hunter_try.py` | 세션별 스크래치 절대경로 | `_common.scratch_dir(...)` |

## 3. 예약 작업 이식

### (a) 윈도우 작업 스케줄러 5개 → **launchd**
`~/Library/LaunchAgents/com.nugasatna.<이름>.plist` 로 만든다.

| 이름 | 시각 | 하는 일 |
|---|---|---|
| `BamNatJang-EveningCollect` | 평일 15:31 | 수집+대본(15:40:45 확정 수급까지 기다림) |
| `BamNatJang-EveningBuild` | 평일 15:55 | `APPROVED` 보고 음성·영상(16:45까지 없으면 안 만듦) |
| `BamNatJang-Intraday` | 평일 14:00 | 장중 정리 |
| `BamNatJang-Morning` | 매일 05:40 | 아침 수집 |
| `BamNatJang-PublishEvening` | 평일 17:00 | 게시 |

> launchd 는 잠자기 중엔 안 뜬다 → **잠자기 끄기가 전제**(2절 8번). `StartCalendarInterval` 사용.

### (b) Claude 예약 작업 14개
지금 살아 있는 것: `kr-weekly-*`(토 4개) · `us-weekly-*`(일 4개) · `nugasatna-script-preview`(평일 15:46) ·
`nugasatna-info-scout`(매일 19시) · `nugasatna-event-watch`(휴장일 08:00). 나머지 3개는 지난 1회성(꺼짐).

이건 **맥미니의 Claude Code 세션에서 다시 만든다** — 작업 정의(`SKILL.md`)는 `~/.claude/scheduled-tasks/` 에 있으니 그 폴더를 옮기거나 다시 만든다.

## 4. 원격으로 시키기

맥미니 Claude Code 세션에서 **Remote Control 을 켜면** 폰·노트북에서 그 세션에 지시할 수 있다.
JJ가 폰으로 "오늘 대본 보여줘" 하면 맥미니가 받아서 돌리고 결과를 보낸다.

- 맥미니는 계속 켜져 있으니 **긴 작업(렌더 8분, 전 종목 수급 스캔, 롱폼)을 걸어 두고 나가도 된다.**
- 지금 윈도우에서 겪던 "시간 없어서 그냥 올렸다" 가 없어진다 — **프레임 50장 다 보고 고치고 다시 렌더**할 시간이 생긴다.

## 5. 옮긴 뒤 반드시 통과시킬 검증

```
PY=../backend/.venv/bin/python                               # market-close/ 에서
$PY jobs/qa_script.py script --kind day --date 20260923      # 검사기가 도는가 (평일편 = --kind day)
$PY jobs/frame_check.py 20260923 --ed=kr                     # ffmpeg·한글 폰트 (out/<날짜>/kr/video.mp4 가 있어야 함)
$PY jobs/build_info.py 20261006 --stage=script               # 정보형 검사기
cd render && npx remotion compositions src/index.ts          # 렌더러 번들
```
네 개가 다 통과해야 옮긴 것이다. 하나라도 실패하면 그 자리에서 고친다.
(처음 문서의 `qa_script.py 20260923 --ed=kr` 는 실제 인자와 달랐다 — 위가 맞다.)

## 6. 맥미니 설치 기록 (2026-09-24 새벽, 맥미니 세션에서)

**Homebrew 는 안 깔았다** — 설치에 sudo 비밀번호가 필요한데 그건 JJ만 친다. 비밀번호 없이 되는 길로 갔다:

| 것 | 어떻게 | 어디 |
|---|---|---|
| Python 3.12.14 | `uv`(astral) | `~/.local/bin/uv` → `backend/.venv` |
| 파이썬 패키지 | `backend/requirements*.txt` + **`market-close/requirements.txt`(새로 만듦)** | 원래 requirements 에 없던 8개: pillow·yt-dlp·edge-tts·mutagen·numpy·psutil·pykrx·requests |
| Node 22.23.2 | 공식 tarball | `~/.local/node` (PATH 는 `~/.zprofile` 에 넣음) |
| 렌더러 | `npm ci` | `@remotion/compositor-darwin-arm64` 깔림 |
| 한글 폰트 | 이미 있음 | `/System/Library/Fonts/AppleSDGothicNeo.ttc` |

**고친 것:** 맥용 remotion ffmpeg 는 옆의 `libav*.dylib` 를 못 찾아 바로 죽는다(`Library not loaded: libavdevice.dylib`).
`_common.ffmpeg_path()` 가 맥에서 `DYLD_LIBRARY_PATH` 를 그 폴더로 잡아 준다 → `frame_check`·`qa_script frames` 가 돈다.

**검증 결과:** 네 개 모두 돈다. qa 는 9/23 옛 대본에서 7건 실패 — 전면 감사 때 잡힌 것(번호 막대 `bar:0`·'코스피 넷부터')이 그대로 걸린 것이라 검사기는 정상.
렌더: 9/23 편(172초)을 무음 mp3 로 렌더해 보니 **1분 43초**(윈도우 약 8분). frame_check 50장 한글·화면 정상. 시험 영상·무음 파일은 지웠다.

### 아직 JJ가 할 것 (내가 못 하거나 하면 안 되는 것)
1. **키 넣기** — `cd backend && .venv/bin/python scripts/set_api_key.py <이름> <항목>` 로 macOS 키체인에. 코드가 읽는 항목:
   `kiwoom: app_key·app_secret·is_mock·account_no` · `typecast: api_key` · `krx: id·pw` · `ecos: key` · `threads: access_token·redirect_uri` · `youtube: client_id·client_secret·refresh_token`
   ⚠️ **음성 설정도 키체인에 있다** — `tts: engine·voice·typecast_voice·typecast_tempo·typecast_pause·typecast_qpause·typecast_us`, `brand: name`. 윈도우 값을 그대로 옮기지 않으면 **목소리·속도가 달라진다.**
2. **BGM 복사** — `render/public/bgm/*.wav` 는 `.gitignore` 라 저장소에 없다. 윈도우에서 `bgm_B_dark_arp.wav` 를 같은 자리로. **없으면 `render.py` 가 BGM 없이 조용히 렌더한다.**
3. `~/.claude/scheduled-tasks/` 폴더(Claude 예약 작업 정의) — 맥미니엔 없다. 윈도우에서 복사해 오면 그걸로 다시 만든다.
4. 크롬 + Claude in Chrome, 유튜브(cjm8905) 로그인 · 잠자기 끄기 · (원하면) Homebrew·`gh auth login`.
5. **윈도우 작업 스케줄러 5개를 끈 뒤** 맥에서 `zsh jobs/schedule_tasks_mac.sh` — launchd 5개 등록(둘 다 켜 두면 수집·제작이 두 번 돈다). 해제는 `--remove`.

### 9/23 편 수집→대본 시험 (2026-09-24 02:27, 저장소 복사본에서 — 원본 데이터·`script_history` 는 안 건드림)
- **키움 실전 연결 정상**(토큰·ka10001). 수집 7분, 대본 16초. 코스피 종가 7,080.92 원본과 같음.
  4주체 합산은 1% 안쪽 차이(개인 −14,543 vs 나간 편 −14,397억) — 하루 뒤 다시 받아 키움 값이 조금 바뀐 것.
- 브리핑 형식이 검사에 3번 걸려 **A+ 로 떨어졌다**(s1 질문이 대사에 없음 · s2 기타법인 두 문장·'101%'). **맥 문제가 아니다** —
  윈도우도 9/23 당일 똑같이 떨어졌다(`computed_kr_fallback_backup.json`). 생성기 쪽 숙제로 따로 본다.
- **자금 흐름 아카이브가 맥에 없다** — `~/Documents/VitalityNexus/flow`(윈도우 `문서\VitalityNexus\flow`). 'N일째'·직전 거래일·테마 판정이 이걸 본다.
  **윈도우에서 폴더째 복사해야 한다**(안 하면 첫날 100일치만 새로 받는다 — 윈도우엔 수백 일치).
- 비어 있는 키: `krx:id·pw`(지수 확정치·환율 → 없으면 키움 일봉으로 대신, 환율 없음) · `ecos:key` · `threads`·`youtube`(업로드는 크롬으로 하니 당장은 안 씀) · `tts:typecast_pause·qpause`.
- **launchd 스크립트를 고쳤다**: 윈도우 실제 저녁 작업은 `run_day.py` 가 아니라 `tasks/evening_collect.ps1`·`evening_build.ps1` 래퍼였다.
  옛 `schedule_tasks.ps1` 대로 `--stage=krx` 를 걸면 **승인 없이 음성·렌더까지 간다.** 맥 판 `tasks/evening_collect.sh`·`evening_build.sh` 를 만들어
  launchd 가 그걸 부르게 했다(대본 없음→건너뜀 · MANUAL→비킴 · 승인 없음→16:45 까지 기다렸다 안 만듦, 시험함).
- **Claude 예약 작업은 폴더만 옮겨 왔지 등록은 안 돼 있다.** `SKILL.md` 안의 경로가 전부 윈도우(`C:\Users\Jeff\…`, `.ps1`)라 맥 경로로 바꿔서 다시 만들어야 한다.

### 등록 (2026-09-24, 윈도우 작업 스케줄러 5개 Disabled 확인 뒤)
- **launchd 5개 등록함** — `launchctl list | grep nugasatna` 로 5개 확인.
- **Claude 예약 작업 11개: `SKILL.md` 경로는 맥으로 바꿈**(`/Users/jm/asset/...`, `.venv/bin/python`, `tasks/*.sh`, launchd 이름, `compositor-darwin-arm64`, `npx`, 크롬은 `open -a "Google Chrome"`). 원본은 윈도우에 그대로.
  **등록 자체는 CLI 세션에서 못 한다** — 등록부는 데스크톱 앱(`~/Library/Application Support/Claude/claude-code-sessions/…/scheduled-tasks.json`)이 관리하고,
  CLI 의 `CronCreate` 는 세션이 끝나면 사라진다(7일 만료). 데스크톱 앱의 Claude Code 세션에서 아래 표대로 만든다.
  빼는 것: 지난 1회성 3개(`nugasatna-info-threads-20260919`·`…-20260920`·`nugasatna-info3-threads-20260920`), `betrader-daily-mustdo`(다른 프로젝트).

| 작업 | cron (로컬 시각) | 뜻 |
|---|---|---|
| kr-weekly-prep | `0 9 * * 6` | 토 09:00 |
| kr-weekly-script | `30 10 * * 6` | 토 10:30 |
| kr-weekly-video | `4 11 * * 6` | 토 11:04 |
| kr-weekly-threads | `2 12 * * 6` | 토 12:02 |
| us-weekly-prep | `40 8 * * 0` | 일 08:40 |
| us-weekly-script | `30 10 * * 0` | 일 10:30 |
| us-weekly-video | `4 11 * * 0` | 일 11:04 |
| us-weekly-threads | `2 12 * * 0` | 일 12:02 |
| nugasatna-script-preview | `46 15 * * 1-5` | 평일 15:46 |
| nugasatna-info-scout | `0 19 * * *` | 매일 19:00 |
| nugasatna-event-watch | `0 8 * * *` | 매일 08:00 — 휴장일인지는 작업이 스스로 판단 |

> 급한 것: 추석 연휴 9/24(목)~9/27(일). **9/26(토) 09:00 kr-weekly-prep** 이 떠야 그 주 주간 결산이 나온다(주간편은 그날 만든다 — `data/weekly` 마지막이 20260919).
> 9/27(일) 미국 주간편도 같다. 평일 국장 마감 파이프라인은 **9/28(월)** 부터.
