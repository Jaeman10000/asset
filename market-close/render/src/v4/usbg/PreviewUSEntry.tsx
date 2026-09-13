import React, { useEffect, useState } from "react";
import { AbsoluteFill, Composition, continueRender, delayRender, registerRoot, staticFile } from "remotion";
import { fontCss } from "../../tokens";
import { USW_COMP } from "../WeeklyUSV4";
import type { Props } from "../../types";
import type { Cue } from "../../Scenes";

// 미국 주간 화면 격리 미리보기: props(주간 JSON + scenes) 에서 scene 하나(uw0~uw6)만 그린다. 프레임 = 그 장면 안의 시각.
// npx remotion still src/v4/usbg/PreviewUSEntry.tsx PreviewUS out.jpg --frame=90 --props=<json(+ "scene":"uw1")>
type P = Props & { scene?: string };

const useFonts = () => {
  const [h] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const css = fontCss.replace("FONT_REG", staticFile("fonts/Pretendard-Regular.woff2")).replace("FONT_SEMI", staticFile("fonts/Pretendard-SemiBold.woff2"))
      .replace("FONT_XB", staticFile("fonts/Pretendard-ExtraBold.woff2")).replace("FONT_BLK", staticFile("fonts/Pretendard-Black.woff2"));
    const el = document.createElement("style");
    el.textContent = css;
    document.head.appendChild(el);
    Promise.all(["400", "600", "800", "900"].map((wt) => document.fonts.load(`${wt} 40px Pretendard`))).then(() => continueRender(h), () => continueRender(h));
  }, [h]);
};

const Preview: React.FC<P> = (p) => {
  useFonts();
  const id = p.scene ?? "uw0";
  const sc = (p.scenes ?? []).find((s) => s.id === id);
  const Sc = USW_COMP[id];
  return <AbsoluteFill style={{ background: "#05070D" }}>{sc && USW_COMP[id] ? <Sc p={p} sub={sc.sub} cues={(sc as unknown as { cues?: Cue[] }).cues} /> : null}</AbsoluteFill>;
};

registerRoot(() => (
  <Composition id="PreviewUS" component={Preview as unknown as React.FC<Record<string, unknown>>} width={1080} height={1920} fps={30} durationInFrames={900}
    defaultProps={{ scene: "uw0", scenes: [], date_label: "", fps: 30 } as Record<string, unknown>} />
));
