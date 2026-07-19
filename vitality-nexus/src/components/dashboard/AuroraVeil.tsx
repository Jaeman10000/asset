import { useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
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
 *
 * fps 캡: 기본 frameloop은 모니터 주사율(예: 165Hz)로 매 프레임 렌더한다.
 * 흐릿한 안개는 24fps면 충분하므로 demand + 저속 페이서로 상한을 건다
 * (메인 씬 FramePacer와 같은 패턴, QA 지적 — 유휴 GPU/배터리 절약).
 */

const VEIL_FPS = 24;

function VeilPacer() {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    let raf = 0;
    let next = 0;
    const interval = 1000 / VEIL_FPS;
    const loop = (t: number) => {
      raf = requestAnimationFrame(loop);
      if (t >= next) {
        next = next === 0 || t - next > interval * 2 ? t + interval : next + interval;
        invalidate();
      }
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [invalidate]);
  return null;
}

export function AuroraVeil() {
  return (
    <div className="aurora-veil" aria-hidden>
      <Canvas
        dpr={0.12}
        gl={{ alpha: true, antialias: false }}
        camera={{ position: [0, 0, 5], fov: 45 }}
        frameloop="demand"
      >
        <VeilPacer />
        <AuroraBackground color={LIFE_COLOR} depth={-6} />
      </Canvas>
    </div>
  );
}
