/** 유튜브 채널 사진 (900×900, 유튜브가 원형으로 자른다) — 주사위 탐정 v3 정장 (JJ 2026-09-21 "최신 캐릭터로 교체").
 *  상반신 컷(phone_close 514×540)을 쓴다 — 전신 컷을 확대하면 흐려진다. 작게 줄어드니 얼굴이 커야 알아본다. */
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

const S = 900;

export const ChannelProfile: React.FC = () => (
  <AbsoluteFill style={{ background: "#0B1222" }}>
    <div style={{ position: "absolute", left: 0, top: 0, width: S, height: S, borderRadius: S / 2, overflow: "hidden",
      background: "radial-gradient(circle at 50% 34%, #27467A 0%, #16243F 58%, #0B1222 100%)",
      border: "12px solid #FFFFFF", boxSizing: "border-box" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(255,255,255,0.05) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,0.05) 2px, transparent 2px)", backgroundSize: "56px 56px" }} />
      <Img src={staticFile("mascot/v3/phone_close.png")}
        style={{ position: "absolute", width: 514 * 1.6, height: 540 * 1.6, left: 34, top: 176,
          filter: "drop-shadow(0 20px 30px rgba(0,0,0,0.5))" }} />
    </div>
  </AbsoluteFill>
);
