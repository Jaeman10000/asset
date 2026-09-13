import React, { useId, useMemo } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

/**
 * BgChip — 반도체 테마 배경.
 * 원근으로 누운 PCB 위 QFP 칩(하단 중앙), 칩에서 뻗는 네온 회로선(톤색 + 보조 시안), 비아, 파티클·보케, 안개·비네트.
 * 기하는 seed로 한 번만 만들고(useMemo), 프레임마다는 transform/opacity/dashoffset만 바꾼다.
 */

export type Tone = "up" | "down" | "neutral";

type P2 = [number, number];
type Kind = 0 | 1 | 2 | 3 | 4; // 0 dim copper · 1 tone neon · 2 cyan neon · 3 tone faint · 4 cyan faint

const W = 1080;
const H = 1920;
const TONE_HEX: Record<Tone, string> = { up: "#FF4D4D", down: "#3D7BFF", neutral: "#7FB2FF" };
const CYAN = "#38E1FF";
const VOID = "#02040A";

/* ---------- camera: shift-lens perspective onto the board plane (board units) ---------- */
const CX = 540;
const HY = 560; // horizon line on screen
const FL = 1700; // focal length (px)
const CH = 3.4; // camera height
const Z0 = 7; // camera → chip centre distance
const YAW = 0.28;
const CS = Math.cos(YAW);
const SN = Math.sin(YAW);
const ZNEAR = 3.3;
const ZFAR = 42;

const depth = (p: P2) => Z0 + p[0] * SN + p[1] * CS;
const proj = (u: number, v: number, y = 0): P2 => {
  const x = u * CS - v * SN;
  const z = Z0 + u * SN + v * CS;
  return [CX + (FL * x) / z, HY + (FL * (CH - y)) / z];
};
const unproj = (sx: number, sy: number): P2 => {
  const z = (FL * CH) / (sy - HY);
  const x = ((sx - CX) * z) / FL;
  return [CS * x + SN * (z - Z0), -SN * x + CS * (z - Z0)];
};
const CHIP_C = proj(0, 0);

/* ---------- chip dimensions ---------- */
const A = 1; // package half size
const T = 0.15; // package height
const BV = 0.045; // top bevel inset
const RIM = T - 0.035;
const LP = 0.2; // pin reach
const NP = 14; // pins per side
const TSPAN = 0.78;
const PITCH = (2 * TSPAN) / (NP - 1);
const PW = 0.056;
const TAN8 = Math.tan(Math.PI / 8);
const SQ = Math.SQRT1_2;

type Side = { o: P2; t: P2; c: [number, number, number, number] };
const SIDES: Side[] = [
  { o: [0, 1], t: [1, 0], c: [-1, 1, 1, 1] }, // far
  { o: [1, 0], t: [0, -1], c: [1, 1, 1, -1] }, // right
  { o: [0, -1], t: [-1, 0], c: [1, -1, -1, -1] }, // near
  { o: [-1, 0], t: [0, 1], c: [-1, -1, -1, 1] }, // left
];
const CAM_G: P2 = [-SN * Z0, -CS * Z0];
const faceVisible = (o: P2) => o[0] * (CAM_G[0] - o[0] * A) + o[1] * (CAM_G[1] - o[1] * A) > 0;

/* ---------- small utils ---------- */
const mulberry32 = (a: number) => () => {
  a |= 0;
  a = (a + 0x6d2b79f5) | 0;
  let t = Math.imul(a ^ (a >>> 15), 1 | a);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const hexRgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a: string, b: string, k: number) => {
  const x = hexRgb(a);
  const y = hexRgb(b);
  return `#${x.map((v, i) => Math.round(v + (y[i] - v) * k).toString(16).padStart(2, "0")).join("")}`;
};
const r1 = (v: number) => Math.round(v * 10) / 10;
const pt = (p: P2) => `${r1(p[0])} ${r1(p[1])}`;
const poly = (ps: P2[]) => `M${ps.map(pt).join("L")}Z`;
const polyline = (ps: P2[]) => `M${ps.map(pt).join("L")}`;

const leftNormal = (a: P2, b: P2): P2 => {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const l = Math.hypot(dx, dy) || 1;
  return [-dy / l, dx / l];
};
/** mitred parallel offset of a polyline (board space) */
const offsetLine = (pts: P2[], d: number): P2[] =>
  pts.map((p, i) => {
    const n1 = i === 0 ? leftNormal(p, pts[1]) : leftNormal(pts[i - 1], p);
    const n2 = i === pts.length - 1 ? n1 : leftNormal(p, pts[i + 1]);
    const mx = n1[0] + n2[0];
    const my = n1[1] + n2[1];
    const ml = Math.hypot(mx, my) || 1;
    const m: P2 = [mx / ml, my / ml];
    const k = 1 / Math.max(0.35, m[0] * n1[0] + m[1] * n1[1]);
    return [p[0] + m[0] * d * k, p[1] + m[1] * d * k];
  });
/** truncate a run at the near/far planes */
const clipRun = (pts: P2[]): { pts: P2[]; cut: boolean } => {
  const out: P2[] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    const za = depth(a);
    const zb = depth(b);
    const lim = zb < ZNEAR ? ZNEAR : zb > ZFAR ? ZFAR : null;
    if (lim === null) {
      out.push(b);
      continue;
    }
    const k = (za - lim) / (za - zb);
    out.push([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]);
    return { pts: out, cut: true };
  }
  return { pts: out, cut: false };
};
/** trace as a filled ribbon so its width foreshortens with depth */
const ribbon = (pts: P2[], w: number) => {
  if (pts.length < 2) return "";
  const l = offsetLine(pts, w / 2).map((p) => proj(p[0], p[1]));
  const r = offsetLine(pts, -w / 2)
    .map((p) => proj(p[0], p[1]))
    .reverse();
  return poly([...l, ...r]);
};
/** circle lying on the board (height y) → projected ellipse, as 4 cubic arcs */
const KB = 0.5523;
const disc = (u: number, v: number, r: number, y = 0) => {
  const c = proj(u, v, y);
  const a = proj(u + r, v, y);
  const b = proj(u, v + r, y);
  const ax = a[0] - c[0];
  const ay = a[1] - c[1];
  const bx = b[0] - c[0];
  const by = b[1] - c[1];
  const P = (s: number, t: number) => `${r1(c[0] + s * ax + t * bx)} ${r1(c[1] + s * ay + t * by)}`;
  return `M${P(1, 0)}C${P(1, KB)} ${P(KB, 1)} ${P(0, 1)}C${P(-KB, 1)} ${P(-1, KB)} ${P(-1, 0)}C${P(-1, -KB)} ${P(-KB, -1)} ${P(0, -1)}C${P(KB, -1)} ${P(1, -KB)} ${P(1, 0)}Z`;
};
const plen = (ps: P2[]) => ps.reduce((s, p, i) => (i ? s + Math.hypot(p[0] - ps[i - 1][0], p[1] - ps[i - 1][1]) : 0), 0);

type Pulse = { d: string; len: number; w: number; k: 1 | 2; sp: number; ph: number };
type Tw = { x: number; y: number; r: number; k: 1 | 2; per: number; ph: number };
type Pt = { x: number; y: number; r: number; sp: number; range: number; ph: number; op: number; c: 0 | 1 | 2; sway: number };
type Bk = { x: number; y: number; r: number; op: number; c: 1 | 2; ph: number };

function build(seed: number) {
  const rnd = mulberry32((Math.floor(seed) * 2654435761 + 12345) >>> 0);
  const R = (a: number, b: number) => a + (b - a) * rnd();
  const traces: { pts: P2[]; w: number; k: Kind }[] = [];
  const vias: { p: P2; r: number; k: Kind }[] = [];
  const onScreen = (p: P2, m = 30) => {
    const s = proj(p[0], p[1]);
    return s[0] > -m && s[0] < W + m && s[1] > HY + 80 && s[1] < H + m;
  };

  /* --- fan-out from every pin row --- */
  for (const sd of SIDES) {
    const Kf = R(1.75, 2.05);
    const d1 = R(0.1, 0.18);
    const loc = (s: number, t: number): P2 => [sd.o[0] * s + sd.t[0] * t, sd.o[1] * s + sd.t[1] * t];
    for (const sg of [-1, 1]) {
      const S = R(3.0, 3.6);
      const bend = rnd() < 0.75;
      let run = 0;
      let k: Kind = 1;
      for (let i = 0; i < NP; i++) {
        const t = -TSPAN + i * PITCH;
        if (Math.sign(t) !== sg) continue;
        if (run <= 0) {
          const q = rnd();
          k = q < 0.28 ? 0 : q < 0.78 ? 1 : 2;
          run = 1 + Math.floor(rnd() * 4);
        }
        run--;
        if (rnd() < 0.14) continue;
        const tp = t * Kf;
        const s0 = A + LP - 0.04;
        const s1 = A + LP + d1;
        const s2 = s1 + Math.abs(tp - t);
        const pts: P2[] = [loc(s0, t), loc(s1, t), loc(s2, tp)];
        const len = rnd() < 0.4 ? R(0.2, 1.1) : R(1.6, 9);
        const s3 = S - Math.abs(tp) * TAN8;
        if (bend && s3 > s2 + 0.02 && len > s3 - s2) {
          pts.push(loc(s3, tp));
          const rem = len - (s3 - s2);
          pts.push(loc(s3 + rem * SQ, tp + sg * rem * SQ));
        } else pts.push(loc(s2 + len, tp));
        const c = clipRun(pts);
        traces.push({ pts: c.pts, w: 0.026, k });
        const end = c.pts[c.pts.length - 1];
        if (!c.cut && onScreen(end)) vias.push({ p: end, r: 0.052, k });
      }
    }
  }

  /* --- background routing: buses + singles, avoiding the chip --- */
  const DIRS: P2[] = Array.from({ length: 8 }, (_, i) => [Math.cos((i * Math.PI) / 4), Math.sin((i * Math.PI) / 4)] as P2);
  const keepOut = (p: P2) => Math.abs(p[0]) < 2.2 && Math.abs(p[1]) < 2.2;
  const sample = (): P2 => {
    for (let n = 0; n < 40; n++) {
      const sy = 780 + Math.pow(rnd(), 0.75) * 1200;
      const sx = -60 + rnd() * 1200;
      const p = unproj(sx, sy);
      if (!keepOut(p)) return p;
    }
    return unproj(80, 1800);
  };
  const route = (start: P2, segs: number) => {
    let di = rnd() < 0.7 ? 2 * Math.floor(rnd() * 4) : Math.floor(rnd() * 8);
    const pts: P2[] = [start];
    for (let s = 0; s < segs; s++) {
      const L = R(0.5, 2.4);
      const last = pts[pts.length - 1];
      const nx: P2 = [last[0] + DIRS[di][0] * L, last[1] + DIRS[di][1] * L];
      if (keepOut(nx)) break;
      pts.push(nx);
      di = (di + (rnd() < 0.5 ? 1 : 7)) % 8;
    }
    return pts;
  };
  const bgKind = (): Kind => {
    const q = rnd();
    return q < 0.7 ? 0 : q < 0.85 ? 4 : 3;
  };
  for (let b = 0; b < 9; b++) {
    const center = route(sample(), 2 + Math.floor(rnd() * 3));
    if (center.length < 2) continue;
    const n = 3 + Math.floor(rnd() * 4);
    const sp = R(0.07, 0.1);
    const w = R(0.018, 0.026);
    const k = bgKind();
    for (let j = 0; j < n; j++) {
      const c = clipRun(offsetLine(center, (j - (n - 1) / 2) * sp));
      traces.push({ pts: c.pts, w, k });
      if (!c.cut && onScreen(c.pts[c.pts.length - 1])) vias.push({ p: c.pts[c.pts.length - 1], r: 0.042, k });
      if (onScreen(c.pts[0])) vias.push({ p: c.pts[0], r: 0.042, k });
    }
  }
  for (let s = 0; s < 34; s++) {
    const c = clipRun(route(sample(), 1 + Math.floor(rnd() * 3)));
    if (c.pts.length < 2) continue;
    const k = bgKind();
    traces.push({ pts: c.pts, w: rnd() < 0.2 ? R(0.05, 0.08) : R(0.018, 0.03), k });
    if (onScreen(c.pts[0])) vias.push({ p: c.pts[0], r: 0.045, k });
    if (!c.cut && onScreen(c.pts[c.pts.length - 1])) vias.push({ p: c.pts[c.pts.length - 1], r: 0.045, k });
  }
  // stitching-via fields
  for (let f = 0; f < 4; f++) {
    const o = sample();
    const nx = 2 + Math.floor(rnd() * 3);
    const ny = 2 + Math.floor(rnd() * 3);
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) vias.push({ p: [o[0] + i * 0.13, o[1] + j * 0.13], r: 0.035, k: 0 });
  }
  for (let v = 0; v < 26; v++) vias.push({ p: sample(), r: R(0.03, 0.05), k: 0 });

  /* --- path strings --- */
  const P: Record<string, string> = { dim: "", tone: "", cyan: "", toneF: "", cyanF: "", toneCore: "", cyanCore: "", viaDim: "", viaTone: "", viaCyan: "" };
  for (const tr of traces) {
    const rb = ribbon(tr.pts, tr.w);
    if (tr.k === 0) P.dim += rb;
    else if (tr.k === 1) {
      P.tone += rb;
      P.toneCore += ribbon(tr.pts, tr.w * 0.34);
    } else if (tr.k === 2) {
      P.cyan += rb;
      P.cyanCore += ribbon(tr.pts, tr.w * 0.34);
    } else if (tr.k === 3) P.toneF += rb;
    else P.cyanF += rb;
  }
  for (const v of vias) {
    const ringD = disc(v.p[0], v.p[1], v.r) + disc(v.p[0], v.p[1], v.r * 0.5);
    if (v.k === 1) P.viaTone += ringD;
    else if (v.k === 2) P.viaCyan += ringD;
    else P.viaDim += ringD;
  }

  /* --- data pulses on bright fan traces (start 0.45 units out, clear of the package silhouette) --- */
  const trimStart = (pts: P2[], d: number): P2[] => {
    let rem = d;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1];
      const b = pts[i];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (L > rem) {
        const k = rem / L;
        return [[a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k], ...pts.slice(i)];
      }
      rem -= L;
    }
    return [];
  };
  const cands = traces
    .filter((tr) => tr.k === 1 || tr.k === 2)
    .map((tr) => ({ tr, run: trimStart(tr.pts, 0.45) }))
    .filter((c) => c.run.length > 1 && plen(c.run.map((p) => proj(p[0], p[1]))) > 240);
  const pulses: Pulse[] = [];
  for (let i = 0; i < cands.length && pulses.length < 8; i++) {
    if (rnd() < 0.45) continue;
    const { tr, run } = cands[i];
    const sp = run.map((p) => proj(p[0], p[1]));
    pulses.push({
      d: polyline(sp),
      len: plen(sp),
      w: (tr.w * FL) / depth(run[0]),
      k: tr.k === 1 ? 1 : 2,
      sp: R(4.5, 7.5),
      ph: R(0, 2400),
    });
  }

  /* --- twinkling via lights --- */
  const tw: Tw[] = [];
  for (const v of vias) {
    if (tw.length >= 12) break;
    if (!(v.k === 1 || v.k === 2) || rnd() < 0.35) continue;
    const s = proj(v.p[0], v.p[1]);
    if (s[1] < 1000) continue;
    tw.push({ x: s[0], y: s[1], r: (0.03 * FL) / depth(v.p), k: v.k === 1 ? 1 : 2, per: R(2.2, 5), ph: R(0, 6.28) });
  }

  /* --- chip --- */
  const at = (sd: Side, s: number, t: number, y: number) => proj(sd.o[0] * s + sd.t[0] * t, sd.o[1] * s + sd.t[1] * t, y);
  const cc = (sx: number, sy: number, h: number, y: number) => proj(sx * h, sy * h, y);
  const YR = T * 0.42;
  const YF = 0.012;
  const pins = { back: { sh: "", sl: "", ft: "" }, front: { sh: "", sl: "", ft: "" } };
  let pads = "";
  const walls: { d: string; side: number }[] = [];
  const bevels: string[] = [];
  const rimBack: string[] = [];
  const rimFront: string[] = [];
  SIDES.forEach((sd, si) => {
    const vis = faceVisible(sd.o);
    const tg = vis ? pins.front : pins.back;
    for (let i = 0; i < NP; i++) {
      const t = -TSPAN + i * PITCH;
      const q = (sA: number, yA: number, sB: number, yB: number, w: number) =>
        poly([at(sd, sA, t - w / 2, yA), at(sd, sB, t - w / 2, yB), at(sd, sB, t + w / 2, yB), at(sd, sA, t + w / 2, yA)]);
      tg.sh += q(A - 0.02, YR, A + 0.06, YR, PW);
      tg.sl += q(A + 0.06, YR, A + 0.11, YF, PW);
      tg.ft += q(A + 0.11, YF, A + LP, YF, PW);
      pads += q(A + 0.085, 0, A + LP + 0.035, 0, PW * 1.45);
    }
    const [ax, ay, bx, by] = sd.c;
    if (vis) walls.push({ d: poly([cc(ax, ay, A, 0.015), cc(bx, by, A, 0.015), cc(bx, by, A, RIM), cc(ax, ay, A, RIM)]), side: si });
    bevels.push(poly([cc(ax, ay, A, RIM), cc(bx, by, A, RIM), cc(bx, by, A - BV, T), cc(ax, ay, A - BV, T)]));
    if (vis) rimFront.push(polyline([cc(ax, ay, A - BV, T), cc(bx, by, A - BV, T)]));
    else rimBack.push(polyline([cc(ax, ay, A, RIM), cc(bx, by, A, RIM)]));
  });
  const topPts = [cc(-1, 1, A - BV, T), cc(1, 1, A - BV, T), cc(1, -1, A - BV, T), cc(-1, -1, A - BV, T)];
  const top = poly(topPts);
  const topY0 = Math.min(...topPts.map((p) => p[1]));
  const topY1 = Math.max(...topPts.map((p) => p[1]));
  const topX0 = Math.min(...topPts.map((p) => p[0]));
  const topX1 = Math.max(...topPts.map((p) => p[0]));

  // die window (slightly towards the far edge so the marking fits in front)
  const DH = 0.46;
  const DV = 0.12;
  const YD = T + 0.004;
  const dp = (u: number, v: number) => proj(u, v + DV, YD);
  const die = poly([dp(-DH, DH), dp(DH, DH), dp(DH, -DH), dp(-DH, -DH)]);
  const NG = 16;
  let dieGrid = "";
  for (let i = 1; i < NG; i++) {
    const a = -DH + (2 * DH * i) / NG;
    dieGrid += `M${pt(dp(a, -DH))}L${pt(dp(a, DH))}M${pt(dp(-DH, a))}L${pt(dp(DH, a))}`;
  }
  // die floorplan (die-local −1..1): two cores, a cache band, four IP blocks, an I/O pad ring
  const rect = (a0: number, b0: number, a1: number, b1: number) => poly([dp(a0 * DH, b0 * DH), dp(a1 * DH, b0 * DH), dp(a1 * DH, b1 * DH), dp(a0 * DH, b1 * DH)]);
  const plan: [number, number, number, number, 1 | 2][] = [
    [-0.8, 0.08, -0.05, 0.8, 1],
    [0.05, 0.08, 0.8, 0.8, 1],
    [-0.8, -0.3, 0.8, -0.04, 2],
    [-0.8, -0.8, -0.43, -0.4, 2],
    [-0.37, -0.8, -0.03, -0.4, 1],
    [0.03, -0.8, 0.37, -0.4, 2],
    [0.43, -0.8, 0.8, -0.4, 1],
  ];
  const blocks = plan.map(([a0, b0, a1, b1, k], i) => ({ d: rect(a0, b0, a1, b1), k, op: i < 2 ? R(0.13, 0.19) : R(0.06, 0.12) }));
  let io = "";
  for (let i = 0; i < 12; i++) {
    const p = -0.82 + (i * 1.64) / 11;
    const s = 0.035;
    io += rect(p - s, 0.9 - s, p + s, 0.9 + s) + rect(p - s, -0.9 - s, p + s, -0.9 + s) + rect(0.9 - s, p - s, 0.9 + s, p + s) + rect(-0.9 - s, p - s, -0.9 + s, p + s);
  }
  const dieGlow = disc(0, DV, DH * 1.1, YD);
  const pin1 = disc(-0.8, 0.8, 0.045, T);

  // laser marking — local affine of the projection at the text anchor (1 local unit = 0.01 board units)
  const tc: P2 = [0, -0.66];
  const p0 = proj(tc[0], tc[1], T);
  const pu = proj(tc[0] + 0.01, tc[1], T);
  const pv = proj(tc[0], tc[1] - 0.01, T);
  const txtM = `matrix(${[pu[0] - p0[0], pu[1] - p0[1], pv[0] - p0[0], pv[1] - p0[1], p0[0], p0[1]].map((x) => x.toFixed(4)).join(" ")})`;

  /* --- particles & bokeh (screen space) --- */
  const parts: Pt[] = [];
  while (parts.length < 28) {
    const x = R(0, W);
    const y = 620 + Math.pow(rnd(), 0.65) * (H - 560);
    if (x < 640 && y < 1050 && rnd() < 0.9) continue;
    const q = rnd();
    parts.push({ x, y, r: q < 0.14 ? R(4, 6.5) : R(1.5, 3.6), sp: R(0.2, 0.7), range: R(140, 380), ph: R(0, 380), op: R(0.35, 0.9), c: q < 0.45 ? 1 : q < 0.75 ? 2 : 0, sway: R(3, 10) });
  }
  const bokeh: Bk[] = [];
  for (let i = 0; i < 13; i++) {
    let x: number;
    let y: number;
    if (i < 8) {
      x = i % 2 ? R(-60, 210) : R(870, 1140);
      y = R(1050, 1980);
    } else if (i < 11) {
      x = R(200, 880);
      y = R(1780, 2000);
    } else {
      x = R(820, 1100);
      y = R(160, 620);
    }
    bokeh.push({ x, y, r: i >= 11 ? R(40, 80) : R(30, 115), op: i >= 11 ? R(0.06, 0.1) : R(0.18, 0.34), c: rnd() < 0.55 ? 1 : 2, ph: R(0, 6.28) });
  }

  return {
    P,
    pulses,
    tw,
    pins,
    pads,
    walls,
    bevels,
    rimBack,
    rimFront,
    top,
    topY0,
    topY1,
    topX0,
    topX1,
    die,
    dieGrid,
    blocks,
    io,
    dieGlow,
    pin1,
    txtM,
    parts,
    bokeh,
    under: disc(0, 0.3, 3.6),
    halo: disc(0, 0, 1.9),
    shadow: disc(0, 0, 1.22),
    leak: disc(0, 0, 1.75),
  };
}

const TAU = Math.PI * 2;
const M = 48; // each layer's SVG overhangs the frame so drift/push never exposes an edge

const Layer: React.FC<{ style?: React.CSSProperties; children?: React.ReactNode }> = ({ style, children }) => (
  <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, ...style }}>
    <svg width={W + 2 * M} height={H + 2 * M} viewBox={`${-M} ${-M} ${W + 2 * M} ${H + 2 * M}`} style={{ position: "absolute", left: -M, top: -M }}>
      {children}
    </svg>
  </div>
);

export const BgChip: React.FC<{ tone?: Tone; seed?: number; dim?: number }> = ({ tone = "neutral", seed = 7, dim = 0.15 }) => {
  const frame = useCurrentFrame();
  const id = "bgc" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const g = useMemo(() => build(seed), [seed]);
  const u = (s: string) => `url(#${id}${s})`;

  const TC = TONE_HEX[tone];
  const toneHot = mix(TC, "#FFFFFF", 0.55);
  const cyanHot = mix(CYAN, "#FFFFFF", 0.55);
  const dimTrace = mix(TC, "#A9BCE0", 0.7);

  // slow camera: push-in 0–3.6 % over 14 s, lateral drift; near layer gets 2.4× parallax
  const t = frame / 30;
  const push = 1.018 + 0.018 * Math.sin((TAU * t) / 14 - Math.PI / 2);
  const dx = 9 * Math.sin((TAU * t) / 11);
  const dy = 6 * Math.sin((TAU * t) / 13 + 1);
  const breathe = 0.5 + 0.5 * Math.sin((TAU * t) / 4.2);
  // Static layers never change their SVG content, only a CSS transform/opacity, so Chrome rasterises them
  // (blur included) once per tab and just re-composites them every frame.
  const cam: React.CSSProperties = {
    transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${push.toFixed(5)})`,
    transformOrigin: `${CHIP_C[0].toFixed(1)}px ${CHIP_C[1].toFixed(1)}px`,
    willChange: "transform",
  };
  const near: React.CSSProperties = { transform: `translate(${(dx * 2.4).toFixed(2)}px, ${(dy * 2.4).toFixed(2)}px)`, willChange: "transform" };

  const pf = [u("pW"), u("pT"), u("pC")];

  return (
    <AbsoluteFill style={{ background: VOID, overflow: "hidden" }}>
      {/* L1 · the whole static board: base, baked neon glow (blur rasterised once per tab), cores (+ all shared defs) */}
      <Layer style={cam}>
        <defs>
          <linearGradient id={`${id}bg`} x1="0" y1="0" x2="0" y2={H} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#03050C" />
            <stop offset="0.36" stopColor="#040916" />
            <stop offset="0.72" stopColor="#071122" />
            <stop offset="1" stopColor="#081428" />
          </linearGradient>
          {/* energy falloff: traces burn hottest next to the chip */}
          {(
            [
              ["eT", TC, 1],
              ["eC", CYAN, 0.85],
              ["eTh", toneHot, 0.95],
              ["eCh", cyanHot, 0.8],
            ] as const
          ).map(([k, c, o]) => (
            <radialGradient key={k} id={`${id}${k}`} cx={CHIP_C[0]} cy={CHIP_C[1]} r="1050" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor={c} stopOpacity={o} />
              <stop offset="0.3" stopColor={c} stopOpacity={o * 0.85} />
              <stop offset="0.65" stopColor={c} stopOpacity={o * 0.45} />
              <stop offset="1" stopColor={c} stopOpacity={o * 0.22} />
            </radialGradient>
          ))}
          <radialGradient id={`${id}vol`} cx="540" cy="1330" r="760" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={TC} stopOpacity="0.16" />
            <stop offset="0.5" stopColor={TC} stopOpacity="0.06" />
            <stop offset="1" stopColor={TC} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}orb`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#6F9BFF" stopOpacity="0.5" />
            <stop offset="1" stopColor="#6F9BFF" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${id}fg`} x1="0" y1="1560" x2="0" y2={H} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#000" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.68" />
          </linearGradient>
          <radialGradient id={`${id}under`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor={TC} stopOpacity="0.42" />
            <stop offset="0.35" stopColor={TC} stopOpacity="0.16" />
            <stop offset="1" stopColor={TC} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}halo`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0.45" stopColor={TC} stopOpacity="0.22" />
            <stop offset="1" stopColor={TC} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}shadow`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0.6" stopColor="#000" stopOpacity="0.8" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}leak`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0.52" stopColor={TC} stopOpacity="0" />
            <stop offset="0.64" stopColor={TC} stopOpacity="0.8" />
            <stop offset="0.78" stopColor={TC} stopOpacity="0.28" />
            <stop offset="1" stopColor={TC} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}amb`} cx="930" cy="160" r="820" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#13264D" stopOpacity="0.55" />
            <stop offset="0.55" stopColor="#0C1A38" stopOpacity="0.2" />
            <stop offset="1" stopColor="#0C1A38" stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}glow`} x={-M} y={HY} width={W + 2 * M} height={H + M - HY} filterUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="a" />
            <feGaussianBlur in="SourceGraphic" stdDeviation="15" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="b" />
              <feMergeNode in="a" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id={`${id}metal`} x1={g.topX0} y1="0" x2={g.topX1} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#7D8797" />
            <stop offset="0.22" stopColor="#D7DDE6" />
            <stop offset="0.45" stopColor="#8B95A6" />
            <stop offset="0.68" stopColor="#E3E8EF" />
            <stop offset="1" stopColor="#7A8496" />
          </linearGradient>
          <linearGradient id={`${id}metalD`} x1={g.topX0} y1="0" x2={g.topX1} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#3B4352" />
            <stop offset="0.5" stopColor="#7E889A" />
            <stop offset="1" stopColor="#3B4352" />
          </linearGradient>
          <linearGradient id={`${id}wall`} x1="0" y1={g.topY1 - 20} x2="0" y2={g.topY1 + 60} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#141923" />
            <stop offset="1" stopColor="#06080C" />
          </linearGradient>
          <linearGradient id={`${id}top`} x1="0" y1={g.topY0} x2="0" y2={g.topY1} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#1A202C" />
            <stop offset="0.5" stopColor="#10141C" />
            <stop offset="1" stopColor="#0A0D13" />
          </linearGradient>
          <linearGradient id={`${id}tint`} x1="0" y1={g.topY0} x2="0" y2={g.topY1} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={TC} stopOpacity="0.26" />
            <stop offset="0.42" stopColor={TC} stopOpacity="0" />
            <stop offset="0.86" stopColor={TC} stopOpacity="0" />
            <stop offset="1" stopColor={TC} stopOpacity="0.09" />
          </linearGradient>
          <linearGradient id={`${id}sheen`} x1={g.topX0} y1={g.topY0} x2={g.topX1} y2={g.topY1} gradientUnits="userSpaceOnUse">
            <stop offset="0.25" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="0.42" stopColor="#FFFFFF" stopOpacity="0.1" />
            <stop offset="0.52" stopColor="#FFFFFF" stopOpacity="0.02" />
            <stop offset="0.6" stopColor="#FFFFFF" stopOpacity="0" />
          </linearGradient>
          <radialGradient id={`${id}dieGlow`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor={TC} stopOpacity="0.3" />
            <stop offset="1" stopColor={TC} stopOpacity="0" />
          </radialGradient>
          {(
            [
              ["pW", "#EAF2FF"],
              ["pT", toneHot],
              ["pC", cyanHot],
            ] as const
          ).map(([k, c]) => (
            <radialGradient key={k} id={`${id}${k}`} cx="0.5" cy="0.5" r="0.5">
              <stop offset="0" stopColor={c} stopOpacity="1" />
              <stop offset="0.35" stopColor={c} stopOpacity="0.55" />
              <stop offset="1" stopColor={c} stopOpacity="0" />
            </radialGradient>
          ))}
          {(
            [
              ["bT", TC],
              ["bC", CYAN],
            ] as const
          ).map(([k, c]) => (
            <radialGradient key={k} id={`${id}${k}`} cx="0.5" cy="0.5" r="0.5">
              <stop offset="0" stopColor={c} stopOpacity="0.42" />
              <stop offset="0.7" stopColor={c} stopOpacity="0.36" />
              <stop offset="0.88" stopColor={c} stopOpacity="0.48" />
              <stop offset="1" stopColor={c} stopOpacity="0" />
            </radialGradient>
          ))}
          <linearGradient id={`${id}fog`} x1="0" y1="0" x2="0" y2={H} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={VOID} stopOpacity="1" />
            <stop offset="0.3" stopColor={VOID} stopOpacity="0.94" />
            <stop offset="0.42" stopColor={VOID} stopOpacity="0.62" />
            <stop offset="0.52" stopColor={VOID} stopOpacity="0.36" />
            <stop offset="0.62" stopColor={VOID} stopOpacity="0.1" />
            <stop offset="0.7" stopColor={VOID} stopOpacity="0" />
          </linearGradient>
          <radialGradient id={`${id}haze`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#173065" stopOpacity="0.42" />
            <stop offset="0.6" stopColor="#10224A" stopOpacity="0.14" />
            <stop offset="1" stopColor="#10224A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}tl`} cx="200" cy="420" r="820" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={VOID} stopOpacity="0.6" />
            <stop offset="1" stopColor={VOID} stopOpacity="0" />
          </radialGradient>
          <radialGradient id={`${id}vig`} cx="540" cy="1280" r="1180" gradientUnits="userSpaceOnUse">
            <stop offset="0.42" stopColor="#000" stopOpacity="0" />
            <stop offset="0.78" stopColor="#000" stopOpacity="0.5" />
            <stop offset="1" stopColor="#000" stopOpacity="0.88" />
          </radialGradient>
        </defs>
        <rect x={-M} y={-M} width={W + 2 * M} height={H + 2 * M} fill={u("bg")} />
        <path d={g.P.dim} fill={dimTrace} fillOpacity="0.14" />
        <path d={g.P.viaDim} fill="#9FB2D4" fillOpacity="0.2" fillRule="evenodd" />
        <path d={g.under} fill={u("under")} />
        <g filter={u("glow")}>
          <path d={g.P.toneF} fill={TC} fillOpacity="0.36" />
          <path d={g.P.cyanF} fill={CYAN} fillOpacity="0.28" />
          <path d={g.P.tone} fill={u("eT")} />
          <path d={g.P.cyan} fill={u("eC")} />
          <path d={g.P.viaTone} fill={u("eT")} fillRule="evenodd" />
          <path d={g.P.viaCyan} fill={u("eC")} fillRule="evenodd" />
        </g>
        <path d={g.halo} fill={u("halo")} />
        <path d={g.P.toneCore} fill={u("eTh")} />
        <path d={g.P.cyanCore} fill={u("eCh")} />
        <path d={g.shadow} fill={u("shadow")} />
      </Layer>

      {/* L2 · moving data pulses + twinkling vias (sparse, unfiltered; soft edge from stacked strokes) */}
      <Layer style={cam}>
        {g.pulses.map((p, i) => {
          const cycle = p.len + 900;
          const pos = (frame * p.sp + p.ph) % cycle;
          const env = Math.min(1, pos / 60) * Math.max(0, Math.min(1, (p.len + 40 - pos) / 220));
          if (env <= 0) return null;
          const hot = p.k === 1 ? toneHot : cyanHot;
          const col = p.k === 1 ? TC : CYAN;
          const gap = p.len + 600;
          return (
            <g key={i} opacity={env} fill="none" strokeLinecap="round">
              <path d={p.d} stroke={col} strokeOpacity={0.14} strokeWidth={p.w * 4.5} strokeDasharray={`70 ${gap}`} strokeDashoffset={70 - pos} />
              <path d={p.d} stroke={col} strokeOpacity={0.5} strokeWidth={p.w * 1.2} strokeDasharray={`160 ${gap}`} strokeDashoffset={160 - pos} />
              <path d={p.d} stroke={hot} strokeWidth={p.w * 1.4} strokeDasharray={`36 ${gap}`} strokeDashoffset={36 - pos} />
            </g>
          );
        })}
        {g.tw.map((w, i) => (
          <circle key={i} cx={w.x} cy={w.y} r={w.r * 2.6} fill={w.k === 1 ? u("pT") : u("pC")} opacity={0.12 + 0.88 * Math.pow(0.5 + 0.5 * Math.sin((TAU * t) / w.per + w.ph), 4)} />
        ))}
      </Layer>

      {/* L3 · light leaking from under the package — the one glow that breathes (layer opacity only) */}
      <Layer style={{ ...cam, opacity: 0.6 + 0.4 * breathe, willChange: "transform, opacity" }}>
        <path d={g.leak} fill={u("leak")} />
      </Layer>

      {/* L4 · the chip (static, sparse) */}
      <Layer style={cam}>
        <path d={g.pads} fill="#8A97AE" fillOpacity="0.42" />
        <path d={g.pins.back.ft} fill={u("metalD")} />
        <path d={g.pins.back.sl} fill="#2A303C" />
        <path d={g.pins.back.sh} fill={u("metalD")} />
        {g.walls.map((w, i) => (
          <path key={i} d={w.d} fill={u("wall")} />
        ))}
        {g.bevels.map((d, i) => (
          <path key={i} d={d} fill={i === 2 ? "#2B3342" : i === 0 ? mix(TC, "#10131A", 0.55) : i === 1 ? mix(TC, "#141821", 0.78) : "#1D2330"} />
        ))}
        <path d={g.top} fill={u("top")} />
        <path d={g.top} fill={u("tint")} />
        <path d={g.dieGlow} fill={u("dieGlow")} />
        <path d={g.die} fill="#070A12" fillOpacity="0.82" stroke={mix(TC, "#FFFFFF", 0.35)} strokeOpacity="0.45" strokeWidth="1.2" />
        {g.blocks.map((b, i) => (
          <path key={i} d={b.d} fill={b.k === 1 ? TC : CYAN} fillOpacity={b.op} />
        ))}
        <path d={g.dieGrid} stroke={mix(TC, "#FFFFFF", 0.4)} strokeOpacity="0.16" strokeWidth="0.7" fill="none" />
        <path d={g.io} fill="#AEB9CC" fillOpacity="0.28" />
        <path d={g.top} fill={u("sheen")} />
        <path d={g.pin1} fill="#04060A" stroke="#56627A" strokeOpacity="0.5" strokeWidth="0.8" />
        <text transform={g.txtM} fontSize={9.5} fontWeight={600} letterSpacing={2.6} textAnchor="middle" dominantBaseline="middle" fill="#B7C1D3" fillOpacity="0.5" fontFamily="'Segoe UI', 'Helvetica Neue', Arial, sans-serif">
          SEMICONDUCTOR
        </text>
        {/* rim light on the back silhouette, specular on the front top edge */}
        {g.rimBack.map((d, i) => (
          <g key={i} fill="none" strokeLinecap="round">
            <path d={d} stroke={TC} strokeOpacity={0.11} strokeWidth="9" />
            <path d={d} stroke={TC} strokeOpacity={0.28} strokeWidth="4" />
            <path d={d} stroke={toneHot} strokeOpacity="0.9" strokeWidth="1.4" />
          </g>
        ))}
        {g.rimFront.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="#DDE6F5" strokeOpacity="0.32" strokeWidth="1.2" />
        ))}
        <path d={g.pins.front.ft} fill={u("metal")} />
        <path d={g.pins.front.sl} fill={u("metalD")} />
        <path d={g.pins.front.sh} fill={u("metal")} />
      </Layer>

      {/* L5 · near: rising dust motes (2.4× parallax) */}
      <Layer style={near}>
        {g.parts.map((p, i) => {
          const pr = ((frame * p.sp + p.ph) % p.range) / p.range;
          return <circle key={i} cx={p.x + p.sway * Math.sin(frame / 45 + i)} cy={p.y - pr * p.range} r={p.r} fill={pf[p.c]} opacity={p.op * Math.sin(Math.PI * pr)} />;
        })}
      </Layer>

      {/* L6 · air: fog, haze, bokeh, vignette, readability darkening (static) */}
      <Layer>
        <rect x={-M} y={-M} width={W + 2 * M} height={H + 2 * M} fill={u("fog")} />
        <rect width={W} height={H} fill={u("amb")} />
        <ellipse cx={720} cy={HY + 90} rx={760} ry={250} fill={u("haze")} />
        <rect width={W} height={H} fill={u("vol")} />
        {g.bokeh.map((b, i) => (
          <circle key={i} cx={b.x} cy={b.y} r={b.r} fill={i >= 11 ? u("orb") : b.c === 1 ? u("bT") : u("bC")} opacity={b.op} />
        ))}
        <rect width={W} height={H} fill={u("tl")} />
        <rect y={1560} width={W} height={H - 1560} fill={u("fg")} />
        <rect width={W} height={H} fill={u("vig")} />
        {dim > 0 && <rect width={W} height={H} fill="#000" opacity={Math.min(1, dim)} />}
      </Layer>
    </AbsoluteFill>
  );
};

export default BgChip;
