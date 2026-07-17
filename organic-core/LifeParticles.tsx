import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { LIFE_COLOR } from './lifeColors';

/**
 * LifeParticles — 심장에서 바깥으로 서서히 퍼지는 생명력 입자.
 *
 * 그 AI 진단의 "파티클이 떠다니는 대기감"을 만드는 요소.
 * 심장 박동(beatEnergy)에 맞춰 입자가 살짝 바깥으로 밀려나 "숨쉬는" 느낌.
 *
 * 성능: count를 낮추면 가벼워진다. 부모(OrganicCoreScene)의 quality 단계에서
 * count를 조절해 프레임 드롭 시 자동으로 줄일 수 있게 설계.
 */
interface LifeParticlesProps {
  count?: number;          // 입자 수 (60~150 권장, 성능에 따라 조절)
  color?: string;
  /** 0~1.5, 심장 박동 에너지. 부모에서 넘겨주면 박동에 반응 */
  beatEnergy?: number;
}

export function LifeParticles({
  count = 120,
  color = LIFE_COLOR,
  beatEnergy = 0,
}: LifeParticlesProps) {
  const pointsRef = useRef<THREE.Points>(null);

  // 초기 입자 위치: 심장 주변 구형 분포 (안쪽에 밀집, 바깥으로 희박)
  const { positions, seeds } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const seeds = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // 구면 좌표, 반경은 제곱근 분포로 안쪽 밀집
      const r = 1.5 + Math.sqrt(Math.random()) * 3.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6; // y축 눌러서 옆으로 퍼짐
      positions[i * 3 + 2] = r * Math.cos(phi);
      seeds[i] = Math.random();
    }
    return { positions, seeds };
  }, [count]);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, [positions]);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;
    const t = clock.getElapsedTime();
    const posAttr = pointsRef.current.geometry.attributes.position as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;

    for (let i = 0; i < count; i++) {
      const seed = seeds[i];
      // 각 입자가 자기 위치에서 아주 느리게 부유
      const drift = Math.sin(t * (0.1 + seed * 0.15) + seed * 6.28) * 0.15;
      // 심장 박동 시 바깥으로 살짝 밀림
      const push = 1 + beatEnergy * 0.04 * (0.5 + seed);
      const bx = positions[i * 3];
      const by = positions[i * 3 + 1];
      const bz = positions[i * 3 + 2];
      arr[i * 3] = bx * push + drift;
      arr[i * 3 + 1] = by * push + drift * 0.7;
      arr[i * 3 + 2] = bz * push - drift;
    }
    posAttr.needsUpdate = true;

    // 전체가 아주 느리게 회전 — 정지 안 함 = 살아있음
    pointsRef.current.rotation.y = t * 0.03;
  });

  return (
    <points ref={pointsRef} geometry={geometry}>
      <pointsMaterial
        color={color}
        size={0.06}
        sizeAttenuation
        transparent
        opacity={0.55}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}
