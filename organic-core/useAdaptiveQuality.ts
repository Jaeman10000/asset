import { useState, useRef, useEffect } from 'react';

/**
 * useAdaptiveQuality — FPS를 감시해서 시각 품질을 자동으로 단계 조절.
 *
 * 왜 필요한가: 이건 항상 떠 있는 데스크톱 위젯이다. 파티클+바닥반사+유리재질을
 * 다 켜면 예쁘지만 GPU를 계속 태운다. 노트북 배터리, 발열 문제.
 * → 프레임이 떨어지면 자동으로 무거운 요소부터 끈다.
 *
 * 품질 단계:
 *   3 (high)   : 파티클 150 + 바닥반사 2048 + 풀 오로라   — 성능 여유 있을 때
 *   2 (medium) : 파티클 100 + 바닥반사 1024 + 오로라       — 기본
 *   1 (low)    : 파티클 60  + 바닥반사 512  + 오로라        — 프레임 빠듯
 *   0 (minimal): 파티클 0   + 바닥반사 끔   + 오로라만      — 심하게 느릴 때
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

const QUALITY_LEVELS: Record<number, QualityConfig> = {
  3: { particleCount: 150, floor: true,  floorRes: 2048, aurora: true },
  2: { particleCount: 100, floor: true,  floorRes: 1024, aurora: true },
  1: { particleCount: 60,  floor: true,  floorRes: 512,  aurora: true },
  0: { particleCount: 0,   floor: false, floorRes: 512,  aurora: true },
};

export function useAdaptiveQuality(startLevel: number = 2) {
  const [level, setLevel] = useState(startLevel);
  const frameTimes = useRef<number[]>([]);
  const lastTime = useRef(performance.now());
  const levelRef = useRef(startLevel);
  const stableFrames = useRef(0);

  useEffect(() => {
    let raf: number;
    const tick = () => {
      const now = performance.now();
      const dt = now - lastTime.current;
      lastTime.current = now;
      frameTimes.current.push(dt);
      if (frameTimes.current.length > 60) frameTimes.current.shift();

      // 60프레임마다 평가
      if (frameTimes.current.length === 60) {
        const avg = frameTimes.current.reduce((a, b) => a + b, 0) / 60;
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
    return () => cancelAnimationFrame(raf);
  }, []);

  return { level, config: QUALITY_LEVELS[level] };
}
