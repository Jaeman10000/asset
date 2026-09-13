import React from "react";
import { Composition, Still } from "remotion";
import { Card } from "./Card";
import { Video } from "./Video";
import type { Props } from "./types";
import sample from "./sample_kr.json";
import sampleUS from "./sample_us.json";
import { CardUS } from "./ScenesUS";
import { Thumb } from "./Thumb";

const P = sample as unknown as Props;
const PU = sampleUS as unknown as Props;

export const Root: React.FC = () => (
  <>
    <Composition
      id="Video"
      component={Video}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={P.total_frames ?? 30 * 45}
      defaultProps={P}
      calculateMetadata={({ props }) => ({ durationInFrames: (props as Props).total_frames ?? 30 * 45, fps: (props as Props).fps ?? 30 })}
    />
    <Still id="Card" component={Card} width={1080} height={1350} defaultProps={P} />
    <Composition
      id="VideoUS"
      component={Video}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={PU.total_frames ?? 30 * 45}
      defaultProps={PU}
      calculateMetadata={({ props }) => ({ durationInFrames: (props as Props).total_frames ?? 30 * 45, fps: (props as Props).fps ?? 30 })}
    />
    <Still id="CardUS" component={CardUS as never} width={1080} height={1350} defaultProps={PU} />
    {/* 썸네일 전용(1080×1920) — props로 글자만 받는다. jobs/make_thumb.py 가 호출한다. */}
    <Still id="Thumb" component={Thumb} width={1080} height={1920} defaultProps={P} />
  </>
);
