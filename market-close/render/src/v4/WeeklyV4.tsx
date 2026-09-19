/** 주간 결산 v4 화면(토요일 영상 w0~w6). 틀은 ScenesV4와 같다 — 색조별로 미리 구운 배경 그림(고정), Pretendard 800/900,
 * 빛나는 카드, 그라데이션 숫자, 노란 질문. 오른쪽 위는 '주간 결산 / 9/7–9/11'.
 * 숫자는 전부 props(data/weekly/<토>/computed_weekly.json을 맨 위에 합친 것)의 실제 값. 장면 단계는 말(큐)에 맞춘다 — 질문 문장은 질문만 크게.
 * 렌더 비용: 배경은 고정 이미지, filter·drop-shadow 없음, 그래프는 SVG 선의 dashoffset·막대 높이만 움직인다.
 * 색: 한국식 — 빨강 = 순매수·상승, 파랑 = 순매도·하락. 노랑 = 질문·기준선. */
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { FONT, FOOTER, fmtEok, fmtIdx } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";

const ease = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const RED = "#FF4D4D";
const BLUE = "#3D7BFF";
const YEL = "#FFD84D";
const GREEN = "#2FD27A";
const SUBC = "#B8C2D6";
const SH = "0 3px 14px rgba(0,0,0,0.85)";
const SH_BIG = "0 8px 34px rgba(0,0,0,0.75)";
const SH_Q = "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)";
type Tone = "up" | "down" | "neutral";
const toneOf = (v?: number | null): Tone => (v == null || v === 0 ? "neutral" : v > 0 ? "up" : "down");
const colOf = (v?: number | null) => (v == null || v === 0 ? "#E6E6E3" : v > 0 ? RED : BLUE);

/* ───────── 주간 props(공유 스키마) ───────── */
type KDay = { d: string; close: number; chg_pct?: number | null; high?: number | null; low?: number | null };
type KEv = { d: string; kind: string; line?: number | null; text?: string };
type InvKey = "indiv" | "foreign" | "inst" | "others";
type InvRow = Partial<Record<InvKey, number | null>>;
type ThemeW = { theme: string; net: number; foreign?: number | null; inst?: number | null; days?: { d: string; net: number }[]; pos_days?: number | null };
type Stock = { code?: string; name: string; v: number };
type News = { d?: string; date?: string; title?: string; link?: string; line?: string; text?: string; why?: string; note?: string; src?: string; source?: string; url?: string };
type Wk = {
  week_start?: string; week_end?: string; build_date?: string; days?: string[];
  kospi?: { prev_close?: number | null; days?: KDay[]; week_chg_pct?: number | null; week_high?: number | null; week_low?: number | null; events?: KEv[] };
  inv?: { days?: ({ d: string } & InvRow)[]; week?: InvRow; streak_end?: Partial<Record<InvKey, number>> };
  themes?: { week?: ThemeW[]; top_out?: ThemeW | null; top_in?: ThemeW | null; stayed?: string[] };
  others_stocks?: { week?: Stock[]; days?: { d: string; top: Stock[] }[]; buyback_share?: number | null };
  buybacks?: { code?: string; name: string }[];
  checks?: { d: string; q: string; ok: boolean | null }[];
  news?: News[];
  // 주의: Root의 Video 기본 props(sample_kr.json)가 입력 props 아래에 얕게 합쳐진다 → 일간 필드(protagonist·hook_parts·check·contrast…)는 여기서 읽지 않는다.
  view?: string | { text?: string } | null;
  next_week?: { q?: string; day?: string } | null;
  next?: { q?: string; day?: string } | null;
  date_label?: string;
};
const wk = (p: Props) => p as unknown as Wk;
const INV: { k: InvKey; name: string }[] = [{ k: "indiv", name: "개인" }, { k: "foreign", name: "외국인" }, { k: "inst", name: "기관" }, { k: "others", name: "기타법인" }];

/* ───────── 글자·숫자 도우미 ───────── */
/** '2.5조' / '4,600억' — 화면 큰 숫자(말과 같은 반올림, ScenesV4와 동일) */
const short = (v: number) => {
  const a = Math.abs(v);
  if (a >= 10000) return `${(Math.round(a / 1000) / 10).toFixed(1).replace(/\.0$/, "")}조`;
  return `${(a >= 1000 ? Math.round(a / 100) * 100 : Math.round(a / 10) * 10).toLocaleString("ko-KR")}억`;
};
/** 막대 옆 작은 숫자: 1조 이상은 x.x조, 그 아래는 억 단위 그대로(데이터가 이미 억 정수) */
const tiny = (v: number) => (Math.abs(v) >= 10000 ? short(v) : `${Math.round(Math.abs(v)).toLocaleString("ko-KR")}억`);
const sgn = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");
const WD = ["일", "월", "화", "수", "목", "금", "토"];
const md = (d: string) => `${+d.slice(4, 6)}/${+d.slice(6, 8)}`;
const wdOf = (d: string) => WD[new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8)).getDay()];
const norm = (s: string) => s.replace(/[\s·/,.'"‘’“”…()]/g, "");
const has = (text: string, name?: string | null) => !!name && norm(text).includes(norm(name));
const isQ = (s: string) => /\?\s*$/.test(s.trim());
const daysKo = (n: number) => (n === 2 ? "이틀째" : n === 3 ? "사흘째" : n === 4 ? "나흘째" : n === 5 ? "닷새째" : `${n}일째`);
/** 대략 글자 폭(em) — 큰 글자가 한 줄에 들어가게 크기를 고를 때만 쓴다 */
const emOf = (s: string) => [...s].reduce((a, ch) => a + (/[0-9+−-]/.test(ch) ? 0.6 : /[.,]/.test(ch) ? 0.3 : ch === " " ? 0.28 : ch === "/" ? 0.42 : ch === "?" ? 0.55 : ch === "%" ? 0.85 : 0.98) - 0.04, 0);
const fit = (s: string, width: number, max: number) => Math.min(max, Math.floor(width / Math.max(emOf(s), 0.5)));
const weekDays = (w: Wk) => (w.days && w.days.length ? w.days : (w.kospi?.days ?? []).map((x) => x.d));
const rangeLabel = (w: Wk) => { const ds = weekDays(w); const a = ds[0] ?? w.week_start; const b = ds[ds.length - 1] ?? w.week_end; return a && b ? `${md(a)}–${md(b)}` : ""; };
/** 문장에 나온 요일·날짜 → 그 주의 몇 번째 날인지 */
const dayHits = (text: string, ds: string[]) => ds.map((d, i) => {
  const m = +d.slice(4, 6), dd = +d.slice(6, 8);
  return new RegExp(`${wdOf(d)}요일|${m}월\\s?${dd}일|(^|[^0-9])${dd}일|(^|[^0-9])${m}/${dd}(?![0-9])`).test(text) ? i : -1;
}).filter((i) => i >= 0);

const useT = () => { const f = useCurrentFrame(); const { fps, durationInFrames } = useVideoConfig(); return { f, fps, t: f / fps, dur: durationInFrames / fps }; };
const usePop = () => {
  const { f, fps } = useT();
  return (sec: number, dy = 26) => {
    const x = interpolate(f, [sec * fps, (sec + 0.45) * fps], [0, 1], { ...CLAMP, easing: ease });
    return { opacity: x, transform: `translateY(${(1 - x) * dy}px)` } as React.CSSProperties;
  };
};
const curCue = (cues: Cue[] | undefined, t: number) => { const l = cues ?? []; const i = l.filter((c) => t >= c.start).length - 1; return { list: l, i, cur: i >= 0 ? l[i] : undefined }; };
const findIdx = (list: Cue[], pred: (x: string) => boolean, from = 0) => { for (let i = Math.max(0, from); i < list.length; i++) if (pred(list[i].text)) return i; return -1; };

/* ───────── ScenesV4와 같은 틀(배경·카드·로고·그라데이션 숫자) ───────── */
/** 배경: public/bg 에 미리 구운 그림. 고정 — 매 프레임 확대·이동·drop-shadow는 렌더를 2배 늦춘다(2026-09-11 측정). */
const BgImg: React.FC<{ name: string; tone?: Tone; dim?: number }> = ({ name, tone = "neutral", dim = 0.15 }) => (
  <AbsoluteFill style={{ overflow: "hidden" }}>
    <Img src={staticFile(`bg/${name}_${tone}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scale(1.04)" }} />
    <AbsoluteFill style={{ background: `rgba(3,5,10,${dim})` }} />
  </AbsoluteFill>
);
const BgCity: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="city" {...pr} />;
const BgMarket: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="market" {...pr} />;
const BgChip: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="chip" {...pr} />;

const Grad: React.FC<{ tone: Tone; children: React.ReactNode; style?: React.CSSProperties }> = ({ tone, children, style }) => {
  const g = tone === "down" ? "linear-gradient(180deg,#A8DCFF 0%,#4A8BFF 48%,#2554E6 100%)"
    : tone === "up" ? "linear-gradient(180deg,#FFC2B8 0%,#FF5A4E 46%,#E2242B 100%)" : "linear-gradient(180deg,#FFFFFF 0%,#CFD6E4 100%)";
  return <span style={{ backgroundImage: g, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", ...style }}>{children}</span>;
};

const Card: React.FC<{ color: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ color, children, style }) => (
  <div style={{ border: `2.5px solid ${color}`, borderRadius: 24, background: "linear-gradient(180deg, rgba(10,14,26,0.86), rgba(6,9,18,0.92))",
    boxShadow: `0 0 34px ${color}66, inset 0 0 22px ${color}22`, padding: "28px 34px", ...style }}>{children}</div>
);

const Logo: React.FC<{ scale?: number }> = ({ scale = 1 }) => (
  <div style={{ transform: `scale(${scale})`, transformOrigin: "left top" }}>
    <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 60, color: "#FFFFFF", transform: "skewX(-10deg)", letterSpacing: "-0.05em", lineHeight: 1, textShadow: "0 3px 16px rgba(0,0,0,0.7)" }}>누가샀나</div>
    <svg width="220" height="24" viewBox="0 0 220 24" style={{ display: "block", marginTop: 2 }}>
      <path d="M3 15 C 46 7, 120 3, 216 8 L 213 14 C 150 11, 90 13, 40 17 C 25 18, 12 20, 5 21 Z" fill="#E8362F" />
      <path d="M40 18 C 90 15, 150 14, 205 13" stroke="#FF6A55" strokeWidth="2" fill="none" opacity="0.6" />
    </svg>
  </div>
);

/** 틀: 로고(왼쪽 위) + '주간 결산 / 9/7–9/11'(오른쪽 위) + 자막 + 바닥 문구 */
const WShell: React.FC<{ p: Props; bg: React.ReactNode; cues?: Cue[]; hideSub?: boolean; children: React.ReactNode }> = ({ p, bg, cues, hideSub, children }) => {
  const { t } = useT();
  const rg = rangeLabel(wk(p)) || (p.date_label ?? "").split(" ")[0];
  let sub = "";
  if (!hideSub && cues && cues.length) {
    const c = cues.find((x) => t >= x.start && t < x.end + 0.5);
    sub = c ? c.text : "";
  }
  return (
    <AbsoluteFill style={{ background: "#05070D", fontFamily: FONT, color: "#FFFFFF", fontVariantNumeric: "tabular-nums" }}>
      {bg}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(3,5,10,0.55) 0%, rgba(3,5,10,0.05) 38%, rgba(3,5,10,0) 60%, rgba(3,5,10,0.75) 100%)" }} />
      <div style={{ position: "absolute", left: 64, top: 64 }}><Logo /></div>
      <div style={{ position: "absolute", right: 64, top: 70, textAlign: "right", fontWeight: 800, lineHeight: 1.15, textShadow: "0 2px 10px rgba(0,0,0,0.7)" }}>
        <div style={{ fontSize: 32, color: "#E6E6E3" }}>주간 결산</div>
        <div style={{ fontSize: 44 }}>{rg}</div>
      </div>
      {children}
      {sub ? (
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 240, display: "flex", justifyContent: "center" }}>
          <div style={{ background: "rgba(8,10,16,0.9)", border: "2px solid rgba(255,255,255,0.12)", color: "#FFFFFF", fontSize: 42, fontWeight: 700, lineHeight: 1.38, padding: "16px 28px", borderRadius: 18,
            wordBreak: "keep-all", textAlign: "center", boxShadow: "0 10px 28px rgba(0,0,0,0.45)" }}>{sub}</div>
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 52, fontSize: 26, color: "rgba(230,230,227,0.55)", letterSpacing: "0.02em" }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};

/** 질문 문장 → 화면용: 앞 접속어를 떼고 '~까요?'는 '~까?'로. 앞부분(주제)과 질문 본체를 나눈다. */
const qSplit = (text: string) => {
  const q = text.trim().replace(/^(그럼|그렇다면|그런데|자)[,\s]*/, "").replace(/요\?\s*$/, "?");
  const m = q.match(/^([^,?]{2,}?),\s*(.+)$/) ?? q.match(/^(.*?[은는])\s+(.+)$/);
  return { head: m ? m[1] : "", body: m ? m[2] : q };
};
const QBig: React.FC<{ text: string; at: number; top?: number; small?: boolean }> = ({ text, at, top = 300, small }) => {
  const pop = usePop();
  const { head, body } = qSplit(text);
  const bfs = small ? Math.max(84, fit(body, 950, 112)) : body.length <= 7 ? Math.max(120, fit(body, 950, 172)) : body.length <= 10 ? 150 : body.length <= 16 ? 132 : 112;
  const hfs = Math.max(small ? 50 : 60, fit(head, 950, small ? 64 : 120));
  return (
    <div style={{ position: "absolute", left: 64, right: 64, top, ...pop(at, 30) }}>
      {head ? <div style={{ fontSize: hfs, fontWeight: 900, lineHeight: 1.1, letterSpacing: "-0.03em", wordBreak: "keep-all", textShadow: "0 6px 26px rgba(0,0,0,0.8)" }}>{head}</div> : null}
      <div style={{ fontSize: bfs, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: YEL, wordBreak: "keep-all", marginTop: head ? 6 : 0, textShadow: SH_Q }}>{body}</div>
    </div>
  );
};

/** 문장 속 숫자(약 8조 5천억·3.3%)만 노랗게 */
const Hi: React.FC<{ text: string }> = ({ text }) => {
  const parts = text.split(/(약\s?[\d,.]+\s?(?:조|억|%)(?:\s?\d[\d,]*천?억)?|[\d,.]+\s?(?:조|억|%)(?:\s?\d[\d,]*천?억)?)/);
  return <>{parts.map((x, i) => (i % 2 ? <span key={i} style={{ color: YEL }}>{x}</span> : <React.Fragment key={i}>{x}</React.Fragment>))}</>;
};
/** 줄바꿈이 '한 / 주로'처럼 끊기지 않게 짧은 말끼리 붙인다(줄바꿈 없는 공백) */
const glue = (s: string) => s.replace(/(한|이번|지난|다음|두|세) (주|회사|번)/g, "$1\u00A0$2").replace(/(\S) 수 있/g, "$1\u00A0수\u00A0있").replace(/약 (\d)/g, "약\u00A0$1");

/** 5일 막대 띠(SVG). 막대 높이만 움직인다. 0선은 (최대 순매수 : 최대 순매도) 비율 자리 — 띠 높이를 다 쓴다. 눈금은 띠마다 따로(합계 숫자가 크기를 말한다). */
const Bars: React.FC<{ vals: number[]; labels: string[]; w: number; h: number; at: number; showVals?: boolean; fs?: number }> = ({ vals, labels, w, h, at, showVals, fs = 26 }) => {
  const { t } = useT();
  const uid = React.useId().replace(/[^a-zA-Z0-9]/g, "");
  const k = interpolate(t, [at, at + 0.7], [0, 1], { ...CLAMP, easing: ease });
  const n = Math.max(vals.length, 1);
  const maxPos = Math.max(0, ...vals), maxNeg = Math.max(0, ...vals.map((v) => -v));
  const labH = fs + 20;
  const top = showVals && maxPos > 0 ? fs + 14 : 6;
  const bot = h - labH - (showVals && maxNeg > 0 ? fs + 14 : 4);
  const tot = maxPos + maxNeg || 1;
  const zero = top + (bot - top) * (maxPos / tot);
  const sc = (bot - top) / tot;
  const cw = w / n, bw = Math.min(cw * 0.5, 64);
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={`bu${uid}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FF7D72" /><stop offset="100%" stopColor="#D8202B" /></linearGradient>
        <linearGradient id={`bd${uid}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2658EC" /><stop offset="100%" stopColor="#72A9FF" /></linearGradient>
      </defs>
      <line x1={0} x2={w} y1={zero} y2={zero} stroke="rgba(230,230,227,0.38)" strokeWidth={2} />
      {vals.map((v, i) => {
        const bh = Math.max(4, Math.abs(v) * sc) * k;
        const x = cw * i + (cw - bw) / 2;
        const y = v >= 0 ? zero - bh : zero;
        const col = colOf(v);
        return (
          <g key={i}>
            <rect x={x - 6} y={v >= 0 ? y - 3 : y} width={bw + 12} height={bh + 3} rx={Math.min(14, bw / 3)} fill={col} opacity={0.13} />
            <rect x={x} y={y} width={bw} height={bh} rx={Math.min(9, bw / 4)} fill={v > 0 ? `url(#bu${uid})` : v < 0 ? `url(#bd${uid})` : col} />
            {showVals ? (
              <text x={cw * i + cw / 2} y={v >= 0 ? y - 11 : y + bh + fs + 4} fontSize={fs} fontWeight={800} fill={v > 0 ? "#FF8A80" : v < 0 ? "#8FB4FF" : "#E6E6E3"} textAnchor="middle" opacity={k}>
                {sgn(v)}{tiny(v)}
              </text>
            ) : null}
            <text x={cw * i + cw / 2} y={h - 4} fontSize={fs} fontWeight={800} fill={SUBC} textAnchor="middle">{labels[i]}</text>
          </g>
        );
      })}
    </svg>
  );
};

/* ───────── w0: 첫 화면(0프레임부터 한 주 큰 숫자 + 대비) → 질문 문장부터 질문 + 코스피 한 주 카드 ───────── */
export const W0: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const list = cues ?? [];
  const week = w.inv?.week ?? {};
  // 주인공: 첫 문장에서 먼저 나온 주체(말과 화면이 같게) → 없으면 한 주 절대값이 가장 큰 주체
  const first = list[0]?.text ?? "";
  const hit = INV.map((x) => ({ ...x, at: first.indexOf(x.name) })).filter((x) => x.at >= 0 && week[x.k] != null).sort((a, b) => a.at - b.at)[0];
  const biggest = [...INV].sort((a, b) => Math.abs(week[b.k] ?? 0) - Math.abs(week[a.k] ?? 0))[0];
  const pr = hit ?? biggest;
  const amt = week[pr.k] ?? 0;
  const tone = toneOf(amt);
  const chg = w.kospi?.week_chg_pct ?? 0;
  const kd = w.kospi?.days ?? [];
  const last = kd[kd.length - 1];
  const qc = list.find((c) => isQ(c.text));
  if (qc && t >= qc.start) {
    const who = /누가|누구/.test(qc.text) ? (amt < 0 ? "누가 샀을까?" : "누가 팔았을까?") : null;
    return (
      <WShell p={p} cues={cues} hideSub bg={<BgMarket tone={toneOf(chg)} dim={0.2} />}>
        {who ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(qc.start, 30) }}>
            <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.04em", textShadow: "0 6px 30px rgba(0,0,0,0.7)" }}>그럼</div>
            <div style={{ fontSize: fit(who, 950, 172), fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", color: YEL, textShadow: "0 0 36px rgba(255,216,77,0.45), 0 6px 30px rgba(0,0,0,0.7)", whiteSpace: "nowrap" }}>{who}</div>
          </div>
        ) : <QBig text={qc.text} at={qc.start} />}
        {last ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 1010, ...pop(qc.start + 0.25) }}>
            <Card color={colOf(chg)} style={{ display: "inline-block", minWidth: 640 }}>
              <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4", letterSpacing: "0.02em" }}>KOSPI <span style={{ color: SUBC, fontWeight: 700 }}>· 이번 주</span></div>
              <div style={{ fontSize: 118, fontWeight: 800, lineHeight: 1.05, marginTop: 6 }}>{fmtIdx(last.close)}</div>
              <div style={{ fontSize: 64, fontWeight: 800, color: colOf(chg), marginTop: 6 }}>{chg > 0 ? "▲" : chg < 0 ? "▼" : "−"} {Math.abs(chg).toFixed(2)}%</div>
              {w.kospi?.prev_close != null ? <div style={{ fontSize: 34, fontWeight: 700, color: SUBC, marginTop: 10 }}>지난주 마감 {fmtIdx(w.kospi.prev_close)}에서</div> : null}
            </Card>
          </div>
        ) : null}
      </WShell>
    );
  }
  const amtTxt = short(amt);
  const word = amt < 0 ? "매도" : "매수";
  const fs = fit(`${amtTxt} ${word}`, 950, 196);
  const opp = list.some((c) => /^그런데/.test(c.text.trim()) && c.text.includes("코스피")) || (amt < 0) === (chg > 0);
  return (
    <WShell p={p} cues={cues} hideSub bg={<BgCity tone={tone} dim={0.15} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 236 }}>
        <div style={{ fontSize: 62, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주</div>
        <div style={{ fontSize: 196, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.05em", textShadow: SH_BIG }}>{pr.name}</div>
        <div style={{ fontSize: fs, fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", whiteSpace: "nowrap" }}>
          <Grad tone={tone}>{amtTxt}</Grad><span style={{ textShadow: SH_BIG }}> {word}</span>
        </div>
        <div style={{ marginTop: 56 }}>
          <div style={{ fontSize: 66, fontWeight: 800, lineHeight: 1.2, textShadow: "0 4px 18px rgba(0,0,0,0.8)" }}>{opp ? "그런데 코스피는" : "코스피는"}</div>
          <div style={{ fontSize: 88, fontWeight: 900, lineHeight: 1.15, letterSpacing: "-0.03em", textShadow: "0 4px 18px rgba(0,0,0,0.8)" }}>
            한 주 <span style={{ color: YEL }}>{Math.abs(chg).toFixed(2)}%</span> {chg > 0 ? "올랐다" : chg < 0 ? "내렸다" : "제자리"}{opp ? "?" : ""}
          </div>
        </div>
      </div>
    </WShell>
  );
};

/* ───────── w1: 코스피 한 주 길(월~금 종가 5점, 지난주 마감에서 출발) + 7,000선 + 말하는 요일 강조 ───────── */
const KChart: React.FC<{ w: Wk; W: number; H: number; t0: number; span: number; hot: number[] }> = ({ w, W, H, t0, span, hot }) => {
  const { t } = useT();
  const ds = w.kospi?.days ?? [];
  const n = ds.length;
  if (!n) return null;
  const prev = w.kospi?.prev_close ?? null;
  const evs = w.kospi?.events ?? [];
  const lineV = evs.find((e) => (e.kind === "regained" || e.kind === "lost") && e.line)?.line ?? 7000;
  const L = 22, R = 124, T = 84, B = 150;
  const vals = [...ds.flatMap((x) => [x.close, x.high ?? x.close, x.low ?? x.close]), ...(prev != null ? [prev] : [])];
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const showLine = lineV >= lo - (hi - lo) * 0.4 && lineV <= hi + (hi - lo) * 0.4;
  if (showLine) { lo = Math.min(lo, lineV); hi = Math.max(hi, lineV); }
  const pad = (hi - lo) * 0.07 || 10;
  const y0 = lo - pad, y1 = hi + pad;
  const Y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const colW = (W - L - R) / n;
  const X = (i: number) => L + colW * (i + 0.5);
  const base = H - B;
  // 선: 지난주 마감(왼쪽 끝) → 월 … 금. 구간 색은 도착한 날의 등락.
  const pts = [...(prev != null ? [{ x: L, y: Y(prev) }] : []), ...ds.map((d, i) => ({ x: X(i), y: Y(d.close) }))];
  const off = prev != null ? 0 : 1;
  let acc = 0;
  const segs = pts.slice(1).map((b, j) => { const a = pts[j]; const len = Math.hypot(b.x - a.x, b.y - a.y); const s = { a, b, len, acc, col: colOf(ds[j + off]?.chg_pct) }; acc += len; return s; });
  const total = acc || 1;
  const P = interpolate(t, [t0, t0 + span], [0, 1], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const drawn = P * total;
  const segF = segs.map((s) => Math.max(0, Math.min(1, (drawn - s.acc) / (s.len || 1))));
  let headX = pts[0].x;
  segs.forEach((s, j) => { if (segF[j] > 0) headX = s.a.x + (s.b.x - s.a.x) * segF[j]; });
  if (!segs.length) headX = W;
  const reachAt = (i: number) => (prev != null ? segs[i].acc + segs[i].len : i === 0 ? 0 : segs[i - 1].acc + segs[i - 1].len);
  const kPt = (i: number) => Math.max(0, Math.min(1, (drawn - reachAt(i) + 24) / 24));
  const done = interpolate(t, [t0 + span, t0 + span + 0.45], [0, 1], CLAMP);
  const area = `M ${pts[0].x} ${base} ${pts.map((q) => `L ${q.x} ${q.y}`).join(" ")} L ${pts[pts.length - 1].x} ${base} Z`;
  const wchg = w.kospi?.week_chg_pct ?? 0;
  const aCol = wchg >= 0 ? "255,77,77" : "61,123,255";
  const anyHot = hot.length > 0;
  const lvl = (v: number, label: string, dy = 0, strong = false) => {
    const fs = Math.min(27, Math.floor((R - 40) / Math.max(emOf(label), 1)));
    return (
      <g transform={`translate(${W - R + 14}, ${Y(v) - 22 + dy})`}>
        <rect width={R - 16} height={44} rx={12} fill={strong ? YEL : "rgba(10,14,26,0.92)"} stroke={strong ? "none" : "rgba(207,214,228,0.6)"} strokeWidth={2} />
        <text x={(R - 16) / 2} y={22 + fs * 0.36} fontSize={fs} fontWeight={900} fill={strong ? "#0B0E16" : "#CFD6E4"} textAnchor="middle">{label}</text>
      </g>
    );
  };
  const evChip = (e: KEv, j: number) => {
    const i = ds.findIndex((x) => x.d === e.d);
    if (i < 0) return null;
    const dd = ds[i];
    const row = evs.slice(0, j).filter((x) => x.d === e.d).length;   // 같은 날 사건이 둘이면 아래로 한 칸
    const txt = e.kind === "regained" ? `${(e.line ?? lineV).toLocaleString("ko-KR")} 회복` : e.kind === "lost" ? `${(e.line ?? lineV).toLocaleString("ko-KR")} 이탈`
      : e.kind === "high" && dd.high != null ? `고점 ${fmtIdx(dd.high)}` : e.kind === "low" && dd.low != null ? `저점 ${fmtIdx(dd.low)}` : "";
    if (!txt) return null;
    const col = e.kind === "regained" ? RED : e.kind === "lost" ? BLUE : "#CFD6E4";
    const fs = emOf(txt) * 22 + 22 > colW - 6 ? 20 : 22, cw = Math.min(colW - 4, emOf(txt) * fs + 22);
    return (
      <g key={`${e.d}${e.kind}${j}`} opacity={Math.max(done, hot.includes(i) ? 1 : 0)} transform={`translate(0, ${row * 44})`}>
        <rect x={X(i) - cw / 2} y={14} width={cw} height={40} rx={12} fill="rgba(10,14,26,0.92)" stroke={col} strokeWidth={2} />
        <text x={X(i)} y={42} fontSize={fs} fontWeight={800} fill={col} textAnchor="middle">{txt}</text>
        {row === 0 ? <line x1={X(i)} x2={X(i)} y1={56} y2={Math.min(Y(dd.high ?? dd.close), Y(dd.close)) - 12} stroke={col} strokeOpacity={0.35} strokeWidth={2} strokeDasharray="3 6" /> : null}
      </g>
    );
  };
  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      <defs>
        <linearGradient id="wkArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={`rgba(${aCol},0.34)`} />
          <stop offset="100%" stopColor={`rgba(${aCol},0)`} />
        </linearGradient>
        <clipPath id="wkClip"><rect x={0} y={0} width={Math.max(0, headX)} height={H} /></clipPath>
      </defs>
      {/* 가로 눈금(옅게) */}
      {[0.25, 0.5, 0.75].map((r) => <line key={r} x1={L} x2={W - R + 8} y1={T + r * (base - T)} y2={T + r * (base - T)} stroke="rgba(143,167,217,0.12)" strokeWidth={2} />)}
      {/* 지난주 마감 · 7,000선 */}
      {prev != null ? <line x1={L} x2={W - R + 8} y1={Y(prev)} y2={Y(prev)} stroke="rgba(207,214,228,0.5)" strokeWidth={2.5} strokeDasharray="6 10" /> : null}
      {showLine ? <line x1={L} x2={W - R + 8} y1={Y(lineV)} y2={Y(lineV)} stroke={YEL} strokeOpacity={0.9} strokeWidth={3} strokeDasharray="16 12" /> : null}
      {/* 요일 강조 세로선 */}
      {hot.map((i) => <rect key={`h${i}`} x={X(i) - colW / 2 + 6} y={T - 16} width={colW - 12} height={base - T + 16} rx={18} fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.22)" strokeWidth={2} />)}
      {/* 하루 고가~저가 막대(실제 고가·저가) */}
      {ds.map((d, i) => d.high != null && d.low != null ? (
        <rect key={`r${i}`} x={X(i) - 14} y={Y(d.high)} width={28} height={Math.max(6, Y(d.low) - Y(d.high))} rx={14} fill={colOf(d.chg_pct)} fillOpacity={0.16} stroke={colOf(d.chg_pct)} strokeOpacity={0.55} strokeWidth={2} opacity={kPt(i)} />
      ) : null)}
      {/* 면 + 선(그려지며 나타남) */}
      <path d={area} fill="url(#wkArea)" clipPath="url(#wkClip)" />
      {segs.map((s, j) => segF[j] > 0 ? (
        <g key={`s${j}`}>
          <line x1={s.a.x} y1={s.a.y} x2={s.b.x} y2={s.b.y} stroke={s.col} strokeOpacity={0.22} strokeWidth={20} strokeLinecap="round" strokeDasharray={s.len} strokeDashoffset={s.len * (1 - segF[j])} />
          <line x1={s.a.x} y1={s.a.y} x2={s.b.x} y2={s.b.y} stroke={s.col} strokeWidth={7} strokeLinecap="round" strokeDasharray={s.len} strokeDashoffset={s.len * (1 - segF[j])} />
        </g>
      ) : null)}
      {prev != null ? <circle cx={pts[0].x} cy={pts[0].y} r={8} fill="#CFD6E4" opacity={P > 0 ? 1 : 0} /> : null}
      {/* 점 + 종가 */}
      {ds.map((d, i) => {
        const k = kPt(i);
        const on = hot.includes(i);
        const y = Y(d.close);
        const ny = [i > 0 ? Y(ds[i - 1].close) : prev != null ? Y(prev) : null, i < n - 1 ? Y(ds[i + 1].close) : null].filter((v): v is number => v != null);
        const up = !ny.length || y <= ny.reduce((a, b) => a + b, 0) / ny.length;
        const ly = up ? Math.min(y, d.high != null ? Y(d.high) : y) - 18 : Math.max(y, d.low != null ? Y(d.low) : y) + (on ? 46 : 40);
        const col = colOf(d.chg_pct);
        return (
          <g key={`p${i}`} opacity={k}>
            <circle cx={X(i)} cy={y} r={on ? 19 : 13} fill="#0B0E16" stroke={col} strokeWidth={on ? 7 : 5} />
            {on ? <circle cx={X(i)} cy={y} r={30} fill="none" stroke={col} strokeOpacity={0.35} strokeWidth={3} /> : null}
            <text x={X(i)} y={ly} fontSize={on ? 36 : 30} fontWeight={on ? 900 : 800} fill="#FFFFFF" fillOpacity={anyHot && !on ? 0.7 : 1} textAnchor="middle"
              stroke="#05070D" strokeWidth={8} strokeLinejoin="round" paintOrder="stroke">{fmtIdx(d.close)}</text>
          </g>
        );
      })}
      {/* 오른쪽 기준선 이름표 */}
      {prev != null ? (
        <g opacity={P > 0 ? 1 : 0}>
          <text x={W - R + 14 + (R - 16) / 2} y={Y(prev) + (showLine && Math.abs(Y(prev) - Y(lineV)) < 60 ? 42 : 0) - 30} fontSize={20} fontWeight={800} fill={SUBC} textAnchor="middle">지난주</text>
          {lvl(prev, fmtIdx(prev), showLine && Math.abs(Y(prev) - Y(lineV)) < 60 ? 42 : 0)}
        </g>
      ) : null}
      {showLine ? lvl(lineV, lineV.toLocaleString("ko-KR"), 0, true) : null}
      {/* 사건 칩(7,000 회복/이탈, 주간 고점) */}
      {evs.map(evChip)}
      {/* 요일 · 등락 */}
      {ds.map((d, i) => {
        const on = hot.includes(i);
        const c = d.chg_pct ?? 0;
        return (
          <g key={`l${i}`} opacity={anyHot && !on ? 0.6 : 1}>
            {on ? <rect x={X(i) - colW / 2 + 10} y={base + 14} width={colW - 20} height={118} rx={16} fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.45)" strokeWidth={2} /> : null}
            <text x={X(i)} y={base + 64} fontSize={44} fontWeight={900} fill="#FFFFFF" textAnchor="middle">{wdOf(d.d)}<tspan fontSize={22} fontWeight={700} fill={SUBC} dx={6}>{md(d.d)}</tspan></text>
            <text x={X(i)} y={base + 110} fontSize={29} fontWeight={800} fill={colOf(c)} textAnchor="middle">{c > 0 ? "▲" : c < 0 ? "▼" : ""}{Math.abs(c).toFixed(2)}%</text>
          </g>
        );
      })}
    </svg>
  );
};

export const W1: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const { cur } = curCue(cues, t);
  const kd = w.kospi?.days ?? [];
  const last = kd[kd.length - 1];
  const chg = w.kospi?.week_chg_pct ?? 0;
  const hot = cur && t < cur.end + 0.6 ? dayHits(cur.text, kd.map((x) => x.d)) : [];
  const q = cur && isQ(cur.text) ? cur : undefined;
  return (
    <WShell p={p} cues={cues} hideSub={!!q} bg={<BgMarket tone={toneOf(chg)} dim={0.42} />}>
      {q ? <QBig text={q.text} at={q.start} top={236} small /> : null}
      <div style={{ position: "absolute", left: 64, right: 64, top: 226, height: 330 }}>
        {q ? null : (
          <div style={pop(0.05, 20)}>
            <div style={{ fontSize: 56, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주 코스피</div>
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginTop: 2 }}>
              <div style={{ fontSize: 158, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.0 }}><Grad tone={toneOf(chg)}>{sgn(chg)}{Math.abs(chg).toFixed(2)}%</Grad></div>
              {last ? (
                <div style={{ textAlign: "right", paddingBottom: 14, textShadow: SH }}>
                  <div style={{ fontSize: 58, fontWeight: 900, lineHeight: 1.1 }}>{fmtIdx(last.close)}</div>
                  {w.kospi?.prev_close != null ? <div style={{ fontSize: 30, fontWeight: 700, color: SUBC }}>지난주 {fmtIdx(w.kospi.prev_close)}</div> : null}
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(0.15, 24) }}>
        <Card color={colOf(chg)} style={{ padding: "18px 26px" }}>
          <KChart w={w} W={892} H={860} t0={0.35} span={1.5} hot={hot} />
        </Card>
      </div>
    </WShell>
  );
};

/* ───────── w2: 한 주 누가 샀나·팔았나 — 주체 카드 4장(한 주 합계 + 5일 막대). 이름을 말할 때 카드가 뜨고 밝아진다.
   기타법인 종목(자사주)을 말하는 동안은 종목 카드로 바뀐다. 질문 문장은 질문만. ───────── */
export const W2: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const { list, i: ci, cur } = curCue(cues, t);
  const ds = weekDays(w);
  const invDays = w.inv?.days ?? [];
  const week = w.inv?.week ?? {};
  const series = (k: InvKey) => ds.map((d) => invDays.find((x) => x.d === d)?.[k] ?? 0);
  const cards = INV.filter((x) => week[x.k] != null).sort((a, b) => (week[b.k] ?? 0) - (week[a.k] ?? 0));
  /** '5일 모두 순매수' / '금요일까지 사흘째 순매도' / '순매수 4일 · 순매도 1일' + 색 */
  const streakOf = (k: InvKey): [string, string] => {
    const ser = series(k);
    const pos = ser.filter((d) => d > 0).length, neg = ser.filter((d) => d < 0).length;
    const st = w.inv?.streak_end?.[k];
    if (ser.length && pos === ser.length) return [`${ser.length}일 모두 순매수`, RED];
    if (ser.length && neg === ser.length) return [`${ser.length}일 모두 순매도`, "#8FB4FF"];
    if (st != null && Math.abs(st) >= 2) return [`${ds.length ? `${wdOf(ds[ds.length - 1])}요일까지 ` : ""}${daysKo(Math.abs(st))} ${st > 0 ? "순매수" : "순매도"}`, st > 0 ? RED : "#8FB4FF"];
    return [`순매수 ${pos}일 · 순매도 ${neg}일`, SUBC];
  };
  // 문장의 '주인공' = 가장 먼저 나온 주체 이름
  const lead = (s: string) => INV.map((x) => ({ x, at: s.indexOf(x.name) })).filter((o) => o.at >= 0).sort((a, b) => a.at - b.at)[0]?.x.k;
  const leadIdx = list.map((c) => lead(c.text));
  const anyNamed = leadIdx.some(Boolean);
  const appearAt = (k: InvKey, slot: number) => {
    if (!anyNamed) return 0.2 + slot * 0.25;
    const i = leadIdx.indexOf(k);
    if (i >= 0) return list[i].start;
    const j = list.findIndex((c) => c.text.includes(INV.find((x) => x.k === k)!.name));
    return j >= 0 ? list[j].start : list.length ? list[list.length - 1].start : 0.2 + slot * 0.25;
  };
  const activeK = cur && !isQ(cur.text) ? leadIdx[ci] : undefined;
  // 기타법인 종목 구간: 종목 이름(또는 자사주)을 말하는 문장들
  const os = w.others_stocks ?? {};
  const total = week.others ?? 0;
  const rows = (os.week ?? []).filter((x) => x.v > 0 && (total <= 0 || x.v >= total * 0.03)).slice(0, 3);
  const bbNames = new Set((w.buybacks ?? []).flatMap((b) => [b.name, b.code ?? ""]));
  const stockCue = (s: string) => rows.some((x) => s.includes(x.name)) || /자사주/.test(s);
  const oFrom = rows.length ? findIdx(list, (s) => rows.some((x) => s.includes(x.name))) : -1;
  let oTo = oFrom;
  if (oFrom >= 0) for (let j = oFrom + 1; j < list.length && stockCue(list[j].text); j++) oTo = j;
  if (cur && isQ(cur.text)) {
    return (
      <WShell p={p} cues={cues} hideSub bg={<BgCity tone={toneOf(week.others ?? 0)} dim={0.3} />}>
        <QBig text={cur.text} at={cur.start} />
      </WShell>
    );
  }
  if (oFrom >= 0 && ci >= oFrom && ci <= oTo) {
    const o0 = list[oFrom].start;
    const [stTxt, stCol] = streakOf("others");
    const bbRows = rows.filter((x) => bbNames.has(x.name) || (x.code != null && bbNames.has(x.code)));
    const share = os.buyback_share;
    return (
      <WShell p={p} cues={cues} bg={<BgCity tone="up" dim={0.3} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
          <div style={{ fontSize: 56, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>기타법인 · 이번 주 순매수</div>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
            <div style={{ fontSize: 176, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.02 }}><Grad tone={toneOf(total)}>{sgn(total)}{short(total)}</Grad></div>
            <div style={{ fontSize: 42, fontWeight: 900, color: stCol, paddingBottom: 26, textShadow: SH }}>{stTxt}</div>
          </div>
        </div>
        <div style={{ position: "absolute", left: 64, right: 64, top: 540 }}>
          <Card color={RED} style={pop(o0 + 0.15)}>
            <div style={{ fontSize: 38, fontWeight: 800, color: "#CFD6E4" }}>가장 많이 산 종목 <span style={{ color: SUBC, fontWeight: 700, fontSize: 32 }}>({ds.length}일 합계)</span></div>
            {rows.map((x, k) => (
              <div key={x.name} style={{ ...pop(o0 + 0.55 + k * 0.25), display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
                <span style={{ fontSize: 60, fontWeight: 900, display: "flex", alignItems: "center", gap: 16 }}>
                  {x.name}
                  {bbNames.has(x.name) || (x.code != null && bbNames.has(x.code)) ? <span style={{ fontSize: 28, fontWeight: 800, color: "#0B0E16", background: YEL, borderRadius: 10, padding: "4px 12px" }}>자사주</span> : null}
                </span>
                <span style={{ fontSize: 58, fontWeight: 900, color: RED }}>+{fmtEok(x.v)}</span>
              </div>
            ))}
            {bbRows.length ? (
              <div style={{ fontSize: 34, color: YEL, fontWeight: 700, marginTop: 20, lineHeight: 1.35, wordBreak: "keep-all" }}>
                {bbRows.length >= 2 ? "두 회사 모두" : bbRows[0].name} 자사주 매입 중 · 회사가 자기 주식을 사면 기타법인으로 집계
              </div>
            ) : null}
            {share != null && share > 0 ? (
              <div style={{ ...pop(o0 + 1.1), display: "flex", alignItems: "baseline", justifyContent: "space-between", marginTop: 22, paddingTop: 18, borderTop: "2px solid rgba(255,77,77,0.35)" }}>
                <span style={{ fontSize: 36, fontWeight: 800, color: "#E6E6E3" }}>기타법인 순매수 중 자사주 매입 종목</span>
                <span style={{ fontSize: 64, fontWeight: 900 }}><span style={{ fontSize: 36, color: "#E6E6E3" }}>약 </span><Grad tone="up">{Math.round(share * 100)}%</Grad></span>
              </div>
            ) : null}
          </Card>
        </div>
      </WShell>
    );
  }
  // 첫 공개: 처음 이름이 나온 주체 하나만 보이는 동안은 크게(일간 s2의 답 공개와 같은 무게)
  const firstK = leadIdx.find((k): k is InvKey => !!k);
  const shown = cards.filter((x, slot) => t >= appearAt(x.k, slot)).length;
  if (firstK && shown <= 1 && ci >= 0) {
    const fi = leadIdx.indexOf(firstK);
    const r0 = list[fi].start;
    const v = week[firstK] ?? 0;
    const nm = INV.find((x) => x.k === firstK)!.name;
    const ctx = list.slice(0, fi + 1).map((c) => c.text).join(" ");   // 앞 질문('누가 가장 많이 샀을까요?')까지 본다
    const lab = v > 0 && /가장 많이 산|누가.*샀/.test(ctx) ? "이번 주 가장 많이 산 쪽은" : v < 0 && /가장 많이 판|누가.*팔/.test(ctx) ? "이번 주 가장 많이 판 쪽은" : "이번 주";
    const [stTxt, stCol] = streakOf(firstK);
    return (
      <WShell p={p} cues={cues} bg={<BgCity tone={toneOf(v)} dim={0.25} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 230 }}>
          <div style={{ fontSize: 58, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>{lab}</div>
          <div style={{ ...pop(r0, 30), fontSize: 184, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", marginTop: 6, textShadow: SH_BIG }}>{nm}</div>
          <div style={{ ...pop(r0 + 0.3, 30), fontSize: 200, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.05em", marginTop: 4 }}><Grad tone={toneOf(v)}>{sgn(v)}{short(v)}</Grad></div>
          <div style={{ ...pop(r0 + 0.55), fontSize: 50, fontWeight: 900, color: stCol, marginTop: 14, textShadow: SH }}>{stCol === RED ? "▲ " : stCol === SUBC ? "" : "▼ "}{stTxt}</div>
        </div>
        <div style={{ position: "absolute", left: 64, right: 64, top: 1000 }}>
          <Card color={colOf(v)} style={pop(r0 + 0.5)}>
            <div style={{ fontSize: 38, fontWeight: 800, color: "#CFD6E4" }}>하루씩 보면 <span style={{ fontSize: 30, color: SUBC, fontWeight: 700 }}>· 코스피</span></div>
            <div style={{ marginTop: 18 }}>
              <Bars vals={series(firstK)} labels={ds.map(wdOf)} w={880} h={300} at={r0 + 0.7} showVals fs={30} />
            </div>
          </Card>
        </div>
      </WShell>
    );
  }
  return (
    <WShell p={p} cues={cues} bg={<BgCity tone="neutral" dim={0.38} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 224, display: "flex", flexDirection: "column", gap: 22 }}>
        {cards.map((x, slot) => {
          const v = week[x.k] ?? 0;
          const ser = series(x.k);
          const at = appearAt(x.k, slot);
          const [stTxt, stCol] = streakOf(x.k);
          const on = activeK === x.k;
          const po = pop(at);
          return (
            <Card key={x.k} color={colOf(v)} style={{ ...po, opacity: (po.opacity as number) * (activeK && !on ? 0.66 : 1), padding: "20px 30px", display: "flex", alignItems: "center", justifyContent: "space-between",
              boxShadow: on ? `0 0 48px ${colOf(v)}99, inset 0 0 26px ${colOf(v)}33` : `0 0 34px ${colOf(v)}66, inset 0 0 22px ${colOf(v)}22` }}>
              <div>
                <div style={{ fontSize: 50, fontWeight: 900, lineHeight: 1.15 }}>{x.name}</div>
                <div style={{ fontSize: fit(`${sgn(v)}${short(v)}`, 470, 124), fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.04 }}><Grad tone={toneOf(v)}>{sgn(v)}{short(v)}</Grad></div>
                <div style={{ fontSize: 30, fontWeight: 800, color: stCol, marginTop: 4 }}>{stTxt}</div>
              </div>
              <Bars vals={ser} labels={ds.map(wdOf)} w={380} h={200} at={at + 0.15} fs={26} />
            </Card>
          );
        })}
      </div>
    </WShell>
  );
};

/* ───────── w3: 한 주 돈이 빠진 곳(크게) → 들어온 곳·머문 곳(목록). 질문 문장은 질문만. ───────── */
const ThemeBlock: React.FC<{ th: ThemeW; ds: string[]; at: number; head: string; hBars?: number }> = ({ th, ds, at, head, hBars = 380 }) => {
  const pop = usePop();
  const ser = ds.map((d) => th.days?.find((x) => x.d === d)?.net ?? 0);
  const pos = th.pos_days ?? ser.filter((v) => v > 0).length;
  const col = th.net < 0 ? BLUE : RED;
  return (
    <Card color={col} style={pop(at)}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ fontSize: 40, fontWeight: 800 }}>{head} <span style={{ fontSize: 30, color: SUBC, fontWeight: 700 }}>(외국인+기관 합산)</span></div>
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginTop: 6 }}>
        <div style={{ fontSize: 112, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.05 }}><Grad tone={toneOf(th.net)}>{sgn(th.net)}{short(th.net)}</Grad></div>
        <div style={{ textAlign: "right", paddingBottom: 14, fontSize: 34, fontWeight: 800, lineHeight: 1.35 }}>
          {th.foreign != null ? <div>외국인 <span style={{ color: colOf(th.foreign) }}>{sgn(th.foreign)}{tiny(th.foreign)}</span></div> : null}
          {th.inst != null ? <div>기관 <span style={{ color: colOf(th.inst) }}>{sgn(th.inst)}{tiny(th.inst)}</span></div> : null}
        </div>
      </div>
      <div style={{ marginTop: 18 }}>
        <Bars vals={ser} labels={ds.map(wdOf)} w={880} h={hBars} at={at + 0.3} showVals fs={28} />
      </div>
      <div style={{ fontSize: 34, fontWeight: 800, color: "#E6E6E3", marginTop: 14 }}>{ser.length}일 중 <span style={{ color: RED }}>{pos}일 순매수</span> · <span style={{ color: "#8FB4FF" }}>{ser.filter((v) => v < 0).length}일 순매도</span></div>
    </Card>
  );
};

export const W3: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const { list, i: ci, cur } = curCue(cues, t);
  const ds = weekDays(w);
  const th = w.themes ?? {};
  const out = th.top_out && th.top_out.net < 0 ? th.top_out : null;
  const inn = th.top_in && th.top_in.net > 0 ? th.top_in : null;
  const stayed = (th.stayed ?? []).map((n) => (th.week ?? []).find((x) => x.theme === n)).filter((x): x is ThemeW => !!x);
  const outIdx = out ? findIdx(list, (s) => has(s, out.theme)) : -1;
  let inIdx = inn ? findIdx(list, (s) => has(s, inn.theme) || /들어온|들어갔/.test(s), outIdx + 1) : -1;
  if (inn && inIdx < 0 && !out) inIdx = 0;
  const stIdx = stayed.length ? findIdx(list, (s) => stayed.some((x) => x.theme !== inn?.theme && has(s, x.theme)) || /나흘|머문|이어진 곳/.test(s), Math.max(inIdx, 0)) : -1;
  const firstStage = [outIdx, inIdx].filter((x) => x >= 0).sort((a, b) => a - b)[0] ?? list.length;
  // 질문(단계 공개 전 질문 문장)
  if (cur && isQ(cur.text) && (ci < firstStage || !out)) {
    const lead = out ?? inn;
    const Bg = lead?.theme === "반도체" ? BgChip : BgMarket;
    return (
      <WShell p={p} cues={cues} hideSub bg={<Bg tone={toneOf(lead?.net)} dim={0.3} />}>
        <QBig text={cur.text} at={cur.start} />
      </WShell>
    );
  }
  const listStage = inn && inIdx >= 0 && ci >= inIdx;
  if (!listStage && out) {
    const r0 = outIdx >= 0 ? list[outIdx].start : 0.1;
    const Bg = out.theme === "반도체" ? BgChip : BgMarket;
    return (
      <WShell p={p} cues={cues} bg={<Bg tone="down" dim={0.3} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 236 }}>
          <div style={{ fontSize: 58, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주 가장 큰 돈이 빠진 곳은</div>
          <div style={{ ...pop(r0, 34), fontSize: fit(out.theme, 950, 210), fontWeight: 900, lineHeight: 1.06, letterSpacing: "-0.05em", marginTop: 8, whiteSpace: "nowrap" }}><Grad tone="down">{out.theme}</Grad></div>
        </div>
        <div style={{ position: "absolute", left: 64, right: 64, top: 640 }}>
          <ThemeBlock th={out} ds={ds} at={r0 + 0.4} head={`${out.theme} · 한 주 순매도`} hBars={420} />
        </div>
      </WShell>
    );
  }
  if (!inn) return <WShell p={p} cues={cues} bg={<BgMarket tone="neutral" />}>{null}</WShell>;
  const i0 = inIdx >= 0 ? list[inIdx].start : 0.1;
  const s0 = stIdx >= 0 ? list[stIdx].start : i0 + 1.6;
  const Bg = inn.theme === "반도체" ? BgChip : BgMarket;
  const stayRows = stayed.slice(0, 3);
  return (
    <WShell p={p} cues={cues} bg={<Bg tone="up" dim={0.34} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 230 }}>
        <div style={{ fontSize: 56, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주 가장 많이 들어온 곳은</div>
        <div style={{ ...pop(i0, 34), fontSize: fit(inn.theme, 950, 188), fontWeight: 900, lineHeight: 1.06, letterSpacing: "-0.05em", marginTop: 4, whiteSpace: "nowrap" }}><Grad tone="up">{inn.theme}</Grad></div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 520 }}>
        <ThemeBlock th={inn} ds={ds} at={i0 + 0.35} head={`${inn.theme} · 한 주 순매수`} hBars={stayRows.length ? 340 : 400} />
        {stayRows.length ? (
          <Card color={RED} style={{ ...pop(s0), marginTop: 28, padding: "22px 34px 26px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "250px 1fr 250px", alignItems: "center" }}>
              <span style={{ fontSize: 36, fontWeight: 800, color: "#CFD6E4", gridColumn: "1 / span 3", marginBottom: 8 }}>{ds.length}일 중 {Math.min(...stayRows.map((x) => x.pos_days ?? ds.filter((d) => (x.days?.find((y) => y.d === d)?.net ?? 0) > 0).length))}일 이상 순매수</span>
              <span />
              <span style={{ display: "flex", justifyContent: "center", gap: 14 }}>{ds.map((d) => <span key={d} style={{ width: 34, textAlign: "center", fontSize: 24, fontWeight: 800, color: SUBC }}>{wdOf(d)}</span>)}</span>
              <span />
              {stayRows.map((x, k) => {
                const ser = ds.map((d) => x.days?.find((y) => y.d === d)?.net ?? 0);
                const st = pop(s0 + 0.2 + k * 0.2);
                return (
                  <React.Fragment key={x.theme}>
                    <span style={{ ...st, fontSize: 54, fontWeight: 900, whiteSpace: "nowrap", marginTop: 10 }}>{x.theme}</span>
                    <span style={{ ...st, display: "flex", justifyContent: "center", gap: 14, marginTop: 10 }}>
                      {ser.map((v, j) => <span key={j} style={{ width: 34, height: 34, borderRadius: 17, background: v > 0 ? RED : v < 0 ? BLUE : "#3A4150", boxShadow: v > 0 ? "0 0 12px rgba(255,77,77,0.55)" : "none" }} />)}
                    </span>
                    <span style={{ ...st, fontSize: 50, fontWeight: 900, color: colOf(x.net), textAlign: "right", whiteSpace: "nowrap", marginTop: 10 }}>{sgn(x.net)}{tiny(x.net)}</span>
                  </React.Fragment>
                );
              })}
            </div>
          </Card>
        ) : null}
      </div>
    </WShell>
  );
};

/* ───────── w4: 이번 주 겹친 뉴스 — 날짜 칩 + 제목 + 연결 한 줄, 말하는 순서대로 한 장씩 ───────── */
const newsLine = (n: News) => [n.line, n.link, n.text, n.why, n.note].find((x) => !!x && !/^https?:\/\//i.test(x.trim())) ?? "";
const newsDay = (n: News) => { const s = (n.d ?? n.date ?? "").replace(/[^0-9]/g, ""); return s.length >= 8 ? s.slice(0, 8) : ""; };

export const W4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t, dur } = useT();
  const pop = usePop();
  const { list, i: ci, cur } = curCue(cues, t);
  const items = (w.news ?? []).filter((n) => n.title).slice(0, 3);
  const kd = w.kospi?.days ?? [];
  // 카드 k가 뜨는 문장: 그 날짜(요일)나 제목 낱말을 말하는 첫 문장. 못 찾으면 고르게 나눈 시각.
  let from = 0;
  const reveal = items.map((n, k) => {
    const d = newsDay(n);
    const words = (n.title ?? "").replace(/[\[\](){}'"‘’“”…·,.!?]/g, " ").split(/\s+/).filter((x) => x.length >= 3 && !/코스피|마감|하락|상승/.test(x));
    const i = findIdx(list, (s) => (d ? dayHits(s, [d]).length > 0 : false) || words.some((x) => s.includes(x)), from);
    if (i >= 0) { from = i + 1; return { at: list[i].start, idx: i }; }
    const span = Math.max(dur - 1, 3);
    return { at: 0.4 + (span * k) / Math.max(items.length, 1), idx: -1 };
  });
  if (cur && isQ(cur.text) && !reveal.some((r) => r.idx === ci)) {
    return (
      <WShell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.35} />}>
        <QBig text={cur.text} at={cur.start} />
      </WShell>
    );
  }
  if (!items.length) {
    // 기사 목록이 비었으면(뉴스 수집 실패 등) 지금 말하는 문장을 카드로 — 빈 화면 방지
    const txt = glue(cur?.text ?? "");
    return (
      <WShell p={p} cues={cues} hideSub={!!txt} bg={<BgCity tone="neutral" dim={0.42} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 228 }}>
          <div style={{ ...pop(0.05, 20), fontSize: 60, fontWeight: 900, textShadow: SH }}>이번 주 <span style={{ color: YEL }}>겹친 뉴스</span></div>
          {txt ? (
            <Card color="#CFD6E4" style={{ ...pop(cur?.start ?? 0.1), marginTop: 40, padding: "48px 46px" }}>
              <div key={cur?.start} style={{ fontSize: txt.length <= 30 ? 84 : 70, fontWeight: 900, lineHeight: 1.3, letterSpacing: "-0.03em", wordBreak: "keep-all" }}><Hi text={txt} /></div>
            </Card>
          ) : null}
        </div>
      </WShell>
    );
  }
  const shown = reveal.map((r) => t >= r.at);
  const hotK = shown.lastIndexOf(true);
  return (
    <WShell p={p} cues={cues} bg={<BgCity tone="neutral" dim={0.42} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 228 }}>
        <div style={{ ...pop(0.05, 20), fontSize: 60, fontWeight: 900, textShadow: SH }}>이번 주 <span style={{ color: YEL }}>겹친 뉴스</span></div>
        <div style={{ ...pop(0.2, 20), fontSize: 32, fontWeight: 700, color: SUBC, marginTop: 6, textShadow: SH }}>같은 날 수급과 함께 본 기사 · 원인 단정 아님</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 400, display: "flex", flexDirection: "column", gap: 26 }}>
        {items.map((n, k) => {
          const d = newsDay(n);
          const kday = kd.find((x) => x.d === d);
          const c = kday?.chg_pct ?? null;
          const col = c == null ? "#CFD6E4" : colOf(c);
          const po = pop(reveal[k].at);
          const on = k === hotK;
          const line = newsLine(n);
          const src = n.src ?? n.source ?? "";
          return (
            <Card key={k} color={col} style={{ ...po, opacity: (po.opacity as number) * (on ? 1 : 0.55), padding: "24px 32px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                {d ? <span style={{ fontSize: 34, fontWeight: 900, color: c ? "#FFFFFF" : "#0B0E16", background: col, borderRadius: 12, padding: "4px 16px" }}>{md(d)} {wdOf(d)}</span> : null}
                {c != null ? <span style={{ fontSize: 32, fontWeight: 800, color: col }}>코스피 {c > 0 ? "▲" : c < 0 ? "▼" : ""}{Math.abs(c).toFixed(2)}%</span> : null}
                {src ? <span style={{ marginLeft: "auto", fontSize: 26, fontWeight: 700, color: "#8E96A8", whiteSpace: "nowrap" }}>{src}</span> : null}
              </div>
              <div style={{ fontSize: 46, fontWeight: 900, lineHeight: 1.28, marginTop: 14, wordBreak: "keep-all", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{n.title}</div>
              {line ? (
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start", fontSize: 36, fontWeight: 800, color: "#E6E6E3", marginTop: 14, lineHeight: 1.3, wordBreak: "keep-all" }}>
                  <span style={{ color: YEL, flex: "none" }}>↳</span><span>{line}</span>
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>
    </WShell>
  );
};

/* ───────── w5: 우리 시각 — 큰 문장 카드 하나(p.view가 있으면 그 문장, 없으면 지금 말하는 문장) ───────── */
export const W5: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const { cur } = curCue(cues, t);
  const fixed = typeof w.view === "string" ? w.view : w.view?.text ?? "";
  const text = glue((fixed || cur?.text || sub || "").trim().replace(/^(정리하면|요약하면),?\s*/, ""));
  const at = fixed ? 0.1 : cur?.start ?? 0.1;
  const fs = text.length <= 18 ? 104 : text.length <= 30 ? 92 : text.length <= 44 ? 80 : 68;
  const chg = w.kospi?.week_chg_pct ?? 0;
  const week = w.inv?.week ?? {};
  const tiles = INV.filter((x) => week[x.k] != null).sort((a, b) => Math.abs(week[b.k] ?? 0) - Math.abs(week[a.k] ?? 0));
  return (
    <WShell p={p} cues={cues} hideSub={!fixed} bg={<BgCity tone={toneOf(chg)} dim={0.32} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 290 }}>
        <div style={{ ...pop(0.05, 20), display: "flex", alignItems: "center", gap: 18, fontSize: 46, fontWeight: 900, textShadow: SH }}>
          <span style={{ width: 16, height: 16, borderRadius: 8, background: RED, boxShadow: "0 0 14px rgba(255,77,77,0.8)" }} />
          이번 주를 한 줄로
        </div>
        <Card color="#CFD6E4" style={{ ...pop(0.2), position: "relative", marginTop: 30, padding: "76px 50px 56px", minHeight: 480, display: "flex", alignItems: "center" }}>
          <div style={{ position: "absolute", left: 38, top: 6, fontSize: 150, fontWeight: 900, lineHeight: 1, color: RED, opacity: 0.85, fontFamily: "Georgia, 'Times New Roman', serif" }}>“</div>
          <div key={at} style={{ ...pop(at, 18), fontSize: fs, fontWeight: 900, lineHeight: 1.32, letterSpacing: "-0.03em", wordBreak: "keep-all" }}><Hi text={text} /></div>
        </Card>
        {tiles.length ? (
          <div style={{ ...pop(0.45, 16), display: "grid", gridTemplateColumns: `repeat(${tiles.length}, 1fr)`, marginTop: 26, borderRadius: 20, border: "1.5px solid rgba(207,214,228,0.22)", background: "rgba(8,11,20,0.78)" }}>
            {tiles.map((x, k) => {
              const v = week[x.k] ?? 0;
              return (
                <div key={x.k} style={{ padding: "18px 0 20px", textAlign: "center", borderLeft: k ? "1.5px solid rgba(207,214,228,0.16)" : "none" }}>
                  <div style={{ fontSize: 30, fontWeight: 800, color: SUBC }}>{x.name}</div>
                  <div style={{ fontSize: 50, fontWeight: 900, letterSpacing: "-0.03em", marginTop: 2 }}><Grad tone={toneOf(v)}>{sgn(v)}{short(v)}</Grad></div>
                </div>
              );
            })}
          </div>
        ) : null}
        <div style={{ ...pop(0.6, 16), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 22, textShadow: SH }}>이번 주 투자자별 순매수 합계(코스피)로 본 해석 · 추천 아님</div>
      </div>
    </WShell>
  );
};

/* ───────── w6: 이번 주 확인 기록 → 다음 주 볼 것 하나 → 끝 인사 ───────── */
const shortQ = (q: string) => q.replace(/(이|가)\s+(\S+째)\s+이어지는지$/, " $2").replace(/(이|가)\s+이어지는지$/, "").replace(/(이|가)\s+멈추는지$/, " 멈춤").replace(/는지$/, "").trim();

export const W6: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const list = cues ?? [];
  const checks = w.checks ?? [];
  const done = checks.filter((c) => c.ok != null);
  const okN = done.filter((c) => c.ok).length;
  const endIdx = findIdx(list, (s) => /누가샀나였습니다|올라옵니다|오후 4시|다음 주에 (뵙|만나)/.test(s));
  const nextIdx = findIdx(list, (s) => /다음 주|볼 것|봅니다\.?$/.test(s));
  const endAt = endIdx >= 0 ? list[endIdx].start : list.length ? list[list.length - 1].end + 0.15 : 1e9;
  const nextAt = nextIdx >= 0 ? list[nextIdx].start : list.length >= 2 ? list[Math.floor(list.length / 2)].start : 3;
  if (t >= endAt) {
    return (
      <WShell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.2} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(endAt + 0.05, 30) }}>
          <Logo scale={2.4} />
          <div style={{ fontSize: 64, fontWeight: 800, marginTop: 190, textShadow: SH }}>국장 마감은 매일</div>
          <div style={{ fontSize: 120, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: SH_Q }}>저녁 5시</div>
        </div>
      </WShell>
    );
  }
  const nx = w.next_week ?? w.next ?? null;
  const nCue = nextIdx >= 0 ? list[nextIdx].text : "";
  const nq = (nx?.q ?? nCue.replace(/^다음 주\s*(\S+엔\s*)?/, "").replace(/[을를]?\s*봅니다\.?$/, "")).replace(/\s+/g, " ").trim();
  const nday = nx?.day ?? "다음 주";
  return (
    <WShell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.45} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
        <div style={{ ...pop(0.05), fontSize: 56, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주 확인한 것</div>
        {done.length ? (
          <div style={{ ...pop(0.15), display: "flex", alignItems: "baseline", gap: 26, marginTop: 4, textShadow: SH }}>
            <span style={{ fontSize: 132, fontWeight: 900, letterSpacing: "-0.04em" }}>{done.length}번</span>
            <span style={{ fontSize: 56, fontWeight: 900 }}>이어짐 <span style={{ color: GREEN }}>{okN}</span></span>
            <span style={{ fontSize: 56, fontWeight: 900 }}>끊김 <span style={{ color: RED }}>{done.length - okN}</span></span>
          </div>
        ) : null}
        {checks.length ? (
          <Card color="#8FA7D9" style={{ ...pop(0.35), marginTop: 22, padding: "16px 30px" }}>
            {checks.slice(0, 5).map((c, k) => {
              const col = c.ok == null ? SUBC : c.ok ? GREEN : RED;
              return (
                <div key={k} style={{ ...pop(0.5 + k * 0.2, 16), display: "flex", alignItems: "center", gap: 20, padding: "14px 0", borderTop: k ? "2px solid rgba(143,167,217,0.18)" : "none" }}>
                  <span style={{ fontSize: 32, fontWeight: 800, color: SUBC, width: 118, whiteSpace: "nowrap" }}>{c.d && c.d.length >= 8 ? `${md(c.d)} ${wdOf(c.d)}` : ""}</span>
                  <span style={{ flex: 1, fontSize: 42, fontWeight: 900, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{shortQ(c.q)}</span>
                  <span style={{ fontSize: 32, fontWeight: 900, color: "#0B0E16", background: col, borderRadius: 10, padding: "4px 14px", whiteSpace: "nowrap" }}>{c.ok == null ? "확인 중" : c.ok ? "이어짐" : "끊김"}</span>
                </div>
              );
            })}
          </Card>
        ) : null}
        {nq ? (
          <Card color={YEL} style={{ ...pop(nextAt), marginTop: 36 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 40, fontWeight: 800, color: YEL }}>
              <svg width="40" height="40" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2.5" fill="none" stroke={YEL} strokeWidth="2" /><path d="M3 10h18M8 3v4M16 3v4" stroke={YEL} strokeWidth="2" /></svg>
              {nday} 볼 것 하나
            </div>
            <div style={{ fontSize: 62, fontWeight: 900, lineHeight: 1.25, marginTop: 12, wordBreak: "keep-all" }}>{nq}</div>
          </Card>
        ) : null}
      </div>
    </WShell>
  );
};

/** 장면 id → 주간 화면. Video.tsx가 w0~w6에 이것을 먼저 쓴다(일간 s*·u*는 그대로). */
export const WEEKLY_COMP: Record<string, React.FC<{ p: Props; sub: string; cues?: Cue[] }>> = { w0: W0, w1: W1, w2: W2, w3: W3, w4: W4, w5: W5, w6: W6 };
