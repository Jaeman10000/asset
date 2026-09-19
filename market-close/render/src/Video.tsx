import React, { useEffect, useState } from "react";
import { AbsoluteFill, Audio, Sequence, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { S0, S1, S2, S3, S4, S5, S6 } from "./Scenes";
import { U0, U1, U2, U3, U4, U5 } from "./ScenesUS";
import { S0V4, S2V4, S3V4, S4V4, S5V4, S6V4 } from "./v4/ScenesV4";
import { WEEKLY_COMP } from "./v4/WeeklyV4";
import { WEEKLY2_COMP } from "./v4/WeeklyV5";
import { USW_COMP } from "./v4/WeeklyUSV4";
import { NOTICE_COMP } from "./v4/NoticeV4";
import { INFO_COMP } from "./v4/InfoV1";
import { HUNTER_COMP } from "./v4/HunterV4";
import { BRIEF_COMP } from "./v4/BriefV4";
import { C, fontCss } from "./tokens";
import type { Props } from "./types";

export const useFonts = () => {
  const [h] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const css = fontCss.replace("FONT_REG", staticFile("fonts/Pretendard-Regular.woff2")).replace("FONT_SEMI", staticFile("fonts/Pretendard-SemiBold.woff2"))
      .replace("FONT_XB", staticFile("fonts/Pretendard-ExtraBold.woff2")).replace("FONT_BLK", staticFile("fonts/Pretendard-Black.woff2"));
    const el = document.createElement("style"); el.textContent = css; document.head.appendChild(el);
    Promise.all([document.fonts.load("400 40px Pretendard"), document.fonts.load("600 40px Pretendard"), document.fonts.load("800 40px Pretendard"), document.fonts.load("900 40px Pretendard")])
      .then(() => continueRender(h))
      .catch(() => continueRender(h));
  }, [h]);
};

const comp: Record<string, React.FC<{ p: Props; sub: string; cues?: { start: number; end: number; text: string }[] }>> = { s0: S0, s1: S1, s2: S2, s3: S3, s4: S4, s5: S5, s6: S6,
  u0: U0 as never, u1: U1 as never, u2: U2 as never, u3: U3 as never, u4: U4 as never, u5: U5 as never };

// v4 화면(2026-09-11 JJ 시안): A+ 형식이고 visual이 legacy가 아니면 s0·s2·s3·s5·s6을 v4로(s4 이슈는 기존 화면)
const compV4: Record<string, React.FC<{ p: Props; sub: string; cues?: { start: number; end: number; text: string }[] }>> = { s0: S0V4, s2: S2V4, s3: S3V4, s4: S4V4, s5: S5V4, s6: S6V4 };

/** 초보자용 용어 풀이 — 풀이 문장이 읽히는 동안만 자막 위에 표시 */
const Glossary: React.FC<{ g: { term: string; text: string }; cues?: { start: number; end: number; text: string }[] }> = ({ g, cues }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const t = f / fps;
  const cue = cues?.find((c) => c.text.includes(g.text.slice(0, 12)));
  const show = cue ? t >= cue.start - 0.2 && t <= cue.end + 0.8 : true;
  if (!show) return null;
  return (
    <div style={{ position: "absolute", left: 96, right: 96, bottom: 330, padding: "18px 24px", border: `2px solid ${C.line}`, borderRadius: 14, background: "#1C1C1F", fontFamily: "Pretendard, sans-serif" }}>
      <div style={{ fontSize: 28, color: C.sub, letterSpacing: "0.02em" }}>용어 · {g.term}</div>
      <div style={{ fontSize: 34, color: C.text, lineHeight: 1.4, marginTop: 6, wordBreak: "keep-all" }}>{g.text}</div>
    </div>
  );
};

/** 배경음 — 인트로 1초 페이드인, 끝 2초 페이드아웃. 나레이션이 주인공이라 기본 0.12. */
const Bgm: React.FC<{ file: string; volume: number; total: number }> = ({ file, volume, total }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const v = volume * interpolate(f, [0, fps * 1, total - fps * 2, total], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <Audio src={staticFile(file)} volume={v} loop />;
};

export const Video: React.FC<Props> = (p) => {
  useFonts();
  const fps = p.fps ?? 30;
  const bgm = (p as unknown as { bgm?: { file: string; volume: number } }).bgm;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {bgm ? <Bgm file={bgm.file} volume={bgm.volume} total={p.total_frames ?? 30 * 45} /> : null}
      {p.scenes.map((sc) => {
        const from = Math.round((sc.start ?? 0) * fps);
        const dur = sc.frames ?? Math.round((sc.sec ?? sc.min) * fps);
        const v4 = (p as unknown as { format?: string; visual?: string }).format === "aplus" && (p as unknown as { visual?: string }).visual !== "legacy";
        const fmt = (p as unknown as { format?: string }).format;
        const hunter = fmt === "hunter";   // 헌터 포맷(docs/HUNTER_FORMAT_DESIGN.md §6.2): s0 s1 s2 s3a s3b s3c s4 s5 s6 → HunterV4
        const brief = fmt === "brief";     // 수급 브리핑(docs/BRIEF_FORMAT_DESIGN.md §3): 같은 9장면, s0·s1·s2·s6 은 헌터 화면, s3a·s3b·s3c·s4·s5 는 BriefV4
        const NOTICE: Record<string, typeof comp[string]> = { ...(NOTICE_COMP as Record<string, typeof comp[string]>), n6: S6V4 };
        const INFO: Record<string, typeof comp[string]> = INFO_COMP as Record<string, typeof comp[string]>;   // i0~i6 = 생활형 정보 쇼츠(JJ 2026-09-19)   // n0~n6 = 제도 안내편(끝 멘트 화면은 평일과 같은 것)
        const Sc = ((p as unknown as { weekly_v?: number }).weekly_v === 2 ? WEEKLY2_COMP[sc.id] : WEEKLY_COMP[sc.id]) || (USW_COMP as Record<string, typeof comp[string]>)[sc.id] || NOTICE[sc.id] || INFO[sc.id] || (brief && BRIEF_COMP[sc.id]) || (hunter && HUNTER_COMP[sc.id]) || (v4 && compV4[sc.id]) || comp[sc.id];   // w0~w6 = 주간 결산(토)
        return (
          <Sequence key={sc.id} from={from} durationInFrames={dur} name={sc.id}>
            {Sc ? <Sc p={p} sub={sc.sub} cues={(sc as unknown as { cues?: { start: number; end: number; text: string }[] }).cues} /> : null}
            {(p as unknown as { glossary?: { scene: string; term: string; text: string } | null }).glossary?.scene === sc.id ? (
              <Glossary g={(p as unknown as { glossary: { scene: string; term: string; text: string } }).glossary} cues={(sc as unknown as { cues?: { start: number; end: number; text: string }[] }).cues} />
            ) : null}
            {/* 문장별 조각이 있으면 제자리에 놓는다 — 조각 사이가 그대로 쉼이 된다(말이 끝나고 받아들일 틈) */}
            {(sc as unknown as { audio_parts?: { file: string; at: number }[] }).audio_parts?.length
              ? (sc as unknown as { audio_parts: { file: string; at: number }[] }).audio_parts.map((a, ai) => (
                  <Sequence key={a.file} from={Math.round(a.at * fps)} name={`${sc.id}-${ai}`}>
                    <Audio src={staticFile(a.file)} />
                  </Sequence>
                ))
              : sc.audio ? <Audio src={staticFile(sc.audio)} /> : null}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
