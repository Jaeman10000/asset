/**
 * BgWallSt — 맨해튼·월가 야경 배경 (1080x1920). 미국 주간(일요일) 전용.
 * 원경: 청록 안개 빌딩 / 중경: 맨해튼 — 원 월드 트레이드 센터(첨탑), 엠파이어 스테이트(첨탑 + 삼색 조명),
 * 크라이슬러(아르데코 왕관) + 계단형 빌딩 / 왼쪽 앞: 브루클린 다리 탑·케이블 / 오른쪽: 전광판 띠(성조기 조각 + 시세 기호)
 * / 아래: 강물 반사(물결 왜곡) + 톤 색 차트 선(물에도 비친다).
 * 팔레트: 짙은 남색 + 따뜻한 금색 창문 + 청록 안개. 한국 배경(푸른 서울 야경)과 구분되게 금색·청록 위주.
 * 상단 55%(큰 글자 자리)는 옅은 별만. 프레임과 무관한 정적 그림 — public/bg/us_wallst_<tone>.jpg 로 한 번 굽는다(BakeUSEntry.tsx).
 */
import React, { useId, useMemo } from "react";
import { AbsoluteFill } from "remotion";

export type Tone = "up" | "down" | "neutral";

const W = 1080;
const H = 1920;
const WL = 1478; // 물가(수평선)
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

const PAL: Record<Tone, { a: string; lt: string }> = {
  up: { a: "#FF4D4D", lt: "#FFC6BC" },
  down: { a: "#3D7BFF", lt: "#C6D8FF" },
  neutral: { a: "#F2C66D", lt: "#FFEBC4" },
};
const GOLD = "#FFC873";
const TEAL = "#38D3C8";
const COOL = "#D6E8FF";

/* ───────── 계단형(아르데코) 빌딩 ───────── */
type Lv = { ins: number; y: number }; // 왼쪽에서 들여쓴 폭, 그 층의 윗면 y
type Bld = { x: number; w: number; lv: Lv[]; ant?: number };

function genRow(r: Rnd, o: { x0: number; x1: number; wMin: number; wMax: number; tMin: number; tMax: number; pSet: number; gap?: number }): Bld[] {
  const out: Bld[] = [];
  let x = o.x0;
  while (x < o.x1) {
    const w = lerp(o.wMin, o.wMax, r());
    const top = lerp(o.tMin, o.tMax, r() ** 1.3);
    const lv: Lv[] = [];
    const nSet = r() < o.pSet ? (r() < 0.45 ? 2 : 1) : 0;
    const total = nSet ? lerp(24, 70, r()) : 0;
    let y = top + total;
    lv.push({ ins: 0, y });
    let ins = 0;
    for (let k = 0; k < nSet; k++) {
      ins += w * lerp(0.1, 0.18, r());
      y -= total / nSet;
      lv.push({ ins, y });
    }
    out.push({ x, w, lv, ant: r() < 0.12 ? lerp(18, 46, r()) : undefined });
    x += w * (r() < 0.35 ? 0.7 : 1) + (o.gap ?? 0);
  }
  return out;
}

function bodyPath(b: Bld, base: number) {
  const { x, w, lv } = b;
  const X = x + w;
  const n = lv.length;
  const last = lv[n - 1];
  let d = `M${F(x)} ${base}V${F(lv[0].y)}`;
  for (let i = 1; i < n; i++) d += `H${F(x + lv[i].ins)}V${F(lv[i].y)}`;
  d += `H${F(X - last.ins)}`;
  for (let i = n - 2; i >= 0; i--) d += `V${F(lv[i].y)}H${F(X - lv[i].ins)}`;
  d += `V${base}Z`;
  if (b.ant) {
    const cx = x + w / 2;
    d += `M${F(cx - 1.4)} ${F(last.y + 1)}V${F(last.y - b.ant)}H${F(cx + 1.4)}V${F(last.y + 1)}Z`;
  }
  return d;
}

/** 창문: 켜진 층(가로 줄) + 드문 낱개. 밝기 버킷 3개 × 색 2개(금·흰). */
function windows(r: Rnd, b: Bld, base: number, cfg: { cw: number; ww: number; wh: number; fh: number; pRun: number; pIdle: number; yMax: number }, buckets: string[], budget: { n: number }) {
  const { lv } = b;
  for (let li = 0; li < lv.length; li++) {
    const x0 = b.x + lv[li].ins + 4;
    const x1 = b.x + b.w - lv[li].ins - 4;
    const yTop = lv[li].y + 5;
    const yBot = li === 0 ? Math.min(base, cfg.yMax) : lv[li - 1].y - 3;
    const cols = Math.floor((x1 - x0) / cfg.cw);
    if (cols < 1) continue;
    const warm = r() < 0.8;
    for (let y = yTop; y + cfg.wh < yBot; y += cfg.fh) {
      const run = r() < cfg.pRun;
      const len = 1 + Math.floor(r() * cols);
      const st = Math.floor(r() * (cols - len + 1));
      const lvl = r() < 0.55 ? 0 : r() < 0.7 ? 1 : 2;
      for (let c = 0; c < cols; c++) {
        const on = run && c >= st && c < st + len ? r() > 0.1 : r() < cfg.pIdle;
        if (!on || budget.n <= 0) continue;
        budget.n--;
        const k = (warm ? 0 : 3) + (run ? lvl : 0);
        buckets[k] += `M${F(x0 + c * cfg.cw)} ${F(y)}h${cfg.ww}v${cfg.wh}h${-cfg.ww}z`;
      }
    }
  }
}

/* ───────── 장면 기하(시드로 한 번) ───────── */
function makeScene(seed: number) {
  const r = rng(seed);
  // 원경: 청록 안개 속 낮은 빌딩
  const far = genRow(r, { x0: -30, x1: W + 30, wMin: 22, wMax: 62, tMin: 1262, tMax: 1402, pSet: 0.35 });
  const farD = far.map((b) => bodyPath(b, WL)).join("");
  let farWin = "";
  let fb = 900;
  for (const b of far) {
    const top = b.lv[0].y;
    for (let y = top + 6; y < WL - 4; y += 7)
      for (let x = b.x + 4; x < b.x + b.w - 4; x += 6) if (r() < 0.07 && fb-- > 0) farWin += `M${F(x)} ${F(y)}h2v2.2h-2z`;
  }
  // 중경 뒤: 맨해튼 계단형 빌딩
  const midB = genRow(r, { x0: -20, x1: W + 20, wMin: 44, wMax: 104, tMin: 1128, tMax: 1330, pSet: 0.55 });
  const midD = midB.map((b) => bodyPath(b, WL)).join("");
  const midWin = ["", "", "", "", "", ""];
  const mb = { n: 1500 };
  midB.forEach((b) => windows(r, b, WL, { cw: 8, ww: 4, wh: 5, fh: 11, pRun: 0.34, pIdle: 0.05, yMax: WL - 4 }, midWin, mb));
  const midSide = midB.map((b) => `M${F(b.x + b.w * 0.66)} ${WL}V${F(b.lv[0].y)}H${F(b.x + b.w)}V${WL}Z`).join("");
  // 중경 앞: 낮고 어두운 빌딩(아이콘 밑동을 가린다)
  const lowB = genRow(r, { x0: 150, x1: 720, wMin: 50, wMax: 120, tMin: 1340, tMax: 1432, pSet: 0.3 });
  const lowD = lowB.map((b) => bodyPath(b, WL + 2)).join("");
  const lowWin = ["", "", "", "", "", ""];
  const lb = { n: 700 };
  lowB.forEach((b) => windows(r, b, WL, { cw: 10, ww: 5, wh: 6, fh: 13, pRun: 0.3, pIdle: 0.04, yMax: WL - 3 }, lowWin, lb));

  // 엠파이어 스테이트: 세로 창 줄
  let esbWin = "";
  for (let x = 534; x < 648; x += 7) {
    for (let y = 1068; y < 1262; y += 6) if (r() < 0.36) esbWin += `M${x} ${y}h3v3.6h-3z`;
  }
  for (let x = 500; x < 682; x += 8) for (let y = 1308; y < WL - 30; y += 8) if (r() < 0.16) esbWin += `M${x} ${y}h3.4v4h-3.4z`;
  // 크라이슬러 몸통 창
  let chWin = "";
  for (let x = 748; x < 834; x += 6.5) for (let y = 1146; y < WL - 30; y += 7) if (r() < 0.22) chWin += `M${F(x)} ${y}h3v3.6h-3z`;
  // 원 WTC 유리면 옅은 층 빛
  let wtcWin = "";
  for (let y = 1000; y < 1352; y += 9) {
    const k = (y - 990) / 370;
    const half = lerp(32, 58, k) - 4;
    if (r() < 0.5) {
      const a = 360 - half + r() * half * 0.8;
      const len = 10 + r() * half * 0.9;
      wtcWin += `M${F(a)} ${y}h${F(len)}v1.6h${F(-len)}z`;
    }
  }

  // 브루클린 다리: 주케이블(3차 베지어) 표본 → 행어
  const P0: [number, number] = [197, 1158], C1: [number, number] = [322, 1336], C2: [number, number] = [512, 1422], P3: [number, number] = [664, 1432];
  const cub = (t: number) => {
    const u = 1 - t;
    return [u * u * u * P0[0] + 3 * u * u * t * C1[0] + 3 * u * t * t * C2[0] + t * t * t * P3[0], u * u * u * P0[1] + 3 * u * u * t * C1[1] + 3 * u * t * t * C2[1] + t * t * t * P3[1]];
  };
  const samp = Array.from({ length: 80 }, (_, i) => cub(i / 79));
  let hangers = "";
  for (let x = 206; x < 656; x += 13) {
    const j = samp.findIndex((p) => p[0] >= x);
    if (j <= 0) continue;
    const [xa, ya] = samp[j - 1];
    const [xb, yb] = samp[j];
    const y = ya + ((yb - ya) * (x - xa)) / (xb - xa || 1);
    if (y < 1428) hangers += `M${x} ${F(y)}V1432`;
  }
  let stays = "";
  for (let k = 0; k < 9; k++) stays += `M197 1166L${F(232 + k * 40)} 1432`;
  for (let k = 0; k < 5; k++) stays += `M18 1166L${F(-10 - k * 36)} 1432`;

  // 물 위 반짝임(밝은 빛 아래 세로 길)
  const glints: { d: string; op: number; col: string }[] = [];
  const addPath = (cx: number, spread: number, reach: number, col: string, amt: number) => {
    let d = "";
    for (let y = WL + 5; y < WL + reach; y += 6 + r() * 5) {
      const k = (y - WL) / reach;
      if (r() > amt * (1 - k * 0.6)) continue;
      const w = (4 + r() * 26) * (1 - k * 0.5);
      const x = cx + (r() - 0.5) * spread * (0.6 + k);
      d += `M${F(x - w / 2)} ${F(y)}h${F(w)}v1.6h${F(-w)}z`;
    }
    glints.push({ d, op: 0.6, col });
  };
  addPath(590, 40, 420, GOLD, 0.9); // 엠파이어
  addPath(790, 40, 420, "#FFF1D2", 0.9); // 크라이슬러
  addPath(360, 26, 300, TEAL, 0.6); // 원 WTC
  addPath(900, 80, 330, GOLD, 0.7); // 전광판
  addPath(430, 300, 260, GOLD, 0.7); // 다리 불빛
  // 잔물결 선
  let ripples = "";
  for (let i = 0; i < 150; i++) {
    const y = lerp(WL + 8, H, r() ** 1.6);
    const w = lerp(30, 220, r()) * (0.5 + (y - WL) / (H - WL));
    const x = r() * (W + 100) - 50;
    ripples += `M${F(x)} ${F(y)}h${F(w)}v${F(1 + (y - WL) / 260)}h${F(-w)}z`;
  }
  // 별(상단은 아주 옅게)
  const stars = Array.from({ length: 70 }, () => ({ x: r() * W, y: lerp(30, 1060, r() ** 0.9), rr: lerp(0.6, 1.7, r() ** 2), op: lerp(0.1, 0.42, r() ** 2) }));
  return { farD, farWin, midD, midWin, midSide, lowD, lowWin, esbWin, chWin, wtcWin, hangers, stays, glints, ripples, stars, samp };
}

/** 톤 차트 선: 추세(부드러운 S자) + 평균회귀 잡음(실제 가격선처럼) → 끝 두 구간에서 추세를 한 번 더 */
function makeChart(seed: number, tone: Tone) {
  const r = rng(seed * 17 + (tone === "up" ? 11 : tone === "down" ? 23 : 37));
  const N = 34;
  const x0 = -40;
  const x1 = 902;
  const [ya, yb] = tone === "up" ? [1412, 1124] : tone === "down" ? [1132, 1352] : [1292, 1276];
  const pts: [number, number][] = [];
  let e = 0;
  for (let i = 0; i < N; i++) {
    const k = i / (N - 1);
    const base = lerp(ya, yb, tone === "neutral" ? k : Math.pow(k, 1.15));
    e = 0.55 * e + (r() - 0.5) * (tone === "neutral" ? 46 : 40);
    const osc = tone === "neutral" ? Math.sin(k * Math.PI * 3.2) * 22 : 0;
    const edge = i === 0 || i === N - 1;
    pts.push([lerp(x0, x1, k), base + (edge ? 0 : e + osc)]);
  }
  const s = Math.sign(yb - ya) || -1;
  if (tone !== "neutral") {
    pts[N - 3][1] = yb - s * 34;
    pts[N - 2][1] = yb - s * 40;
  } else {
    pts[N - 3][1] = yb + 18;
    pts[N - 2][1] = yb + 6;
  }
  pts[N - 1][1] = yb;
  const line = "M" + pts.map((p) => `${F(p[0])} ${F(p[1])}`).join("L");
  const minY = Math.min(...pts.map((p) => p[1]));
  return { line, fill: `${line}L${x1} ${WL}L${x0} ${WL}Z`, end: pts[N - 1], minY };
}

/* 크라이슬러 왕관: 겹겹의 반원 아치 + 방사형 삼각 창 */
function chryslerCrown(cx: number, baseY: number) {
  let body = "";
  let rims = "";
  let tri = "";
  for (let i = 0; i < 6; i++) {
    const w = 84 - i * 12.6;
    const yb = baseY - i * 21;
    const rad = w / 2;
    const ys = yb - 10;
    body += `M${F(cx - rad)} ${F(yb + 2)}V${F(ys)}A${F(rad)} ${F(rad)} 0 0 1 ${F(cx + rad)} ${F(ys)}V${F(yb + 2)}Z`;
    rims += `M${F(cx - rad + 3)} ${F(ys)}A${F(rad - 3)} ${F(rad - 3)} 0 0 1 ${F(cx + rad - 3)} ${F(ys)}`;
    const n = Math.max(3, Math.round(7 - i * 0.7));
    for (let k = 0; k < n; k++) {
      const th = Math.PI * (0.1 + (0.8 * k) / (n - 1));
      const rr = rad - 9;
      const px = cx - Math.cos(th) * rr;
      const py = ys - Math.sin(th) * rr;
      const s = Math.max(2.4, 5.2 - i * 0.45);
      const ox = -Math.cos(th), oy = -Math.sin(th);
      const tx = -oy, ty = ox;
      tri += `M${F(px + ox * s * 1.4)} ${F(py + oy * s * 1.4)}L${F(px + tx * s * 0.8)} ${F(py + ty * s * 0.8)}L${F(px - tx * s * 0.8)} ${F(py - ty * s * 0.8)}Z`;
    }
  }
  const topY = baseY - 5 * 21 - 10 - (84 - 5 * 12.6) / 2;
  return { body, rims, tri, topY };
}

export const BgWallSt: React.FC<{ tone?: Tone; dim?: number; seed?: number }> = ({ tone = "neutral", dim = 0, seed = 11 }) => {
  const pal = PAL[tone] ?? PAL.neutral;
  const uid = "uws" + useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const id = (s: string) => `${uid}-${s}`;
  const u = (s: string) => `url(#${id(s)})`;
  const sc = useMemo(() => makeScene(seed), [seed]);
  const ch = useMemo(() => makeChart(seed, tone), [seed, tone]);
  const cr = useMemo(() => chryslerCrown(790, 1118), []);
  const [ex, ey] = ch.end;
  const winCol = [GOLD, GOLD, "#FFE2A8", COOL, COOL, "#FFFFFF"];
  const winOp = [0.34, 0.62, 0.92, 0.28, 0.5, 0.8];

  // 다리 탑(뾰족 아치 두 개를 뚫은 돌탑)
  const arch = (x0: number, x1: number) => {
    const xm = (x0 + x1) / 2;
    return `M${x0} 1447V1300Q${x0} 1262 ${xm} 1248Q${x1} 1262 ${x1} 1300V1447Z`;
  };
  const tower = `M18 ${WL + 12}V1152H196V${WL + 12}Z` + arch(42, 98) + arch(116, 172);

  const city = (
    <g>
      {/* 원경 */}
      <path d={sc.farD} fill={u("farF")} />
      <path d={sc.farWin} fill={COOL} opacity={0.22} />
      <rect x={0} y={1240} width={W} height={WL - 1240} fill={u("haze")} />
      {/* 중경 뒤 */}
      <path d={sc.midD} fill={u("midF")} />
      <path d={sc.midSide} fill="#000" opacity={0.3} />
      {sc.midWin.map((d, i) => <path key={i} d={d} fill={winCol[i]} opacity={winOp[i] * 0.85} />)}

      {/* 원 월드 트레이드 센터 */}
      <g>
        <rect x={302} y={1356} width={116} height={WL - 1356} fill="#07101E" />
        <path d="M302 1360L418 1360L392 992L328 992Z" fill={u("wtcC")} />
        <path d="M302 1360L360 1360L328 992Z" fill="#050C18" opacity={0.85} />
        <path d="M418 1360L360 1360L392 992Z" fill={u("wtcR")} />
        <path d="M302 1360L360 992L418 1360M328 992L360 1360L392 992" fill="none" stroke={TEAL} strokeOpacity={0.22} strokeWidth={1.2} />
        <path d={sc.wtcWin} fill="#BFF4EE" opacity={0.28} />
        <path d="M392 992L418 1360" stroke="#9FF0E6" strokeOpacity={0.5} strokeWidth={1.4} />
        <rect x={325} y={982} width={70} height={11} fill="#0A1424" />
        <rect x={351} y={958} width={18} height={25} fill="#0A1424" />
        <rect x={358.4} y={836} width={3.2} height={124} fill="#0E1A2E" />
        <path d="M354 930h12M355 902h10M356 874h8" stroke="#8FB7C8" strokeOpacity={0.35} strokeWidth={1.4} />
        <circle cx={360} cy={835} r={10} fill={u("tipR")} />
        <circle cx={360} cy={835} r={2.4} fill="#FF7A6E" />
      </g>

      {/* 엠파이어 스테이트 */}
      <g>
        <path d={`M495 ${WL}V1300H510V1270H528V1062H538V1046H547V1032H559V1010H567V994H574V980H580V952H584V942H588.5V880H591.5V942H596V952H600V980H606V994H613V1010H621V1032H633V1046H642V1062H652V1270H670V1300H685V${WL}Z`} fill={u("esbF")} />
        <path d={`M590 1062V1270H652V1062ZM590 1300V${WL}H685V1300Z`} fill="#000" opacity={0.28} />
        <path d={sc.esbWin} fill={GOLD} opacity={0.55} />
        {/* 삼색 조명(아래 파랑 · 가운데 흰 · 위 빨강) */}
        <ellipse cx={590} cy={1000} rx={70} ry={52} fill={u("crownGlow")} />
        <rect x={559} y={1010} width={62} height={22} fill={u("litB")} />
        <rect x={567} y={994} width={46} height={16} fill={u("litW")} />
        <rect x={574} y={980} width={32} height={14} fill={u("litR")} />
        <path d="M562 1014v15M570 1014v15M578 1014v15M586 1014v15M594 1014v15M602 1014v15M610 1014v15M618 1014v15" stroke="#0A1226" strokeOpacity={0.6} strokeWidth={1.6} />
        <path d="M571 997v11M579 997v11M587 997v11M595 997v11M603 997v11M611 997v11" stroke="#0A1226" strokeOpacity={0.5} strokeWidth={2} />
        <rect x={580} y={952} width={20} height={28} fill="#DCE6FF" opacity={0.22} />
        <circle cx={590} cy={880} r={9} fill={u("tipR")} />
        <circle cx={590} cy={880} r={2.2} fill="#FF7A6E" />
      </g>

      {/* 크라이슬러 */}
      <g>
        <path d={`M730 ${WL}V1300H742V1142H748V1118H832V1142H838V1300H850V${WL}Z`} fill={u("chF")} />
        <path d={`M790 1142V1300H838V1142ZM790 1300V${WL}H850V1300Z`} fill="#000" opacity={0.26} />
        <path d={sc.chWin} fill={GOLD} opacity={0.5} />
        <ellipse cx={790} cy={1060} rx={78} ry={70} fill={u("crownGlowW")} />
        <path d={cr.body} fill="#1A2233" />
        <path d={cr.body} fill={u("chCrown")} />
        <path d={cr.rims} fill="none" stroke="#FFF0CC" strokeOpacity={0.75} strokeWidth={1.6} />
        <path d={cr.tri} fill="#FFF4DA" opacity={0.92} />
        <path d={`M786.6 ${F(cr.topY + 2)}L789 ${F(cr.topY - 82)}H791L793.4 ${F(cr.topY + 2)}Z`} fill="#C9D2E0" opacity={0.9} />
        <path d="M748 1120l-16 -5 4 6zM832 1120l16 -5 -4 6z" fill="#8C97AB" opacity={0.7} />
      </g>

      {/* 오른쪽 유리 타워 */}
      <path d={`M944 ${WL}V1132L1100 1104V${WL}Z`} fill={u("glassF")} />
      <path d="M944 1132L1100 1104" stroke={TEAL} strokeOpacity={0.45} strokeWidth={1.4} />
      <path d={`M944 1132V${WL}`} stroke="#9FE9E0" strokeOpacity={0.35} strokeWidth={1.4} />
      <path d={Array.from({ length: 26 }, (_, i) => `M944 ${1150 + i * 13}L1100 ${1124 + i * 13}`).join("")} stroke="#8FD8FF" strokeOpacity={0.05} strokeWidth={1} />

      {/* 중경 앞: 낮은 빌딩 */}
      <path d={sc.lowD} fill={u("lowF")} />
      {sc.lowWin.map((d, i) => <path key={i} d={d} fill={winCol[i]} opacity={winOp[i] * 0.8} />)}

      {/* 전광판 빌딩(오른쪽) */}
      <path d={`M690 ${WL + 2}V1356H1100V${WL + 2}Z`} fill="#04070F" />
      <path d={Array.from({ length: 8 }, (_, i) => `M700 ${1402 + i * 10}h${380}`).join("")} stroke={GOLD} strokeOpacity={0.07} strokeWidth={4} strokeDasharray="5 5" />
      <rect x={690} y={1360} width={410} height={38} fill={GOLD} opacity={0.16} filter={u("blurS")} />
      <rect x={694} y={1366} width={406} height={24} fill="#03050A" />
      <path d="M694 1366H1100M694 1390H1100" stroke="#FFC27A" strokeOpacity={0.7} strokeWidth={1.2} />
      <g clipPath={u("flagC")}>
        {Array.from({ length: 7 }, (_, i) => <rect key={i} x={700} y={1366 + (24 / 7) * i} width={92} height={24 / 7 + 0.2} fill={i % 2 ? "#EFE8DA" : "#D8483F"} opacity={0.82} />)}
        <rect x={700} y={1366} width={38} height={13} fill="#22367A" />
        {Array.from({ length: 12 }, (_, i) => <circle key={i} cx={704 + (i % 6) * 6 + (Math.floor(i / 6) % 2) * 3} cy={1369.5 + Math.floor(i / 6) * 5.5} r={0.9} fill="#FFFFFF" opacity={0.9} />)}
      </g>
      <text x={804} y={1383} fontFamily="Consolas, 'DejaVu Sans Mono', monospace" fontSize={14.5} fontWeight={700} letterSpacing={1.6} fill="#FFD08A">
        {"S&P 500 · NASDAQ · DOW · RUSSELL 2000 · US 10Y · WTI · GOLD · DXY"}
      </text>

      {/* 브루클린 다리(왼쪽 앞) */}
      <path d={sc.stays} stroke="#AFC6D8" strokeOpacity={0.3} strokeWidth={1} />
      <path d={sc.hangers} stroke="#AFC6D8" strokeOpacity={0.22} strokeWidth={1} />
      <path d="M197 1158C322 1336 512 1422 664 1432" fill="none" stroke="#C9D8E6" strokeOpacity={0.55} strokeWidth={2.4} />
      <path d="M197 1166C318 1340 508 1426 664 1437" fill="none" stroke="#C9D8E6" strokeOpacity={0.3} strokeWidth={1.6} />
      <path d="M18 1158C-10 1230 -40 1300 -60 1340" fill="none" stroke="#C9D8E6" strokeOpacity={0.45} strokeWidth={2.4} />
      <path d={tower} fill={u("stone")} fillRule="evenodd" />
      {/* 기둥(버트레스) 세 줄 + 돌 줄눈 + 아치 테 */}
      <path d={`M18 1152H38V${WL}H18ZM96 1152H118V${WL}H96ZM176 1152H196V${WL}H176Z`} fill="#16263C" opacity={0.55} />
      <path d={Array.from({ length: 13 }, (_, i) => `M18 ${1172 + i * 24}H196`).join("")} stroke="#8DA2C0" strokeOpacity={0.07} strokeWidth={1} />
      <path d={arch(42, 98) + arch(116, 172)} fill="none" stroke={GOLD} strokeOpacity={0.34} strokeWidth={1.4} />
      <path d={`M18 1152V${WL}`} stroke={TEAL} strokeOpacity={0.55} strokeWidth={1.6} />
      <path d={`M196 1152V${WL}`} stroke={GOLD} strokeOpacity={0.5} strokeWidth={1.4} />
      <rect x={8} y={1138} width={198} height={14} fill="#0B1322" />
      <path d="M8 1138H206" stroke={GOLD} strokeOpacity={0.45} strokeWidth={1.2} />
      <rect x={22} y={1122} width={170} height={16} fill="#09101D" />
      <path d="M22 1122H192" stroke={TEAL} strokeOpacity={0.3} strokeWidth={1} />
      <circle cx={34} cy={1116} r={9} fill={u("lamp")} />
      <circle cx={180} cy={1116} r={9} fill={u("lamp")} />
      <rect x={-20} y={1432} width={700} height={14} fill="#060B16" />
      <path d="M-20 1432H680" stroke={GOLD} strokeOpacity={0.55} strokeWidth={1.2} />
      {Array.from({ length: 28 }, (_, i) => (
        <g key={i}>
          <circle cx={-8 + i * 24.5} cy={1438} r={7} fill={u("lamp")} />
          <circle cx={-8 + i * 24.5} cy={1438} r={1.6} fill="#FFE2AA" />
        </g>
      ))}

      {/* 차트: 면 + 번짐 + 선 (맨 앞, 물에도 비친다) */}
      <path d={ch.fill} fill={u("chartF")} mask={u("fillM")} />
      <path d={ch.line} fill="none" stroke={pal.a} strokeOpacity={0.07} strokeWidth={38} strokeLinejoin="round" strokeLinecap="round" />
      <path d={ch.line} fill="none" stroke={pal.a} strokeOpacity={0.7} strokeWidth={12} strokeLinejoin="round" strokeLinecap="round" filter={u("blurL")} />
      <path d={ch.line} fill="none" stroke={pal.a} strokeWidth={4.4} strokeLinejoin="round" strokeLinecap="round" />
      <path d={ch.line} fill="none" stroke={pal.lt} strokeOpacity={0.9} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <rect x={F(ex - 260)} y={F(ey - 1.4)} width={520} height={2.8} fill={u("flare")} opacity={0.75} />
      <circle cx={F(ex)} cy={F(ey)} r={50} fill={u("halo")} />
      <circle cx={F(ex)} cy={F(ey)} r={17} fill="none" stroke={pal.a} strokeOpacity={0.5} strokeWidth={2} />
      <circle cx={F(ex)} cy={F(ey)} r={6.4} fill="#FFFFFF" />
    </g>
  );

  return (
    <AbsoluteFill style={{ background: "#01030A", overflow: "hidden" }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id={id("sky")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#010208" />
            <stop offset="0.3" stopColor="#020612" />
            <stop offset="0.5" stopColor="#040C1F" />
            <stop offset="0.62" stopColor="#081834" />
            <stop offset="0.72" stopColor="#0D2445" />
            <stop offset="0.77" stopColor="#123150" />
            <stop offset="1" stopColor="#030710" />
          </linearGradient>
          <radialGradient id={id("dome")}>
            <stop offset="0" stopColor="#F0A64C" stopOpacity="0.44" />
            <stop offset="0.45" stopColor="#D98B3E" stopOpacity="0.12" />
            <stop offset="1" stopColor="#D98B3E" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("tealG")}>
            <stop offset="0" stopColor="#1FB5AE" stopOpacity="0.3" />
            <stop offset="1" stopColor="#1FB5AE" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("toneG")}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.26" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("farF")} gradientUnits="userSpaceOnUse" x1="0" y1="1260" x2="0" y2={WL}>
            <stop offset="0" stopColor="#12304A" />
            <stop offset="1" stopColor="#1A4058" />
          </linearGradient>
          <linearGradient id={id("haze")} gradientUnits="userSpaceOnUse" x1="0" y1="1240" x2="0" y2={WL}>
            <stop offset="0" stopColor="#2BA59E" stopOpacity="0" />
            <stop offset="0.7" stopColor="#2BA59E" stopOpacity="0.1" />
            <stop offset="1" stopColor="#E7A456" stopOpacity="0.16" />
          </linearGradient>
          <linearGradient id={id("midF")} gradientUnits="userSpaceOnUse" x1="0" y1="1120" x2="0" y2={WL}>
            <stop offset="0" stopColor="#060D1C" />
            <stop offset="1" stopColor="#0B1A30" />
          </linearGradient>
          <linearGradient id={id("lowF")} gradientUnits="userSpaceOnUse" x1="0" y1="1330" x2="0" y2={WL}>
            <stop offset="0" stopColor="#03070F" />
            <stop offset="1" stopColor="#060D1A" />
          </linearGradient>
          <linearGradient id={id("esbF")} gradientUnits="userSpaceOnUse" x1="0" y1="900" x2="0" y2={WL}>
            <stop offset="0" stopColor="#1B2740" />
            <stop offset="0.3" stopColor="#0B1426" />
            <stop offset="1" stopColor="#081120" />
          </linearGradient>
          <linearGradient id={id("chF")} gradientUnits="userSpaceOnUse" x1="0" y1="1100" x2="0" y2={WL}>
            <stop offset="0" stopColor="#0E1829" />
            <stop offset="1" stopColor="#07101E" />
          </linearGradient>
          <linearGradient id={id("chCrown")} gradientUnits="userSpaceOnUse" x1="740" y1="0" x2="840" y2="0">
            <stop offset="0" stopColor="#5E6A80" stopOpacity="0.55" />
            <stop offset="0.45" stopColor="#D8DEE8" stopOpacity="0.5" />
            <stop offset="1" stopColor="#3A4458" stopOpacity="0.5" />
          </linearGradient>
          <linearGradient id={id("wtcC")} gradientUnits="userSpaceOnUse" x1="0" y1="990" x2="0" y2="1360">
            <stop offset="0" stopColor="#1A4152" />
            <stop offset="0.5" stopColor="#0C2334" />
            <stop offset="1" stopColor="#091827" />
          </linearGradient>
          <linearGradient id={id("wtcR")} gradientUnits="userSpaceOnUse" x1="360" y1="0" x2="418" y2="0">
            <stop offset="0" stopColor="#15394A" />
            <stop offset="1" stopColor="#23596A" />
          </linearGradient>
          <linearGradient id={id("glassF")} gradientUnits="userSpaceOnUse" x1="944" y1="0" x2="1100" y2="0">
            <stop offset="0" stopColor="#123445" />
            <stop offset="0.12" stopColor="#0A1C2C" />
            <stop offset="1" stopColor="#040A14" />
          </linearGradient>
          <linearGradient id={id("stone")} gradientUnits="userSpaceOnUse" x1="18" y1="0" x2="196" y2="0">
            <stop offset="0" stopColor="#10243A" />
            <stop offset="0.5" stopColor="#0A1322" />
            <stop offset="1" stopColor="#161C2A" />
          </linearGradient>
          <radialGradient id={id("crownGlow")}>
            <stop offset="0" stopColor="#F5F0FF" stopOpacity="0.34" />
            <stop offset="0.5" stopColor="#8FA8FF" stopOpacity="0.12" />
            <stop offset="1" stopColor="#8FA8FF" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("crownGlowW")}>
            <stop offset="0" stopColor="#FFE6B0" stopOpacity="0.4" />
            <stop offset="0.5" stopColor="#FFC873" stopOpacity="0.12" />
            <stop offset="1" stopColor="#FFC873" stopOpacity="0" />
          </radialGradient>
          {([["litB", "#5A88F0"], ["litW", "#F6F2E8"], ["litR", "#EE5A4E"]] as const).map(([k, c]) => (
            <linearGradient key={k} id={id(k)} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0" stopColor={c} stopOpacity="0.62" />
              <stop offset="1" stopColor={c} stopOpacity="0.22" />
            </linearGradient>
          ))}
          <radialGradient id={id("tipR")}>
            <stop offset="0" stopColor="#FF6A5E" stopOpacity="0.75" />
            <stop offset="1" stopColor="#FF6A5E" stopOpacity="0" />
          </radialGradient>
          <radialGradient id={id("lamp")}>
            <stop offset="0" stopColor="#FFD58F" stopOpacity="0.7" />
            <stop offset="1" stopColor="#FFD58F" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("chartF")} gradientUnits="userSpaceOnUse" x1="0" y1={F(ch.minY)} x2="0" y2={F(ch.minY + 380)}>
            <stop offset="0" stopColor={pal.a} stopOpacity="0.34" />
            <stop offset="0.5" stopColor={pal.a} stopOpacity="0.08" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("hfade")} gradientUnits="userSpaceOnUse" x1={-40} y1="0" x2={902} y2="0">
            <stop offset="0" stopColor="#fff" stopOpacity="0" />
            <stop offset="0.15" stopColor="#fff" stopOpacity="1" />
            <stop offset="0.78" stopColor="#fff" stopOpacity="1" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id={id("fillM")} maskUnits="userSpaceOnUse" x={-100} y={0} width={W + 200} height={H}>
            <rect x={-100} y={0} width={W + 200} height={H} fill={u("hfade")} />
          </mask>
          <radialGradient id={id("halo")}>
            <stop offset="0" stopColor={pal.lt} stopOpacity="0.95" />
            <stop offset="0.22" stopColor={pal.a} stopOpacity="0.55" />
            <stop offset="1" stopColor={pal.a} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("flare")} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={pal.lt} stopOpacity="0" />
            <stop offset="0.5" stopColor={pal.lt} stopOpacity="0.7" />
            <stop offset="1" stopColor={pal.lt} stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("water")} gradientUnits="userSpaceOnUse" x1="0" y1={WL} x2="0" y2={H}>
            <stop offset="0" stopColor="#0C1E36" />
            <stop offset="0.35" stopColor="#060F1F" />
            <stop offset="1" stopColor="#020409" />
          </linearGradient>
          <linearGradient id={id("fadeG")} gradientUnits="userSpaceOnUse" x1="0" y1={WL} x2="0" y2={H}>
            <stop offset="0" stopColor="#fff" stopOpacity="0.8" />
            <stop offset="0.45" stopColor="#fff" stopOpacity="0.32" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id={id("fade")} maskUnits="userSpaceOnUse" x={0} y={WL} width={W} height={H - WL}>
            <rect x={0} y={WL} width={W} height={H - WL} fill={u("fadeG")} />
          </mask>
          <clipPath id={id("flagC")}>
            <rect x={700} y={1366} width={92} height={24} />
          </clipPath>
          <clipPath id={id("above")}>
            <rect x={-100} y={-100} width={W + 200} height={WL + 100} />
          </clipPath>
          <filter id={id("blurL")} filterUnits="userSpaceOnUse" x={-120} y={1000} width={W + 240} height={560}>
            <feGaussianBlur stdDeviation="10" />
          </filter>
          <filter id={id("blurS")} filterUnits="userSpaceOnUse" x={600} y={1320} width={560} height={120}>
            <feGaussianBlur stdDeviation="6" />
          </filter>
          <filter id={id("ripple")} filterUnits="userSpaceOnUse" x={-40} y={WL} width={W + 80} height={H - WL}>
            <feTurbulence type="fractalNoise" baseFrequency="0.006 0.11" numOctaves={2} seed={4} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={30} xChannelSelector="R" yChannelSelector="G" result="d" />
            <feGaussianBlur in="d" stdDeviation="1.4 3.2" />
          </filter>
          <filter id={id("soft")} filterUnits="userSpaceOnUse" x={0} y={WL} width={W} height={H - WL}>
            <feGaussianBlur stdDeviation="0.8 0.3" />
          </filter>
          <g id={id("city")}>{city}</g>
        </defs>

        {/* 하늘 */}
        <rect x={-20} y={-20} width={W + 40} height={H + 40} fill={u("sky")} />
        {sc.stars.map((s, i) => <circle key={i} cx={F(s.x)} cy={F(s.y)} r={s.rr} fill="#E8F0FF" opacity={s.op} />)}
        <ellipse cx={600} cy={1400} rx={820} ry={360} fill={u("dome")} />
        <ellipse cx={120} cy={1360} rx={520} ry={260} fill={u("tealG")} />
        <ellipse cx={980} cy={1250} rx={420} ry={260} fill={u("tealG")} opacity={0.6} />
        <ellipse cx={720} cy={1260} rx={560} ry={220} fill={u("toneG")} />

        {/* 도시 */}
        <g clipPath={u("above")}>
          <use href={`#${id("city")}`} />
        </g>

        {/* 물: 바탕 → 반사(물결 왜곡) → 반짝임 → 잔물결 */}
        <rect x={0} y={WL} width={W} height={H - WL} fill={u("water")} />
        <g mask={u("fade")}>
          <g filter={u("ripple")} opacity={0.56}>
            <use href={`#${id("city")}`} transform={`translate(0 ${2 * WL}) scale(1 -1)`} />
          </g>
        </g>
        <g filter={u("soft")}>
          {sc.glints.map((g, i) => <path key={i} d={g.d} fill={g.col} opacity={g.op} />)}
        </g>
        <path d={sc.ripples} fill="#01040B" opacity={0.45} />
        <rect x={0} y={WL - 1} width={W} height={2} fill="#FFD9A0" opacity={0.28} />
      </svg>

      {/* 비네트 · 상단 암부 · 감광 */}
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <radialGradient id={id("vig")} gradientUnits="userSpaceOnUse" cx={560} cy={1280} r={1200}>
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
            <stop offset="1" stopColor="#000" stopOpacity="0.45" />
          </linearGradient>
        </defs>
        <rect width={W} height={H} fill={u("vig")} />
        <rect width={W} height={H} fill={u("top")} />
        {dim > 0 && <rect width={W} height={H} fill="#000" opacity={Math.min(1, dim)} />}
      </svg>
    </AbsoluteFill>
  );
};

export default BgWallSt;
