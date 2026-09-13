import React, { useEffect, useState } from "react";
import { AbsoluteFill, Composition, continueRender, delayRender, registerRoot, staticFile } from "remotion";
import { BgMarket, type Tone } from "../BgMarket";

const FONT = "Pretendard, 'Noto Sans KR', 'Malgun Gothic', sans-serif";

const useFont = () => {
  const [h] = useState(() => delayRender("font"));
  useEffect(() => {
    const el = document.createElement("style");
    el.textContent = `@font-face{font-family:Pretendard;font-weight:600;src:url(${staticFile("fonts/Pretendard-SemiBold.woff2")}) format('woff2');font-display:block}`;
    document.head.appendChild(el);
    document.fonts
      .load("600 40px Pretendard")
      .then(() => continueRender(h))
      .catch(() => continueRender(h));
  }, [h]);
};

const Demo: React.FC<{ tone: Tone; bare?: boolean; blank?: boolean; seed?: number }> = ({ tone, bare, blank, seed = 7 }) => {
  useFont();
  if (blank) return <AbsoluteFill style={{ background: "linear-gradient(#000, #123)" }} />; // 렌더 속도 기준선
  if (bare) return <BgMarket tone={tone} seed={seed} />;
  return (
    <AbsoluteFill>
      <BgMarket tone={tone} seed={seed} />
      <div style={{ position: "absolute", left: 80, top: 160, right: 60, fontFamily: FONT, fontWeight: 600, fontSize: 36, color: "rgba(255,255,255,0.6)", letterSpacing: "0.02em" }}>9월 11일(목) 장 마감</div>
      <div
        style={{
          position: "absolute",
          left: 76,
          top: 230,
          right: 50,
          fontFamily: FONT,
          fontWeight: 600,
          fontSize: 170,
          lineHeight: 1.12,
          color: "#FFFFFF",
          letterSpacing: "-0.03em",
          wordBreak: "keep-all",
          textShadow: "0 6px 30px rgba(0,0,0,0.5)",
        }}
      >
        외국인 <span style={{ color: "#FFD84D" }}>2.5조</span> 매도
      </div>
      <div
        style={{
          position: "absolute",
          left: 80,
          right: 80,
          top: 1190,
          height: 440,
          borderRadius: 32,
          background: "rgba(14,18,30,0.78)",
          border: "2px solid rgba(255,255,255,0.08)",
          padding: 48,
          fontFamily: FONT,
          fontWeight: 600,
          color: "#F2F2F0",
          fontSize: 56,
        }}
      >
        <div style={{ fontSize: 34, color: "#8E8E93" }}>외국인 순매도 상위</div>
        <div style={{ marginTop: 28 }}>삼성전자 −1.2조</div>
        <div style={{ marginTop: 18 }}>SK하이닉스 −6,400억</div>
      </div>
    </AbsoluteFill>
  );
};

registerRoot(() => (
  <Composition id="P" component={Demo} width={1080} height={1920} fps={30} durationInFrames={300} defaultProps={{ tone: "down" as Tone, bare: false, seed: 7 }} />
));
