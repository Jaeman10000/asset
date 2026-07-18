import { useEffect, useRef } from 'react';

/**
 * SectorFlowOrbs — 오브 본체는 청록(생명) 컨셉, 파티클은 스펙의 정보 인코딩 색.
 *
 * 스펙 1장 "파티클 색으로 정보 인코딩":
 *   한국: 외국인=금색(45) · 기관=청록(175) · 개인=회청(220) — 3색 수급 파티클
 *   미국: 상승=시안(195) · 하락=보라(240)
 * 오브/노드 본체는 청록 계열로 유지해 심장·카드와 같은 광원 느낌.
 *
 * 데이터: KR은 KRX 12섹터 수급 강도(모의→실데이터 교체 예정), US는 실 SPDR.
 */

// 청록(생명력) 오브 본체 색
const LIFE_HUE_KR = 168;
const LIFE_HUE_US = 184;
// 스펙의 정보 인코딩 색 (파티클)
const INV_HUES = { foreign: 45, inst: 175, individual: 220 } as const;
const US_UP_HUE = 195;
const US_DOWN_HUE = 240;

export interface OrbSector {
  name: string;
  ret: number;
  /** KR만: 투자자별 순매수 강도 0~1 (3색 파티클 구동) */
  foreign?: number;
  inst?: number;
  individual?: number;
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

    // 오브 전체를 청록(hue) 톤으로. 한 색상의 명도/채도만 흔들어 오로라 느낌.
    const drawAuroraOrb = (cx: number, cy: number, R: number, now: number, hue: number, beat: number) => {
      const auroras = [
        { dh: -6, phase: 0, speed: 0.00032, ampl: 0.35 },
        { dh: 4, phase: 1.5, speed: 0.00044, ampl: 0.42 },
        { dh: 10, phase: 3.2, speed: 0.00024, ampl: 0.28 },
      ];
      auroras.forEach((a) => {
        const t = now * a.speed + a.phase;
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        for (let ring = 0; ring < 2; ring++) {
          const ringOff = ring * 6;
          const alpha = (0.2 - ring * 0.05) * (1 + beat * 0.3);
          ctx.strokeStyle = `hsla(${hue + a.dh + Math.sin(t) * 8}, 78%, 62%, ${alpha})`;
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
      // 외곽 글로우 (청록)
      const glowR = R * 3;
      const outer = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, glowR);
      outer.addColorStop(0, `hsla(${hue},72%,55%,${0.14 + beat * 0.08})`);
      outer.addColorStop(0.45, `hsla(${hue + 8},60%,48%,0.06)`);
      outer.addColorStop(1, `hsla(${hue},50%,45%,0)`);
      ctx.fillStyle = outer;
      ctx.beginPath();
      ctx.arc(cx, cy, glowR, 0, Math.PI * 2);
      ctx.fill();
      // 본체 (밝은 청록 → 깊은 청록)
      const body = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.35, 0, cx, cy, R);
      body.addColorStop(0, `hsla(${hue},70%,72%,0.7)`);
      body.addColorStop(0.5, `hsla(${hue},62%,45%,0.5)`);
      body.addColorStop(1, `hsla(${hue + 6},58%,20%,0.7)`);
      ctx.fillStyle = body;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fill();
      // 코어 하이라이트
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.5);
      core.addColorStop(0, `rgba(255,255,255,${0.85 + beat * 0.15})`);
      core.addColorStop(0.6, `hsla(${hue},90%,85%,0.4)`);
      core.addColorStop(1, `hsla(${hue},85%,70%,0)`);
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
      orbHue: number,
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
        // 노드 색: KR은 지배적 투자자의 색(수급 정보), US는 상승/하락 색
        let hue: number = orbHue;
        if (side === 'kr') {
          const f = s.foreign ?? 0,
            i2 = s.inst ?? 0,
            p2 = s.individual ?? 0;
          const m = Math.max(f, i2, p2);
          if (m > 0.05) hue = m === f ? INV_HUES.foreign : m === i2 ? INV_HUES.inst : INV_HUES.individual;
        } else {
          hue = s.ret >= 0 ? US_UP_HUE : US_DOWN_HUE;
        }
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
      drawAuroraOrb(cx, cy, orbR, now, orbHue, beat);
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
      const krPos = drawOrb(krCx, krCy, orbR, ringR, krS, 'kr', LIFE_HUE_KR, now, beat);
      const usPos = drawOrb(usCx, usCy, orbR, ringR, usS, 'us', LIFE_HUE_US, now, beat);

      // 파티클 스폰 — 스펙의 정보 인코딩:
      //   KR: 투자자별 3색 (외국인 금 45 / 기관 청록 175 / 개인 회청 220), 강도∝수급
      //   US: 상승 시안 195 / 하락 보라 240, 강도∝|등락률|
      if (now - lastSpawn > 460) {
        lastSpawn = now;
        const push = (
          s: { x: number; y: number; name: string },
          cx: number,
          cy: number,
          side: 'kr' | 'us',
          hue: number,
          strength: number,
        ) => {
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
            dur: 1700 + Math.random() * 600,
            key: s.name,
            side,
            hue,
            strength,
          });
        };
        // KR: 섹터×투자자 3색
        krPos.forEach((s) => {
          (
            [
              ['foreign', s.foreign ?? 0],
              ['inst', s.inst ?? 0],
              ['individual', s.individual ?? 0],
            ] as const
          ).forEach(([key, strength]) => {
            if (strength < 0.25) return;
            if (Math.random() < strength * strength * 0.85) {
              push(s, krCx, krCy, 'kr', INV_HUES[key], strength);
            }
          });
        });
        // US: 등락률
        const maxRet = Math.max(...usPos.map((s) => Math.abs(s.ret)), 0.1);
        usPos.forEach((s) => {
          const intensity = Math.abs(s.ret) / maxRet;
          if (intensity < 0.2) return;
          if (Math.random() < intensity * intensity * 0.85) {
            push(s, usCx, usCy, 'us', s.ret >= 0 ? US_UP_HUE : US_DOWN_HUE, intensity);
          }
        });
        if (particles.length > 140) particles.splice(0, particles.length - 140);
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
