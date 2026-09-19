import React from "react";
import { Composition, Still } from "remotion";
import { Card } from "./Card";
import { Video } from "./Video";
import type { Props } from "./types";
import sample from "./sample_kr.json";
import sampleUS from "./sample_us.json";
import { CardUS } from "./ScenesUS";
import { Thumb } from "./Thumb";
import { DissectThumb, HunterThumb, OverlayThumb } from "./v4/DissectV1";
import { BoldThumb } from "./v4/BoldThumb";
import { MascotSheet } from "./v4/Mascot";
import { SceneThumb } from "./v4/SceneThumb";

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
    {/* 기업 해부 썸네일(JJ 2026-09-19 "기존 것과 아예 다르게") — props = computed_info.json */}
    <Still id="DissectThumb" component={DissectThumb as never} width={1080} height={1920} defaultProps={P} />
    {/* 기업 해부 썸네일 v2 — 경제사냥꾼 틀(글자 세로 50% 이상, JJ 9/19 밤) */}
    <Still id="HunterThumb" component={HunterThumb as never} width={1080} height={1920} defaultProps={P} />
    {/* 받은 그림(ChatGPT) 위에 글자만 다시 — 로고 가리기·전망 표시·글자 세로 50%+ */}
    <Still id="OverlayThumb" component={OverlayThumb as never} width={1080} height={1920} defaultProps={P} />
    {/* 정보 영상 썸네일 — 어두운 바탕·초대형 글자·빨간 질문 띠·SVG 그림(JJ 9/19 밤, 사진·로고 없음) */}
    <Still id="BoldThumb" component={BoldThumb as never} width={1080} height={1920} defaultProps={P} />
    <Still id="SceneThumb" component={SceneThumb as never} width={1080} height={1920} defaultProps={{}} />
    <Still id="MascotSheet" component={MascotSheet as never} width={1920} height={1080} defaultProps={{ pick: "kid" }} />
  </>
);
