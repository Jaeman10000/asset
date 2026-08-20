import { Component, Suspense, useRef, type ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import type { Group } from 'three';
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

/** 천천히 자전 — 유리 재질의 하이라이트가 계속 흐르며 입체감이 산다 */
function Spin({ children }: { children: ReactNode }) {
  const ref = useRef<Group>(null);
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.y += dt * 0.35;
  });
  return <group ref={ref}>{children}</group>;
}

export function HeartOrb({ bpm, size = 150 }: { bpm: number; size?: number }) {
  return (
    <div className="heart-orb" style={{ width: size, height: size }}>
      <OrbBoundary>
        <Canvas
          dpr={window.devicePixelRatio > 1 ? 1.5 : 1}
          gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
          camera={{ position: [0, 0, 3.9], fov: 38 }}
        >
          <RenderTick />
          {/* 저퀄 지적(어둡고 납작) 수선 — 키/림 라이트로 유리질 광택 살림 */}
          <ambientLight intensity={0.55} />
          <directionalLight position={[2.5, 3, 4]} intensity={1.4} />
          <pointLight position={[-3, -1, 2]} intensity={0.6} color={HEART_COLOR} />
          <Suspense fallback={null}>
            <Spin>
              <HeartCore
                modelPath="/models/heart.glb"
                bpm={bpm}
                attenuationColor={HEART_COLOR}
                scale={1.18}
                transmissionRes={192}
                backside={false}
              />
            </Spin>
          </Suspense>
        </Canvas>
      </OrbBoundary>
    </div>
  );
}
