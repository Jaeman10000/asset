# market-close — 장 마감 자동 브리핑 (v2)

스펙: [SPEC.md](SPEC.md). 시안: https://claude.ai/code/artifact/e45baab5-bf73-46de-8c4f-42be00eb0316

## 실행 (Windows, backend 가상환경 재사용)
```powershell
cd C:\Users\Jeff\Documents\GitHub\asset\market-close\jobs
$py = "..\..\backend\.venv\Scripts\python.exe"

& $py run_day.py 20260905 --edition=us             # 05:40 자동: 아침편(직전 미국 세션, 월요일=금요일 세션+주간) → 06:00 업로드
& $py run_day.py 20260904 --edition=kr --stage=collect   # 15:41 이후: 키움 1분봉·전종목 수급 합산 / 테마 아카이브 / 미국
& $py run_day.py 20260904 --edition=kr --stage=krx       # 18:00 이후: 재수집 → compute → 다듬기 → TTS → 렌더 → review
# 옵션: --no-polish (Claude 다듬기 생략), --stage=render (녹음본 교체 후 렌더만)
```
자동 실행: 작업 스케줄러 `BamNatJang-Morning`(월~금 05:40) · `BamNatJang-Intraday`(월~금 14:00, 코스피 장중 잠정 수급) · `BamNatJang-EveningCollect`(월~금 15:41) · `BamNatJang-EveningBuild`(월~금 18:00). 재등록/삭제는 `jobs/schedule_tasks.ps1` 참고.
산출물: `out/YYYYMMDD/us/`, `out/YYYYMMDD/kr/` — `card.png`(1080×1350) `video.mp4`(1080×1920) `voice/*.mp3` `subs.srt` `caption.txt` `props.json` `review.html`
로그: `logs/YYYYMMDD.log`. 원자료: `data/YYYYMMDD/raw/*.json`, 계산 결과 `data/YYYYMMDD/computed.json`.

## 한 번만 해야 하는 것 (JJ)
1. **KRX 정보데이터시스템 계정** (data.krx.co.kr 회원가입, 무료) → 키체인 저장:
   ```powershell
   cd ..\..\backend
   .venv\Scripts\python.exe scripts\set_api_key.py krx id
   .venv\Scripts\python.exe scripts\set_api_key.py krx pw
   ```
   없으면 수급 장면(개인·외국인·기관·기타법인)이 "확정치 대기"로 비어 나간다. 키움은 이 값의 정의가 달라 대체 불가(SPEC §2).
2. **한국은행 ECOS 인증키** (ecos.bok.or.kr) → `set_api_key.py ecos key`. 없으면 환율 칸 비움.
3. TTS 음성 바꾸기: `set_api_key.py tts voice ko-KR-InJoonNeural` (기본 SunHi 여성). 확인 모드는 edge-tts, 정식 벤더는 SPEC §10.

## CapCut Pro 편집 (확인 모드 4주)
- `out/YYYYMMDD/` 폴더를 CapCut 새 프로젝트에 통째로 드래그. `video.mp4`를 그대로 쓰거나, 장면별로 자르고 `voice/s1~s5.mp3`·`subs.srt`(Captions > Add Captions → Apply to all)로 재조립.
- 편집본을 같은 이름(`video.mp4`, `card.png`)으로 덮어쓰면 게시기는 그 파일을 올린다.
- 초안(draft) 자동 생성은 CapCut 9.x 검증 뒤 도입(SPEC §10). CapCut 자동 업데이트는 꺼 둘 것(9.1.0 유지).

## v2.7 (2026-09-05 저녁)
- 14:00 장중 잠정 수급(`--stage=intraday`, 코스피 전 종목 ka10059 합산 → `raw/kiwoom_sum_1400.json`)을 마감과 비교해 수급 장면에 한 문장 추가: 부호 전환("오후 2시엔 외국인이 약 1,200억 순매도였는데, 마감엔 약 5천억 순매수로 돌아섰습니다") > 외국인·기관 막판 유입/이탈 > 개인. 화면 막대에 "14:00 → 마감" 표기.
- 아웃트로 고정 멘트: "미국장 마감은 매일 아침 7시 30분, 국장 마감은 매일 저녁 6시 30분에 올라옵니다" — 시각은 `data/publish_config.json`의 `upload_times`로 바꾼다(auto 모드 전환 때 실제 게시 시각으로).
- 벤치마크(경제사냥꾼) 반영: 날짜+이유 제목, 영상당 용어 풀이 1개(`glossary.py`), 관문마다 '볼 것'.

## v2.4 (2026-09-05) — 수급 중심 구조
- 대본: `narrate.py`(국장 s0–s6 / 미국 u0–u5), 원인·배경은 `polish.py`가 Google News 헤드라인(`collect_news.py`)에서 완곡하게 엮음. 인트로 10초(72자) 제한, 시각 서술 금지, 조건부 어시스트 문장(테마 단위).
- 미국 헤드라인 지수는 야후 공식 지수(`collect_us_index.py`: ^IXIC ^GSPC ^DJI ^SOX ^VIX). QQQ는 분봉·보조. 지표 실제값은 BLS API v1(`collect_us.py` `_bls_values`).
- 미국 휴장(예: 9/7 노동절)이면 다음 날 아침편은 자동 건너뜀(QQQ 세션 없음). 국장 휴장이면 저녁편 건너뜀(1분봉 없음). 11월~3월(EST)엔 미국 마감이 06:00 KST라 아침편이 마감+35분까지 자동 대기(약 06:35 시작).
- 스케줄러: 배터리 상태에서도 실행, 절전에서 깨움(WakeToRun). 조건: 노트북 전원 켜짐(잠금 화면 OK, 종료·최대 절전 X) + JJ 로그인 세션 유지.
- 조사 메모(SPEC v2.4): 세이브로 서학개미 순매수는 결제일 기준으로 미국 세션 D+2~4일 지연 → "어젯밤 서학개미"는 불가, 주간 항목 후보.

## 구조
```
jobs/     run_day.py  collect_kiwoom.py  collect_kiwoom_sum.py  collect_flows.py  collect_krx.py  collect_us.py  collect_us_kiwoom.py
          collect_us_index.py  collect_news.py  compute.py  compute_us.py  narrate.py  polish.py  tts.py  render.py  review.py
checks/   forbidden.py (금지어·완곡 표지·어시스트 검사)
render/   Remotion (src/Root.tsx Video.tsx Card.tsx Scenes.tsx ScenesUS.tsx Chart.tsx tokens.ts), public/fonts(Pretendard), public/voice
```

## 게시 자동화 (YouTube Shorts · TikTok · Threads) — v2.5
게시 코드는 `jobs/publish.py`, 인증은 `jobs/auth.py`. 비밀값은 전부 Windows 자격 증명 관리자에만 저장된다(파일에 없음).

```powershell
cd C:\Users\Jeff\Documents\GitHub\asset\market-close\jobs
$py = "..\..\backend\.venv\Scripts\python.exe"
& $py publish.py 20260907 us            # 드라이런: 제목·설명·캡션만 출력, 아무것도 안 올림
& $py publish.py 20260907 us --go       # 실제 게시(확인 모드: 유튜브 private · 틱톡 본인만 · 스레드 공개)
& $py publish.py 20260904 kr --go --targets=threads   # 일부만
& $py auth.py status                    # 연결 상태
```
결과는 `out/D/ed/publish.json`(플랫폼별 id·URL). 한 번 올린 대상은 다시 올리지 않는다.

### 모드 — `data/publish_config.json`
- `"mode": "confirm"` (기본, 첫 4주): 자동 실행은 영상까지만 만들고 게시하지 않는다. 아침 06:00·저녁 18:10에 `review.html`을 보고 위 `--go`를 실행한다. `--go`도 유튜브는 `publish_at` 시각(07:30/18:30)이 아직 안 지났으면 예약 공개로 올린다.
- `"mode": "auto"`: **제작 시각과 공개 시각이 다르다.** 05:40/18:00 작업이 렌더 직후 유튜브에 올리며 `publish_at`(07:30/18:30)으로 예약 공개를 걸고, 07:30/18:30 작업(`BamNatJang-PublishMorning/Evening`)이 틱톡·스레드를 그 시각에 게시한다. 공개 범위는 `youtube.privacy`(`private`→`public`), `tiktok.privacy`(`SELF_ONLY`→`PUBLIC_TO_EVERYONE`)로 바꾼다. 아웃트로의 "매일 아침 7시 30분 / 저녁 6시 30분" 멘트도 `publish_at`에서 자동으로 만든다.
- 유튜브 예약 공개(publishAt)는 **API 감사(Audit) 통과 뒤에만 실제로 풀린다.** 감사 전엔 private로 잠기므로 YouTube 스튜디오에서 '예약'을 직접 걸어야 한다(하루 1분). 감사 신청: YouTube API Services – Audit and Quota Extension Form (1~2주).

### 한 번만 하는 설정 (JJ, 각 15분) — 순서대로
**0. 리다이렉트 주소(틱톡·스레드용, https 필수).** 카드 이미지용 `assets` 브랜치에 `oauth.html`을 넣어 두었다. 브랜치를 올리고 GitHub Pages를 켠다.
```powershell
git -C C:\Users\Jeff\Documents\GitHub\asset\market-close\.assets push -u origin assets
```
그다음 github.com/Jaeman10000/asset → Settings → Pages → Source: Deploy from a branch, Branch: `assets` / (root) → 저장. 1~2분 뒤 `https://jaeman10000.github.io/asset/oauth.html`이 열리면 준비 끝. 이 주소가 아래 Redirect URI다.

**1. YouTube (Google Cloud, 무료).** https://console.cloud.google.com → 새 프로젝트(이름 bamnatjang) → 'API 및 서비스' → 라이브러리에서 **YouTube Data API v3** 사용 설정 → 'OAuth 동의 화면': 외부, 앱 이름 밤낮장, 지원 이메일 본인, 범위 추가 `youtube.upload`·`youtube.readonly`, 테스트 사용자에 본인 Gmail 추가 → **게시 상태를 '프로덕션'으로 전환**(테스트 상태면 토큰이 7일마다 끊긴다; '앱 확인' 경고는 무시해도 본인 계정은 동작) → '사용자 인증 정보' → OAuth 클라이언트 ID → 유형 **데스크톱 앱** → 클라이언트 ID·시크릿 복사. 그리고:
```powershell
& $py auth.py youtube     # ID·시크릿 붙여넣기 → 브라우저 허용 → 자동 완료
```
제약: API 감사(Audit) 전 프로젝트로 올린 영상은 **비공개로 잠긴다** → 확인 모드 동안은 YouTube 스튜디오에서 수동 공개. 완전 자동 공개를 원하면 'YouTube API Services – Audit and Quota Extension Form'을 제출(1~2주). 일 할당량 10,000 unit, 업로드 1건 1,600 → 하루 2편 OK.

**2. TikTok.** https://developers.tiktok.com → 앱 생성(이름 밤낮장, 플랫폼 Web) → 제품 추가 **Login Kit** + **Content Posting API** → Redirect URI에 0번 주소 등록 → Client Key·Secret 복사 → 앱 심사 제출(Direct Post 사용 사유: 자동 생성 마감 브리핑). 심사 전에는 `SELF_ONLY`(본인만 보임)로만 올라간다. 심사 통과 뒤 config를 `PUBLIC_TO_EVERYONE`으로.
```powershell
& $py auth.py tiktok      # 키 붙여넣기 → 브라우저 허용 → 리다이렉트된 주소 전체 붙여넣기
```

**3. Threads (Meta).** https://developers.facebook.com → 앱 만들기 → 사용 사례 **'Threads API 액세스'** → 앱 설정 → Threads API: Threads 앱 ID·시크릿 복사, **Redirect Callback URLs**에 0번 주소, Uninstall/Delete Callback도 같은 주소 → 앱 역할 → 'Threads 테스터'에 본인 Threads 계정 추가 → Threads 앱(휴대폰) 설정 → 웹사이트 권한 → 초대 수락. 개발 모드로도 본인 계정 게시는 된다.
```powershell
& $py auth.py threads     # ID·시크릿 붙여넣기 → 브라우저 허용 → 리다이렉트된 주소 전체 붙여넣기
```
이미지는 `assets` 브랜치 raw URL(공개 저장소)로 첨부된다. 텍스트 500자 제한은 코드가 자른다.

### 매일 흐름 (확인 모드)
06:00 `out\YYYYMMDD\us\review.html` 확인 → `publish.py YYYYMMDD us --go` → YouTube 스튜디오에서 공개 전환.
18:10 `out\YYYYMMDD\kr\review.html` 확인 → `publish.py YYYYMMDD kr --go`.
4주 뒤 `publish_config.json`의 mode를 `auto`로 바꾸면 사람 손 없이 돈다.
