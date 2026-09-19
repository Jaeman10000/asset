/** 미국 주간 v4 화면(일요일 영상 uw0~uw6). 틀은 ScenesV4와 같다 — 로고 + 오른쪽 위 'US 미국 주간 / 9/8–9/11',
 * 미리 구운 미국 배경(public/bg/us_wallst|fed|macro_<tone>.jpg ← usbg/Bg*.tsx, 고정 — 확대·이동·filter 없음),
 * Pretendard 800/900, 빛나는 카드, 그라데이션 숫자, 노란 질문.
 * 숫자는 전부 props(data/weekly_us/<일>/computed_us_weekly.json을 맨 위에 합친 것)의 실제 값. 아직 없는 날(금요일 장은
 * 한국 토요일 새벽 5시 마감)은 '집계 전'으로 비워 두고, 일요일 아침 다시 돌리면 그대로 채워진다.
 * 장면 단계는 말(큐)에 맞춘다: 질문 문장은 질문만 크게, 이름·요일을 말하면 그 카드·그 날이 밝아진다.
 * 화면 글자도 원인을 단정하지 않는다(뉴스 = '같은 주에 겹친 기사 · 원인 단정 아님', 해석 = '추천 아님').
 * 렌더 비용: 배경은 고정 이미지 한 장, 그래프는 clip 폭·막대 길이·opacity만 움직인다.
 * 색: 한국식 — 빨강 = 상승, 파랑 = 하락. 노랑 = 질문·볼 것. */
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { FONT, FOOTER } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";

const ease = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const RED = "#FF4D4D";
const BLUE = "#3D7BFF";
const YEL = "#FFD84D";
const SUBC = "#B8C2D6";
const GOLD = "#FFC873";
const TEAL = "#38D3C8";
const SH = "0 3px 14px rgba(0,0,0,0.85)";
const SH_BIG = "0 8px 34px rgba(0,0,0,0.75)";
const SH_Q = "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)";
type Tone = "up" | "down" | "neutral";
const toneOf = (v?: number | null): Tone => (v == null || v === 0 ? "neutral" : v > 0 ? "up" : "down");
const colOf = (v?: number | null) => (v == null || v === 0 ? "#E6E6E3" : v > 0 ? RED : BLUE);
const softOf = (v?: number | null) => (v == null || v === 0 ? "#CFD6E4" : v > 0 ? "#FF9A90" : "#8FB4FF");

/* ───────── 주간 props(공유 스키마: data/weekly_us/<일>/computed_us_weekly.json) ───────── */
type Day = { d: string; close?: number | null; pct?: number | null; chg_bp?: number | null };
type Ser = { name_ko?: string; prev_close?: number | null; days?: Day[]; week_pct?: number | null; week_high?: number | null; week_low?: number | null; week_chg_bp?: number | null };
type Sector = { etf: string; name_ko?: string; week_pct?: number | null };
type Mega = { ticker: string; name_ko?: string; week_pct?: number | null; close?: number | null };
type Cal = { date?: string; d?: string; event_ko?: string; text?: string };
type News = { d?: string; date?: string; title?: string; headline?: string; line?: string; link_line?: string; text?: string; why?: string; note?: string; summary?: string; src?: string; source?: string; press?: string; tag?: string; kind?: string; cat?: string; category?: string };
/** 물가 지표(선택 필드 — 공유 스키마 밖): p.releases(또는 data_releases·macro) = [{key,name_ko,period,basis,actual,forecast,prev,unit,d,time_kst,src}] */
type Release = { key?: string; name_ko?: string; name?: string; period?: string; basis?: string; actual?: number | null; forecast?: number | null; consensus?: number | null; prev?: number | null; unit?: string; d?: string; date?: string; time_kst?: string; src?: string };
type Watch = string | { q?: string; text?: string; how?: string };
type UW = {
  week_start?: string; week_end?: string; build_date?: string; sessions?: string[];
  idx?: Record<string, Ser>; rates?: Record<string, Ser>; fx?: Record<string, Ser>; commod?: Record<string, Ser>;
  sectors?: Sector[]; megacaps?: Mega[]; calendar_next?: Cal[]; news?: News[];
  releases?: Release[]; data_releases?: Release[]; macro?: Release[];
  holidays?: { d: string; name_ko?: string }[];
  hook_us?: { key?: string; name: string; v: number; unit?: "%" | "bp"; val_text?: string; word?: string; qcard?: "SOX" | "SPX" | "IXIC" } | null;   // val_text·word·qcard = 사건 훅(9/20 "금리 인상")
  view_us?: string | { text?: string } | null; view?: string | { text?: string } | null;
  kr_watch?: Watch | Watch[] | null; monday_watch?: Watch | Watch[] | null;
  fomc_odds?: { before?: number | null; after?: number | null; label?: string; src?: string } | null;
};
const uw = (p: Props) => p as unknown as UW;

/* ───────── 날짜 ───────── */
const ymd = (d?: string | null) => (d ?? "").replace(/[^0-9]/g, "").slice(0, 8);
const dt = (d: string) => { const s = ymd(d); return new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8)); };
const WD = ["일", "월", "화", "수", "목", "금", "토"];
const wdOf = (d: string) => WD[dt(d).getDay()];
const md = (d: string) => { const s = ymd(d); return `${+s.slice(4, 6)}/${+s.slice(6, 8)}`; };
const addDays = (d: string, n: number) => {
  const x = dt(d); x.setDate(x.getDate() + n);
  return `${x.getFullYear()}${String(x.getMonth() + 1).padStart(2, "0")}${String(x.getDate()).padStart(2, "0")}`;
};
/** week_start~week_end의 평일 전부 */
const allWeekdays = (w: UW): string[] => {
  const a = ymd(w.week_start), b = ymd(w.week_end);
  if (a.length === 8 && b.length === 8 && a <= b) {
    const out: string[] = [];
    for (let c = a, k = 0; c <= b && k < 9; c = addDays(c, 1), k++) { const g = dt(c).getDay(); if (g >= 1 && g <= 5) out.push(c); }
    if (out.length) return out;
  }
  return (w.sessions ?? []).map(ymd);
};
/** 실제로 값이 있는 거래일 */
const sessionsOf = (w: UW): string[] => {
  const s = (w.sessions ?? []).map(ymd).filter((x) => x.length === 8);
  if (s.length) return s;
  return (w.idx?.SPX?.days ?? []).filter((x) => x.close != null).map((x) => ymd(x.d));
};
/** 그 주의 거래일 칸: 값이 있는 날 + 마지막 거래일 뒤의 평일(아직 집계 전). 마지막 거래일 앞인데 값이 없는 평일은 휴장이라 뺀다.
 * (월요일 휴장이면 week_start가 화요일이라 처음부터 빠진다) */
const weekDays = (w: UW): string[] => {
  const s = sessionsOf(w);
  const last = s[s.length - 1] ?? "";
  return allWeekdays(w).filter((d) => s.includes(d) || d > last);
};
const pendingDays = (w: UW) => { const s = sessionsOf(w); return weekDays(w).filter((d) => !s.includes(d)); };
const rangeLabel = (w: UW) => { const wd = weekDays(w); return wd.length ? `${md(wd[0])}–${md(wd[wd.length - 1])}` : ""; };
const asOfLabel = (w: UW) => { const s = sessionsOf(w); const l = s[s.length - 1]; return pendingDays(w).length && l ? `${wdOf(l)}요일 마감 기준` : ""; };
/** 월요일 휴장 표시(명시 필드 우선, 없으면 week_start가 화요일일 때 미국 월요일 공휴일 이름) */
const holidayNote = (w: UW) => {
  const h = (w.holidays ?? [])[0];
  if (h) return `${md(h.d)} ${wdOf(h.d)} 휴장${h.name_ko ? `(${h.name_ko})` : ""}`;
  const s = sessionsOf(w);
  const mid = allWeekdays(w).filter((d) => !s.includes(d) && d < (s[s.length - 1] ?? ""));
  if (mid.length) return `${md(mid[0])} ${wdOf(mid[0])} 휴장`;
  const a = ymd(w.week_start);
  if (a.length !== 8 || dt(a).getDay() !== 2) return "";
  const mon = addDays(a, -1);
  const m = +mon.slice(4, 6), dd = +mon.slice(6, 8);
  const nm = m === 9 && dd <= 7 ? "노동절" : m === 1 && dd >= 15 && dd <= 21 ? "마틴 루서 킹 데이" : m === 2 && dd >= 15 && dd <= 21 ? "대통령의 날" : m === 5 && dd >= 25 ? "메모리얼 데이" : "";
  return `${md(mon)} 월 휴장${nm ? `(${nm})` : ""}`;
};
const dayOf = (s: Ser | undefined, d: string) => (s?.days ?? []).find((x) => ymd(x.d) === d);
/** 말에 나온 요일·날짜 → 그 주의 몇 번째 날인지 */
const dayHits = (text: string, ds: string[]) => ds.map((d, i) => {
  const m = +d.slice(4, 6), dd = +d.slice(6, 8);
  return new RegExp(`${wdOf(d)}요일|${m}월\\s?${dd}일|(^|[^0-9])${m}/${dd}(?![0-9])`).test(text) ? i : -1;
}).filter((i) => i >= 0);

/* ───────── 숫자 ───────── */
const MINUS = "−";
const sgn = (v: number) => (v > 0 ? "+" : v < 0 ? MINUS : "");
const pctTxt = (v?: number | null, dg = 2) => (v == null ? "—" : `${sgn(v)}${Math.abs(v).toFixed(dg)}%`);
const numTxt = (v?: number | null, dg = 2) => (v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: dg, maximumFractionDigits: dg }));
const bpTxt = (v?: number | null) => (v == null ? "—" : `${sgn(Math.round(v))}${Math.abs(Math.round(v))}bp`);
const arrow = (v?: number | null) => (v == null || v === 0 ? "" : v > 0 ? "▲" : "▼");
const nDays = (n: number) => (n === 2 ? "이틀" : n === 3 ? "사흘" : n === 4 ? "나흘" : n === 5 ? "닷새" : `${n}일`);
const NAME: Record<string, string> = { SPX: "S&P500", IXIC: "나스닥", DJI: "다우", SOX: "필라델피아 반도체", VIX: "VIX", US10Y: "미국 10년물", US2Y: "미국 2년물", DXY: "달러 인덱스", USDJPY: "엔·달러", USDKRW: "원·달러", WTI: "WTI 유가", GOLD: "금" };
const nm = (key: string, s?: Ser) => s?.name_ko || NAME[key] || key;
const lastClose = (s?: Ser) => { const d = (s?.days ?? []).filter((x) => x.close != null); return d.length ? d[d.length - 1].close! : null; };
/** 대략 글자 폭(em) — 큰 글자가 한 줄에 들어가게 크기를 고를 때만 쓴다 */
const emOf = (s: string) => [...s].reduce((a, ch) => a + (/[0-9+−-]/.test(ch) ? 0.6 : /[.,]/.test(ch) ? 0.3 : ch === " " ? 0.28 : /[A-Za-z&]/.test(ch) ? 0.66 : ch === "%" ? 0.85 : ch === "·" ? 0.4 : 0.98) - 0.04, 0);
const fit = (s: string, width: number, max: number) => Math.min(max, Math.floor(width / Math.max(emOf(s), 0.5)));
const norm = (s: string) => s.replace(/[\s·/,.'"‘’“”…()]/g, "").toLowerCase();

/* ───────── 시간·큐 ───────── */
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
const isQ = (s: string) => /\?\s*$/.test(s.trim());
/** 이 장면의 길이(초): p.scenes에서 같은 cues를 가진 장면 → 마지막 큐 끝 → 컴포지션 길이 */
const useSceneSec = (p: Props, cues?: Cue[]) => {
  const { fps, durationInFrames } = useVideoConfig();
  const sc = (p.scenes ?? []).find((s) => (s as unknown as { cues?: Cue[] }).cues === cues);
  if (sc) return sc.frames ? sc.frames / (p.fps ?? fps) : sc.sec ?? sc.min ?? durationInFrames / fps;
  const l = cues ?? [];
  return l.length ? l[l.length - 1].end + 0.6 : durationInFrames / fps;
};

/* ───────── 틀(ScenesV4와 같은 로고·카드·그라데이션 숫자) ───────── */
const UBg: React.FC<{ name: "wallst" | "fed" | "macro"; tone?: Tone; dim?: number }> = ({ name, tone = "neutral", dim = 0.2 }) => (
  <AbsoluteFill>
    <Img src={staticFile(`bg/us_${name}_${tone}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
    <AbsoluteFill style={{ background: `rgba(3,5,10,${dim})` }} />
  </AbsoluteFill>
);

const Grad: React.FC<{ tone: Tone; children: React.ReactNode; style?: React.CSSProperties }> = ({ tone, children, style }) => {
  const g = tone === "down" ? "linear-gradient(180deg,#A8DCFF 0%,#4A8BFF 48%,#2554E6 100%)"
    : tone === "up" ? "linear-gradient(180deg,#FFC2B8 0%,#FF5A4E 46%,#E2242B 100%)" : "linear-gradient(180deg,#FFFFFF 0%,#CFD6E4 100%)";
  return <span style={{ backgroundImage: g, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", ...style }}>{children}</span>;
};

/** dim: 말하지 않는 카드를 어둡게(카드 자체를 투명하게 하면 배경이 비쳐 지저분해서 위에 어두운 덮개를 얹는다) */
const Card: React.FC<{ color: string; children: React.ReactNode; style?: React.CSSProperties; strong?: boolean; dim?: number }> = ({ color, children, style, strong, dim = 0 }) => (
  <div style={{ position: "relative", border: `2.5px solid ${color}`, borderRadius: 24, background: "linear-gradient(180deg, rgba(10,14,26,0.9), rgba(6,9,18,0.94))",
    boxShadow: dim > 0 ? "none" : strong ? `0 0 48px ${color}99, inset 0 0 26px ${color}33` : `0 0 34px ${color}66, inset 0 0 22px ${color}22`, padding: "28px 34px", ...style }}>
    {children}
    {dim > 0 ? <div style={{ position: "absolute", inset: -3, borderRadius: 24, background: `rgba(5,7,13,${dim})` }} /> : null}
  </div>
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

/** 작은 US 표(성조기 조각 + US) */
const UsTag: React.FC = () => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "3px 10px 3px 6px", borderRadius: 9, border: "2px solid rgba(255,255,255,0.55)", background: "rgba(6,9,18,0.55)", lineHeight: 1 }}>
    <svg width="30" height="20" viewBox="0 0 30 20" style={{ display: "block", borderRadius: 2 }}>
      {Array.from({ length: 7 }, (_, i) => <rect key={i} x={0} y={(20 / 7) * i} width={30} height={20 / 7 + 0.1} fill={i % 2 ? "#F2F2F0" : "#E8453C"} />)}
      <rect x={0} y={0} width={13} height={10.8} fill="#22367A" />
      {[[3, 3], [7, 3], [11, 3], [5, 6], [9, 6], [3, 9], [7, 9], [11, 9]].map(([x, y], i) => <circle key={i} cx={x - 0.6} cy={y - 0.6} r={0.9} fill="#FFFFFF" />)}
    </svg>
    <span style={{ fontSize: 24, fontWeight: 900, color: "#FFFFFF", letterSpacing: "0.02em" }}>US</span>
  </span>
);

/** 틀: 로고(왼쪽 위) + 'US 미국 주간 / 9/8–9/11'(오른쪽 위) + 자막 + 바닥 문구 */
const UShell: React.FC<{ p: Props; bg: React.ReactNode; cues?: Cue[]; hideSub?: boolean; children: React.ReactNode }> = ({ p, bg, cues, hideSub, children }) => {
  const { t } = useT();
  const rg = rangeLabel(uw(p)) || (p.date_label ?? "").split(" ")[0];
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
      <div style={{ position: "absolute", right: 64, top: 66, textAlign: "right", fontWeight: 800, lineHeight: 1.15, textShadow: "0 2px 10px rgba(0,0,0,0.7)" }}>
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, fontSize: 32, color: "#E6E6E3" }}><UsTag />미국 주간</div>
        <div style={{ fontSize: 44, marginTop: 4 }}>{rg}</div>
      </div>
      {children}
      {sub ? (
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 300, display: "flex", justifyContent: "center" }}>
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
const QBig: React.FC<{ text: string; at: number; top?: number }> = ({ text, at, top = 300 }) => {
  const pop = usePop();
  const { head, body } = qSplit(text);
  const bfs = body.length <= 7 ? 172 : body.length <= 10 ? 150 : body.length <= 16 ? 132 : 112;
  const hfs = head.length <= 6 ? 120 : head.length <= 12 ? 92 : 76;
  return (
    <div style={{ position: "absolute", left: 64, right: 64, top, ...pop(at, 30) }}>
      {head ? <div style={{ fontSize: hfs, fontWeight: 900, lineHeight: 1.1, letterSpacing: "-0.03em", wordBreak: "keep-all", textShadow: "0 6px 26px rgba(0,0,0,0.8)" }}>{head}</div> : null}
      <div style={{ fontSize: bfs, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: YEL, wordBreak: "keep-all", marginTop: head ? 6 : 0, textShadow: SH_Q }}>{body}</div>
    </div>
  );
};

/** 작은 칩 */
const Chip: React.FC<{ bg: string; children: React.ReactNode; fs?: number; dark?: boolean; style?: React.CSSProperties }> = ({ bg, children, fs = 30, dark = true, style }) => (
  <span style={{ display: "inline-block", fontSize: fs, fontWeight: 900, color: dark ? "#0B0E16" : "#FFFFFF", background: bg, borderRadius: 10, padding: "4px 14px", whiteSpace: "nowrap", lineHeight: 1.2, ...style }}>{children}</span>
);
const Pending: React.FC<{ w: UW; fs?: number }> = ({ w, fs = 28 }) => {
  const pd = pendingDays(w);
  if (!pd.length) return null;
  return <Chip bg="rgba(184,194,214,0.18)" dark={false} fs={fs} style={{ border: "2px dashed rgba(207,214,228,0.6)", color: "#DCE3F0" }}>{pd.map((d) => `${wdOf(d)}요일`).join("·")} 장 집계 전</Chip>;
};

/* ═════════ uw0: 첫 화면 — 한 주 가장 크게 움직인 것 + 그 사이 S&P500 → 질문 문장부터 질문 + S&P500 카드 ═════════ */
type Hero = { key: string; name: string; v: number; unit: "%" | "bp" };
const HERO_NAME: Record<string, string> = { WTI: "유가", GOLD: "금값", DXY: "달러", USDJPY: "엔·달러", USDKRW: "원·달러", US10Y: "10년물 금리", SOX: "반도체지수", VIX: "공포지수(VIX)", IXIC: "나스닥", DJI: "다우" };
const pickHero = (w: UW): Hero | null => {
  const h = w.hook_us;
  if (h && h.name && h.v != null && isFinite(h.v)) return { key: h.key ?? "", name: h.name, v: h.v, unit: h.unit ?? "%" };
  const c: (Hero & { z: number })[] = [];
  const add = (key: string, s: Ser | undefined, scale: number, unit: "%" | "bp" = "%") => {
    const v = unit === "bp" ? s?.week_chg_bp : s?.week_pct;
    if (v != null && isFinite(v)) c.push({ key, name: HERO_NAME[key] ?? nm(key, s), v, unit, z: Math.abs(v) / scale });
  };
  add("WTI", w.commod?.WTI, 4); add("GOLD", w.commod?.GOLD, 2.5); add("DXY", w.fx?.DXY, 1); add("USDJPY", w.fx?.USDJPY, 1.3); add("USDKRW", w.fx?.USDKRW, 1);
  add("US10Y", w.rates?.US10Y, 10, "bp"); add("SOX", w.idx?.SOX, 4); add("VIX", w.idx?.VIX, 15); add("IXIC", w.idx?.IXIC, 2.4); add("DJI", w.idx?.DJI, 2);
  c.sort((a, b) => b.z - a.z);
  return c[0] ?? null;
};
/** 이번 주 거래일이 모두 같은 방향이면 그 날 수 */
const sameDir = (w: UW, s?: Ser) => {
  const ds = sessionsOf(w).map((d) => dayOf(s, d)?.pct).filter((v): v is number => v != null);
  if (ds.length < 2) return 0;
  return ds.every((v) => v < 0) ? -ds.length : ds.every((v) => v > 0) ? ds.length : 0;
};

/* ═════════ uw0: 첫 화면 — 말 순서대로: '사흘 연속 하락'(요일 칩이 차례로) → '금요일 되돌림' → 질문만 크게 + S&P500 카드 ═════════ */
export const UW0: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const list = cues ?? [];
  const spx = w.idx?.SPX;
  const chg = spx?.week_pct ?? null;
  const last = lastClose(spx);
  const sess = sessionsOf(w);
  const qc = list.find((c) => isQ(c.text));
  if (qc && t >= qc.start) {
    // 질문이 둘이면(과연 …? 아니면 …?) 지금 말하는 질문을 띄운다
    const qNow = [...list].reverse().find((c) => isQ(c.text) && t >= c.start) ?? qc;
    // 질문에 반도체가 나오거나 훅이 반도체 카드를 고르면 반도체 지수 카드, 아니면 S&P500 카드
    const qSox = (w.hook_us?.qcard === "SOX" || /반도체/.test(qc.text)) && w.idx?.SOX?.week_pct != null;
    const onlyPlus = ["SPX", "IXIC", "DJI"].every((k) => ((w.idx as Record<string, Ser | undefined> | undefined)?.[k]?.week_pct ?? 0) <= 0);
    const qs = qSox ? w.idx!.SOX : spx;
    const qChg = qs?.week_pct ?? null, qLast = lastClose(qs);
    return (
      <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone={toneOf(chg)} dim={0.22} />}>
        <QBig text={qNow.text} at={qNow.start} />
        {qLast != null ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 1010, ...pop(qc.start + 0.25) }}>
            <Card color={colOf(qChg)} strong={qSox} style={{ display: "inline-block", minWidth: 660 }}>
              <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4" }}>{qSox ? "필라델피아 반도체" : "S&P500"} <span style={{ color: SUBC, fontWeight: 700 }}>· 이번 주</span></div>
              <div style={{ fontSize: 118, fontWeight: 800, lineHeight: 1.05, marginTop: 6 }}>{numTxt(qLast)}</div>
              <div style={{ fontSize: 64, fontWeight: 800, color: colOf(qChg), marginTop: 6 }}>{arrow(qChg) || "−"} {Math.abs(qChg ?? 0).toFixed(2)}%{qSox && onlyPlus ? <span style={{ fontSize: 34, color: SUBC, fontWeight: 700, marginLeft: 14 }}>지수 중 유일한 플러스</span> : null}</div>
              {qs?.prev_close != null ? <div style={{ fontSize: 34, fontWeight: 700, color: SUBC, marginTop: 10 }}>지난주 마감 {numTxt(qs.prev_close)}에서</div> : null}
              {pendingDays(w).length ? <div style={{ marginTop: 16 }}><Pending w={w} /></div> : null}
            </Card>
          </div>
        ) : null}
      </UShell>
    );
  }
  // 마지막 세션 직전까지 같은 방향으로 이어진 날들(연속 하락/상승) + 방향이 바뀐 마지막 날
  const pcts = sess.map((d) => ({ d, v: dayOf(spx, d)?.pct ?? null }));
  const lastIdx = pcts.length - 1;
  let runStart = lastIdx - 1;
  const dir = runStart >= 0 && pcts[runStart].v != null ? Math.sign(pcts[runStart].v!) : 0;
  while (dir !== 0 && runStart > 0 && pcts[runStart - 1].v != null && Math.sign(pcts[runStart - 1].v!) === dir) runStart--;
  const run = !w.hook_us?.val_text && dir !== 0 ? pcts.slice(runStart, lastIdx) : [];   // 사건 훅이면 연속 하락 칸 대신 사건
  const lastDay = pcts[lastIdx];
  const flipped = !!lastDay && lastDay.v != null && dir !== 0 && Math.sign(lastDay.v) === -dir;
  const turnIdx = findIdx(list, (s) => /되돌|반등|돌아섰|회복|올랐/.test(s), 1);
  const turnAt = turnIdx >= 0 ? list[turnIdx].start : list[1]?.start ?? 3.2;
  const stage2 = flipped && t >= turnAt;
  const hero = pickHero(w);
  const heroTone = toneOf(hero?.v);
  const heroVal = w.hook_us?.val_text ?? (hero ? (hero.unit === "bp" ? bpTxt(hero.v) : pctTxt(hero.v)) : "");
  const word = w.hook_us?.word ?? (hero ? (hero.v > 0 ? "올랐다" : hero.v < 0 ? "내렸다" : "제자리") : "");
  const dayBox = (x: { d: string; v: number | null }, at: number, strong = false): React.CSSProperties & { key?: string } => ({
    ...pop(at, 16), flex: 1, borderRadius: 20, padding: "16px 10px", textAlign: "center", border: `${strong ? 3 : 2.5}px solid ${colOf(x.v)}`,
    background: "rgba(6,9,18,0.8)", boxShadow: `0 0 ${strong ? 34 : 22}px ${colOf(x.v)}${strong ? "AA" : "66"}`,
  });
  return (
    <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone={toneOf(chg)} dim={0.2} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 236 }}>
        <div style={{ ...pop(0.05, 18), fontSize: 62, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>이번 주 뉴욕 증시</div>
        {run.length ? (
          <div style={pop(0.2, 24)}>
            <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1.04, letterSpacing: "-0.05em", textShadow: SH_BIG }}>
              <Grad tone={dir < 0 ? "down" : "up"}>{nDays(run.length)} 연속</Grad> {dir < 0 ? "하락" : "상승"}
            </div>
            <div style={{ display: "flex", gap: 18, marginTop: 30 }}>
              {run.map((x, i) => (
                <div key={x.d} style={dayBox(x, 0.5 + i * 0.32)}>
                  <div style={{ fontSize: 40, fontWeight: 900 }}>{wdOf(x.d)}<span style={{ fontSize: 22, color: SUBC, marginLeft: 6 }}>{md(x.d)}</span></div>
                  <div style={{ fontSize: 46, fontWeight: 900, color: colOf(x.v), marginTop: 4 }}>{arrow(x.v)} {Math.abs(x.v ?? 0).toFixed(2)}%</div>
                </div>
              ))}
              {flipped ? (
                <div style={{ ...dayBox(lastDay, turnAt, true), ...(stage2 ? {} : { opacity: 0 }) }}>
                  <div style={{ fontSize: 40, fontWeight: 900 }}>{wdOf(lastDay.d)}<span style={{ fontSize: 22, color: SUBC, marginLeft: 6 }}>{md(lastDay.d)}</span></div>
                  <div style={{ fontSize: 46, fontWeight: 900, color: colOf(lastDay.v), marginTop: 4 }}>{arrow(lastDay.v)} {Math.abs(lastDay.v ?? 0).toFixed(2)}%</div>
                </div>
              ) : null}
            </div>
            {stage2 ? (
              <div style={{ ...pop(turnAt + 0.15, 22), marginTop: 56 }}>
                <div style={{ fontSize: 62, fontWeight: 800, lineHeight: 1.2, textShadow: SH }}>그런데 {wdOf(lastDay.d)}요일 하루에</div>
                <div style={{ fontSize: 118, fontWeight: 900, lineHeight: 1.1, letterSpacing: "-0.04em", textShadow: SH_BIG }}><Grad tone={toneOf(lastDay.v)}>{pctTxt(lastDay.v)}</Grad> <span style={{ color: YEL }}>되돌림</span></div>
                {chg != null ? <div style={{ fontSize: 44, fontWeight: 800, color: SUBC, marginTop: 12, textShadow: SH }}>한 주로는 S&P500 {pctTxt(chg)}</div> : null}
              </div>
            ) : null}
          </div>
        ) : hero ? (
          <>
            <div style={{ fontSize: fit(hero.name, 950, 190), fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", whiteSpace: "nowrap", textShadow: SH_BIG }}>{hero.name}</div>
            <div style={{ fontSize: fit(`${heroVal} ${word}`, 950, 184), fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", whiteSpace: "nowrap" }}>
              <Grad tone={heroTone}>{heroVal}</Grad><span style={{ textShadow: SH_BIG }}> {word}</span>
            </div>
          </>
        ) : null}
      </div>
    </UShell>
  );
};

/* ═════════ uw1: 지수 한 주 길 — S&P500·나스닥(지난주 마감 대비 누적 %), 화~금 네 칸. 없는 날은 '집계 전' ═════════ */
const IdxChart: React.FC<{ w: UW; W: number; H: number; t0: number; span: number; hot: number[] }> = ({ w, W, H, t0, span, hot }) => {
  const { t } = useT();
  const days = weekDays(w);
  const sess = sessionsOf(w);
  const n = Math.max(days.length, 1);
  const spx = w.idx?.SPX, ndx = w.idx?.IXIC;
  const L = 104, R = 34, T = 92, B = 196;
  const base = H - B;
  const colW = (W - L - R) / n;
  const X = (i: number) => L + colW * (i + 0.5);
  const cum = (s?: Ser): (number | null)[] | null => {
    if (!s) return null;
    let b = s.prev_close ?? null;
    if (b == null) { const f = (s.days ?? []).find((x) => x.close != null && x.pct != null); if (f) b = f.close! / (1 + f.pct! / 100); }
    if (b == null) return null;
    return days.map((d) => { const x = dayOf(s, d); return x && x.close != null && sess.includes(d) ? (x.close / b! - 1) * 100 : null; });
  };
  const a = cum(spx), b = cum(ndx);
  const vals = [0, ...(a ?? []), ...(b ?? [])].filter((v): v is number => v != null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi - lo < 1) { const m = (hi + lo) / 2; lo = m - 0.5; hi = m + 0.5; }
  const pad = (hi - lo) * 0.16;
  const y0 = lo - pad, y1 = hi + pad;
  const Y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (base - T);
  const lastI = (arr: (number | null)[] | null) => (arr ?? []).reduce<number>((k, v, i) => (v != null ? i : k), -1);
  const endI = Math.max(lastI(a), lastI(b), 0);
  const P = interpolate(t, [t0, t0 + span], [0, 1], { ...CLAMP, easing: Easing.inOut(Easing.cubic) });
  const clipX = L - 12 + (X(endI) - L + 40) * P;
  const kPt = (i: number) => Math.max(0, Math.min(1, (clipX - X(i) + 6) / 26));
  const path = (arr: (number | null)[] | null) => { if (!arr) return ""; let d = `M${L} ${Y(0)}`; arr.forEach((v, i) => { if (v != null) d += `L${X(i)} ${Y(v)}`; }); return d; };
  const cA = colOf(spx?.week_pct), cB = softOf(ndx?.week_pct);
  // 눈금: 0.5%/1%/2% 간격 중 4~6줄이 되는 것
  const stepV = [0.25, 0.5, 1, 2, 5].find((s) => (y1 - y0) / s <= 6) ?? 5;
  const ticks: number[] = [];
  for (let v = Math.ceil(y0 / stepV) * stepV; v <= y1; v += stepV) ticks.push(Math.round(v * 100) / 100);
  const anyHot = hot.length > 0;
  const firstMiss = days.findIndex((d) => !sess.includes(d));
  const aTone = toneOf(spx?.week_pct);
  const aCol = aTone === "down" ? "61,123,255" : "255,77,77";
  const area = a ? `${path(a)}L${X(lastI(a))} ${base}L${L} ${base}Z` : "";
  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      <defs>
        <clipPath id="uw1clip"><rect x={0} y={0} width={Math.max(0, clipX)} height={H} /></clipPath>
        <linearGradient id="uw1area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={`rgba(${aCol},0.30)`} />
          <stop offset="100%" stopColor={`rgba(${aCol},0)`} />
        </linearGradient>
      </defs>
      {/* 범례: 한 주 등락 */}
      <g>
        <line x1={L} x2={L + 46} y1={30} y2={30} stroke={cA} strokeWidth={7} strokeLinecap="round" />
        <text x={L + 58} y={41} fontSize={32} fontWeight={900} fill="#FFFFFF">S&P500 <tspan fill={cA}>{pctTxt(spx?.week_pct)}</tspan></text>
        {ndx ? (
          <>
            <line x1={L + 430} x2={L + 476} y1={30} y2={30} stroke={cB} strokeWidth={5} strokeDasharray="10 7" strokeLinecap="round" />
            <text x={L + 488} y={41} fontSize={32} fontWeight={900} fill="#FFFFFF">나스닥 <tspan fill={cB}>{pctTxt(ndx.week_pct)}</tspan></text>
          </>
        ) : null}
      </g>
      {/* 눈금 */}
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke={v === 0 ? "rgba(207,214,228,0.55)" : "rgba(143,167,217,0.13)"} strokeWidth={v === 0 ? 2.5 : 2} strokeDasharray={v === 0 ? "6 10" : undefined} />
          <text x={L - 14} y={Y(v) + 9} fontSize={24} fontWeight={800} fill={v === 0 ? "#E6E6E3" : SUBC} textAnchor="end">{v === 0 ? "0%" : `${sgn(v)}${Math.abs(v)}%`}</text>
        </g>
      ))}
      <text x={firstMiss >= 0 ? X(firstMiss) - colW / 2 - 2 : W - R} y={Y(0) - 12} fontSize={22} fontWeight={800} fill={SUBC} textAnchor="end">지난주 마감</text>
      {/* 말하는 요일 강조 · 집계 전 칸 */}
      {days.map((d, i) => sess.includes(d) ? (hot.includes(i) ? (
        <rect key={`h${i}`} x={X(i) - colW / 2 + 6} y={T - 14} width={colW - 12} height={base - T + 14} rx={18} fill="rgba(255,255,255,0.07)" stroke="rgba(255,255,255,0.24)" strokeWidth={2} />
      ) : null) : (
        <g key={`m${i}`}>
          <rect x={X(i) - colW / 2 + 8} y={T - 10} width={colW - 16} height={base - T + 10} rx={18} fill="rgba(184,194,214,0.05)" stroke="rgba(207,214,228,0.4)" strokeWidth={2} strokeDasharray="8 8" />
          <text x={X(i)} y={(T + base) / 2 - 6} fontSize={30} fontWeight={900} fill="#DCE3F0" textAnchor="middle">집계 전</text>
          <text x={X(i)} y={(T + base) / 2 + 30} fontSize={22} fontWeight={700} fill={SUBC} textAnchor="middle">{wdOf(d)}요일 장</text>
        </g>
      ))}
      {/* 면 + 선(그려지며 나타남) */}
      <g clipPath="url(#uw1clip)">
        {area ? <path d={area} fill="url(#uw1area)" /> : null}
        {b ? <path d={path(b)} fill="none" stroke={cB} strokeWidth={5} strokeDasharray="12 9" strokeLinejoin="round" strokeLinecap="round" /> : null}
        {a ? (
          <>
            <path d={path(a)} fill="none" stroke={cA} strokeOpacity={0.22} strokeWidth={20} strokeLinejoin="round" strokeLinecap="round" />
            <path d={path(a)} fill="none" stroke={cA} strokeWidth={7} strokeLinejoin="round" strokeLinecap="round" />
          </>
        ) : null}
      </g>
      <circle cx={L} cy={Y(0)} r={8} fill="#CFD6E4" opacity={P > 0 ? 1 : 0} />
      {/* 점 */}
      {days.map((d, i) => {
        const k = kPt(i);
        const on = hot.includes(i);
        const va = a?.[i], vb = b?.[i];
        return (
          <g key={`p${i}`} opacity={k}>
            {vb != null ? <circle cx={X(i)} cy={Y(vb)} r={on ? 11 : 8} fill="#0B0E16" stroke={cB} strokeWidth={4} /> : null}
            {va != null ? (
              <>
                <circle cx={X(i)} cy={Y(va)} r={on ? 18 : 13} fill="#0B0E16" stroke={cA} strokeWidth={on ? 7 : 5} />
                {on ? <circle cx={X(i)} cy={Y(va)} r={29} fill="none" stroke={cA} strokeOpacity={0.35} strokeWidth={3} /> : null}
                {/* 이름표: 보통은 점 아래(나스닥 점이 아래면 위). 맨 오른쪽 칸의 마지막 점은 들어오는 선을 피해 왼쪽 위. */}
                <text x={i === n - 1 && i === lastI(a) ? X(i) - 22 : X(i)} y={i === n - 1 && i === lastI(a) ? Y(va) - 24 : Y(va) + (vb != null && vb < va ? -26 : 48)} fontSize={on ? 34 : 29} fontWeight={900} fill="#FFFFFF" fillOpacity={anyHot && !on ? 0.72 : 1}
                  textAnchor={i === n - 1 && i === lastI(a) ? "end" : "middle"} stroke="#05070D" strokeWidth={8} strokeLinejoin="round" paintOrder="stroke">{pctTxt(va)}</text>
              </>
            ) : null}
          </g>
        );
      })}
      {/* 요일 · 하루 등락(S&P500 / 나스닥) */}
      <text x={L - 14} y={base + 108} fontSize={21} fontWeight={800} fill={SUBC} textAnchor="end">S&P</text>
      {ndx ? <text x={L - 14} y={base + 150} fontSize={21} fontWeight={800} fill={SUBC} textAnchor="end">나스닥</text> : null}
      {days.map((d, i) => {
        const on = hot.includes(i);
        const has = sess.includes(d);
        const ca = dayOf(spx, d)?.pct ?? null, cb = dayOf(ndx, d)?.pct ?? null;
        return (
          <g key={`l${i}`} opacity={anyHot && !on ? 0.6 : has ? 1 : 0.75}>
            {on ? <rect x={X(i) - colW / 2 + 10} y={base + 14} width={colW - 20} height={160} rx={16} fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.45)" strokeWidth={2} /> : null}
            <text x={X(i)} y={base + 62} fontSize={44} fontWeight={900} fill="#FFFFFF" textAnchor="middle">{wdOf(d)}<tspan fontSize={22} fontWeight={700} fill={SUBC} dx={6}>{md(d)}</tspan></text>
            {has ? (
              <>
                <text x={X(i)} y={base + 108} fontSize={30} fontWeight={900} fill={colOf(ca)} textAnchor="middle">{arrow(ca)}{ca == null ? "—" : `${Math.abs(ca).toFixed(2)}%`}</text>
                {ndx ? <text x={X(i)} y={base + 150} fontSize={25} fontWeight={800} fill={softOf(cb)} textAnchor="middle">{arrow(cb)}{cb == null ? "—" : `${Math.abs(cb).toFixed(2)}%`}</text> : null}
              </>
            ) : <text x={X(i)} y={base + 108} fontSize={26} fontWeight={800} fill={SUBC} textAnchor="middle">대기</text>}
          </g>
        );
      })}
    </svg>
  );
};

export const UW1: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const { cur } = curCue(cues, t);
  const spx = w.idx?.SPX;
  const chg = spx?.week_pct ?? null;
  const last = lastClose(spx);
  const days = weekDays(w);
  const txt = cur && t < cur.end + 0.6 ? cur.text : "";
  // 말하는 요일이 켜진다. '화요일부터 목요일까지'는 구간 전체가, 말하는 동안 왼쪽부터 차례로.
  let hot = txt ? dayHits(txt, days) : [];
  if (txt && /부터/.test(txt) && /까지/.test(txt) && hot.length >= 2) {
    const a = Math.min(...hot), b = Math.max(...hot);
    hot = days.map((_, i) => i).filter((i) => i >= a && i <= b);
  }
  if (cur && hot.length > 1) {
    const k = interpolate(t, [cur.start + 0.15, Math.max(cur.start + 1.0, cur.end - 0.5)], [0, 1], CLAMP);
    hot = hot.slice(0, Math.max(1, Math.ceil(k * hot.length)));
  }
  const q = cur && isQ(cur.text) ? cur : undefined;
  const asOf = asOfLabel(w);
  const hol = holidayNote(w);
  const saySpx = /S&P|에스앤피/i.test(txt);
  const minis = ([["DJI", "다우", /다우/], ["IXIC", "나스닥", /나스닥/], ["SOX", "반도체(SOX)", /반도체/]] as const)
    .map(([k, label, re]) => ({ k, label, re, s: w.idx?.[k] })).filter((x) => x.s && x.s.week_pct != null);
  const onlyUp = /하나만 플러스|유일|하나만 올|하나만 오/.test(txt);
  const upCount = [spx, ...minis.map((m) => m.s)].filter((s) => (s?.week_pct ?? 0) > 0).length;
  const miniOn = (x: (typeof minis)[number]) => x.re.test(txt) || (onlyUp && upCount === 1 && x.s!.week_pct! > 0);
  const anyMiniOn = minis.some(miniOn);
  const pulse = saySpx ? 1 + 0.045 * Math.sin((t - (cur?.start ?? 0)) * 7) : 1;
  const bg = <UBg name="wallst" tone={toneOf(chg)} dim={0.44} />;
  if (q) {
    // 질문은 질문만 — 표·카드는 모두 걷어낸다
    return (
      <UShell p={p} cues={cues} hideSub bg={bg}>
        <QBig text={q.text} at={q.start} />
      </UShell>
    );
  }
  return (
    <UShell p={p} cues={cues} bg={bg}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 226, height: 330, opacity: anyMiniOn && !saySpx ? 0.45 : 1 }}>
        <div style={pop(0.05, 20)}>
          <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 56, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>
            이번 주 S&P500
            {asOf ? <Chip bg="rgba(184,194,214,0.16)" dark={false} fs={26} style={{ border: "2px solid rgba(207,214,228,0.45)", color: "#DCE3F0" }}>{asOf}</Chip> : null}
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginTop: 2 }}>
            <div style={{ fontSize: 158, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.0, transform: `scale(${pulse})`, transformOrigin: "left bottom",
              filter: saySpx ? `drop-shadow(0 0 22px ${colOf(chg)})` : "none" }}><Grad tone={toneOf(chg)}>{pctTxt(chg)}</Grad></div>
            {last != null ? (
              <div style={{ textAlign: "right", paddingBottom: 14, textShadow: SH }}>
                <div style={{ fontSize: 58, fontWeight: 900, lineHeight: 1.1 }}>{numTxt(last)}</div>
                {spx?.prev_close != null ? <div style={{ fontSize: 30, fontWeight: 700, color: SUBC }}>지난주 {numTxt(spx.prev_close)}</div> : null}
              </div>
            ) : null}
          </div>
          {hol ? <div style={{ fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 6, textShadow: SH }}>{hol} · 거래일 {days.length}일</div> : null}
        </div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 590, ...pop(0.15, 24), opacity: anyMiniOn ? 0.35 : undefined }}>
        <Card color={colOf(chg)} style={{ padding: "18px 26px" }}>
          <IdxChart w={w} W={892} H={740} t0={0.35} span={1.4} hot={hot} />
        </Card>
      </div>
      {minis.length ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1398, display: "flex", gap: 20, alignItems: "stretch" }}>
          {minis.map((x, k) => {
            const on = miniOn(x);
            return (
              <Card key={x.k} color={colOf(x.s!.week_pct)} strong={on} dim={anyMiniOn && !on ? 0.6 : 0}
                style={{ ...pop(1.2 + k * 0.18, 18), flex: 1, padding: "16px 20px", transform: on ? "scale(1.07)" : "none", transformOrigin: "center bottom", zIndex: on ? 2 : 1 }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: "#CFD6E4", whiteSpace: "nowrap" }}>{x.label}</div>
                <div style={{ fontSize: 50, fontWeight: 900, color: colOf(x.s!.week_pct), letterSpacing: "-0.03em", lineHeight: 1.15 }}>{pctTxt(x.s!.week_pct)}</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: SUBC }}>{numTxt(lastClose(x.s))}</div>
                {on && upCount === 1 && x.s!.week_pct! > 0 ? <div style={{ marginTop: 8 }}><Chip bg={YEL} fs={24}>지수 중 유일한 플러스</Chip></div> : null}
              </Card>
            );
          })}
        </div>
      ) : null}
    </UShell>
  );
};

/* ═════════ uw2: 금리와 물가 — 10년물 한 주 bp + 요일별 칸 → (물가를 말할 때) CPI·PPI 실제 vs 예상 카드 ═════════ */
const releasesOf = (w: UW): Release[] => (w.releases ?? w.data_releases ?? w.macro ?? []).filter((r) => r && (r.name_ko || r.name || r.key)).slice(0, 2);
const RelCard: React.FC<{ r: Release; at: number; on: boolean }> = ({ r, at, on }) => {
  const pop = usePop();
  const { t } = useT();
  const fc = r.forecast ?? r.consensus ?? null;
  const act = r.actual ?? null;
  const unit = r.unit ?? "%";
  const surprise = act != null && fc != null ? Math.round((act - fc) * 1000) / 1000 : null;
  const col = surprise == null ? "#CFD6E4" : surprise > 0 ? RED : surprise < 0 ? BLUE : "#CFD6E4";
  const d = ymd(r.d ?? r.date);
  const title = r.name_ko ?? r.name ?? r.key ?? "";
  const k = interpolate(t, [at + 0.35, at + 1.0], [0, 1], { ...CLAMP, easing: ease });
  const mx = Math.max(Math.abs(act ?? 0), Math.abs(fc ?? 0), 0.0001);
  const bar = (v: number | null, c: string, label: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
      <span style={{ width: 62, fontSize: 26, fontWeight: 800, color: SUBC }}>{label}</span>
      <div style={{ flex: 1, height: 22, borderRadius: 11, background: "rgba(143,167,217,0.14)", overflow: "hidden" }}>
        {v != null ? <div style={{ width: `${(Math.abs(v) / mx) * 100 * k}%`, height: "100%", borderRadius: 11, background: c }} /> : null}
      </div>
      <span style={{ width: 92, textAlign: "right", fontSize: 28, fontWeight: 900, color: v == null ? SUBC : "#FFFFFF" }}>{v == null ? "—" : `${v}${unit}`}</span>
    </div>
  );
  return (
    <Card color={act == null ? "#8FA7D9" : col} strong={on} style={{ ...pop(at), flex: 1, padding: "24px 26px" }}>
      <div style={{ fontSize: 38, fontWeight: 900, lineHeight: 1.15, whiteSpace: "nowrap" }}>{title}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: SUBC, marginTop: 4 }}>{[r.period, r.basis].filter(Boolean).join(" · ")}</div>
      {act != null ? (
        <>
          <div style={{ fontSize: 104, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.05, marginTop: 8 }}><Grad tone="neutral">{act}{unit}</Grad></div>
          {fc != null ? (
            <>
              {bar(fc, "rgba(207,214,228,0.55)", "예상")}
              {bar(act, col === "#CFD6E4" ? "#E6E6E3" : col, "실제")}
              <div style={{ marginTop: 16 }}><Chip bg={col} fs={28} dark={col === "#CFD6E4"}>{surprise! > 0 ? "예상보다 높음" : surprise! < 0 ? "예상보다 낮음" : "예상과 같음"}</Chip></div>
            </>
          ) : null}
        </>
      ) : (
        <>
          <div style={{ fontSize: 64, fontWeight: 900, color: "#DCE3F0", marginTop: 14 }}>발표 대기</div>
          {fc != null ? <div style={{ fontSize: 30, fontWeight: 800, color: SUBC, marginTop: 6 }}>예상 {fc}{unit}</div> : null}
        </>
      )}
      {d ? <div style={{ fontSize: 24, fontWeight: 700, color: SUBC, marginTop: 14 }}>{md(d)} {wdOf(d)} {r.time_kst ? `${r.time_kst} (한국)` : ""}{r.src ? ` · ${r.src}` : ""}</div> : null}
    </Card>
  );
};

/* ═════════ uw2: 물가 → 인상 확률 → '그런데 주식은 올랐다' → 금리 자리(2년물·10년물) → 해석. 말에 맞춰 한 단계씩 ═════════ */
export const UW2: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const secs = useSceneSec(p, cues);
  const { list, cur } = curCue(cues, t);
  const y10 = w.rates?.US10Y, y2 = w.rates?.US2Y;
  const bp = y10?.week_chg_bp ?? null, bp2 = y2?.week_chg_bp ?? null;
  const rels = releasesOf(w);
  const odds = w.fomc_odds ?? null;
  const spx = w.idx?.SPX, vix = w.idx?.VIX;
  const sess = sessionsOf(w);
  const lastD = sess[sess.length - 1];
  const spxLast = lastD ? dayOf(spx, lastD)?.pct ?? null : null;
  const vixLast = lastD ? dayOf(vix, lastD)?.pct ?? null : null;
  const txt = cur && t < cur.end + 0.6 ? cur.text : "";
  const at = (i: number, fb: number) => (i >= 0 ? list[i].start : fb);
  const oddsAt = at(findIdx(list, (s) => /확률/.test(s)), secs * 0.3);
  const stockAt = at(findIdx(list, (s) => /주식은 올랐|주식은 오히려|주식은 왜|세 지수가 모두|지수가 모두 올|부담인 소식/.test(s)), secs * 0.42);
  const rateAt = at(findIdx(list, (s) => /2년물|10년물|금리를 뜯어|실마리|금리 안에|답은 금리/.test(s)), secs * 0.55);
  const interpAt = at(findIdx(list, (s) => /당장 한 번|멀리까지|한 번 올리|계속 올릴|한숨 돌린/.test(s)), secs * 0.85);
  const stage = t >= rateAt ? 2 : t >= oddsAt ? 1 : 0;
  const bg = <UBg name="fed" tone={toneOf(bp)} dim={0.36} />;
  if (cur && isQ(cur.text)) {
    return (
      <UShell p={p} cues={cues} hideSub bg={bg}>
        <QBig text={cur.text} at={cur.start} />
      </UShell>
    );
  }
  const relOn = (r: Release) => !!txt && [r.key, r.name_ko, r.name].some((x) => !!x && (txt.includes(x) || (/근원/.test(x) && /근원/.test(txt)) || (/CPI|소비자/.test(x) && !/근원/.test(x) && /소비자|1년 전/.test(txt))));
  const rateRows = [
    { label: "2년물", s: y2, v: bp2, re: /2년물/ },
    { label: "10년물", s: y10, v: bp, re: /10년물/ },
  ].filter((r) => r.s && r.v != null);
  const sayRate = /2년물|10년물/.test(txt);
  return (
    <UShell p={p} cues={cues} bg={bg}>
      {stage < 2 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
          <div style={{ ...pop(0.05, 18), fontSize: 50, fontWeight: 900, textShadow: SH }}>금요일 아침에 나온 <span style={{ color: YEL }}>8월 물가</span></div>
          {rels.length ? (
            <div style={{ display: "flex", gap: 22, marginTop: 18, alignItems: "stretch" }}>
              {rels.map((r, k) => <RelCard key={k} r={r} at={0.2 + k * 0.35} on={relOn(r)} />)}
            </div>
          ) : null}
          {stage >= 1 && odds && odds.after != null ? (
            <Card color={RED} strong style={{ ...pop(oddsAt, 22), marginTop: 26, padding: "22px 34px" }}>
              <div style={{ fontSize: 34, fontWeight: 800, color: "#CFD6E4" }}>{odds.label ?? "9월 금리 인상 확률"}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 22, marginTop: 4 }}>
                {odds.before != null ? <span style={{ fontSize: 88, fontWeight: 900, color: SUBC, letterSpacing: "-0.03em" }}>{Math.round(odds.before)}%</span> : null}
                {odds.before != null ? <span style={{ fontSize: 64, fontWeight: 900, color: RED }}>→</span> : null}
                <span style={{ fontSize: 146, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1 }}><Grad tone="up">{Math.round(odds.after)}%</Grad></span>
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: SUBC, marginTop: 6 }}>{odds.src ?? "CME 페드워치"} · 발표 전 → 발표 후</div>
            </Card>
          ) : null}
          {stage >= 1 && t >= stockAt ? (
            <div style={{ ...pop(stockAt, 18), display: "flex", gap: 18, marginTop: 22, flexWrap: "wrap" }}>
              {odds?.after != null ? <Chip bg={RED} fs={34} dark={false}>올린다는 쪽 ↑ {Math.round(odds.after)}%</Chip> : null}
              {spxLast != null ? <Chip bg={colOf(spxLast)} fs={34} dark={false}>그런데 S&P500 {pctTxt(spxLast)}</Chip> : null}
              {vixLast != null ? <Chip bg="rgba(207,214,228,0.22)" fs={30} dark={false} style={{ border: "2px solid rgba(207,214,228,0.5)" }}>공포지수 {pctTxt(vixLast)}</Chip> : null}
            </div>
          ) : null}
        </div>
      ) : (
        <div key="rates" style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
          <div style={{ ...pop(rateAt, 18), fontSize: 50, fontWeight: 900, textShadow: SH }}>금리가 오른 <span style={{ color: YEL }}>자리</span> <span style={{ color: SUBC, fontWeight: 700, fontSize: 36 }}>· 이번 주</span></div>
          <div style={{ display: "flex", gap: 22, marginTop: 18 }}>
            {rateRows.map((r, k) => {
              const on = r.re.test(txt);
              const prev = r.s!.prev_close ?? null, lastV = lastClose(r.s);
              return (
                <Card key={r.label} color={colOf(r.v)} strong={on} dim={sayRate && !on ? 0.55 : 0}
                  style={{ ...pop(rateAt + 0.15 + k * 0.3, 20), flex: 1, padding: "24px 30px", transform: on ? "scale(1.05)" : "none", transformOrigin: "center top", zIndex: on ? 2 : 1 }}>
                  <div style={{ fontSize: 38, fontWeight: 800, color: "#CFD6E4" }}>미국 {r.label} <span style={{ fontSize: 26, color: SUBC, fontWeight: 700 }}>{r.label === "2년물" ? "· 당장의 정책" : "· 먼 앞날의 경기"}</span></div>
                  <div style={{ fontSize: 92, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.1, marginTop: 8, whiteSpace: "nowrap" }}><Grad tone={toneOf(r.v)}>{sgn(r.v ?? 0)}{(Math.abs(r.v ?? 0) / 100).toFixed(2)}%p</Grad></div>
                  {prev != null && lastV != null ? <div style={{ fontSize: 36, fontWeight: 900, marginTop: 6 }}>{prev.toFixed(2)}% <span style={{ color: SUBC }}>→</span> {lastV.toFixed(2)}%</div> : null}
                </Card>
              );
            })}
          </div>
          {t >= interpAt && (w as unknown as { rates_interp?: boolean }).rates_interp !== false ? (   /* 대사와 다른 자동 해석이면 끈다(9/20) */
            <Card color={YEL} style={{ ...pop(interpAt, 20), marginTop: 30, padding: "26px 34px" }}>
              <div style={{ fontSize: 46, fontWeight: 900, lineHeight: 1.25, wordBreak: "keep-all" }}>9월 한 번은 <span style={{ color: YEL }}>받아들임</span> · 계속 올린다고는 <span style={{ color: YEL }}>안 봄</span></div>
              <div style={{ fontSize: 26, fontWeight: 700, color: SUBC, marginTop: 10 }}>2년물(당장 정책)이 10년물(먼 앞날)보다 더 올랐다 · 숫자로 본 해석, 추천 아님</div>
            </Card>
          ) : null}
        </div>
      )}
    </UShell>
  );
};

/* ═════════ uw3: 달러·엔·원·유가·금 — 카드 5장(한 주 %, 방향 색). 이름을 말하면 그 카드가 밝아진다. ═════════ */
type FxItem = { key: string; label: string; sub: (v: number | null) => string; s?: Ser; dg: number; re: RegExp; note?: (v: number) => string };
const fxItems = (w: UW): FxItem[] => [
  { key: "DXY", label: "달러", s: w.fx?.DXY, dg: 2, sub: (v) => `달러 인덱스 ${numTxt(v)}`, re: /달러\s?인덱스|달러\s?가치|달러(는|가|도|값)|DXY/ },
  { key: "USDJPY", label: "엔·달러", s: w.fx?.USDJPY, dg: 2, sub: (v) => `1달러 = ${numTxt(v)}엔`, re: /엔화|엔·달러|엔달러|엔(은|이|도)\s/, note: (v) => (v > 0 ? "엔화 약세" : v < 0 ? "엔화 강세" : "") },
  { key: "USDKRW", label: "원·달러", s: w.fx?.USDKRW, dg: 1, sub: (v) => `1달러 = ${numTxt(v, 1)}원`, re: /원화|원·달러|원달러|환율/, note: (v) => (v > 0 ? "원화 약세" : v < 0 ? "원화 강세" : "") },
  { key: "WTI", label: "유가", s: w.commod?.WTI, dg: 2, sub: (v) => `WTI 배럴당 $${numTxt(v)}`, re: /유가|원유|WTI|브렌트|기름값/ },
  { key: "GOLD", label: "금", s: w.commod?.GOLD, dg: 1, sub: (v) => `온스당 $${numTxt(v, 1)}`, re: /금값|금 가격|국제 금|금(은|이|도|값)\s/ },
];
const Spark: React.FC<{ w: UW; s?: Ser; width: number; height: number; at: number }> = ({ w, s, width, height, at }) => {
  const { t } = useT();
  const days = weekDays(w);
  const sess = sessionsOf(w);
  const vals = [s?.prev_close ?? null, ...days.map((d) => (sess.includes(d) ? dayOf(s, d)?.close ?? null : null))];
  const ok = vals.filter((v): v is number => v != null);
  if (ok.length < 2) return null;
  const lo = Math.min(...ok), hi = Math.max(...ok);
  const sp = hi - lo || 1;
  const X = (i: number) => 6 + (i * (width - 12)) / (vals.length - 1);
  const Y = (v: number) => 6 + (1 - (v - lo) / sp) * (height - 12);
  let d = "";
  vals.forEach((v, i) => { if (v != null) d += `${d ? "L" : "M"}${X(i)} ${Y(v)}`; });
  const k = interpolate(t, [at, at + 0.8], [0, 1], { ...CLAMP, easing: ease });
  const col = colOf(s?.week_pct);
  const lastI = vals.reduce<number>((a, v, i) => (v != null ? i : a), 0);
  return (
    <svg width={width} height={height} style={{ display: "block", overflow: "visible" }}>
      <path d={d} fill="none" stroke={col} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - k} />
      <circle cx={X(lastI)} cy={Y(vals[lastI]!)} r={6} fill={col} opacity={k} />
    </svg>
  );
};

export const UW3: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const { list, cur } = curCue(cues, t);
  const items = fxItems(w).filter((x) => x.s && x.s.week_pct != null);
  const clean = (s: string) => s.replace(/원·달러|원달러|엔·달러|엔달러/g, (m) => (m.startsWith("원") ? "원화 " : "엔화 "));
  const said = (x: FxItem, s: string) => x.re.test(x.key === "DXY" ? clean(s) : s);
  const appearAt = (x: FxItem, k: number) => { const i = findIdx(list, (s) => said(x, s)); return i >= 0 ? Math.min(list[i].start, 0.2 + k * 0.22) : 0.2 + k * 0.22; };
  const activeK = cur && !isQ(cur.text) ? items.find((x) => said(x, cur.text))?.key : undefined;
  if (cur && isQ(cur.text) && !items.some((x) => said(x, cur.text))) {
    return (
      <UShell p={p} cues={cues} hideSub bg={<UBg name="macro" tone="neutral" dim={0.3} />}>
        <QBig text={cur.text} at={cur.start} />
      </UShell>
    );
  }
  const big = [...items].sort((a, b) => Math.abs(b.s!.week_pct!) - Math.abs(a.s!.week_pct!))[0];
  const asOf = asOfLabel(w);
  const card = (x: FxItem, k: number, wide: boolean) => {
    const v = x.s!.week_pct!;
    const lv = lastClose(x.s);
    const on = activeK === x.key;
    const po = pop(appearAt(x, k));
    const note = x.note ? x.note(v) : "";
    return (
      <Card key={x.key} color={colOf(v)} strong={on} dim={activeK && !on ? 0.52 : 0} style={{ ...po, padding: wide ? "20px 30px" : "20px 26px", flex: wide ? undefined : 1,
        display: "flex", flexDirection: wide ? "row" : "column", alignItems: wide ? "center" : "stretch", justifyContent: "space-between", minHeight: wide ? 0 : 292 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 48, fontWeight: 900 }}>{x.label}</span>
            {note ? <Chip bg={colOf(v)} fs={24} dark={false}>{note}</Chip> : null}
          </div>
          <div style={{ fontSize: wide ? 96 : 86, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.08 }}><Grad tone={toneOf(v)}>{pctTxt(v)}</Grad></div>
          <div style={{ fontSize: 28, fontWeight: 800, color: SUBC, whiteSpace: "nowrap" }}>{x.sub(lv)}</div>
        </div>
        <div style={{ marginTop: wide ? 0 : 14, alignSelf: wide ? "center" : "stretch" }}><Spark w={w} s={x.s} width={wide ? 320 : 400} height={wide ? 110 : 62} at={appearAt(x, k) + 0.2} /></div>
      </Card>
    );
  };
  const rows = [items.slice(0, 2), items.slice(2, 4)];
  const tail = items.slice(4);
  return (
    <UShell p={p} cues={cues} bg={<UBg name="macro" tone={toneOf(big?.s?.week_pct)} dim={0.42} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
        <div style={{ ...pop(0.05, 20), fontSize: 56, fontWeight: 900, textShadow: SH }}>이번 주 <span style={{ color: YEL }}>달러·엔·원·유가·금</span></div>
        <div style={{ ...pop(0.12, 16), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 4, textShadow: SH }}>한 주 등락률{asOf ? ` · ${asOf}` : ""} · 숫자가 오르면 빨강</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 382, display: "flex", flexDirection: "column", gap: 22 }}>
        {rows.map((r, ri) => (r.length ? <div key={ri} style={{ display: "flex", gap: 22 }}>{r.map((x, k) => card(x, ri * 2 + k, false))}</div> : null))}
        {tail.map((x, k) => card(x, 4 + k, true))}
      </div>
    </UShell>
  );
};

/* ═════════ uw4: 이번 주 겹친 뉴스·정치·전쟁 — 날짜 칩 + 분류 + 제목 + 연결 한 줄, 말하는 순서대로 한 장씩 ═════════ */
const newsDay = (n: News) => { const s = ymd(n.d ?? n.date); return s.length === 8 ? s : ""; };
const newsLine = (n: News) => [n.line, n.link_line, n.why, n.note, n.summary, n.text].find((x) => !!x && !/^https?:\/\//i.test(x.trim())) ?? "";
const TAGC: [RegExp, string][] = [[/전쟁|분쟁|중동|군사|공습|폭발|지정학/, "#FF9A5B"], [/정치|트럼프|대선|의회|관세|정부|백악관/, "#B99BFF"], [/연준|FOMC|금리|파월/, TEAL], [/지표|물가|CPI|PPI|고용|경제/, GOLD], [/유가|원유|OPEC|에너지/, "#FFB347"], [/기업|실적|반도체|AI|빅테크/, "#8FB4FF"]];
const tagColor = (tag: string) => TAGC.find(([re]) => re.test(tag))?.[1] ?? "#CFD6E4";

/** 뉴스가 비어 있을 때: 요일별 숫자 카드(지수·금리·유가의 그날 등락만 — 원인 문장 없음) */
const DayCards: React.FC<{ p: Props; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const { cur } = curCue(cues, t);
  const days = weekDays(w);
  const sess = sessionsOf(w);
  const hot = cur ? dayHits(cur.text, days) : [];
  const cell = (label: string, v: number | null | undefined, bp = false) => (v == null ? null : (
    <span style={{ fontSize: 32, fontWeight: 800, color: "#E6E6E3", whiteSpace: "nowrap" }}>{label} <span style={{ color: colOf(v) }}>{bp ? bpTxt(v) : `${arrow(v)}${Math.abs(v).toFixed(2)}%`}</span></span>
  ));
  return (
    <UShell p={p} cues={cues} bg={<UBg name="macro" tone="neutral" dim={0.46} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 228 }}>
        <div style={{ ...pop(0.05, 20), fontSize: 60, fontWeight: 900, textShadow: SH }}>이번 주 <span style={{ color: YEL }}>요일별 시장</span></div>
        <div style={{ ...pop(0.2, 20), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 6, textShadow: SH }}>그날 종가 기준 등락 · 숫자만</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 392, display: "flex", flexDirection: "column", gap: 22 }}>
        {days.map((d, k) => {
          const has = sess.includes(d);
          const c = dayOf(w.idx?.SPX, d)?.pct ?? null;
          const on = hot.includes(k);
          return (
            <Card key={d} color={has ? colOf(c) : "#8FA7D9"} strong={on} dim={hot.length && !on ? 0.45 : 0} style={{ ...pop(0.3 + k * 0.25), padding: "20px 28px", borderStyle: has ? "solid" : "dashed" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <Chip bg={has ? colOf(c) : "#8FA7D9"} fs={30}>{md(d)} {wdOf(d)}</Chip>
                {has ? <span style={{ fontSize: 40, fontWeight: 900 }}>S&P500 <span style={{ color: colOf(c) }}>{pctTxt(c)}</span></span> : <span style={{ fontSize: 36, fontWeight: 900, color: "#DCE3F0" }}>장 집계 전</span>}
              </div>
              {has ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 26px", marginTop: 12 }}>
                  {cell("나스닥", dayOf(w.idx?.IXIC, d)?.pct)}
                  {cell("10년물", dayOf(w.rates?.US10Y, d)?.chg_bp, true)}
                  {cell("유가", dayOf(w.commod?.WTI, d)?.pct)}
                  {cell("원·달러", dayOf(w.fx?.USDKRW, d)?.pct)}
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>
    </UShell>
  );
};

export const UW4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const secs = useSceneSec(p, cues);
  const { list, i: ci, cur } = curCue(cues, t);
  const items = (w.news ?? []).filter((n) => n && (n.title || n.headline)).slice(0, 4);
  let from = 0;
  const reveal = items.map((n, k) => {
    const d = newsDay(n);
    const title = n.title ?? n.headline ?? "";
    const words = title.replace(/[[\](){}'"‘’“”…·,.!?|]/g, " ").split(/\s+/).filter((x) => x.length >= 2 && !/뉴욕|증시|마감|하락|상승|지수|3대/.test(x));
    const i = findIdx(list, (s) => (d ? dayHits(s, [d]).length > 0 : false) || words.some((x) => x.length >= 3 && s.includes(x)), from);
    if (i >= 0) {
      const same = k + 1 < items.length && newsDay(items[k + 1]) === d && !!d;   // 같은 날 기사 두 건은 같은 문장에서 차례로
      from = same ? i : i + 1;
      const prevSame = k > 0 && newsDay(items[k - 1]) === d && !!d;
      return { at: list[i].start + (prevSame ? 0.6 : 0), idx: i };
    }
    const span = Math.max(secs - 1.2, 3);
    return { at: 0.5 + (span * k) / Math.max(items.length, 1), idx: -1 };
  });
  // 순서가 뒤집히지 않게(뒤 카드가 앞 카드보다 먼저 뜨지 않게)
  for (let k = 1; k < reveal.length; k++) if (reveal[k].at < reveal[k - 1].at) reveal[k] = { ...reveal[k], at: reveal[k - 1].at + 0.3 };
  // 대사가 카드 날짜를 차례로 부르지 않는 편(9/20)은 처음부터 다 띄운다 — 빈 화면 3초 금지
  if ((w as unknown as { news_reveal?: string }).news_reveal === "all") reveal.forEach((r, k) => { reveal[k] = { at: 0.15 + k * 0.25, idx: -1 }; });
  if (cur && isQ(cur.text) && !reveal.some((r) => r.idx === ci)) {
    return (
      <UShell p={p} cues={cues} hideSub bg={<UBg name="macro" tone="neutral" dim={0.36} />}>
        <QBig text={cur.text} at={cur.start} />
      </UShell>
    );
  }
  if (!items.length) return <DayCards p={p} cues={cues} />;
  const shown = reveal.map((r) => t >= r.at);
  const hotK = shown.lastIndexOf(true);
  const compact = items.length >= 4;
  return (
    <UShell p={p} cues={cues} bg={<UBg name="macro" tone="neutral" dim={0.46} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 228 }}>
        <div style={{ ...pop(0.05, 20), fontSize: 60, fontWeight: 900, textShadow: SH }}>이번 주 <span style={{ color: YEL }}>겹친 뉴스</span></div>
        <div style={{ ...pop(0.2, 20), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 6, textShadow: SH }}>같은 주에 시장과 함께 본 기사 · 원인 단정 아님</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 392, display: "flex", flexDirection: "column", gap: compact ? 18 : 24 }}>
        {items.map((n, k) => {
          const d = newsDay(n);
          const c = d ? dayOf(w.idx?.SPX, d)?.pct ?? null : null;
          const dcol = c == null ? "#CFD6E4" : colOf(c);
          const tag = n.tag ?? n.kind ?? n.cat ?? n.category ?? "";
          const po = pop(reveal[k].at);
          const on = k === hotK;
          const line = newsLine(n);
          const src = n.src ?? n.source ?? n.press ?? "";
          return (
            <Card key={k} color={tag ? tagColor(tag) : dcol} strong={on} dim={on ? 0 : 0.45} style={{ ...po, padding: compact ? "18px 28px" : "22px 30px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {d ? <Chip bg={dcol} fs={30}>{md(d)} {wdOf(d)}</Chip> : null}
                {tag ? <Chip bg={tagColor(tag)} fs={26}>{tag}</Chip> : null}
                {c != null ? <span style={{ fontSize: 28, fontWeight: 800, color: dcol, whiteSpace: "nowrap" }}>S&P500 {arrow(c)}{Math.abs(c).toFixed(2)}%</span> : null}
                {src ? <span style={{ marginLeft: "auto", fontSize: 24, fontWeight: 700, color: "#8E96A8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 220 }}>{src}</span> : null}
              </div>
              <div style={{ fontSize: compact ? 38 : 44, fontWeight: 900, lineHeight: 1.28, marginTop: 12, wordBreak: "keep-all", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{n.title ?? n.headline}</div>
              {line ? (
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start", fontSize: compact ? 30 : 34, fontWeight: 800, color: "#E6E6E3", marginTop: 10, lineHeight: 1.3, wordBreak: "keep-all" }}>
                  <span style={{ color: YEL, flex: "none" }}>↳</span><span>{line}</span>
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>
    </UShell>
  );
};

/* ═════════ uw5: 업종·대형주 막대 — 한 주 등락률(오른 곳 빨강 오른쪽 · 내린 곳 파랑 왼쪽). 대형주를 말하면 대형주로 바뀐다. ═════════ */
type Row = { key: string; label: string; sub: string; v: number; alias: string[] };
const HBars: React.FC<{ rows: Row[]; at: number; rowH: number; hotText: string }> = ({ rows, at, rowH, hotText }) => {
  const { t } = useT();
  const pop = usePop();
  const mx = Math.max(0.5, ...rows.map((r) => Math.abs(r.v)));
  const LW = 300, VW = 150, BW = 952 - LW - VW;
  const hasNeg = rows.some((r) => r.v < 0), hasPos = rows.some((r) => r.v > 0);
  const cx = hasNeg && hasPos ? LW + BW / 2 : hasNeg ? LW + BW : LW;
  const span = hasNeg && hasPos ? BW / 2 - 8 : BW - 8;
  const hot = (r: Row) => !!hotText && r.alias.some((a) => a.length >= 2 && norm(hotText).includes(norm(a)));
  const anyHot = rows.some(hot);
  return (
    <div style={{ position: "relative", width: 952, height: rows.length * rowH }}>
      <div style={{ position: "absolute", left: cx - 1, top: -6, width: 2, height: rows.length * rowH + 12, background: "rgba(230,230,227,0.35)" }} />
      {rows.map((r, i) => {
        const k = interpolate(t, [at + 0.15 + i * 0.05, at + 0.75 + i * 0.05], [0, 1], { ...CLAMP, easing: ease });
        const len = (Math.abs(r.v) / mx) * span * k;
        const col = colOf(r.v);
        const on = hot(r);
        const po = pop(at + i * 0.05, 12);
        return (
          <div key={r.key} style={{ ...po, opacity: (po.opacity as number) * (anyHot && !on ? 0.5 : 1), position: "absolute", left: 0, top: i * rowH, width: 952, height: rowH }}>
            {on ? <div style={{ position: "absolute", left: -14, right: -14, top: 3, bottom: 3, borderRadius: 14, background: "rgba(255,255,255,0.09)", border: "2px solid rgba(255,255,255,0.35)" }} /> : null}
            <div style={{ position: "absolute", left: 0, top: 0, width: LW - 14, height: rowH, display: "flex", alignItems: "center", gap: 10, whiteSpace: "nowrap", overflow: "hidden" }}>
              <span style={{ fontSize: Math.min(rowH >= 66 ? 38 : 34, fit(r.label, LW - 24 - emOf(r.sub) * 21, 38)), fontWeight: 900 }}>{r.label}</span>
              <span style={{ fontSize: 21, fontWeight: 800, color: SUBC }}>{r.sub}</span>
            </div>
            <div style={{ position: "absolute", top: rowH * 0.22, height: rowH * 0.56, left: r.v >= 0 ? cx : cx - len, width: Math.max(len, 3), borderRadius: 9, background: col, boxShadow: on ? `0 0 18px ${col}` : "none" }} />
            <div style={{ position: "absolute", right: 0, top: 0, width: VW, height: rowH, display: "flex", alignItems: "center", justifyContent: "flex-end", fontSize: rowH >= 66 ? 36 : 33, fontWeight: 900, color: r.v > 0 ? "#FF8A80" : r.v < 0 ? "#8FB4FF" : "#E6E6E3" }}>{pctTxt(r.v)}</div>
          </div>
        );
      })}
    </div>
  );
};

export const UW5: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const secs = useSceneSec(p, cues);
  const { list, i: ci, cur } = curCue(cues, t);
  const sec: Row[] = (w.sectors ?? []).filter((s) => s.week_pct != null).map((s) => ({ key: s.etf, label: s.name_ko ?? s.etf, sub: s.etf, v: s.week_pct!, alias: [s.name_ko ?? "", s.etf] })).sort((a, b) => b.v - a.v);
  const mega: Row[] = (w.megacaps ?? []).filter((s) => s.week_pct != null).map((s) => ({ key: s.ticker, label: s.name_ko ?? s.ticker, sub: s.ticker, v: s.week_pct!, alias: [s.name_ko ?? "", s.ticker] })).sort((a, b) => b.v - a.v);
  const megaRe = /대형주|빅테크|종목|매그니피센트|M7/;
  const mIdx = mega.length ? findIdx(list, (s) => megaRe.test(s) || mega.some((m) => m.alias.some((a) => a.length >= 2 && norm(s).includes(norm(a))))) : -1;
  const mAt = mIdx >= 0 ? list[mIdx].start : mega.length && sec.length ? Math.max(2, secs * 0.5) : mega.length ? 0 : 1e9;
  const stageMega = mega.length > 0 && (t >= mAt || !sec.length);
  if (cur && isQ(cur.text) && ci !== mIdx) {
    return (
      <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone={toneOf(w.idx?.SPX?.week_pct)} dim={0.3} />}>
        <QBig text={cur.text} at={cur.start} />
      </UShell>
    );
  }
  const rows = stageMega ? mega : sec;
  const at = stageMega ? (sec.length ? mAt : 0.1) : 0.1;
  const rowH = rows.length > 10 ? 64 : 70;
  const hotText = cur && t < cur.end + 0.6 ? cur.text : "";
  const up = rows.filter((r) => r.v > 0).length;
  return (
    <UShell p={p} cues={cues} bg={<UBg name="wallst" tone={toneOf(w.idx?.SPX?.week_pct)} dim={0.5} />}>
      <div key={stageMega ? "m" : "s"} style={{ position: "absolute", left: 64, right: 64, top: 226 }}>
        <div style={{ ...pop(at, 20), fontSize: 56, fontWeight: 900, textShadow: SH }}>{stageMega ? <>대형주 <span style={{ color: YEL }}>한 주 성적</span></> : <>업종별 <span style={{ color: YEL }}>한 주 성적</span></>}</div>
        <div style={{ ...pop(at + 0.1, 16), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 4, textShadow: SH }}>
          {stageMega ? "미국 주요 대형주 · 한 주 등락률" : "S&P500 업종 ETF · 한 주 등락률"} · 오른 곳 <span style={{ color: "#FF8A80" }}>{up}</span> · 내린 곳 <span style={{ color: "#8FB4FF" }}>{rows.filter((r) => r.v < 0).length}</span>
        </div>
      </div>
      <div key={stageMega ? "mb" : "sb"} style={{ position: "absolute", left: 64, right: 64, top: 392 }}>
        <HBars rows={rows} at={at} rowH={rowH} hotText={hotText} />
      </div>
    </UShell>
  );
};

/* ═════════ uw6: 우리 시각 한 줄 → 월요일 국장에서 볼 것 + 다음 주 미국 일정 → 끝 인사 ═════════ */
const Hi: React.FC<{ text: string }> = ({ text }) => {
  const parts = text.split(/([+−-]?[\d,.]+\s?(?:%|bp|달러|원|엔)|\d+일(?:\s?연속)?|사흘|나흘|닷새|이틀)/);
  return <>{parts.map((x, i) => (i % 2 ? <span key={i} style={{ color: YEL }}>{x}</span> : <React.Fragment key={i}>{x}</React.Fragment>))}</>;
};
const watchList = (w: UW): string[] => {
  const raw = w.kr_watch ?? w.monday_watch ?? null;
  const arr = raw == null ? [] : Array.isArray(raw) ? raw : [raw];
  return arr.map((x) => (typeof x === "string" ? x : x.q ?? x.text ?? "")).map((s) => s.trim()).filter(Boolean).slice(0, 3);
};

export const UW6: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const w = uw(p);
  const { t } = useT();
  const pop = usePop();
  const secs = useSceneSec(p, cues);
  const { list, cur } = curCue(cues, t);
  const endIdx = findIdx(list, (s) => /누가샀나였습니다|다음 주에 (뵙|만나)|매주 일요일|일요일 (낮|정오)|구독/.test(s));
  const monIdx = findIdx(list, (s) => /월요일에 볼|월요일 국장|볼 것|볼 건|봅니다/.test(s));
  const endAt = endIdx >= 0 ? list[endIdx].start : list.length ? list[list.length - 1].end + 0.15 : secs - 2.2;
  const monAt = monIdx >= 0 && monIdx !== endIdx ? list[monIdx].start : Math.min(endAt - 0.5, Math.max(2, secs * 0.4));
  if (t >= endAt) {
    return (
      <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone="neutral" dim={0.32} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(endAt + 0.05, 30) }}>
          <Logo scale={2.4} />
          <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 64, fontWeight: 800, marginTop: 190, textShadow: SH }}><UsTag />미국 주간은 매주</div>
          <div style={{ fontSize: 120, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: SH_Q }}>일요일 낮 12시</div>
        </div>
      </UShell>
    );
  }
  const vRaw = w.view_us ?? w.view ?? null;
  const fixed = typeof vRaw === "string" ? vRaw : vRaw?.text ?? "";
  const vCue = list.find((c) => /^정리하면/.test(c.text.trim()));
  const text = (fixed || vCue?.text || (t < monAt ? cur?.text : "") || sub || "").trim().replace(/^정리하면,?\s*/, "");
  const watch = watchList(w);
  const mCue = monIdx >= 0 ? list[monIdx].text : "";
  const items = watch.length ? watch : mCue ? [mCue.replace(/^월요일\s*국장(에서는|에선|에서)?\s*/, "").replace(/[을를]?\s*봅니다\.?$/, "").trim()] : [];
  const cal = (w.calendar_next ?? []).map((c) => ({ d: ymd(c.date ?? c.d), e: c.event_ko ?? c.text ?? "" })).filter((c) => c.e).slice(0, 3);
  const stage2 = t >= monAt && (items.length > 0 || cal.length > 0);
  const chg = w.idx?.SPX?.week_pct ?? null;
  const fs = stage2 ? (text.length <= 24 ? 58 : 50) : text.length <= 18 ? 104 : text.length <= 24 ? 88 : text.length <= 30 ? 72 : text.length <= 44 ? 64 : 56;
  return (
    <UShell p={p} cues={cues} hideSub={!fixed && !stage2} bg={<UBg name="wallst" tone={toneOf(chg)} dim={0.4} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: stage2 ? 228 : 300 }}>
        <div style={{ ...pop(0.05, 20), display: "flex", alignItems: "center", gap: 18, fontSize: stage2 ? 38 : 46, fontWeight: 900, textShadow: SH }}>
          <span style={{ width: 16, height: 16, borderRadius: 8, background: RED, boxShadow: "0 0 14px rgba(255,77,77,0.8)" }} />
          이번 주를 한 줄로
        </div>
        {text ? (
          <Card color="#CFD6E4" style={{ ...pop(0.2), marginTop: stage2 ? 16 : 30, padding: stage2 ? "26px 34px" : "46px 46px 52px", minHeight: stage2 ? 0 : 480, display: "flex", alignItems: "center" }}>
            <div style={{ fontSize: fs, fontWeight: 900, lineHeight: 1.3, letterSpacing: "-0.03em", wordBreak: "keep-all" }}><Hi text={text} /></div>
          </Card>
        ) : null}
        {!stage2 ? <div style={{ ...pop(0.4, 16), fontSize: 30, fontWeight: 700, color: SUBC, marginTop: 22, textShadow: SH }}>한 주 숫자로 본 해석 · 추천 아님</div> : null}
        {stage2 ? (
          <>
            {items.length ? (
              <Card color={YEL} strong style={{ ...pop(monAt), marginTop: 34 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 42, fontWeight: 900, color: YEL }}>
                  <svg width="42" height="42" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2.5" fill="none" stroke={YEL} strokeWidth="2" /><path d="M3 10h18M8 3v4M16 3v4" stroke={YEL} strokeWidth="2" /></svg>
                  월요일 국장에서 볼 것
                </div>
                {items.map((s, k) => (
                  <div key={k} style={{ ...pop(monAt + 0.2 + k * 0.2, 14), display: "flex", gap: 16, alignItems: "flex-start", fontSize: 54, fontWeight: 900, lineHeight: 1.28, marginTop: 14, wordBreak: "keep-all" }}>
                    <span style={{ color: YEL, flex: "none" }}>{items.length > 1 ? `${k + 1}` : "·"}</span><span>{s}</span>
                  </div>
                ))}
                <div style={{ fontSize: 26, fontWeight: 700, color: SUBC, marginTop: 14 }}>확인할 질문 · 매매 추천 아님</div>
              </Card>
            ) : null}
            {cal.length ? (
              <div style={{ ...pop(monAt + 0.5, 16), marginTop: 30 }}>
                <div style={{ fontSize: 34, fontWeight: 900, color: "#E6E6E3", textShadow: SH }}>다음 주 미국 일정</div>
                {cal.map((c, k) => (
                  <div key={k} style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 12, fontSize: 36, fontWeight: 800, textShadow: SH }}>
                    {c.d ? <Chip bg="rgba(56,211,200,0.9)" fs={28}>{md(c.d)} {wdOf(c.d)}</Chip> : null}
                    <span style={{ wordBreak: "keep-all" }}>{c.e}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </UShell>
  );
};

/* ═════════ 문장마다 바뀌는 화면(beats) — JJ 9/19 "말과 화면 불일치·20초 정지 = 대탈주" ═════════
 * props.beats = { uw1: [{m:"문장 속 낱말", kind, ...}], ... } — 그 낱말이 나오는 자막 줄이 시작될 때 그 조각으로 바뀐다(이전 조각은 사라진다). */
type BeatV = { label: string; value: string; sub?: string; tone?: "up" | "down" | "neutral" };
type Beat = { m: string; kind: "event" | "big" | "pair" | "flow" | "bars" | "cond" | "list" | "q" | "end"; day?: string; title?: string; text?: string;
  label?: string; value?: string; sub?: string; tone?: "up" | "down" | "neutral"; a?: BeatV; b?: BeatV;
  from?: { label: string; value: string }[]; to?: { label: string; value: string }; rows?: { label: string; v: number; vlabel: string }[];
  cond?: string; then?: string; items?: string[]; fs?: number };
const BG_OF: Record<string, "wallst" | "fed" | "macro"> = { uw1: "wallst", uw2: "fed", uw3: "macro", uw4: "macro", uw5: "wallst", uw6: "wallst" };
const beatTimes = (beats: Beat[], list: Cue[]) => {
  let from = 0, last = 0;
  return beats.map((b, k) => {
    let i = -1;
    for (let j = from; j < list.length; j++) if (list[j].text.includes(b.m)) { i = j; break; }
    const at = i >= 0 ? list[i].start : k === 0 ? 0 : last + 2.2;
    if (i >= 0) from = i;
    last = at;
    return at;
  });
};
const toneCol = (t?: string) => (t === "up" ? RED : t === "down" ? BLUE : "#E6E6E3");
const BeatBig: React.FC<{ v: BeatV; fs: number }> = ({ v, fs }) => (
  <Card color={toneCol(v.tone)} strong style={{ padding: "26px 34px" }}>
    <div style={{ fontSize: 42, fontWeight: 800, color: "#CFD6E4" }}>{v.label}</div>
    <div style={{ fontSize: fs, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.04, marginTop: 4, whiteSpace: "nowrap" }}><Grad tone={(v.tone ?? "neutral") as Tone}>{v.value}</Grad></div>
    {v.sub ? <div style={{ fontSize: 40, fontWeight: 800, color: "#E6E6E3", marginTop: 8, wordBreak: "keep-all" }}>{v.sub}</div> : null}
  </Card>
);
const DayChip: React.FC<{ d?: string; mb?: number }> = ({ d, mb = 0 }) => (d ? <div style={{ display: "inline-block", fontSize: 44, fontWeight: 900, color: "#0B0E16", background: YEL, borderRadius: 12, padding: "6px 22px", marginBottom: mb }}>{d}</div> : null);
const BeatView: React.FC<{ b: Beat; at: number }> = ({ b, at }) => {
  const pop = usePop();
  const wrap: React.CSSProperties = { position: "absolute", left: 64, right: 64, top: 300, ...pop(at, 26) };
  if (b.kind === "event") return (
    <div style={wrap}>
      <DayChip d={b.day} />
      <div style={{ fontSize: 92, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", marginTop: 26, textShadow: SH_BIG, wordBreak: "keep-all" }}>{b.title}</div>
      {b.text ? <div style={{ fontSize: 76, fontWeight: 900, lineHeight: 1.15, color: YEL, marginTop: 14, textShadow: SH_BIG, wordBreak: "keep-all" }}>{b.text}</div> : null}
    </div>
  );
  if (b.kind === "big") return (
    <div style={wrap}>
      <DayChip d={b.day} mb={22} />
      <BeatBig v={{ label: b.label ?? "", value: b.value ?? "", sub: b.sub, tone: b.tone }} fs={b.fs ?? 230} />
    </div>
  );
  if (b.kind === "pair") return (
    <div style={{ ...wrap, display: "flex", flexDirection: "column", gap: 26 }}>
      {b.day ? <div style={{ alignSelf: "flex-start" }}><DayChip d={b.day} /></div> : null}
      {b.a ? <BeatBig v={b.a} fs={150} /> : null}
      {b.b ? <div style={pop(at + 0.5, 20)}><BeatBig v={b.b} fs={150} /></div> : null}
    </div>
  );
  if (b.kind === "flow") return (
    <div style={wrap}>
      {b.title ? <div style={{ fontSize: 62, fontWeight: 900, textShadow: SH_BIG, marginBottom: 26, wordBreak: "keep-all" }}>{b.title}</div> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {(b.from ?? []).map((x, i) => (
          <Card key={i} color={BLUE} style={{ padding: "18px 30px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 60, fontWeight: 900 }}>{x.label}</div><div style={{ fontSize: 72, fontWeight: 900 }}><Grad tone="down">{x.value}</Grad></div>
          </Card>
        ))}
      </div>
      <div style={{ textAlign: "center", fontSize: 120, fontWeight: 900, color: YEL, lineHeight: 1.1, textShadow: SH_BIG, ...pop(at + 0.4, 16) }}>↓</div>
      {b.to ? (
        <div style={pop(at + 0.6, 20)}>
          <Card color={RED} strong style={{ padding: "22px 30px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 72, fontWeight: 900 }}>{b.to.label}</div><div style={{ fontSize: 76, fontWeight: 900 }}><Grad tone="up">{b.to.value}</Grad></div>
          </Card>
        </div>
      ) : null}
    </div>
  );
  if (b.kind === "bars") {
    const rows = b.rows ?? [];
    const mx = Math.max(1e-9, ...rows.map((r) => Math.abs(r.v)));
    const W0 = 900, H0 = 520, gap = 18, bw = (W0 - gap * (rows.length - 1)) / Math.max(1, rows.length), base = H0 * 0.3;
    return (
      <div style={wrap}>
        {b.title ? <div style={{ fontSize: 58, fontWeight: 900, textShadow: SH_BIG, marginBottom: 20, wordBreak: "keep-all" }}>{b.title}</div> : null}
        <Card color="#CFD6E4" style={{ padding: "26px 26px 18px" }}>
          <svg width={W0} height={H0 + 70} style={{ overflow: "visible" }}>
            <line x1={0} x2={W0} y1={base} y2={base} stroke="rgba(255,255,255,0.55)" strokeWidth={3} />
            {rows.map((r, i) => {
              const down = r.v < 0, h = (Math.abs(r.v) / mx) * (down ? H0 * 0.6 : H0 * 0.26);
              const x = i * (bw + gap), col = down ? BLUE : RED;
              return (
                <g key={i}>
                  <rect x={x} y={down ? base : base - h} width={bw} height={h} rx={8} fill={col} />
                  <text x={x + bw / 2} y={down ? base + h + 40 : base - h - 12} textAnchor="middle" fontSize={36} fontWeight={900} fill={col} fontFamily={FONT}>{r.vlabel}</text>
                  <text x={x + bw / 2} y={H0 + 56} textAnchor="middle" fontSize={34} fontWeight={800} fill="#CFD6E4" fontFamily={FONT}>{r.label}</text>
                </g>
              );
            })}
          </svg>
        </Card>
      </div>
    );
  }
  if (b.kind === "cond") return (
    <div style={wrap}>
      <Card color={toneCol(b.tone)} strong style={{ padding: "30px 34px" }}>
        <div style={{ fontSize: 46, fontWeight: 900, color: YEL }}>만약</div>
        <div style={{ fontSize: 86, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.03em", marginTop: 6, wordBreak: "keep-all" }}>{b.cond}</div>
        <div style={{ fontSize: 120, fontWeight: 900, lineHeight: 1, color: YEL, margin: "14px 0" }}>→</div>
        <div style={{ fontSize: 70, fontWeight: 900, lineHeight: 1.18, wordBreak: "keep-all" }}><Grad tone={(b.tone ?? "neutral") as Tone}>{b.then}</Grad></div>
      </Card>
    </div>
  );
  if (b.kind === "list") return (
    <div style={wrap}>
      {b.title ? <div style={{ fontSize: 66, fontWeight: 900, textShadow: SH_BIG, marginBottom: 26, wordBreak: "keep-all" }}>{b.title}</div> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {(b.items ?? []).map((x, i) => (
          <div key={i} style={pop(at + 0.2 + i * 0.35, 18)}>
            <Card color={YEL} strong={i === 0} style={{ padding: "24px 30px", display: "flex", gap: 22, alignItems: "center" }}>
              <div style={{ fontSize: 60, fontWeight: 900, color: YEL }}>✓</div>
              <div style={{ fontSize: 58, fontWeight: 900, lineHeight: 1.2, wordBreak: "keep-all" }}>{x}</div>
            </Card>
          </div>
        ))}
      </div>
    </div>
  );
  if (b.kind === "end") return (
    <div style={{ position: "absolute", left: 64, right: 64, top: 600, ...pop(at, 24) }}>
      <Logo scale={2.4} />
      <div style={{ fontSize: 62, fontWeight: 800, marginTop: 190, color: "#CFD6E4" }}>평일 국장 마감은 매일</div>
      <div style={{ fontSize: 110, fontWeight: 900, color: YEL, textShadow: "0 0 30px rgba(255,216,77,0.4)" }}>저녁 5시</div>
    </div>
  );
  return null;
};
const UBeats = (id: string): React.FC<{ p: Props; sub: string; cues?: Cue[] }> => ({ p, cues }) => {
  const w = uw(p) as UW & { beats?: Record<string, Beat[]> };
  const { t } = useT();
  const beats = w.beats?.[id] ?? [];
  const list = cues ?? [];
  const ats = beatTimes(beats, list);
  let k = 0;
  for (let j = 0; j < ats.length; j++) if (t >= ats[j] - 0.05) k = j;
  const b = beats[k];
  const hide = b?.kind === "q" || b?.kind === "end";
  const qText = b?.kind === "q" ? (list.find((c) => c.text.includes(b.m))?.text ?? b.title ?? "") : "";
  return (
    <UShell p={p} cues={cues} hideSub={hide} bg={<UBg name={BG_OF[id] ?? "wallst"} tone={b?.tone === "down" ? "down" : b?.tone === "up" ? "up" : "neutral"} dim={0.5} />}>
      {b?.kind === "q" ? <QBig text={qText} at={ats[k]} /> : b ? <BeatView key={k} b={b} at={ats[k]} /> : null}
    </UShell>
  );
};

/* ═════════ uw0 사건 대비 훅(9/20) — 0초부터 '금리 ▲ 인상 / 그런데 / AI 반도체 +6%' + 요일 막대 ═════════ */
type HookC = { top: { label: string; value: string; sub: string }; mid: string; bottom: { label: string; value: string; sub: string }; days: { d: string; v: number }[] };
const UW0C: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = uw(p) as UW & { hook_contrast?: HookC };
  const h = w.hook_contrast!;
  const { t } = useT();
  const list = cues ?? [];
  const qNow = [...list].reverse().find((c) => isQ(c.text) && t >= c.start);
  if (qNow) return (
    <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone="up" dim={0.3} />}>
      <QBig text={qNow.text} at={qNow.start} />
    </UShell>
  );
  const mx = Math.max(1e-9, ...h.days.map((d) => Math.abs(d.v)));
  return (
    <UShell p={p} cues={cues} hideSub bg={<UBg name="wallst" tone="up" dim={0.35} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 230 }}>
        <div style={{ fontSize: 46, fontWeight: 800, color: "#CFD6E4", textShadow: SH }}>{h.top.label}</div>
        <div style={{ fontSize: 190, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.02, textShadow: SH_BIG, whiteSpace: "nowrap" }}><Grad tone="up">{h.top.value}</Grad></div>
        <div style={{ fontSize: 46, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>{h.top.sub}</div>
        <div style={{ fontSize: 110, fontWeight: 900, color: YEL, margin: "24px 0 8px", textShadow: SH_BIG }}>{h.mid}</div>
        <div style={{ fontSize: 46, fontWeight: 800, color: "#CFD6E4", textShadow: SH }}>{h.bottom.label}</div>
        <div style={{ fontSize: 240, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 1.0, textShadow: SH_BIG, whiteSpace: "nowrap" }}><Grad tone="up">{h.bottom.value}</Grad></div>
        <div style={{ fontSize: 46, fontWeight: 800, color: "#E6E6E3", textShadow: SH }}>{h.bottom.sub}</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 1250, height: 300, display: "flex", gap: 18 }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 150, height: 3, background: "rgba(255,255,255,0.5)" }} />
        {h.days.map((d, i) => {
          const hh = (Math.abs(d.v) / mx) * 130 * Math.min(1, Math.max(0, (t + 0.4) * 3 - i));
          return (
            <div key={i} style={{ flex: 1, height: 300, position: "relative" }}>
              <div style={{ position: "absolute", left: 6, right: 6, top: d.v >= 0 ? 150 - hh : 150, height: hh, background: d.v >= 0 ? RED : BLUE, borderRadius: 8, boxShadow: `0 0 18px ${d.v >= 0 ? RED : BLUE}88` }} />
              <div style={{ position: "absolute", left: 0, right: 0, top: d.v >= 0 ? 150 - hh - 44 : 150 + hh + 6, textAlign: "center", fontSize: 32, fontWeight: 900, color: d.v >= 0 ? RED : BLUE }}>{d.v > 0 ? "+" : "−"}{Math.abs(d.v).toFixed(1)}%</div>
              <div style={{ position: "absolute", left: 0, right: 0, bottom: -10, textAlign: "center", fontSize: 32, fontWeight: 800, color: "#CFD6E4" }}>{d.d}</div>
            </div>
          );
        })}
      </div>
    </UShell>
  );
};

/** 장면 id → 미국 주간 화면. Video.tsx가 uw0~uw6에 이것을 쓴다(오케스트레이터가 연결). */
const USW_BASE: Record<string, React.FC<{ p: Props; sub: string; cues?: Cue[] }>> = { uw0: UW0, uw1: UW1, uw2: UW2, uw3: UW3, uw4: UW4, uw5: UW5, uw6: UW6 };
/** beats·hook_contrast 가 있으면 그 화면(문장마다 바뀜), 없으면 예전 화면 */
const usRoute = (id: string): React.FC<{ p: Props; sub: string; cues?: Cue[] }> => (props) => {
  const w = uw(props.p) as UW & { beats?: Record<string, Beat[]>; hook_contrast?: HookC };
  if (id === "uw0" && w.hook_contrast) return <UW0C {...props} />;
  if (w.beats?.[id]?.length) { const B = UBeats(id); return <B {...props} />; }
  const X = USW_BASE[id];
  return <X {...props} />;
};
export const USW_COMP: Record<string, React.FC<{ p: Props; sub: string; cues?: Cue[] }>> = Object.fromEntries(Object.keys(USW_BASE).map((id) => [id, usRoute(id)]));
