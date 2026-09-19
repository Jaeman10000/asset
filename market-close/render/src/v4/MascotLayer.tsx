/** 주사위 탐정 영상 출연 (JJ 9/20 "OK, 넣어") — 한 편 4~6번, 한 번 2~3초, 말에 맞춘 포즈로 빈 자리에 튀어 올라왔다 내려간다.
 * props.mascot_beats = [{ t: 시작 초(영상 전체 기준), dur: 초, pose: "point_surprise"|"peer"|"tablet_think"|"arms_suspect"|"thumbs_found"|"face_*",
 *                         x, y, h: 1080×1920 기준 위치·키, flip?: 좌우 뒤집기 }]
 * 숫자·글자·자막을 가리지 않는 자리는 대본마다 사람이 정한다(프레임으로 확인). 그림은 render/public/mascot/*.png(정본 시트에서 오린 컷). */
import React from "react";
import { AbsoluteFill, Img, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";

export type MascotBeat = { t: number; dur: number; pose: string; x: number; y: number; h: number; flip?: boolean };

const Pop: React.FC<{ b: MascotBeat; frames: number }> = ({ b, frames }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inn = spring({ frame: f, fps, config: { damping: 11, stiffness: 170, mass: 0.7 } });
  const out = interpolate(f, [frames - 8, frames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = (1 - inn) * 140 + out * 90;
  const op = Math.min(1, f / 4) * (1 - out);
  const bob = Math.sin((f / fps) * Math.PI * 1.6) * 4;          // 숨 쉬듯 살짝
  return (
    <div style={{ position: "absolute", left: b.x, top: b.y, height: b.h, opacity: op,
      transform: `translateY(${y + bob}px) scale(${0.9 + 0.1 * inn})${b.flip ? " scaleX(-1)" : ""}`, transformOrigin: "50% 100%",
      filter: "drop-shadow(0 16px 22px rgba(0,0,0,0.45))" }}>
      <Img src={staticFile(`mascot/${b.pose}.png`)} style={{ height: b.h }} />
    </div>
  );
};

export const MascotLayer: React.FC<{ beats?: MascotBeat[] }> = ({ beats }) => {
  const { fps } = useVideoConfig();
  if (!beats?.length) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {beats.map((b, i) => {
        const frames = Math.max(12, Math.round(b.dur * fps));
        return (
          <Sequence key={i} from={Math.round(b.t * fps)} durationInFrames={frames} name={`mascot-${b.pose}`}>
            <Pop b={b} frames={frames} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
