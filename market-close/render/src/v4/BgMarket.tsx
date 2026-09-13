import React, { useEffect, useMemo, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, useCurrentFrame } from "remotion";

/**
 * BgMarket — 트레이딩 스크린 분위기 배경 (1080x1920).
 * 원경: 흐린 도시 보케·세로 빛줄기·먼 모니터 / 중경: 기울어진 캔들차트 모니터 / 근경: 큰 보케·비네트.
 *
 * 성능: Remotion은 프레임마다 페이지 전체를 다시 칠한다(captureBeyondViewport). 그래서 무거운 정적 레이어
 * (블러·수백 개 도형)는 seed로 한 번만 SVG 문자열로 만들어 data-URI 배경으로 쓴다 — 크롬이 래스터를
 * 캐시해 매 프레임 비트맵 한 장 그리는 비용만 든다. 프레임마다 바뀌는 건 transform·opacity와 작은 div 몇 개뿐.
 * 상단 55%는 큰 글자 자리라 어둡고 조용하게, 밝은 글로우는 하단 45%와 가장자리에 둔다.
 */
export type Tone = "up" | "down" | "neutral";

const W = 1080;
const H = 1920;
const TAU = Math.PI * 2;

type Pal = {
  accent: string;
  light: string;
  opp: string;
  base0: string;
  base1: string;
  bokeh: string[]; // [강조, 강조 밝은, 따뜻한 도시광, 흰빛, 보조]
};

const PAL: Record<Tone, Pal> = {
  up: { accent: "#FF4D4D", light: "#FFB0A4", opp: "#3D7BFF", base0: "#04050D", base1: "#0B0B1D", bokeh: ["#FF4D4D", "#FF7B63", "#FFB36B", "#FFE4CF", "#7D9CFF"] },
  down: { accent: "#3D7BFF", light: "#AFCBFF", opp: "#FF4D4D", base0: "#030611", base1: "#061229", bokeh: ["#3D7BFF", "#79A7FF", "#FFB36B", "#E0EBFF", "#45C8FF"] },
  neutral: { accent: "#7FB2FF", light: "#D6E7FF", opp: "#4C6A9E", base0: "#030712", base1: "#07142B", bokeh: ["#7FB2FF", "#A9CCFF", "#FFBF7A", "#E8F1FF", "#5ED6E8"] },
};

const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.round(a * 1000) / 1000})`;
};

function mulberry32(a: number) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r1 = (n: number) => Math.round(n * 10) / 10;
const r2 = (n: number) => Math.round(n * 100) / 100;
const fmt2 = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Catmull-Rom → cubic Bézier */
function smooth(pts: [number, number][]) {
  let d = `M${r1(pts[0][0])},${r1(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    d += `C${r1(p1[0] + (p2[0] - p0[0]) / 6)},${r1(p1[1] + (p2[1] - p0[1]) / 6)} ${r1(p2[0] - (p3[0] - p1[0]) / 6)},${r1(p2[1] - (p3[1] - p1[1]) / 6)} ${r1(p2[0])},${r1(p2[1])}`;
  }
  return d;
}

// ---------- SVG 문자열 도우미 ----------
type Attrs = Record<string, string | number>;
const tag = (name: string, a: Attrs, inner?: string) => {
  let s = `<${name}`;
  for (const k of Object.keys(a)) s += ` ${k}="${a[k]}"`;
  return inner === undefined ? `${s}/>` : `${s}>${inner}</${name}>`;
};
const svgDoc = (w: number, h: number, inner: string) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${inner}</svg>`;
const toUri = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
const stops = (c: string, list: [number, number][]) => list.map(([o, a]) => tag("stop", { offset: o, "stop-color": c, "stop-opacity": a })).join("");

const MONO = "'SF Mono', Consolas, 'Roboto Mono', 'DejaVu Sans Mono', monospace";

// 모니터 패널 (로컬 좌표)
const PW = 1060;
const PH = 800;
const PL = -40; // 화면상 위치
const PT = 1092;
const CX0 = 40;
const CX1 = PW - 154;
const CY0 = 104;
const CY1 = 606;
const VY0 = 634;
const VY1 = 704;
const N = 32;
const GM = 130; // 글로우 이미지 여백
const PERSP = 2000;
const BM = 40; // 원경 이미지 여백(패럴랙스 이동분)
const TW_Y0 = 940; // 반짝이는 보케 띠 시작 y
const TW_H = 340;

function build(tone: Tone, seed: number) {
  const pal = PAL[tone];
  const rnd = mulberry32(((seed | 0) * 7919 + (tone === "up" ? 101 : tone === "down" ? 202 : 303)) >>> 0);
  const sgn = tone === "up" ? 1 : tone === "down" ? -1 : 0;
  const riseC = tone === "down" ? pal.opp : pal.accent;
  const fallC = tone === "down" ? pal.accent : pal.opp;

  // ================= 캔들: 추세 → 반등(반대색 몇 개) → 가속 =================
  const O: number[] = [];
  const Cl: number[] = [];
  const Hi: number[] = [];
  const Lo: number[] = [];
  const Vo: number[] = [];
  let p = 0;
  const ph = rnd() * TAU;
  for (let i = 0; i < N; i++) {
    const pTone = i < 11 ? 0.76 : i < 17 ? 0.4 : 0.88;
    const dir = sgn ? (rnd() < pTone ? sgn : -sgn) : Math.sin(i * 0.45 + ph) + (rnd() - 0.5) * 1.1 >= 0 ? 1 : -1;
    const climax = sgn && i >= N - 6 && dir === sgn ? 1.7 : 1;
    const body = (0.3 + rnd() * rnd() * 2.0 + rnd() * 0.45) * climax * (dir === sgn || !sgn ? 1 : 0.8);
    const open = p + (rnd() - 0.5) * 0.26;
    const close = open + dir * body;
    O.push(open);
    Cl.push(close);
    Hi.push(Math.max(open, close) + rnd() * rnd() * 1.1 + 0.1);
    Lo.push(Math.min(open, close) - rnd() * rnd() * 1.1 - 0.1);
    Vo.push((0.2 + rnd() * 0.6) * (climax > 1 ? 1.4 : 1));
    p = close;
  }
  const mn = Math.min(...Lo);
  const span = Math.max(...Hi) - mn;
  const yOf = (v: number) => CY1 - 14 - ((v - mn) / span) * (CY1 - CY0 - 34);
  const slot = (CX1 - CX0) / N;
  const bw = slot * 0.58;
  const xOf = (i: number) => CX0 + (i + 0.5) * slot;

  let riseWick = "", riseBody = "", fallWick = "", fallBody = "", volRise = "", volFall = "";
  const vmax = Math.max(...Vo);
  for (let i = 0; i < N; i++) {
    const x = xOf(i);
    const top = yOf(Math.max(O[i], Cl[i]));
    const bh = Math.max(3, yOf(Math.min(O[i], Cl[i])) - top);
    const wick = `M${r1(x)},${r1(yOf(Hi[i]))}V${r1(yOf(Lo[i]))}`;
    const body = `M${r1(x - bw / 2)},${r1(top)}h${r1(bw)}v${r1(bh)}h${r1(-bw)}Z`;
    const vh = (Vo[i] / vmax) * (VY1 - VY0 - 6);
    const vol = `M${r1(x - bw / 2)},${VY1}v${r1(-vh)}h${r1(bw)}v${r1(vh)}Z`;
    if (Cl[i] >= O[i]) {
      riseWick += wick;
      riseBody += body;
      volRise += vol;
    } else {
      fallWick += wick;
      fallBody += body;
      volFall += vol;
    }
  }

  // 지수선 = 종가 EMA
  const pts: [number, number][] = [];
  let ema = Cl[0];
  for (let i = 0; i < N; i++) {
    ema = i === 0 ? Cl[0] : ema + 0.34 * (Cl[i] - ema);
    pts.push([xOf(i), yOf(ema)]);
  }
  const line = smooth(pts);
  const area = `${line}L${r1(pts[N - 1][0])},${CY1}L${r1(pts[0][0])},${CY1}Z`;

  let grid = "";
  for (let k = 0; k <= 6; k++) grid += `M${CX0},${r1(CY0 + (k * (CY1 - CY0)) / 6)}H${CX1}`;
  for (let k = 0; k <= N; k += 4) grid += `M${r1(CX0 + k * slot)},${CY0}V${VY1}`;
  grid += `M${CX0},${VY0}H${CX1}`;

  // 질감용 숫자(낮은 불투명도)
  const base = 6400 + Math.floor(rnd() * 1400) + rnd();
  const unit = 9 + rnd() * 7;
  const valOfY = (y: number) => base + (mn + ((CY1 - 14 - y) / (CY1 - CY0 - 34)) * span) * unit;
  const lastV = Cl[N - 1];
  const lastY = yOf(lastV);
  const lastX = xOf(N - 1);
  const lastLineY = pts[N - 1][1];
  const lastPrice = fmt2(base + lastV * unit);
  const chg = ((Cl[N - 1] - O[0]) * unit) / base;
  const chgTxt = `${chg >= 0 ? "+" : "−"}${Math.abs(chg * 100).toFixed(2)}%`;
  const times = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "15:30"];

  // ---------- 패널 이미지 한 장: 유리 → 네온 글로우(blur #2) → 선명한 차트 ----------
  const GW = PW + GM * 2;
  const GH = PH + GM * 2;
  const pDefs = tag("defs", {},
    tag("linearGradient", { id: "gl", x1: 0, y1: 0, x2: 0, y2: 1 }, tag("stop", { offset: 0, "stop-color": "#0D1834", "stop-opacity": 0.74 }) + tag("stop", { offset: 1, "stop-color": "#060C1C", "stop-opacity": 0.88 })) +
    tag("radialGradient", { id: "bl", cx: 0.58, cy: 0.48, r: 0.62 }, stops(pal.accent, [[0, 0.12], [1, 0]])) +
    tag("linearGradient", { id: "ar", x1: 0, y1: 0, x2: 0, y2: 1 }, stops(pal.accent, [[0, 0.32], [1, 0]])) +
    tag("linearGradient", { id: "sh", x1: 0, y1: 0, x2: 1, y2: 0.55 }, stops("#FFFFFF", [[0, 0.08], [0.24, 0.02], [0.38, 0]])) +
    tag("filter", { id: "g", x: -GM, y: -GM, width: GW, height: GH, filterUnits: "userSpaceOnUse", "color-interpolation-filters": "sRGB" },
      tag("feGaussianBlur", { stdDeviation: 11 }) + tag("feComponentTransfer", {}, tag("feFuncA", { type: "linear", slope: 1.8 }))),
  );
  let panel = "";
  panel += tag("rect", { x: 1, y: 1, width: PW - 2, height: PH - 2, rx: 26, fill: "url(#gl)" });
  panel += tag("rect", { x: 1, y: 1, width: PW - 2, height: PH - 2, rx: 26, fill: "url(#bl)" });
  panel += tag("g", { filter: "url(#g)", opacity: 0.85 },
    tag("rect", { x: -18, y: -18, width: PW + 36, height: PH + 36, rx: 40, fill: "none", stroke: pal.accent, "stroke-width": 44, opacity: 0.1 }) +
    tag("rect", { x: 0, y: 0, width: PW, height: PH, rx: 26, fill: "none", stroke: pal.accent, "stroke-width": 6, opacity: 0.45 }) +
    tag("path", { d: riseBody || "M0,0", fill: riseC, stroke: riseC, "stroke-width": 8 }) +
    (tone === "neutral" ? "" : tag("path", { d: fallBody || "M0,0", fill: fallC, stroke: fallC, "stroke-width": 8 })) +
    tag("path", { d: line, fill: "none", stroke: pal.light, "stroke-width": 16 }) +
    tag("circle", { cx: r1(lastX), cy: r1(lastLineY), r: 22, fill: "#FFFFFF" }));
  panel += tag("path", { d: grid, fill: "none", stroke: pal.light, "stroke-opacity": 0.09, "stroke-width": 1.2 });
  panel += tag("path", { d: area, fill: "url(#ar)" });
  panel += tag("path", { d: volRise || "M0,0", fill: riseC, opacity: 0.18 });
  panel += tag("path", { d: volFall || "M0,0", fill: fallC, opacity: 0.18 });
  panel += tag("path", { d: riseWick || "M0,0", stroke: riseC, "stroke-width": 2.4, opacity: 0.9 });
  panel += tag("path", { d: fallWick || "M0,0", stroke: fallC, "stroke-width": 2.4, opacity: 0.9 });
  panel += tag("path", { d: riseBody || "M0,0", fill: riseC });
  panel += tag("path", { d: fallBody || "M0,0", fill: fallC });
  panel += tag("path", { d: line, fill: "none", stroke: "#FFFFFF", "stroke-opacity": 0.92, "stroke-width": 3.2, "stroke-linecap": "round" });
  panel += tag("line", { x1: CX0, x2: CX1 + 8, y1: r1(lastY), y2: r1(lastY), stroke: pal.accent, "stroke-width": 1.8, "stroke-dasharray": "8 8", opacity: 0.6 });
  panel += tag("rect", { x: CX1 + 10, y: r1(lastY - 20), width: 138, height: 40, rx: 7, fill: pal.accent, opacity: 0.55 });
  let txt = "";
  txt += tag("text", { x: CX1 + 79, y: r1(lastY + 8), "text-anchor": "middle", "font-size": 22, "font-weight": 700, fill: "#FFFFFF", opacity: 0.42 }, lastPrice);
  for (let k = 0; k <= 6; k++) {
    const y = CY0 + (k * (CY1 - CY0)) / 6;
    txt += tag("text", { x: CX1 + 18, y: r1(y + 8), "font-size": 21, fill: pal.light, opacity: 0.26 }, fmt2(valOfY(y)));
  }
  times.forEach((s, k) => {
    txt += tag("text", { x: r1(CX0 + k * 4 * slot), y: VY1 + 34, "font-size": 20, "text-anchor": "middle", fill: pal.light, opacity: 0.26 }, s);
  });
  txt += tag("text", { x: CX0, y: 64, "font-size": 22, fill: pal.light, opacity: 0.3, "letter-spacing": 3 }, "INDEX · 5M");
  txt += tag("text", { x: CX0 + 196, y: 67, "font-size": 34, "font-weight": 700, fill: "#FFFFFF", opacity: 0.16 }, lastPrice);
  txt += tag("text", { x: CX0 + 410, y: 67, "font-size": 26, "font-weight": 700, fill: chg >= 0 ? riseC : fallC, opacity: 0.26 }, chgTxt);
  ["1D", "1W", "1M", "1Y"].forEach((s, i) => {
    txt += tag("text", { x: CX1 - 170 + i * 48, y: 64, "font-size": 20, fill: pal.light, opacity: i === 0 ? 0.5 : 0.2 }, s);
  });
  panel += tag("g", { "font-family": MONO }, txt);
  panel += tag("rect", { x: 1, y: 1, width: PW - 2, height: PH - 2, rx: 26, fill: "url(#sh)" });
  panel += tag("rect", { x: 1, y: 1, width: PW - 2, height: PH - 2, rx: 26, fill: "none", stroke: pal.light, "stroke-opacity": 0.3, "stroke-width": 2 });
  const panelSvg = svgDoc(GW, GH, pDefs + tag("g", { transform: `translate(${GM},${GM})` }, panel));

  // ================= 원경 이미지 (blur #1) =================
  const gauss = () => rnd() + rnd() + rnd() - 1.5;
  const pickC = () => {
    const u = rnd();
    return u < 0.34 ? 0 : u < 0.52 ? 1 : u < 0.8 ? 2 : u < 0.93 ? 3 : 4;
  };
  let farDefs = tag("filter", { id: "f", x: -80, y: 120, width: W + 160, height: H - 80, filterUnits: "userSpaceOnUse", "color-interpolation-filters": "sRGB" }, tag("feGaussianBlur", { stdDeviation: 5 }));
  for (const c of [0, 2, 3]) farDefs += tag("linearGradient", { id: `s${c}`, x1: 0, y1: 0, x2: 0, y2: 1 }, stops(pal.bokeh[c], [[0, 0], [0.38, 1], [0.75, 0.45], [1, 0]]));
  for (const c of [0, 2]) farDefs += tag("radialGradient", { id: `m${c}`, cx: 0.5, cy: 0.62, r: 0.5 }, stops(pal.bokeh[c], [[0, 1], [0.45, 0.35], [1, 0]]));

  // 넓은 빔(블러 없이도 부드러운 타원 그라데이션)
  let far = "";
  for (let i = 0; i < 6; i++) {
    const x = i < 2 ? -40 + rnd() * 160 : i < 4 ? 860 + rnd() * 200 : 260 + rnd() * 520;
    const top = i < 4 ? 520 + rnd() * 300 : 860 + rnd() * 120;
    const w = 80 + rnd() * 120;
    far += tag("rect", { x: r1(x - w / 2), y: r1(top), width: r1(w), height: r1(H - top + 200), fill: `url(#m${rnd() < 0.7 ? 0 : 2})`, opacity: r2(0.14 + rnd() * 0.1) });
  }
  let blurred = "";
  // 먼 보케(블러로 부드럽게)
  for (let i = 0; i < 24; i++) {
    blurred += tag("circle", { cx: r1(-40 + rnd() * (W + 80)), cy: r1(1085 + gauss() * 105), r: r1(9 + Math.pow(rnd(), 1.3) * 30), fill: pal.bokeh[pickC()], opacity: r2(0.22 + rnd() * 0.3) });
  }
  // 세로 빛줄기 코어 (가장자리 몇 줄은 위쪽까지 희미하게)
  for (let i = 0; i < 18; i++) {
    const edge = rnd() < 0.66;
    const tall = i < 4;
    const x = tall ? (i % 2 ? 930 + rnd() * 140 : 4 + rnd() * 90) : edge ? (rnd() < 0.45 ? -6 + rnd() * 200 : 870 + rnd() * 220) : 200 + rnd() * 680;
    const top = tall ? 160 + rnd() * 260 : edge ? 560 + rnd() * 420 : 900 + rnd() * 180;
    const w = 3 + rnd() * rnd() * 7;
    const c = rnd() < 0.55 ? 0 : rnd() < 0.6 ? 2 : 3;
    blurred += tag("rect", { x: r1(x), y: r1(top), width: r1(w), height: r1(H - top + 40), fill: `url(#s${c})`, opacity: r2(tall ? 0.14 + rnd() * 0.1 : 0.28 + rnd() * 0.36) });
  }
  // 먼 모니터 두 대
  for (const fp of [
    { x: 790, y: 760, w: 360, h: 230, rot: -4 },
    { x: -130, y: 900, w: 290, h: 180, rot: 5 },
  ]) {
    const lp: [number, number][] = [];
    let v = 0.5;
    for (let i = 0; i < 14; i++) {
      v += (rnd() - 0.5 + (sgn ? sgn * -0.1 : 0)) * 0.24;
      v = Math.max(0.1, Math.min(0.9, v));
      lp.push([fp.x + 24 + (i / 13) * (fp.w - 48), fp.y + 34 + v * (fp.h - 70)]);
    }
    let bars = "";
    for (let i = 0; i < 9; i++) {
      const hh = 6 + rnd() * 24;
      bars += `M${r1(fp.x + 28 + i * ((fp.w - 56) / 9))},${r1(fp.y + fp.h - 12)}v${r1(-hh)}h12v${r1(hh)}Z`;
    }
    blurred += tag("g", { transform: `rotate(${fp.rot} ${fp.x + fp.w / 2} ${fp.y + fp.h / 2})`, opacity: 0.5 },
      tag("rect", { x: fp.x, y: fp.y, width: fp.w, height: fp.h, rx: 10, fill: "#0A142C", "fill-opacity": 0.85, stroke: pal.light, "stroke-opacity": 0.4, "stroke-width": 2 }) +
      tag("path", { d: smooth(lp), fill: "none", stroke: pal.accent, "stroke-width": 4 }) +
      tag("path", { d: bars, fill: pal.light, opacity: 0.3 }));
  }
  // 흐린 숫자 질감
  const tickFmt = () => {
    const kind = rnd();
    if (kind < 0.45) return fmt2(500 + rnd() * 9000);
    if (kind < 0.75) return `${rnd() < 0.5 ? "+" : "−"}${(rnd() * 4).toFixed(2)}%`;
    return fmt2(10000 + rnd() * 40000);
  };
  let ticks = "";
  for (let i = 0; i < 14; i++) {
    const edge = i % 2 === 0;
    const x = edge ? (rnd() < 0.5 ? 16 + rnd() * 110 : 820 + rnd() * 170) : 180 + rnd() * 640;
    const y = edge ? 900 + rnd() * 300 : 990 + rnd() * 100;
    ticks += tag("text", { x: r1(x), y: r1(y), "font-size": r1(24 + rnd() * 20), fill: pal.bokeh[rnd() < 0.5 ? 1 : 3], opacity: r2(0.12 + rnd() * 0.14) }, tickFmt());
  }
  blurred += tag("g", { "font-family": MONO }, ticks);
  far += tag("g", { filter: "url(#f)" }, blurred);

  // ================= 보케 =================
  // 보케 원판 그라데이션 — 실제로 쓰인 색만 defs에 넣는다
  const bkDefs = (body: string) => pal.bokeh.map((c, k) => (body.includes(`url(#b${k})`) ? tag("radialGradient", { id: `b${k}` }, stops(c, [[0, 0.6], [0.62, 0.58], [0.84, 0.62], [1, 0]])) : "")).join("");
  const disc = (x: number, y: number, r: number, c: number, o: number, dy = 0) => tag("circle", { cx: r1(x), cy: r1(y - dy), r: r1(r), fill: `url(#b${c})`, opacity: r2(o) });
  // 수평선 띠의 보케·작은 점은 반짝이는 두 장(A/B)에, 나머지는 원경 이미지에 고정
  const tw = ["", ""];
  for (let i = 0; i < 16; i++) tw[i % 2] += disc(-30 + rnd() * (W + 60), 1092 + gauss() * 80, 7 + Math.pow(rnd(), 1.5) * 26, pickC(), 0.2 + rnd() * 0.28, TW_Y0);
  let still = "";
  for (let i = 0; i < 14; i++) {
    const left = rnd() < 0.42;
    const y = 600 + rnd() * 900;
    still += disc(left ? -30 + rnd() * 190 : 900 + rnd() * 210, y, 18 + rnd() * 38, pickC(), (0.08 + rnd() * 0.16) * (y < 1000 ? 0.7 : 1));
  }
  for (let i = 0; i < 12; i++) still += disc(rnd() * W, 1320 + rnd() * 600, 20 + rnd() * 40, pickC(), 0.12 + rnd() * 0.16);
  for (let i = 0; i < 2; i++) still += disc(960 + rnd() * 160, 300 + rnd() * 320, 30 + rnd() * 30, rnd() < 0.5 ? 0 : 3, 0.05 + rnd() * 0.04);
  for (let i = 0; i < 16; i++) {
    const band = rnd() < 0.6;
    const y = band ? 1060 + gauss() * 70 : 1300 + rnd() * 600;
    const dot = tag("circle", { cx: r1(rnd() * W), cy: r1(y - (band ? TW_Y0 : 0)), r: r1(1.4 + rnd() * 2.2), fill: pal.bokeh[rnd() < 0.5 ? 3 : rnd() < 0.5 ? 1 : 2], opacity: r2(0.5 + rnd() * 0.4) });
    if (band) tw[i % 2] += dot;
    else still += dot;
  }

  // ================= 원경 이미지 한 장: 하늘 그라데이션 + 헤이즈 + 빔 + 블러 요소 + 고정 보케 =================
  const ell = (id: string, cx: number, cy: number, rx: number, ry: number, c: string, list: [number, number][]) =>
    tag("radialGradient", { id, gradientUnits: "userSpaceOnUse", cx: 0, cy: 0, r: 1, gradientTransform: `translate(${r1(cx)} ${r1(cy)}) scale(${r1(rx)} ${r1(ry)})` }, stops(c, list));
  const skyDefs =
    tag("linearGradient", { id: "sky", gradientUnits: "userSpaceOnUse", x1: 0, y1: 0, x2: 0, y2: H }, tag("stop", { offset: 0, "stop-color": pal.base0 }) + tag("stop", { offset: 0.18, "stop-color": pal.base0 }) + tag("stop", { offset: 0.62, "stop-color": pal.base1 }) + tag("stop", { offset: 1, "stop-color": pal.base1 })) +
    ell("n1", W * 0.64, H * 0.4, W * 0.95, H * 0.36, "#182E64", [[0, 0.26], [0.7, 0]]) +
    ell("n2", W * 0.94, H * 0.14, W * 0.6, H * 0.26, pal.accent, [[0, 0.08], [0.7, 0]]) +
    ell("h1", W * 0.55, H * 0.56, W, H * 0.1, pal.accent, [[0, 0.18], [0.55, 0.055], [1, 0]]) +
    ell("h2", W * 0.68, H * 0.9, W * 0.85, H * 0.32, pal.accent, [[0, 0.22], [0.7, 0]]) +
    ell("h3", W * 0.1, H * 0.66, W * 0.5, H * 0.18, pal.bokeh[2], [[0, 0.055], [0.7, 0]]);
  const full = (fill: string) => tag("rect", { x: -BM, y: -BM, width: W + BM * 2, height: H + BM * 2, fill });
  const sky = full("url(#sky)") + full("url(#n1)") + full("url(#n2)") + full("url(#h1)") + full("url(#h2)") + full("url(#h3)");
  const baseSvg = svgDoc(W + BM * 2, H + BM * 2, tag("defs", {}, skyDefs + farDefs + bkDefs(still)) + tag("g", { transform: `translate(${BM},${BM})` }, sky + far + still));

  // 근경 큰 보케(CSS)
  const fg = [
    { x: 10, y: 1720, r: 170, c: 0, o: 0.2 },
    { x: 1060, y: 1560, r: 190, c: 2, o: 0.12 },
    { x: 900, y: 1880, r: 130, c: 1, o: 0.18 },
    { x: 1050, y: 1180, r: 80, c: 3, o: 0.08 },
    { x: 40, y: 1400, r: 96, c: 2, o: 0.1 },
    { x: 500, y: 1970, r: 150, c: 0, o: 0.14 },
  ].map((b) => ({ ...b, x: b.x + (rnd() - 0.5) * 60, y: b.y + (rnd() - 0.5) * 40 }));

  return {
    base: toUri(baseSvg),
    twinkle: tw.map((s) => toUri(svgDoc(W + BM * 2, TW_H, tag("defs", {}, bkDefs(s)) + tag("g", { transform: `translate(${BM},0)` }, s)))),
    panel: toUri(panelSvg),
    lastX,
    lastLineY,
    fg,
  };
}

/** 맨 위 덮개 한 장: 패널 앞 안개 + 비네트 + 상단 암부 + dim */
function buildOverlay(tone: Tone, dim: number) {
  const pal = PAL[tone];
  const ell = (id: string, cx: number, cy: number, rx: number, ry: number, c: string, list: [number, number][]) =>
    tag("radialGradient", { id, gradientUnits: "userSpaceOnUse", cx: 0, cy: 0, r: 1, gradientTransform: `translate(${r1(cx)} ${r1(cy)}) scale(${r1(rx)} ${r1(ry)})` }, stops(c, list));
  const lin = (id: string, c: string, list: [number, number][]) => tag("linearGradient", { id, gradientUnits: "userSpaceOnUse", x1: 0, y1: 0, x2: 0, y2: H }, stops(c, list));
  const defs =
    ell("fh", W * 0.45, H, W * 0.8, H * 0.16, pal.accent, [[0, 0.15], [0.6, 0.045], [1, 0]]) +
    lin("fb", "#030610", [[0, 0], [0.84, 0], [1, 0.35]]) +
    ell("vg", W * 0.55, H * 0.58, W * 0.92, H * 0.76, "#000000", [[0, 0], [0.4, 0], [0.72, 0.46], [1, 0.9]]) +
    ell("tl", W * 0.18, H * 0.22, W * 0.72, H * 0.36, "#000000", [[0, 0.32], [0.7, 0]]) +
    lin("td", "#010206", [[0, 0.5], [0.24, 0.34], [0.46, 0.12], [0.58, 0]]);
  let body = "";
  for (const k of ["fh", "fb", "vg", "tl", "td"]) body += tag("rect", { width: W, height: H, fill: `url(#${k})` });
  if (dim > 0) body += tag("rect", { width: W, height: H, fill: "#000000", opacity: r2(Math.min(1, dim)) });
  return toUri(svgDoc(W, H, tag("defs", {}, defs) + body));
}

/** 패널 로컬 점(u,v)을 CSS transform과 똑같이 화면 좌표로 투영 (플레어 위치용) */
function projectPt(u: number, v: number, tx: number, ty: number, ax: number, ay: number, az: number): [number, number] {
  const d = Math.PI / 180;
  let x = u - PW / 2;
  let y = v - PH / 2;
  let z = 0;
  const cz = Math.cos(az * d), sz = Math.sin(az * d);
  [x, y] = [x * cz - y * sz, x * sz + y * cz];
  const cy = Math.cos(ay * d), sy = Math.sin(ay * d);
  [x, z] = [x * cy + z * sy, -x * sy + z * cy];
  const cx = Math.cos(ax * d), sx = Math.sin(ax * d);
  [y, z] = [y * cx - z * sx, y * sx + z * cx];
  const s = PERSP / (PERSP - z);
  return [PL + PW / 2 + (x + tx) * s, PT + PH / 2 + (y + ty) * s];
}

/** data-URI 이미지가 디코드될 때까지 렌더를 잡아 둔다(첫 프레임에 빈 배경 방지) */
const usePreload = (uris: string[]) => {
  const key = uris.join("|");
  // 첫 렌더에서 바로 잡아 둔다 — effect가 돌기 전에 스크린샷이 찍히지 않도록
  const [first] = useState(() => delayRender("BgMarket images"));
  useEffect(() => {
    const h = delayRender("BgMarket images");
    continueRender(first);
    let alive = true;
    Promise.all(
      key.split("|").map((src) => {
        const im = new Image();
        im.src = src;
        return im.decode().catch(() => undefined);
      }),
    ).then(() => {
      if (alive) continueRender(h);
    });
    return () => {
      alive = false;
      continueRender(h);
    };
  }, [key, first]);
};

const layer = (uri: string): React.CSSProperties => ({ backgroundImage: `url("${uri}")`, backgroundSize: "100% 100%", backgroundRepeat: "no-repeat" });

export const BgMarket: React.FC<{ tone?: Tone; seed?: number; dim?: number }> = ({ tone = "neutral", seed = 1, dim = 0.15 }) => {
  const frame = useCurrentFrame();
  const pal = PAL[tone];
  const g = useMemo(() => build(tone, seed), [tone, seed]);
  const overlay = useMemo(() => buildOverlay(tone, dim), [tone, dim]);
  usePreload(useMemo(() => [g.base, ...g.twinkle, g.panel, overlay], [g, overlay]));

  // ---------- 움직임: transform·opacity만 (10~20초 주기, 이동 2~4%) ----------
  const t = frame / 30;
  const wv = (period: number, phase = 0) => Math.sin((t / period) * TAU + phase);
  const farT = `translate(${r1(24 * wv(13))}px,${r1(14 * wv(17, 1.3))}px)`;
  const bkT = `translate(${r1(34 * wv(11, 0.4))}px,${r1(12 * wv(15, 2.1))}px)`;
  const ptx = r1(16 * wv(12, 0.9));
  const pty = r1(12 * wv(16, 0.2));
  const pax = Math.round((11 + 1.2 * wv(14, 0.5)) * 1000) / 1000;
  const pay = Math.round((-24 + 2.2 * wv(12)) * 1000) / 1000;
  const paz = Math.round((3.5 + 0.4 * wv(18, 1.7)) * 1000) / 1000;
  const panelT = `perspective(${PERSP}px) translate3d(${ptx}px,${pty}px,0) rotateX(${pax}deg) rotateY(${pay}deg) rotateZ(${paz}deg)`;
  const [fx, fy] = projectPt(g.lastX, g.lastLineY, ptx, pty, pax, pay, paz);
  const fgT = `translate(${r1(48 * wv(10, 2.4))}px,${r1(-18 * wv(13, 0.8))}px)`;
  const glowO = r2(0.7 + 0.3 * (0.5 + 0.5 * wv(3.4)));
  const tw = [0, 1].map((k) => r2(0.55 + 0.45 * (0.5 + 0.5 * wv(4.2 + k * 1.7, k * 2.6))));
  const pulse = (frame % 54) / 54; // 1.8초 라이브 점 파동
  const sweep = ((frame % 330) / 330) * (PW + 700) - 450;
  const ring = 16 + pulse * 56;

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: pal.base0 }}>
      {/* 1) 원경 한 장: 하늘·헤이즈·빛줄기·흐린 숫자·먼 모니터·고정 보케 (패럴랙스 이동만) */}
      <div style={{ position: "absolute", left: -BM, top: -BM, width: W + BM * 2, height: H + BM * 2, transform: farT, ...layer(g.base) }} />

      {/* 2) 수평선 보케 띠 두 장 — 번갈아 반짝, 원경보다 조금 더 움직임 */}
      {g.twinkle.map((uri, k) => (
        <div key={k} style={{ position: "absolute", left: -BM, top: TW_Y0, width: W + BM * 2, height: TW_H, transform: bkT, opacity: tw[k], ...layer(uri) }} />
      ))}

      {/* 3) 중경: 기울어진 트레이딩 모니터 (유리+글로우+차트 한 장) */}
      <div style={{ position: "absolute", left: PL, top: PT, width: PW, height: PH, transform: panelT, transformOrigin: "50% 50%" }}>
        <div style={{ position: "absolute", left: -GM, top: -GM, width: PW + GM * 2, height: PH + GM * 2, ...layer(g.panel) }} />
        {/* 끝점 블룸 */}
        <div
          style={{
            position: "absolute",
            left: g.lastX - 240,
            top: g.lastLineY - 240,
            width: 480,
            height: 480,
            opacity: glowO,
            background: `radial-gradient(circle closest-side, ${rgba(pal.accent, 0.32)} 0%, ${rgba(pal.accent, 0.09)} 56%, transparent 100%)`,
          }}
        />
        {/* 라이브 점 파동 */}
        <div
          style={{
            position: "absolute",
            left: g.lastX - ring / 2,
            top: g.lastLineY - ring / 2,
            width: ring,
            height: ring,
            borderRadius: "50%",
            border: `2px solid ${rgba(pal.light, r2((1 - pulse) * 0.75))}`,
          }}
        />
        <div style={{ position: "absolute", left: g.lastX - 7, top: g.lastLineY - 7, width: 14, height: 14, borderRadius: "50%", background: "#FFFFFF" }} />
        {/* 윗 테두리 반사광 */}
        <div
          style={{
            position: "absolute",
            left: 40,
            right: 40,
            top: -1,
            height: 3,
            opacity: glowO,
            background: `linear-gradient(90deg, transparent, ${rgba(pal.light, 0.85)} 30%, rgba(255,255,255,0.9) 55%, ${rgba(pal.light, 0.6)} 75%, transparent)`,
          }}
        />
        {/* 느린 스캔 스윕 */}
        <div style={{ position: "absolute", inset: 0, borderRadius: 26, overflow: "hidden" }}>
          <div
            style={{
              position: "absolute",
              top: -40,
              bottom: -40,
              left: 0,
              width: 280,
              transform: `translateX(${r1(sweep)}px) skewX(-14deg)`,
              background: `linear-gradient(90deg, transparent, ${rgba(pal.light, 0.06)}, transparent)`,
            }}
          />
        </div>
      </div>

      {/* 4) 끝점 아나모픽 플레어 (화면 좌표 — 투영으로 끝점 추적) */}
      <div
        style={{
          position: "absolute",
          left: r1(fx - 460),
          top: r1(fy - 7),
          width: 920,
          height: 14,
          opacity: glowO,
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, rgba(255,255,255,0.75) 0%, ${rgba(pal.light, 0.4)} 22%, ${rgba(pal.accent, 0.12)} 55%, transparent 72%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: r1(fx - 150),
          top: r1(fy - 150),
          width: 300,
          height: 300,
          opacity: glowO,
          background: `radial-gradient(circle closest-side, rgba(255,255,255,0.28) 0%, ${rgba(pal.light, 0.14)} 20%, ${rgba(pal.accent, 0.06)} 58%, transparent 100%)`,
        }}
      />

      {/* 5) 근경 큰 보케 (빠른 패럴랙스 — 전체 화면 레이어 없이 원마다 이동) */}
      {g.fg.map((b, i) => {
        const c = pal.bokeh[b.c];
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: b.x - b.r,
              top: b.y - b.r,
              width: b.r * 2,
              height: b.r * 2,
              transform: fgT,
              background: `radial-gradient(circle closest-side, ${rgba(c, b.o * 0.5)} 0%, ${rgba(c, b.o * 0.8)} 76%, ${rgba(c, b.o)} 86%, ${rgba(c, b.o * 0.3)} 94%, ${rgba(c, 0)} 100%)`,
            }}
          />
        );
      })}

      {/* 6) 덮개 한 장: 패널 앞 안개 · 비네트 · 상단 암부 · dim */}
      <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, ...layer(overlay) }} />
    </AbsoluteFill>
  );
};
