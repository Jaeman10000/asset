import { useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { MOUSE } from 'three';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { HeartCore } from './HeartCore';
import { AuroraBackground } from './AuroraBackground';
import { LifeParticles } from './LifeParticles';
import { ReflectiveFloor } from './ReflectiveFloor';
import { useAdaptiveQuality, QUALITY_LEVELS } from './useAdaptiveQuality';
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
 * 성능 (상시 떠 있는 위젯 전제):
 *   - maxFps 캡: 모니터 주사율(예: 165Hz)로 풀 파이프라인을 돌리지 않도록
 *     demand 렌더 + 자체 페이스 루프로 상한을 건다. 탭이 숨겨지면 RAF가 멈춰
 *     렌더도 자동 정지된다.
 *   - useAdaptiveQuality: FPS 감시 → 파티클/바닥반사부터 자동으로 끔.
 *
 * GUIDE.md 통합 순서(심장→오로라→색→파티클→바닥→Bloom→성능)를 하나씩 확인할 수
 * 있도록 각 레이어에 토글 prop을 뒀다. 기본값은 전부 켜짐(최종 상태).
 */

interface OrganicCoreSceneProps {
  bpm: number;
  /**
   * 심장 박동 에너지 0~1.5. 대시보드의 heart.beatEnergy와 연동하면 파티클이
   * 그 값에 반응한다 (명시하면 파티클의 내부 bpm 박동은 꺼짐 — 이중 박동 방지).
   * 생략하면 파티클이 bpm으로 박동을 자체 계산한다.
   */
  beatEnergy?: number;
  /** ── 단계별 통합 확인용 토글 (기본 전부 켬) ── */
  aurora?: boolean;
  particles?: boolean;
  floor?: boolean;
  bloom?: boolean;
  /** false면 FPS 적응 없이 medium(레벨 2) 고정 */
  adaptive?: boolean;
  /** 'never'면 RAF 대신 advance()로 수동 구동 (숨겨진 탭에서의 자동 검증용) */
  frameloop?: 'always' | 'never';
  /** 렌더 상한 fps — 상시 위젯의 배터리/발열 대책. 0이면 캡 없음 */
  maxFps?: number;
}

export function OrganicCoreScene({
  bpm,
  beatEnergy,
  // 안개는 3D 씬의 풀스크린 셰이더(렉 주범) 대신 DOM 레이어 AuroraVeil
  // (초저해상도+CSS블러, 비용 ~2%)가 담당한다. 여기선 심장/파티클/Bloom만.
  aurora = false,
  particles = true,
  floor = false,
  bloom = true,
  adaptive = true,
  frameloop = 'always',
  maxFps = 60,
}: OrganicCoreSceneProps) {
  // 수동 구동(never) 중에는 측정이 무의미하므로 (idle RAF 주기를 재게 됨) 끔
  // 약한 GPU 우선: 레벨 1(파티클 36)에서 시작해 여유가 있으면 자동 승급한다.
  const { level, config: adaptiveConfig } = useAdaptiveQuality(
    1,
    adaptive && frameloop === 'always'
  );
  const config = adaptive ? adaptiveConfig : QUALITY_LEVELS[2];

  // 자동화 검증/디버깅용: 현재 적응형 품질 레벨을 window에 노출
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__qualityLevel = adaptive ? level : 'fixed(2)';
  }, [level, adaptive]);

  return (
    <Canvas
      camera={{ position: [0, 0.5, 5], fov: 45 }}
      // bloom이 켜지면 EffectComposer가 MSAA 오프스크린 버퍼에 렌더하므로
      // 캔버스 자체 antialias는 이득 없이 메모리/리졸브 비용만 이중으로 든다
      gl={{ antialias: !bloom, alpha: true }}
      // dpr 1 고정: 상시 배경 위젯이라 선명함보다 부하가 중요하다. 디스플레이 배율
      // 150%(dpr 1.5)면 백버퍼가 2.25배가 되어 유리 심장 트랜스미션·파티클 래스터가
      // 그만큼 무거워지는 게 약한 GPU(Intel UHD) 렉의 최대 주범이었다. DOM/글래스
      // UI 텍스트는 CSS라 네이티브 해상도 그대로 선명하게 유지된다(캔버스만 1x).
      dpr={1}
      // 'demand' + FramePacer 조합으로 maxFps 캡 (frameloop prop이 'never'면 그대로)
      frameloop={frameloop === 'always' && maxFps > 0 ? 'demand' : frameloop}
    >
      {frameloop === 'always' && maxFps > 0 && <FramePacer fps={maxFps} />}
      <RenderCounter />
      <CameraProbe />

      <ambientLight intensity={0.12} />

      {/* 바닥 먼 가장자리를 어둠에 녹여 하드 라인 제거 (오로라는 커스텀 셰이더라
          fog의 영향을 받지 않음 — 배경 밝기는 유지된다) */}
      <fog attach="fog" args={['#050709', 9, 22]} />

      {/* 배경 안개 (제일 뒤) */}
      {aurora && config.aurora && <AuroraBackground color={LIFE_COLOR} depth={-8} />}

      {/* 바닥 반사 (심장 아래) — 해상도는 고정 (가변 시 FBO 고아화, useAdaptiveQuality 주석 참고) */}
      {floor && config.floor && (
        <ReflectiveFloor resolution={config.floorRes} blur={400} y={-2.2} />
      )}

      {/* 심장을 중앙에 배치 — 상단 총합 4카드에 위쪽이 가리지 않도록 y를 낮춤.
          자동 자전은 제거: 궤도가 12시=1위로 고정되고, 회전은 사용자가
          OrbitControls로 카메라를 돌릴 때만 일어난다 (심장·궤도·섹터가 한 덩어리로
          같이 움직임 = 카메라 오빗). 살아있는 느낌은 심박 스케일·섹터 파티클·
          프로젝터 디스크·beat-rings가 담당한다. */}
      <group position={[0, 0.55, 0]}>
        {/* 떠다니는 생명력 입자 (beatEnergy 미지정 시 bpm으로 심장과 같은 위상으로 숨쉼).
            섹터 궤도(HoloSectorRings)는 제거 — 심장만 주인공으로, 부하도 크게 줄인다. */}
        {particles && config.particleCount > 0 && (
          <LifeParticles count={config.particleCount} beatEnergy={beatEnergy} bpm={bpm} />
        )}

        {/* 해부학적 유리질 심장 — 이제 씬의 유일한 오브젝트라 좀 더 크게 */}
        <HeartCore
          modelPath="/models/heart.glb"
          bpm={bpm}
          attenuationColor={LIFE_COLOR}
          scale={0.72}
          transmissionRes={256}
          backside={false}
        />
      </group>

      {/* 발광 번짐 — 홀로그램 느낌의 핵심. 단, 심박마다 심장이 하얗게 터지지
          않도록 강도를 낮추고 컷오프를 올려 "가장 밝은 하이라이트만" 물게 한다. */}
      {bloom && (
        <EffectComposer multisampling={4}>
          <Bloom
            intensity={0.42}
            // 컷오프를 올릴수록 어두운 부분은 안 물고 하이라이트만 은은히 번진다
            luminanceThreshold={0.5}
            luminanceSmoothing={0.85}
            mipmapBlur
          />
        </EffectComposer>
      )}

      {/* 사용자가 심장을 자유롭게 배치: 좌클릭 드래그=회전, 휠클릭 드래그=이동(팬),
          휠 스크롤=확대/축소. 카메라가 도므로 궤도·섹터가 심장과 함께 움직인다.
          drag/zoom은 사용자 이벤트라 demand 모드의 fps 캡을 깨지 않는다(자가 루프 없음). */}
      <OrbitControls
        makeDefault
        enableRotate
        enablePan
        enableZoom
        mouseButtons={{ LEFT: MOUSE.ROTATE, MIDDLE: MOUSE.PAN, RIGHT: MOUSE.PAN }}
        rotateSpeed={0.8}
        panSpeed={0.7}
        zoomSpeed={0.9}
        target={[0, 0.5, 0]}
        minDistance={2.5}
        maxDistance={9}
        minPolarAngle={Math.PI / 5}
        maxPolarAngle={Math.PI / 1.5}
      />
    </Canvas>
  );
}

/**
 * FramePacer — demand 모드에서 최대 fps 상한으로 invalidate를 발행하는 페이스 루프.
 * RAF 기반이므로 탭이 숨겨지면 자동으로 멈추고, GPU가 상한을 못 따라가면
 * 자연히 그 속도로 떨어진다 (useAdaptiveQuality가 그때 품질을 낮춘다).
 */
function FramePacer({ fps }: { fps: number }) {
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => {
    let raf = 0;
    let next = 0;
    const interval = 1000 / fps;
    const loop = (t: number) => {
      raf = requestAnimationFrame(loop);
      if (t >= next) {
        // 누적 스케줄 방식: RAF 지터가 있어도 평균이 fps에 수렴 (드리프트 없음)
        next = next === 0 || t - next > interval * 2 ? t + interval : next + interval;
        invalidate();
      }
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [fps, invalidate]);

  return null;
}

/** 실제 렌더된 프레임 수를 window.__renderCount로 노출 (FPS 표시/검증용) */
function RenderCounter() {
  useFrame(() => {
    const w = window as unknown as Record<string, number>;
    w.__renderCount = (w.__renderCount ?? 0) + 1;
  });
  return null;
}

/** 카메라 위치를 window.__camPos로 노출 (드래그 회전 자동 검증용) */
function CameraProbe() {
  useFrame(({ camera }) => {
    (window as unknown as Record<string, unknown>).__camPos = [
      +camera.position.x.toFixed(3),
      +camera.position.y.toFixed(3),
      +camera.position.z.toFixed(3),
    ];
  });
  return null;
}
