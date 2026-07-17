import { useRef, useMemo } from 'react';
import { useFrame, useThree, extend, type ThreeElement } from '@react-three/fiber';
import { shaderMaterial } from '@react-three/drei';
import * as THREE from 'three';

import fragmentShader from '../../shaders/aurora.frag.glsl?raw';
import vertexShader from '../../shaders/aurora.vert.glsl?raw';

// `?raw` import requires Vite (default for Tauri + React). If your bundler
// doesn't support it, inline the shader strings directly instead.

const AuroraMaterial = shaderMaterial(
  {
    uTime: 0,
    uColor: new THREE.Color('#2be6c8'), // keep in sync with HeartCore.attenuationColor
    uResolution: new THREE.Vector2(1, 1),
  },
  vertexShader,
  fragmentShader
);

extend({ AuroraMaterial });

// shaderMaterial이 uniform마다 런타임 getter/setter를 만들어 주지만
// 타입에는 없으므로 인스턴스 타입을 명시적으로 보강한다.
type AuroraMaterialImpl = THREE.ShaderMaterial & {
  uTime: number;
  uColor: THREE.Color;
  uResolution: THREE.Vector2;
};

// R3F v9 방식: 특화 Node 타입(Object3DNode/MaterialNode 등)이 제거되고
// ThreeElement 하나로 통합됨. uniform prop은 위 Impl 타입에서 가져온다.
// (v8이었다면 declare global + JSX.IntrinsicElements 확장이 필요했다.)
declare module '@react-three/fiber' {
  interface ThreeElements {
    auroraMaterial: ThreeElement<typeof AuroraMaterial> &
      Partial<Pick<AuroraMaterialImpl, 'uTime' | 'uColor' | 'uResolution'>>;
  }
}

interface AuroraBackgroundProps {
  color?: string;
  /** Distance behind the heart core, in scene units */
  depth?: number;
}

/**
 * Fullscreen-ish plane behind the heart, rendered with a domain-warped
 * simplex noise shader instead of Canvas 2D — gives real depth/parallax
 * as the camera moves, and can share exact color with the heart's glow.
 */
export function AuroraBackground({ color = '#2be6c8', depth = -6 }: AuroraBackgroundProps) {
  const materialRef = useRef<AuroraMaterialImpl>(null);
  const { viewport } = useThree();

  const colorObj = useMemo(() => new THREE.Color(color), [color]);

  useFrame(({ clock }) => {
    if (materialRef.current) {
      materialRef.current.uTime = clock.getElapsedTime();
    }
  });

  return (
    <mesh position={[0, 0, depth]}>
      {/* Oversize relative to viewport so it still covers the frame
          when the camera orbits slightly. */}
      <planeGeometry args={[viewport.width * 2.5, viewport.height * 2.5, 1, 1]} />
      <auroraMaterial
        ref={materialRef}
        uColor={colorObj}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}
