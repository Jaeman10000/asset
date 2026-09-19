/** 기업 해부(이슈 해설) 화면 — JJ 2026-09-19 "썸네일은 기존 것과 아예 다르게, 모든 장면을 이미지 시각화 자료로 꽉 채워".
 * 국장 마감(어두운 야경·네온)과 한눈에 갈리게 밝은 종이 + 검은 글자 + 빨강(오름)·파랑(내림).
 * 장면마다 그림이 화면 대부분을 차지한다: 선 그래프·막대·맞대기·가로 막대·그림 개수·비중 띠·확인 목록.
 * 말과 맞추기: 그림 조각은 그 장면의 i번째 문장이 시작할 때 켜진다(at = 문장 번호). 질문 문장에선 질문만 크게.
 * 데이터는 대본 파일(data/<날짜>/info_script.json → info.cards)에서 받는다 — 여기서 숫자를 만들지 않는다. */
import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile } from "remotion";
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
  kind: "hook" | "hook2" | "line" | "bars" | "vs" | "hbars" | "picto" | "stack" | "big" | "check" | "split" | "q" | "duo" | "score" | "steps";
  // hook2(9/20 JJ "첫 장면 세련되게"): 제목 + 한 줄 + 숫자 칩 + 넓은 차트 카드 한 장
  sub2?: string; chips?: { label: string; value: string; tone?: "red" | "blue" | "ink"; note?: string }[];
  chart?: { kind: "linebars" | "negbars"; title?: string; series?: number[]; bars?: number[]; rows?: Pt[]; startLabel?: string; endLabel?: string; barLabel?: string; legend?: [string, string] };
  head?: string; note?: string; note_at?: number; unit?: string;
  // hook
  tag?: string; name?: string; a?: { label: string; value: string; series: number[] }; b?: { label: string; value: string; bars: number[]; labels?: string[] }; q?: QLine[];
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
        <div style={{ fontSize: 34, fontWeight: 900, color: "#FFFFFF", background: INK, padding: "10px 22px", borderRadius: 12 }}>{(p as unknown as { badge?: string }).badge ?? "기업 해부"}</div>
        <div style={{ fontSize: 38, fontWeight: 800, color: SUB }}>{md}</div>
      </div>
      {head ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 196, fontSize: fitHead(head), fontWeight: 900, lineHeight: 1.16, letterSpacing: "-0.035em", wordBreak: "keep-all", ...pop(0, 14) }}>{head}</div>
      ) : null}
      {children}
      {sub ? (
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 300, display: "flex", justifyContent: "center" }}>
          <div style={{ background: "rgba(20,20,20,0.93)", color: "#FFFFFF", fontSize: 42, fontWeight: 700, lineHeight: 1.38, padding: "16px 28px", borderRadius: 18, wordBreak: "keep-all", textAlign: "center", boxShadow: "0 10px 28px rgba(0,0,0,0.25)" }}>{sub}</div>
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 52, fontSize: 26, color: "rgba(20,20,20,0.45)" }}>{FOOT}</div>
    </AbsoluteFill>
  );
};

/** 질문 문장이 시작되면 그림을 흐리게 깔고 질문만 크게 */
type QLine = string | { t: string; at?: number };
const QOverlay: React.FC<{ cues?: Cue[]; lines?: QLine[] }> = ({ cues, lines }) => {
  const { t } = useT();
  const q = qCue(cues);
  const L = (lines ?? []).map((l) => (typeof l === "string" ? { t: l, at: undefined as number | undefined } : l));
  // 줄마다 at(문장 번호)이 있으면 그 문장에서 켜진다 — 선택지 두 개를 하나씩(JJ 9/19 "과연 …? 아니면 …?")
  const start = L.length && L[0].at !== undefined ? cueAt(cues, L[0].at, 0) : q ? q.start : Infinity;
  if (t < start) return null;
  const k = prog(t, start, 0.35);
  const text = L.length ? L : [{ t: (q?.text ?? "").trim(), at: undefined }];
  return (
    <AbsoluteFill style={{ background: `rgba(243,239,231,${0.96 * k})` }}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 600, opacity: k, transform: `translateY(${(1 - k) * 30}px)` }}>
        {text.map((l, i) => {
          const on = l.at === undefined || t >= cueAt(cues, l.at, 0);
          return (
            <div key={i} style={{ fontSize: 104, fontWeight: 900, lineHeight: 1.16, letterSpacing: "-0.045em", wordBreak: "keep-all", color: i === text.length - 1 ? PRED : INK,
              opacity: on ? 1 : 0, marginTop: i > 0 && L.some((x) => x.at !== undefined) ? 24 : 0 }}>{l.t}</div>
          );
        })}
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
        <div style={{ flex: 1, background: "#FFFFFF", borderRadius: 28, padding: 28, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", position: "relative" }}>
          <div style={{ fontSize: 46, fontWeight: 900, color: SUB }}>{a.label}</div>
          <div style={{ fontSize: a.value.length > 7 ? 70 : 108, fontWeight: 900, color: PBLUE, letterSpacing: "-0.04em", lineHeight: 1.1, whiteSpace: "nowrap" }}>{a.value}</div>
          <svg width={402} height={520} style={{ position: "absolute", left: 28, bottom: 30, overflow: "visible" }}>
            <SvgLine series={a.series} w={402} h={520} color={PBLUE} k={k} area />
          </svg>
        </div>
        <div style={{ flex: 1, background: "#FFFFFF", borderRadius: 28, padding: 28, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", position: "relative" }}>
          <div style={{ fontSize: 46, fontWeight: 900, color: SUB }}>{b.label}</div>
          <div style={{ fontSize: b.value.length > 7 ? 70 : 108, fontWeight: 900, color: PRED, letterSpacing: "-0.04em", lineHeight: 1.1, whiteSpace: "nowrap" }}>{b.value}</div>
          <div style={{ position: "absolute", left: 28, right: 28, bottom: 30, height: 520, display: "flex", alignItems: "flex-end", gap: b.bars.length > 12 ? 3 : 16 }}>
            {b.bars.map((v, i) => (
              <div key={i} style={{ flex: 1, height: `${(v / mb) * 100 * Math.min(1, Math.max(0, k * b.bars.length - i + 0.6))}%`, background: b.labels ? PRED : i === b.bars.length - 1 ? PRED : "rgba(224,49,43,0.45)", borderRadius: "10px 10px 0 0", position: "relative" }}>
                {b.labels?.[i] ? <div style={{ position: "absolute", left: 0, right: 0, bottom: 10, textAlign: "center", fontSize: 30, fontWeight: 900, color: "#FFFFFF", lineHeight: 1.15, whiteSpace: "pre-line" }}>{b.labels[i]}</div> : null}
              </div>
            ))}
          </div>
        </div>
      </div>
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};


/** 첫 장면 v2 — 0초부터 제목·한 줄·숫자 칩이 서 있고, 아래 넓은 카드에 차트가 그려진다. 질문 문장이면 질문만 */
const Hook2: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const k = Math.min(1, 0.3 + t / 1.4);
  const chips = c.chips ?? [];
  const ch = c.chart;
  const CW = W - 64, CH = 520;
  return (
    <PaperShell p={p} cues={cues} hideSub>
      <div style={{ position: "absolute", left: 64, right: 64, top: 186 }}>
        {c.tag ? <div style={{ display: "inline-block", fontSize: 38, fontWeight: 900, background: HL, padding: "6px 18px", borderRadius: 8 }}>{c.tag}</div> : null}
        <div style={{ fontSize: 150, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.04, marginTop: 12 }}>{c.name}</div>
        {c.sub2 ? <div style={{ fontSize: 54, fontWeight: 900, color: SUB, marginTop: 10, letterSpacing: "-0.02em", wordBreak: "keep-all" }}>{c.sub2}</div> : null}
      </div>
      <div style={{ position: "absolute", left: 64, width: W, top: 560, display: "flex", gap: 20 }}>
        {chips.map((x, i) => {
          const col = C(x.tone);
          return (
            <div key={i} style={{ flex: 1, background: "#FFFFFF", borderRadius: 24, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", padding: "22px 24px 20px", borderTop: `10px solid ${col}` }}>
              <div style={{ fontSize: chips.length > 2 ? 34 : 38, fontWeight: 900, color: SUB }}>{x.label}</div>
              <div style={{ fontSize: chips.length > 2 ? (x.value.length > 5 ? 58 : 76) : x.value.length > 7 ? 74 : 96, fontWeight: 900, color: col, letterSpacing: "-0.04em", lineHeight: 1.08, whiteSpace: "nowrap" }}>{x.value}</div>
              {x.note ? <div style={{ fontSize: 30, fontWeight: 800, color: SUB, marginTop: 4, wordBreak: "keep-all" }}>{x.note}</div> : null}
            </div>
          );
        })}
      </div>
      {ch ? (
        <div style={{ position: "absolute", left: 64, width: W, top: 850, height: 700, background: "#FFFFFF", borderRadius: 32, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 18px 44px rgba(20,20,20,0.12)" }}>
          {ch.title ? <div style={{ position: "absolute", left: 34, top: 26, fontSize: 38, fontWeight: 900, color: SUB }}>{ch.title}</div> : null}
          <svg width={CW} height={CH} style={{ position: "absolute", left: 32, top: 96, overflow: "visible" }}>
            {[0.25, 0.5, 0.75].map((g) => <line key={g} x1={0} x2={CW} y1={CH * g} y2={CH * g} stroke="rgba(20,20,20,0.08)" strokeWidth={2} />)}
            {ch.kind === "linebars" ? (
              <>
                {(ch.bars ?? []).map((v, i, arr) => {
                  const mb = Math.max(1e-9, ...arr);
                  const bw = CW / arr.length;
                  const h = (v / mb) * CH * 0.62 * Math.min(1, Math.max(0, k * arr.length - i + 0.5));
                  return <rect key={i} x={i * bw + 1} y={CH - h} width={Math.max(2, bw - 3)} height={h} fill={i === arr.length - 1 ? PRED : "rgba(224,49,43,0.32)"} />;
                })}
                <SvgLine series={ch.series ?? []} w={CW} h={CH * 0.9} color={PBLUE} k={k} stroke={9} area />
                {ch.startLabel ? <text x={4} y={30} fontSize={40} fontWeight={900} fill={PBLUE} stroke="#FFFFFF" strokeWidth={10} paintOrder="stroke" fontFamily={FONT}>{ch.startLabel}</text> : null}
                {ch.endLabel && k > 0.95 ? <text x={CW} y={CH * 0.62} textAnchor="end" fontSize={44} fontWeight={900} fill={PBLUE} stroke="#FFFFFF" strokeWidth={10} paintOrder="stroke" fontFamily={FONT}>{ch.endLabel}</text> : null}
                {ch.barLabel && k > 0.95 ? <text x={CW} y={CH - (CH * 0.62) - 14} textAnchor="end" fontSize={40} fontWeight={900} fill={PRED} stroke="#FFFFFF" strokeWidth={10} paintOrder="stroke" fontFamily={FONT}>{ch.barLabel}</text> : null}
              </>
            ) : (
              <>
                <line x1={0} x2={CW} y1={CH * 0.3} y2={CH * 0.3} stroke={INK} strokeWidth={3} />
                {(ch.rows ?? []).map((r, i, arr) => {
                  const mx = Math.max(1e-9, ...arr.map((x) => Math.abs(x.v)));
                  const gap = 14, bw = (CW - gap * (arr.length - 1)) / arr.length;
                  const g = Math.min(1, Math.max(0, k * arr.length - i + 0.5));
                  const h = (Math.abs(r.v) / mx) * (r.v < 0 ? CH * 0.6 : CH * 0.26) * g;
                  const x = i * (bw + gap), down = r.v < 0;
                  const col = down ? PBLUE : PRED;
                  return (
                    <g key={i}>
                      <rect x={x} y={down ? CH * 0.3 : CH * 0.3 - h} width={bw} height={h} rx={8} fill={col} opacity={r.hl ? 1 : 0.85} />
                      <text x={x + bw / 2} y={down ? CH * 0.3 + h + 36 : CH * 0.3 - h - 12} textAnchor="middle" fontSize={30} fontWeight={900} fill={col} opacity={g} fontFamily={FONT}>{r.vlabel}</text>
                      <text x={x + bw / 2} y={CH + 44} textAnchor="middle" fontSize={30} fontWeight={800} fill={SUB} fontFamily={FONT}>{r.label}</text>
                    </g>
                  );
                })}
              </>
            )}
          </svg>
          {ch.legend ? (
            <div style={{ position: "absolute", left: 34, right: 34, bottom: 22, display: "flex", justifyContent: "space-between", fontSize: 34, fontWeight: 900 }}>
              <span style={{ color: PBLUE }}>━ {ch.legend[0]}</span><span style={{ color: PRED }}>■ {ch.legend[1]}</span>
            </div>
          ) : null}
        </div>
      ) : null}
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
      <QOverlay cues={cues} lines={c.q} />
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

/** 세로 막대 — 분기 이익 등. est=전망(빗금), hl=강조. 음수가 있으면 0선을 가운데 두고 아래로(파랑) */
const Bars: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const bars = c.bars ?? [];
  const H = 700, top = 520;
  const neg = bars.some((b) => b.v < 0);
  const mx = Math.max(1e-9, ...bars.map((b) => Math.abs(b.v)));
  const n = bars.length, gap = n > 8 ? 12 : 22, bw = (W - gap * (n - 1)) / n;
  const base = neg ? H * 0.5 : H;
  const span = neg ? H * 0.42 : H * 0.86;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <svg width={W} height={H + 90} style={{ position: "absolute", left: 64, top, overflow: "visible" }}>
        <defs>
          <pattern id="hatch" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="18" height="18" fill="rgba(224,49,43,0.18)" />
            <line x1="0" y1="0" x2="0" y2="18" stroke={PRED} strokeWidth="8" />
          </pattern>
        </defs>
        <line x1={0} x2={W} y1={base} y2={base} stroke={INK} strokeWidth={3} />
        {bars.map((b, i) => {
          const at = cueAt(cues, b.at, 0.1 + i * 0.25);
          const g = prog(t, at, 0.7);
          const h = (Math.abs(b.v) / mx) * span * g;
          const x = i * (bw + gap);
          const down = b.v < 0;
          const col = b.color ? C(b.color) : neg ? (down ? PBLUE : PRED) : b.hl || b.est ? PRED : "#B9B2A7";
          const y = down ? base : base - h;
          const fs = bw > 150 ? 46 : bw > 70 ? 38 : 30;
          return (
            <g key={i}>
              <rect x={x} y={y} width={bw} height={h} rx={bw > 40 ? 10 : 5} fill={b.est ? "url(#hatch)" : col} stroke={b.est ? PRED : "none"} strokeWidth={b.est ? 5 : 0} opacity={b.hl || !neg ? 1 : 0.85} />
              {b.vlabel || !neg ? <text x={x + bw / 2} y={down ? y + h + fs + 4 : y - 16} textAnchor="middle" fontSize={fs} fontWeight={900} fill={neg ? col : b.hl || b.est ? PRED : INK} opacity={g} fontFamily={FONT}>{b.vlabel ?? b.v}</text> : null}
              {b.label ? <text x={x + bw / 2} y={neg ? H + 50 : H + 50} textAnchor="middle" fontSize={bw > 150 ? 38 : bw > 70 ? 32 : 26} fontWeight={800} fill={SUB} fontFamily={FONT}>{b.label}</text> : null}
              {b.est ? <text x={x + bw / 2} y={H + 86} textAnchor="middle" fontSize={30} fontWeight={900} fill={PRED} fontFamily={FONT}>추정</text> : null}
            </g>
          );
        })}
      </svg>
      {c.note ? <Note c={c} cues={cues} top={top + H + 110} /> : null}
      <QOverlay cues={cues} lines={c.q} />
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
      <div style={{ position: "absolute", left: 64, width: W, top, height: 470, background: "#FFFFFF", borderRadius: 28, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", opacity: Math.min(1, 0.25 + k * 1.5) }}>
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
      <QOverlay cues={cues} lines={c.q} />
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
  // 이름+값 글자 폭 어림(한글 1em, 숫자·기호 0.6em) — 섞인 막대는 반쪽에 들어가야 한다
  const shrink = (r: Pt) => {
    const em = (x: string) => [...x].reduce((a, ch) => a + (/[가-힣]/.test(ch) ? 1 : ch === " " ? 0.3 : 0.62), 0);
    const need = em(r.label ?? "") * 42 + em(String(r.vlabel ?? r.v)) * 50 + 30;
    const room = (mixed ? W / 2 : W) - 20;
    return Math.min(1, room / need);
  };
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
              <div style={{ position: "absolute", top: 0, display: "flex", alignItems: "baseline", gap: 14, whiteSpace: "nowrap", ...side }}>
                <span style={{ fontSize: (r.hl ? 46 : 40) * shrink(r), fontWeight: 900, background: r.hl ? `linear-gradient(transparent 55%, ${HL} 55%)` : "none" }}>{r.label}</span>
                <span style={{ fontSize: 50 * shrink(r), fontWeight: 900, color: col }}>{r.vlabel ?? r.v}</span>
              </div>
              <div style={{ position: "absolute", top: bt, height: bh, left: mixed && r.v < 0 ? zero - w : zero, width: w, background: col, borderRadius: 10, opacity: r.hl ? 1 : 0.8 }} />
            </div>
          );
        })}
      </div>
      {c.note ? <Note c={c} cues={cues} top={top + rh * rows.length + 30} /> : null}
      <QOverlay cues={cues} lines={c.q} />
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
            <div key={gi} style={{ background: "#FFFFFF", borderRadius: 28, padding: "26px 30px", border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", opacity: t >= at - 0.05 ? 1 : 0.25 }}>
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
      <QOverlay cues={cues} lines={c.q} />
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
      <QOverlay cues={cues} lines={c.q} />
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
      <QOverlay cues={cues} lines={c.q} />
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
            <div key={i} style={{ display: "flex", gap: 26, alignItems: "flex-start", background: "#FFFFFF", borderRadius: 24, padding: "28px 30px", boxShadow: "0 14px 36px rgba(20,20,20,0.10)",
              opacity: on ? 1 : 0.3, border: cur ? `5px solid ${PRED}` : "5px solid rgba(20,20,20,0.06)" }}>
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
      <QOverlay cues={cues} lines={c.q} />
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
      <div style={{ position: "absolute", left: 64, width: W, top, background: "#FFFFFF", borderRadius: 28, padding: "30px 34px", border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)",
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
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};


/* ───────── 9/20 JJ "삼성전기 편만큼 꽉 차게" — 빈 화면 카드(big·split) 대신 쓰는 그림 ───────── */
type DuoPanel = { title: string; bars: Pt[]; at?: number; note?: string };
type ScoreRow = { label: string; value: string; good: boolean; note?: string; at?: number };
type StepPt = { label: string; v: number | null; vlabel: string };

/** 막대 두 묶음(위·아래) — 오를 때 vs 내릴 때, 주가 vs 장부 가치 + 도매가격 */
const Duo: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const panels = ((c as unknown as { duo?: DuoPanel[] }).duo ?? []).slice(0, 2);
  const PH = 470, top0 = 440;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      {panels.map((pn, pi) => {
        const at = cueAt(cues, pn.at, 0.1 + pi * 1.5);
        const g0 = prog(t, at, 0.7);
        const on = t >= at - 0.05;
        const bars = pn.bars;
        const neg = bars.some((b) => b.v < 0);
        const mx = Math.max(1e-9, ...bars.map((b) => Math.abs(b.v)));
        const CW = W - 68, CH = 300, gap = 40, bw = Math.min(260, (CW - gap * (bars.length - 1)) / bars.length);
        const x0 = (CW - (bw * bars.length + gap * (bars.length - 1))) / 2;
        const base = neg ? CH * 0.5 : CH;
        const span = neg ? CH * 0.44 : CH * 0.82;
        return (
          <div key={pi} style={{ position: "absolute", left: 64, width: W, top: top0 + pi * (PH + 28), height: PH, background: "#FFFFFF", borderRadius: 28,
            border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 14px 36px rgba(20,20,20,0.10)", opacity: on ? 1 : 0.32 }}>
            <div style={{ position: "absolute", left: 34, top: 22, fontSize: 42, fontWeight: 900, color: INK }}>{pn.title}</div>
            <svg width={CW} height={CH + 60} style={{ position: "absolute", left: 34, top: 96, overflow: "visible" }}>
              <line x1={0} x2={CW} y1={base} y2={base} stroke={INK} strokeWidth={3} />
              {bars.map((b, i) => {
                const h = (Math.abs(b.v) / mx) * span * g0;
                const x = x0 + i * (bw + gap), down = b.v < 0;
                const col = b.color ? C(b.color) : down ? PBLUE : PRED;
                return (
                  <g key={i}>
                    <rect x={x} y={down ? base : base - h} width={bw} height={h} rx={12} fill={col} />
                    <text x={x + bw / 2} y={down ? base + h + 44 : base - h - 14} textAnchor="middle" fontSize={44} fontWeight={900} fill={col} opacity={g0} fontFamily={FONT}>{b.vlabel}</text>
                    <text x={x + bw / 2} y={neg ? (down ? base - 16 : base + 44) : CH + 48} textAnchor="middle" fontSize={38} fontWeight={900} fill={SUB} fontFamily={FONT}>{b.label}</text>
                  </g>
                );
              })}
            </svg>
            {pn.note ? <div style={{ position: "absolute", right: 34, top: 28, fontSize: 32, fontWeight: 800, color: SUB }}>{pn.note}</div> : null}
          </div>
        );
      })}
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};

/** 점수표 — 버핏 기준: 싸 보이는 숫자(✓) / 걸리는 숫자(✗). 말하는 줄이 켜진다 */
const Score: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const rows = (c as unknown as { score?: ScoreRow[] }).score ?? [];
  const RH = 176;
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top: 440, background: "#FFFFFF", borderRadius: 30, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 18px 44px rgba(20,20,20,0.12)", overflow: "hidden" }}>
        {rows.map((r, i) => {
          const at = r.at === undefined ? -1 : cueAt(cues, r.at, 0.3 + i * 1.2);
          const on = t >= at - 0.05;
          const nextAt = rows.slice(i + 1).map((x) => (x.at === undefined ? -1 : cueAt(cues, x.at, 99))).find((x) => x > at) ?? 1e9;
          const cur = on && r.at !== undefined && t < nextAt;
          const col = r.good ? PRED : PBLUE;
          return (
            <div key={i} style={{ height: RH, display: "flex", alignItems: "center", gap: 22, padding: "0 30px", borderTop: i ? "2px solid rgba(20,20,20,0.07)" : "none",
              background: cur ? "rgba(255,212,59,0.22)" : "transparent", opacity: on ? 1 : 0.28 }}>
              <div style={{ width: 88, height: 88, borderRadius: 44, background: on ? col : "#D8D2C7", color: "#FFFFFF", fontSize: 54, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center", flex: "0 0 auto" }}>{r.good ? "✓" : "✗"}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 46, fontWeight: 900, lineHeight: 1.1 }}>{r.label}</div>
                {r.note ? <div style={{ fontSize: 30, fontWeight: 800, color: SUB, marginTop: 6, wordBreak: "keep-all" }}>{r.note}</div> : null}
              </div>
              <div style={{ fontSize: 64, fontWeight: 900, color: col, letterSpacing: "-0.03em", whiteSpace: "nowrap" }}>{r.value}</div>
            </div>
          );
        })}
      </div>
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};

/** 계단 — 기준금리 인상 흐름(마지막 칸은 다음 결정 '?') */
const Steps: React.FC<SC & { c: DCard }> = ({ p, cues, c }) => {
  const { t } = useT();
  const pts = (c as unknown as { steps?: StepPt[] }).steps ?? [];
  const vals = pts.map((x) => x.v).filter((v): v is number => v != null);
  const lo = Math.min(...vals) - 0.25, hi = Math.max(...vals) + 0.35;
  const CW = W - 60, CH = 640, n = pts.length, sw = CW / n;
  const Y = (v: number) => CH - ((v - lo) / (hi - lo)) * CH;
  const k = prog(t, 0.1, 1.8);
  return (
    <PaperShell p={p} cues={cues} head={c.head}>
      <div style={{ position: "absolute", left: 64, width: W, top: 450, height: 860, background: "#FFFFFF", borderRadius: 30, border: "2px solid rgba(20,20,20,0.07)", boxShadow: "0 18px 44px rgba(20,20,20,0.12)" }}>
        <svg width={CW} height={CH + 90} style={{ position: "absolute", left: 30, top: 70, overflow: "visible" }}>
          {pts.map((x, i) => {
            const show = k * n >= i + 0.2;
            const xs = i * sw;
            if (x.v == null) return (
              <g key={i} opacity={show ? 1 : 0}>
                <rect x={xs + 10} y={Y(vals[vals.length - 1]) - 150} width={sw - 20} height={150} rx={14} fill="url(#hatchS)" stroke={PRED} strokeWidth={4} strokeDasharray="12 10" />
                <text x={xs + sw / 2} y={Y(vals[vals.length - 1]) - 170} textAnchor="middle" fontSize={84} fontWeight={900} fill={PRED} fontFamily={FONT}>?</text>
                <text x={xs + sw / 2} y={CH + 60} textAnchor="middle" fontSize={36} fontWeight={900} fill={PRED} fontFamily={FONT}>{x.label}</text>
              </g>
            );
            const y = Y(x.v);
            return (
              <g key={i} opacity={show ? 1 : 0}>
                <rect x={xs + 10} y={y} width={sw - 20} height={CH - y} rx={14} fill={i === vals.length - 1 ? PRED : "rgba(224,49,43,0.35)"} />
                <text x={xs + sw / 2} y={y - 18} textAnchor="middle" fontSize={50} fontWeight={900} fill={i === vals.length - 1 ? PRED : INK} fontFamily={FONT}>{x.vlabel}</text>
                <text x={xs + sw / 2} y={CH + 60} textAnchor="middle" fontSize={36} fontWeight={900} fill={SUB} fontFamily={FONT}>{x.label}</text>
              </g>
            );
          })}
          <defs>
            <pattern id="hatchS" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="18" height="18" fill="rgba(224,49,43,0.10)" /><line x1="0" y1="0" x2="0" y2="18" stroke={PRED} strokeWidth="6" />
            </pattern>
          </defs>
          <line x1={0} x2={CW} y1={CH} y2={CH} stroke={INK} strokeWidth={3} />
        </svg>
      </div>
      {c.note ? <Note c={c} cues={cues} top={1340} /> : null}
      <QOverlay cues={cues} lines={c.q} />
    </PaperShell>
  );
};

const pickD = (id: string): React.FC<SC> => ({ p, cues, sub }) => {
  const c = infoOf(p).cards?.[id];
  if (!c) return <PaperShell p={p} cues={cues}><></></PaperShell>;
  const M: Record<string, React.FC<SC & { c: DCard }>> = { duo: Duo, score: Score, steps: Steps, hook: Hook, hook2: Hook2, line: Line, bars: Bars, vs: Vs, hbars: HBars, picto: Picto, stack: Stack, big: Big, check: Check, split: Split };
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
 * props.info.thumb = {name, lines:[{t, color?}] (3줄까지), a:{series}, b:{bars, label?(범례, 기본 "분기 영업이익")}} — a·b 가 없으면 cards.i0 의 것을 쓴다. */
export const DissectThumb: React.FC<Props> = (p) => {
  const info = infoOf(p) as Info & { thumb?: { lines?: { t: string; color?: string; size?: number }[]; a?: { series: number[] }; b?: { bars: number[]; label?: string }; legend?: [string, string] } };
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
          <div key={i} style={{ fontSize: (i === 0 ? 150 : 132) * (l.size ?? 1), fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.05em", color: C(l.color), wordBreak: "keep-all" }}>{l.t}</div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 64, width: W, top: 800, height: 860, background: "#FFFFFF", borderRadius: 36, boxShadow: "0 12px 40px rgba(0,0,0,0.12)" }}>
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 26, display: "flex", justifyContent: "space-between", fontSize: 40, fontWeight: 900 }}>
          <span style={{ color: PBLUE }}>━ 주가</span><span style={{ color: PRED }}>■ {th.b?.label ?? "분기 영업이익"}</span>
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

/* ───────── 썸네일 v2(경제사냥꾼 틀, JJ 2026-09-19 밤) ─────────
 * "글씨가 세로로 50% 이상 차지해서 그 글에 눈이 가게." 위쪽은 그림(인물 사진 자리 — 라이선스 확인된 사진이 없으면 우리가 그린 그림),
 * 아래쪽 절반 이상은 검은 테두리 흰·노랑 초대형 글자. props.info.thumb2 = {lines:[{t, size(px), color:"yellow"|"white"|"red"}], tag} */
const Knife: React.FC<{ x: number; y: number; s: number; rot: number }> = ({ x, y, s, rot }) => (
  <g transform={`translate(${x},${y}) rotate(${rot}) scale(${s})`}>
    <path d="M-18 -170 L18 -170 L22 60 Q0 150 -22 60 Z" fill="#E6EAF0" stroke="#0B0E14" strokeWidth={6} />
    <path d="M-4 -165 L4 -165 L6 50 L-6 50 Z" fill="#FFFFFF" opacity={0.7} />
    <rect x={-30} y={-178} width={60} height={16} rx={6} fill="#9AA3AF" stroke="#0B0E14" strokeWidth={5} />
    <rect x={-20} y={-300} width={40} height={124} rx={12} fill="#2A2F3A" stroke="#0B0E14" strokeWidth={5} />
    {[-40, 0, 40].map((dx) => <line key={dx} x1={dx} y1={-330} x2={dx} y2={-420} stroke="#FFFFFF" strokeWidth={8} strokeLinecap="round" opacity={0.55} />)}
  </g>
);

export const HunterThumb: React.FC<Props> = (p) => {
  const info = infoOf(p) as Info & { thumb2?: { lines?: { t: string; size?: number; color?: string }[]; tag?: string } };
  const th = info.thumb2 ?? {};
  const h0 = info.cards?.i0;
  const series = h0?.a?.series ?? [];
  const bars = h0?.b?.bars ?? [];
  const mb = Math.max(1e-9, ...bars);
  const col = (c?: string) => (c === "yellow" ? "#FFE14D" : c === "red" ? "#FF4A3D" : "#FFFFFF");
  return (
    <AbsoluteFill style={{ background: "#0B0E14", fontFamily: FONT }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 22%, #1E2A44 0%, #0B0E14 70%)" }} />
      {/* 위 그림: 개인 누적 매수 막대(빨강) 위로 무너지는 주가 선(파랑), 떨어지는 칼날 */}
      <div style={{ position: "absolute", left: 60, right: 60, top: 250, height: 560, display: "flex", alignItems: "flex-end", gap: 18, opacity: 0.9 }}>
        {bars.map((v, i) => <div key={i} style={{ flex: 1, height: `${(v / mb) * 100}%`, background: i === bars.length - 1 ? "#FF4A3D" : "rgba(255,74,61,0.45)", borderRadius: "12px 12px 0 0" }} />)}
      </div>
      <svg width={1080} height={900} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <g transform="translate(60,230)"><SvgLine series={series} w={960} h={560} color="#3D8BFF" k={1} stroke={18} /></g>
        <Knife x={820} y={420} s={1.05} rot={18} />
      </svg>
      <div style={{ position: "absolute", left: 40, top: 40, display: "flex", gap: 14, alignItems: "center" }}>
        <div style={{ fontSize: 46, fontWeight: 900, color: "#0B0E14", background: "#FFE14D", padding: "8px 20px", borderRadius: 10 }}>{th.tag ?? "기업 해부"}</div>
        <div style={{ fontSize: 46, fontWeight: 900, color: "#FFFFFF" }}>누가샀나<span style={{ color: "#FF4A3D" }}>.</span></div>
      </div>
      {/* 아래 글자: 세로 50% 이상 */}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(11,14,20,0) 40%, rgba(11,14,20,0.85) 52%, #0B0E14 62%)" }} />
      <div style={{ position: "absolute", left: 30, right: 30, bottom: 60, textAlign: "center" }}>
        {(th.lines ?? []).map((l, i) => (
          <div key={i} style={{ fontSize: l.size ?? 180, fontWeight: 900, lineHeight: 1.04, letterSpacing: "-0.04em", color: col(l.color), whiteSpace: "nowrap",
            WebkitTextStroke: `${Math.round((l.size ?? 180) / 14)}px #000`, paintOrder: "stroke fill", textShadow: "0 10px 30px rgba(0,0,0,0.8)" }}>{l.t}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ───────── 썸네일 v3: 받은 그림(ChatGPT 등) 위에 글자만 다시 얹기 (JJ 2026-09-19 밤 "썸네일은 chatgpt한테 부탁할게") ─────────
 * props.info.thumb3 = {src:"thumbsrc/…", srcW, srcH, blur:[{x,y,w,h}] (원본 좌표, 로고·가짜 간판 가리기), top(글자 시작 y, 1920 기준),
 *                      lines:[{t, size, color:"white"|"yellow"}], tag?, brand?}
 * 글자는 세로 50% 이상, 아래 약 16%(쇼츠 제목·버튼 자리)는 비운다. 숫자는 대본과 같은 것만. */
export const OverlayThumb: React.FC<Props> = (p) => {
  const info = infoOf(p) as Info & { thumb3?: { src: string; srcW: number; srcH: number; blur?: { x: number; y: number; w: number; h: number }[]; top?: number;
    lines?: { t: string; size?: number; color?: string }[]; tag?: string; brand?: boolean; cover?: number } };
  const th = info.thumb3;
  if (!th) return <AbsoluteFill style={{ background: "#000" }} />;
  const k = 1080 / th.srcW;
  const Y = (c?: string) => (c === "yellow" ? "#FFE033" : "#FFFFFF");
  return (
    <AbsoluteFill style={{ background: "#05070C", fontFamily: FONT }}>
      <Img src={staticFile(th.src)} style={{ position: "absolute", left: 0, top: 0, width: 1080, height: th.srcH * k }} />
      {(th.blur ?? []).map((b, i) => (
        <div key={i} style={{ position: "absolute", left: b.x * k, top: b.y * k, width: b.w * k, height: b.h * k, backdropFilter: "blur(44px) brightness(0.72)",
          WebkitBackdropFilter: "blur(44px) brightness(0.72)", maskImage: "radial-gradient(ellipse closest-side at center, #000 55%, transparent 100%)", WebkitMaskImage: "radial-gradient(ellipse closest-side at center, #000 55%, transparent 100%)" }} />
      ))}
      {/* 받은 그림에 박힌 원래 글자(아래쪽)는 완전히 덮는다 — cover 부터 불투명 */}
      <AbsoluteFill style={{ background: `linear-gradient(180deg, rgba(5,7,12,0) ${(th.cover ?? 900) / 19.2 - 12}%, rgba(5,7,12,0.9) ${(th.cover ?? 900) / 19.2 - 3}%, #05070C ${(th.cover ?? 900) / 19.2}%, #05070C 100%)` }} />
      {th.brand ? <div style={{ position: "absolute", right: 44, top: 46, fontSize: 48, fontWeight: 900, color: "#FFFFFF", textShadow: "0 4px 18px rgba(0,0,0,0.9)" }}>누가샀나<span style={{ color: PRED }}>.</span></div> : null}
      <div style={{ position: "absolute", left: 30, right: 30, top: th.top ?? 560, textAlign: "center" }}>
        {(th.lines ?? []).map((l, i) => {
          const sz = l.size ?? 200;
          return (
            <div key={i} style={{ fontSize: sz, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.045em", color: Y(l.color), whiteSpace: "nowrap",
              WebkitTextStroke: `${Math.round(sz / 11)}px #000`, paintOrder: "stroke fill",
              textShadow: l.color === "yellow" ? "0 0 40px rgba(255,170,0,0.75), 0 10px 26px rgba(0,0,0,0.9)" : "0 10px 26px rgba(0,0,0,0.9)" }}>{l.t}</div>
          );
        })}
        {th.tag ? <div style={{ display: "inline-block", marginTop: 18, fontSize: 50, fontWeight: 900, color: "#0B0E14", background: "#FFE033", padding: "8px 26px", borderRadius: 12 }}>{th.tag}</div> : null}
      </div>
    </AbsoluteFill>
  );
};
