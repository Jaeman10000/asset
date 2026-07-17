# VITALITY NEXUS — Organic Core (3D 심장 씬)

핸드오프 꾸러미(`../organic-core/`)의 스타터 코드를 실제로 통합한 Vite + React 19 + R3F v9 프로젝트.
스펙 전체는 `../VITALITY_NEXUS_SPEC.md`, 통합 가이드는 `../organic-core/GUIDE.md` 참고.

## 실행 (프론트 + 백엔드 둘 다 필요)

대시보드는 백엔드(`../backend`, localhost:8787)를 폴링해서 실 포트폴리오 데이터를
띄운다. 두 개를 같이 실행한다:

```bash
# 터미널 1 — 백엔드
cd ../backend
.venv/Scripts/python -m uvicorn app.main:app --port 8787 --reload

# 터미널 2 — 프론트엔드
npm install
npm run dev        # http://localhost:5173
```

백엔드가 없어도 프론트는 뜨지만 "백엔드 오프라인" 안내가 나온다. 개발 중
`/api` 요청은 Vite 프록시가 8787로 넘긴다(vite.config.ts). 프로덕션 Tauri
빌드에서는 `VITE_API_BASE` 환경변수로 백엔드 주소를 지정한다.

### 데이터 흐름

- 백엔드가 6개 소스(수동입력/Yahoo섹터/암호화폐/주식시세 + 거래소 계좌)를 합쳐
  `PortfolioSnapshot` 하나로 반환 → 프론트가 7초마다 폴링(`src/store/portfolio.ts`)
- **API 키 없이도** 보유종목을 UI로 추가하면(우하단 "보유종목 편집") 대시보드가
  채워진다 — 암호화폐/주식 현재가는 공개 시세로 자동 갱신
- 상태 구분: 연결(백엔드 살아있나) vs 추정치(isEstimate, 진짜 조회 실패 시 흐리게)

## 통합 단계 확인 (씬 디버깅)

`?scene=1`을 붙이면 3D 씬만(오버레이 없이) 본다.

## 확인된 스택 (2026-07 기준, npm list로 실측)

| 패키지 | 버전 | 비고 |
|---|---|---|
| react | 19.2.7 | |
| @react-three/fiber | **9.6.1** | **v9 경로** — 타입 확장은 `ThreeElement` 방식 |
| @react-three/drei | 10.7.7 | |
| @react-three/postprocessing | 3.0.4 | |
| three | 0.185.1 | 물리 광원 단위 주의 |

> 참고: 초기 통합 단계별 토글(`?stage=1~7`)은 대시보드 연결 과정에서 제거됐다.
> `OrganicCoreScene`은 여전히 레이어별 prop(aurora/particles/floor/bloom)을 받으므로,
> 씬만 단계별로 확인하려면 App에서 그 prop을 넘기면 된다.

## heart.glb 교체 (지금은 절차적 폴백 심장)

Meshy에서 GLB를 만들면 `public/models/heart.glb`에 넣기만 하면 자동 전환된다.
자세한 export 설정은 `public/models/README.md` 참고.
mesh 노드 이름을 알아냈다면 `src/components/organic-core/HeartCore.tsx`의
`GLBHeart`에서 `find(isMesh)` 폴백을 직접 참조로 바꿀 것.

## 헤드리스 검증 스크립트

브라우저 없이 각 단계를 캡처/검증 (puppeteer-core + 시스템 Chrome/Edge):

```bash
node scripts/capture-stage.mjs ./shots 1 2 3 4 5 6 7   # SwiftShader, 시각 검증
$env:ANGLE='d3d11'; node scripts/capture-stage.mjs ./shots 7   # 하드웨어 GPU, 실측 FPS
$env:WAIT_MS='70000'  # 대기 시간 조절 (적응형 품질 강등 관찰 등)
```

## 성능 아키텍처 (상시 떠 있는 위젯 전제)

- **60fps 캡** (`maxFps` prop): demand 렌더 + FramePacer. 캡 없이는 모니터
  주사율(165Hz)로 풀 파이프라인이 돌아 배터리를 태운다. 탭이 숨겨지면 자동 정지.
- **트랜스미션 해상도 1024 고정** (`transmissionRes`): drei 기본(풀스크린×dpr)은
  매 프레임 씬 2회 추가 렌더가 지배 비용이 됨.
- **적응형 품질**: 파티클 수·바닥 on/off만 조절 (해상도 가변은 FBO 고아화 유발이라 금지).
  dt 250ms 클램프 + visibilitychange 리셋으로 alt-tab 허위 강등 방지.
- 실측 (Intel UHD, 1280×720 풀 씬): 캡 해제 시 157~165fps → 캡 적용 후 60~61fps.
  SwiftShader(저사양 시뮬레이션): 품질 자동 강등 확인.

## 다중 에이전트 코드 리뷰 반영 (2026-07-17)

43개 에이전트 리뷰(3관점 발견 → 발견당 반박 검증 2회)에서 확정된 19건 수정 완료:
dt 무클램프(High), 트랜스미션 풀해상도 2패스(High), 프레임 캡 부재(High),
반사 FBO 고아화, 파티클 텔레포트+지오메트리 누수, beatEnergy 이중 박동 계약,
환경맵 색 하드코딩, PMREM 베이크 씬 dispose, AA 이중 부담, Draco CDN 문서화 등.
미해결(선택): backdrop-filter blur(24px) 7장 상시 비용 — 저품질 연동은 추후 판단.

## 색 규칙 (하이브리드, lifeColors.ts가 단일 소스)

- 청록 `#2be6c8` = 생명력 (평상시): 심장·오로라·파티클·카드 glow
- 금색 `#f2d675` = 사건 (갱신 순간만): `.event-flash` 클래스
- 상승 `#f0a878` / 하락 `#7fa3c9` = 정보 신호 (별도 유지)

## 다음 단계 (스펙 로드맵)

- Meshy GLB 생성 → 교체 (Week 0)
- FastAPI 백엔드 + 거래소 어댑터 (Week 1)
- 대시보드 본편(랭킹/리스트/sector flow) React 이식 + Tauri 래핑 (Week 2)
- 이 씬을 심장 카드 영역에 축소 배치 (심장은 "작고 상징적으로" — 스펙 6장)
