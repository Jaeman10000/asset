# heart.glb를 여기에 넣으세요

Meshy AI에서 생성한 심장 GLB를 이 폴더에 `heart.glb` 이름으로 놓으면
HeartCore가 자동으로 GLB를 사용합니다 (지금은 절차적 폴백 심장이 표시됨).

Meshy export 설정 (organic-core/GUIDE.md 기준):
- 포맷: **GLB** (GLTF+bin 분리 아님)
- **Draco 압축은 끄고** 내보낼 것 — Draco GLB는 디코더를 구글 CDN(gstatic)에서
  받아와야 해서 오프라인/방화벽 환경이면 로드가 조용히 실패하고 폴백 심장이 뜬다
- 텍스처: 2K로 낮춤
- Remesh: **Medium** (20~50K tris)
- Normal map 유지, Albedo/BaseColor는 버려도 됨 (유리 재질이 덮어씀)

주의: 로드 실패는 세션 동안 캐시된다 — GLB를 넣거나 교체한 뒤에는 **새로고침**해야
전환된다.

GLB를 받으면 https://gltf-viewer.donmccurdy.com 에 드래그해서 mesh 노드
이름을 확인하고, `src/components/organic-core/HeartCore.tsx`의 GLBHeart에서
`find(isMesh)` 폴백을 실제 노드 이름으로 바꾸면 더 정확합니다.
