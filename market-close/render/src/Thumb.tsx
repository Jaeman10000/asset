/** 썸네일 전용 스틸 (1080×1920) — 배경 + 그림 + 글자를 겹쳐 만든다.
 * 이유(JJ 2026-09-13): 영상 프레임을 잘라 쓰면 로고·날짜·고지·데이터 카드가 자리를 먹어 글자를 못 키운다.
 * 그리고 글자만 얹으면 반쪽이다 — 눈이 먼저 잡는 건 그림이다.
 *
 * 그림은 전부 여기서 SVG로 그린다(외부 이미지를 받아 쓰지 않는다 — 저작권 확인 없이 쓸 수 없다).
 *
 * props.thumb = {
 *   bg: "city"|"market"|"chip"|"us_fed",  tone: "up"|"down"|"neutral",  dim: 0~1,
 *   objects?: [                      // 글자 뒤/옆에 깔리는 그림. 먼저 그린 것이 아래.
 *     {k:"clock", h:8, m:0, x:660, y:980, size:420, color:"yellow", label:"밤 8시", strike:false},
 *     {k:"phone", x:120, y:1050, w:360, tone:"down", label:"3:30"},
 *     {k:"glow",  x:540, y:900, r:520, color:"yellow", a:0.20},
 *     {k:"arrow", x:520, y:1180, w:220, color:"yellow", dir:"right"}
 *   ],
 *   badge?: "내일 9월 14일",
 *   lines: [{t:"밤 8시까지", size?:1.0, color?:"yellow", gap?:46}, ...],   // gap = 이 줄 위에 띄우는 px
 *   sub?: "그런데 종가는 3시 반?",
 *   logo?: boolean
 * }
 */
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { FONT } from "./tokens";
import type { Props } from "./types";

const COL: Record<string, string> = { yellow: "#FFD84D", white: "#FFFFFF", red: "#FF4D4D", blue: "#3D7BFF", green: "#2FD27A", grey: "#8C99AD" };
const col = (c?: string) => COL[c ?? "white"] ?? c ?? "#FFFFFF";

type Line = { t: string; size?: number; color?: string; gap?: number };
type Obj = Record<string, never> & { k: string; [k: string]: unknown };
type T = { bg?: string; tone?: string; dim?: number; badge?: string; lines?: Line[]; sub?: string; logo?: boolean; objects?: Obj[] };

/** 시계 — 숫자 하나를 그림으로 보여 주는 가장 빠른 방법 */
const Clock: React.FC<{ o: Record<string, unknown> }> = ({ o }) => {
  const size = (o.size as number) ?? 420;
  const c = col(o.color as string);
  const h = (o.h as number) ?? 8, m = (o.m as number) ?? 0;
  const ha = (h % 12) * 30 + m * 0.5 - 90;
  const ma = m * 6 - 90;
  const R = 50, cx = 60, cy = 60;
  const hand = (deg: number, len: number, w: number) => {
    const r = (deg * Math.PI) / 180;
    return <line x1={cx} y1={cy} x2={cx + Math.cos(r) * len} y2={cy + Math.sin(r) * len} stroke={c} strokeWidth={w} strokeLinecap="round" />;
  };
  return (
    <div style={{ position: "absolute", left: (o.x as number) ?? 0, top: (o.y as number) ?? 0, width: size, height: size,
      filter: `drop-shadow(0 0 34px ${c}66)`, opacity: (o.strike ? 0.42 : 1) }}>
      <svg viewBox="0 0 120 120" width={size} height={size}>
        <circle cx={cx} cy={cy} r={R} fill="rgba(5,8,16,0.55)" stroke={c} strokeWidth={5} />
        {[...Array(12)].map((_, i) => {
          const a = ((i * 30 - 90) * Math.PI) / 180;
          return <circle key={i} cx={cx + Math.cos(a) * (R - 9)} cy={cy + Math.sin(a) * (R - 9)} r={i % 3 === 0 ? 3 : 1.6} fill={c} opacity={i % 3 === 0 ? 1 : 0.5} />;
        })}
        {hand(ha, 26, 7)}
        {hand(ma, 37, 4.5)}
        <circle cx={cx} cy={cy} r={4} fill={c} />
        {o.strike ? <line x1={20} y1={100} x2={100} y2={20} stroke="#FF4D4D" strokeWidth={7} strokeLinecap="round" /> : null}
      </svg>
      {o.label ? (
        <div style={{ textAlign: "center", marginTop: -10, fontSize: Math.round(size * 0.17), fontWeight: 900, color: c, letterSpacing: "-0.04em" }}>{o.label as string}</div>
      ) : null}
    </div>
  );
};

/** 휴대폰 — '내 앱에서 벌어지는 일'을 그림으로 */
const Phone: React.FC<{ o: Record<string, unknown> }> = ({ o }) => {
  const w = (o.w as number) ?? 360, h = Math.round(w * 2.05);
  const c = col((o.tone as string) === "up" ? "red" : (o.tone as string) === "down" ? "blue" : "yellow");
  return (
    <div style={{ position: "absolute", left: (o.x as number) ?? 0, top: (o.y as number) ?? 0, width: w, height: h,
      transform: `rotate(${(o.rotate as number) ?? -8}deg)`, filter: "drop-shadow(0 22px 60px rgba(0,0,0,0.75))" }}>
      <div style={{ width: "100%", height: "100%", borderRadius: w * 0.14, background: "linear-gradient(180deg,#11151F,#070A12)",
        border: `${Math.round(w * 0.022)}px solid #2E3444`, overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", left: "50%", top: w * 0.045, width: w * 0.3, height: w * 0.055, background: "#2E3444", borderRadius: 99, transform: "translateX(-50%)" }} />
        <svg viewBox="0 0 100 120" width="100%" height="72%" style={{ position: "absolute", bottom: "8%" }}>
          <polyline points="4,92 16,74 26,84 38,52 50,64 62,34 74,46 86,18 96,26" fill="none" stroke={c} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" />
          <polyline points="4,92 16,74 26,84 38,52 50,64 62,34 74,46 86,18 96,26 96,120 4,120" fill={`${c}22`} stroke="none" />
        </svg>
        {o.label ? (
          <div style={{ position: "absolute", left: 0, right: 0, top: w * 0.16, textAlign: "center", fontFamily: FONT,
            fontSize: Math.round(w * 0.2), fontWeight: 900, color: c, letterSpacing: "-0.04em" }}>{o.label as string}</div>
        ) : null}
      </div>
    </div>
  );
};

const Glow: React.FC<{ o: Record<string, unknown> }> = ({ o }) => {
  const r = (o.r as number) ?? 520, c = col(o.color as string);
  return <div style={{ position: "absolute", left: ((o.x as number) ?? 0) - r, top: ((o.y as number) ?? 0) - r, width: r * 2, height: r * 2,
    borderRadius: "50%", background: `radial-gradient(circle, ${c}${Math.round(((o.a as number) ?? 0.2) * 255).toString(16).padStart(2, "0")} 0%, rgba(0,0,0,0) 70%)` }} />;
};

const Arrow: React.FC<{ o: Record<string, unknown> }> = ({ o }) => {
  const w = (o.w as number) ?? 220, c = col(o.color as string);
  return (
    <div style={{ position: "absolute", left: (o.x as number) ?? 0, top: (o.y as number) ?? 0, width: w, filter: `drop-shadow(0 0 22px ${c}77)` }}>
      <svg viewBox="0 0 100 36" width={w}><path d="M2 18 H78 M62 4 L80 18 L62 32" stroke={c} strokeWidth={9} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </div>
  );
};

const OBJ: Record<string, React.FC<{ o: Record<string, unknown> }>> = { clock: Clock, phone: Phone, glow: Glow, arrow: Arrow };

const Logo: React.FC = () => (
  <div style={{ position: "absolute", left: 72, top: 64 }}>
    <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 54, color: "#FFFFFF", transform: "skewX(-10deg)", letterSpacing: "-0.05em", lineHeight: 1,
      textShadow: "0 3px 16px rgba(0,0,0,0.7)" }}>누가샀나</div>
    <svg width="198" height="22" viewBox="0 0 220 24" style={{ display: "block", marginTop: 2 }}>
      <path d="M6 15 C60 6, 150 6, 214 13" stroke="#E8232B" strokeWidth="9" strokeLinecap="round" fill="none" />
    </svg>
  </div>
);

export const Thumb: React.FC<Props> = (p) => {
  const t = ((p as unknown as { thumb?: T }).thumb ?? {}) as T;
  const lines = t.lines ?? [{ t: "제목을 넣으세요" }];
  const bg = `${t.bg ?? "city"}_${t.tone ?? "neutral"}`;
  const base = lines.length <= 2 ? 200 : lines.length === 3 ? 168 : 138;
  return (
    <AbsoluteFill style={{ background: "#05070D", fontFamily: FONT, color: "#FFFFFF" }}>
      <Img src={staticFile(`bg/${bg}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <AbsoluteFill style={{ background: `rgba(3,5,10,${t.dim ?? 0.34})` }} />
      {(t.objects ?? []).map((o, i) => {
        const C = OBJ[o.k as string];
        return C ? <C key={i} o={o as unknown as Record<string, unknown>} /> : null;
      })}
      {/* 글자 뒤만 더 어둡게 — 그림 위에서도 글자가 뜬다 */}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(3,5,10,0.80) 0%, rgba(3,5,10,0.52) 44%, rgba(3,5,10,0.06) 66%, rgba(3,5,10,0.45) 100%)", pointerEvents: "none" }} />
      {t.logo === false ? null : <Logo />}
      <div style={{ position: "absolute", left: 72, right: 72, top: 250 }}>
        {t.badge ? (
          <div style={{ display: "inline-block", fontSize: 46, fontWeight: 900, color: "#0B0E16", background: COL.yellow, padding: "12px 30px", borderRadius: 16, marginBottom: 28 }}>{t.badge}</div>
        ) : null}
        {lines.map((l, i) => (
          <div key={i} style={{ fontSize: Math.round(base * (l.size ?? 1)), fontWeight: 900, lineHeight: 1.04, letterSpacing: "-0.055em",
            marginTop: l.gap ?? 0, color: col(l.color), wordBreak: "keep-all",
            textShadow: (l.color === "yellow" ? "0 0 46px rgba(255,216,77,0.5), " : "") + "0 10px 40px rgba(0,0,0,0.9)" }}>{l.t}</div>
        ))}
        {t.sub ? (
          <div style={{ fontSize: 60, fontWeight: 800, color: "#E6E6E3", marginTop: 30, wordBreak: "keep-all", textShadow: "0 6px 26px rgba(0,0,0,0.95)" }}>{t.sub}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
