import { Component, Suspense, type ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { HeartCore } from '../organic-core/HeartCore';
import { HEART_COLOR } from '../organic-core/lifeColors';

/**
 * HeartOrb — 자산구성 도넛 중앙에서 뛰는 작은 3D 심장 (v0.3 디자인의 핵심 융합).
 * 배경 풀스크린 씬을 없애고, 기존 HeartCore(유리질 심장 + 글로우 + 심박)를
 * 카드 안 소형 캔버스로 옮겼다. "Heart at the Center"가 레이아웃의 중심 논리가 된다.
 */

/** WebGL 오류 시 심장만 조용히 숨김 (대시보드는 계속) */
class OrbBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn('[heart-orb] 3D 심장 오류 — 심장 없이 계속', error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** FpsMeter(우하단)가 읽는 전역 렌더 카운터 — 배경 씬 제거 후에도 실측 fps 유지 */
function RenderTick() {
  useFrame(() => {
    const w = window as unknown as Record<string, number>;
    w.__renderCount = (w.__renderCount ?? 0) + 1;
  });
  return null;
}

export function HeartOrb({ bpm, size = 150 }: { bpm: number; size?: number }) {
  return (
    <div className="heart-orb" style={{ width: size, height: size }}>
      <OrbBoundary>
        <Canvas
          dpr={1}
          gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
          camera={{ position: [0, 0, 4.4], fov: 38 }}
        >
          <RenderTick />
          <ambientLight intensity={0.35} />
          <Suspense fallback={null}>
            <HeartCore
              modelPath="/models/heart.glb"
              bpm={bpm}
              attenuationColor={HEART_COLOR}
              scale={1.05}
              transmissionRes={128}
              backside={false}
            />
          </Suspense>
        </Canvas>
      </OrbBoundary>
    </div>
  );
}
