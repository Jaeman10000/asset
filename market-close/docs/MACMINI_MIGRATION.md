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
python jobs/qa_script.py 20260923 --ed=kr        # 검사기가 도는가
python jobs/frame_check.py 20260923 --ed=kr      # ffmpeg·한글 폰트가 잡히는가
python jobs/build_info.py 20261006 --stage=script # 정보형 검사기
cd render && npx remotion compositions src/index.ts  # 렌더러 번들
```
네 개가 다 통과해야 옮긴 것이다. 하나라도 실패하면 그 자리에서 고친다.
