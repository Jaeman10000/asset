# VITALITY NEXUS — 핸드오프 꾸러미

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
