/** 유튜브 채널 배너 (2560×1440, 모든 기기 안전 영역 가운데 1546×423) — 주사위 탐정 + 누가샀나 (JJ 9/20) */
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { FONT } from "../tokens";

const YEL = "#FFD43B", RED = "#E8342C", BLUE = "#2F6BFF";
const SX = 507, SY = 508, SW = 1546, SH = 423;   // 안전 영역

const Bars: React.FC<{ x: number; flip?: boolean }> = ({ x, flip }) => {
  const v = [34, -22, 48, 18, -40, 62, -16, 28, 70, -30, 44, 22];
  return (
    <div style={{ position: "absolute", left: x, top: SY + 60, width: 420, height: 300, display: "flex", alignItems: "center", gap: 12, opacity: 0.22, transform: flip ? "scaleX(-1)" : undefined }}>
      {v.map((h, i) => <div key={i} style={{ width: 22, height: Math.abs(h) * 3.4, background: h > 0 ? RED : BLUE, borderRadius: 4, alignSelf: h > 0 ? "flex-end" : "flex-start", marginTop: h > 0 ? 0 : 150, marginBottom: h > 0 ? 150 : 0 }} />)}
    </div>
  );
};

export const ChannelBanner: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: FONT, background: "radial-gradient(ellipse at 50% 50%, #1E3259 0%, #0B1222 55%, #05070D 100%)" }}>
    <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.045) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,0.045) 2px, transparent 2px)", backgroundSize: "64px 64px" }} />
    <Bars x={40} />
    <Bars x={2100} flip />
    {/* 탐정 — 안전 영역 왼쪽, 발은 안전 영역 아래 끝 */}
    <div style={{ position: "absolute", left: SX + 50, top: SY + 4, height: SH - 4, filter: "drop-shadow(0 18px 30px rgba(0,0,0,0.6))" }}>
      <Img src={staticFile("mascot/thumbs_found.png")} style={{ height: SH - 4 }} />
    </div>
    <div style={{ position: "absolute", left: SX + 420, top: SY + 18, width: SW - 440 }}>
      <div style={{ fontSize: 190, fontWeight: 900, color: "#FFFFFF", lineHeight: 1, letterSpacing: "-0.04em", WebkitTextStroke: "14px #000", paintOrder: "stroke fill" }}>누가샀나<span style={{ color: RED }}>.</span></div>
      <div style={{ fontSize: 70, fontWeight: 900, color: YEL, marginTop: 26, letterSpacing: "-0.03em", WebkitTextStroke: "8px #000", paintOrder: "stroke fill" }}>오늘 주식, 누가 샀을까?</div>
      <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4", marginTop: 26 }}>평일 저녁 5시 국장 마감 · 토 주간 결산 · 일 미장 주간</div>
    </div>
  </AbsoluteFill>
);
