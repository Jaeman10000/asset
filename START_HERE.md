# 지금부터 뭘 해야 하나 — 실행 순서

Fable 5가 만들어준 3D 스타터 코드를 로컬 프로젝트에 붙이는 순서다.
이 문서 → `organic-core/GUIDE.md` 순으로 읽으면 된다.

받은 파일 6개:
```
organic-core/
├── GUIDE.md              ← Meshy export 설정 + 파라미터 튜닝 가이드
├── HeartCore.tsx         ← 3D 심장 (GLB + 유리질 재질 + 심박)
├── OrganicCoreScene.tsx  ← 위 둘을 합치는 최상위 씬
├── AuroraBackground.tsx  ← WebGL 오로라 배경
└── shaders/
    ├── aurora.frag.glsl  ← 오로라 프래그먼트 셰이더
    └── aurora.vert.glsl  ← 오로라 버텍스 셰이더
```

---

## 단계 0 — 이 코드가 뭘 하는지 (1분 이해)

지금 프로토타입(`full-dashboard-v2.html`)은 **Canvas 2D로 심장을 흉내** 낸 거다.
이 스타터 코드는 그걸 **진짜 3D**로 바꾼다:
- 심장 = Meshy로 만든 GLB 모델 + 유리질 재질(빛이 통과/굴절)
- 배경 = WebGL 셰이더로 그린 오로라 안개
- **하나의 색(`LIFE_COLOR = #2be6c8` 청록)** 을 심장·오로라·카드 테두리가 전부 공유

마지막 게 핵심이다. 지금 프로토타입의 가장 큰 약점이 "위젯마다 색이 따로 노는 것"인데,
이 구조는 색을 한 곳에서 관리해서 그걸 막는다.

---

## 단계 1 — Meshy에서 심장 GLB 먼저 만들기 (제일 먼저!)

코드보다 이걸 먼저 해야 한다. 모델 없으면 코드 돌려도 아무것도 안 나온다.

1. https://www.meshy.ai 접속 → 가입
2. **Text-to-3D** 선택, 프롬프트 (GUIDE.md에 있는 것):
   ```
   anatomical human heart, translucent, bioluminescent veins,
   semi-transparent tissue, glowing internal glow, smooth organic
   surface, medical hologram style, no background
   ```
   - 더 좋은 방법: 예전에 쓰던 레퍼런스 심장 이미지가 있으면 **Image-to-3D**로. 형태가 훨씬 안정적으로 나옴.
3. Export 설정 (중요, GUIDE.md 13~15줄):
   - **GLB** 포맷 (GLTF+bin 분리 아님)
   - 텍스처 2K로 낮춤
   - Remesh: **Medium** (20~50K tris)
   - **Normal map은 유지, Albedo/BaseColor 텍스처는 버려도 됨** (유리 재질이 덮어씀)
4. 받은 파일을 프로젝트의 `public/models/heart.glb`에 놓는다
5. **라이선스 확인**: Meshy 무료 플랜 생성물의 상업적 사용 가능 여부를 계정 설정에서 확인. 나중에 앱을 팔거나 배포하면 중요해짐.

### GLB 받으면 바로 할 것: 실제 mesh 노드 이름 확인
HeartCore.tsx는 GLB 안의 mesh 이름을 몰라서 `Object.values(nodes).find(isMesh)`로 임시 처리돼 있다.
정확하게 하려면:
- https://gltf-viewer.donmccurdy.com 에 GLB를 드래그 → 노드 구조 확인
- 또는 코드에서 `console.log(nodes)` 한 번 찍어보기
- 실제 이름(예: `Heart_mesh`)을 알아내면 나중에 Claude Code한테 "이 이름으로 바꿔줘" 하면 됨

---

## 단계 2 — HDRI 다운로드

유리 재질은 반사할 환경(HDRI)이 없으면 그냥 회색 덩어리로 보인다. 필수다.

- HeartCore.tsx는 지금 `<Environment preset="night" />`로 drei 내장 프리셋을 쓴다 → **일단 이대로 돌려도 됨**
- 더 좋은 결과를 원하면 Poly Haven에서 `studio_small_04.hdr` 받아서 교체:
  ```
  <Environment files="/env/studio_small_04.hdr" />
  ```
  파일은 `public/env/`에 놓는다.

---

## 단계 3 — 패키지 설치 + 버전 확인 (여기서 함정 주의)

```bash
npm install three @react-three/fiber @react-three/drei
```

**⚠️ 반드시 확인할 것 (Fable 5도 경고한 부분):**

R3F(react-three-fiber)는 v8과 v9에서 문법이 다르다. v9는 React 19 대응 버전이다.
설치 후 버전을 확인해라:
```bash
npm list @react-three/fiber @react-three/drei three react
```

- **React 19 + R3F v9를 쓴다면**: `AuroraBackground.tsx`의 `ThreeElements` 확장 문법이
  v9 방식이어야 한다. v9는 특화 Node 타입(`Object3DNode` 등)이 제거되고 `ThreeElement` 하나로 통합됐다.
- **React 18 + R3F v8을 쓴다면**: 지금 코드의 `declare module` 부분이 v8 문법과 맞는지 확인 필요.

이건 Claude Code한테 넘길 때 **"내 프로젝트의 R3F 버전은 X다. AuroraBackground.tsx의
타입 확장을 이 버전에 맞게 고쳐줘"** 라고 하면 정확히 처리해준다.
(버전을 모르면 Claude Code가 추측하다 틀릴 수 있으니 위 명령으로 먼저 확인.)

**추가 주의**: MeshTransmissionMaterial은 R3F v9 + React 19 조합에서 예전에 피드백 루프 버그가
있었다(2024년 말). R3F를 최신으로 올리면 해결됐다. 화면이 이상하게 번쩍이면 이걸 의심.

---

## 단계 4 — Vite `?raw` import 확인

`AuroraBackground.tsx`는 셰이더를 이렇게 불러온다:
```ts
import fragmentShader from '../shaders/aurora.frag.glsl?raw';
```

- **Tauri가 Vite 기반이면** (`npm create tauri-app`에서 React 선택 시 기본값) → 그냥 됨
- **다른 번들러면** → `?raw`가 안 먹힘. 셰이더 문자열을 파일에 직접 인라인해야 함.

확인: 프로젝트 루트에 `vite.config.ts`가 있으면 Vite다. 있으면 걱정 없음.

---

## 단계 5 — 폴더 배치

받은 파일을 프로젝트에 이렇게 넣는다 (import 경로가 이 구조 기준):
```
src/
├── components/
│   └── organic-core/
│       ├── HeartCore.tsx
│       ├── OrganicCoreScene.tsx
│       └── AuroraBackground.tsx
└── shaders/
    ├── aurora.frag.glsl
    └── aurora.vert.glsl
```

주의: `AuroraBackground.tsx`가 `../shaders/aurora.frag.glsl`로 불러오므로,
`organic-core` 폴더와 `shaders` 폴더의 상대 위치가 위와 같아야 한다.
안 맞으면 import 경로만 고치면 됨.

---

## 단계 6 — 대시보드에 심장만 먼저 끼우기

전체를 한 번에 붙이지 말고, **심장 3D 씬 하나만** 먼저 넣어서 돌아가는지 본다.

지금 프로토타입의 심장 카드 자리에 `<OrganicCoreScene bpm={72} />`를 렌더.
```tsx
import { OrganicCoreScene } from './components/organic-core/OrganicCoreScene';

// 심장 카드 안에서
<OrganicCoreScene bpm={currentBpm} />
```

이게 화면에 심장이 뜨고 유리질로 빛나면 → 1차 성공.
안 뜨면 순서대로: GLB 경로 맞나? → mesh 노드 찾았나? → Environment 있나?

---

## 단계 7 — 색 통일 (이 프로젝트의 핵심 미학)

`OrganicCoreScene.tsx` 맨 위:
```ts
const LIFE_COLOR = '#2be6c8';
```

이 값 하나가 심장 내부색·오로라·point light를 다 정한다.
**여기에 더해서, 대시보드 CSS의 카드 테두리 glow도 이 색으로 맞춰라.**
지금 프로토타입은 카드 발광이 금색(`--gold: #f2d675`)인데,
3D로 가면 이 청록(`#2be6c8`)과 충돌한다.

→ 결정 필요: 생명력 색을 **청록으로 통일**할지, **금색으로 통일**할지.
   (레퍼런스 무드 이미지는 청록. 지금 프로토타입은 금색.)
   둘 중 하나로 정해서 `LIFE_COLOR`와 CSS `--gold`(또는 새 변수)를 같은 값으로.

---

## 요약: 오늘 할 것 vs 나중에 할 것

**오늘 (막히면 여기서 멈춰도 됨):**
1. ✅ Meshy에서 GLB 생성 → `public/models/heart.glb`
2. ✅ `npm install three @react-three/fiber @react-three/drei`
3. ✅ 버전 확인 (`npm list ...`)
4. ✅ 파일 6개 폴더에 배치
5. ✅ 심장 카드에 `<OrganicCoreScene>` 하나만 끼워서 뜨는지 확인

**그 다음 (Claude Code에 맡길 것):**
6. R3F 버전에 맞게 타입 확장 수정
7. 오로라 배경 통합
8. 색 통일 (LIFE_COLOR ↔ 카드 CSS)
9. 기존 Canvas 2D 대시보드(랭킹/리스트/sector flow)와 3D 씬 레이어 합치기
10. 성능 측정 (60fps 유지되나)

**Claude Code 첫 명령 예시:**
```
organic-core/ 폴더의 스타터 코드를 이 Tauri 프로젝트에 통합해줘.
먼저 `npm list @react-three/fiber`로 버전 확인하고,
AuroraBackground.tsx의 ThreeElements 확장을 그 버전에 맞게 고쳐줘.
public/models/heart.glb는 이미 배치했고, 실제 mesh 노드 이름은 [GLB뷰어에서 확인한 이름]야.
심장 씬이 화면에 뜨는 것부터 확인한 뒤 오로라 배경을 붙여줘.
```
