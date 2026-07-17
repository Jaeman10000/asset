import { useRef, useMemo } from 'react';
import { useFrame, useThree, extend } from '@react-three/fiber';
import { shaderMaterial } from '@react-three/drei';
import * as THREE from 'three';

import fragmentShader from '../shaders/aurora.frag.glsl?raw';
import vertexShader from '../shaders/aurora.vert.glsl?raw';

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

declare module '@react-three/fiber' {
  interface ThreeElements {
    auroraMaterial: any;
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
  const materialRef = useRef<any>(null);
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
      {/* @ts-expect-error custom shader material registered via extend() */}
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
