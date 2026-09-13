import React from "react";
import { interpolate } from "remotion";
import { C, FONT, fmtIdx, hhmm } from "./tokens";
import type { Props, Pt } from "./types";

/** 「하루 한 줄」 — 밤(QQQ) 22:30→05:00 | 낮(코스피) 09:00→15:30, 전일 종가 대비 %. SPEC §1-5.
 *  progress: 0..1 밤 선, 1..2 낮 선. labelsAt: 라벨 그룹별 표시 여부(0..1) */
const W = 888, H = 640, TOP = 40, BOT = 600, NX0 = 0, NX1 = 420, DX0 = 468, DX1 = 888, GAP = (NX1 + DX0) / 2;

const tmin = (t: string) => parseInt(t.slice(0, 2), 10) * 60 + parseInt(t.slice(2), 10);
const nightX = (t: string) => {
  let m = tmin(t); if (m < 12 * 60) m += 24 * 60; // 00:00~05:00 → 다음날
  return NX0 + ((m - 22.5 * 60) / 390) * (NX1 - NX0);
};
const dayX = (t: string) => DX0 + ((tmin(t) - 9 * 60) / 390) * (DX1 - DX0);

export const Chart: React.FC<{ p: Props; night: number; day: number; labels: number[]; scale?: number; mode?: "both" | "kr" | "us" }> = ({ p, night, day, labels, scale = 1, mode = "kr" }) => {
  if (mode !== "both") return <SingleChart p={p} progress={mode === "kr" ? day : night} labels={labels} scale={scale} mode={mode} />;
  const kp = p.kospi.minutes?.points ?? [];
  const np = p.us.qqq_points ?? [];
  const all = [...kp, ...np].map((x) => Math.abs(x.pct));
  const yMax = Math.max(2, Math.ceil(Math.max(0, ...all) * 1.15 * 2) / 2);
  const y = (pct: number) => TOP + ((yMax - pct) / (2 * yMax)) * (BOT - TOP);
  const zero = y(0);
  const dayPts = kp.map((q) => `${dayX(q.t).toFixed(1)},${y(q.pct).toFixed(1)}`).join(" ");
  const nightPts = np.map((q) => `${nightX(q.t).toFixed(1)},${y(q.pct).toFixed(1)}`).join(" ");
  const km = p.kospi.minutes ?? {};
  const nightClipW = interpolate(night, [0, 1], [0, NX1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  const dayClipW = interpolate(day, [0, 1], [0, DX1 - DX0], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  const last = kp[kp.length - 1];
  const lastN = np[np.length - 1];
  const band = p.news.find((n) => n.band);
  const fs = 30; // 보조 36 → 라벨은 30/34
  const S = { fontFamily: FONT, fontVariantNumeric: "tabular-nums" as const };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W * scale} height={H * scale} style={{ display: "block", overflow: "visible" }}>
      <text x={0} y={TOP - 8} fontSize={fs} fill={C.sub} style={S}>+{yMax}%</text>
      <text x={0} y={BOT - 10} fontSize={fs} fill={C.sub} style={S}>−{yMax}%</text>
      <line x1={0} y1={zero} x2={W} y2={zero} stroke={C.line} strokeWidth={2} />
      <line x1={GAP} y1={TOP} x2={GAP} y2={BOT} stroke={C.line} strokeWidth={2} strokeDasharray="6 8" />
      <text x={NX0} y={H + 4} fontSize={fs} fill={C.sub} style={S}>22:30 미국</text>
      <text x={GAP} y={H + 4} fontSize={fs} fill={C.sub} textAnchor="middle" style={S}>05:00 · 09:00</text>
      <text x={DX1} y={H + 4} fontSize={fs} fill={C.sub} textAnchor="end" style={S}>한국 15:30</text>
      {band && (
        <g opacity={labels[2] ?? 0}>
          <rect x={dayX(band.band![0])} y={TOP} width={dayX(band.band![1]) - dayX(band.band![0])} height={BOT - TOP} fill="none" stroke={C.sub} strokeWidth={2} strokeDasharray="6 6" opacity={0.6} />
          <text x={dayX(band.band![0]) - 10} y={y(-yMax * 0.55)} fontSize={fs} fill={C.sub} textAnchor="end" style={S}>{band.text}</text>
          <text x={dayX(band.band![0]) - 10} y={y(-yMax * 0.55) + 34} fontSize={fs} fill={C.sub} textAnchor="end" style={S}>{band.t ?? "시각 미확인"}</text>
        </g>
      )}
      <clipPath id="nclip"><rect x={NX0} y={0} width={nightClipW} height={H} /></clipPath>
      <clipPath id="dclip"><rect x={DX0} y={0} width={dayClipW} height={H} /></clipPath>
      {np.length > 0 && <polyline points={nightPts} fill="none" stroke={C.sub} strokeWidth={5} strokeLinejoin="round" strokeLinecap="round" clipPath="url(#nclip)" />}
      {kp.length > 0 && <polyline points={dayPts} fill="none" stroke={C.text} strokeWidth={7} strokeLinejoin="round" strokeLinecap="round" clipPath="url(#dclip)" />}
      {/* 밤 라벨 */}
      {lastN && (
        <g opacity={labels[0] ?? 0}>
          {(p.us.events ?? []).filter((e) => e.kst).slice(0, 1).map((e, i) => {
            const t = e.kst.slice(11, 16).replace(":", "");
            const x = nightX(t);
            return (
              <g key={i}>
                <circle cx={x} cy={y(np.reduce((a, b) => (Math.abs(tmin(b.t) - tmin(t)) < Math.abs(tmin(a.t) - tmin(t)) ? b : a), np[0]).pct)} r={9} fill={C.sub} />
                <text x={x} y={TOP + 60} fontSize={fs} fill={C.sub} textAnchor="middle" style={S}>{e.kst.slice(11, 16)} {e.what.slice(0, 18)}</text>
              </g>
            );
          })}
          <circle cx={nightX(lastN.t)} cy={y(lastN.pct)} r={10} fill={lastN.pct >= 0 ? C.up : C.down} />
          <text x={NX1 - 6} y={y(lastN.pct) + (lastN.pct >= 0 ? 48 : -24)} fontSize={34} fontWeight={600} fill={lastN.pct >= 0 ? C.up : C.down} textAnchor="end" style={S}>
            QQQ 마감 {lastN.pct > 0 ? "+" : ""}{(p.us.qqq_pct ?? lastN.pct).toFixed(2)}
          </text>
        </g>
      )}
      {/* 낮 라벨 */}
      {km.high_t && (
        <g opacity={labels[1] ?? 0}>
          <circle cx={dayX(km.high_t)} cy={y(km.high_pct ?? 0)} r={10} fill={C.up} />
          <text x={dayX(km.high_t) > (DX0 + DX1) / 2 ? dayX(km.high_t) - 16 : dayX(km.high_t) + 16} y={y(km.high_pct ?? 0) - 24} fontSize={34} fill={C.up} textAnchor={dayX(km.high_t) > (DX0 + DX1) / 2 ? "end" : "start"} style={S}>{hhmm(km.high_t)} 고점 {fmtIdx(km.high)}</text>
        </g>
      )}
      {km.low_t && (
        <g opacity={labels[3] ?? 0}>
          {km.drop30 && km.drop30.pct <= -1 && (
            <text x={dayX(km.low_t) - 22} y={y(km.low_pct ?? 0) + 6} fontSize={32} fill={C.down} textAnchor="end" style={S}>
              {hhmm(km.drop30.from)}→{hhmm(km.drop30.to)} {km.drop30.pct.toFixed(2)}%
            </text>
          )}
          <circle cx={dayX(km.low_t)} cy={y(km.low_pct ?? 0)} r={10} fill={C.down} />
          <text x={dayX(km.low_t) - 22} y={y(km.low_pct ?? 0) + ((km.low_pct ?? 0) < -0.55 * yMax && dayX(km.low_t) > DX0 + (DX1 - DX0) * 0.5 ? -20 : 46)} fontSize={34} fill={C.down} textAnchor="end" style={S}>{hhmm(km.low_t)} 저점 {fmtIdx(km.low)}</text>
        </g>
      )}
      {last && (
        <g opacity={labels[4] ?? 0}>
          <circle cx={DX1} cy={y(last.pct)} r={10} fill={last.pct >= 0 ? C.up : C.down} />
          <text x={DX1 - 4} y={BOT - 12} fontSize={36} fontWeight={600} fill={last.pct >= 0 ? C.up : C.down} textAnchor="end" style={S}>마감 {fmtIdx(p.kospi.close)} · {last.pct > 0 ? "+" : ""}{(p.kospi.chg_pct ?? last.pct).toFixed(2)}%</text>
        </g>
      )}
    </svg>
  );
};


/** 한 시장만 전폭으로: kr = 코스피 09:00→15:30, us = QQQ 22:30→05:00(KST). 라벨은 고점·저점·마감만. */
const SingleChart: React.FC<{ p: Props; progress: number; labels: number[]; scale: number; mode: "kr" | "us" }> = ({ p, progress, labels, scale, mode }) => {
  const kr = mode === "kr";
  const pts = kr ? (p.kospi.minutes?.points ?? []) : ((p as unknown as { qqq_points?: Pt[] }).qqq_points ?? p.us?.qqq_points ?? []);
  const X0 = 0, X1 = W;
  const xOf = (t: string) => {
    let m = tmin(t);
    if (!kr && m < 12 * 60) m += 24 * 60;
    const start = kr ? 9 * 60 : 22.5 * 60;
    return X0 + ((m - start) / 390) * (X1 - X0);
  };
  const all = pts.map((q) => Math.abs(q.pct));
  const yMax = Math.max(1, Math.ceil(Math.max(0, ...all) * 1.15 * 2) / 2);
  const y = (pct: number) => TOP + ((yMax - pct) / (2 * yMax)) * (BOT - TOP);
  const zero = y(0);
  const line = pts.map((q) => `${xOf(q.t).toFixed(1)},${y(q.pct).toFixed(1)}`).join(" ");
  const clipW = interpolate(progress, [0, 1], [0, X1 - X0], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  const S = { fontFamily: FONT, fontVariantNumeric: "tabular-nums" as const };
  const fs = 30;
  let hi: Pt | undefined, lo: Pt | undefined;
  for (const q of pts) { if (!hi || q.pct > hi.pct) hi = q; if (!lo || q.pct < lo.pct) lo = q; }
  const last = pts[pts.length - 1];
  const closeVal = kr ? fmtIdx(p.kospi.close) : ((p as unknown as { index?: { QQQ?: { close?: number } } }).index?.QQQ?.close ?? 0).toFixed(2) + "달러";
  const hiVal = kr ? fmtIdx(p.kospi.high) : ((p as unknown as { index?: { QQQ?: { high?: number } } }).index?.QQQ?.high ?? 0).toFixed(2);
  const loVal = kr ? fmtIdx(p.kospi.low) : ((p as unknown as { index?: { QQQ?: { low?: number } } }).index?.QQQ?.low ?? 0).toFixed(2);
  const closePct = kr ? (p.kospi.chg_pct ?? 0) : ((p as unknown as { index?: { QQQ?: { pct?: number } } }).index?.QQQ?.pct ?? 0);
  const hiRight = hi ? xOf(hi.t) > W * 0.55 : false;
  const loRight = lo ? xOf(lo.t) > W * 0.55 : false;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W * scale} height={H * scale} style={{ display: "block", overflow: "visible" }}>
      <text x={0} y={TOP - 8} fontSize={fs} fill={C.sub} style={S}>+{yMax}%</text>
      <text x={0} y={BOT - 10} fontSize={fs} fill={C.sub} style={S}>−{yMax}%</text>
      <line x1={0} y1={zero} x2={W} y2={zero} stroke={C.line} strokeWidth={2} />
      <text x={0} y={H + 4} fontSize={fs} fill={C.sub} style={S}>{kr ? "09:00" : "22:30 (ET 09:30)"}</text>
      {!kr && <text x={W / 2} y={TOP - 8} fontSize={fs} fill={C.sub} textAnchor="middle" style={S}>정규장 흐름 · 나스닥100 ETF QQQ 1분봉</text>}
      <text x={W} y={H + 4} fontSize={fs} fill={C.sub} textAnchor="end" style={S}>{kr ? "15:30" : "05:00 (ET 16:00)"}</text>
      <clipPath id="sclip"><rect x={X0} y={0} width={clipW} height={H} /></clipPath>
      {pts.length > 0 && <polyline points={line} fill="none" stroke={C.text} strokeWidth={7} strokeLinejoin="round" strokeLinecap="round" clipPath="url(#sclip)" />}
      {hi && (
        <g opacity={labels[1] ?? 0}>
          <circle cx={xOf(hi.t)} cy={y(hi.pct)} r={10} fill={C.up} />
          <text x={hiRight ? xOf(hi.t) - 16 : xOf(hi.t) + 16} y={y(hi.pct) - 24} fontSize={34} fill={C.up} textAnchor={hiRight ? "end" : "start"} style={S}>고점 {hiVal}{kr ? "" : "달러"}</text>
        </g>
      )}
      {lo && (
        <g opacity={labels[3] ?? 0}>
          <circle cx={xOf(lo.t)} cy={y(lo.pct)} r={10} fill={C.down} />
          <text x={loRight ? xOf(lo.t) - 16 : xOf(lo.t) + 16} y={y(lo.pct) + 46} fontSize={34} fill={C.down} textAnchor={loRight ? "end" : "start"} style={S}>저점 {loVal}{kr ? "" : "달러"}</text>
        </g>
      )}
      {last && (
        <g opacity={labels[4] ?? 0}>
          <circle cx={W} cy={y(last.pct)} r={10} fill={closePct >= 0 ? C.up : C.down} />
          <text x={W - 4} y={BOT - 12} fontSize={36} fontWeight={600} fill={closePct >= 0 ? C.up : C.down} textAnchor="end" style={S}>{kr ? `마감 ${closeVal} · ${closePct > 0 ? "+" : ""}${closePct.toFixed(2)}%` : `QQQ 마감 ${closeVal}`}</text>
        </g>
      )}
    </svg>
  );
};
