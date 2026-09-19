/** 정보 영상 썸네일 — 어두운 바탕 + 초대형 글자 + 빨간 질문 띠 + 가운데 그림(JJ 9/19 밤: ChatGPT·Gemini 판 느낌, 아래 카드 없이).
 * 사진·로고 없이 SVG 로만 그린다(라이선스·가짜 로고 문제 없음). props.info.thumbB = {tag, lines:[{t,size,color}], banner, visual:"rates"|"power", stats:[{label,value,color}]} */
import React from "react";
import { AbsoluteFill } from "remotion";
import type { Props } from "../types";
import { FONT } from "../tokens";

type TB = { bars?: number[]; tag?: string; lines?: { t: string; size?: number; color?: string }[]; banner?: string; visual?: "rates" | "power";
  stats?: { label: string; value: string; color?: string }[]; chip?: string; series?: number[] };
const YEL = "#FFD43B", RED = "#E8342C", BLUE = "#2F6BFF";
const col = (c?: string) => (c === "yellow" ? YEL : c === "red" ? "#FF5A4E" : c === "blue" ? "#5B8CFF" : "#FFFFFF");

const Flag: React.FC<{ kind: "us" | "jp" | "kr"; w: number; h: number }> = ({ kind, w, h }) => {
  if (kind === "jp") return (<svg width={w} height={h}><rect width={w} height={h} rx={14} fill="#FFFFFF" /><circle cx={w / 2} cy={h / 2} r={h * 0.3} fill="#D7263D" /></svg>);
  if (kind === "kr") return (
    <svg width={w} height={h}>
      <rect width={w} height={h} rx={14} fill="#FFFFFF" />
      <path d={`M ${w / 2 - h * 0.25} ${h / 2} A ${h * 0.25} ${h * 0.25} 0 0 1 ${w / 2 + h * 0.25} ${h / 2} Z`} fill="#CD2E3A" />
      <path d={`M ${w / 2 - h * 0.25} ${h / 2} A ${h * 0.25} ${h * 0.25} 0 0 0 ${w / 2 + h * 0.25} ${h / 2} Z`} fill="#0047A0" />
      {[[0.14, 0.2], [0.86, 0.2], [0.14, 0.8], [0.86, 0.8]].map(([x, y], i) => (
        <g key={i} transform={`translate(${w * x} ${h * y}) rotate(${i === 0 || i === 3 ? -34 : 34})`}>
          {[-12, 0, 12].map((dy, j) => ([[1, 1, 1], [0, 1, 0], [1, 0, 1], [0, 0, 0]][i][j]
            ? <rect key={dy} x={-22} y={dy - 4} width={44} height={8} fill="#111" />
            : <g key={dy}><rect x={-22} y={dy - 4} width={19} height={8} fill="#111" /><rect x={3} y={dy - 4} width={19} height={8} fill="#111" /></g>))}
        </g>
      ))}
    </svg>
  );
  return (
    <svg width={w} height={h}>
      <rect width={w} height={h} rx={14} fill="#FFFFFF" />
      {Array.from({ length: 7 }).map((_, i) => <rect key={i} x={0} y={(h / 13) * i * 2} width={w} height={h / 13} fill="#B22234" />)}
      <rect x={0} y={0} width={w * 0.44} height={h * 0.54} fill="#3C3B6E" />
      {Array.from({ length: 12 }).map((_, i) => <circle key={i} cx={w * 0.06 + (i % 4) * w * 0.1} cy={h * 0.1 + Math.floor(i / 4) * h * 0.16} r={5} fill="#FFFFFF" />)}
    </svg>
  );
};

const Pylon: React.FC = () => (
  <svg width={420} height={560} viewBox="0 0 420 560">
    <g stroke="#9FB3D9" strokeWidth={10} fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M210 20 L120 540 M210 20 L300 540 M150 360 L270 360 M135 450 L285 450 M170 250 L250 250 M185 160 L235 160" />
      <path d="M40 120 L380 120 M70 200 L350 200 M150 360 L270 450 M270 360 L150 450 M170 250 L270 360 M250 250 L150 360" />
      <path d="M40 120 L40 150 M380 120 L380 150 M70 200 L70 230 M350 200 L350 230" />
    </g>
    <path d="M232 70 L178 230 L226 230 L190 380 L300 190 L246 190 L284 70 Z" fill={YEL} stroke="#000" strokeWidth={8} strokeLinejoin="round" />
  </svg>
);

export const BoldThumb: React.FC<Props> = (p) => {
  const th = ((p as unknown as { info?: { thumbB?: TB } }).info?.thumbB ?? {}) as TB;
  const lines = th.lines ?? [];
  const series = th.series ?? [];
  const lo = Math.min(...series, 0), hi = Math.max(...series, 1);
  const SW = 900, SH = 330;
  const pts = series.map((v, i) => `${(i / Math.max(1, series.length - 1)) * SW},${SH - ((v - lo) / Math.max(1e-9, hi - lo)) * SH}`).join(" ");
  return (
    <AbsoluteFill style={{ fontFamily: FONT, background: "radial-gradient(ellipse at 50% 18%, #20345C 0%, #0B1222 55%, #05070D 100%)" }}>
      <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.04) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,0.04) 2px, transparent 2px)", backgroundSize: "60px 60px" }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 85%, rgba(232,52,44,0.28) 0%, rgba(0,0,0,0) 60%)" }} />
      {th.tag ? <div style={{ position: "absolute", left: 50, top: 56, fontSize: 56, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "8px 26px", borderRadius: 10, transform: "rotate(-2deg)", boxShadow: "0 8px 22px rgba(0,0,0,0.5)" }}>{th.tag}</div> : null}
      <div style={{ position: "absolute", right: 54, top: 70, fontSize: 48, fontWeight: 900, color: "#FFFFFF" }}>누가샀나<span style={{ color: RED }}>.</span></div>
      <div style={{ position: "absolute", left: 30, right: 30, top: 190, textAlign: "center" }}>
        {lines.map((l, i) => {
          const sz = l.size ?? 170;
          return (
            <div key={i} style={{ fontSize: sz, fontWeight: 900, lineHeight: 1.04, letterSpacing: "-0.045em", color: col(l.color), whiteSpace: "nowrap",
              WebkitTextStroke: `${Math.round(sz / 12)}px #000`, paintOrder: "stroke fill", textShadow: "0 12px 30px rgba(0,0,0,0.85)" }}>{l.t}</div>
          );
        })}
      </div>
      {th.banner ? (
        <div style={{ position: "absolute", left: 60, right: 60, top: 590, display: "flex", justifyContent: "center" }}>
          <div style={{ fontSize: 64, fontWeight: 900, color: "#FFFFFF", background: RED, padding: "12px 34px", borderRadius: 12, transform: "rotate(-1.5deg)", boxShadow: "0 10px 26px rgba(0,0,0,0.55)", whiteSpace: "nowrap" }}>{th.banner}</div>
        </div>
      ) : null}
      {th.visual === "rates" ? (
        <>
          <div style={{ position: "absolute", left: 60, right: 60, top: 760, display: "flex", justifyContent: "space-between" }}>
            {([["us", "미국", "4%"], ["jp", "일본", "1.25%"], ["kr", "한국", "3%"]] as const).map(([k, n, v]) => (
              <div key={k} style={{ width: 300, textAlign: "center" }}>
                <div style={{ borderRadius: 16, overflow: "hidden", boxShadow: "0 12px 28px rgba(0,0,0,0.6)", border: "4px solid rgba(255,255,255,0.85)", width: 292, height: 196, margin: "0 auto" }}><Flag kind={k} w={284} h={188} /></div>
                <div style={{ fontSize: 50, fontWeight: 900, color: "#FFFFFF", marginTop: 16 }}>{n}</div>
                <div style={{ fontSize: 70, fontWeight: 900, color: "#FF5A4E", lineHeight: 1.05, WebkitTextStroke: "6px #000", paintOrder: "stroke fill", whiteSpace: "nowrap" }}>▲{v}</div>
              </div>
            ))}
          </div>
          <div style={{ position: "absolute", left: 90, right: 90, top: 1130, height: 330, display: "flex", gap: 22, alignItems: "flex-start" }}>
            {(th.bars ?? []).map((v, i, arr) => {
              const mx = Math.max(1e-9, ...arr.map((x) => Math.abs(x)));
              const hh = (Math.abs(v) / mx) * 300;
              return <div key={i} style={{ flex: 1, height: hh, background: v < 0 ? BLUE : RED, borderRadius: "0 0 10px 10px", boxShadow: `0 0 20px ${v < 0 ? BLUE : RED}99` }} />;
            })}
          </div>
          <div style={{ position: "absolute", left: 90, right: 90, top: 1126, height: 5, background: "rgba(255,255,255,0.7)" }} />
        </>
      ) : null}
      {th.visual === "power" ? (
        <>
          <div style={{ position: "absolute", left: 60, top: 740 }}><Pylon /></div>
          <svg width={520} height={420} style={{ position: "absolute", left: 500, top: 820, overflow: "visible" }}>
            <polyline points={pts.split(" ").map((xy) => { const [x, y] = xy.split(",").map(Number); return `${(x / SW) * 500},${(y / SH) * 380}`; }).join(" ")} fill="none" stroke={BLUE} strokeWidth={14} strokeLinejoin="round" strokeLinecap="round" />
            <text x={0} y={-16} fontSize={48} fontWeight={900} fill="#FFFFFF" stroke="#000" strokeWidth={10} paintOrder="stroke" fontFamily={FONT}>67,900원</text>
            <text x={500} y={((SH - ((series[series.length - 1] - lo) / Math.max(1e-9, hi - lo)) * SH) / SH) * 380 + 70} textAnchor="end" fontSize={56} fontWeight={900} fill="#5B8CFF" stroke="#000" strokeWidth={10} paintOrder="stroke" fontFamily={FONT}>30,900원</text>
          </svg>
        </>
      ) : null}
      {th.stats?.length ? (
        <div style={{ position: "absolute", left: 60, right: 60, top: 1330, display: "flex", gap: 24, justifyContent: "center" }}>
          {th.stats.map((s, i) => (
            <div key={i} style={{ flex: 1, textAlign: "center", background: "rgba(5,7,13,0.75)", border: `4px solid ${col(s.color)}`, borderRadius: 18, padding: "14px 10px" }}>
              <div style={{ fontSize: 40, fontWeight: 900, color: "#E6EAF2" }}>{s.label}</div>
              <div style={{ fontSize: 72, fontWeight: 900, color: col(s.color), lineHeight: 1.05, whiteSpace: "nowrap" }}>{s.value}</div>
            </div>
          ))}
        </div>
      ) : null}
      {th.chip ? <div style={{ position: "absolute", left: 60, right: 60, top: 1500, textAlign: "center" }}><span style={{ fontSize: 58, fontWeight: 900, color: "#FFFFFF", background: "rgba(232,52,44,0.9)", padding: "10px 28px", borderRadius: 12 }}>{th.chip}</span></div> : null}
    </AbsoluteFill>
  );
};
