/** 영상 첫 2초 훅 (JJ 2026-09-20 밤: "첫 장면에 훅이 아예 없어. 차라리 썸네일로 시작을 하던가").
 *  쇼츠는 썸네일이 피드에서 잘 안 보인다 → 영상 안에 썸네일을 심는다.
 *  props.info.thumbS(썸네일에 쓰는 장면 그림 + 3줄)를 그대로 쓴다.
 *  **훅 대사가 끝날 때까지 띄운다**(JJ 2026-09-23: "첫 썸네일로 훅을 치려면 그 대사가 끝날 때까지는 보여줘라").
 *  9/20~9/22 는 2.0초 상수라 8초짜리 훅에서도 2초에 사라졌고, 그래서 남은 훅 대사를 다음 장면이 글자로 다시 썼다.
 *  이제 첫 장면 길이에서 닫히는 시간을 뺀 만큼 띄운다. thumbS.hold(초)로 덮어쓸 수 있다.
 *  대본 파일에 thumbS 가 있으면 자동으로 붙는다(정보형 전용 — 평일 국장편은 그대로). */
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT } from "../tokens";
import type { Props } from "../types";

type TS = { src: string; tag?: string; hold?: number; lines: { t: string; color?: string; size?: number }[] };
const YEL = "#FFD43B";
const col = (c?: string) => (c === "yellow" ? YEL : c === "red" ? "#FF4A3D" : "#FFFFFF");

export const OpenHook: React.FC<{ p: Props }> = ({ p }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const th = (p as unknown as { info?: { thumbS?: TS } }).info?.thumbS;
  const OUT = Math.round(fps * 0.45);          // 닫히는 시간
  // 꽉 차 있는 시간 = 훅 장면이 끝날 때까지(닫히는 시간은 그 안에서 쓴다). 대사보다 먼저 사라지지 않는다.
  const first = p.scenes?.[0];
  const firstFrames = first ? (first.frames ?? Math.round((first.sec ?? first.min ?? 2.5) * fps)) : Math.round(fps * 2.45);
  const HOLD = Math.max(Math.round(fps * 1.2), (th?.hold ? Math.round(fps * th.hold) : firstFrames) - OUT);
  if (!th?.src || f > HOLD + OUT) return null;

  const out = interpolate(f, [HOLD, HOLD + OUT], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const zoom = 1.02 + f * 0.0006;
  const lines = (th.lines ?? []).slice(0, 3);
  return (
    <AbsoluteFill style={{ fontFamily: FONT, background: "#05070D", opacity: 1 - out, transform: `scale(${1 + out * 0.06})` }}>
      <Img src={staticFile(th.src)} style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1920, objectFit: "cover", objectPosition: "top", transform: `scale(${zoom})`, transformOrigin: "50% 35%" }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(5,7,13,0.45) 0%, rgba(5,7,13,0) 22%, rgba(5,7,13,0.2) 44%, rgba(5,7,13,0.88) 62%, #05070D 78%)" }} />
      {th.tag ? (
        <div style={{ position: "absolute", left: 44, top: 48, fontSize: 52, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "6px 22px", borderRadius: 10, transform: "rotate(-2deg)", boxShadow: "0 8px 22px rgba(0,0,0,0.5)" }}>{th.tag}</div>
      ) : null}
      <div style={{ position: "absolute", left: 52, top: 142, fontSize: 44, fontWeight: 900, color: "#FFFFFF", textShadow: "0 3px 12px rgba(0,0,0,0.8)" }}>
        누가샀나<span style={{ color: "#E8342C" }}>.</span>
      </div>
      <div style={{ position: "absolute", left: 30, right: 30, top: 1185, textAlign: "center" }}>
        {lines.map((l, i) => {
          const at = i * 4;                                  // 줄이 하나씩 탁탁 붙는다
          const k = interpolate(f, [at, at + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ fontSize: l.size ?? 120, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: col(l.color),
              whiteSpace: "nowrap", opacity: k, transform: `translateY(${(1 - k) * 26}px)`,
              WebkitTextStroke: "14px #05070D", paintOrder: "stroke fill", textShadow: "0 6px 22px rgba(0,0,0,0.75)" }}>{l.t}</div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
