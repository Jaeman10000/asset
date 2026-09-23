/** 경제사냥꾼 방식 썸네일 (JJ 9/20) — 위: Gemini 장면(관련 인물·소품, 글자 없음) · 아래: 굵은 글자 3~4줄(흰·노랑) · 주사위 탐정은 우리 고정 컷을 붙인다.
 * props.info.thumbS = { src: "thumbsrc/…jpg", tag?, lines: [{t, color?, size?}], mascot?: { src: "mascot/…png", x, y, h, flip? }, cut?: 0.56 } */
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import type { Props } from "../types";
import { FONT } from "../tokens";

type TS = {
  src: string; shot?: string; tag?: string; cut?: number; logoLeft?: boolean; img?: { x: number; y: number; w: number; h: number }; textTop?: number;
  lines: { t: string; color?: "white" | "yellow" | "red"; size?: number }[];
  mascot?: { src: string; x: number; y: number; h: number; w: number; flip?: boolean; clipBottom?: number };
};
const YEL = "#FFD43B";
const col = (c?: string) => (c === "yellow" ? YEL : c === "red" ? "#FF4A3D" : "#FFFFFF");

export const SceneThumb: React.FC<Props> = (p) => {
  const th = ((p as unknown as { info?: { thumbS?: TS } }).info?.thumbS ?? { src: "", lines: [] }) as TS;
  const cut = th.cut ?? 0.56;                       // 장면이 차지하는 위쪽 비율
  const top = Math.round(1920 * cut);
  const shot = th.shot ?? th.src;                   // 썸네일 그림만 따로(shot) — 영상 첫 훅(OpenHook)은 src 그대로 써서 i0 과 이어진다
  return (
    <AbsoluteFill style={{ fontFamily: FONT, background: "#05070D" }}>
      {shot ? <Img src={staticFile(shot)} style={th.img ? { position: "absolute", left: th.img.x, top: th.img.y, width: th.img.w, height: th.img.h } : { position: "absolute", left: 0, top: 0, width: 1080, height: 1935, objectFit: "cover", objectPosition: "top" }} /> : null}
      {/* 장면 아래를 어둡게 — 글자 자리 */}
      <div style={{ position: "absolute", left: 0, right: 0, top: top - 260, bottom: 0, background: "linear-gradient(180deg, rgba(5,7,13,0) 0%, rgba(5,7,13,0.85) 26%, #05070D 40%, #05070D 100%)" }} />
      {th.tag ? <div style={{ position: "absolute", left: 44, top: 48, fontSize: 52, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "6px 22px", borderRadius: 10, transform: "rotate(-2deg)", boxShadow: "0 8px 22px rgba(0,0,0,0.5)" }}>{th.tag}</div> : null}
      <div style={{ position: "absolute", ...(th.logoLeft ? { left: 52, top: 142 } : { right: 44, top: 58 }), fontSize: 44, fontWeight: 900, color: "#FFFFFF", textShadow: "0 3px 12px rgba(0,0,0,0.8)" }}>누가샀나<span style={{ color: "#E8342C" }}>.</span></div>
      {th.mascot ? (() => {
        const m = th.mascot; const clip = m.clipBottom ?? 99999; const vis = Math.min(m.h, clip - m.y);
        return (
          <div style={{ position: "absolute", left: m.x, top: m.y, width: m.w, height: vis, overflow: "hidden",
            WebkitMaskImage: clip < m.y + m.h ? "linear-gradient(to bottom, #000 calc(100% - 110px), transparent)" : undefined, filter: "drop-shadow(0 16px 26px rgba(0,0,0,0.6))" }}>
            <Img src={staticFile(m.src)} style={{ width: m.w, height: m.h, transform: m.flip ? "scaleX(-1)" : undefined }} />
          </div>
        );
      })() : null}
      <div style={{ position: "absolute", left: 30, right: 30, top: th.textTop ?? top + 40, textAlign: "center" }}>
        {th.lines.map((l, i) => {
          const sz = l.size ?? 132;
          return (
            <div key={i} style={{ fontSize: sz, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: col(l.color), whiteSpace: "nowrap",
              WebkitTextStroke: `${Math.round(sz / 11)}px #000`, paintOrder: "stroke fill", textShadow: "0 10px 26px rgba(0,0,0,0.9)" }}>{l.t}</div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
