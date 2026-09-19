/** 누가샀나 캐릭터 초안 (JJ 9/19 밤) — 탐정: 중절모·트렌치코트·돋보기·장부(빨강 = 산 돈, 파랑 = 판 돈).
 * SVG 로 직접 그린다 → 매번 같은 얼굴, 어느 크기에서도 같은 모양, 표정·포즈를 파이프라인이 고른다.
 * kind: kid(꼬마 탐정) | lens(돋보기 머리 '보기') | bear(곰 탐정) · mood: calm|suspect|surprise|found · pose: peer(돋보기를 눈에) | point(돋보기를 내밀어 숫자 위에) */
import React from "react";
import { AbsoluteFill } from "remotion";
import { FONT } from "../tokens";

export type MascotKind = "kid" | "lens" | "bear";
export type Mood = "calm" | "suspect" | "surprise" | "found";
export type Pose = "peer" | "point";

const OUT = "#14161C", CAMEL = "#E0AE62", CAMEL_D = "#B98440", RED = "#E8342C", BLUE = "#2F6BFF", YEL = "#FFD43B";
const SKIN = "#F8D4B4", GLASS = "#DFF1FF", FUR = "#A9744A", FUR_L = "#F0D9BC", WOOD = "#7A5526", PANTS = "#2B303B";
const S = { stroke: OUT, strokeWidth: 8, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

const Hat: React.FC<{ y: number; w?: number; tilt?: number }> = ({ y, w = 1, tilt = -6 }) => (
  <g transform={`rotate(${tilt} 200 ${y})`}>
    <ellipse cx={200} cy={y + 6} rx={128 * w} ry={24} fill={CAMEL_D} {...S} />
    <path d={`M${200 - 76 * w} ${y + 2} C${200 - 82 * w} ${y - 60} ${200 - 54 * w} ${y - 88} 200 ${y - 74} C${200 + 54 * w} ${y - 88} ${200 + 82 * w} ${y - 60} ${200 + 76 * w} ${y + 2} Q200 ${y + 18} ${200 - 76 * w} ${y + 2} Z`} fill={CAMEL_D} {...S} />
    <path d={`M${200 - 78 * w} ${y - 24} Q200 ${y - 8} ${200 + 78 * w} ${y - 24} L${200 + 76 * w} ${y + 2} Q200 ${y + 18} ${200 - 76 * w} ${y + 2} Z`} fill={RED} {...S} strokeWidth={6} />
  </g>
);

/** 돋보기 — 렌즈 가운데 (cx,cy), 손 쪽으로 손잡이 */
const Glass: React.FC<{ cx: number; cy: number; r: number; hx: number; hy: number; eye?: boolean; spark?: boolean; text?: string; textColor?: string }> = ({ cx, cy, r, hx, hy, eye, spark, text, textColor }) => {
  const dx = hx - cx, dy = hy - cy, d = Math.hypot(dx, dy) || 1;
  const rx = cx + (dx / d) * (r + 6), ry = cy + (dy / d) * (r + 6);
  return (
    <g>
      <line x1={rx} y1={ry} x2={hx} y2={hy} stroke={OUT} strokeWidth={26} strokeLinecap="round" />
      <line x1={rx} y1={ry} x2={hx} y2={hy} stroke={WOOD} strokeWidth={14} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={r} fill={text ? "#FFFFFF" : GLASS} fillOpacity={eye ? 0.5 : text ? 0.97 : 0.78} />
      {text ? <text x={cx} y={cy + (r * 1.5 / Math.max(3, text.length)) * 0.36} textAnchor="middle" fontSize={Math.min(r * 0.9, (r * 1.62) / Math.max(1, text.length) * 1.55)} fontWeight={900} fill={textColor ?? OUT} fontFamily={FONT} letterSpacing="-0.04em">{text}</text> : null}
      {eye ? (<><ellipse cx={cx} cy={cy + 3} rx={r * 0.36} ry={r * 0.48} fill={OUT} /><circle cx={cx + r * 0.13} cy={cy - r * 0.14} r={r * 0.15} fill="#FFFFFF" /></>) : null}
      {text ? null : <path d={`M${cx - r * 0.62} ${cy - r * 0.12} A${r * 0.64} ${r * 0.64} 0 0 1 ${cx - r * 0.1} ${cy - r * 0.63}`} fill="none" stroke="#FFFFFF" strokeWidth={6} strokeLinecap="round" opacity={0.9} />}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={OUT} strokeWidth={20} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={YEL} strokeWidth={10} />
      {spark ? [[cx + r + 22, cy - r - 8, 16], [cx + r + 48, cy - r + 30, 9]].map(([x, y, k], i) => (
        <path key={i} d={`M${x} ${y - k} L${x + k * 0.3} ${y - k * 0.3} L${x + k} ${y} L${x + k * 0.3} ${y + k * 0.3} L${x} ${y + k} L${x - k * 0.3} ${y + k * 0.3} L${x - k} ${y} L${x - k * 0.3} ${y - k * 0.3} Z`} fill={YEL} stroke={OUT} strokeWidth={4} strokeLinejoin="round" />
      )) : null}
    </g>
  );
};

const Face: React.FC<{ mood: Mood; bigRight: boolean; bear?: boolean }> = ({ mood, bigRight, bear }) => {
  const eye = (x: number) => mood === "found"
    ? <path d={`M${x - 13} 208 Q${x} 190 ${x + 13} 208`} fill="none" stroke={OUT} strokeWidth={8} strokeLinecap="round" />
    : mood === "surprise"
      ? <g><circle cx={x} cy={203} r={17} fill="#FFFFFF" stroke={OUT} strokeWidth={6} /><circle cx={x} cy={204} r={7.5} fill={OUT} /></g>
      : <g><ellipse cx={x} cy={204} rx={10} ry={13.5} fill={OUT} /><circle cx={x + 3.5} cy={198.5} r={4.2} fill="#FFFFFF" /></g>;
  const my = bear ? 250 : 242;
  return (
    <g>
      <ellipse cx={146} cy={230} rx={14} ry={8.5} fill="#F59C93" opacity={0.75} />
      <ellipse cx={254} cy={230} rx={14} ry={8.5} fill="#F59C93" opacity={0.75} />
      {eye(166)}
      {bigRight ? null : eye(234)}
      {mood === "suspect" ? <path d="M148 176 L186 186" stroke={OUT} strokeWidth={8} strokeLinecap="round" /> : null}
      {mood === "suspect" && !bigRight ? <path d="M216 180 L252 170" stroke={OUT} strokeWidth={8} strokeLinecap="round" /> : null}
      {mood === "surprise" ? (<><path d="M150 172 Q166 162 182 172" fill="none" stroke={OUT} strokeWidth={7} strokeLinecap="round" />{bigRight ? null : <path d="M218 172 Q234 162 250 172" fill="none" stroke={OUT} strokeWidth={7} strokeLinecap="round" />}</>) : null}
      {bear ? (<><ellipse cx={200} cy={238} rx={36} ry={27} fill={FUR_L} stroke={OUT} strokeWidth={6} /><ellipse cx={200} cy={226} rx={12} ry={8.5} fill={OUT} /></>) : null}
      {mood === "calm" ? <path d={`M186 ${my} Q200 ${my + 12} 214 ${my}`} fill="none" stroke={OUT} strokeWidth={7} strokeLinecap="round" /> : null}
      {mood === "suspect" ? <path d={`M188 ${my + 6} Q200 ${my + 2} 213 ${my - 2}`} fill="none" stroke={OUT} strokeWidth={7} strokeLinecap="round" /> : null}
      {mood === "surprise" ? <ellipse cx={200} cy={my + 6} rx={9} ry={12} fill="#7A2E2E" stroke={OUT} strokeWidth={6} /> : null}
      {mood === "found" ? <path d={`M182 ${my - 4} Q200 ${my + 26} 218 ${my - 4} Z`} fill="#7A2E2E" stroke={OUT} strokeWidth={6} strokeLinejoin="round" /> : null}
    </g>
  );
};

export const Mascot: React.FC<{ kind?: MascotKind; mood?: Mood; pose?: Pose; size?: number; sticker?: boolean; flip?: boolean; lensText?: string; lensColor?: string; lensR?: number }> = ({ kind = "kid", mood = "suspect", pose = "peer", size = 400, sticker = true, flip, lensText, lensColor, lensR = 50 }) => {
  const fid = `stk-${kind}-${mood}-${pose}`;
  const hand = kind === "bear" ? FUR : kind === "lens" ? "#FFFFFF" : SKIN;
  const holds = kind !== "lens";                    // 돋보기 머리는 돋보기를 들지 않는다
  const bigRight = holds && pose === "peer";
  const arm = pose === "point" ? { x: 322, y: 288 } : holds ? { x: 298, y: 258 } : { x: 246, y: 284 };
  return (
    <svg width={size} height={size * 1.2} viewBox="0 0 400 480" style={{ overflow: "visible", transform: flip ? "scaleX(-1)" : undefined }}>
      <defs>
        <filter id={fid} x="-15%" y="-15%" width="130%" height="130%">
          <feMorphology in="SourceAlpha" operator="dilate" radius="7" result="d" />
          <feFlood floodColor="#FFFFFF" /><feComposite in2="d" operator="in" result="o" />
          <feMerge><feMergeNode in="o" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <ellipse cx={200} cy={464} rx={112} ry={13} fill="rgba(0,0,0,0.28)" />
      <g filter={sticker ? `url(#${fid})` : undefined}>
        {/* 다리·신발 */}
        <rect x={163} y={400} width={30} height={46} rx={8} fill={PANTS} {...S} />
        <rect x={207} y={400} width={30} height={46} rx={8} fill={PANTS} {...S} />
        <ellipse cx={172} cy={450} rx={27} ry={13} fill="#3B2A20" {...S} />
        <ellipse cx={228} cy={450} rx={27} ry={13} fill="#3B2A20" {...S} />
        {/* 코트 */}
        <path d="M138 300 Q200 274 262 300 L288 408 Q200 428 112 408 Z" fill={CAMEL} {...S} />
        <path d="M178 286 L222 286 L200 332 Z" fill="#FFFFFF" {...S} strokeWidth={6} />
        <path d="M193 290 L207 290 L205 303 L212 328 L200 340 L188 328 L195 303 Z" fill={BLUE} {...S} strokeWidth={5} />
        <path d="M200 338 L200 418" stroke={OUT} strokeWidth={5} strokeLinecap="round" />
        <path d="M120 358 Q200 376 280 358 L283 378 Q200 396 117 378 Z" fill={CAMEL_D} {...S} strokeWidth={6} />
        <rect x={188} y={364} width={24} height={20} rx={4} fill={YEL} {...S} strokeWidth={5} />
        {[[176, 346], [224, 346], [174, 404], [226, 404]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={5.5} fill={WOOD} stroke={OUT} strokeWidth={3} />)}
        {/* 왼팔 + 장부(빨강 = 산 돈, 파랑 = 판 돈) */}
        <line x1={144} y1={314} x2={126} y2={372} stroke={OUT} strokeWidth={42} strokeLinecap="round" />
        <line x1={144} y1={314} x2={126} y2={372} stroke={CAMEL} strokeWidth={28} strokeLinecap="round" />
        <g transform="rotate(-10 96 392)">
          <rect x={58} y={346} width={76} height={94} rx={10} fill="#1B2232" {...S} />
          {([[70, 26, 1], [84, 38, 1], [98, 24, 0], [112, 18, 1]] as const).map(([x, h, up], i) => (
            <rect key={i} x={x} y={up ? 398 - h : 398} width={9} height={h} rx={2} fill={up ? RED : BLUE} />
          ))}
          <line x1={66} y1={398} x2={126} y2={398} stroke="#FFFFFF" strokeWidth={2} opacity={0.7} />
        </g>
        <circle cx={124} cy={384} r={14} fill={hand} {...S} strokeWidth={6} />
        {/* 머리 */}
        {kind === "bear" ? (<>
          <circle cx={112} cy={98} r={25} fill={FUR} {...S} /><circle cx={112} cy={98} r={11} fill={FUR_L} />
          <circle cx={288} cy={98} r={25} fill={FUR} {...S} /><circle cx={288} cy={98} r={11} fill={FUR_L} />
        </>) : null}
        {kind === "kid" ? (<><circle cx={110} cy={204} r={14} fill={SKIN} {...S} strokeWidth={6} /><circle cx={290} cy={204} r={14} fill={SKIN} {...S} strokeWidth={6} /></>) : null}
        {kind === "lens" ? (<>
          <circle cx={200} cy={192} r={92} fill={GLASS} />
          <path d="M136 176 A70 70 0 0 1 176 126" fill="none" stroke="#FFFFFF" strokeWidth={9} strokeLinecap="round" />
          <circle cx={200} cy={192} r={92} fill="none" stroke={OUT} strokeWidth={26} />
          <circle cx={200} cy={192} r={92} fill="none" stroke={YEL} strokeWidth={14} />
        </>) : <circle cx={200} cy={192} r={90} fill={kind === "bear" ? FUR : SKIN} {...S} />}
        {kind === "kid" ? (<><path d="M112 168 Q116 140 134 138 L138 176 Q124 186 114 180 Z" fill="#3B2A20" /><path d="M288 168 Q284 140 266 138 L262 176 Q276 186 286 180 Z" fill="#3B2A20" /></>) : null}
        <Face mood={mood} bigRight={bigRight} bear={kind === "bear"} />
        <Hat y={kind === "lens" ? 112 : 124} w={kind === "lens" ? 0.92 : 1} />
        {/* 코트 깃 — 얼굴 아래를 살짝 덮는다 */}
        <path d="M148 296 L178 268 L198 322 Z" fill={CAMEL} {...S} strokeWidth={6} />
        <path d="M252 296 L222 268 L202 322 Z" fill={CAMEL} {...S} strokeWidth={6} />
        {/* 오른팔 + 돋보기 */}
        <line x1={258} y1={314} x2={arm.x - 6} y2={arm.y + 8} stroke={OUT} strokeWidth={42} strokeLinecap="round" />
        <line x1={258} y1={314} x2={arm.x - 6} y2={arm.y + 8} stroke={CAMEL} strokeWidth={28} strokeLinecap="round" />
        {holds ? (pose === "peer"
          ? <Glass cx={234} cy={204} r={43} hx={arm.x} hy={arm.y} eye />
          : <Glass cx={352 + (lensR - 50) * 0.75} cy={214 - (lensR - 50) * 0.6} r={lensR} hx={arm.x} hy={arm.y} spark={mood === "found"} text={lensText} textColor={lensColor === "blue" ? BLUE : lensColor === "red" ? RED : undefined} />) : null}
        <circle cx={arm.x} cy={arm.y} r={15} fill={hand} {...S} strokeWidth={6} />
        {!holds && pose === "point" ? <line x1={arm.x + 8} y1={arm.y - 8} x2={arm.x + 30} y2={arm.y - 26} stroke={OUT} strokeWidth={13} strokeLinecap="round" /> : null}
        {!holds && pose === "point" ? <line x1={arm.x + 8} y1={arm.y - 8} x2={arm.x + 29} y2={arm.y - 25} stroke="#FFFFFF" strokeWidth={6} strokeLinecap="round" /> : null}
        {mood === "surprise" ? <path d="M318 120 Q330 142 318 152 Q306 142 318 120 Z" fill="#8FD3FF" stroke={OUT} strokeWidth={4} /> : null}
      </g>
    </svg>
  );
};

/* ───────── 초안 시트 (1920×1080) ───────── */
const CANDS: { kind: MascotKind; name: string; note: string }[] = [
  { kind: "kid", name: "가. 꼬마 탐정", note: "사람 · 돋보기로 한쪽 눈이 커 보이는 게 표식" },
  { kind: "lens", name: "나. 돋보기 머리 ‘보기’", note: "물건 + 모자 (경제사냥꾼 방식) · 가장 단순한 실루엣" },
  { kind: "bear", name: "다. 곰 탐정", note: "Threads @bearpicks 와 이어짐 · 곰 = 하락장 뜻 주의" },
];
const MOODS: { mood: Mood; pose: Pose; label: string; when: string }[] = [
  { mood: "calm", pose: "peer", label: "차분", when: "평소" }, { mood: "suspect", pose: "peer", label: "의심", when: "그런데?" },
  { mood: "surprise", pose: "point", label: "놀람", when: "반전 숫자" }, { mood: "found", pose: "point", label: "발견", when: "답" },
];

export const MascotSheet: React.FC<{ pick?: MascotKind }> = ({ pick = "kid" }) => (
  <AbsoluteFill style={{ fontFamily: FONT, background: "#0B1222", color: "#FFFFFF" }}>
    <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.04) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,0.04) 2px, transparent 2px)", backgroundSize: "60px 60px" }} />
    <div style={{ position: "absolute", left: 60, top: 36, fontSize: 46, fontWeight: 900 }}>누가샀나 캐릭터 초안 — 탐정 <span style={{ fontSize: 28, fontWeight: 700, color: "#AEB8CC", marginLeft: 16 }}>중절모(빨간 띠) · 트렌치코트 · 돋보기 · 장부(빨강 = 산 돈, 파랑 = 판 돈)</span></div>
    {CANDS.map((c, i) => (
      <div key={c.kind} style={{ position: "absolute", left: 60 + i * 440, top: 120, width: 410, height: 640, borderRadius: 24, overflow: "hidden", border: c.kind === pick ? `5px solid ${YEL}` : "2px solid rgba(255,255,255,0.14)", background: "#111A2E" }}>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 150, background: "#F4EFE6" }} />
        <div style={{ position: "absolute", left: 35, top: 16 }}><Mascot kind={c.kind} mood="suspect" pose="peer" size={340} /></div>
        <div style={{ position: "absolute", left: 20, top: 424, fontSize: 36, fontWeight: 900, lineHeight: 1.2 }}>{c.name}</div>
        <div style={{ position: "absolute", left: 22, right: 150, bottom: 22, fontSize: 23, fontWeight: 700, color: "#3A3F4B", lineHeight: 1.35, wordBreak: "keep-all" }}>{c.note}</div>
        <div style={{ position: "absolute", right: 14, bottom: 6 }}><Mascot kind={c.kind} mood="found" pose="point" size={112} /></div>
      </div>
    ))}
    {/* 작은 크기에서도 읽히나 — 프로필 */}
    <div style={{ position: "absolute", left: 1400, top: 120, width: 460, height: 640, borderRadius: 24, border: "2px solid rgba(255,255,255,0.14)", background: "#111A2E" }}>
      <div style={{ position: "absolute", left: 24, top: 18, fontSize: 30, fontWeight: 900 }}>프로필 · 작은 크기</div>
      {CANDS.map((c, i) => (
        <div key={c.kind} style={{ position: "absolute", left: 24, top: 80 + i * 184, display: "flex", alignItems: "center", gap: 22 }}>
          {[160, 84, 44].map((d) => (
            <div key={d} style={{ width: d, height: d, borderRadius: d, overflow: "hidden", background: "#1D2A4A", border: "3px solid rgba(255,255,255,0.85)", position: "relative", flex: "0 0 auto" }}>
              <div style={{ position: "absolute", left: -d * 0.23, top: -d * 0.04 }}><Mascot kind={c.kind} mood="calm" pose="peer" size={d * 1.46} sticker={false} /></div>
            </div>
          ))}
        </div>
      ))}
    </div>
    {/* 표정 — 밝은 종이 바탕(기업 해부 화면) */}
    <div style={{ position: "absolute", left: 60, right: 60, top: 790, height: 262, borderRadius: 24, background: "#F4EFE6" }}>
      <div style={{ position: "absolute", left: 28, top: 16, fontSize: 28, fontWeight: 900, color: "#14161C" }}>표정 4 · 포즈 2</div>
      {MOODS.map((m, i) => (
        <div key={m.mood} style={{ position: "absolute", left: 300 + i * 390, top: 6 }}>
          <Mascot kind={pick} mood={m.mood} pose={m.pose} size={200} />
          <div style={{ position: "absolute", left: 232, top: 150, color: "#14161C", whiteSpace: "nowrap" }}><div style={{ fontSize: 32, fontWeight: 900 }}>{m.label}</div><div style={{ fontSize: 24, fontWeight: 700, color: "#6B6257" }}>{m.when}</div></div>
        </div>
      ))}
    </div>
  </AbsoluteFill>
);
