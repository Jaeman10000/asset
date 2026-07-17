import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { HeartCore } from './HeartCore';
import { AuroraBackground } from './AuroraBackground';
import { LifeParticles } from './LifeParticles';
import { ReflectiveFloor } from './ReflectiveFloor';
import { useAdaptiveQuality } from './useAdaptiveQuality';
import { LIFE_COLOR } from './lifeColors';

/**
 * OrganicCoreScene — 심장 코어의 전체 대기감 버전.
 *
 * 구성 (그 AI 진단의 4가지 차이를 다 채움):
 *   - HeartCore        : 해부학적 유리질 심장 (①)
 *   - AuroraBackground : 청록 안개 셰이더 (③ 안개)
 *   - LifeParticles    : 떠다니는 생명력 입자 (③ 파티클)
 *   - ReflectiveFloor  : 바닥 반사 (③ 공간감)
 *   - Bloom            : 발광 번짐 (②④ 홀로그램 느낌)
 *   - LIFE_COLOR 공유  : 하나의 광원이 전체를 물들임 (②)
 *
 * 성능: useAdaptiveQuality가 FPS 감시 → 무거운 요소부터 자동으로 끔.
 * "최대 근접 대기감"이되 항상 떠 있어도 GPU를 안 태우는 구조.
 *
 * ⚠️ 추가 설치 필요:
 *   npm install @react-three/postprocessing postprocessing
 */

interface OrganicCoreSceneProps {
  bpm: number;
  /** 심장 박동 에너지 0~1.5 (대시보드의 heart.beatEnergy와 연동하면 파티클이 박동에 반응) */
  beatEnergy?: number;
}

export function OrganicCoreScene({ bpm, beatEnergy = 0 }: OrganicCoreSceneProps) {
  const { config } = useAdaptiveQuality(2);

  return (
    <Canvas
      camera={{ position: [0, 0.5, 5], fov: 45 }}
      gl={{ antialias: true, alpha: true }}
      dpr={[1, 1.5]}
    >
      <ambientLight intensity={0.12} />

      {/* 배경 안개 (제일 뒤) */}
      {config.aurora && <AuroraBackground color={LIFE_COLOR} depth={-8} />}

      {/* 바닥 반사 (심장 아래) */}
      {config.floor && (
        <ReflectiveFloor resolution={config.floorRes} blur={400} y={-2.2} />
      )}

      {/* 떠다니는 생명력 입자 */}
      {config.particleCount > 0 && (
        <LifeParticles count={config.particleCount} beatEnergy={beatEnergy} />
      )}

      {/* 해부학적 유리질 심장 (주인공) */}
      <HeartCore
        modelPath="/models/heart.glb"
        bpm={bpm}
        attenuationColor={LIFE_COLOR}
      />

      {/* 발광 번짐 — 홀로그램 느낌의 핵심 */}
      <EffectComposer>
        <Bloom
          intensity={0.9}
          luminanceThreshold={0.2}
          luminanceSmoothing={0.9}
          mipmapBlur
        />
      </EffectComposer>

      {/* 천천히 회전 = 정지 안 함 = 살아있음. 줌/팬은 끔 */}
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.4}
        minPolarAngle={Math.PI / 2.6}
        maxPolarAngle={Math.PI / 1.8}
      />
    </Canvas>
  );
}
