import React from "react";
import { AbsoluteFill } from "remotion";
import { Chart } from "./Chart";
import { C, FONT, FOOTER, colorOf, fmtEok, fmtIdx, fmtPct } from "./tokens";
import { useFonts } from "./Video";
import type { Props } from "./types";

/** Threads·IG 카드 1080×1350 — 네 칸 (SPEC §1-2). 카드는 영상의 0.75배 크기 체계. */
const K: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontSize: 27, color: C.sub, letterSpacing: "0.02em", ...style }}>{children}</div>
);
const Blk: React.FC<{ k: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ k, children, style }) => (
  <div style={{ borderTop: `2px solid ${C.line}`, paddingTop: 14, ...style }}>
    <K style={{ marginBottom: 8 }}>{k}</K>
    {children}
  </div>
);
const stateLabel = (s: string, streak: number) => (s.startsWith("쌓임") ? `쌓임 · ${streak}일${s.includes("확산") ? " · 확산" : ""}` : s);

export const Card: React.FC<Props> = (p) => {
  useFonts();
  const inv = p.investors;
  const maxAbs = Math.max(1, ...inv.bars.map((b) => Math.abs(b.v ?? 0)));
  const chg = p.kospi.chg_pct ?? 0;
  return (
    <AbsoluteFill style={{ background: C.bg, color: C.text, fontFamily: FONT, fontVariantNumeric: "tabular-nums", padding: "60px 96px 56px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 18 }}>
        <div style={{ fontSize: 48, fontWeight: 600, letterSpacing: "-0.01em" }}>{p.date_label} 국내장 마감</div>
        <div style={{ fontSize: 27, color: C.sub, textAlign: "right", lineHeight: 1.5 }}>
          코스피 <span style={{ color: colorOf(chg), fontWeight: 600 }}>{fmtIdx(p.kospi.close)} {fmtPct(chg)}</span><br />
          코스닥 <span style={{ color: colorOf(p.kosdaq.chg_pct), fontWeight: 600 }}>{fmtIdx(p.kosdaq.close)} {fmtPct(p.kosdaq.chg_pct)}</span>
          {Math.abs(p.kosdaq.streak ?? 0) >= 2 ? ` · ${Math.abs(p.kosdaq.streak!)}일 연속${(p.kosdaq.streak ?? 0) < 0 ? "↓" : "↑"}` : ""}
        </div>
      </div>
      <Blk k="코스피 · 09:00 → 15:30 · 전일 종가 대비">
        <div style={{ marginTop: 4 }}><Chart p={p} night={1} day={1} labels={[1, 1, 1, 1, 1]} scale={0.43} mode="kr" /></div>
      </Blk>
      <Blk k={`수급 · ${inv.state === "ready" ? (inv.src ?? "") : "집계 대기"}`} style={{ marginTop: 22 }}>
        {inv.state === "ready" ? (
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 200px", rowGap: 6, columnGap: 20, alignItems: "center", fontSize: 28 }}>
            {inv.bars.map((b) => (
              <React.Fragment key={b.name}>
                <span>{b.name}</span>
                <div style={{ height: 12, width: `${(Math.abs(b.v ?? 0) / maxAbs) * 100}%`, background: colorOf(b.v) }} />
                <span style={{ color: colorOf(b.v), textAlign: "right", fontWeight: 600 }}>{fmtEok(b.v, true)}</span>
              </React.Fragment>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 30, color: C.sub }}>수급 집계 반영 후 갱신</div>
        )}
        <K style={{ marginTop: 12 }} >{inv.title.replace(/<br>/g, " ")}</K>
      </Blk>
      <Blk k="돈의 이동 · 테마 외국인+기관 · 어제 → 오늘 · 억원" style={{ marginTop: 22 }}>
        {p.moves.map((m) => (
          <div key={m.theme} style={{ display: "grid", gridTemplateColumns: "110px 1fr 220px", alignItems: "center", columnGap: 16, fontSize: 28, marginBottom: 6 }}>
            <div>{m.theme}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontWeight: 600 }}>
              <span style={{ color: colorOf(m.y) }}>{fmtEok(m.y, true)}</span><span style={{ flex: 1, height: 2, background: C.line }} /><span style={{ color: colorOf(m.t) }}>{fmtEok(m.t, true)}</span>
            </div>
            <div style={{ fontSize: 24, color: C.sub, textAlign: "right" }}>{stateLabel(m.state, m.streak)}</div>
          </div>
        ))}
      </Blk>
      <Blk k="다음에 볼 것" style={{ marginTop: 22 }}>
        <div style={{ fontSize: 26, lineHeight: 1.45 }}>
          {p.watch.map((w, i) => <div key={i}><b style={{ fontWeight: 600 }}>{i === 0 ? "①" : "②"}</b> {w.q} <span style={{ color: C.sub }}>→ {w.how}</span></div>)}
          <K style={{ marginTop: 8 }}>{p.schedule.map((s) => s.d.includes("~") ? `${+s.d.slice(5, 7)}/${+s.d.slice(8, 10)}~${+s.d.slice(-2)} ${s.t}` : `${+s.d.slice(5, 7)}/${+s.d.slice(8, 10)}${s.d.length >= 16 ? " " + s.d.slice(11, 16) : ""} ${s.t}`).join(" · ")}</K>
        </div>
      </Blk>
      <div style={{ position: "absolute", left: 96, right: 96, bottom: 28, fontSize: 21, color: C.sub }}>{FOOTER} · 출처 KRX 확정치 · 키움 REST(지수 1분봉·QQQ) · 보도</div>
    </AbsoluteFill>
  );
};
