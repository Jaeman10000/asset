import React, { useEffect, useState } from "react";
import { AbsoluteFill, Composition, continueRender, delayRender, registerRoot, staticFile } from "remotion";
import { BgWallSt } from "./BgWallSt";
import { BgFed } from "./BgFed";
import { BgMacro } from "./BgMacro";

// 미국 주간 배경을 색조별로 한 번만 그림으로 굽는다 → public/bg/us_<name>_<tone>.jpg (영상에서는 고정 그림만 쓴다)
// npx remotion still src/v4/usbg/BakeUSEntry.tsx BakeUS public/bg/us_wallst_up.jpg --frame=60 --props=<json> --image-format=jpeg --jpeg-quality=88
type P = { name: string; tone: "up" | "down" | "neutral" };

const useFont = () => {
  const [h] = useState(() => delayRender("font"));
  useEffect(() => {
    const el = document.createElement("style");
    el.textContent = `@font-face{font-family:Pretendard;font-weight:800;src:url(${staticFile("fonts/Pretendard-ExtraBold.woff2")}) format('woff2');font-display:block}`;
    document.head.appendChild(el);
    document.fonts.load("800 40px Pretendard").then(() => continueRender(h), () => continueRender(h));
  }, [h]);
};

const Bake: React.FC<P> = ({ name, tone }) => {
  useFont();
  return <AbsoluteFill>{name === "fed" ? <BgFed tone={tone} dim={0} /> : name === "macro" ? <BgMacro tone={tone} dim={0} /> : <BgWallSt tone={tone} dim={0} />}</AbsoluteFill>;
};

registerRoot(() => (
  <Composition id="BakeUS" component={Bake as unknown as React.FC<Record<string, unknown>>} width={1080} height={1920} fps={30} durationInFrames={120} defaultProps={{ name: "wallst", tone: "up" }} />
));
