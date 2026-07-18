import { useEffect, useRef } from 'react';

/**
 * SectorFlowOrbs — 프로토타입 full-dashboard-v2.html의 drawFlow 오브 시각화 이식.
 * 좌: 한국(warm), 우: 미국(cool). 각 오브에서 섹터 노드로 파티클이 흘러가고,
 * 받은 섹터가 발광한다. 파티클 색: 상승 시안 / 하락 보라 (US), warm 계열 (KR).
 *
 * 데이터: US는 실 SPDR 섹터 등락률, KR은 보유 종목 섹터별 평균 등락률.
 * (프로토타입의 외국인/기관/개인 3색 파티클은 KRX 투자자 데이터가 필요 → 추후)
 */

export interface OrbSector {
  name: string;
  ret: number;
}

interface Particle {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  born: number;
  dur: number;
  key: string;
  side: 'kr' | 'us';
  hue: number;
  strength: number;
}

export function SectorFlowOrbs({ kr, us }: { kr: OrbSector[]; us: OrbSector[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dataRef = useRef({ kr, us });
  dataRef.current = { kr, us };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const particles: Particle[] = [];
    const glows: { kr: Record<string, number>; us: Record<string, number> } = { kr: {}, us: {} };
    let lastSpawn = 0;
    let raf = 0;

    const drawAuroraOrb = (cx: number, cy: number, R: number, now: number, warm: boolean, beat: number) => {
      const auroras = warm
        ? [
            { hue: 30, phase: 0, speed: 0.00032, ampl: 0.35 },
            { hue: 15, phase: 1.5, speed: 0.00044, ampl: 0.42 },
            { hue: 45, phase: 3.2, speed: 0.00024, ampl: 0.28 },
          ]
        : [
            { hue: 190, phase: 0, speed: 0.00032, ampl: 0.35 },
            { hue: 210, phase: 1.5, speed: 0.00044, ampl: 0.42 },
            { hue: 280, phase: 3.2, speed: 0.00024, ampl: 0.28 },
          ];
      auroras.forEach((a) => {
        const t = now * a.speed + a.phase;
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        for (let ring = 0; ring < 2; ring++) {
          const ringOff = ring * 6;
          const alpha = (0.2 - ring * 0.05) * (1 + beat * 0.3);
          ctx.strokeStyle = `hsla(${a.hue + Math.sin(t) * 30}, 75%, 65%, ${alpha})`;
          ctx.lineWidth = 1.5 + ring * 0.5;
          ctx.beginPath();
          for (let i = 0; i <= 48; i++) {
            const angle = (i / 48) * Math.PI * 2;
            const wob = 1 + Math.sin(angle * 3 + t * 2 + a.phase) * a.ampl * 0.2;
            const rr = (R + ringOff) * wob;
            const x = cx + Math.cos(angle) * rr;
            const y = cy + Math.sin(angle) * rr;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          }
          ctx.closePath();
          ctx.stroke();
        }
        ctx.restore();
      });
      // 외곽 글로우
      const glowR = R * 3;
      const outer = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, glowR);
      outer.addColorStop(0, warm ? `hsla(30,70%,60%,${0.14 + beat * 0.08})` : `hsla(200,70%,60%,${0.14 + beat * 0.08})`);
      outer.addColorStop(0.4, warm ? 'hsla(340,60%,55%,0.06)' : 'hsla(240,60%,55%,0.06)');
      outer.addColorStop(1, warm ? 'hsla(15,50%,50%,0)' : 'hsla(280,50%,50%,0)');
      ctx.fillStyle = outer;
      ctx.beginPath();
      ctx.arc(cx, cy, glowR, 0, Math.PI * 2);
      ctx.fill();
      // 본체
      const body = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.35, 0, cx, cy, R);
      if (warm) {
        body.addColorStop(0, 'hsla(40,60%,75%,0.65)');
        body.addColorStop(0.5, 'hsla(20,55%,52%,0.5)');
        body.addColorStop(1, 'hsla(345,55%,28%,0.7)');
      } else {
        body.addColorStop(0, 'hsla(190,60%,75%,0.65)');
        body.addColorStop(0.5, 'hsla(210,55%,52%,0.5)');
        body.addColorStop(1, 'hsla(265,55%,28%,0.7)');
      }
      ctx.fillStyle = body;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fill();
      // 코어 하이라이트
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.5);
      core.addColorStop(0, `rgba(255,255,255,${0.85 + beat * 0.15})`);
      const midHue = warm ? 40 : 180;
      core.addColorStop(0.6, `hsla(${midHue},90%,85%,0.4)`);
      core.addColorStop(1, `hsla(${midHue + 20},85%,70%,0)`);
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 0.5, 0, Math.PI * 2);
      ctx.fill();
    };

    const drawOrb = (
      cx: number,
      cy: number,
      orbR: number,
      ringR: number,
      sectors: OrbSector[],
      side: 'kr' | 'us',
      warm: boolean,
      now: number,
      beat: number,
    ) => {
      const sr = 16;
      const positions = sectors.map((s, i) => {
        const angle = -Math.PI / 2 + (i / Math.max(sectors.length, 1)) * Math.PI * 2;
        return { ...s, x: cx + Math.cos(angle) * ringR, y: cy + Math.sin(angle) * ringR, angle };
      });
      // 노드 발광(aura)
      positions.forEach((s) => {
        let glow = glows[side][s.name] ?? 0;
        glow = Math.max(0, glow - 0.006); // 서서히 감쇠
        glows[side][s.name] = glow;
        const hue = warm ? (s.ret >= 0 ? 40 : 15) : s.ret >= 0 ? 195 : 240;
        if (glow > 0.05) {
          const auraR = sr + 16 + glow * 22;
          const aura = ctx.createRadialGradient(s.x, s.y, sr * 0.9, s.x, s.y, auraR);
          aura.addColorStop(0, `hsla(${hue},85%,70%,${glow * 0.7})`);
          aura.addColorStop(1, `hsla(${hue},80%,65%,0)`);
          ctx.fillStyle = aura;
          ctx.beginPath();
          ctx.arc(s.x, s.y, auraR, 0, Math.PI * 2);
          ctx.fill();
        }
        // 노드 본체
        const bg = ctx.createRadialGradient(s.x - sr * 0.3, s.y - sr * 0.3, 0, s.x, s.y, sr);
        bg.addColorStop(0, `hsla(${hue},40%,30%,0.9)`);
        bg.addColorStop(1, `hsla(${hue},35%,12%,0.6)`);
        ctx.fillStyle = bg;
        ctx.beginPath();
        ctx.arc(s.x, s.y, sr, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = `hsla(${hue},${70 + glow * 20}%,${45 + glow * 35}%,${0.4 + glow * 0.6})`;
        ctx.lineWidth = 1 + glow * 3;
        ctx.beginPath();
        ctx.arc(s.x, s.y, sr, 0, Math.PI * 2);
        ctx.stroke();
        // 라벨
        ctx.fillStyle = `rgba(232,236,240,${0.85 + glow * 0.15})`;
        ctx.font = '8px ui-monospace,monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(s.name.slice(0, 4), s.x, s.y);
      });
      drawAuroraOrb(cx, cy, orbR, now, warm, beat);
      return positions;
    };

    const render = (now: number) => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width < 4) {
        raf = requestAnimationFrame(render);
        return;
      }
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(rect.width * dpr)) {
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      const W = rect.width;
      const H = rect.height;
      ctx.clearRect(0, 0, W, H);
      const beat = 0.25 + 0.25 * Math.sin(now * 0.002);

      const orbR = Math.min(W / 2, H) * 0.13;
      const ringR = Math.min(W / 2, H) * 0.36;
      const krCx = W * 0.26,
        krCy = H * 0.52;
      const usCx = W * 0.74,
        usCy = H * 0.52;

      const { kr: krS, us: usS } = dataRef.current;
      const krPos = drawOrb(krCx, krCy, orbR, ringR, krS, 'kr', true, now, beat);
      const usPos = drawOrb(usCx, usCy, orbR, ringR, usS, 'us', false, now, beat);

      // 파티클 스폰 (등락률 클수록 자주)
      if (now - lastSpawn > 420) {
        lastSpawn = now;
        const spawn = (
          pos: ReturnType<typeof drawOrb>,
          cx: number,
          cy: number,
          side: 'kr' | 'us',
          warm: boolean,
        ) => {
          const maxRet = Math.max(...pos.map((s) => Math.abs(s.ret)), 0.1);
          pos.forEach((s) => {
            const intensity = Math.abs(s.ret) / maxRet;
            if (intensity < 0.2) return;
            if (Math.random() < intensity * intensity * 0.9) {
              const dx = s.x - cx,
                dy = s.y - cy;
              const dist = Math.hypot(dx, dy) || 1;
              const ux = dx / dist,
                uy = dy / dist;
              particles.push({
                x0: cx + ux * orbR,
                y0: cy + uy * orbR,
                x1: s.x - ux * 20,
                y1: s.y - uy * 20,
                born: now,
                dur: 1600 + Math.random() * 500,
                key: s.name,
                side,
                hue: warm ? (s.ret >= 0 ? 45 : 15) : s.ret >= 0 ? 195 : 240,
                strength: intensity,
              });
            }
          });
        };
        spawn(krPos, krCx, krCy, 'kr', true);
        spawn(usPos, usCx, usCy, 'us', false);
        if (particles.length > 120) particles.splice(0, particles.length - 120);
      }

      // 파티클 그리기
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        const t = (now - p.born) / p.dur;
        if (t >= 1) {
          glows[p.side][p.key] = Math.min(1, (glows[p.side][p.key] ?? 0) + 0.06 + p.strength * 0.18);
          particles.splice(i, 1);
          continue;
        }
        const px = p.x0 + (p.x1 - p.x0) * t;
        const py = p.y0 + (p.y1 - p.y0) * t;
        const sc = 0.6 + p.strength;
        for (let k = 0; k < 5; k++) {
          const tk = Math.max(0, t - k * 0.03);
          const kx = p.x0 + (p.x1 - p.x0) * tk;
          const ky = p.y0 + (p.y1 - p.y0) * tk;
          ctx.fillStyle = `hsla(${p.hue},85%,75%,${(1 - k / 5) * 0.5})`;
          ctx.beginPath();
          ctx.arc(kx, ky, 1.5 * (1 - k / 5) * sc, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = `hsla(${p.hue},95%,85%,0.9)`;
        ctx.beginPath();
        ctx.arc(px, py, 2 * sc, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} className="flow-canvas" />;
}
