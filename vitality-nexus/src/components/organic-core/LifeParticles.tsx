import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { LIFE_COLOR } from './lifeColors';

/**
 * LifeParticles — 심장에서 바깥으로 서서히 퍼지는 생명력 입자.
 *
 * 그 AI 진단의 "파티클이 떠다니는 대기감"을 만드는 요소.
 * 심장 박동(beatEnergy)에 맞춰 입자가 살짝 바깥으로 밀려나 "숨쉬는" 느낌.
 *
 * 성능: 버퍼는 MAX_COUNT(150)로 1회만 할당하고 count는 drawRange로만 조절한다.
 * 적응형 품질이 count를 150↔100↔60으로 바꿔도 지오메트리 재생성이 없고
 * (= GPU 재할당 없음), 입자들이 새 난수 위치로 순간이동하는 팝도 생기지 않는다.
 */
const MAX_COUNT = 150;

interface LifeParticlesProps {
  count?: number;          // 표시할 입자 수 (0~150, 성능에 따라 조절)
  color?: string;
  /**
   * 0~1.5, 심장 박동 에너지. 대시보드 스토어(heart.beatEnergy)와 연동하면
   * 파티클이 그 값에 반응한다. **이 prop을 명시하면 내부 bpm 박동은 꺼진다**
   * (이중 박동 방지). 생략하면 bpm으로 내부 계산.
   */
  beatEnergy?: number;
  /**
   * beatEnergy가 없을 때 HeartCore와 동일한 수축 곡선(수축기+이중박동)을
   * 내부에서 계산하는 폴백. 외부 스토어 연동 전까지의 기본 동작.
   */
  bpm?: number;
}

export function LifeParticles({
  count = 120,
  color = LIFE_COLOR,
  beatEnergy,
  bpm,
}: LifeParticlesProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const visibleCount = Math.min(count, MAX_COUNT);

  // 초기 입자 위치: 심장 주변 구형 분포 (안쪽에 밀집, 바깥으로 희박)
  // MAX_COUNT로 1회만 생성 — count 변경 시에도 위치가 유지된다.
  const { positions, seeds } = useMemo(() => {
    const positions = new Float32Array(MAX_COUNT * 3);
    const seeds = new Float32Array(MAX_COUNT);
    for (let i = 0; i < MAX_COUNT; i++) {
      // 구면 좌표, 반경은 제곱근 분포로 안쪽 밀집.
      // 최대 반경을 카메라(z=5)에서 충분히 떨어뜨려, 코앞 입자가
      // sizeAttenuation으로 거대 사각형으로 보이는 것을 방지
      const r = 1.5 + Math.sqrt(Math.random()) * 2.6;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6; // y축 눌러서 옆으로 퍼짐
      positions[i * 3 + 2] = r * Math.cos(phi);
      seeds[i] = Math.random();
    }
    return { positions, seeds };
  }, []);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions.slice(), 3));
    return geo;
  }, [positions]);

  // R3F는 prop으로 주입한 외부 지오메트리를 자동 dispose하지 않으므로 직접 정리
  useEffect(() => () => geometry.dispose(), [geometry]);

  // count는 drawRange로만 반영 (재할당/텔레포트 없음)
  useEffect(() => {
    geometry.setDrawRange(0, visibleCount);
  }, [geometry, visibleCount]);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;
    const t = clock.getElapsedTime();
    const posAttr = pointsRef.current.geometry.attributes.position as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;

    // 외부 beatEnergy가 명시되면 그 값이 유일한 박동원.
    // 없으면 bpm으로 심장과 같은 위상의 박동을 자체 계산 (HeartCore와 동일 곡선).
    let energy = beatEnergy ?? 0;
    if (beatEnergy === undefined && bpm) {
      const phase = (t * (bpm / 60)) % 1;
      const systole = Math.exp(-Math.pow((phase - 0.08) / 0.06, 2));
      const secondaryBeat = 0.4 * Math.exp(-Math.pow((phase - 0.28) / 0.08, 2));
      energy = systole + secondaryBeat;
    }

    for (let i = 0; i < visibleCount; i++) {
      const seed = seeds[i];
      // 각 입자가 자기 위치에서 아주 느리게 부유
      const drift = Math.sin(t * (0.1 + seed * 0.15) + seed * 6.28) * 0.15;
      // 심장 박동 시 바깥으로 살짝 밀림
      const push = 1 + energy * 0.04 * (0.5 + seed);
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
