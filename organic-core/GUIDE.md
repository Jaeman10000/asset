# Vitality Nexus — Organic Core Pipeline

목표: Canvas 2D 흉내 → 진짜 3D 해부학적 심장(GLB) + 유리질 트랜스미션 머티리얼 + WebGL 오로라 셰이더.
Reference mood: `Gemini_Generated_Image_nub2rynub2rynub2.png` (심장에서 뿜어나오는 단일 청록 광원이 안개/파티클/카드 테두리까지 물들이는 느낌).

---

## 1. Meshy AI로 GLB 생성

**프롬프트 방향 (Meshy Text-to-3D 또는 Image-to-3D):**
- Text-to-3D를 쓴다면: `anatomical human heart, translucent, bioluminescent veins, semi-transparent tissue, glowing internal glow, smooth organic surface, medical hologram style, no background`
- Image-to-3D가 가능하면 레퍼런스 이미지(위 예시 같은 반투명 심장 렌더)를 넣는 게 훨씬 결과가 안정적임. 텍스트만으로는 "심장 모양"은 나와도 "반투명 유리질"까지는 지오메트리에 반영 안 됨 — 그건 지오메트리가 아니라 머티리얼 몫이라 3번 단계에서 만든다고 생각하고, Meshy에서는 **형태와 토폴로지**만 잘 뽑는 데 집중.
- Export 설정: **GLB (not GLTF+bin separate)**, 텍스처는 4K→2K로 낮춰서 export (트랜스미션 머티리얼을 씌우면 원본 텍스처는 거의 안 보이고 노멀맵 정도만 살아남음).
- Poly count: Meshy 기본 remesh 옵션에서 "Medium" (약 20-50K tris) 정도면 충분. 데스크톱 Tauri 앱이라 모바일 대비 여유 있지만, 회전/줌 인터랙션이 있으면 너무 무겁게 가져올 필요 없음.
- **Normal map은 유지, Albedo/Base Color 텍스처는 버릴 준비할 것** — MeshTransmissionMaterial은 색을 자체 파라미터(color, attenuationColor)로 내는 게 낫고 베이크된 텍스처와 충돌하면 탁해 보임.

## 2. Three.js 셋업

```bash
npm install three @react-three/fiber @react-three/drei
```

`@react-three/drei`의 `MeshTransmissionMaterial`이 핵심. 유리/젤리/오브 재질을 물리 기반으로 시뮬레이션(굴절, 색수차, 두께 감쇠)한다. `HeartCore.tsx` 참고.

**핵심 파라미터 튜닝 포인트:**
- `transmission`: 1에 가까울수록 투명. 0.9~1.0
- `thickness`: 내부 빛 감쇠 두께 시뮬레이션. 너무 낮으면 유리처럼, 너무 높으면 불투명 젤리처럼 보임 → 1.5~3 사이에서 실물 보면서 조정
- `attenuationColor`: 심장 내부에서 새어나오는 빛의 색 (레퍼런스처럼 청록으로) — 이게 사실상 "생명력 색"을 결정하는 가장 중요한 값
- `attenuationDistance`: 낮을수록 색이 빨리 흡수되어 표면 근처만 색이 남음
- `roughness`: 0에 가깝게 (매끈한 유리질). 0.05~0.15
- `chromaticAberration`: 0.02~0.05 정도만 — 너무 크면 싸구려 필터처럼 보임
- `ior`: 1.3~1.5 (유리~물 사이)
- 뒤에 **environment map(HDRI)**이 반드시 있어야 transmission이 그럴듯하게 보임. drei의 `<Environment preset="night">` 또는 커스텀 HDRI로 시작.

**심박 모션(살아있음의 핵심):**
- `useFrame`에서 heart의 `scale`을 `88 BPM` 같은 실제 심박수 데이터에 맞춰 sin 파형으로 pulsing — 단순 정현파보다 실제 심전도 파형(빠른 수축 + 느린 이완)에 가까운 easing이 훨씬 유기적으로 보임. 아래 컴포넌트에 이중 sin 조합 예시 포함.

## 3. WebGL 오로라 배경 셰이더

Canvas 2D 대신 풀스크린 plane에 커스텀 fragment shader로 domain-warped simplex noise를 그려서 안개/오로라 흐름을 만든다. `AuroraBackground.tsx` + `shaders/aurora.frag.glsl` 참고.

- Additive blending으로 배경 위에 얹으면 레퍼런스 이미지처럼 "빛이 안개를 물들이는" 느낌이 남.
- 색상은 heart의 `attenuationColor`와 반드시 통일 — 사이드 패널 테두리 glow, 오로라, 심장 내부색이 전부 같은 hue 계열이어야 "하나의 광원에서 퍼져나간다"는 느낌이 생김. 지금 스크린샷처럼 위젯마다 색이 따로 노는 걸 여기서 고쳐야 함.
- 파티클: `<Points>` + 커스텀 point shader로 심장에서 바깥으로 서서히 퍼지는 소수의 파티클 (50~150개 정도, 너무 많으면 노이즈처럼 보임). 파티클 색도 동일 hue.

## 4. 사이드 패널(카드) 개선 방향

기존 `dark-neon-fintech` 톤(글래스모피즘, 라운드 코너)은 유지하되:
- 카드 테두리를 하드 스트로크 대신 **box-shadow glow**(심장 색과 동일 hue, blur 크게)로 바꿔서 "홀로그램처럼 빛이 번지는" 느낌으로.
- 카드 배경에 아주 옅은 backdrop-blur + 노이즈 텍스처를 얹으면 평평한 느낌이 줄어듦.
- 그리드에 칼같이 정렬하지 말고 카드마다 `transform: translateY(...)`로 몇 px씩 미세하게 어긋나게(또는 아주 느린 float 애니메이션) 주면 "부유하는" 느낌.

---

## 다음 단계
1. Meshy에서 GLB 1차 생성 → `/public/models/heart.glb`에 배치
2. `HeartCore.tsx`, `AuroraBackground.tsx`를 프로젝트에 통합, `attenuationColor`/오로라 색을 동일 값으로 맞추기
3. 실제 화면 캡처해서 레퍼런스 이미지랑 다시 비교 — 광원 통일과 안개 depth 두 가지만 맞아도 체감 차이가 클 것

---

## 5. 확장 컴포넌트 (대기감 최대 + 하이브리드 색 + 성능 폴백)

초기 스타터(심장+오로라)에 더해, "최대 근접 대기감" 결정에 따라 아래를 추가했다:

| 파일 | 역할 | AI 진단 매핑 |
|---|---|---|
| `lifeColors.ts` | 청록(생명)+금색(사건) 색 단일 소스, CSS 주입 | ② 하나의 광원 |
| `LifeParticles.tsx` | 심장에서 퍼지는 청록 입자 (박동 반응) | ③ 파티클 대기감 |
| `ReflectiveFloor.tsx` | 바닥 반사 (공간감) | ③ 바닥 반사 |
| `useAdaptiveQuality.ts` | FPS 감시 → 자동 품질 조절 | (성능 안전장치) |
| `glass-cards.css` | 홀로그램 유리 카드 + 부유 + glow | ④ 카드 재질 |
| `OrganicCoreScene.tsx` | 위 전부 + Bloom 합친 최종 씬 | ①②③④ 통합 |

### 색 결정 (확정): 하이브리드
- **청록 `#2be6c8` = 생명력.** 평상시. 심장·오로라·파티클·바닥반사·카드 기본 glow.
- **금색 `#f2d675` = 사건.** 데이터 갱신 플래시·랭킹 1위·BPM 등 "주목" 신호에만.
- 한국 관례색(상승 주황/하락 파랑)은 정보 신호로 별도 유지.
- 이유: 전체를 청록으로 깔면 트레이딩에서 중요한 "상승/하락/강조" 신호가 죽는다.
  청록 바다 위에 금색 사건이 떠야 오히려 눈에 띈다 (Von Restorff).

### 추가 설치
```bash
npm install @react-three/postprocessing postprocessing
```
(three, @react-three/fiber, @react-three/drei는 이미 설치했다고 가정)

### 성능 (항상 떠 있는 위젯이므로 필수)
`useAdaptiveQuality`가 FPS를 감시해서 4단계로 자동 조절한다:
- 45fps 밑으로 떨어지면 → 무거운 것부터 끔 (바닥반사 해상도↓ → 파티클↓ → 바닥반사 off)
- 58fps 이상 5초 지속되면 → 다시 품질 올림
- 즉 "예쁘게 최대치"로 시작하되, 느려지면 알아서 가벼워진다.

### 통합 순서 (권장)
1. 심장만 (`HeartCore`) 떠서 유리질로 빛나는지 확인
2. 오로라 배경 추가 → 청록 안개 확인
3. `injectLifeColorsToCSS()` 호출 + `glass-cards.css` 적용 → 카드가 청록 glow로 바뀌는지
4. 파티클 추가 → 대기감 확인
5. 바닥 반사 추가 → 공간감 확인
6. Bloom 추가 → 홀로그램 번짐 확인
7. `useAdaptiveQuality` 연결 → 무거운 기기에서 FPS 유지되는지 확인

한 번에 다 켜지 말고 위 순서로 하나씩. 어디서 무거워지는지/안 예쁜지 원인을 알 수 있다.
