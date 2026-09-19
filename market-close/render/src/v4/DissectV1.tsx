/** 기업 해부(이슈 해설) 화면 — JJ 2026-09-19 "썸네일은 기존 것과 아예 다르게, 모든 장면을 이미지 시각화 자료로 꽉 채워".
 * 국장 마감(어두운 야경·네온)과 한눈에 갈리게 밝은 종이 + 검은 글자 + 빨강(오름)·파랑(내림).
 * 장면마다 그림이 화면 대부분을 차지한다: 선 그래프·막대·맞대기·가로 막대·그림 개수·비중 띠·확인 목록.
 * 말과 맞추기: 그림 조각은 그 장면의 i번째 문장이 시작할 때 켜진다(at = 문장 번호). 질문 문장에선 질문만 크게.
 * 데이터는 대본 파일(data/<날짜>/info_script.json → info.cards)에서 받는다 — 여기서 숫자를 만들지 않는다. */
import React from "react";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import type { Props } from "../types";
import type { Cue } from "../Scenes";
import { FONT } from "../tokens";
import { usePop, useT } from "./ScenesV4";

export const PAPER = "#F3EFE7";
export const INK = "#141414";
export const SUB = "#5F5A53";
export const PRED = "#E0312B";
export const PBLUE = "#1F5BD8";
export const HL = "#FFD43B";
const GRID = "rgba(20,20,20,0.055)";
const FOOT = "자동 생성 · AI 음성 · 종목·매매 추천 아님";
const ease = Easing.bezier(0.2, 0.8, 0.2, 1);
const W = 952;

type SC = { p: Props; sub: string; cues?: Cue[] };
type Pt = { label?: string; v: number; vlabel?: string; est?: boolean; hl?: boolean; color?: "red" | "blue" | "ink" | "grey"; at?: number };
type Mark = { i: number; label: string; at?: number; color?: "red" | "blue" | "ink"; pos?: "top" | "bottom" };
export type DCard = {
  kind: "hook" | "line" | "bars" | "vs" | "hbars" | "picto" | "stack" | "big" | "check" | "split" | "q";
  head?: string; note?: string; note_at?: number; unit?: string;
  // hook
  tag?: string; name?: string; a?: { label: string; value: string; series: number[] }; b?: { label: string; value: string; bars: number[] }; q?: string[];
  // line
  series?: number[]; xlabels?: [string, string]; marks?: Mark[]; min?: number; max?: number;
  // bars / hbars
  bars?: Pt[]; rows?: Pt[];
  // vs
  left?: { label: string; from: string; to: string; fromLabel: string; toLabel: string; delta: string; dir: "up" | "down"; at?: number };
  right?: { label: string; from: string; to: string; fromLabel: string; toLabel: string; delta: string; dir: "up" | "down"; at?: number };
  // picto
  groups?: { label: string; n: number; at?: number }[]; icon?: "chip" | "server" | "won";
  // stack
  parts?: { label: string; v: number; sub?: string }[];
  // big
  big?: string; big_sub?: string; ratio?: { label: string; v: number; of: string };
  // check / split
  items?: { t: string; at?: number }[];
  up?: { title: string; t: string; at?: number }; down?: { title: string; t: string; at?: number };
};
type Info = { style?: string; cards?: Record<string, DCard> };

const C = (c?: string) => (c === "red" ? PRED : c === "blue" ? PBLUE : c === "grey" ? "#9A948B" : INK);
const infoOf = (p: Props) => ((p as unknown as { info?: Info }).info ?? {}) as Info;
const cueAt = (cues: Cue[] | undefined, i: number | undefined, fb: number) => (i === undefined ? fb : cues && cues[i] ? cues[i].start : fb + i * 2.4);
const prog = (t: number, a: number, d = 1.0) => interpolate(t, [a, a + d], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
const fitHead = (s: string) => (s.length <= 14 ? 76 : s.length <= 22 ? 66 : 58);
const qCue = (cues?: Cue[]) => (cues ?? []).find((x) => /\?$/.test(x.text.trim()));

/* ───────── 틀: 종이 바탕 · 머리 · 자막 상자 ───────── */
export const PaperShell: React.FC<{ p: Props; cues?: Cue[]; hideSub?: boolean; head?: string; children: React.ReactNode }> = ({ p, cues, hideSub, head, children }) => {
  const { t } = useT();
  const pop = usePop();
  const md = p.date_label.split(" ")[0];
  let sub = "";
  if (!hideSub && cues && cues.length) {
    const c = cues.find((x) => t >= x.start && t < x.end + 0.5);
    sub = c ? c.text : "";
  }
  return (
    <AbsoluteFill style={{ background: PAPER, fontFamily: FONT, color: INK, fontVariantNumeric: "tabular-nums" }}>
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${GRID} 2px, transparent 2px), linear-gradient(90deg, ${GRID} 2px, transparent 2px)`, backgroundSize: "54px 54px" }} />
      <div style={{ position: "absolute", left: 64, top: 64 }}>
        <div style={{ fontSize: 50, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1 }}>누가샀나</div>
        <div style={{ height: 8, width: 176, background: PRED, borderRadius: 4, marginTop: 8 }} />
      </div>
      <div style={{ position: "absolute", right: 64, top: 62, display: "flex", gap: 14, alignItems: "center" }}>
        <div style={{ fontSize: 34, fontWeight: 900, color: "#FFFFFF", background: INK, padding: "10px 22px", borderRadius: 12 }}>기업 해부</div>
        <div style={{ fontSize: 38, fontWeight: 800, color: SUB }}>{md}</div>
      </div>
      {head ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 196, fontSize: fitHead(head), fontWeight: 900, lineHeight: 1.16, letterSpacing: "-0.035em", wordBreak: "keep-all", ...pop(0, 14) }}>{head}</div>
      ) : null}
      {children}
      {sub ? (
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 300, display: "flex", justifyContent: "center" }}>
          <div style={{ background: "rgba(20,20,20,0.93)", color: "#FFFFFF", fontSize: 42, fontWeight: 700, lineHeight: 1.38, padding: "16px 28px", borderRadius: 18, wordBreak: "keep-all", textAlign: "center" }}>{sub}</div>
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 52, fontSize: 26, color: "rgba(20,20,20,0.45)" }}>{FOOT}</div>
    </AbsoluteFill>
  );
};

/** 질문 문장이 시작되면 그림을 흐리게 깔고 질문만 크게 */
const QOverlay: React.FC<{ cues?: Cue[]; lines?: string[] }> = ({ cues, lines }) => {
  const { t } = useT();
  const q = qCue(cues);
  if (!q || t < q.start) return null;
  const k = prog(t, q.start, 0.35);
  const text = lines && lines.length ? lines : [q.text.trim()];
  return (
    <AbsoluteFill style={{ background: `rgba(243,239,231,${0.9 * k})` }}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 640, opacity: k, transform: `translateY(${(1 - k) * 30}px)` }}>
        {text.map((l, i) => (
          <div key={i} style={{ fontSize: 104, fontWeight: 900, lineHeight: 1.16, letterSpacing: "-0.045em", wordBreak: "keep-all", color: i === text.length - 1 ? PRED : INK }}>{l}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ───────── 그림 조각 ───────── */
const SvgLine: React.FC<{ series: number[]; w: number; h: number; color: string; k: number; min?: number; max?: number; stroke?: number; area?: boolean }> = ({ series, w, h, color, k, min, max, stroke = 9, area }) => {
  const n = series.length;
  const lo = min ?? Math.min(...series), hi = max ?? Math.max(...series);
  const X = (i: number) => (i / Math.max(1, n - 1)) * w;
  const Y = (v: number) => h - ((v - lo) / Math.max(1e-9, hi - lo)) * h * 0.9 - h * 0.05;
  const upto = Math.max(1, k * (n - 1));
  const pts: string[] = [];
  for (let i = 0; i <= Math.floor(upto); i++) pts.push(`${X(i)},${Y(series[i])}`);
  const fr = upto - Math.floor(upto);
  if (fr > 0 && Math.floor(upto) + 1 < n) {
    const i = Math.floor(upto);
    pts.push(`${X(i) + (X(i + 1) - X(i)) * fr},${Y(series[i]) + (Y(series[i + 1]) - Y(series[i])) * fr}`);
  }
  const last = pts[pts.length - 1].split(",").map(Number);
  return (
    <g>
      {area ? <polygon points={`0,${h} ${pts.join(" ")} ${last[0]},${h}`} fill={color} opacity={0.1} /> : null}
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={stroke + 5} fill={color} />
    </g>
  );
};

const Arrow: React.FC<{ dir: "up" | "down"; color: string; size?: number }> = ({ dir, color, size = 80 }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ display: "block" }}>
    <path d={dir === "up" ? "M50 8 L92 58 L64 58 L64 94 L36 94 L36 58 L8 58 Z" : "M50 92 L92 42 L64 42 L64 6 L36 6 L36 42 L8 42 Z"} fill={color} />
  </svg>
);

const Chip: React.FC<{ size: number; color: string }> = ({ size, color }) => (
  <svg width={size} height={size} viewBox="0 0 100 100">
    {[20, 40, 60, 80].map((x) => (
      <g key={x}>
        <rect x={x - 4} y={2} width={8} height={14} rx={2} fill={color} />
        <rect x={x - 4} y={84} width={8} height={14} rx={2} fill={color} />
        <rect x={2} y={x - 4} width={14} height={8} rx={2} fill={color} />
        <rect x={84} y={x - 4} width={14} height={8} rx={2} fill={color} />
      </g>
    ))}
    <rect x={14} y={14} width={72} height={72} rx={10} fill={color} />
    <rect x={32} y={32} width={36} height={36} rx={5} fill={PAPER} opacity={0.9} />
  </svg>
);

/* ───────── 장면 카드 ───────── */
/** 훅: 0초부터 회사 이름 + 두 그림이 맞선다(주가 선은 내려가고 이익 막대는 올라간다) → 질문 */
const Hook: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const a = c.a!, b = c.b!;
  const k = Math.min(1, 0.35 + t / 1.6);
  const mb = Math.max(...b.bars);
  return (
    <PaperShell p={p} cues={cues} hideSub>
      <div style={{ position: "absolute", left: 64, right: 64, top: 200 }}>
        {c.tag ? <div style={{ display: "inline-block", fontSize: 40, fontWeight: 900, background: HL, padding: "6px 18px", borderRadius: 8 }}>{c.tag}</div> : null}
        <div style={{ fontSize: 150, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.05, marginTop: 14 }}>{c.name}</div>
      </div>
      <div style={{ position: "absolute", left: 64, width: W, top: 560, height: 860, display: "flex", gap: 36 }}>
        <div style={{ flex: 1, background: "#FFFFFF", borderRadius: 28, padding: 28, boxShadow: "0 8px 30px rgba(0,0,0,0.08)", position: "relative" }}>
          <div style={{ fontSize: 46, fontWeight: 900, color: SUB }}>{a.label}</div>
          <div style={{ fontSize: 108, fontWeight: 900, color: PBLUE, letterSpacing: "-0.04em", lineHeight: 1.1 }}>{a.value}</div>
          <svg width={402} height={520} style={{ position: "absolute", left: 28, bottom: 30, overflow: "visible" }}>
            <SvgLine series={a.series} w={402} h={520} color={PBLUE} k={k} area />
          </svg>
        </div>
        <div style={{ flex: 1, background: "#FFFFFF", borderRadius: 28, padding: 28, boxShadow: "0 8px 30px rgba(0,0,0,0.08)", position: "relative" }}>
          <div style={{ fontSize: 46, fontWeight: 900, color: SUB }}>{b.label}</div>
          <div style={{ fontSize: 108, fontWeight: 900, color: PRED, letterSpacing: "-0.04em", lineHeight: 1.1 }}>{b.value}</div>
          <div style={{ position: "absolute", left: 28, right: 28, bottom: 30, height: 520, display: "flex", alignItems: "flex-end", gap: 16 }}>
            {b.bars.map((v, i) => (
              <div key={i} style={{ flex: 1, height: `${(v / mb) * 100 * Math.min(1, Math.max(0, k * b.bars.length - i + 0.6))}%`, background: i === b.bars.length - 1 ? PRED : "rgba(224,49,43,0.45)", borderRadius: "10px 10px 0 0" }} />
            ))}
          </div>
        </div>
      </div>
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};

/** 선 그래프 — 그려지면서, 표시점은 해당 문장에 켜진다 */
const Line: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const s = c.series ?? [];
  const H = 820, top = 480;
  const k = prog(t, 0.1, 2.2);
  const lo = c.min ?? Math.min(...s), hi = c.max ?? Math.max(...s);
  const X = (i: number) => (i / Math.max(1, s.length - 1)) * W;
  const Y = (v: number) => H - ((v - lo) / Math.max(1e-9, hi - lo)) * H * 0.9 - H * 0.05;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <svg width={W} height={H + 80} style={{ position: "absolute", left: 64, top, overflow: "visible" }}>
        {[0.25, 0.5, 0.75].map((g) => <line key={g} x1={0} x2={W} y1={H * g} y2={H * g} stroke="rgba(20,20,20,0.12)" strokeWidth={2} strokeDasharray="8 10" />)}
        <line x1={0} x2={W} y1={H} y2={H} stroke={INK} strokeWidth={3} />
        <SvgLine series={s} w={W} h={H} color={INK} k={k} min={lo} max={hi} stroke={7} area />
        {(c.marks ?? []).map((m, j) => {
          const at = cueAt(cues, m.at, 0.6 + j * 1.2);
          const on = prog(t, at, 0.4);
          const x = X(m.i), y = Y(s[m.i]);
          const anchor = x > W * 0.72 ? "end" : x < W * 0.22 ? "start" : "middle";
          const ly = m.pos === "bottom" ? y + 78 : y - 36;
          return (
            <g key={j} opacity={on}>
              <circle cx={x} cy={y} r={16} fill={C(m.color)} stroke={PAPER} strokeWidth={6} />
              <text x={x} y={ly} textAnchor={anchor} fontSize={48} fontWeight={900} fill={C(m.color)} stroke={PAPER} strokeWidth={12} paintOrder="stroke" fontFamily={FONT}>{m.label}</text>
            </g>
          );
        })}
        {c.xlabels ? (
          <>
            <text x={0} y={H + 56} fontSize={34} fontWeight={700} fill={SUB} fontFamily={FONT}>{c.xlabels[0]}</text>
            <text x={W} y={H + 56} textAnchor="end" fontSize={34} fontWeight={700} fill={SUB} fontFamily={FONT}>{c.xlabels[1]}</text>
          </>
        ) : null}
      </svg>
      {c.note ? <Note c={c} cues={cues} top={top + H + 90} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

const Note: React.FC<{ c: DCard; cues?: Cue[]; top: number }> = ({ c, cues, top }) => {
  const pop = usePop();
  const at = cueAt(cues, c.note_at, 2.5);
  return (
    <div style={{ position: "absolute", left: 64, right: 64, top, ...pop(at, 14) }}>
      <span style={{ fontSize: 52, fontWeight: 900, lineHeight: 1.35, background: `linear-gradient(transparent 55%, ${HL} 55%)`, wordBreak: "keep-all" }}>{c.note}</span>
    </div>
  );
};

/** 세로 막대 — 분기 이익 등. est=전망(빗금), hl=강조 */
const Bars: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const bars = c.bars ?? [];
  const H = 700, top = 520;
  const mx = Math.max(1e-9, ...bars.map((b) => Math.abs(b.v)));
  const n = bars.length, gap = 22, bw = (W - gap * (n - 1)) / n;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <svg width={W} height={H + 90} style={{ position: "absolute", left: 64, top, overflow: "visible" }}>
        <defs>
          <pattern id="hatch" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="18" height="18" fill="rgba(224,49,43,0.18)" />
            <line x1="0" y1="0" x2="0" y2="18" stroke={PRED} strokeWidth="8" />
          </pattern>
        </defs>
        <line x1={0} x2={W} y1={H} y2={H} stroke={INK} strokeWidth={3} />
        {bars.map((b, i) => {
          const at = cueAt(cues, b.at, 0.1 + i * 0.25);
          const g = prog(t, at, 0.7);
          const h = (Math.abs(b.v) / mx) * H * 0.86 * g;
          const x = i * (bw + gap);
          const col = b.color ? C(b.color) : b.hl || b.est ? PRED : "#B9B2A7";
          return (
            <g key={i}>
              <rect x={x} y={H - h} width={bw} height={h} rx={10} fill={b.est ? "url(#hatch)" : col} stroke={b.est ? PRED : "none"} strokeWidth={b.est ? 5 : 0} />
              <text x={x + bw / 2} y={H - h - 18} textAnchor="middle" fontSize={bw > 150 ? 46 : 38} fontWeight={900} fill={b.hl || b.est ? PRED : INK} opacity={g} fontFamily={FONT}>{b.vlabel ?? b.v}</text>
              <text x={x + bw / 2} y={H + 50} textAnchor="middle" fontSize={bw > 150 ? 38 : 32} fontWeight={800} fill={SUB} fontFamily={FONT}>{b.label}</text>
              {b.est ? <text x={x + bw / 2} y={H + 86} textAnchor="middle" fontSize={30} fontWeight={900} fill={PRED} fontFamily={FONT}>추정</text> : null}
            </g>
          );
        })}
      </svg>
      {c.note ? <Note c={c} cues={cues} top={top + H + 110} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 맞대기 — 같은 석 달, 한쪽은 오르고 한쪽은 내렸다(작은 기울기 그림 + 큰 증감) */
const Vs: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const Panel: React.FC<{ d: NonNullable<DCard["left"]>; top: number; fb: number }> = ({ d, top, fb }) => {
    const at = cueAt(cues, d.at, fb);
    const k = prog(t, at, 0.9);
    const col = d.dir === "up" ? PRED : PBLUE;
    const x0 = 30, x1 = 640, hi = 20, lo = 190;
    const y0 = d.dir === "up" ? lo : hi, y1 = d.dir === "up" ? hi : lo;
    const xe = x0 + (x1 - x0) * k, ye = y0 + (y1 - y0) * k;
    return (
      <div style={{ position: "absolute", left: 64, width: W, top, height: 470, background: "#FFFFFF", borderRadius: 28, boxShadow: "0 8px 30px rgba(0,0,0,0.08)", opacity: Math.min(1, 0.25 + k * 1.5) }}>
        <div style={{ position: "absolute", left: 34, top: 26, fontSize: 44, fontWeight: 900, color: SUB, wordBreak: "keep-all", maxWidth: 560 }}>{d.label}</div>
        <div style={{ position: "absolute", right: 34, top: 14, display: "flex", alignItems: "center", gap: 8, opacity: k }}>
          <Arrow dir={d.dir} color={col} size={84} />
          <div style={{ fontSize: 100, fontWeight: 900, color: col, letterSpacing: "-0.04em", lineHeight: 1 }}>{d.delta}</div>
        </div>
        <svg width={880} height={300} style={{ position: "absolute", left: 34, top: 150, overflow: "visible" }}>
          <line x1={x0} x2={x1} y1={lo + 84} y2={lo + 84} stroke="rgba(20,20,20,0.25)" strokeWidth={3} />
          <line x1={x0} y1={y0} x2={xe} y2={ye} stroke={col} strokeWidth={12} strokeLinecap="round" />
          <circle cx={x0} cy={y0} r={16} fill="#9A948B" />
          <circle cx={xe} cy={ye} r={20} fill={col} />
          <text x={x0 + 26} y={y0 + 60} fontSize={46} fontWeight={900} fill={INK} fontFamily={FONT}>{d.from}</text>
          <text x={x1 + 32} y={y1 + 16} fontSize={50} fontWeight={900} fill={col} opacity={k} fontFamily={FONT}>{d.to}</text>
          <text x={x0} y={lo + 124} fontSize={32} fontWeight={800} fill={SUB} fontFamily={FONT}>{d.fromLabel}</text>
          <text x={x1} y={lo + 124} textAnchor="middle" fontSize={32} fontWeight={800} fill={SUB} opacity={k} fontFamily={FONT}>{d.toLabel}</text>
        </svg>
      </div>
    );
  };
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      {c.left ? <Panel d={c.left} top={460} fb={0.1} /> : null}
      {c.right ? <Panel d={c.right} top={960} fb={2.4} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 가로 막대 — 위 줄에 이름 + 값, 아래에 막대. 부호가 섞이면 0을 가운데(+ 빨강 오른쪽, − 파랑 왼쪽), 한쪽뿐이면 왼쪽부터 크기만 */
const HBars: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const rows = c.rows ?? [];
  const mixed = rows.some((r) => r.v < 0) && rows.some((r) => r.v > 0);
  const mx = Math.max(1e-9, ...rows.map((r) => Math.abs(r.v)));
  const top = 470, rh = Math.min(190, 880 / Math.max(1, rows.length));
  const zero = mixed ? W / 2 : 0;
  const span = (mixed ? W / 2 : W) - 12;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top, height: rh * rows.length }}>
        {mixed ? <div style={{ position: "absolute", left: zero - 2, top: 0, width: 4, height: rh * rows.length, background: INK }} /> : null}
        {rows.map((r, i) => {
          const at = cueAt(cues, r.at, 0.1 + i * 0.35);
          const g = prog(t, at, 0.7);
          const w = (Math.abs(r.v) / mx) * span * g;
          const col = r.color ? C(r.color) : r.v >= 0 ? PRED : PBLUE;
          const bt = rh * 0.44, bh = rh * 0.42;
          const side = mixed ? (r.v >= 0 ? { left: zero + 16 } : { right: W - zero + 16 }) : { left: 0 };
          return (
            <div key={i} style={{ position: "absolute", left: 0, top: i * rh, width: W, height: rh, opacity: Math.min(1, 0.2 + g * 2) }}>
              <div style={{ position: "absolute", top: 0, display: "flex", alignItems: "baseline", gap: 18, whiteSpace: "nowrap", ...side }}>
                <span style={{ fontSize: r.hl ? 46 : 40, fontWeight: 900, background: r.hl ? `linear-gradient(transparent 55%, ${HL} 55%)` : "none" }}>{r.label}</span>
                <span style={{ fontSize: 50, fontWeight: 900, color: col }}>{r.vlabel ?? r.v}</span>
              </div>
              <div style={{ position: "absolute", top: bt, height: bh, left: mixed && r.v < 0 ? zero - w : zero, width: w, background: col, borderRadius: 10, opacity: r.hl ? 1 : 0.8 }} />
            </div>
          );
        })}
      </div>
      {c.note ? <Note c={c} cues={cues} top={top + rh * rows.length + 30} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 그림 개수 — 일반 서버 1 : AI 서버 10 같은 배수 */
const Picto: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const groups = c.groups ?? [];
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top: 480, display: "flex", flexDirection: "column", gap: 40 }}>
        {groups.map((g, gi) => {
          const at = cueAt(cues, g.at, 0.1 + gi * 1.6);
          return (
            <div key={gi} style={{ background: "#FFFFFF", borderRadius: 28, padding: "26px 30px", boxShadow: "0 8px 30px rgba(0,0,0,0.08)", opacity: t >= at - 0.05 ? 1 : 0.25 }}>
              <div style={{ fontSize: 48, fontWeight: 900, color: gi === groups.length - 1 ? PRED : SUB }}>{g.label}</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 16 }}>
                {Array.from({ length: g.n }).map((_, i) => {
                  const k = prog(t, at + i * 0.12, 0.3);
                  return <div key={i} style={{ transform: `scale(${0.4 + 0.6 * k})`, opacity: k }}><Chip size={150} color={gi === groups.length - 1 ? PRED : "#9A948B"} /></div>;
                })}
              </div>
            </div>
          );
        })}
      </div>
      {c.note ? <Note c={c} cues={cues} top={1340} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 비중 띠 — 무엇으로 돈을 버나(사업부 매출 비중) */
const Stack: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const parts = c.parts ?? [];
  const tot = parts.reduce((a, b) => a + b.v, 0) || 1;
  const cols = [PRED, INK, "#9A948B", PBLUE];
  const k = prog(t, 0.1, 1.2);
  let acc = 0;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top: 480, height: 200, borderRadius: 24, overflow: "hidden", display: "flex", background: "#E3DDD2" }}>
        {parts.map((s, i) => <div key={i} style={{ width: `${(s.v / tot) * 100 * k}%`, background: cols[i % cols.length] }} />)}
      </div>
      <div style={{ position: "absolute", left: 64, width: W, top: 740, display: "flex", flexDirection: "column", gap: 34 }}>
        {parts.map((s, i) => {
          acc += s.v;
          const at = cueAt(cues, i === 0 ? 0 : undefined, 0.4 + i * 0.4);
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 24, opacity: prog(t, at, 0.4) }}>
              <div style={{ width: 64, height: 64, borderRadius: 14, background: cols[i % cols.length], flex: "0 0 auto" }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 60, fontWeight: 900, lineHeight: 1.1 }}>{s.label} <span style={{ color: cols[i % cols.length] === INK ? INK : cols[i % cols.length] }}>{Math.round((s.v / tot) * 100)}%</span></div>
                {s.sub ? <div style={{ fontSize: 42, fontWeight: 700, color: SUB, marginTop: 4 }}>{s.sub}</div> : null}
              </div>
            </div>
          );
        })}
      </div>
      {c.note ? <Note c={c} cues={cues} top={1340} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 큰 숫자 + 무엇에 비해 얼마나 큰지 띠 */
const Big: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const pop = usePop();
  const r = c.ratio;
  const at = cueAt(cues, 1, 2.4);
  const k = prog(t, at, 1.0);
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 520, ...pop(0.05, 20) }}>
        <div style={{ fontSize: 170, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1, color: PRED }}>{c.big}</div>
        {c.big_sub ? <div style={{ fontSize: 50, fontWeight: 800, color: SUB, marginTop: 20, wordBreak: "keep-all" }}>{c.big_sub}</div> : null}
      </div>
      {r ? (
        <div style={{ position: "absolute", left: 64, width: W, top: 930, opacity: Math.min(1, 0.2 + k * 2) }}>
          <div style={{ fontSize: 42, fontWeight: 800, color: SUB, marginBottom: 14 }}>{r.of}</div>
          <div style={{ height: 110, borderRadius: 20, background: "#E3DDD2", overflow: "hidden", position: "relative" }}>
            <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${Math.min(100, r.v) * k}%`, background: PRED }} />
          </div>
          <div style={{ fontSize: 64, fontWeight: 900, marginTop: 16 }}>{r.label}</div>
        </div>
      ) : null}
      {c.note ? <Note c={c} cues={cues} top={1340} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 확인 목록 — 말하는 항목에 형광펜 */
const Check: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const items = c.items ?? [];
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top: 500, display: "flex", flexDirection: "column", gap: 30 }}>
        {items.map((it, i) => {
          const at = cueAt(cues, it.at, 0.2 + i * 2.2);
          const next = i + 1 < items.length ? cueAt(cues, items[i + 1].at, at + 2.2) : 1e9;
          const on = t >= at;
          const cur = on && t < next;
          const k = prog(t, at, 0.4);
          return (
            <div key={i} style={{ display: "flex", gap: 26, alignItems: "flex-start", background: "#FFFFFF", borderRadius: 24, padding: "28px 30px", boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
              opacity: on ? 1 : 0.3, border: cur ? `5px solid ${PRED}` : "5px solid transparent" }}>
              <svg width={78} height={78} viewBox="0 0 100 100" style={{ flex: "0 0 auto" }}>
                <rect x={6} y={6} width={88} height={88} rx={18} fill="none" stroke={INK} strokeWidth={9} />
                <path d="M24 52 L44 72 L80 30" fill="none" stroke={PRED} strokeWidth={12} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={100} strokeDashoffset={100 - 100 * k} />
              </svg>
              <div style={{ fontSize: 54, fontWeight: 900, lineHeight: 1.28, wordBreak: "keep-all" }}>
                <span style={{ background: cur ? `linear-gradient(transparent 58%, ${HL} 58%)` : "none" }}>{it.t}</span>
              </div>
            </div>
          );
        })}
      </div>
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

/** 갈림길 — 이 숫자가 이어지면 / 깨지면 */
const Split: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const Box: React.FC<{ d: NonNullable<DCard["up"]>; dir: "up" | "down"; top: number; fb: number }> = ({ d, dir, top, fb }) => {
    const at = cueAt(cues, d.at, fb);
    const k = prog(t, at, 0.5);
    const col = dir === "up" ? PRED : PBLUE;
    return (
      <div style={{ position: "absolute", left: 64, width: W, top, background: "#FFFFFF", borderRadius: 28, padding: "30px 34px", boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
        borderLeft: `18px solid ${col}`, opacity: Math.min(1, 0.2 + k * 2), display: "flex", gap: 26, alignItems: "center" }}>
        <div style={{ flex: "0 0 auto" }}><Arrow dir={dir} color={col} size={120} /></div>
        <div>
          <div style={{ fontSize: 46, fontWeight: 900, color: col }}>{d.title}</div>
          <div style={{ fontSize: 54, fontWeight: 900, lineHeight: 1.28, marginTop: 8, wordBreak: "keep-all" }}>{d.t}</div>
        </div>
      </div>
    );
  };
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      {c.up ? <Box d={c.up} dir="up" top={480} fb={0.2} /> : null}
      {c.down ? <Box d={c.down} dir="down" top={900} fb={2.6} /> : null}
      <QOverlay cues={cues} />
    </PaperShell>
  );
};

const pickD = (id: string): React.FC<SC> => ({ p, cues, sub }) => {
  const c = infoOf(p).cards?.[id];
  if (!c) return <PaperShell p={p} cues={cues}><></></PaperShell>;
  const M: Record<string, React.FC<SC & { c: DCard }>> = { hook: Hook, line: Line, bars: Bars, vs: Vs, hbars: HBars, picto: Picto, stack: Stack, big: Big, check: Check, split: Split };
  const X = M[c.kind] ?? Check;
  return <X p={p} cues={cues} sub={sub} c={c} />;
};

/** 끝 화면 — 0초부터 */
const EndD: React.FC<SC> = ({ p, cues }) => {
  const pop = usePop();
  return (
    <PaperShell p={p} cues={cues} hideSub>
      <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(0, 24) }}>
        <div style={{ fontSize: 150, fontWeight: 900, letterSpacing: "-0.05em" }}>누가샀나</div>
        <div style={{ height: 12, width: 330, background: PRED, borderRadius: 6, marginTop: 6 }} />
        <div style={{ fontSize: 60, fontWeight: 800, marginTop: 40, color: SUB }}>국장 마감은 매일</div>
        <div style={{ fontSize: 110, fontWeight: 900 }}><span style={{ background: `linear-gradient(transparent 55%, ${HL} 55%)` }}>저녁 5시</span></div>
      </div>
    </PaperShell>
  );
};

export const DISSECT_COMP: Record<string, React.FC<SC>> = Object.fromEntries([
  ...Array.from({ length: 10 }, (_, i) => [`i${i}`, pickD(`i${i}`)] as const),
  ["iz", EndD] as const,
]);

/* ───────── 썸네일(1080×1920 스틸) — 종이 바탕 + 맞선 두 그림 + 3줄 ─────────
 * props.info.thumb = {name, lines:[{t, color?}] (3줄까지), a:{series}, b:{bars}} — a·b 가 없으면 cards.i0 의 것을 쓴다. */
export const DissectThumb: React.FC<Props> = (p) => {
  const info = infoOf(p) as Info & { thumb?: { lines?: { t: string; color?: string }[]; a?: { series: number[] }; b?: { bars: number[] } } };
  const th = info.thumb ?? {};
  const h0 = info.cards?.i0;
  const series = th.a?.series ?? h0?.a?.series ?? [];
  const bars = th.b?.bars ?? h0?.b?.bars ?? [];
  const mb = Math.max(1e-9, ...bars);
  const lines = (th.lines ?? []).slice(0, 3);
  return (
    <AbsoluteFill style={{ background: PAPER, fontFamily: FONT, color: INK }}>
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${GRID} 2px, transparent 2px), linear-gradient(90deg, ${GRID} 2px, transparent 2px)`, backgroundSize: "54px 54px" }} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 150, background: INK }} />
      <div style={{ position: "absolute", left: 64, top: 40, fontSize: 64, fontWeight: 900, color: "#FFFFFF", letterSpacing: "-0.03em" }}>기업 해부</div>
      <div style={{ position: "absolute", right: 64, top: 48, fontSize: 52, fontWeight: 900, color: "#FFFFFF" }}>누가샀나<span style={{ color: PRED }}>.</span></div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 230 }}>
        {lines.map((l, i) => (
          <div key={i} style={{ fontSize: i === 0 ? 150 : 132, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.05em", color: C(l.color), wordBreak: "keep-all" }}>{l.t}</div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 64, width: W, top: 800, height: 860, background: "#FFFFFF", borderRadius: 36, boxShadow: "0 12px 40px rgba(0,0,0,0.12)" }}>
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 26, display: "flex", justifyContent: "space-between", fontSize: 40, fontWeight: 900 }}>
          <span style={{ color: PBLUE }}>━ 주가</span><span style={{ color: PRED }}>■ 분기 영업이익</span>
        </div>
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 100, height: 600, display: "flex", alignItems: "flex-end", gap: 22 }}>
          {bars.map((v, i) => <div key={i} style={{ flex: 1, height: `${(v / mb) * 100}%`, background: i === bars.length - 1 ? PRED : "rgba(224,49,43,0.35)", borderRadius: "14px 14px 0 0" }} />)}
        </div>
        <svg width={W - 80} height={600} style={{ position: "absolute", left: 40, top: 60, overflow: "visible" }}>
          <SvgLine series={series} w={W - 80} h={600} color={PBLUE} k={1} stroke={16} />
        </svg>
      </div>
    </AbsoluteFill>
  );
};
