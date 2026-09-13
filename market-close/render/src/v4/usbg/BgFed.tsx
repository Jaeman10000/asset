/**
 * BgFed — 밤 조명을 받은 신고전주의 중앙은행 건물 배경 (1080x1920). 미국 주간(일요일) 금리·물가 장면용.
 * 박공(삼각 지붕) · 이오니아식 기둥 8개(아래에서 비추는 금색 투광) · 문틈의 따뜻한 빛 · 넓은 계단 · 왼쪽 앞 성조기(어둡게)
 * + 기둥 앞에 떠 있는 수익률 곡선(3M·2Y·5Y·10Y·30Y) — 톤에 따라 오름(빨강)·내림(파랑)·평평(금색).
 * 특정 기관 이름·문장(紋章)은 넣지 않는다(일반적인 건물). 상단 55%는 옅은 구름과 달빛만(큰 글자 자리).
 * 프레임과 무관한 정적 그림 — public/bg/us_fed_<tone>.jpg 로 한 번 굽는다(BakeUSEntry.tsx).
 */
import React, { useId, useMemo } from "react";
import { AbsoluteFill } from "remotion";

export type Tone = "up" | "down" | "neutral";

const W = 1080;
const H = 1920;
const F = (n: number) => Math.round(n * 10) / 10;
const MONO = "Consolas, 'DejaVu Sans Mono', monospace";

function rng(seed: number) {
  let s = (Math.floor(seed) * 2654435761 + 1013904223) >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PAL: Record<Tone, { a: string; lt: string }> = {
  up: { a: "#FF4D4D", lt: "#FFC6BC" },
  down: { a: "#3D7BFF", lt: "#C6D8FF" },
  neutral: { a: "#F2C66D", lt: "#FFEBC4" },
};
const GOLD = "#FFC873";
const TEAL = "#38D3C8";

/** Catmull-Rom → 3차 베지어 */
function smooth(pts: [number, number][]) {
  let d = `M${F(pts[0][0])} ${F(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    d += `C${F(p1[0] + (p2[0] - p0[0]) / 6)} ${F(p1[1] + (p2[1] - p0[1]) / 6)} ${F(p2[0] - (p3[0] - p1[0]) / 6)} ${F(p2[1] - (p3[1] - p1[1]) / 6)} ${F(p2[0])} ${F(p2[1])}`;
  }
  return d;
}

// 건물 기준선
const COL_TOP = 1322;
const COL_BOT = 1668;
const STY = 1690; // 기단(계단 윗면)
const NCOL = 8;
const CX = Array.from({ length: NCOL }, (_, i) => 128 + (i * (952 - 128)) / (NCOL - 1));

function makeCurve(tone: Tone) {
  const xs = [128, 330, 520, 704, 952];
  const ys = tone === "up" ? [1566, 1498, 1452, 1418, 1386] : tone === "down" ? [1388, 1440, 1494, 1530, 1560] : [1478, 1462, 1466, 1472, 1468];
  const pts = xs.map((x, i) => [x, ys[i]] as [number, number]);
  const ext: [number, number][] = [[40, ys[0] + (ys[0] - ys[1]) * 0.35], ...pts, [1040, ys[4] + (ys[4] - ys[3]) * 0.4]];
  return { pts, line: smooth(ext), labels: ["3M", "2Y", "5Y", "10Y", "30Y"] };
}

function makeScene(seed: number) {
  const r = rng(seed);
  const stars = Array.from({ length: 46 }, () => ({ x: r() * W, y: 40 + r() * 900, rr: 0.6 + r() * 1.1, op: 0.08 + r() ** 2 * 0.3 }));
  const clouds = Array.from({ length: 7 }, (_, i) => ({ x: 80 + r() * 920, y: 820 + r() * 260, rx: 220 + r() * 260, ry: 26 + r() * 30, op: 0.5 + r() * 0.5, i }));
  // 기둥 세로 홈(플루팅)
  let flute = "";
  let fluteLt = "";
  for (const cx of CX) {
    for (let k = -3; k <= 3; k++) {
      const x0 = cx + k * 7.6;
      flute += `M${F(x0)} ${COL_TOP + 6}L${F(x0 + k * 0.5)} ${COL_BOT - 4}`;
      fluteLt += `M${F(x0 + 2.2)} ${COL_TOP + 6}L${F(x0 + 2.2 + k * 0.5)} ${COL_BOT - 4}`;
    }
  }
  // 이빨 장식(덴틸)
  let dent = "";
  for (let x = 58; x < 1022; x += 15) dent += `M${x} 1220h8v9h-8z`;
  // 계단
  const steps = Array.from({ length: 10 }, (_, k) => ({ y: STY + k * 23, x0: 58 - k * 22, x1: 1022 + k * 22 }));
  return { stars, clouds, flute, fluteLt, dent, steps };
}

export const BgFed: React.FC<{ tone?: Tone; dim?: number; seed?: number }> = ({ tone = "neutral", dim = 0, seed = 5 }) => {
  const pal = PAL[tone] ?? PAL.neutral;
  const uid = "ufd" + useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const id = (s: string) => `${uid}-${s}`;
  const u = (s: string) => `url(#${id(s)})`;
  const sc = useMemo(() => makeScene(seed), [seed]);
  const cv = useMemo(() => makeCurve(tone), [tone]);
  const colPath = CX.map((cx) => `M${F(cx - 33)} ${COL_BOT}L${F(cx - 28.5)} ${COL_TOP}H${F(cx + 28.5)}L${F(cx + 33)} ${COL_BOT}Z`).join("");
  const last = cv.pts[cv.pts.length - 1];

  // 깃발(왼쪽 앞): 물결 모양 테두리
  const fx0 = 44, fx1 = 206, fy0 = 1112, fh = 92;
  const wave = (x: number) => Math.sin(((x - fx0) / (fx1 - fx0)) * Math.PI * 1.6) * 7 + ((x - fx0) / (fx1 - fx0)) * 10;
  const topE: string[] = [];
  const botE: string[] = [];
  for (let x = fx0; x <= fx1; x += 6) {
    topE.push(`${F(x)} ${F(fy0 + wave(x))}`);
    botE.unshift(`${F(x)} ${F(fy0 + fh + wave(x) + ((x - fx0) / (fx1 - fx0)) * 6)}`);
  }
  const flag = `M${topE.join("L")}L${botE.join("L")}Z`;
  const yAt = (x: number, t: number) => fy0 + wave(x) + t * (fh + ((x - fx0) / (fx1 - fx0)) * 6);
  const band = (xa: number, xb: number, ta: number, tb: number) => {
    const xsB: number[] = [];
    for (let x = xa; x <= xb + 0.01; x += 6) xsB.push(Math.min(x, xb));
    return `M${xsB.map((x) => `${F(x)} ${F(yAt(x, ta))}`).join("L")}L${xsB.slice().reverse().map((x) => `${F(x)} ${F(yAt(x, tb))}`).join("L")}Z`;
  };
  const flagStripes = Array.from({ length: 13 }, (_, i) => band(fx0 - 2, fx1 + 2, i / 13 - (i === 0 ? 0.05 : 0), (i + 1) / 13 + (i === 12 ? 0.05 : 0)));
  const cantonW = (fx1 - fx0) * 0.42;
  const canton = band(fx0 - 2, fx0 + cantonW, -0.05, 7 / 13);
  const flagStars: [number, number][] = [];
  for (let rI = 0; rI < 5; rI++) for (let c = 0; c < 6; c++) {
    const x = fx0 + 6 + c * (cantonW / 6) + (rI % 2) * (cantonW / 12);
    if (x > fx0 + cantonW - 3) continue;
    flagStars.push([F(x), F(yAt(x, (rI + 0.6) / 5 * (7 / 13)))]);
  }

  return (
    <AbsoluteFill style={{ background: "#01030A", overflow: "hidden" }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id={id("sky")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#01020A" />
            <stop offset="0.35" stopColor="#030817" />
            <stop offset="0.52" stopColor="#071329" />
            <stop offset="0.62" stopColor="#0C1D3C" />
            <stop offset="0.72" stopColor="#0A1630" />
            <stop offset="1" stopColor="#03060F" />
          </linearGradient>
          <radialGradient id={id("moon")}>
            <stop offset="0" stopColor="#A9C2F0" stopOpacity="0.1" />
            <stop offset="1" stopColor="#A9C2F0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("cloud")}>
            <stop offset="0" stopColor="#6F8CC0" stopOpacity="0.09" />
            <stop offset="1" stopColor="#6F8CC0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("warmBack")}>
            <stop offset="0" stopColor="#E9A04E" stopOpacity="0.26" />
            <stop offset="1" stopColor="#E9A04E" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("toneBack")}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.2" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("stone")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#2A3346" />
            <stop offset="1" stopColor="#161D2C" />
          </linearGradient>
          <linearGradient id={id("pedi")} gradientUnits="userSpaceOnUse" x1="0" y1="1086" x2="0" y2="1204">
            <stop offset="0" stopColor="#1A2233" />
            <stop offset="1" stopColor="#2C3548" />
          </linearGradient>
          <radialGradient id={id("pediLit")} gradientUnits="userSpaceOnUse" cx={540} cy={1210} r={420}>
            <stop offset="0" stopColor="#FFC873" stopOpacity="0.22" />
            <stop offset="1" stopColor="#FFC873" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("tymp")} gradientUnits="userSpaceOnUse" x1="0" y1="1100" x2="0" y2="1198">
            <stop offset="0" stopColor="#0C1220" />
            <stop offset="1" stopColor="#1B2233" />
          </linearGradient>
          <linearGradient id={id("frieze")} gradientUnits="userSpaceOnUse" x1="0" y1="1204" x2="0" y2="1300">
            <stop offset="0" stopColor="#3A3C44" />
            <stop offset="0.5" stopColor="#2A2F3C" />
            <stop offset="1" stopColor="#4A4236" />
          </linearGradient>
          <linearGradient id={id("col")} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#0E1320" />
            <stop offset="0.3" stopColor="#2B3446" />
            <stop offset="0.58" stopColor="#465166" />
            <stop offset="0.86" stopColor="#222A3A" />
            <stop offset="1" stopColor="#0B0F19" />
          </linearGradient>
          <radialGradient id={id("uplight")}>
            <stop offset="0" stopColor="#FFE0A8" stopOpacity="0.95" />
            <stop offset="0.3" stopColor="#F5BA66" stopOpacity="0.62" />
            <stop offset="0.7" stopColor="#D98E3E" stopOpacity="0.16" />
            <stop offset="1" stopColor="#D98E3E" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("door")} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#FFD28E" stopOpacity="0.95" />
            <stop offset="0.6" stopColor="#F0A955" stopOpacity="0.7" />
            <stop offset="1" stopColor="#C97C35" stopOpacity="0.45" />
          </linearGradient>
          <linearGradient id={id("riser")} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={W} y2="0">
            <stop offset="0" stopColor="#07090F" />
            <stop offset="0.5" stopColor="#1A1712" />
            <stop offset="1" stopColor="#07090F" />
          </linearGradient>
          <radialGradient id={id("spill")}>
            <stop offset="0" stopColor="#FFC873" stopOpacity="0.4" />
            <stop offset="1" stopColor="#FFC873" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("fixture")}>
            <stop offset="0" stopColor="#FFF0CC" stopOpacity="1" />
            <stop offset="0.3" stopColor="#FFC873" stopOpacity="0.5" />
            <stop offset="1" stopColor="#FFC873" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("tread")} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={W} y2="0">
            <stop offset="0" stopColor="#1A1E28" />
            <stop offset="0.3" stopColor="#3A3934" />
            <stop offset="0.5" stopColor="#5A4E3C" />
            <stop offset="0.7" stopColor="#3A3934" />
            <stop offset="1" stopColor="#1A1E28" />
          </linearGradient>
          <linearGradient id={id("flagShade")} gradientUnits="userSpaceOnUse" x1={fx0} y1="0" x2={fx1} y2="0">
            {Array.from({ length: 7 }, (_, i) => (
              <stop key={i} offset={i / 6} stopColor={i % 2 ? "#000" : "#FFF"} stopOpacity={i % 2 ? 0.35 : 0.06} />
            ))}
          </linearGradient>
          <linearGradient id={id("flagLit")} gradientUnits="userSpaceOnUse" x1="0" y1={fy0 + fh + 10} x2="0" y2={fy0}>
            <stop offset="0" stopColor="#FFC873" stopOpacity="0.22" />
            <stop offset="1" stopColor="#FFC873" stopOpacity="0" />
          </linearGradient>
          <clipPath id={id("colC")}>
            <path d={colPath} />
          </clipPath>
          <clipPath id={id("flagC")}>
            <path d={flag} />
          </clipPath>
          <radialGradient id={id("halo")}>
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.95" />
            <stop offset="0.22" stopColor={pal.a} stopOpacity="0.55" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("curveF")} gradientUnits="userSpaceOnUse" x1="0" y1="1380" x2="0" y2="1640">
            <stop offset="0" stopColor={pal.a} stopOpacity="0.22" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </linearGradient>
          <filter id={id("blurL")} filterUnits="userSpaceOnUse" x={-40} y={1300} width={W + 80} height={380}>
            <feGaussianBlur stdDeviation="9" />
          </filter>
          <filter id={id("blurW")} filterUnits="userSpaceOnUse" x={0} y={1050} width={W} height={900}>
            <feGaussianBlur stdDeviation="14" />
          </filter>
        </defs>

        {/* 하늘 · 달빛 · 구름 · 별 */}
        <rect x={-20} y={-20} width={W + 40} height={H + 40} fill={u("sky")} />
        <circle cx={880} cy={360} r={560} fill={u("moon")} />
        {sc.stars.map((s, i) => <circle key={i} cx={F(s.x)} cy={F(s.y)} r={s.rr} fill="#E8F0FF" opacity={s.op} />)}
        {sc.clouds.map((c) => <ellipse key={c.i} cx={F(c.x)} cy={F(c.y)} rx={F(c.rx)} ry={F(c.ry)} fill={u("cloud")} opacity={c.op} />)}
        <ellipse cx={540} cy={1230} rx={760} ry={300} fill={u("warmBack")} />
        <ellipse cx={540} cy={1120} rx={640} ry={200} fill={u("toneBack")} />

        {/* 박공 */}
        <path d="M40 1206L540 1082L1040 1206Z" fill={u("pedi")} />
        <path d="M96 1198L540 1100L984 1198Z" fill={u("tymp")} />
        <path d="M96 1198L540 1100L984 1198Z" fill={u("pediLit")} />
        <path d="M40 1206L540 1082L1040 1206" fill="none" stroke={GOLD} strokeOpacity={0.4} strokeWidth={2} />
        <path d="M96 1198L540 1100L984 1198" fill="none" stroke="#E8D2AC" strokeOpacity={0.14} strokeWidth={1.4} />
        {/* 박공 가운데 둥근 장식(일반 문양) */}
        <circle cx={540} cy={1160} r={30} fill="none" stroke={GOLD} strokeOpacity={0.3} strokeWidth={2} />
        <circle cx={540} cy={1160} r={20} fill="none" stroke={GOLD} strokeOpacity={0.18} strokeWidth={1.4} />
        <path d={Array.from({ length: 16 }, (_, i) => { const a = (i / 16) * Math.PI * 2; return `M${F(540 + Math.cos(a) * 32)} ${F(1160 + Math.sin(a) * 32)}L${F(540 + Math.cos(a) * 42)} ${F(1160 + Math.sin(a) * 42)}`; }).join("")} stroke={GOLD} strokeOpacity={0.16} strokeWidth={1.4} />
        <path d="M300 1182C380 1176 440 1172 500 1170M780 1182C700 1176 640 1172 580 1170" stroke="#E8D2AC" strokeOpacity={0.1} strokeWidth={3} fill="none" />

        {/* 엔태블러처: 코니스 · 덴틸 · 프리즈 · 아키트레이브 */}
        <rect x={36} y={1204} width={1008} height={14} fill="#3A3F4C" />
        <path d="M36 1204H1044" stroke="#FFE2B0" strokeOpacity={0.45} strokeWidth={1.4} />
        <path d={sc.dent} fill="#2A303D" />
        <rect x={60} y={1229} width={960} height={42} fill={u("frieze")} />
        {CX.map((cx, i) => <circle key={i} cx={F(cx)} cy={1250} r={7} fill="none" stroke={GOLD} strokeOpacity={0.22} strokeWidth={1.4} />)}
        <rect x={70} y={1271} width={940} height={30} fill="#322F2E" />
        <path d="M70 1281H1010M70 1291H1010" stroke="#000" strokeOpacity={0.3} strokeWidth={1.2} />
        <path d="M70 1301H1010" stroke="#FFD08A" strokeOpacity={0.35} strokeWidth={1.2} />

        {/* 주랑 안쪽 벽 · 문 빛 */}
        <rect x={80} y={1301} width={920} height={STY - 1301} fill="#060A13" />
        {[305, 775].map((x) => (
          <g key={x}>
            <rect x={x - 30} y={1528} width={60} height={STY - 1528} fill={u("door")} opacity={0.62} />
            <path d={`M${x - 30} ${STY}V1528H${x + 30}V${STY}`} fill="none" stroke={GOLD} strokeOpacity={0.4} strokeWidth={2} />
            <rect x={x - 22} y={1380} width={44} height={70} fill={u("door")} opacity={0.2} />
          </g>
        ))}
        <rect x={492} y={1486} width={96} height={STY - 1486} fill={u("door")} />
        <path d="M540 1486V1690" stroke="#8A5A26" strokeOpacity={0.5} strokeWidth={2} />
        <rect x={492} y={1438} width={96} height={40} fill={u("door")} opacity={0.6} />
        <path d="M516 1438V1478M540 1438V1478M564 1438V1478" stroke="#3A2610" strokeOpacity={0.6} strokeWidth={2} />
        <path d="M484 1690V1430H596V1690" fill="none" stroke={GOLD} strokeOpacity={0.5} strokeWidth={3} />
        <ellipse cx={540} cy={1596} rx={170} ry={130} fill={u("spill")} filter={u("blurW")} />

        {/* 기둥 */}
        <path d={colPath} fill={u("col")} />
        <g clipPath={u("colC")}>
          {CX.map((cx, i) => <ellipse key={i} cx={F(cx + 4)} cy={COL_BOT + 6} rx={40} ry={400} fill={u("uplight")} />)}
          <path d={sc.flute} stroke="#000" strokeOpacity={0.28} strokeWidth={1.6} />
          <path d={sc.fluteLt} stroke="#FFE3B8" strokeOpacity={0.1} strokeWidth={1.2} />
        </g>
        {CX.map((cx, i) => (
          <g key={i}>
            {/* 주두(이오니아) */}
            <rect x={F(cx - 43)} y={1301} width={86} height={9} fill="#4A4A50" />
            <rect x={F(cx - 36)} y={1310} width={72} height={13} rx={4} fill="#3A3E4A" />
            <circle cx={F(cx - 36)} cy={1318} r={8.5} fill="#3A3E4A" stroke="#FFD9A0" strokeOpacity={0.3} strokeWidth={1.4} />
            <circle cx={F(cx + 36)} cy={1318} r={8.5} fill="#3A3E4A" stroke="#FFD9A0" strokeOpacity={0.3} strokeWidth={1.4} />
            <circle cx={F(cx - 36)} cy={1318} r={3.4} fill="none" stroke="#FFD9A0" strokeOpacity={0.3} strokeWidth={1.2} />
            <circle cx={F(cx + 36)} cy={1318} r={3.4} fill="none" stroke="#FFD9A0" strokeOpacity={0.3} strokeWidth={1.2} />
            {/* 주초 */}
            <rect x={F(cx - 38)} y={COL_BOT} width={76} height={12} rx={6} fill="#5A5044" />
            <rect x={F(cx - 43)} y={COL_BOT + 12} width={86} height={10} fill="#6A5B48" />
            {/* 투광기 */}
            <circle cx={F(cx)} cy={STY + 4} r={26} fill={u("fixture")} />
            <path d={`M${F(cx - 33)} ${COL_BOT}L${F(cx - 28.5)} ${COL_TOP}`} stroke={TEAL} strokeOpacity={0.18} strokeWidth={1.4} />
          </g>
        ))}

        {/* 계단 */}
        {sc.steps.map((s, k) => (
          <g key={k}>
            <rect x={s.x0} y={s.y} width={s.x1 - s.x0} height={9} fill={u("tread")} opacity={1 - k * 0.06} />
            <path d={`M${s.x0} ${s.y}H${s.x1}`} stroke="#FFE0B0" strokeOpacity={0.42 - k * 0.03} strokeWidth={1.4} />
            <rect x={s.x0} y={s.y + 9} width={s.x1 - s.x0} height={14} fill={u("riser")} />
          </g>
        ))}
        <ellipse cx={540} cy={1712} rx={300} ry={46} fill={u("spill")} />

        {/* 수익률 곡선(기둥 앞에 떠 있는 선) */}
        <g>
          <path d={[1392, 1452, 1512, 1572].map((y) => `M92 ${y}H988`).join("")} stroke={TEAL} strokeOpacity={0.14} strokeWidth={1.2} strokeDasharray="3 9" />
          <path d={`${cv.line}L1040 1640L40 1640Z`} fill={u("curveF")} />
          <path d={cv.line} fill="none" stroke={pal.a} strokeOpacity={0.08} strokeWidth={36} strokeLinecap="round" />
          <path d={cv.line} fill="none" stroke={pal.a} strokeOpacity={0.75} strokeWidth={12} strokeLinecap="round" filter={u("blurL")} />
          <path d={cv.line} fill="none" stroke={pal.a} strokeWidth={4.6} strokeLinecap="round" />
          <path d={cv.line} fill="none" stroke={pal.lt} strokeOpacity={0.9} strokeWidth={1.6} strokeLinecap="round" />
          {cv.pts.map(([x, y], i) => (
            <g key={i}>
              <path d={`M${x} ${F(y + 14)}V1606`} stroke={pal.lt} strokeOpacity={0.22} strokeWidth={1.2} strokeDasharray="2 6" />
              <circle cx={x} cy={F(y)} r={9} fill="#0A0E18" stroke={pal.a} strokeWidth={3} />
              <text x={x} y={1634} textAnchor="middle" fontFamily={MONO} fontSize={21} fontWeight={700} fill={pal.lt} opacity={0.55}>{cv.labels[i]}</text>
            </g>
          ))}
          <circle cx={last[0]} cy={F(last[1])} r={46} fill={u("halo")} />
          <circle cx={last[0]} cy={F(last[1])} r={6} fill="#FFFFFF" />
        </g>

        {/* 성조기(왼쪽 앞, 어둡게) */}
        <rect x={38} y={1098} width={5} height={H - 1098} fill="#1A1F2B" />
        <path d={`M43 1098V${H}`} stroke={GOLD} strokeOpacity={0.35} strokeWidth={1} />
        <circle cx={40.5} cy={1094} r={6} fill="#C9A45E" />
        <g clipPath={u("flagC")} opacity={0.72}>
          {flagStripes.map((d, i) => <path key={i} d={d} fill={i % 2 ? "#B4AEA4" : "#8E2A30"} />)}
          <path d={canton} fill="#1D2A58" />
          {flagStars.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={1.6} fill="#EDEAE2" opacity={0.85} />)}
          <rect x={fx0} y={fy0 - 20} width={fx1 - fx0} height={fh + 40} fill={u("flagShade")} />
          <rect x={fx0} y={fy0 - 20} width={fx1 - fx0} height={fh + 40} fill={u("flagLit")} />
        </g>
      </svg>

      {/* 비네트 · 상단 암부 · 감광 */}
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <radialGradient id={id("vig")} gradientUnits="userSpaceOnUse" cx={540} cy={1360} r={1180}>
            <stop offset="0" stopColor="#000" stopOpacity="0" />
            <stop offset="0.55" stopColor="#000" stopOpacity="0" />
            <stop offset="0.82" stopColor="#000" stopOpacity="0.45" />
            <stop offset="1" stopColor="#000" stopOpacity="0.85" />
          </radialGradient>
          <linearGradient id={id("top")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" stopOpacity="0.5" />
            <stop offset="0.4" stopColor="#000" stopOpacity="0.12" />
            <stop offset="0.54" stopColor="#000" stopOpacity="0" />
            <stop offset="0.9" stopColor="#000" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.5" />
          </linearGradient>
        </defs>
        <rect width={W} height={H} fill={u("vig")} />
        <rect width={W} height={H} fill={u("top")} />
        {dim > 0 && <rect width={W} height={H} fill="#000" opacity={Math.min(1, dim)} />}
      </svg>
    </AbsoluteFill>
  );
};

export default BgFed;
