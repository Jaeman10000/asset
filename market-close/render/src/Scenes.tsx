import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { Chart } from "./Chart";
import { C, FONT, PAD, SIZE, FOOTER, colorOf, fmtEok, fmtIdx, fmtPct } from "./tokens";
import type { Props } from "./types";

const ease = Easing.out(Easing.cubic);
const base: React.CSSProperties = { fontFamily: FONT, color: C.text, fontVariantNumeric: "tabular-nums" };

/** 등장: 24px 아래→위 0.45s (SPEC §1-6) */
const Reveal: React.FC<{ at: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at, children, style }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [at, at + 0.45 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return <div style={{ opacity: t, transform: `translateY(${(1 - t) * 24}px)`, ...style }}>{children}</div>;
};
const fade = (f: number, at: number, fps: number) => interpolate(f, [at, at + 0.4 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

export type Cue = { start: number; end: number; text: string };

/** 자막: TTS 문장 경계에 맞춰 현재 문장만. 문장 사이 공백은 직전 문장을 0.6s까지 유지. */
export const Sub: React.FC<{ cues?: Cue[]; fallback?: string }> = ({ cues, fallback }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = f / fps;
  let text = "";
  if (cues && cues.length) {
    const cur = cues.find((c) => t >= c.start && t < c.end + 0.6);
    text = cur ? cur.text : (t < cues[0].start ? "" : cues[cues.length - 1].text);
  } else {
    text = fallback ?? "";
  }
  if (!text) return null;
  return <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 150, fontSize: 42, lineHeight: 1.4, color: "#D9D9D6", wordBreak: "keep-all" }}>{text}</div>;
};

export const Frame: React.FC<{ children: React.ReactNode; sub?: string; cues?: Cue[] }> = ({ children, sub, cues }) => (
  <AbsoluteFill style={{ background: C.bg, ...base }}>
    <div style={{ position: "absolute", left: PAD, right: PAD, top: 120 }}>{children}</div>
    <Sub cues={cues} fallback={sub} />
    <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub, letterSpacing: "0.02em" }}>{FOOTER}</div>
  </AbsoluteFill>
);

const K: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontSize: SIZE.small, color: C.sub, letterSpacing: "0.02em", ...style }}>{children}</div>
);

/** 숫자·퍼센트만 강조색(썸네일처럼 읽히게) */
const NUM_SPLIT = /(\d[\d,.]*\s?(?:조\s?\d[\d,.]*\s?억|조|천억|억|%|원|선|포인트))/g;
const Highlight: React.FC<{ text: string; color?: string }> = ({ text, color = "#FFD84D" }) => {
  const parts = text.split(NUM_SPLIT);
  return <>{parts.map((x, i) => (i % 2 === 1 ? <span key={i} style={{ color, fontWeight: 800 }}>{x}</span> : <React.Fragment key={i}>{x}</React.Fragment>))}</>;
};

type Ap = { format?: string; ep?: number | null; protagonist?: { name: string; amount: number; sold: boolean } | null;
  contrast?: { kind: string; short: string; line?: number | null } | null;
  check?: { verdict?: { kind: string; theme: string; n?: number | null; ok: boolean; amount?: number | null } | null; record?: { n: number; k: number } | null; next_q: string; next_day: string } | null };

const dateChip = (label: string) => { const [md, wd] = label.split(" "); return wd ? `${md}(${wd})` : label; };

/** A+ 첫 화면: 0프레임부터 두 줄(주인공 숫자 / 질문). 1초에 상단 칩, 대비 문장이 나오면 지수 줄. */
const S0Aplus: React.FC<{ p: Props; cues?: Cue[] }> = ({ p, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const ap = p as unknown as Ap;
  const pr = ap.protagonist!;
  const parts = (p as unknown as { hook_parts: string[] }).hook_parts;
  const [nm, amt, word] = parts[0].split(" ");
  const fadeAt = (sec: number) => interpolate(f, [sec * fps, (sec + 0.35) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const ctAt = cues && cues.length > 1 ? cues[1].start : 3.2;
  const ct = ap.contrast;
  const chg = p.kospi.chg_pct;
  const qc = (cues ?? []).find((c) => /\?$/.test(c.text.trim()));
  if (qc && f / fps >= qc.start) {
    const v = fadeAt(qc.start);
    return (
      <AbsoluteFill style={{ background: C.bg, ...base }}>
        <div style={{ position: "absolute", left: PAD, right: PAD, top: 150, display: "flex", alignItems: "center", gap: 18 }}>
          <span style={{ fontSize: SIZE.small + 4, fontWeight: 700, background: "#FFFFFF", color: "#141416", padding: "6px 16px", borderRadius: 999 }}>{p.brand ?? "누가샀나"}{ap.ep ? ` #${String(ap.ep).padStart(3, "0")}` : ""}</span>
          <K>{dateChip(p.date_label)} 국장 마감</K>
        </div>
        <div style={{ position: "absolute", left: PAD, right: PAD, top: "50%", transform: `translateY(-50%) scale(${0.94 + 0.06 * v})`, transformOrigin: "left center" }}>
          <div style={{ fontSize: SIZE.small + 10, color: C.sub }}>{nm} <span style={{ color: colorOf(pr.amount) }}>{amt}</span> {word} · 코스피 {ct && ct.kind !== "pct" ? ct.short : fmtPct(chg)}</div>
          <div style={{ fontSize: 150, fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", color: "#FFD84D", marginTop: 20, wordBreak: "keep-all" }}>{parts[1]}</div>
        </div>
        <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub }}>{FOOTER}</div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: C.bg, ...base }}>
      <div style={{ position: "absolute", left: PAD, right: PAD, top: 150, opacity: fadeAt(1.0), display: "flex", alignItems: "center", gap: 18 }}>
        <span style={{ fontSize: SIZE.small + 4, fontWeight: 700, background: "#FFFFFF", color: "#141416", padding: "6px 16px", borderRadius: 999 }}>{p.brand ?? "누가샀나"}{ap.ep ? ` #${String(ap.ep).padStart(3, "0")}` : ""}</span>
        <K>{dateChip(p.date_label)} 국장 마감</K>
      </div>
      <div style={{ position: "absolute", left: PAD, right: PAD, top: "30%" }}>
        <div style={{ fontSize: 104, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.03em", whiteSpace: "nowrap" }}>
          {nm} <span style={{ color: colorOf(pr.amount) }}>{amt}</span> {word}
        </div>
        <div style={{ fontSize: 118, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.03em", color: "#FFD84D", marginTop: 28, whiteSpace: "nowrap" }}>{parts[1]}</div>
        <div style={{ marginTop: 72, opacity: fadeAt(ctAt), transform: `translateY(${(1 - fadeAt(ctAt)) * 16}px)` }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24 }}>
            <span style={{ fontSize: SIZE.body - 4, color: C.sub }}>코스피</span>
            <span style={{ fontSize: SIZE.mid, fontWeight: 700 }}>{fmtIdx(p.kospi.close)}</span>
            <span style={{ fontSize: SIZE.body, fontWeight: 700, color: colorOf(chg) }}>{fmtPct(chg)}</span>
          </div>
          {ct && ct.kind !== "pct" ? <div style={{ marginTop: 14, fontSize: SIZE.small + 10, color: "#E6E6E3" }}>{ct.short}{ct.kind === "held" && p.kospi.low != null ? <span style={{ color: C.sub }}> · 장중 저점 {fmtIdx(p.kospi.low)}</span> : null}</div> : null}
        </div>
      </div>
      <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub, opacity: fadeAt(3.0) }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};

export const S0: React.FC<{ p: Props; sub?: string; cues?: Cue[] }> = ({ p, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const isUS = (p as unknown as { edition?: string }).edition === "us";
  if (!isUS && (p as unknown as Ap).format === "aplus" && (p as unknown as Ap).protagonist && (p as unknown as { hook_parts?: string[] }).hook_parts) {
    return <S0Aplus p={p} cues={cues} />;
  }
  const parts = (p as unknown as { hook_parts?: string[] }).hook_parts;
  const chg = p.kospi.chg_pct;
  // 국장편: 첫 프레임부터 '오늘의 사실' 큰 글자 → 질문 → 날짜·브랜드 (문장 큐에 맞춰 순서대로 등장)
  if (!isUS && parts && parts.length >= 2) {
    const at = (k: number, fb: number) => (cues && cues.length > k ? cues[k].start : fb);
    const rise = (start: number, dy = 24) => {
      const v = interpolate(f, [start * fps, (start + 0.45) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
      return { opacity: v, transform: `translateY(${(1 - v) * dy}px)` } as React.CSSProperties;
    };
    const evImg = (p as unknown as { event?: { image?: { file: string; credit: string } | null } | null }).event?.image;
    const kb = interpolate(f, [0, 12 * fps], [1.04, 1.14], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <AbsoluteFill style={{ background: C.bg, ...base, justifyContent: "center", alignItems: "flex-start", padding: `0 ${PAD}px` }}>
        {evImg ? (
          <>
            <Img src={staticFile(evImg.file)} style={{ position: "absolute", left: 0, top: 0, width: "100%", height: "100%", objectFit: "cover", transform: `scale(${kb})`, filter: "brightness(0.42) saturate(0.9)" }} />
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(20,20,22,0.55) 0%, rgba(20,20,22,0.35) 45%, rgba(20,20,22,0.9) 100%)" }} />
            <div style={{ position: "absolute", right: PAD, bottom: 120, fontSize: SIZE.tiny, color: "#CFCFCC", background: "rgba(0,0,0,0.5)", padding: "4px 10px", borderRadius: 8 }}>{evImg.credit}</div>
          </>
        ) : null}
        <div style={{ position: "absolute", left: PAD, right: PAD, top: 150, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <span style={{ fontSize: SIZE.small + 4, fontWeight: 700, background: "#FFFFFF", color: "#141416", padding: "6px 16px", borderRadius: 999 }}>{p.brand ?? "누가샀나"}</span>
            <K>{p.date_label} 국내장 마감</K>
          </div>
          <span style={{ fontSize: SIZE.body - 4, fontWeight: 700, color: colorOf(chg) }}>코스피 {fmtPct(chg)}</span>
        </div>
        <div style={{ position: "relative", zIndex: 1, opacity: 1 - (rise(at(1, 5.5), 0).opacity as number), fontSize: 86, fontWeight: 800, lineHeight: 1.24, letterSpacing: "-0.025em", wordBreak: "keep-all", textShadow: evImg ? "0 4px 24px rgba(0,0,0,0.6)" : undefined }}><Highlight text={parts[0]} /></div>
        <div style={{ position: "absolute", left: PAD, right: PAD, top: "50%", transform: "translateY(-50%)", ...rise(at(1, 5.5), 16), fontSize: 92, fontWeight: 700, color: "#7FB2FF", lineHeight: 1.25, wordBreak: "keep-all" }}>{parts[1]}</div>
        <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 170, ...rise(at(2, 8.0), 12), display: "flex", alignItems: "baseline", gap: 24, flexWrap: "wrap" }}>
          <span style={{ fontSize: 84, fontWeight: 700, letterSpacing: "-0.03em" }}>{p.brand ?? "누가샀나"}</span>
          <span style={{ fontSize: SIZE.small + 4, color: C.sub }}>누가 샀고, 돈이 어디로 갔나</span>
        </div>
        <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub }}>{FOOTER}</div>
      </AbsoluteFill>
    );
  }
  return <S0Legacy p={p} cues={cues} />;
};

const S0Legacy: React.FC<{ p: Props; sub?: string; cues?: Cue[] }> = ({ p, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [0, 0.6 * fps], [0, 1], { extrapolateRight: "clamp", easing: ease });
  const isUS = (p as unknown as { edition?: string }).edition === "us";
  // 두 번째 문장(훅)이 시작되면 브랜드 화면 → 훅 화면으로 전환
  const hookAt = cues && cues.length > 1 ? cues[1].start : 4.0;
  const hookT = interpolate(f, [hookAt * fps, (hookAt + 0.45) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const ul = (p as unknown as { us_link?: { name: string; pct: number; when?: string } | null }).us_link;
  const chg = p.kospi.chg_pct;
  const inv = p.investors;
  const buyers = inv?.state === "ready" ? inv.bars.filter((b) => b.name !== "기타법인" && (b.v ?? 0) > 0).sort((a, b) => (b.v ?? 0) - (a.v ?? 0)).map((b) => b.name) : [];
  const side = buyers.length ? buyers.slice(0, 2).join(" · ") : (inv?.bars.find((b) => b.name === "기타법인")?.v ?? 0) > 0 ? "기타법인" : "";
  return (
    <AbsoluteFill style={{ background: C.bg, ...base, justifyContent: "center", alignItems: "flex-start", padding: `0 ${PAD}px` }}>
      {hookT < 1 && (
        <div style={{ opacity: t * (1 - hookT), transform: `translateY(${(1 - t) * 24}px)` }}>
          <div style={{ fontSize: 200, fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 1 }}>{p.brand ?? "밤낮장"}</div>
          <div style={{ fontSize: SIZE.body - 8, color: C.sub, marginTop: 36, lineHeight: 1.4 }}>{p.tagline ?? ""}</div>
          <div style={{ fontSize: SIZE.small + 6, color: C.text, marginTop: 64 }}>{p.date_label} {isUS ? "미국장 마감" : "국내장 마감"}</div>
        </div>
      )}
      {hookT > 0 && !isUS && (
        <div style={{ position: "absolute", left: PAD, right: PAD, top: "50%", transform: `translateY(calc(-50% + ${(1 - hookT) * 24}px))`, opacity: hookT }}>
          <K>{p.date_label} 국내장 마감</K>
          {ul && (
            <div style={{ fontSize: SIZE.body - 4, color: C.sub, marginTop: 28 }}>
              {ul.when ?? "간밤"} {ul.name} <b style={{ color: colorOf(ul.pct) }}>{fmtPct(ul.pct)}</b>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "baseline", gap: 28, marginTop: 20 }}>
            <span style={{ fontSize: SIZE.body }}>코스피</span>
            <span style={{ fontSize: 150, fontWeight: 600, lineHeight: 1, letterSpacing: "-0.02em", color: colorOf(chg) }}>{fmtPct(chg)}</span>
          </div>
          <div style={{ fontSize: SIZE.small + 8, color: C.sub, marginTop: 16 }}>{fmtIdx(p.kospi.close)}</div>
          {side && (
            <div style={{ marginTop: 56, paddingTop: 28, borderTop: `2px solid ${C.line}` }}>
              <K>산 쪽</K>
              <div style={{ fontSize: SIZE.mid - 8, fontWeight: 600, marginTop: 8 }}>{side}</div>
            </div>
          )}
        </div>
      )}
      <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};

export const S6: React.FC<{ p: Props; sub?: string }> = ({ p }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [0, 0.5 * fps], [0, 1], { extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ background: C.bg, ...base, justifyContent: "center", alignItems: "flex-start", padding: `0 ${PAD}px` }}>
      <div style={{ opacity: t }}>
        <div style={{ fontSize: 120, fontWeight: 600, letterSpacing: "-0.02em" }}>{p.brand ?? "밤낮장"}</div>
        <div style={{ fontSize: SIZE.small + 4, color: C.sub, marginTop: 28, lineHeight: 1.5 }}>공개 데이터로 자동 생성 · AI 음성 · 운영자 규칙<br />종목·매매 추천이 아닙니다</div>
      </div>
    </AbsoluteFill>
  );
};

export const S1: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const cnt = interpolate(f, [0, 0.8 * fps], [0, 1], { extrapolateRight: "clamp", easing: ease });
  const close = (p.kospi.close ?? 0) * cnt;
  const night = 0;
  const day = interpolate(f, [1.0 * fps, 7.0 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const labels = [0, fade(f, 4.0 * fps, fps), 0, fade(f, 5.5 * fps, fps), fade(f, 7.2 * fps, fps)];
  const chg = p.kospi.chg_pct ?? 0;
  const desc = chg >= 0.5 ? "상승" : chg >= 0 ? "강보합" : chg > -0.5 ? "약보합" : "하락";
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>{p.date_label} 국내장 · 코스피 · 전일 종가 대비</K></Reveal>
      <Reveal at={3} style={{ marginTop: 40 }}>
        <div style={{ fontSize: 176, fontWeight: 600, lineHeight: 1, letterSpacing: "-0.02em" }}>{fmtIdx(close)}</div>
      </Reveal>
      <Reveal at={6} style={{ marginTop: 24, fontSize: SIZE.small + 8, fontWeight: 600, color: colorOf(chg) }}>
        코스피 {fmtPct(chg)} {desc} · 고 {fmtIdx(p.kospi.high)} · 저 {fmtIdx(p.kospi.low)}
      </Reveal>
      {(p as unknown as { us_link?: { name: string; pct: number } }).us_link && (
        <Reveal at={9} style={{ marginTop: 14, fontSize: SIZE.small + 2, color: C.sub }}>
          {(p as unknown as { us_link: { when?: string } }).us_link.when ?? "간밤"} {(p as unknown as { us_link: { name: string; pct: number } }).us_link.name} <b style={{ color: colorOf((p as unknown as { us_link: { pct: number } }).us_link.pct) }}>{fmtPct((p as unknown as { us_link: { pct: number } }).us_link.pct)}</b>
          {" · "}코스닥 <b style={{ color: colorOf(p.kosdaq.chg_pct) }}>{fmtPct(p.kosdaq.chg_pct)}</b>
        </Reveal>
      )}
      <div style={{ marginTop: 80 }}><Chart p={p} night={night} day={day} labels={labels} mode="kr" /></div>
    </Frame>
  );
};

export const S2: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const inv = p.investors;
  const list2 = cues ?? [];
  const ci = list2.filter((c) => f / fps >= c.start).length - 1;
  const cur2 = ci >= 0 ? list2[ci] : undefined;
  const mk = (p as unknown as { s2_marks?: { answer?: string | null; counter?: string | null; bars?: string | null; snap?: number | null } | null }).s2_marks;
  const apx = p as unknown as Ap;
  const center = (children: React.ReactNode) => (
    <AbsoluteFill style={{ background: C.bg, ...base }}>
      <div style={{ position: "absolute", left: PAD, right: PAD, top: "50%", transform: "translateY(-50%)" }}>{children}</div>
      <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub, letterSpacing: "0.02em" }}>{FOOTER}</div>
    </AbsoluteFill>
  );
  if (apx.format === "aplus" && mk && mk.answer && list2.length && cur2 && !/\?$/.test(cur2.text.trim())) {
    const idxOf = (pred: (t: string) => boolean) => list2.findIndex((c) => pred(c.text.trim()));
    const ansName = mk.answer;
    const rIdx = idxOf((t) => t === `${ansName}입니다.` || t.startsWith(`가장 많이`) && t.includes(`쪽은 ${ansName}`));
    const cIdx = mk.counter ? idxOf((t) => t.startsWith(mk.counter as string)) : -1;
    const bIdx = mk.bars ? idxOf((t) => t.startsWith(mk.bars as string)) : -1;
    const pop = (sec: number, dy = 20) => { const x = interpolate(f, [sec * fps, (sec + 0.4) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }); return { opacity: x, transform: `translateY(${(1 - x) * dy}px)` } as React.CSSProperties; };
    const ansBar = inv.bars.find((b) => b.name === ansName);
    const endReveal = [cIdx, bIdx].filter((x) => x > rIdx).sort((a, b) => a - b)[0] ?? list2.length;
    if (rIdx >= 0 && ci < rIdx) {
      return center(<div style={{ ...pop(cur2.start), fontSize: 88, fontWeight: 700, lineHeight: 1.3, wordBreak: "keep-all" }}>{cur2.text}</div>);
    }
    if (rIdx >= 0 && ci >= rIdx && ci < endReveal && ansBar) {
      const r0 = list2[rIdx].start;
      return center(
        <div>
          <K>가장 많이 {(ansBar.v ?? 0) > 0 ? "산" : "판"} 쪽 · {p.date_label.slice(0, -2)}</K>
          <div style={{ ...pop(r0, 28), fontSize: 168, fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.03em", marginTop: 12 }}>{ansName}</div>
          <div style={{ ...pop(r0 + 0.25), fontSize: SIZE.mid, fontWeight: 700, color: colorOf(ansBar.v), marginTop: 28 }}>{fmtEok(ansBar.v, true)}</div>
          {ansName === "기타법인" ? <div style={{ ...pop(r0 + 0.6), fontSize: SIZE.small + 4, color: C.sub, marginTop: 28, lineHeight: 1.45 }}>일반 회사들의 거래를 묶은 숫자 · 어느 회사인지는 알 수 없음</div> : null}
        </div>
      );
    }
    const pr = apx.protagonist;
    if (cIdx >= 0 && ci >= cIdx && (bIdx < 0 || ci < bIdx) && pr && mk.snap != null) {
      const c0 = list2[cIdx];
      const k = interpolate(f, [(c0.start + 0.3) * fps, (c0.end - 0.2) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
      const val = Math.round((mk.snap + (pr.amount - mk.snap) * k) / 10) * 10;
      return center(
        <div>
          <K>{pr.name} {pr.sold ? "순매도" : "순매수"} · 코스피</K>
          <div style={{ fontSize: 150, fontWeight: 800, color: colorOf(pr.amount), letterSpacing: "-0.03em", marginTop: 12, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{fmtEok(k >= 1 ? pr.amount : val, true)}</div>
          <div style={{ display: "flex", gap: 36, marginTop: 36, fontSize: SIZE.small + 10 }}>
            <span style={{ color: C.sub }}>오후 2시 <b style={{ color: "#E6E6E3" }}>{fmtEok(mk.snap, true)}</b></span>
            <span style={{ color: C.sub, opacity: k >= 1 ? 1 : 0.25 }}>→ 마감 <b style={{ color: colorOf(pr.amount) }}>{fmtEok(pr.amount, true)}</b></span>
          </div>
        </div>
      );
    }
  }
  if (cur2 && /\?$/.test(cur2.text.trim())) {
    const v = interpolate(f, [cur2.start * fps, (cur2.start + 0.4) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    return (
      <AbsoluteFill style={{ background: C.bg, ...base }}>
        <div style={{ position: "absolute", left: PAD, right: PAD, top: "50%", transform: `translateY(-50%) translateY(${(1 - v) * 20}px)`, opacity: v, fontSize: 96, fontWeight: 700, color: "#7FB2FF", lineHeight: 1.25, wordBreak: "keep-all" }}>{cur2.text}</div>
        <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub, letterSpacing: "0.02em" }}>{FOOTER}</div>
      </AbsoluteFill>
    );
  }
  const maxAbs = Math.max(1, ...inv.bars.map((b) => Math.abs(b.v ?? 0)));
  return (
    <Frame sub={sub} cues={cues}>
      <Reveal at={0}><K>코스피 투자자별 순매수 · {p.date_label.slice(0, -2)} · {inv.src ?? "확정치 대기"}</K></Reveal>
      <Reveal at={3} style={{ marginTop: 32 }}>
        <div style={{ fontSize: SIZE.mid - 6, fontWeight: 600, lineHeight: 1.22, letterSpacing: "-0.01em", wordBreak: "keep-all" }} dangerouslySetInnerHTML={{ __html: inv.title }} />
      </Reveal>
      {inv.state !== "ready" ? (
        <Reveal at={12} style={{ marginTop: 80, fontSize: SIZE.body, color: C.sub }}>수급 집계 반영 후 갱신</Reveal>
      ) : (
        <div style={{ marginTop: 80 }}>
          {inv.bars.map((b, i) => {
            const at = 12 + i * 5;
            const w = interpolate(f, [at + 10, at + 10 + 0.9 * fps], [0, (Math.abs(b.v ?? 0) / maxAbs) * 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
            const st = ((p as unknown as { inv_streak?: Record<string, { streak: number; turned_after: number }> }).inv_streak ?? {})[b.name === "외국인" ? "foreign" : b.name === "기관" ? "inst" : ""];
            const stTxt = st ? (st.turned_after >= 3 ? `${st.turned_after}일 만에 전환` : Math.abs(st.streak) >= 2 ? `${Math.abs(st.streak)}일째` : "") : "";
            const it = (p as unknown as { intraday?: { at: string; snap: Record<string, number | null> } | null }).intraday;
            const k14 = it?.snap?.[b.name === "개인" ? "indiv" : b.name === "외국인" ? "foreign" : b.name === "기관" ? "inst" : "others"];
            const itTxt = it && k14 != null ? `${it.at} ${fmtEok(k14, true)} → 마감` : "";
            return (
              <Reveal key={b.name} at={at} style={{ marginBottom: 44 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16, fontSize: SIZE.small + 10, marginBottom: 12 }}>
                  <span style={{ minWidth: 0 }}>{b.name}{stTxt ? <span style={{ color: C.sub, fontSize: SIZE.small }}> · {stTxt}</span> : null}{itTxt ? <div style={{ color: C.sub, fontSize: SIZE.small - 4, marginTop: 2 }}>{itTxt}</div> : null}</span>
                  <span style={{ color: colorOf(b.v), fontWeight: 600, whiteSpace: "nowrap" }}>{fmtEok(b.v)} {(b.v ?? 0) >= 0 ? "순매수" : "순매도"}</span>
                </div>
                <div style={{ height: 24, width: `${w}%`, background: colorOf(b.v) }} />
              </Reveal>
            );
          })}
          {p.kospi.program_mn != null && (
            <Reveal at={34}><K>프로그램 매매 {fmtEok(Math.round(p.kospi.program_mn / 100), true)} · 코스피</K></Reveal>
          )}
        </div>
      )}
    </Frame>
  );
};

const stateLabel = (s: string, streak: number) => (s.startsWith("쌓임") ? `쌓임 · ${streak}일 연속${s.includes("확산") ? " · 확산" : ""}` : s);

type Story = { verdict?: { kind: string; theme: string; n?: number | null; ok: boolean; amount?: number | null } | null; lead?: { theme: string; t: number; who: string; names: string[] } | null; summary?: string };
const daysKo = (n?: number | null) => (n === 2 ? "이틀째" : n === 3 ? "사흘째" : n === 4 ? "나흘째" : n === 5 ? "닷새째" : n ? `${n}일째` : "");

/** 돈의 이동: 어제 예고 → 오늘 결과 → 질문 → 테마 공개 → 종목 이름 하나씩 → 표. 현재 읽는 문장(큐)으로 단계를 정한다. */
export const S3: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = f / fps;
  const story = (p as unknown as { s3_story?: Story | null }).s3_story;
  const list = cues ?? [];
  const started = list.filter((c) => t >= c.start);
  const cur = started.length ? started[started.length - 1] : undefined;
  const txt = cur?.text ?? "";
  const names = story?.lead?.names ?? [];
  const isVerdict = !!story?.verdict && /보자고 했죠|끊겼습니다|이어졌습니다|빠졌습니다|미루자고|더 들어왔고|멈췄습니다|돌아섰습니다|아직 빠지는/.test(txt) && !/어디로 갔을까요|어디였을까요/.test(txt);
  const isQuestion = /어디로 갔을까요|어디였을까요/.test(txt);
  const isReveal = !!story?.lead && (txt.replace(/\s/g, "") === `${story.lead.theme}입니다.` || txt.includes(`곳은 ${story.lead.theme}`));
  const isNames = names.length > 0 && names.some((n) => txt.includes(n));
  const resultSaid = /끊겼습니다|이어졌습니다|빠졌습니다|미루자고|더 들어왔고|멈췄습니다|돌아섰습니다|아직 빠지는/.test(txt);
  const pop = (start: number, dy = 20) => {
    const v = interpolate(f, [start * fps, (start + 0.4) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    return { opacity: v, transform: `translateY(${(1 - v) * dy}px)` } as React.CSSProperties;
  };
  const Stage: React.FC<{ children: React.ReactNode; center?: boolean; hideSub?: boolean }> = ({ children, center, hideSub }) => (
    <AbsoluteFill style={{ background: C.bg, ...base }}>
      <div style={{ position: "absolute", left: PAD, right: PAD, top: center ? "50%" : 120, transform: center ? "translateY(-50%)" : undefined }}>{children}</div>
      {!hideSub && <Sub cues={cues} fallback={sub} />}
      <div style={{ position: "absolute", left: PAD, right: PAD, bottom: 60, fontSize: SIZE.tiny, color: C.sub, letterSpacing: "0.02em" }}>{FOOTER}</div>
    </AbsoluteFill>
  );
  if (isVerdict && story?.verdict) {
    const v = story.verdict;
    const ask = v.kind === "theme_continue" ? `${v.theme} ${daysKo(v.n)} 이어질까?` : v.kind === "theme_sell_stop" ? `${v.theme} 순매도 멈출까?` : v.kind === "inv_continue" ? `${v.theme} 이어질까?` : v.kind === "kosdaq_break" ? "코스닥 연속 흐름 끊길까?" : v.theme;
    const res = v.ok ? "이어졌습니다" : "끊겼습니다";
    const amt = v.amount != null ? fmtEok(v.amount, true) : "";
    return (
      <Stage center>
        <K>어제 예고</K>
        <div style={{ ...pop(cur?.start ?? 0), fontSize: 84, fontWeight: 600, lineHeight: 1.25, marginTop: 16, wordBreak: "keep-all" }}>{ask}</div>
        {resultSaid && (
          <div style={{ marginTop: 72 }}>
            <K>오늘 결과</K>
            <div style={{ ...pop(cur?.start ?? 0), display: "flex", alignItems: "baseline", gap: 28, marginTop: 12 }}>
              <span style={{ fontSize: 120, fontWeight: 700, color: v.ok ? C.up : C.down, lineHeight: 1 }}>{res}</span>
              {amt && <span style={{ fontSize: SIZE.body, color: C.sub }}>{amt}</span>}
            </div>
          </div>
        )}
      </Stage>
    );
  }
  if (isQuestion) {
    return (
      <Stage center hideSub>
        <div style={{ ...pop(cur?.start ?? 0), fontSize: 96, fontWeight: 700, color: "#7FB2FF", lineHeight: 1.25, wordBreak: "keep-all" }}>{txt}</div>
      </Stage>
    );
  }
  if (isReveal && story?.lead) {
    const l = story.lead;
    return (
      <Stage center hideSub>
        <K>{l.t < 0 ? "오늘 돈이 가장 많이 빠진 곳" : "오늘 돈이 가장 많이 들어간 곳"}</K>
        <div style={{ ...pop(cur?.start ?? 0, 28), fontSize: 168, fontWeight: 700, lineHeight: 1.05, letterSpacing: "-0.03em", marginTop: 12 }}>{l.theme}</div>
        <div style={{ ...pop((cur?.start ?? 0) + 0.25), display: "flex", alignItems: "baseline", gap: 24, marginTop: 32 }}>
          <span style={{ fontSize: SIZE.mid, fontWeight: 600, color: colorOf(l.t) }}>{fmtEok(l.t, true)}</span>
          {l.who && <span style={{ fontSize: SIZE.small + 8, color: C.sub }}>{l.who}</span>}
        </div>
      </Stage>
    );
  }
  if (isNames && cur && story?.lead) {
    const span = Math.max(0.6, cur.end - cur.start);
    const k = Math.min(names.length, Math.floor((t - cur.start) / (span / names.length)) + 1);
    return (
      <Stage center>
        <K>{story.lead.theme} · 돈이 몰린 곳</K>
        <div style={{ marginTop: 24 }}>
          {names.slice(0, Math.max(1, k)).map((n, idx) => (
            <div key={n} style={{ ...pop(cur.start + idx * (span / names.length), 18), fontSize: 92, fontWeight: 700, lineHeight: 1.3, letterSpacing: "-0.02em" }}>{n}</div>
          ))}
        </div>
      </Stage>
    );
  }
  return (
    <Stage>
      <K>테마 수급 · 어제 → 오늘 · 외국인+기관 · 억원</K>
      <div style={{ fontSize: SIZE.mid, fontWeight: 600, lineHeight: 1.22, marginTop: 32 }}>{p.s3_title}</div>
      <div style={{ marginTop: 64 }}>
        {p.moves.map((m) => (
          <div key={m.theme} style={{ marginBottom: 56 }}>
            <div style={{ display: "grid", gridTemplateColumns: "150px 1fr 230px", alignItems: "center", columnGap: 20, fontSize: 42, whiteSpace: "nowrap" }}>
              <div>{m.theme}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 16, fontWeight: 600 }}>
                <span style={{ color: colorOf(m.y) }}>{fmtEok(m.y, true)}</span>
                <span style={{ flex: 1, minWidth: 24, height: 2, background: C.line }} />
                <span style={{ color: colorOf(m.t) }}>{fmtEok(m.t, true)}</span>
              </div>
              <div style={{ fontSize: SIZE.tiny, color: C.sub, textAlign: "right", whiteSpace: "normal", lineHeight: 1.2 }}>{stateLabel(m.state, m.streak)}</div>
            </div>
            <div style={{ fontSize: SIZE.tiny, color: C.sub, marginTop: 10, paddingLeft: 170 }}>
              {m.state.includes("확산") && m.spread_names.length ? `${m.spread_names.slice(0, 3).join("·")}로 확산 · ` : ""}
              기관 {fmtEok(m.inst, true)} / 외국인 {fmtEok(m.foreign, true)} · {fmtPct(m.ret)}
            </div>
          </div>
        ))}
      </div>
    </Stage>
  );
};

const Num: React.FC<{ k: string; v: string; c?: string; note: string }> = ({ k, v, c, note }) => (
  <div>
    <K>{k}</K>
    <div style={{ fontSize: 92, fontWeight: 600, color: c ?? C.text, lineHeight: 1.1, marginTop: 6 }}>{v}</div>
    <K style={{ marginTop: 6 }}>{note}</K>
  </div>
);

/** 켄번즈: 등장 페이드 + 12초 동안 천천히 확대·이동. 출처 표기는 오른쪽 아래 고정. */
const KenBurns: React.FC<{ src: string; at: number; height: number; credit?: string }> = ({ src, at, height, credit }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = interpolate(f, [at, at + 0.5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const z = interpolate(f, [at, at + 12 * fps], [1.03, 1.14], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const px = interpolate(f, [at, at + 12 * fps], [1.5, -2.5], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ borderRadius: 18, overflow: "hidden", border: `1px solid ${C.line}`, position: "relative", height, opacity: t, transform: `translateY(${(1 - t) * 22}px)` }}>
      <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block", transform: `scale(${z}) translateX(${px}%)`, transformOrigin: "center" }} />
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,0,0,0) 62%, rgba(0,0,0,0.5) 100%)" }} />
      {credit ? <div style={{ position: "absolute", right: 14, bottom: 10, fontSize: SIZE.tiny, color: "#E6E6E3", background: "rgba(0,0,0,0.55)", padding: "4px 10px", borderRadius: 8 }}>{credit}</div> : null}
    </div>
  );
};

export const S4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const fxSaid = (p as unknown as { fx_said?: boolean }).fx_said;
  const f4 = useCurrentFrame(); const { fps: fps4 } = useVideoConfig();
  const t4 = f4 / fps4;
  const said = ((cues ?? []).filter((c) => t4 >= c.start).slice(-1)[0]?.text) ?? "";
  const ev = (p as unknown as { event?: { label: string; group?: string; image?: { file: string; credit: string } | null; stocks: { name: string; pct: number; foreign: number; inst: number }[] } | null }).event;
  return (
    <Frame sub={sub} cues={cues}>
      {ev && ev.stocks && ev.stocks.length ? (
        <Reveal at={0} style={{ marginBottom: 48 }}>
          <K>오늘의 이슈 · {ev.label}</K>
          {ev.image ? (
            <div style={{ marginTop: 16 }}>
              <KenBurns src={ev.image.file} at={6} height={420} credit={ev.image.credit} />
            </div>
          ) : null}
          {(p as unknown as Ap).format === "aplus" ? (() => {
            const avg = ev.stocks.reduce((a, x) => a + x.pct, 0) / ev.stocks.length;
            const up = ev.stocks.filter((x) => x.pct > 0).length, dn = ev.stocks.filter((x) => x.pct < 0).length, fl = ev.stocks.length - up - dn;
            return (
              <Reveal at={10} style={{ marginTop: 28 }}>
                <K>{ev.group ?? "관련주"} {ev.stocks.length}종목 평균</K>
                <div style={{ display: "flex", alignItems: "baseline", gap: 24, marginTop: 6 }}>
                  <span style={{ fontSize: 120, fontWeight: 800, color: colorOf(avg), letterSpacing: "-0.03em", whiteSpace: "nowrap" }}>{fmtPct(Math.round(avg * 100) / 100)}</span>
                  <span style={{ fontSize: SIZE.small + 8, color: C.sub, whiteSpace: "nowrap" }}>상승 {up} · 보합 {fl} · 하락 {dn}</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "10px 22px", marginTop: 18, fontSize: SIZE.small + 2 }}>
                  {ev.stocks.map((x) => <span key={x.name} style={{ whiteSpace: "nowrap" }}>{x.name} <b style={{ color: colorOf(x.pct) }}>{fmtPct(x.pct)}</b></span>)}
                </div>
              </Reveal>
            );
          })() : null}
          <div style={{ display: (p as unknown as Ap).format === "aplus" ? "none" : "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 32px", marginTop: 16 }}>
            {ev.stocks.slice(0, 6).map((s0, idx) => {
              const hot = said.includes(s0.name);
              return (
                <Reveal key={s0.name} at={14 + idx * 4}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: `1px solid ${C.line}`, padding: "2px 10px 8px", marginLeft: -10, marginRight: -10, borderRadius: 8, background: hot ? "rgba(255,255,255,0.09)" : "transparent" }}>
                    <span style={{ fontSize: SIZE.small + 6, whiteSpace: "nowrap", fontWeight: hot ? 700 : 400 }}>{s0.name}</span>
                    <span style={{ fontSize: SIZE.small + 8, fontWeight: 600, color: colorOf(s0.pct) }}>{fmtPct(s0.pct)}</span>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </Reveal>
      ) : null}
      {(p as unknown as Ap).format !== "aplus" && <Reveal at={ev && ev.stocks && ev.stocks.length ? 6 : 0}><K>종목 수급 · 거래대금 상위 중 외국인·기관이 들어간 곳 · {p.date_label.slice(0, -2)}</K></Reveal>}
      {((p as unknown as Ap).format === "aplus" ? [] : p.stocks.slice(0, 2)).map((s0, i) => (
        <Reveal key={s0.name} at={4 + i * 8} style={{ marginTop: i === 0 ? 40 : 56 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontSize: SIZE.body + 8, fontWeight: 600 }}>{s0.name}</div>
            <div style={{ fontSize: SIZE.body, fontWeight: 600, color: colorOf(s0.pct) }}>{fmtPct(s0.pct)}</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24, marginTop: 18 }}>
            {[["외국인", s0.foreign], ["기관", s0.inst], ["개인", s0.indiv]].map(([k, v]) => (
              <div key={k as string}>
                <K>{k as string}</K>
                <div style={{ fontSize: SIZE.small + 12, fontWeight: 600, color: colorOf(v as number), marginTop: 4 }}>{fmtEok(v as number, true)}</div>
              </div>
            ))}
          </div>
        </Reveal>
      ))}
      {fxSaid && p.fx && (
        <Reveal at={24} style={{ marginTop: 64 }}>
          <K>환율 · 하나은행 매매기준율</K>
          <div style={{ fontSize: SIZE.body, fontWeight: 600, color: colorOf(p.fx.chg), marginTop: 6 }}>{p.fx.close.toLocaleString("ko-KR", { minimumFractionDigits: 1 })} <span style={{ fontSize: SIZE.small + 6 }}>{p.fx.chg != null ? `${p.fx.chg > 0 ? "+" : ""}${p.fx.chg}원` : ""}</span></div>
        </Reveal>
      )}
    </Frame>
  );
};

const schedText = (s: { d: string; t: string }) => {
  const dd = s.d;
  if (dd.length >= 16) return [`${+dd.slice(5, 7)}/${+dd.slice(8, 10)} ${dd.slice(11, 16)}`, s.t];
  if (dd.includes("~")) { const [a, b] = dd.split("~"); return [`${+a.slice(5, 7)}/${+a.slice(8, 10)}–${+b.slice(-2)}`, s.t]; }
  return [`${+dd.slice(5, 7)}/${+dd.slice(8, 10)}`, s.t];
};

const S5Aplus: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const ck = (p as unknown as Ap).check!;
  const v = ck.verdict;
  const find = (re: RegExp, fb: number) => { const c = (cues ?? []).find((x) => re.test(x.text)); return c ? c.start : fb; };
  const show = (sec: number) => { const x = interpolate(f, [sec * fps, (sec + 0.4) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }); return { opacity: x, transform: `translateY(${(1 - x) * 18}px)` } as React.CSSProperties; };
  const ask = v ? (v.kind === "theme_continue" ? `${v.theme} 순매수 ${daysKo(v.n)}?` : v.kind === "inv_continue" ? `${v.theme} 이어질까?` : v.kind === "theme_sell_stop" ? `${v.theme} 순매도 멈출까?` : v.theme) : "";
  const rec = ck.record;
  const resAt = find(/끊겼습니다|이어졌습니다|멈췄습니다/, 2);
  const recAt = find(/^지금까지/, 4);
  const nextAt = find(/하나만 봅니다|볼 것은/, 6);
  return (
    <Frame sub={sub} cues={cues}>
      {v ? (
        <div style={show(0)}>
          <K>어제 보기로 한 것</K>
          <div style={{ fontSize: 80, fontWeight: 700, lineHeight: 1.25, marginTop: 14, wordBreak: "keep-all" }}>{ask}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 26, marginTop: 20 }}>
            <span style={{ ...show(resAt), fontSize: 110, fontWeight: 800, color: v.ok ? C.up : C.down, letterSpacing: "-0.02em" }}>{v.ok ? "이어짐" : "끊김"}</span>
            {v.amount != null ? <span style={{ ...show(resAt), fontSize: SIZE.body, color: C.sub }}>{fmtEok(v.amount, true)}</span> : null}
          </div>
        </div>
      ) : null}
      {rec && rec.n ? (
        <div style={{ ...show(recAt), marginTop: 44, fontSize: SIZE.small + 10, color: "#E6E6E3" }}>
          기록 · 이어짐 <b style={{ color: C.up }}>{rec.k}</b> / 끊김 <b style={{ color: C.down }}>{rec.n - rec.k}</b>
        </div>
      ) : null}
      <div style={{ ...show(nextAt), marginTop: 96, paddingTop: 36, borderTop: `2px solid ${C.line}` }}>
        <K>다음 확인 · {ck.next_day}</K>
        <div style={{ fontSize: 76, fontWeight: 700, lineHeight: 1.25, marginTop: 14, wordBreak: "keep-all" }}>{ck.next_q.replace(/가 (\S+째 )?이어지는지$/, (_m, d1) => ` ${d1 ?? ""}이어질까?`).replace(/\s+/g, " ")}</div>
      </div>
    </Frame>
  );
};

export const S5: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = (props) => ((props.p as unknown as Ap).format === "aplus" && (props.p as unknown as Ap).check ? <S5Aplus {...props} /> : <S5Legacy {...props} />);

const S5Legacy: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, sub, cues }) => (
  <Frame sub={sub} cues={cues}>
    <Reveal at={0}><K>{(p as unknown as { next_label?: string }).next_label ?? "내일"} 우리가 체크해야 할 것 · 조건 → 관찰</K></Reveal>
    {(p.watch as { q: string; how: string; assist?: string }[]).map((w, i) => (
      <Reveal key={i} at={4 + i * 10} style={{ marginTop: i === 0 ? 48 : 56 }}>
        <K>{i === 0 ? "①" : "②"}</K>
        <div style={{ fontSize: i === 0 ? SIZE.body : SIZE.body - 12, fontWeight: 600, lineHeight: 1.3, marginTop: 8, wordBreak: "keep-all" }}>{w.q}</div>
        {i === 0 && w.assist ? <div style={{ fontSize: SIZE.small + 4, color: "#D9D9D6", lineHeight: 1.45, marginTop: 12, wordBreak: "keep-all" }}>{w.assist}</div> : null}
        <K style={{ marginTop: 10 }}>→ {w.how}</K>
      </Reveal>
    ))}
    <Reveal at={28} style={{ marginTop: 72 }}>
      <K>일정</K>
      <div style={{ fontSize: SIZE.small + 8, lineHeight: 1.7, marginTop: 8 }}>
        {p.schedule.map((s, i) => { const [a, b] = schedText(s); return <div key={i}><span style={{ color: C.sub, marginRight: 20 }}>{a}</span>{b}</div>; })}
      </div>
    </Reveal>
  </Frame>
);
