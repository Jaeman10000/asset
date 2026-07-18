import { Canvas } from '@react-three/fiber';
import { AuroraBackground } from '../organic-core/AuroraBackground';
import { LIFE_COLOR } from '../organic-core/lifeColors';

/**
 * AuroraVeil — 렉 없는 고급 안개 배경.
 *
 * 검증된 AuroraBackground(오로라 셰이더)를 별도 R3F 캔버스에서 돌리되
 * dpr을 0.12로 고정한다: 1440px 화면 기준 백버퍼가 ~170px밖에 안 되어
 * 셰이더 비용이 원래의 ~1.5%로 떨어지고, CSS 확대 + 블러로 펼치면
 * 안개는 어차피 흐릿하므로 시각적으로 동일하다.
 * (풀스크린 오로라가 내장 그래픽 렉의 주범이었던 것의 해법)
 */
export function AuroraVeil() {
  return (
    <div className="aurora-veil" aria-hidden>
      <Canvas
        dpr={0.12}
        gl={{ alpha: true, antialias: false }}
        camera={{ position: [0, 0, 5], fov: 45 }}
      >
        <AuroraBackground color={LIFE_COLOR} depth={-6} />
      </Canvas>
    </div>
  );
}
