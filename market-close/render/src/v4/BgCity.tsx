import React, { useId, useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * BgCity — 야간 금융가 스카이라인 배경 (1080x1920).
 * 원경(푸른 안개 빌딩) · 중경(창문 불빛) · 근경(유리 타워, 가장자리 실루엣) + 톤 색 차트 라인 + 안개·보케·비네트.
 * 상단 55%(큰 글자 자리)는 어둡고 조용하게, 밝은 요소는 하단 45%와 가장자리에 둔다.
 * 기하는 seed로 한 번만 만들고(useMemo), 프레임마다 transform/opacity(+차트 빛 훑기 dashoffset)만 바꾼다.
 * 비용: SVG 요소 약 230개, 블러 필터 1개(차트 번짐, 선 주변 영역만). 창문 수천 개는 색·밝기별 path 몇 개로 합침.
 * 실측(동시성 1, 60프레임 중앙값): 글자·카드만 67ms → BgCity 포함 ~84ms/프레임.
 */

export type Tone = "up" | "down" | "neutral";

type Pal = { a: string; lt: string; haze: string };
const PAL: Record<Tone, Pal> = {
  up: { a: "#FF4D4D", lt: "#FFC4BA", haze: "#E0344E" },
  down: { a: "#3D7BFF", lt: "#C2D6FF", haze: "#2F68F2" },
  neutral: { a: "#7FB2FF", lt: "#E0ECFF", haze: "#4E88DA" },
};

const W = 1080;
const H = 1920;
const TAU = Math.PI * 2;
const F = (n: number) => Math.round(n * 10) / 10;
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

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

type Rnd = () => number;
type Bld = { x: number; w: number; top: number; kind: number; flip?: boolean };
type Shape = { body: string; roof: string; peak: [number, number]; face: number };

function shapeOf(b: Bld, bottom: number): Shape {
  const { x, w, top } = b;
  const X = x + w;
  const cx = x + w / 2;
  const B = F(bottom);
  switch (b.kind) {
    case 1: {
      const i = w * 0.2;
      const s = 12 + w * 0.28;
      const roof = `M${F(x)} ${F(top + s)}H${F(x + i)}V${F(top)}H${F(X - i)}V${F(top + s)}H${F(X)}`;
      return { body: `M${F(x)} ${B}V${F(top + s)}H${F(x + i)}V${F(top)}H${F(X - i)}V${F(top + s)}H${F(X)}V${B}Z`, roof, peak: [cx, top], face: top + s };
    }
    case 2: {
      const s = w * 0.42;
      const yl = b.flip ? top : top + s;
      const yr = b.flip ? top + s : top;
      return { body: `M${F(x)} ${B}V${F(yl)}L${F(X)} ${F(yr)}V${B}Z`, roof: `M${F(x)} ${F(yl)}L${F(X)} ${F(yr)}`, peak: [b.flip ? x + 3 : X - 3, top], face: top + s };
    }
    case 3: {
      const h = 34 + w * 0.7;
      return {
        body: `M${F(x)} ${B}V${F(top)}H${F(X)}V${B}ZM${F(cx - 1.6)} ${F(top + 1)}V${F(top - h)}H${F(cx + 1.6)}V${F(top + 1)}Z`,
        roof: `M${F(x)} ${F(top)}H${F(X)}`,
        peak: [cx, top - h],
        face: top,
      };
    }
    case 4: {
      const s = w * 0.38;
      return { body: `M${F(x)} ${B}V${F(top + s)}L${F(cx)} ${F(top)}L${F(X)} ${F(top + s)}V${B}Z`, roof: `M${F(x)} ${F(top + s)}L${F(cx)} ${F(top)}L${F(X)} ${F(top + s)}`, peak: [cx, top], face: top + s };
    }
    default:
      return { body: `M${F(x)} ${B}V${F(top)}H${F(X)}V${B}Z`, roof: `M${F(x)} ${F(top)}H${F(X)}`, peak: [cx, top], face: top };
  }
}

type RowCfg = { x0: number; x1: number; wMin: number; wMax: number; base: number; jit: number; bump: number; bumpW: number; tower: number; tMin: number; tMax: number; leftCalm: number };

function row(r: Rnd, c: RowCfg, cluster: number): Bld[] {
  const out: Bld[] = [];
  let x = c.x0;
  while (x < c.x1) {
    const w = lerp(c.wMin, c.wMax, r());
    const mid = x + w / 2;
    let top = c.base + (r() - 0.5) * c.jit - c.bump * Math.exp(-(((mid - cluster) / c.bumpW) ** 2));
    if (r() < c.tower) top -= lerp(c.tMin, c.tMax, r());
    if (mid < 460) top += c.leftCalm * (1 - mid / 460);
    const k = r();
    const kind = k < 0.48 ? 0 : k < 0.66 ? 1 : k < 0.8 ? 2 : k < 0.91 ? 3 : 4;
    out.push({ x, w, top, kind, flip: r() < 0.5 });
    // 겹치거나(0.72) 붙이거나, 가끔만 뚜렷한 틈(12~26px) — 겹침+틈이 섞여 생기는 가는 빛줄기 방지
    x += r() < 0.3 ? w * 0.72 : w + (r() < 0.1 ? 12 + r() * 14 : 0);
  }
  return out;
}

type WinCfg = { fh: number; cw: number; ww: number; wh: number; pRun: number; runMax: number; pIdle: number; yMax: number; hush?: (x: number, y: number) => number };
type Win = [number, number, number, number];

/** 창문: 층 단위로 켜진 '줄'(사무실 한 층) + 드문 낱개. 색·밝기 버킷별로 한 path에 모은다. */
function addWindows(r: Rnd, b: Bld, face: number, c: WinCfg, buckets: string[], list: Win[], budget: { n: number }) {
  const margin = 5;
  const cols = Math.floor((b.w - margin * 2) / c.cw);
  if (cols < 1) return;
  const x0 = b.x + (b.w - cols * c.cw) / 2 + (c.cw - c.ww) / 2;
  const bWarm = r() < 0.72;
  for (let y = face + margin + 3; y + c.wh < c.yMax; y += c.fh) {
    const hush = c.hush ? c.hush(b.x + b.w / 2, y) : 1;
    const run = r() < c.pRun * hush;
    const len = 1 + Math.floor(r() * Math.min(cols, c.runMax));
    const start = Math.floor(r() * (cols - len + 1));
    const warm = r() < 0.85 ? bWarm : !bWarm;
    const lvRun = r() < 0.6 ? 0 : r() < 0.75 ? 1 : 2;
    for (let i = 0; i < cols; i++) {
      const inRun = run && i >= start && i < start + len;
      if (!inRun && r() >= c.pIdle * hush) continue;
      if (inRun && r() < 0.12) continue; // 줄 속 꺼진 창
      if (budget.n <= 0) return;
      budget.n--;
      const x = x0 + i * c.cw;
      const l = inRun ? lvRun : r() < 0.7 ? 0 : 1;
      buckets[(warm ? 0 : 3) + l] += `M${F(x)} ${F(y)}h${c.ww}v${c.wh}h${-c.ww}z`;
      list.push([x, y, c.ww, c.wh]);
    }
  }
}

function makeCity(seed: number) {
  const r = rng(seed);
  const cluster = 700 + (r() - 0.5) * 140;

  // 원경: 푸르게 흐린 빌딩 숲
  const far = row(r, { x0: -150, x1: W + 150, wMin: 20, wMax: 58, base: 1045, jit: 120, bump: 170, bumpW: 230, tower: 0.16, tMin: 60, tMax: 160, leftCalm: 60 }, cluster);
  const farShapes = far.map((b) => shapeOf(b, 1600));
  // 원경 창문: 아주 작은 점 격자(먼 도시의 반짝임), 밝기 2단
  const farWin = ["", ""];
  let farBudget = 1100;
  far.forEach((b, i) => {
    const face = farShapes[i].face;
    const cols = Math.max(1, Math.floor((b.w - 6) / 6));
    const dens = 0.05 + r() * 0.16;
    for (let y = face + 6; y < 1450; y += 7) {
      const rowLit = r() < 0.25;
      for (let c = 0; c < cols; c++) {
        const x = b.x + 4 + c * 6;
        const p = (rowLit ? dens * 2.4 : dens * 0.5) * (x < 600 && y < 1090 ? 0.2 : 1);
        if (r() >= p || farBudget <= 0) continue;
        farBudget--;
        farWin[r() < 0.75 ? 0 : 1] += `M${F(x)} ${F(y)}h2.2v2.4h-2.2z`;
      }
    }
  });

  // 중경: 어두운 빌딩 + 창문
  const mid = row(r, { x0: -130, x1: W + 130, wMin: 46, wMax: 118, base: 1175, jit: 120, bump: 230, bumpW: 190, tower: 0.13, tMin: 60, tMax: 150, leftCalm: 70 }, cluster + 60);
  const midShapes = mid.map((b) => shapeOf(b, 1760));
  const midWin = ["", "", "", "", "", ""];
  const midList: Win[] = [];
  const midBudget = { n: 1000 };
  const topLeftHush = (x: number, y: number) => (x < 620 && y < 1100 ? 0.3 : 1);
  mid.forEach((b, i) =>
    addWindows(r, b, midShapes[i].face, { fh: 13, cw: 9, ww: 5, wh: 6, pRun: 0.4, runMax: 8, pIdle: 0.04, yMax: 1600, hush: topLeftHush }, midWin, midList, midBudget),
  );
  const beacons = midShapes
    .map((s) => s.peak)
    .filter((p) => p[0] > 380 && p[0] < 1040)
    .sort((a, b) => a[1] - b[1])
    .slice(0, 3);

  // 근경: 가장자리 실루엣 + 낮은 중앙 건물
  const j = (a: number) => (r() - 0.5) * a;
  // 앞 건물에 조금씩 겹쳐 이어 붙인다(틈으로 뒤 안개가 가는 선처럼 새지 않게)
  const spec: [w: number, top: number, kind: number, ov: number, flip?: boolean][] = [
    [270 + j(24), 950 + j(40), 1, 0],
    [150, 1340 + j(40), 0, 12],
    [118, 1540 + j(30), 0, 10],
    [150, 1600 + j(20), 2, 8, true],
    [128, 1575 + j(30), 0, 6],
    [125, 1490 + j(30), 1, 8],
    [124, 1250 + j(40), 4, 10],
  ];
  const near: Bld[] = [];
  let nx = -110;
  for (const [w, top, kind, ov, flip] of spec) {
    nx -= ov;
    near.push({ x: nx, w, top, kind, flip });
    nx += w;
  }
  const nearShapes = near.map((b) => shapeOf(b, 1960));
  const nearWin = ["", "", "", "", "", ""];
  const nearList: Win[] = [];
  const nearBudget = { n: 260 };
  const nearHush = (x: number, y: number) => (Math.abs(x - 540) < 240 && y > 1560 ? 0.25 : 1) * topLeftHush(x, y);
  near.forEach((b, i) =>
    addWindows(r, b, nearShapes[i].face, { fh: 21, cw: 14, ww: 7, wh: 9, pRun: 0.22, runMax: 5, pIdle: 0.01, yMax: 1900, hush: nearHush }, nearWin, nearList, nearBudget),
  );

  // 유리 타워(오른쪽 가장자리)
  const gx = 872 + j(16);
  const gTopL = 800 + j(30);
  const gTopR = gTopL - 80;
  const glass = `M${F(gx)} 1960V${F(gTopL)}L${W + 90} ${F(gTopR - 20)}V1960Z`;
  let floors = "";
  for (let y = gTopL + 14; y < 1960; y += 18) floors += `M${F(gx)} ${F(y)}H${W + 90}`;
  let mullions = "";
  for (let x = gx + 34; x < W + 90; x += 34) mullions += `M${F(x)} ${F(gTopR - 20)}V1960`;
  // 반짝이는 창문 몇 개
  const pick = (list: Win[], n: number) => Array.from({ length: Math.min(n, list.length) }, () => ({ w: list[Math.floor(r() * list.length)], ph: r() * TAU, per: 3 + r() * 5 }));
  const twMid = pick(midList, 6);
  const twNear = pick(nearList, 5);

  // 보케(초점 밖 불빛)
  // 큰 원 몇 개는 톤 색으로 아주 옅게, 나머지는 작고 밝게(탁한 얼룩 대신 빛처럼 보이게)
  const bokeh = Array.from({ length: 18 }, (_, i) => {
    let x: number;
    let y: number;
    if (i < 12) {
      x = r() * W;
      y = lerp(1250, 1880, r());
    } else if (i < 15) {
      x = lerp(900, 1080, r());
      y = lerp(820, 1260, r());
    } else {
      x = lerp(0, 160, r());
      y = lerp(1160, 1600, r());
    }
    const big = i % 5 === 0;
    const c = r();
    const kind = big ? 0 : c < 0.5 ? 3 : c < 0.8 ? 1 : 2;
    const rad = big ? lerp(44, 74, r()) : lerp(5, 17, r() ** 1.3);
    const op = big ? lerp(0.1, 0.16, r()) : lerp(0.6, 0.32, (rad - 5) / 12);
    return { x, y, rad, kind, op, ph: r() * TAU, per: lerp(7, 13, r()) };
  });

  const rim = (arr: Shape[]) => arr.map((s) => s.roof).join("");
  // 옆면(오른쪽 1/3)을 한 톤 어둡게 — 평면 판자처럼 보이지 않게
  const side = (arr: Bld[], sh: Shape[], bottom: number) =>
    arr.map((b, i) => `M${F(b.x + b.w * 0.64)} ${bottom}V${F(sh[i].face)}H${F(b.x + b.w)}V${bottom}Z`).join("");
  return {
    far: farShapes.map((s) => s.body).join(""),
    farWin,
    mid: midShapes.map((s) => s.body).join(""),
    midSide: side(mid, midShapes, 1760),
    midRim: rim(midShapes),
    midWin,
    beacons,
    near: nearShapes.map((s) => s.body).join(""),
    nearSide: side(near, nearShapes, 1960),
    nearRim: rim(nearShapes),
    // 왼쪽 타워 오른쪽 모서리 빛 — 앞 건물(near[1])에 가려지는 지점까지만
    leftEdge: `M${F(near[0].x + near[0].w - 0.5)} ${F(nearShapes[0].face)}V${F(near[1].top)}`,
    nearWin,
    glass,
    gx,
    gTopL,
    gTopR,
    floors,
    mullions,
    twMid,
    twNear,
    bokeh,
  };
}

function makeChart(seed: number, tone: Tone) {
  const r = rng(seed * 31 + (tone === "up" ? 101 : tone === "down" ? 202 : 303));
  const N = 15;
  const x0 = -70;
  const x1 = 938;
  const [ya, yb] = tone === "up" ? [1470, 1120] : tone === "down" ? [1105, 1440] : [1330, 1232];
  const pts: [number, number][] = [];
  let dir = r() < 0.5 ? 1 : -1;
  for (let i = 0; i < N; i++) {
    const k = i / (N - 1);
    const base = lerp(ya, yb, 0.35 * k + 0.65 * k * k * (3 - 2 * k));
    const edge = i === 0 || i === N - 1;
    const x = lerp(x0, x1, k) + (edge ? 0 : (r() - 0.5) * 34);
    dir = r() < 0.8 ? -dir : dir;
    const amp = edge ? 0 : 14 + r() * 42;
    pts.push([x, base + dir * amp]);
  }
  // 마지막 두 구간: 추세를 한 번 더 강조(되돌림 후 급변)
  const s = Math.sign(yb - ya);
  const m = tone === "neutral" ? 0.45 : 1;
  pts[N - 3][1] = yb - s * 46 * m;
  pts[N - 2][1] = yb - s * 118 * m;
  pts[N - 1][1] = yb;
  const line = "M" + pts.map((p) => `${F(p[0])} ${F(p[1])}`).join("L");
  const fill = `${line}L${x1} 1900L${x0} 1900Z`;
  let len = 0;
  for (let i = 1; i < N; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  const minY = Math.min(...pts.map((p) => p[1]));
  const maxY = Math.max(...pts.map((p) => p[1]));
  // 블러 필터 영역을 선 주변으로만 한정(렌더 비용)
  const box: [number, number, number, number] = [x0 - 50, minY - 50, x1 - x0 + 100, maxY - minY + 100];
  return { line, fill, len, end: pts[N - 1], minY, box };
}

export const BgCity: React.FC<{ tone?: Tone; seed?: number; dim?: number }> = ({ tone = "neutral", seed = 7, dim = 0.15 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pal = PAL[tone] ?? PAL.neutral;
  const uid = "bgc" + useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const city = useMemo(() => makeCity(seed), [seed]);
  const chart = useMemo(() => makeChart(seed, tone), [seed, tone]);
  const id = (s: string) => `${uid}-${s}`;
  const u = (s: string) => `url(#${id(s)})`;

  // ── 움직임: 느린 줌 호흡 + 층별 시차 + 빛 맥동 (transform/opacity만)
  const t = frame / (fps || 30);
  const s1 = Math.sin((TAU * t) / 17);
  const s2 = Math.sin((TAU * t) / 11 + 1.3);
  const zoom = 1.035 + 0.02 * Math.sin((TAU * t) / 21 - Math.PI / 2);
  const tr = (dx: number, dy: number) => `translate(${F(dx)} ${F(dy)})`;
  const pulse = 0.5 + 0.5 * Math.sin((TAU * t) / 6.5);
  const pingK = (t % 2.4) / 2.4;
  const sweepP = Math.min(1, (frame % 210) / 150);
  const sweepOp = Math.sin(sweepP * Math.PI) * 0.85;
  const dash = 170;
  const [ex, ey] = chart.end;
  const chartBox = chart.box;
  const winOp = [0.3, 0.55, 0.85];

  const warm = "#FFC47F";
  const cool = "#A8C8FF";

  return (
    <AbsoluteFill style={{ background: "#020308", overflow: "hidden" }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id={id("sky")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#010207" />
            <stop offset="0.22" stopColor="#030610" />
            <stop offset="0.4" stopColor="#050B1A" />
            <stop offset="0.52" stopColor="#081124" />
            <stop offset="0.58" stopColor="#0A1532" />
            <stop offset="0.645" stopColor="#0F1E45" />
            <stop offset="0.72" stopColor="#0A1533" />
            <stop offset="0.85" stopColor="#050A18" />
            <stop offset="1" stopColor="#020409" />
          </linearGradient>
          <radialGradient id={id("glowT")}>
            <stop offset="0" stopColor={pal.haze} stopOpacity="0.55" />
            <stop offset="0.4" stopColor={pal.haze} stopOpacity="0.2" />
            <stop offset="1" stopColor={pal.haze} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("glowC")}>
            <stop offset="0" stopColor="#3A6FD0" stopOpacity="0.34" />
            <stop offset="1" stopColor="#3A6FD0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("glowW")}>
            <stop offset="0" stopColor="#FF9C52" stopOpacity="0.16" />
            <stop offset="1" stopColor="#FF9C52" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("farF")} gradientUnits="userSpaceOnUse" x1="0" y1="860" x2="0" y2="1600">
            <stop offset="0" stopColor="#0E1A35" />
            <stop offset="0.55" stopColor="#13244A" />
            <stop offset="1" stopColor="#1D335F" />
          </linearGradient>
          <linearGradient id={id("midF")} gradientUnits="userSpaceOnUse" x1="0" y1="950" x2="0" y2="1760">
            <stop offset="0" stopColor="#050A15" />
            <stop offset="0.6" stopColor="#081021" />
            <stop offset="1" stopColor="#0D1830" />
          </linearGradient>
          <linearGradient id={id("nearF")} gradientUnits="userSpaceOnUse" x1="0" y1="900" x2="0" y2="1960">
            <stop offset="0" stopColor="#03060D" />
            <stop offset="1" stopColor="#020308" />
          </linearGradient>
          <linearGradient id={id("fogBand")} gradientUnits="userSpaceOnUse" x1="0" y1="1100" x2="0" y2="1660">
            <stop offset="0" stopColor="#6F90CC" stopOpacity="0" />
            <stop offset="0.5" stopColor="#6F90CC" stopOpacity="0.22" />
            <stop offset="1" stopColor="#6F90CC" stopOpacity="0" />
          </linearGradient>
          <radialGradient id={id("fog")}>
            <stop offset="0" stopColor="#A4BCEB" stopOpacity="0.12" />
            <stop offset="1" stopColor="#A4BCEB" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("chartF")} gradientUnits="userSpaceOnUse" x1="0" y1={F(chart.minY)} x2="0" y2={F(chart.minY + 560)}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.44" />
            <stop offset="0.45" stopColor={pal.a} stopOpacity="0.1" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("glassF")} gradientUnits="userSpaceOnUse" x1={F(city.gx)} y1="0" x2={W + 60} y2="0">
            <stop offset="0" stopColor="#173058" />
            <stop offset="0.06" stopColor="#0A162D" />
            <stop offset="0.5" stopColor="#060C1A" />
            <stop offset="1" stopColor="#03060D" />
          </linearGradient>
          <linearGradient id={id("glassR")} gradientUnits="userSpaceOnUse" x1="0" y1={F(city.gTopR)} x2="0" y2="1900">
            <stop offset="0" stopColor={pal.haze} stopOpacity="0" />
            <stop offset="0.5" stopColor={pal.haze} stopOpacity="0.06" />
            <stop offset="1" stopColor={pal.haze} stopOpacity="0.34" />
          </linearGradient>
          <linearGradient id={id("band")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0" />
            <stop offset="0.5" stopColor={pal.lt} stopOpacity="0.16" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("edge")} gradientUnits="userSpaceOnUse" x1="0" y1={F(city.gTopL)} x2="0" y2="1900">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.1" />
            <stop offset="0.45" stopColor={pal.lt} stopOpacity="0.85" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0.15" />
          </linearGradient>
          <clipPath id={id("glassC")}>
            <path d={city.glass} />
          </clipPath>
          {/* bk0: 큰 톤색 원반(가장자리 살짝 밝게) · bk1~3: 작은 빛점(따뜻/흰/톤 밝은색) */}
          <radialGradient id={id("bk0")}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.5" />
            <stop offset="0.8" stopColor={pal.a} stopOpacity="0.4" />
            <stop offset="0.93" stopColor={pal.a} stopOpacity="0.34" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          {["#FFD29A", "#E2EDFF", pal.lt].map((c, i) => (
            <radialGradient key={i} id={id(`bk${i + 1}`)}>
              <stop offset="0" stopColor={c} stopOpacity="0.95" />
              <stop offset="0.5" stopColor={c} stopOpacity="0.6" />
              <stop offset="0.82" stopColor={c} stopOpacity="0.32" />
              <stop offset="1" stopColor={c} stopOpacity="0" />
            </radialGradient>
          ))}
          <radialGradient id={id("halo")}>
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.9" />
            <stop offset="0.25" stopColor={pal.a} stopOpacity="0.5" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("beacon")}>
            <stop offset="0" stopColor="#FFE3D0" stopOpacity="0.8" />
            <stop offset="1" stopColor="#FF8A6A" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("flare")} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0" />
            <stop offset="0.5" stopColor={pal.lt} stopOpacity="0.55" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("figRim")} gradientUnits="userSpaceOnUse" x1="0" y1="1612" x2="0" y2="1900">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.6" />
            <stop offset="0.55" stopColor={pal.lt} stopOpacity="0.18" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0" />
          </linearGradient>
          <filter id={id("blurL")} filterUnits="userSpaceOnUse" x={F(chartBox[0])} y={F(chartBox[1])} width={F(chartBox[2])} height={F(chartBox[3])}>
            <feGaussianBlur stdDeviation="11" />
          </filter>
        </defs>

        <g transform={`translate(540 1150) scale(${zoom.toFixed(4)}) translate(-540 -1150)`}>
          {/* 하늘 + 도시 빛 번짐 */}
          <rect x={-60} y={-60} width={W + 120} height={H + 120} fill={u("sky")} />
          <ellipse cx={1000} cy={640} rx={560} ry={420} fill={u("glowC")} opacity={0.3} />
          <g transform={tr(s2 * 24, 0)}>
            <ellipse cx={940} cy={560} rx={520} ry={56} fill={u("fog")} opacity={0.55} />
            <ellipse cx={820} cy={860} rx={560} ry={80} fill={u("fog")} />
            <ellipse cx={560} cy={985} rx={700} ry={90} fill={u("fog")} opacity={0.9} />
          </g>
          <ellipse cx={280} cy={1210} rx={640} ry={250} fill={u("glowC")} />
          <ellipse cx={60} cy={1320} rx={420} ry={180} fill={u("glowW")} />
          <ellipse cx={680} cy={1160} rx={820} ry={300} fill={u("glowT")} opacity={0.85 + 0.15 * pulse} />

          {/* 원경 */}
          <g transform={tr(s1 * 6, s2 * 2)}>
            <path d={city.far} fill={u("farF")} />
            <path d={city.farWin[0]} fill="#9DB6E6" opacity={0.26} />
            <path d={city.farWin[1]} fill="#FFD6A0" opacity={0.42} />
          </g>

          {/* 원경-중경 사이 안개와 빛 */}
          <ellipse cx={720} cy={1250} rx={520} ry={170} fill={u("glowT")} opacity={0.7} />
          <rect x={-60} y={1100} width={W + 120} height={560} fill={u("fogBand")} />
          <g transform={tr(s2 * 40, 0)}>
            <ellipse cx={260} cy={1330} rx={520} ry={110} fill={u("fog")} />
            <ellipse cx={860} cy={1260} rx={460} ry={90} fill={u("fog")} />
          </g>

          {/* 중경 */}
          <g transform={tr(s1 * 14, s2 * 3)}>
            <path d={city.mid} fill={u("midF")} />
            <path d={city.midSide} fill="#000" opacity={0.28} />
            <path d={city.midRim} fill="none" stroke={pal.lt} strokeOpacity={0.24} strokeWidth={1.2} />
            {city.midWin.map((d, i) => (
              <path key={i} d={d} fill={i < 3 ? warm : cool} opacity={winOp[i % 3] * 0.8} />
            ))}
            {city.twMid.map(({ w, ph, per }, i) => (
              <rect key={i} x={F(w[0])} y={F(w[1])} width={w[2]} height={w[3]} fill={warm} opacity={F(Math.max(0, Math.sin((TAU * t) / per + ph)) * 0.9 * 100) / 100} />
            ))}
            {city.beacons.map((p, i) => {
              const b = Math.max(0, Math.sin((TAU * t) / 2.6 + i * 1.9)) ** 6;
              return (
                <g key={i} opacity={0.25 + 0.75 * b}>
                  <circle cx={F(p[0])} cy={F(p[1] - 2)} r={12} fill={u("beacon")} />
                  <circle cx={F(p[0])} cy={F(p[1] - 2)} r={2.2} fill="#FFD9C8" />
                </g>
              );
            })}
          </g>

          {/* 중경-근경 사이 안개 */}
          <g transform={tr(-s2 * 30, 0)}>
            <ellipse cx={560} cy={1560} rx={720} ry={200} fill={u("glowT")} opacity={0.55} />
            <ellipse cx={420} cy={1500} rx={560} ry={90} fill={u("fog")} />
          </g>

          {/* 차트 격자 + 면 */}
          <g transform={tr(s1 * 18, 0)}>
            <path d={Array.from({ length: 7 }, (_, i) => `M-60 ${1060 + i * 80}H${W + 60}`).join("")} stroke={pal.lt} strokeOpacity={0.07} strokeWidth={1} strokeDasharray="2 12" />
            <path d={chart.fill} fill={u("chartF")} />
          </g>

          {/* 근경 */}
          <g transform={tr(s1 * 26, s2 * 4)}>
            <path d={city.near} fill={u("nearF")} />
            <path d={city.nearSide} fill="#000" opacity={0.35} />
            <g clipPath={u("glassC")}>
              <path d={city.glass} fill={u("glassF")} />
              <rect x={F(city.gx)} y={F(city.gTopR - 40)} width={300} height={1300} fill={u("glassR")} />
              <rect x={F(city.gx - 120)} y={1010} width={520} height={170} fill={u("band")} opacity={0.8 + 0.2 * pulse} transform={`rotate(-30 ${F(city.gx + 140)} 1095)`} />
              <rect x={F(city.gx - 120)} y={1270} width={520} height={34} fill={u("band")} transform={`rotate(-30 ${F(city.gx + 140)} 1287)`} />
              <path d={city.floors} stroke="#7FA6E6" strokeOpacity={0.06} strokeWidth={1} />
              <path d={city.mullions} stroke="#7FA6E6" strokeOpacity={0.04} strokeWidth={1} />
            </g>
            <path d={`M${F(city.gx)} ${F(city.gTopL)}V1960`} stroke={pal.a} strokeOpacity={0.07} strokeWidth={16} />
            <path d={`M${F(city.gx)} ${F(city.gTopL)}V1960`} stroke={u("edge")} strokeWidth={1.6} opacity={0.8} />
            <path d={`M${F(city.gx)} ${F(city.gTopL)}L${W + 90} ${F(city.gTopR - 20)}`} stroke={pal.lt} strokeOpacity={0.3} strokeWidth={1.4} />
            <path d={city.nearRim} fill="none" stroke={pal.lt} strokeOpacity={0.24} strokeWidth={1.5} />
            <path d={city.leftEdge} stroke={u("edge")} strokeWidth={1.4} opacity={0.45} />
            {city.nearWin.map((d, i) => (
              <path key={i} d={d} fill={i < 3 ? warm : cool} opacity={winOp[i % 3] * 0.85} />
            ))}
            {city.twNear.map(({ w, ph, per }, i) => (
              <rect key={i} x={F(w[0])} y={F(w[1])} width={w[2]} height={w[3]} fill={cool} opacity={F(Math.max(0, Math.sin((TAU * t) / per + ph)) * 0.8 * 100) / 100} />
            ))}
          </g>

          {/* 앞쪽 바닥 안개 (실루엣 분리) */}
          <ellipse cx={540} cy={1700} rx={560} ry={180} fill={u("glowT")} opacity={0.75} />
          <ellipse cx={540} cy={1660} rx={620} ry={120} fill={u("fog")} />

          {/* 차트 라인 */}
          <g transform={tr(s1 * 18, 0)}>
            {/* 네온 번짐: 넓은 옅은 선 + 블러 1개(차트 영역에만 한정) */}
            <path d={chart.line} fill="none" stroke={pal.a} strokeOpacity={0.05} strokeWidth={46} strokeLinejoin="round" strokeLinecap="round" />
            <path d={chart.line} fill="none" stroke={pal.a} strokeOpacity={0.6 + 0.15 * pulse} strokeWidth={14} strokeLinejoin="round" strokeLinecap="round" filter={u("blurL")} />
            <path d={chart.line} fill="none" stroke={pal.a} strokeWidth={5} strokeLinejoin="round" strokeLinecap="round" />
            <path d={chart.line} fill="none" stroke={pal.lt} strokeOpacity={0.9} strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round" />
            <path
              d={chart.line}
              fill="none"
              stroke="#FFFFFF"
              strokeOpacity={F(sweepOp * 100) / 100}
              strokeWidth={3}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${F(chart.len + dash)}`}
              strokeDashoffset={F(dash - sweepP * (chart.len + dash))}
            />
            <rect x={F(ex - 280)} y={F(ey - 1.5)} width={560} height={3} fill={u("flare")} opacity={0.5 + 0.35 * pulse} />
            <circle cx={F(ex)} cy={F(ey)} r={F(10 + 36 * pingK)} fill="none" stroke={pal.a} strokeWidth={2} strokeOpacity={F((1 - pingK) * 0.6 * 100) / 100} />
            <circle cx={F(ex)} cy={F(ey)} r={F(46 + 8 * pulse)} fill={u("halo")} opacity={0.8} />
            <circle cx={F(ex)} cy={F(ey)} r={6.5} fill="#FFFFFF" />
          </g>

          {/* 보케 */}
          {city.bokeh.map((b, i) => {
            const k = Math.sin((TAU * t) / b.per + b.ph);
            return (
              <circle
                key={i}
                cx={F(b.x + s1 * 34)}
                cy={F(b.y + k * 10)}
                r={F(b.rad)}
                fill={u(`bk${b.kind}`)}
                opacity={F(b.op * (0.8 + 0.2 * k) * 100) / 100}
              />
            );
          })}

          {/* 뒷모습 실루엣 */}
          <g transform={tr(s1 * -4, 0)}>
            <path d={FIG} fill="#010205" />
            <path d={FIG} fill="none" stroke={u("figRim")} strokeWidth={2.4} />
          </g>
        </g>
      </svg>

      {/* 비네트 · 상단 암부 · 전체 감광 (줌 영향 없음) */}
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <radialGradient id={id("vig")} gradientUnits="userSpaceOnUse" cx={540} cy={1180} r={1180}>
            <stop offset="0" stopColor="#000" stopOpacity="0" />
            <stop offset="0.52" stopColor="#000" stopOpacity="0" />
            <stop offset="0.8" stopColor="#000" stopOpacity="0.5" />
            <stop offset="1" stopColor="#000" stopOpacity="0.88" />
          </radialGradient>
          <linearGradient id={id("top")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" stopOpacity="0.55" />
            <stop offset="0.42" stopColor="#000" stopOpacity="0.12" />
            <stop offset="0.56" stopColor="#000" stopOpacity="0" />
            <stop offset="0.9" stopColor="#000" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.4" />
          </linearGradient>
          <radialGradient id={id("tl")} gradientUnits="userSpaceOnUse" cx={120} cy={320} r={900}>
            <stop offset="0" stopColor="#000" stopOpacity="0.4" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={W} height={H} fill={u("vig")} />
        <rect width={W} height={H} fill={u("top")} />
        <rect width={W} height={H} fill={u("tl")} />
        {dim > 0 && <rect width={W} height={H} fill="#000" opacity={Math.min(1, dim)} />}
      </svg>
    </AbsoluteFill>
  );
};

// 뒷모습(머리·목·어깨) — x=540 기준 좌우 대칭
const FIG =
  "M300 1960L305 1920C310 1885 330 1862 362 1852C405 1840 455 1822 490 1792C496 1786 498 1772 498 1758" +
  "C497 1748 493 1742 488 1736C480 1733 474 1710 478 1698C474 1640 500 1596 540 1596" +
  "C580 1596 606 1640 602 1698C606 1710 600 1733 592 1736C587 1742 583 1748 582 1758" +
  "C582 1772 584 1786 590 1792C625 1822 675 1840 718 1852C750 1862 770 1885 775 1920L780 1960Z";

export default BgCity;
