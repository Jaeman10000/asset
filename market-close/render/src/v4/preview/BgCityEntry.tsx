import React, { useEffect, useState } from "react";
import { AbsoluteFill, Composition, continueRender, delayRender, Freeze, registerRoot, staticFile } from "remotion";
import { BgCity, type Tone } from "../BgCity";

// 격리 미리보기: BgCity 위에 큰 제목과 카드 더미를 얹어 가독성 확인
// props: tone, seed, plain(글자·카드 숨김), bare(배경 숨김 — 렌더 속도 기준선 측정용)
type DemoProps = { tone: Tone; seed?: number; plain?: boolean; bare?: boolean; freeze?: boolean; inspect?: [number, number, number] };

const Demo: React.FC<DemoProps> = (p) => {
  const { inspect } = p;
  if (!inspect) return <Inner {...p} />;
  const [x, y, s] = inspect; // 확대 점검: (x,y)를 중심으로 s배
  return (
    <AbsoluteFill style={{ transform: `scale(${s})`, transformOrigin: `${x}px ${y}px` }}>
      <Inner {...p} />
    </AbsoluteFill>
  );
};

const Inner: React.FC<DemoProps> = ({ tone, seed = 7, plain, bare, freeze }) => {
  const [h] = useState(() => delayRender("font"));
  useEffect(() => {
    const el = document.createElement("style");
    el.textContent = `@font-face{font-family:Pretendard;font-weight:600;src:url(${staticFile("fonts/Pretendard-SemiBold.woff2")}) format('woff2');font-display:block}`;
    document.head.appendChild(el);
    document.fonts.load("600 40px Pretendard").then(
      () => continueRender(h),
      () => continueRender(h),
    );
  }, [h]);
  const accent = tone === "up" ? "#FF4D4D" : tone === "down" ? "#3D7BFF" : "#7FB2FF";
  return (
    <AbsoluteFill style={{ background: "#000", fontFamily: "Pretendard, 'Malgun Gothic', sans-serif" }}>
      {!bare && (freeze ? (
        <Freeze frame={0}>
          <BgCity tone={tone} seed={seed} />
        </Freeze>
      ) : (
        <BgCity tone={tone} seed={seed} />
      ))}
      {!plain && (
        <>
          <div style={{ position: "absolute", left: 90, right: 90, top: 200, fontSize: 170, fontWeight: 600, lineHeight: 1.12, color: "#FFFFFF", letterSpacing: "-0.03em", wordBreak: "keep-all", textShadow: "0 6px 30px rgba(0,0,0,0.6)" }}>
            외국인 <span style={{ color: "#FFD84D" }}>2.5조</span> 매도
          </div>
          <div style={{ position: "absolute", left: 90, top: 640, fontSize: 56, color: "#C9CED8", fontWeight: 600 }}>코스피 −1.8% · 2,540</div>
          <div
            style={{
              position: "absolute",
              left: 96,
              right: 96,
              top: 1180,
              height: 400,
              borderRadius: 28,
              background: "rgba(10,14,26,0.72)",
              border: "1px solid rgba(255,255,255,0.10)",
              padding: 44,
              boxSizing: "border-box",
              color: "#F2F2F0",
            }}
          >
            <div style={{ fontSize: 36, color: "#8E8E93" }}>순매도 상위</div>
            {["삼성전자", "SK하이닉스", "현대차"].map((n, i) => (
              <div key={n} style={{ display: "flex", justifyContent: "space-between", fontSize: 58, fontWeight: 600, marginTop: i ? 18 : 28 }}>
                <span>{n}</span>
                <span style={{ color: accent }}>−{(9800 - i * 2300).toLocaleString("ko-KR")}억</span>
              </div>
            ))}
          </div>
        </>
      )}
    </AbsoluteFill>
  );
};

registerRoot(() => (
  <Composition id="P" component={Demo} width={1080} height={1920} fps={30} durationInFrames={300} defaultProps={{ tone: "down" } as DemoProps} />
));
