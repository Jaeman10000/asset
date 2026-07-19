# VITALITY NEXUS

**심장이 중앙에서 뛰는 살아있는 포트폴리오 대시보드** — KR/US 주식 + 암호화폐 보유 자산을
3D 유리 심장과 홀로그램 섹터 궤도로 보여주는 Windows 데스크톱 위젯.

## ⬇️ 다운로드 (Windows)

**[최신 릴리스 받기 →](https://github.com/Jaeman10000/asset/releases/latest)**
— `Vitality.Nexus_x.y.z_x64-setup.exe`(권장) 또는 `.msi` 중 하나를 받아 실행.

- **API 키 없이 바로 사용**: 설치 후 하단 "보유종목 편집"에서 종목·수량·평단만 입력하면
  암호화폐(업비트/빗썸)·주식(국내/미국) 현재가가 공개 시세로 자동 갱신됩니다.
- ⚠️ **SmartScreen 경고**: 아직 코드서명이 없어 첫 실행 시 "Windows의 PC 보호" 경고가
  뜹니다 → **추가 정보 → 실행**을 누르면 됩니다.
- 시장 랭킹·섹터 수급에 **"⚠ 샘플 데이터"** 배지가 붙은 패널은 증권사 연동 전까지
  모의 데이터입니다 (내 보유 자산 시세는 실데이터).

---

## 개발자용 — 핸드오프 꾸러미

로컬 Claude Code로 넘기는 전체 자료. 아래 순서로 읽으면 된다.

## 📁 이 꾸러미에 든 것

```
vitality-handoff/
├── README.md                  ← 지금 이 파일 (전체 지도)
├── START_HERE.md              ← ① 제일 먼저 읽기. 오늘 뭘 할지 실행 순서
├── VITALITY_NEXUS_SPEC.md     ← ② 프로젝트 전체 명세 (의도·데이터·로드맵)
│
├── prototype/
│   └── full-dashboard-v2.html ← ③ 레이아웃/인터랙션 레퍼런스 (지금까지 다듬은 것)
│
└── organic-core/              ← ④ 진짜 3D 심장 코어 (Fable 5 스타터 + 확장)
    ├── GUIDE.md               ←   3D 통합 상세 가이드 (Meshy 설정~성능)
    ├── HeartCore.tsx          ←   유리질 심장 (GLB + MeshTransmissionMaterial)
    ├── OrganicCoreScene.tsx   ←   전체 씬 (심장+오로라+파티클+바닥+Bloom)
    ├── AuroraBackground.tsx   ←   청록 안개 셰이더
    ├── LifeParticles.tsx      ←   떠다니는 생명력 입자
    ├── ReflectiveFloor.tsx    ←   바닥 반사 (공간감)
    ├── useAdaptiveQuality.ts  ←   FPS 감시 → 자동 품질 조절
    ├── lifeColors.ts          ←   청록(생명)+금색(사건) 색 단일 소스
    ├── glass-cards.css        ←   홀로그램 유리 카드 스타일
    └── shaders/
        ├── aurora.vert.glsl
        └── aurora.frag.glsl
```

## 📖 읽는 순서

1. **START_HERE.md** — 오늘 당장 뭘 할지 (Meshy GLB 생성 → 설치 → 확인)
2. **VITALITY_NEXUS_SPEC.md** — 이 프로젝트가 뭘 만드는지 전체 그림
3. **prototype/full-dashboard-v2.html** — 브라우저로 열어서 목표 UI 확인
4. **organic-core/GUIDE.md** — 3D를 실제로 붙이는 상세 순서

## 🎯 핵심 3줄 요약

- 지금 프로토타입(`full-dashboard-v2.html`)은 **Canvas 2D로 흉내낸** 대시보드다.
- `organic-core/`가 그 심장 부분을 **진짜 3D**(GLB+유리재질+오로라+파티클+바닥반사)로 바꾼다.
- 색은 **청록=생명력(평상시) / 금색=사건(갱신순간)** 하이브리드로 통일한다.

## ⚠️ 선행 조건 (이거 없으면 3D 화면 안 뜸)

1. Meshy에서 심장 GLB 생성 → `public/models/heart.glb`
2. `npm install three @react-three/fiber @react-three/drei @react-three/postprocessing postprocessing`
3. R3F 버전 확인 (`npm list @react-three/fiber`) — v8/v9에 따라 타입 문법 다름

자세한 건 START_HERE.md → organic-core/GUIDE.md 순으로.
