import { useState, useRef, useEffect } from 'react';

/**
 * useAdaptiveQuality — FPS를 감시해서 시각 품질을 자동으로 단계 조절.
 *
 * 왜 필요한가: 이건 항상 떠 있는 데스크톱 위젯이다. 파티클+바닥반사+유리재질을
 * 다 켜면 예쁘지만 GPU를 계속 태운다. 노트북 배터리, 발열 문제.
 * → 프레임이 떨어지면 자동으로 무거운 요소부터 끈다.
 *
 * 품질 단계:
 *   3 (high)   : 파티클 150 + 바닥반사 + 풀 오로라   — 성능 여유 있을 때
 *   2 (medium) : 파티클 100 + 바닥반사 + 오로라       — 기본
 *   1 (low)    : 파티클 60  + 바닥반사 + 오로라        — 프레임 빠듯
 *   0 (minimal): 파티클 0   + 바닥반사 끔 + 오로라만   — 심하게 느릴 때
 *
 * 바닥반사 해상도는 의도적으로 고정이다: drei MeshReflectorMaterial은 resolution이
 * 바뀔 때 기존 렌더타깃(2048² 기준 ~142MB)을 dispose하지 않고 재생성하므로,
 * 레벨별로 해상도를 바꾸면 강등 순간마다 VRAM 고아화 + 재할당 히치가 생긴다.
 * 품질 레버는 [파티클 수, 바닥 on/off]로만 잡는다.
 *
 * 사용:
 *   const { level, config } = useAdaptiveQuality();
 *   <LifeParticles count={config.particleCount} />
 *   {config.floor && <ReflectiveFloor resolution={config.floorRes} />}
 */

export interface QualityConfig {
  particleCount: number;
  floor: boolean;
  floorRes: number;
  aurora: boolean;
}

export const QUALITY_LEVELS: Record<number, QualityConfig> = {
  3: { particleCount: 90, floor: true,  floorRes: 1024, aurora: true },
  2: { particleCount: 60, floor: true,  floorRes: 1024, aurora: true },
  1: { particleCount: 36, floor: true,  floorRes: 1024, aurora: true },
  0: { particleCount: 0,  floor: false, floorRes: 1024, aurora: true },
};

/**
 * 탭 숨김/복귀나 GC 스톨로 생긴 단발성 거대 dt가 60프레임 평균을 오염시켜
 * 허위 강등을 만드는 것을 막는 상한. 진짜로 느린 기기(예: 2fps → dt 500ms)도
 * 클램프된 250ms 평균 = 4fps로 정상 강등되므로 감지 능력은 유지된다.
 */
const DT_CLAMP_MS = 250;

export function useAdaptiveQuality(startLevel: number = 2, enabled: boolean = true) {
  const [level, setLevel] = useState(startLevel);
  const frameTimes = useRef<number[]>([]);
  const lastTime = useRef(performance.now());
  const levelRef = useRef(startLevel);
  const stableFrames = useRef(0);

  useEffect(() => {
    // adaptive=false이거나 수동 프레임 구동(frameloop='never') 중에는 측정 자체가
    // 무의미하므로 (렌더가 아니라 브라우저 idle RAF 주기를 재게 됨) 루프를 돌리지 않음
    if (!enabled) return;

    let raf: number;

    // 렌더 시점(useRef 초기화)과 effect 시작 사이의 지연이 첫 샘플을 부풀리지 않도록
    lastTime.current = performance.now();

    // 탭 숨김 → 복귀 시 측정 창을 통째로 리셋 (복귀 직후 프레임은 신뢰 불가)
    const onVisibilityChange = () => {
      frameTimes.current = [];
      lastTime.current = performance.now();
      stableFrames.current = 0;
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    const tick = () => {
      const now = performance.now();
      const dt = Math.min(now - lastTime.current, DT_CLAMP_MS);
      lastTime.current = now;
      frameTimes.current.push(dt);

      // 60프레임마다 평가
      if (frameTimes.current.length >= 60) {
        const avg = frameTimes.current.reduce((a, b) => a + b, 0) / frameTimes.current.length;
        const fps = 1000 / avg;

        if (fps < 45 && levelRef.current > 0) {
          // 느림 → 품질 낮춤 (즉시)
          levelRef.current -= 1;
          setLevel(levelRef.current);
          stableFrames.current = 0;
        } else if (fps > 58 && levelRef.current < 3) {
          // 빠름이 지속되면 → 품질 높임 (신중하게, 5초 안정 후)
          stableFrames.current += 60;
          if (stableFrames.current > 300) {
            levelRef.current += 1;
            setLevel(levelRef.current);
            stableFrames.current = 0;
          }
        } else {
          stableFrames.current = 0;
        }
        frameTimes.current = [];
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [enabled]);

  return { level, config: QUALITY_LEVELS[level] };
}
