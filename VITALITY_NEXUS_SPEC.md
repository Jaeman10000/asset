# VITALITY NEXUS
## 살아있는 인터페이스를 정보화하는 데스크톱 트레이딩 위젯 — 명세서 v2

**Owner:** JJ
**Status:** 프로토타입 검증 완료, Claude Code로 이전 준비
**MVP 예상 기간:** 3~4주 (하루 3~4시간 기준)

> 이 문서는 **Claude Code에게 넘기는 시작 문서**다.
> 각 세션 첫 명령은 "이 문서를 다시 읽는 것"이다.
> 이 대화에서 만든 프로토타입: `prototypes/full-dashboard-v2.html` (레이아웃/인터랙션 검증용)

---

## 0. 한 문장 요약

**PC 부팅 시 자동 실행되며, 키움+KIS+업비트+빗썸의 매수 종목을 3D 심장 + 오로라 오브 + 유리 카드 UI로 한눈에 보여주는 크로스플랫폼 데스크톱 위젯.**

**컨셉**: "살아있는 인터페이스를 정보화한다." 심장이 뛰고, 유체가 흐르고, 아우라가 울렁이고, 데이터가 갱신될 때만 발광하는 대시보드.

---

## 1. 이 대화에서 검증된 최종 결정

### 화면 구성

```
┌─────────────────────────────────────────────────────────────┐
│  자산군 총합 4개 (항상 같음, 상단)                            │
│  [KR 주식] [US 주식] [주식 총합] [암호화폐 총합]              │
├────────┬───────────────────────────────┬────────────────────┤
│        │                               │                    │
│   KR   │   통합 수급 카드 (중앙)        │    ❤️ 심장         │
│  종목  │                               │                    │
│  상세  │   [한국 오브]  [미국 오브]     │                    │
│ (좌 세 │   따뜻한 톤   차가운 톤        │                    │
│  로 전 │                               ├────────────────────┤
│  체 차 │   각 12/11 섹터 원형 배치      │                    │
│  지)   │   외국인/기관/개인 3색 파티클  │  WL1  │  WL2       │
│        │                               │ (편집가능한        │
│        │                               │  큰 카드 2개)      │
│        ├───────────────────────────────┼────────────────────┤
│        │  하단 라벨: 상위 3섹터         │  Crypto 상세       │
└────────┴───────────────────────────────┴────────────────────┘
```

### 컴포넌트 목록

| 컴포넌트 | 기능 | 데이터 소스 |
|---|---|---|
| 자산군 총합 (4개) | KR주식/US주식/주식총합/암호화폐총합 | 로컬 백엔드 |
| 심장 카드 | 전체 총액 + 손익률 + BPM + 파장 발산 | 계산값 |
| WATCHLIST 슬롯 (2개) | 편집 가능 큰 카드, 도넛+스파크라인+값 | 사용자 선택 |
| 한국 오로라 오브 | 반투명 구 + 오로라 링 + 12섹터 | KRX 정보데이터시스템 |
| 미국 오로라 오브 | 반투명 구 + 오로라 링 + 11 SPDR 섹터 | Yahoo Finance |
| KR 상세 리스트 | 미니 도넛 + 값 (좌측 세로) | 키움 REST |
| 크립토 상세 리스트 | 미니 도넛 + 값 (우측) | 업비트 + 빗썸 |

### 살아있는 규칙 (검증된 원칙)

- **평상시 = 조용함**. 심장만 뛰고, 오로라가 서서히 울렁, 오브가 잔잔히 흐름
- **데이터 갱신 순간 = 발광**. 그 카드 테두리 금빛, 도넛 후광, 숫자 광채, 심장에서 카드로 파장
- **심장 뛰는 순간마다** 대시보드 전체로 파장 확산 (붉은 링이 심장에서 각 카드로 이동)
- **파티클 색으로 정보 인코딩**:
  - 한국 섹터: 외국인=금색(hue 45), 기관=청록(175), 개인=회청(220)
  - 미국 섹터: 상승=시안(195), 하락=보라(240)
- **크기/시간 위계**:
  - 오로라 링 속도: 아주 느림 (0.0006~0.0013)
  - 파티클 흐름: 900ms + 랜덤 300ms
  - 심장 박동: BPM 68~103 (변동성 반영)
  - 이펙트가 서두르지 않고 여유 있어야 함
- **섹터 발광 차이**: 1위와 12위가 확연히 다르게 (단순 강도가 아니라 위계 표현 필요)

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  Tauri Desktop App  (Rust wrapper + React frontend)         │
│  ─ Three.js 3D 씬 (심장, 오브, 유체)                        │
│  ─ Canvas 2D UI (카드, 도넛, 리스트, 파장)                  │
│  ─ 3가지 배치 모드 (desktop / on-top / normal)              │
│  ─ localhost:8787 폴링                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP (localhost only)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Local Backend  (FastAPI, port 8787)                        │
│  ─ API 키: OS keychain (Windows Credential / macOS Keychain)│
│  ─ 어댑터: kiwoom / kis / upbit / bithumb / krx / yahoo    │
│  ─ 통합 Position 스키마로 정규화                            │
│  ─ 캐시 7초 TTL                                             │
│  ─ SQLite (거래 이력, 스냅샷)                               │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTPS (OAuth 2.0 등)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  External APIs                                              │
│  ─ 키움 REST API (국내 주식)                                │
│  ─ KIS API (미국 주식)                                      │
│  ─ 업비트 REST (KRW/BTC 마켓 암호화폐)                      │
│  ─ 빗썸 REST (KRW 마켓 암호화폐)                            │
│  ─ KRX 정보데이터시스템 (섹터별 투자자별 매매동향)          │
│  ─ Yahoo Finance (11개 SPDR ETF 전일 종가)                  │
└─────────────────────────────────────────────────────────────┘
```

### 왜 이 구조인가

- **키움만으로는 미국 주식 안 됨** — KIS 필수 (확인 완료)
- **API 키는 절대 Tauri 번들에 넣지 않음** — 백엔드에서 OS 키체인으로 관리
- **한국 투자자별 매매동향**은 KRX 정보데이터시스템에서 무료로 가져옴
- **미국 섹터 성과**는 Yahoo Finance API로 무료

---

## 3. 3D 시각 요소 (진짜 3D로 만들 것)

지금 이 대화에서 만든 프로토타입은 Canvas 2D로 3D를 흉내낸 것. 로컬 Claude Code에서는 **진짜 3D**로 다시 만듦.

### 3D 심장

- **모델 소스**: Meshy AI 생성 (형님 결정)
  - 프롬프트 예: "anatomical human heart, semi-transparent, realistic, PBR"
  - 결과물: GLB 파일
  - 저장 위치: `/assets/models/heart.glb`
- **재질**: MeshPhysicalMaterial (Three.js)
  - clearcoat: 0.9 (표면 광택)
  - sheen: 0.7 (조직 느낌)
  - emissive: 은은한 붉은 발광 (심장 박동 시 증가)
- **조명**: HDRI 환경맵 + Key/Fill/Rim 3개 point light
- **박동**: 이중 박동(S1 강함 + S2 약함) — 실제 심장 리듬
- **위치**: 심장 카드 영역에 정렬 (positionHeart 함수처럼)

### 3D 오로라 오브 (한국/미국 2개)

- **구 지오메트리** + **커스텀 셰이더**
  - 반투명 유리 재질 (MeshTransmissionMaterial)
  - 내부에서 오로라가 3층으로 유영
  - 표면 반사 + 굴절
- **오로라 링**: 여러 겹의 반투명 링이 각기 다른 색과 위상으로 회전
  - 한국: 따뜻한 팔레트 (금색/주황/붉은색)
  - 미국: 차가운 팔레트 (시안/파랑/보라)
- **속도**: 서두르지 않게 (프로토타입보다 30% 느리게)

### 3D 유체 리본 (배경)

- **WebGL 셰이더 방식** (사인파 여러 겹 + 노이즈)
- 참조 이미지의 청록·초록·자주 유체가 카드 사이를 관통하는 느낌
- 심장 박동 순간 유체 강도 살짝 증가
- 배경 뒤에 낮은 z-index로 배치

### 배경 환경

- **HDRI**: Poly Haven `studio_small_04.hdr` (무료, 상업 사용 가능, 형님 결정)
- 목적: 유리 재질 반사에 사용, 실제 이미지로는 안 보임
- 실제 배경: 참조 이미지처럼 대리석 톤 (radial gradient + 미세 노이즈)

---

## 4. 데이터 모델

```typescript
interface Position {
  id: string;                    // "kiwoom:005930" | "upbit:KRW-BTC"
  exchange: 'kiwoom' | 'kis' | 'upbit' | 'bithumb';
  assetType: 'stock' | 'crypto';
  region?: 'KR' | 'US';          // 주식만
  symbol: string;
  name: string;                  // 한글 우선
  qty: number;
  avg: number;                   // 평균 매입가
  price: number;                 // 현재가
  currency: 'KRW' | 'USD';
  value: number;                 // KRW 환산 평가금액 (백엔드에서 계산)
  cost: number;                  // KRW 환산 매수금액
  ret: number;                   // 수익률 %
  history: number[];             // 최근 32개 가격
  sector?: string;               // KR 주식만
  lastUpdated: number;
}

interface SectorFlow {
  region: 'KR' | 'US';
  id: string;                    // 'semi', 'XLK' 등
  name: string;                  // '반도체', '기술' (한글)
  // 한국만
  foreign?: number;              // 외국인 순매수 강도 0~1
  inst?: number;                 // 기관 순매수 강도 0~1
  individual?: number;           // 개인 순매수 강도 0~1
  // 미국만
  ret?: number;                  // 전일 등락률
  volume?: number;
}

interface PortfolioSnapshot {
  totals: {
    kr: { value, cost, pnl, pnlPct };
    us: { value, cost, pnl, pnlPct };
    stock: { value, cost, pnl, pnlPct };
    crypto: { value, cost, pnl, pnlPct };
    total: { value, cost, pnl, pnlPct };
  };
  positions: Position[];
  sectorFlows: SectorFlow[];
  fetchedAt: number;
  errors: { source: string; message: string }[];
  isEstimate: boolean;
}
```

**핵심 원칙:**
- 프론트엔드는 원본 API 응답 절대 몰라야 함
- 부분 실패 지원 (한 소스 실패해도 나머지는 반환)
- `isEstimate` 플래그: 캐시된 값이면 UI에서 흐리게

---

## 5. 개발 로드맵 (4주 MVP)

### Week 0: 준비 (하루)

- [ ] Meshy AI 계정 만들고 심장 모델 생성 (`assets/models/heart.glb`)
- [ ] Poly Haven에서 `studio_small_04.hdr` 다운로드
- [ ] 각 거래소 API 키 발급 (키움/KIS/업비트/빗썸)
- [ ] KRX 정보데이터시스템 API 접근 방법 확인

### Week 1: 백엔드 (7일)

**Day 1-2**: FastAPI 셋업, OS 키체인, SQLite, 헬스체크
**Day 3-4**: 6개 어댑터 (kiwoom, kis, upbit, bithumb, krx, yahoo)
**Day 5-6**: 통합 API, 부분 실패, 캐싱, rate limit
**Day 7**: 실제 계좌 검증

### Week 2: Tauri + Canvas 2D UI (7일)

**Day 8-9**: Tauri 셋업, 3가지 배치 모드, 시스템 트레이, 자동 시작
**Day 10-11**: Zustand 스토어, 폴링 훅, 에러 처리
**Day 12-14**: 프로토타입 레이아웃을 React 컴포넌트로 이식
- **3D 없이도 대시보드로서 완결**

### Week 3: 3D 통합 (7일)

**Day 15-16**: R3F 심장 (GLB + HDRI + Bloom + 이중 박동)
**Day 17-18**: 3D 오로라 오브 2개 (한국/미국)
**Day 19-20**: 유체 리본 (WebGL 셰이더)
**Day 21**: 성능 프로파일 (목표 60fps, idle 100MB 이하)

### Week 4: 완성도 + 배포 (7일)

**Day 22-23**: UX (배치 모드, 설정, Reduced motion)
**Day 24-25**: WATCHLIST 확장, 색상 옵션
**Day 26-27**: Windows MSI, macOS DMG, Tauri 자동 업데이트
**Day 28**: 실사용

---

## 6. 프로토타입에서 배운 것

### 하지 말 것

- ❌ **심장을 크게 만들어 화면 차지하기** — 심장은 작고 상징적
- ❌ **모든 요소를 계속 발광시키기** — 데이터 갱신 순간에만
- ❌ **섹터 발광이 다 비슷하기** — 1위와 12위가 확연히 다르게
- ❌ **네온 형광색** — 부드러운 파스텔 톤 (up: `#f0a878`, down: `#7fa3c9`)
- ❌ **모든 카드 같은 크기** — 크기 위계
- ❌ **텍스트 위주** — 그래프/도넛/스파크라인
- ❌ **파장이 너무 빠르게** — 여유 있는 리듬

### 반드시 할 것

- ✅ **글로벌 발광 규칙**: 평상시 조용, 갱신 순간만 발광
- ✅ **심장 = 파장의 원천**: 뛸 때마다 대시보드 전체로 파장 확산
- ✅ **카드 → 심장 역방향**: 큰 이벤트 시 심장 색 물듦
- ✅ **정확한 값 = Truth Layer**: 호버 시 정확한 숫자 + 기준시각
- ✅ **자산군별 총합 표시** (KR / US / 주식총합 / 암호화폐총합)
- ✅ **투자자별 매매동향** 3색 파티클
- ✅ **미국 섹터도 한글 이름**
- ✅ **WATCHLIST 슬롯 편집 가능**

### 리스크

1. **KIS API가 처음** → Week 1에 시간 여유. 안 되면 CSV 업로드 폴백
2. **KRX 투자자별 매매동향이 실시간 아님** — 장 마감 후 데이터. UI에 정직하게 표시
3. **3D 심장 모델 라이선스** — Meshy AI 이용약관 확인 필수
4. **macOS 바탕화면 붙이기 제한** — Mac은 "always at bottom" 폴백
5. **성능** — 프레임 드롭 감지 시 파티클/링 자동 감소

---

## 7. Kill Criteria

- Week 2 끝에도 백엔드에서 정확한 값이 안 나옴 → API 방향 재검토
- Week 3 끝에도 60fps 못 지킴 → 3D 야망을 줄이고 Canvas 2D로 복귀
- 실사용 1주일 후 안 열게 됨 → 근본 재검토

---

## 8. 다음 세션 시작 방법

Claude Code에서:

```bash
# 1. 프로젝트 폴더 생성
mkdir vitality-nexus && cd vitality-nexus
git init

# 2. 이 명세서와 프로토타입 배치
mkdir docs prototypes assets
# VITALITY_NEXUS_SPEC.md → docs/
# full-dashboard-v2.html → prototypes/
# heart.glb → assets/models/  (Meshy AI 생성 후)
# studio_small_04.hdr → assets/env/  (Poly Haven)

# 3. Claude Code 첫 명령
"docs/VITALITY_NEXUS_SPEC.md를 처음부터 끝까지 읽어.
prototypes/full-dashboard-v2.html은 레이아웃과 인터랙션의 레퍼런스야.
Week 0 준비 사항 체크 후 Week 1 Day 1-2 (백엔드 셋업)부터 시작해줘.
완료 정의는 '로컬 e2e → 배포 → 버전 확인 → 프로덕션 warm 통과'다."
```

---

## 9. 이 대화에서 얻은 진짜 통찰

이 대화가 20+ 프로토타입을 만들며 오래 걸렸다. 그 과정에서 얻은 것:

1. **심장 하나 두근두근 ≠ 살아있는 인터페이스** — 심장은 원인, 대시보드 전체가 결과여야 함
2. **모든 것이 계속 발광하면 = 아무것도 발광 안 하는 것** — 신호를 만들려면 평상시 조용해야 함
3. **AI 이미지를 그대로 재현하려는 시도 = 함정** — AI 이미지는 실시간 렌더가 아니다. GLB + HDRI + 셰이더 필요
4. **카드가 다 같은 크기 = 엑셀 표** — 크기 위계가 살아있는 감각의 핵심
5. **텍스트 → 그래프 대체 원칙** — 도넛/스파크라인/미니 도넛
6. **정보 밀도와 여유는 반비례가 아니라 위계로 해결**
7. **"AI로 다 된다"** — Claude Code + Meshy AI + Poly Haven + Tauri 조합이면 개인 개발자가 프로덕션급 3D 위젯 만들 수 있음
