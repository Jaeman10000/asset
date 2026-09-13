import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { Chart } from "./Chart";
import { Frame, S6 } from "./Scenes";
import type { Cue } from "./Scenes";
import { C, PAD, SIZE, FOOTER, colorOf, fmtPct } from "./tokens";
import type { Props } from "./types";

/** 미국편 v4 props (computed_us.json) — 인트로 훅 → 지수 → 이벤트·관문 → 돈의 흐름 → 국장 연결 */
export type Etf = { symbol: string; name: string; open?: number; high?: number; low?: number; close?: number; pct: number; prev_close?: number;
  value_ratio20?: number | null; streak?: number; pct5?: number | null; missing?: boolean };
export type PropsUS = Props & {
  edition: "us"; session_et: string; headline: string; hook?: string; index: Record<string, Etf | null>; idx?: Record<string, Etf>; qqq_points: { t: string; pct: number }[];
  sectors: Etf[]; links: Record<string, Etf>; btc?: { price: number; chg_pct: number } | null;
  prev_foreign?: { date: string; foreign: number } | null;
  events: { kst: string; kst_spoken: string; what: string; react30?: number; react_close?: number }[];
  bls_values?: { what: string; period: string; values: Record<string, number>; stale?: boolean } | null;
  tre: { y10?: number; chg_bp?: number | null }; wti: { wti?: number; chg_pct?: number; fresh?: boolean };
  u3_title: string; weekend?: boolean;
};
type SP = { p: PropsUS; sub: string; cues?: Cue[] };
const stk = (p: PropsUS) => (p.stocks as unknown as Etf[]);

const ease = Easing.out(Easing.cubic);
const Reveal: React.FC<{ at: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at, children, style }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [at, at + 0.45 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return <div style={{ opacity: t, transform: `translateY(${(1 - t) * 24}px)`, ...style }}>{children}</div>;
};
const fade = (f: number, at: number, fps: number) => interpolate(f, [at, at + 0.4 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const K: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontSize: SIZE.small, color: C.sub, letterSpacing: "0.02em", ...style }}>{children}</div>
);
const usd = (v?: number) => (v == null ? "—" : `$${v.toFixed(2)}`);
const num = (v?: number) => (v == null ? "—" : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 }));
const fmtEokKR = (v: number) => { const a = Math.abs(Math.round(v)); const s = a >= 10000 ? `${(a / 10000).toFixed(1).replace(/\.0$/, "")}조` : `${a.toLocaleString("ko-KR")}억`; return (v > 0 ? "＋" : v < 0 ? "−" : "") + s; };
const gate = (s: { d: string; t: string }) => {
  const short: Record<string, string> = { "미국 고용보고서": "고용보고서", "미국 소비자물가 CPI": "CPI", "미국 생산자물가 PPI": "PPI", "선물·옵션 동시만기": "국장 동시만기", "옵션 만기": "국장 옵션 만기", "미국 실질임금": "실질임금", "미국 구인건수 JOLTS": "JOLTS" };
  const t = short[s.t] ?? s.t;
  if (s.d.includes("~")) { const [a, b] = s.d.split("~"); return [`${+a.slice(5, 7)}/${+a.slice(8, 10)}–${+b.slice(-2)}`, t]; }
  return [`${+s.d.slice(5, 7)}/${+s.d.slice(8, 10)}${s.d.length >= 16 ? " " + s.d.slice(11, 16) : ""}`, t];
};
/** 나스닥 대표값: 공식 지수(^IXIC) 우선, 없으면 QQQ */
const nasdaq = (p: PropsUS) => (p.idx?.IXIC ? { e: p.idx.IXIC, label: "나스닥 종합", fmt: num } : { e: p.index?.QQQ ?? undefined, label: "나스닥100 QQQ", fmt: usd });

/** u0 인트로 훅 — 헤드라인(원인+결과)이 첫 화면 = 썸네일 */
export const U0: React.FC<SP> = ({ p }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [0, 0.6 * fps], [0, 1], { extrapolateRight: "clamp", easing: ease });
  const n = nasdaq(p);
  return (
    <AbsoluteFill style={{ background: C.bg, color: C.text, fontFamily: "Pretendard, 'Noto Sans KR', sans-serif", fontVariantNumeric: "tabular-nums", justifyContent: "center", padding: `0 ${PAD}px` }}>
      <div style={{ opacity: t, transform: `translateY(${(1 - t) * 24}px)` }}>
        <K>{p.brand ?? "밤낮장"} · {p.date_label} 미국장 마감{p.weekend ? " · 주말 정리" : ""}</K>
        <div style={{ fontSize: 88, fontWeight: 600, lineHeight: 1.2, letterSpacing: "-0.02em", marginTop: 28, wordBreak: "keep-all" }}>{p.headline}</div>
        {n.e && (
          <div style={{ marginTop: 56, display: "flex", alignItems: "baseline", gap: 24 }}>
            <span style={{ fontSize: SIZE.small, color: C.sub }}>{n.label}</span>
            <span style={{ fontSize: 72, fontWeight: 600 }}>{n.fmt(n.e.close)}</span>
            <span style={{ fontSize: 44, fontWeight: 600, color: colorOf(n.e.pct) }}>{fmtPct(n.e.pct)}</span>
          </div>
        )}
        {n.e && <div style={{ marginTop: 16, height: 14, width: `${Math.min(100, Math.abs(n.e.pct) * 25)}%`, background: colorOf(n.e.pct) }} />}
      </div>
      <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};

/** u1 지수 넷(공식 지수) + QQQ 정규장 선 — 고·저·종가만 */
export const U1: React.FC<SP> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const prog = interpolate(f, [0.6 * fps, 4.0 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const labels = [0, fade(f, 2.4 * fps, fps), 0, fade(f, 3.2 * fps, fps), fade(f, 4.2 * fps, fps)];
  const ix = p.idx ?? {};
  const four: { k: string; e?: Etf | null; fmt: (v?: number) => string }[] = ix.IXIC
    ? [{ k: "나스닥 종합", e: ix.IXIC, fmt: num }, { k: "S&P500", e: ix.GSPC, fmt: num }, { k: "다우", e: ix.DJI, fmt: num }, { k: "필라델피아 반도체", e: ix.SOX, fmt: num }]
    : [{ k: "나스닥100 QQQ", e: p.index?.QQQ, fmt: usd }, { k: "S&P500 SPY", e: p.index?.SPY, fmt: usd }, { k: "다우 DIA", e: p.index?.DIA, fmt: usd }, { k: "반도체 SOXX", e: p.links?.SOXX, fmt: usd }];
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>{p.date_label} 미국장 · 전일 종가 대비 · 고점 / 저점 / 종가</K></Reveal>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "36px 32px", marginTop: 32 }}>
        {four.map((x, i) => (
          <Reveal key={x.k} at={4 + i * 4}>
            <K>{x.k}</K>
            <div style={{ fontSize: 80, fontWeight: 600, lineHeight: 1.1, color: colorOf(x.e?.pct) }}>{fmtPct(x.e?.pct)}</div>
            <K>{x.e ? `종가 ${x.fmt(x.e.close)}` : "—"}</K>
            <K>{x.e ? `고 ${x.fmt(x.e.high)} · 저 ${x.fmt(x.e.low)}` : ""}</K>
          </Reveal>
        ))}
      </div>
      <div style={{ marginTop: 40 }}><Chart p={p} night={prog} day={0} labels={labels} mode="us" scale={1} /></div>
    </Frame>
  );
};

const Num: React.FC<{ k: string; v: string; c?: string; note: string; size?: number }> = ({ k, v, c, note, size }) => (
  <div>
    <K>{k}</K>
    <div style={{ fontSize: size ?? 84, fontWeight: 600, color: c ?? C.text, lineHeight: 1.1, marginTop: 6, whiteSpace: "nowrap" }}>{v}</div>
    <K style={{ marginTop: 6 }}>{note}</K>
  </div>
);

/** 천 명 단위 → '+16만 2천 명' */
const manKo = (k: number) => { const n = Math.abs(k); const man = Math.floor(n / 10); const chun = n % 10; const body = n >= 10 ? `${man}만${chun ? ` ${chun}천` : ""}` : `${chun}천`; return `${k < 0 ? "−" : "+"}${body} 명`; };
const valueCards = (bv?: PropsUS["bls_values"]) => {
  if (!bv || bv.stale) return [] as { k: string; v: string; note: string }[];
  const v = bv.values; const m = +bv.period.slice(5);
  if (bv.what === "Employment Situation") return [
    ...(v.nfp_k != null ? [{ k: `${m}월 비농업 고용`, v: manKo(v.nfp_k), note: "BLS · 전월 대비" }] : []),
    ...(v.unemp != null ? [{ k: `${m}월 실업률`, v: `${v.unemp}%`, note: v.unemp_prev != null ? `전달 ${v.unemp_prev}%` : "" }] : []),
  ];
  if (bv.what === "Consumer Price Index") return [
    ...(v.cpi_yy != null ? [{ k: `${m}월 CPI 전년비`, v: `${v.cpi_yy}%`, note: "BLS" }] : []),
    ...(v.core_mm != null ? [{ k: `${m}월 근원 전월비`, v: `${v.core_mm}%`, note: v.cpi_mm != null ? `헤드라인 ${v.cpi_mm}%` : "" }] : []),
  ];
  if (bv.what === "Producer Price Index" && v.ppi_mm != null) return [{ k: `${m}월 PPI 전월비`, v: `${v.ppi_mm}%`, note: "BLS" }];
  if (bv.what === "Job Openings" && v.jolts_k != null) return [{ k: `${m}월 구인 건수`, v: `${Math.round(v.jolts_k / 10).toLocaleString("ko-KR")}만 건`, note: "BLS" }];
  return [];
};

/** u2 이벤트 → 결과 숫자 → 시장 반응 → 다음 관문 */
export const U2: React.FC<SP> = ({ p, sub, cues }) => {
  const e = (p.events ?? [])[0];
  const cards = valueCards(p.bls_values);
  const gates = (p.schedule ?? []).slice(0, p.weekend ? 3 : 2);
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>{p.weekend ? "지난 금요일 밤" : "간밤"} 이벤트 · {p.date_label}</K></Reveal>
      <Reveal at={3} style={{ marginTop: 24 }}>
        {e ? (
          <>
            <K>{e.kst ? e.kst.slice(11, 16) : ""} KST</K>
            <div style={{ fontSize: SIZE.mid - 8, fontWeight: 600, lineHeight: 1.22, marginTop: 6 }}>{e.what}</div>
          </>
        ) : <div style={{ fontSize: SIZE.mid - 8, fontWeight: 600 }}>예정 지표 없음</div>}
      </Reveal>
      {cards.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "40px 40px", marginTop: 40 }}>
          {cards.map((c, i) => <Reveal key={c.k} at={10 + i * 4}><Num k={c.k} v={c.v} note={c.note} size={c.v.length > 7 ? 68 : 84} /></Reveal>)}
        </div>
      )}
      {e && e.react30 != null && (
        <Reveal at={20} style={{ marginTop: 40, fontSize: SIZE.small + 6, display: "flex", gap: 40 }}>
          <span><span style={{ color: C.sub }}>발표 후 30분 </span><b style={{ color: colorOf(e.react30) }}>{fmtPct(e.react30)}</b></span>
          {e.react_close != null && <span><span style={{ color: C.sub }}>이후 마감까지 </span><b style={{ color: colorOf(e.react_close) }}>{fmtPct(e.react_close)}</b></span>}
        </Reveal>
      )}
      <Reveal at={30} style={{ marginTop: 56 }}>
        <K>{p.weekend ? "이번 주 관문" : "다음 관문"}{p.tre?.y10 != null ? ` · 미 10년물 ${p.tre.y10.toFixed(2)}%${p.tre.chg_bp ? ` (${p.tre.chg_bp > 0 ? "+" : ""}${p.tre.chg_bp}bp)` : ""}` : ""}</K>
        <div style={{ fontSize: SIZE.small + 10, lineHeight: 1.7, marginTop: 8 }}>
          {gates.map((s, i) => { const [a, b] = gate(s); return <div key={i}><span style={{ color: C.sub, marginRight: 20 }}>{a}</span>{b}</div>; })}
        </div>
      </Reveal>
    </Frame>
  );
};

/** u3 돈의 흐름 — 섹터 상위 5·하위 3 + 레버리지 ETF + 서학개미 종목 */
export const U3: React.FC<SP> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const all = p.sectors ?? [];
  const rows = all.length > 8 ? [...all.slice(0, 5), ...all.slice(-3)] : all;
  const maxAbs = Math.max(0.5, ...all.map((s) => Math.abs(s.pct ?? 0)));
  const lev = [p.links?.SOXL, p.links?.TQQQ].filter(Boolean) as Etf[];
  const mv = ((p as unknown as { movers?: Etf[] }).movers ?? []);
  const stocks = (mv.length ? mv : (stk(p) ?? [])).slice(0, 6);
  const stockLabel = mv.length ? `${(p as unknown as { mover_min?: number }).mover_min ?? 3}% 이상 움직인 종목 · 미국 대형주 36 중` : "서학개미 보관 상위 · 3% 이상 움직인 종목 없음";
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>미국 돈의 흐름 · 섹터 ETF 상위 5 · 하위 3 · 거래대금 배수 · 연속일</K></Reveal>
      <Reveal at={3} style={{ marginTop: 20 }}>
        <div style={{ fontSize: SIZE.mid - 12, fontWeight: 600, lineHeight: 1.22 }}>{p.u3_title}</div>
      </Reveal>
      <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "210px 1fr 170px 150px", columnGap: 16, alignItems: "center" }}>
        {rows.map((s, i) => {
          const at = 8 + i * 3;
          const w = interpolate(f, [at + 6, at + 6 + 0.6 * fps], [0, (Math.abs(s.pct ?? 0) / maxAbs) * 50], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
          const pos = (s.pct ?? 0) >= 0;
          const hot = (s.value_ratio20 ?? 0) >= 1.3;
          const tag = [hot ? `${s.value_ratio20?.toFixed(1)}×` : "", (s.streak ?? 0) >= 3 ? `${s.streak}일↑` : (s.streak ?? 0) <= -3 ? `${-s.streak!}일↓` : ""].filter(Boolean).join(" ");
          const gap = i === 5 && all.length > 8 ? 18 : 0;
          const cell: React.CSSProperties = { height: 68, marginTop: gap, display: "flex", alignItems: "center", fontSize: 34, lineHeight: 1.2, whiteSpace: "nowrap" };
          return (
            <React.Fragment key={s.symbol}>
              <Reveal at={at} style={cell}>{s.name}</Reveal>
              <Reveal at={at} style={cell}>
                <div style={{ position: "relative", height: 14, width: "100%" }}>
                  <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 2, background: C.line }} />
                  <div style={{ position: "absolute", top: 0, bottom: 0, background: colorOf(s.pct), ...(pos ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }) }} />
                </div>
              </Reveal>
              <Reveal at={at} style={{ ...cell, fontSize: SIZE.tiny, color: C.sub }}>{tag}</Reveal>
              <Reveal at={at} style={{ ...cell, justifyContent: "flex-end", fontWeight: 600, color: colorOf(s.pct) }}>{fmtPct(s.pct)}</Reveal>
            </React.Fragment>
          );
        })}
      </div>
      {lev.length > 0 && (
        <Reveal at={36} style={{ marginTop: 28, display: "flex", gap: 40, fontSize: SIZE.small + 4 }}>
          {lev.map((x) => <span key={x.symbol}><span style={{ color: C.sub }}>{x.name} </span><b style={{ color: colorOf(x.pct) }}>{fmtPct(x.pct)}</b>{(x.value_ratio20 ?? 0) >= 1.3 ? <span style={{ color: C.sub }}> · {x.value_ratio20?.toFixed(1)}×</span> : null}</span>)}
        </Reveal>
      )}
      {stocks.length > 0 && (
        <Reveal at={44} style={{ marginTop: 28 }}>
          <K>{stockLabel}</K>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px 16px", marginTop: 10, fontSize: SIZE.small - 2, whiteSpace: "nowrap" }}>
            {stocks.map((x) => <div key={x.symbol}><span style={{ color: C.sub }}>{x.name} </span><b style={{ color: colorOf(x.pct) }}>{fmtPct(x.pct)}</b></div>)}
          </div>
        </Reveal>
      )}
    </Frame>
  );
};

/** u4 국장 연결 + 오늘 체크 + 어시스트 */
export const U4: React.FC<SP> = ({ p, sub, cues }) => {
  const ewy = p.links?.EWY; const sox = p.idx?.SOX ?? p.links?.SOXX;
  const w = (p.watch ?? [])[0] as { q: string; how: string; assist?: string } | undefined;
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>국장 연결 지표 · 오늘 국장에서 볼 것</K></Reveal>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "40px 32px", marginTop: 36 }}>
        <Reveal at={4}><Num k="한국 ETF · EWY" v={fmtPct(ewy?.pct)} c={colorOf(ewy?.pct)} note={ewy ? usd(ewy.close) : ""} /></Reveal>
        <Reveal at={8}><Num k={p.idx?.SOX ? "필라델피아 반도체" : "반도체 · SOXX"} v={fmtPct(sox?.pct)} c={colorOf(sox?.pct)} note={sox ? (p.idx?.SOX ? num(sox.close) : usd(sox.close)) : ""} /></Reveal>
        <Reveal at={12}>{p.prev_foreign?.foreign != null ? <Num k={`${p.weekend ? "지난 금요일" : "전날"} 국장 외국인 · ${p.prev_foreign.date.slice(4, 6)}/${p.prev_foreign.date.slice(6)}`} v={fmtEokKR(p.prev_foreign.foreign)} c={colorOf(p.prev_foreign.foreign)} note="정규장 체결 기준" /> : <Num k="전날 국장 외국인" v="—" note="" />}</Reveal>
        <Reveal at={16}>{p.fx ? <Num k="환율" v={p.fx.close.toLocaleString("ko-KR", { minimumFractionDigits: 1 })} c={colorOf(p.fx.chg)} note={p.fx.chg != null ? `${p.fx.chg > 0 ? "+" : ""}${p.fx.chg}원` : ""} /> : <Num k="환율" v="—" note="" />}</Reveal>
      </div>
      {w && (
        <Reveal at={24} style={{ marginTop: 64 }}>
          <K>오늘 국장에서 체크</K>
          <div style={{ fontSize: SIZE.body - 6, fontWeight: 600, lineHeight: 1.3, marginTop: 8, wordBreak: "keep-all" }}>{w.q}</div>
          {w.assist ? <div style={{ fontSize: SIZE.small + 4, color: "#D9D9D6", lineHeight: 1.45, marginTop: 14, wordBreak: "keep-all" }}>{w.assist}</div> : null}
          <K style={{ marginTop: 10 }}>→ {w.how}</K>
        </Reveal>
      )}
    </Frame>
  );
};

export const U5 = S6;

/** Threads 카드(미국편) 1080×1350 */
export const CardUS: React.FC<PropsUS> = (p) => {
  const secs = (p.sectors ?? []).slice(0, 4);
  const bot = (p.sectors ?? []).slice(-2).reverse();
  const maxAbs = Math.max(0.5, ...(p.sectors ?? []).map((s) => Math.abs(s.pct ?? 0)));
  const row = (s: Etf) => (
    <div key={s.symbol} style={{ display: "grid", gridTemplateColumns: "150px 1fr 130px", alignItems: "center", columnGap: 14, fontSize: 26, marginBottom: 5 }}>
      <span>{s.name}</span>
      <div style={{ position: "relative", height: 10 }}><div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 2, background: C.line }} />
        <div style={{ position: "absolute", top: 0, bottom: 0, background: colorOf(s.pct), ...((s.pct ?? 0) >= 0 ? { left: "50%", width: `${(Math.abs(s.pct ?? 0) / maxAbs) * 50}%` } : { right: "50%", width: `${(Math.abs(s.pct ?? 0) / maxAbs) * 50}%` }) }} /></div>
      <span style={{ textAlign: "right", fontWeight: 600, color: colorOf(s.pct) }}>{fmtPct(s.pct)}</span>
    </div>
  );
  const e = (p.events ?? [])[0];
  const cards = valueCards(p.bls_values);
  const ix = p.idx ?? {};
  const four = ix.IXIC
    ? [{ k: "나스닥", e: ix.IXIC }, { k: "S&P500", e: ix.GSPC }, { k: "다우", e: ix.DJI }, { k: "반도체", e: ix.SOX }]
    : [{ k: "나스닥100", e: p.index?.QQQ }, { k: "S&P500", e: p.index?.SPY }, { k: "다우", e: p.index?.DIA }, { k: "반도체 SOXX", e: p.links?.SOXX }];
  const w = (p.watch ?? [])[0] as { q: string; how: string; assist?: string } | undefined;
  return (
    <AbsoluteFill style={{ background: C.bg, color: C.text, fontFamily: "Pretendard, 'Noto Sans KR', sans-serif", fontVariantNumeric: "tabular-nums", padding: "56px 96px 56px" }}>
      <div style={{ fontSize: 26, color: C.sub }}>{p.date_label} 미국장 마감{p.weekend ? " · 주말 정리" : ""}</div>
      <div style={{ fontSize: 44, fontWeight: 600, lineHeight: 1.25, letterSpacing: "-0.01em", marginTop: 6, wordBreak: "keep-all" }}>{p.headline}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginTop: 22, borderTop: `2px solid ${C.line}`, paddingTop: 14 }}>
        {four.map((x) => (
          <div key={x.k}><div style={{ fontSize: 22, color: C.sub }}>{x.k}</div><div style={{ fontSize: 40, fontWeight: 600, color: colorOf(x.e?.pct) }}>{fmtPct(x.e?.pct)}</div></div>
        ))}
      </div>
      <div style={{ borderTop: `2px solid ${C.line}`, paddingTop: 12, marginTop: 16 }}>
        <div style={{ fontSize: 26, color: C.sub, marginBottom: 6 }}>이벤트 · 결과 · 다음 관문</div>
        <div style={{ fontSize: 27, lineHeight: 1.5 }}>
          {e ? <div><span style={{ color: C.sub }}>{e.kst ? e.kst.slice(11, 16) : ""}</span> {e.what}{cards.length ? <span style={{ color: C.sub }}> · {cards.map((c) => `${c.k} ${c.v}`).join(" · ")}</span> : null}{e.react30 != null ? <span style={{ color: C.sub }}> · 30분 <b style={{ color: colorOf(e.react30) }}>{fmtPct(e.react30)}</b></span> : null}</div> : <div style={{ color: C.sub }}>예정 지표 없음</div>}
          <div style={{ color: C.sub }}>{(p.schedule ?? []).slice(0, 3).map((s) => gate(s).join(" ")).join(" · ")} · 10년물 {p.tre?.y10 != null ? `${p.tre.y10.toFixed(2)}%` : "—"}</div>
        </div>
      </div>
      <div style={{ borderTop: `2px solid ${C.line}`, paddingTop: 12, marginTop: 16 }}>
        <div style={{ fontSize: 26, color: C.sub, marginBottom: 6 }}>미국 돈의 이동 · 섹터 ETF</div>
        {secs.map(row)}{bot.map(row)}
      </div>
      <div style={{ borderTop: `2px solid ${C.line}`, paddingTop: 12, marginTop: 16 }}>
        <div style={{ fontSize: 26, color: C.sub, marginBottom: 6 }}>크게 움직인 종목 · 국장 연결</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px 16px", fontSize: 27 }}>
          {(((p as unknown as { movers?: Etf[] }).movers ?? []).length ? (p as unknown as { movers: Etf[] }).movers : (stk(p) ?? [])).slice(0, 6).map((x) => <div key={x.symbol}><span style={{ color: C.sub }}>{x.name} </span><b style={{ color: colorOf(x.pct) }}>{fmtPct(x.pct)}</b></div>)}
          {p.links?.EWY && <div><span style={{ color: C.sub }}>한국 ETF EWY </span><b style={{ color: colorOf(p.links.EWY.pct) }}>{fmtPct(p.links.EWY.pct)}</b></div>}
          {p.links?.SOXL && <div><span style={{ color: C.sub }}>SOXL </span><b style={{ color: colorOf(p.links.SOXL.pct) }}>{fmtPct(p.links.SOXL.pct)}</b></div>}
          {p.prev_foreign?.foreign != null && <div><span style={{ color: C.sub }}>전날 국장 외국인 </span><b style={{ color: colorOf(p.prev_foreign.foreign) }}>{fmtEokKR(p.prev_foreign.foreign)}</b></div>}
        </div>
      </div>
      <div style={{ borderTop: `2px solid ${C.line}`, paddingTop: 12, marginTop: 16, fontSize: 26, lineHeight: 1.45 }}>
        {w && <div><b style={{ fontWeight: 600 }}>오늘 국장 체크</b> {w.q}{w.assist ? <span style={{ color: C.sub }}> — {w.assist}</span> : null}</div>}
      </div>
      <div style={{ position: "absolute", left: 96, right: 96, bottom: 24, fontSize: 20, color: C.sub }}>자동 생성 · AI 음성 · 운영자 규칙 · 추천 아님 · 출처 키움 REST · 야후 파이낸스 · BLS · 미 재무부 · Google News</div>
    </AbsoluteFill>
  );
};
