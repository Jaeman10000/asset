import React from "react";
import { Composition, registerRoot } from "remotion";
import { BgCity } from "../BgCity";
import { BgMarket } from "../BgMarket";
import { BgChip } from "../BgChip";

// 배경을 색조별로 한 번만 그림으로 굽는다(영상에서는 그림을 천천히 확대·이동만 → 렌더가 가볍다)
type P = { name: string; tone: "up" | "down" | "neutral" };
const Bake: React.FC<P> = ({ name, tone }) =>
  name === "city" ? <BgCity tone={tone} dim={0} /> : name === "market" ? <BgMarket tone={tone} dim={0} /> : <BgChip tone={tone} dim={0} />;
registerRoot(() => (
  <Composition id="Bake" component={Bake as unknown as React.FC<Record<string, unknown>>} width={1080} height={1920} fps={30} durationInFrames={300} defaultProps={{ name: "city", tone: "down" }} />
));
