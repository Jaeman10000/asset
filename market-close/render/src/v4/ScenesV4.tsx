/** v4 화면(2026-09-11 JJ 시안): 야간 도시·시세·칩 배경 + 굵은 글자 + 빛나는 카드. A+ 형식 전용.
 * 장면 단계는 말(큐)에 맞춘다: 질문은 질문만, 답은 이름과 숫자만 크게. 숫자는 전부 props의 실제 값.
 * 색: 한국식 — 빨강 = 순매수·상승, 파랑 = 순매도·하락. 노랑 = 질문. */
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { FONT, FOOTER, fmtEok, fmtIdx } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";

const ease = Easing.out(Easing.cubic);
export const RED = "#FF4D4D";
export const BLUE = "#3D7BFF";
export const YEL = "#FFD84D";
export const GREEN = "#2FD27A";
type Tone = "up" | "down" | "neutral";
const toneOf = (v?: number | null): Tone => (v == null || v === 0 ? "neutral" : v > 0 ? "up" : "down");
const colOf = (v?: number | null) => (v == null || v === 0 ? "#E6E6E3" : v > 0 ? RED : BLUE);

type Ap = {
  format?: string; ep?: number | null; hook_parts?: string[];
  protagonist?: { name: string; amount: number; sold: boolean } | null;
  contrast?: { kind: string; short: string; text?: string; line?: number | null } | null;
  check?: { verdict?: { kind: string; theme: string; n?: number | null; ok: boolean; amount?: number | null; sign?: number | null; when?: string } | null; record?: { n: number; k: number } | null; next_q: string; next_day: string } | null;
  s2_marks?: { answer?: string | null; counter?: string | null; bars?: string | null; snap?: number | null; prev?: number | null } | null;
  others_top?: { name: string; v: number; buyback: boolean }[] | null;
  s3_story?: { lead?: { theme: string; t: number; who: string; names: string[] } | null } | null;
  inv_streak?: Record<string, { streak: number; turned_after: number }>;
  intraday?: { at?: string; snap?: Record<string, number | null> } | null;
};
const ap = (p: Props) => p as unknown as Ap & Props;
const KEY: Record<string, string> = { 개인: "indiv", 외국인: "foreign", 기관: "inst", 기타법인: "others" };
const daysKo = (n?: number | null) => (n === 2 ? "이틀째" : n === 3 ? "사흘째" : n === 4 ? "나흘째" : n === 5 ? "닷새째" : n ? `${n}일째` : "");

/** '2.5조' / '4,600억' — 화면 큰 숫자(말과 같은 반올림) */
const short = (v: number) => {
  const a = Math.abs(v);
  if (a >= 10000) return `${(Math.round(a / 1000) / 10).toFixed(1).replace(/\.0$/, "")}조`;
  return `${(a >= 1000 ? Math.round(a / 100) * 100 : Math.round(a / 10) * 10).toLocaleString("ko-KR")}억`;   // 말(won)과 같은 반올림: 1,000억 미만은 10억 단위
};
const sgn = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");

export const useT = () => { const f = useCurrentFrame(); const { fps } = useVideoConfig(); return { f, fps, t: f / fps }; };

/** 배경: 색조별로 미리 구운 그림(public/bg ← src/v4/Bg*.tsx, preview/BakeEntry.tsx). 고정 — 매 프레임 SVG는 10분+, 확대·이동·글자 빛번짐(drop-shadow)도 렌더를 2배 늦춰서 뺐다(2026-09-11 측정). */
const BgImg: React.FC<{ name: string; tone?: Tone; dim?: number }> = ({ name, tone = "neutral", dim = 0.15 }) => {
  const { f, fps } = useT();
  const k = interpolate(f, [0, 14 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img src={staticFile(`bg/${name}_${tone}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scale(1.04)" }} />
      <AbsoluteFill style={{ background: `rgba(3,5,10,${dim})` }} />
    </AbsoluteFill>
  );
};
export const BgCity: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="city" {...pr} />;
export const BgMarket: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="market" {...pr} />;
export const BgChip: React.FC<{ tone?: Tone; dim?: number }> = (pr) => <BgImg name="chip" {...pr} />;
export const usePop = () => {
  const { f, fps } = useT();
  return (sec: number, dy = 26) => {
    const x = interpolate(f, [sec * fps, (sec + 0.45) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    return { opacity: x, transform: `translateY(${(1 - x) * dy}px)` } as React.CSSProperties;
  };
};
const curCue = (cues: Cue[] | undefined, t: number) => { const l = cues ?? []; const i = l.filter((c) => t >= c.start).length - 1; return { list: l, i, cur: i >= 0 ? l[i] : undefined }; };

const Grad: React.FC<{ tone: Tone; children: React.ReactNode; style?: React.CSSProperties }> = ({ tone, children, style }) => {
  const g = tone === "down" ? "linear-gradient(180deg,#A8DCFF 0%,#4A8BFF 48%,#2554E6 100%)"
    : tone === "up" ? "linear-gradient(180deg,#FFC2B8 0%,#FF5A4E 46%,#E2242B 100%)" : "linear-gradient(180deg,#FFFFFF 0%,#CFD6E4 100%)";
  const glow = tone === "down" ? "rgba(61,123,255,0.6)" : tone === "up" ? "rgba(255,77,77,0.6)" : "rgba(255,255,255,0.35)";
  return <span style={{ backgroundImage: g, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", ...style }}>{children}</span>;
};

export const Card: React.FC<{ color: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ color, children, style }) => (
  <div style={{ border: `2.5px solid ${color}`, borderRadius: 24, background: "linear-gradient(180deg, rgba(10,14,26,0.86), rgba(6,9,18,0.92))",
    boxShadow: `0 0 34px ${color}66, inset 0 0 22px ${color}22`, padding: "28px 34px", ...style }}>{children}</div>
);

const Logo: React.FC<{ scale?: number }> = ({ scale = 1 }) => (
  <div style={{ transform: `scale(${scale})`, transformOrigin: "left top" }}>
    <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 60, color: "#FFFFFF", transform: "skewX(-10deg)", letterSpacing: "-0.05em", lineHeight: 1, textShadow: "0 3px 16px rgba(0,0,0,0.7)" }}>누가샀나</div>
    <svg width="220" height="24" viewBox="0 0 220 24" style={{ display: "block", marginTop: 2 }}>
      <path d="M3 15 C 46 7, 120 3, 216 8 L 213 14 C 150 11, 90 13, 40 17 C 25 18, 12 20, 5 21 Z" fill="#E8362F" />
      <path d="M40 18 C 90 15, 150 14, 205 13" stroke="#FF6A55" strokeWidth="2" fill="none" opacity="0.6" />
    </svg>
  </div>
);

export const Shell: React.FC<{ p: Props; bg: React.ReactNode; cues?: Cue[]; hideSub?: boolean; badge?: string; children: React.ReactNode }> = ({ p, bg, cues, hideSub, badge, children }) => {
  const { t } = useT();
  const md = p.date_label.split(" ")[0];
  let sub = "";
  if (!hideSub && cues && cues.length) {
    // 겹치면 나중 것 — 0.5초 꼬리 때문에 find 가 앞 자막을 집으면 화면보다 늦는다(JJ 2026-09-21)
    const _on = cues.filter((x) => t >= x.start && t < x.end + 0.5);
    const c = _on.length ? _on[_on.length - 1] : undefined;
    sub = c ? c.text : "";
  }
  return (
    <AbsoluteFill style={{ background: "#05070D", fontFamily: FONT, color: "#FFFFFF", fontVariantNumeric: "tabular-nums" }}>
      {bg}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(3,5,10,0.55) 0%, rgba(3,5,10,0.05) 38%, rgba(3,5,10,0) 60%, rgba(3,5,10,0.75) 100%)" }} />
      <div style={{ position: "absolute", left: 64, top: 64 }}><Logo /></div>
      <div style={{ position: "absolute", right: 64, top: 70, textAlign: "right", fontWeight: 800, lineHeight: 1.15, textShadow: "0 2px 10px rgba(0,0,0,0.7)" }}>
        <div style={{ fontSize: 32, color: "#E6E6E3" }}>{badge ?? (p as unknown as { badge?: string }).badge ?? "국장 마감"}</div>
        <div style={{ fontSize: 44 }}>{md}</div>
      </div>
      {children}
      {sub ? (
        <div style={{ position: "absolute", left: 40, right: 40, bottom: 240, display: "flex", justifyContent: "center" }}>
          <div style={{ background: "rgba(8,10,16,0.9)", border: "2px solid rgba(255,255,255,0.12)", color: "#FFFFFF", fontSize: 42, fontWeight: 700, lineHeight: 1.38, padding: "16px 28px", borderRadius: 18,
            wordBreak: "keep-all", textAlign: "center", boxShadow: "0 10px 28px rgba(0,0,0,0.45)" }}>{sub}</div>
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 52, fontSize: 26, color: "rgba(230,230,227,0.55)", letterSpacing: "0.02em" }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};

/* ───────── s0: 첫 화면(0프레임부터 사실+대비) → 질문 문장부터 질문 + 코스피 카드 ───────── */
export const S0V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const a = ap(p);
  const { t } = useT();
  const pop = usePop();
  const pr = a.protagonist!;
  const [nm, amt, word] = (a.hook_parts?.[0] ?? `${pr.name} ${short(pr.amount)} ${pr.sold ? "순매도" : "순매수"}`).split(" ");
  const ct = a.contrast;
  const chg = p.kospi.chg_pct ?? 0;
  const qc = (cues ?? []).find((c) => /\?$/.test(c.text.trim()));
  const tone: Tone = pr.sold ? "down" : "up";
  if (qc && t >= qc.start) {
    const who = pr.sold ? "누가 샀을까?" : "누가 팔았을까?";
    return (
      <Shell p={p} cues={cues} hideSub bg={<BgMarket tone={toneOf(chg)} dim={0.2} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(qc.start, 30) }}>
          <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.04em", textShadow: "0 6px 30px rgba(0,0,0,0.7)" }}>그럼</div>
          <div style={{ fontSize: 172, fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", color: YEL, textShadow: "0 0 36px rgba(255,216,77,0.45), 0 6px 30px rgba(0,0,0,0.7)", wordBreak: "keep-all" }}>{who}</div>
        </div>
        <div style={{ position: "absolute", left: 64, right: 64, top: 1010, ...pop(qc.start + 0.25) }}>
          <Card color={colOf(chg)} style={{ display: "inline-block", minWidth: 640 }}>
            <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4", letterSpacing: "0.04em" }}>KOSPI</div>
            <div style={{ fontSize: 118, fontWeight: 800, lineHeight: 1.05, marginTop: 6 }}>{fmtIdx(p.kospi.close)}</div>
            <div style={{ fontSize: 64, fontWeight: 800, color: colOf(chg), marginTop: 6 }}>{chg > 0 ? "▲" : chg < 0 ? "▼" : "−"} {Math.abs(chg).toFixed(2)}%</div>
          </Card>
        </div>
      </Shell>
    );
  }
  // 대비 줄: '그런데 코스피는' / '7,000선을 지켰다?'
  const opp = (ct?.text ?? "").startsWith("그런데");
  let big = "", rest = "";
  if (ct && ct.line && ct.kind === "held") { big = `${ct.line.toLocaleString("ko-KR")}선`; rest = "을 지켰다"; }
  else if (ct && ct.line && ct.kind === "regained") { big = `${ct.line.toLocaleString("ko-KR")}선`; rest = "을 되찾았다"; }
  else if (ct && ct.line && ct.kind === "lost") { big = `${ct.line.toLocaleString("ko-KR")}선`; rest = "을 내줬다"; }
  else { big = `${Math.abs(chg).toFixed(2)}%`; rest = chg > 0 ? " 올랐다" : chg < 0 ? " 내렸다" : " 제자리"; }
  // 첫 화면을 말에 맞춰 하나씩 연다. 0프레임에 전부 찍어 두면 이탈이 가장 큰 첫 5초가
  // 완전한 정지 화면이 된다(2026-09-14 점검). 이름 → 금액 → 대비 줄 순서로 켠다.
  const cl0 = cues ?? [];
  const a0 = cl0[0]?.start ?? 0;
  if ((a as unknown as { hook_id?: string }).hook_id === "H07") {
    const turn = cl0.find((c) => /^그런데/.test(c.text.trim()))?.start ?? (cl0[1]?.start ?? a0 + 3);
    const snap = Math.abs((a.intraday?.snap?.[KEY[pr.name] ?? ""] as number | undefined) ?? 0);
    const mult = snap ? Math.round((Math.abs(pr.amount) - snap) / snap) : 0;   // 말과 같은 계산: 더 나온 양 ÷ 오후 2시
    return (
      <Shell p={p} cues={cues} hideSub bg={<BgCity tone={tone} dim={0.15} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 250 }}>
          <div style={{ fontSize: 60, fontWeight: 800, color: "#CFD6E4", ...pop(a0) }}>{pr.name} · 오후 2시까지</div>
          <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.05em", ...pop(a0 + 0.3) }}>{short(snap)}</div>
          <div style={{ marginTop: 60, ...pop(turn) }}>
            <div style={{ fontSize: 60, fontWeight: 800, color: YEL }}>그런데 마지막 한 시간 반에</div>
            <div style={{ fontSize: 196, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.05em", whiteSpace: "nowrap" }}>
              <Grad tone={tone}>{short(Math.abs(pr.amount))}</Grad>
            </div>
            {mult >= 2 ? <div style={{ fontSize: 72, fontWeight: 900, color: YEL, marginTop: 8 }}>오후 2시의 {mult}배</div> : null}
          </div>
        </div>
      </Shell>
    );
  }
  const a1 = cl0.find((c) => /코스피|코스닥|선을|지켰|되찾|내줬/.test(c.text))?.start ?? (cl0[1]?.start ?? a0 + 2.2);
  return (
    <Shell p={p} cues={cues} hideSub bg={<BgCity tone={tone} dim={0.15} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 250 }}>
        <div style={{ fontSize: 196, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.05em", textShadow: "0 8px 34px rgba(0,0,0,0.75)", ...pop(a0) }}>{nm}</div>
        <div style={{ fontSize: 196, fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", whiteSpace: "nowrap", ...pop(a0 + 0.35) }}>
          <Grad tone={tone}>{amt}</Grad><span style={{ textShadow: "0 8px 34px rgba(0,0,0,0.75)" }}> {word.replace("순", "")}</span>
        </div>
        <div style={{ marginTop: 56, ...pop(a1) }}>
          <div style={{ fontSize: 66, fontWeight: 800, lineHeight: 1.2, textShadow: "0 4px 18px rgba(0,0,0,0.8)" }}>{opp ? "그런데 코스피는" : "코스피는"}</div>
          <div style={{ fontSize: 88, fontWeight: 900, lineHeight: 1.15, letterSpacing: "-0.03em", textShadow: "0 4px 18px rgba(0,0,0,0.8)" }}>
            <span style={{ color: YEL }}>{big}</span>{rest}{opp ? "?" : ""}
          </div>
        </div>
      </div>
    </Shell>
  );
};

/* ───────── s2: 답(이름·숫자) → 기타법인 종목(자사주) → 질문 → 오후 2시→마감 카운터 → 나머지 카드 ───────── */
export const S2V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const a = ap(p);
  const { f, fps, t } = useT();
  const pop = usePop();
  const mk = a.s2_marks ?? {};
  const { list, i: ci, cur } = curCue(cues, t);
  const bars = p.investors.bars;
  const pr = a.protagonist!;
  const ansName = mk.answer ?? undefined;
  const ansBar = bars.find((b) => b.name === ansName);
  const idxOf = (pred: (x: string) => boolean) => list.findIndex((c) => pred(c.text.trim()));
  const qIdx = idxOf((x) => /\?$/.test(x));
  const cIdx = mk.counter ? idxOf((x) => x.startsWith(mk.counter as string)) : -1;
  const bIdx = mk.bars ? idxOf((x) => x.startsWith(mk.bars as string)) : -1;
  const firstAfter = [qIdx, cIdx, bIdx].filter((x) => x > 0).sort((x, y) => x - y)[0] ?? list.length;
  const stage = ci < 0 ? "reveal" : bIdx >= 0 && ci >= bIdx ? "bars" : cIdx >= 0 && ci >= cIdx ? "counter" : qIdx >= 0 && ci >= qIdx ? "question" : ci < firstAfter ? "reveal" : "bars";

  if (stage === "reveal" && ansBar && ansBar.v != null) {
    const v = ansBar.v;
    const top = a.others_top ?? [];
    const topIdx = top.length ? idxOf((x) => x.includes(top[0].name)) : -1;
    const showTop = topIdx >= 0 && ci >= topIdx;
    return (
      <Shell p={p} cues={cues} bg={<BgCity tone={toneOf(v)} dim={0.25} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 230 }}>
          <div style={{ fontSize: 58, fontWeight: 800, color: "#E6E6E3", textShadow: "0 3px 14px rgba(0,0,0,0.8)" }}>가장 많이 {v > 0 ? "산" : "판"} 쪽은</div>
          <div style={{ ...pop(0.05, 30), fontSize: 184, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", marginTop: 6, textShadow: "0 8px 34px rgba(0,0,0,0.75)" }}>{ansName}</div>
          <div style={{ ...pop(0.3, 30), fontSize: 200, fontWeight: 900, lineHeight: 1.0, letterSpacing: "-0.05em", marginTop: 4 }}><Grad tone={toneOf(v)}>{sgn(v)}{short(v)}</Grad></div>
          {mk.prev != null ? (
            <div style={{ ...pop(0.6), fontSize: 50, fontWeight: 700, marginTop: 18, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>
              전날에도 <span style={{ color: colOf(mk.prev), fontWeight: 900 }}>{short(mk.prev)}</span> {mk.prev > 0 ? "순매수" : "순매도"}
            </div>
          ) : null}
        </div>
        <div style={{ position: "absolute", left: 64, right: 64, top: 1000 }}>
          {showTop ? (
            <Card color={RED} style={pop(list[topIdx].start)}>
              <div style={{ fontSize: 36, fontWeight: 700, color: "#CFD6E4" }}>{ansName}가 가장 많이 산 종목</div>
              {top.map((x, k) => (
                <div key={x.name} style={{ ...pop(list[topIdx].start + 0.2 + k * 0.25), display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 18 }}>
                  <span style={{ fontSize: 58, fontWeight: 900 }}>{x.name}</span>
                  <span style={{ fontSize: 58, fontWeight: 900, color: RED }}>+{fmtEok(x.v)}</span>
                </div>
              ))}
              {top.some((x) => x.buyback) ? <div style={{ fontSize: 34, color: YEL, fontWeight: 700, marginTop: 16 }}>자사주 매입 진행 중 · 회사가 자기 주식을 사면 기타법인으로 집계</div> : null}
            </Card>
          ) : (
            <Card color={colOf(v)} style={pop(0.5)}>
              <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
                <span style={{ fontSize: 44, fontWeight: 800, whiteSpace: "nowrap" }}>{ansName}</span>
                <div style={{ flex: 1, height: 26, borderRadius: 13, background: `linear-gradient(90deg, ${colOf(v)}, ${colOf(v)}AA)`, boxShadow: `0 0 20px ${colOf(v)}`,
                  transform: `scaleX(${interpolate(f, [0.6 * fps, 1.4 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease })})`, transformOrigin: "left center" }} />
                <span style={{ fontSize: 48, fontWeight: 900, color: colOf(v), whiteSpace: "nowrap" }}>{sgn(v)}{short(v)}</span>
              </div>
            </Card>
          )}
        </div>
      </Shell>
    );
  }
  if (stage === "question" || stage === "counter") {
    const q = list[qIdx >= 0 ? qIdx : Math.max(ci, 0)];
    const qText = (qIdx >= 0 ? list[qIdx].text : "").replace(/^그런데\s*/, "").replace(/요\?$/, "?");
    const m = qText.match(/^(\S+[은는])\s+(.*)$/);
    const head = m ? m[1] : "";
    const body = m ? m[2] : qText;
    const cStart = cIdx >= 0 ? list[cIdx].start : 1e9;
    const cEnd = cIdx >= 0 ? list[cIdx].end : 1e9;
    const k = interpolate(t, [cStart + 0.4, cEnd - 0.2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    const snap = mk.snap ?? null;
    const val = snap != null ? Math.round((snap + (pr.amount - snap) * k) / 10) * 10 : pr.amount;
    const inCounter = stage === "counter" && snap != null;
    return (
      <Shell p={p} cues={cues} hideSub={stage === "question"} bg={<BgCity tone={pr.sold ? "down" : "up"} dim={0.3} />}>
        {qText ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 230, ...(q ? pop(q.start, 30) : {}) }}>
            {head ? <div style={{ fontSize: inCounter ? 84 : 128, fontWeight: 900, lineHeight: 1.1, textShadow: "0 6px 26px rgba(0,0,0,0.8)" }}>{head}</div> : null}
            <div style={{ fontSize: inCounter ? 92 : 132, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: YEL, wordBreak: "keep-all",
              textShadow: "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)" }}>{body}</div>
          </div>
        ) : null}
        {inCounter ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 820 }}>
            <Card color="#8FA7D9" style={{ ...pop(cStart), padding: "22px 32px" }}>
              <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4" }}>오후 2시</div>
              <div style={{ fontSize: 64, fontWeight: 900, marginTop: 4 }}>{(snap ?? 0) < 0 ? "순매도" : "순매수"} <span style={{ color: colOf(snap) }}>{fmtEok(Math.abs(snap!))}</span></div>
            </Card>
            <div style={{ ...pop(cStart + 0.2), fontSize: 64, textAlign: "center", color: "#E6E6E3", margin: "10px 0", lineHeight: 1 }}>↓</div>
            <Card color={colOf(pr.amount)} style={pop(cStart + 0.3)}>
              <div style={{ fontSize: 40, fontWeight: 800, color: colOf(pr.amount) }}>마감</div>
              <div style={{ fontSize: 104, fontWeight: 900, letterSpacing: "-0.04em", whiteSpace: "nowrap", marginTop: 4 }}>
                <Grad tone={toneOf(pr.amount)}>{fmtEok(Math.abs(k >= 1 ? pr.amount : val))}</Grad>
              </div>
              <div style={{ fontSize: 40, fontWeight: 700, color: "#E6E6E3", marginTop: 6, opacity: k >= 1 ? 1 : 0.0 }}>오후 2시보다 {fmtEok(Math.abs(pr.amount - snap!))} 더</div>
            </Card>
          </div>
        ) : null}
      </Shell>
    );
  }
  // 나머지 주체 카드(주인공·답 제외)
  const rest = bars.filter((b) => b.name !== pr.name && b.name !== ansName && b.v != null && Math.abs(b.v) >= 100).slice(0, 3);
  const st = a.inv_streak ?? {};
  const snapAll = a.intraday?.snap ?? {};
  const b0 = bIdx >= 0 ? list[bIdx].start : 0;
  const topB = a.others_top ?? [];
  const topBIdx = topB.length ? idxOf((x) => x.includes(topB[0].name)) : -1;
  const showTopB = topBIdx >= 0 && ci >= topBIdx && ansName !== "기타법인";
  return (
    <Shell p={p} cues={cues} bg={<BgCity tone="neutral" dim={0.35} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 250, display: "flex", flexDirection: "column", gap: 34 }}>
        {showTopB ? (
          <Card color={RED} style={pop(list[topBIdx].start)}>
            <div style={{ fontSize: 40, fontWeight: 800, color: "#CFD6E4" }}>기타법인 <span style={{ color: RED, fontWeight: 900 }}>{fmtEok(bars.find((b) => b.name === "기타법인")?.v ?? 0, true)}</span> · 가장 많이 산 종목</div>
            {topB.map((x, k) => (
              <div key={x.name} style={{ ...pop(list[topBIdx].start + 0.2 + k * 0.25), display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 18 }}>
                <span style={{ fontSize: 62, fontWeight: 900 }}>{x.name}</span>
                <span style={{ fontSize: 62, fontWeight: 900, color: RED }}>+{fmtEok(x.v)}</span>
              </div>
            ))}
            {topB.some((x) => x.buyback) ? <div style={{ fontSize: 36, color: YEL, fontWeight: 700, marginTop: 18 }}>두 회사 모두 자사주 매입 중 · 회사가 자기 주식을 사면 기타법인으로 집계</div> : null}
          </Card>
        ) : null}
        {(showTopB ? rest.filter((b) => b.name !== "기타법인") : rest).map((b, k) => {
          const s = st[KEY[b.name] ?? ""];
          const sTxt = s && Math.abs(s.streak) >= 2 && (s.streak > 0) === ((b.v ?? 0) > 0) ? `${Math.abs(s.streak)}일째 ${s.streak > 0 ? "순매수" : "순매도"}` : "";
          const s14 = snapAll[KEY[b.name] ?? ""];
          return (
            <Card key={b.name} color={k % 2 ? GREEN : colOf(b.v)} style={pop((() => { const i = idxOf((x) => x.includes(b.name)); return i >= 0 ? list[i].start : b0 + k * 0.3; })())}>
              <div style={{ fontSize: 60, fontWeight: 900 }}>{b.name}</div>
              <div style={{ fontSize: 124, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.05, marginTop: 4 }}><Grad tone={toneOf(b.v)}>{sgn(b.v!)}{short(b.v!)}</Grad></div>
              <div style={{ fontSize: 40, fontWeight: 700, color: "#E6E6E3", marginTop: 8 }}>
                {sTxt ? <span style={{ color: colOf(b.v), marginRight: 18 }}>{(b.v ?? 0) > 0 ? "▲" : "▼"} {sTxt}</span> : null}
                {s14 != null && Math.abs(s14) >= 100 ? <span style={{ color: "#B8C2D6" }}>오후 2시 {fmtEok(s14, true)} → 마감</span> : null}
              </div>
            </Card>
          );
        })}
      </div>
    </Shell>
  );
};

/* ───────── s3: 질문 → 테마 공개 + 전날→오늘 카드 ───────── */
export const S3V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const a = ap(p);
  const { f, fps, t } = useT();          // 훅은 조기 return 앞에서 한 번만(React #310 방지)
  const pop = usePop();
  const lead = a.s3_story?.lead;
  const { list, i: ci, cur } = curCue(cues, t);
  if (!lead) return <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" />}>{null}</Shell>;
  const mv = p.moves.find((m) => m.theme === lead.theme);
  const tone = toneOf(lead.t);
  const Bg = lead.theme === "반도체" ? BgChip : BgMarket;
  // 공개 큐: "반도체입니다." / "반도체 한 곳입니다." 둘 다(여는 문장이 T05·T08·D02 로 돌아가므로)
  const rIdx = list.findIndex((c) => c.text.includes(lead.theme) && /입니다\.?$/.test(c.text.trim()));
  // 여는 문장(공개 전) — 질문이든 재정의든 크게 띄운다. 그 전엔 화면이 비어 있었다
  const isQ = cur && (rIdx < 0 || ci < rIdx);
  // 끝의 다리 질문 — 카드를 내리고 질문만 남긴다(S5V4 마무리와 같은 리셋)
  const bridge = rIdx >= 0 && ci > rIdx && cur && /\?$/.test(cur.text.trim()) ? cur : undefined;
  if (bridge) {
    const q = bridge.text.replace(/^그럼\s*/, "").replace(/요\?$/, "?");
    return (
      <Shell p={p} cues={cues} hideSub bg={<Bg tone={tone} dim={0.5} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 360, ...pop(bridge.start, 30), fontSize: 108, fontWeight: 900, lineHeight: 1.18, letterSpacing: "-0.04em",
          color: YEL, wordBreak: "keep-all", textShadow: "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)" }}>{q}</div>
      </Shell>
    );
  }
  if (isQ && cur) {
    const q = cur.text.replace(/^그럼\s*/, "").replace(/요\?$/, "?");
    return (
      <Shell p={p} cues={cues} hideSub bg={<Bg tone={tone} dim={0.3} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(cur.start, 30), fontSize: 132, fontWeight: 900, lineHeight: 1.14, letterSpacing: "-0.04em",
          color: YEL, wordBreak: "keep-all", textShadow: "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)" }}>{q}</div>
      </Shell>
    );
  }
  const r0 = rIdx >= 0 ? list[rIdx].start : 0;
  const cmpIdx = list.findIndex((c, k) => k > rIdx && /전날|합쳐|합친|빠졌|들어왔|커졌/.test(c.text));
  const c0 = cmpIdx >= 0 ? list[cmpIdx].start : r0 + 0.4;
  const c1 = cmpIdx >= 0 ? list[cmpIdx].end : c0 + 3;
  const nmIdx = lead.names && lead.names.length ? list.findIndex((c, k) => k > rIdx && c.text.includes(lead.names[0])) : -1;
  const n0 = nmIdx >= 0 ? list[nmIdx].start : c0 + 0.6;
  const kk = interpolate(f, [(c0 + 0.3) * fps, Math.max((c0 + 0.31) * fps, (c1 - 0.2) * fps)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const nowV = mv && mv.y != null ? mv.y + (lead.t - mv.y) * kk : lead.t;
  return (
    <Shell p={p} cues={cues} bg={<Bg tone={tone} dim={0.25} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 240 }}>
        <div style={{ fontSize: 60, fontWeight: 800, color: "#E6E6E3", textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>가장 큰 돈이 {lead.t < 0 ? "빠진" : "들어간"} 곳은</div>
        <div style={{ ...pop(r0, 34), fontSize: 210, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", marginTop: 8 }}><Grad tone={tone}>{lead.theme}</Grad></div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: 1010 }}>
        <Card color={tone === "down" ? BLUE : RED} style={pop(c0)}>
          <div style={{ fontSize: 44, fontWeight: 800 }}>{lead.theme} {lead.t < 0 ? "순매도" : "순매수"} <span style={{ fontSize: 32, color: "#B8C2D6" }}>(외국인+기관 합산)</span></div>
          {mv && mv.y != null ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 20 }}>
              <div><div style={{ fontSize: 36, color: "#B8C2D6", fontWeight: 700 }}>전날</div><div style={{ fontSize: 76, fontWeight: 900, color: colOf(mv.y) }}>{sgn(mv.y)}{short(mv.y)}</div></div>
              <div style={{ fontSize: 70, color: "#E6E6E3" }}>→</div>
              <div style={{ textAlign: "right" }}><div style={{ fontSize: 36, color: "#B8C2D6", fontWeight: 700 }}>오늘</div><div style={{ fontSize: 96, fontWeight: 900 }}><Grad tone={tone}>{sgn(lead.t)}{short(nowV)}</Grad></div></div>
            </div>
          ) : <div style={{ fontSize: 96, fontWeight: 900, marginTop: 12 }}><Grad tone={tone}>{sgn(lead.t)}{short(lead.t)}</Grad></div>}
          {lead.names && lead.names.length ? <div style={{ fontSize: 40, fontWeight: 700, marginTop: 16, color: "#E6E6E3", ...pop(n0) }}>{lead.names.join(" · ")}</div> : null}
        </Card>
      </div>
    </Shell>
  );
};

/* ───────── s5: 어제 확인 → 결과 카드 → 기록 → 내일 볼 것 카드 ───────── */
/* ───────── s4: 이슈(있는 날만) — 무슨 일이 있었나(그림) → 그 묶음이 오늘 어떻게 움직였나 ───────── */
type EvStock = { name: string; pct: number; foreign?: number; inst?: number };
type Ev = { label: string; group?: string; stocks?: EvStock[]; icons?: string[] } | null | undefined;

/** 이슈를 그림으로 — 외부 이미지는 쓰지 않는다(저작권). 전부 여기서 그린다. */
const IssueIcon: React.FC<{ kind: string; color: string; size?: number }> = ({ kind, color, size = 300 }) => {
  const S = size;
  if (kind === "shield") return (
    <svg width={S} height={S} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 28px ${color}66)` }}>
      <path d="M50 6 L86 20 V48 C86 70 68 86 50 94 C32 86 14 70 14 48 V20 Z" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" strokeLinejoin="round" />
      <rect x="36" y="46" width="28" height="22" rx="4" fill={color} />
      <path d="M41 46 V38 a9 9 0 0 1 18 0 V46" fill="none" stroke={color} strokeWidth="5" />
      <circle cx="50" cy="57" r="3.2" fill="#0B0E16" />
    </svg>);
  if (kind === "fiber") return (
    <svg width={S * 1.4} height={S} viewBox="0 0 140 100" style={{ filter: `drop-shadow(0 0 24px ${color}66)` }}>
      {[22, 50, 78].map((y, i) => (
        <g key={i}>
          <path d={`M4 ${y} C40 ${y - 14}, 70 ${y + 14}, 136 ${y}`} fill="none" stroke={color} strokeWidth="4" opacity="0.55" />
          <circle cx={30 + i * 28} cy={y - 4 + i * 2} r="5.5" fill={color} />
          <circle cx={92 - i * 14} cy={y + 4 - i * 2} r="4" fill="#FFFFFF" opacity="0.9" />
        </g>))}
      <rect x="2" y="12" width="10" height="76" rx="3" fill={color} opacity="0.9" />
    </svg>);
  if (kind === "chip") return (
    <svg width={S} height={S} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 24px ${color}66)` }}>
      <rect x="26" y="26" width="48" height="48" rx="6" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" />
      {[34, 44, 54, 64].map((v) => (<g key={v}><line x1={v} y1="10" x2={v} y2="26" stroke={color} strokeWidth="4" /><line x1={v} y1="74" x2={v} y2="90" stroke={color} strokeWidth="4" /><line x1="10" y1={v} x2="26" y2={v} stroke={color} strokeWidth="4" /><line x1="74" y1={v} x2="90" y2={v} stroke={color} strokeWidth="4" /></g>))}
      <rect x="40" y="40" width="20" height="20" rx="3" fill={color} />
    </svg>);
  if (kind === "battery") return (
    <svg width={S} height={S} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 24px ${color}66)` }}>
      <rect x="14" y="30" width="64" height="40" rx="7" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" />
      <rect x="80" y="42" width="8" height="16" rx="2" fill={color} />
      {[22, 36, 50].map((x) => <rect key={x} x={x} y="38" width="11" height="24" rx="2" fill={color} />)}
      <path d="M58 24 L50 46 H60 L52 68" fill="none" stroke="#FFFFFF" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" opacity="0.95" />
    </svg>);
  if (kind === "robot") return (
    <svg width={S} height={S} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 24px ${color}66)` }}>
      <line x1="50" y1="8" x2="50" y2="20" stroke={color} strokeWidth="4" />
      <circle cx="50" cy="7" r="4" fill={color} />
      <rect x="22" y="20" width="56" height="42" rx="9" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" />
      <rect x="32" y="32" width="12" height="12" rx="3" fill={color} />
      <rect x="56" y="32" width="12" height="12" rx="3" fill={color} />
      <line x1="36" y1="52" x2="64" y2="52" stroke={color} strokeWidth="4" strokeLinecap="round" />
      <rect x="30" y="66" width="40" height="26" rx="6" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" />
      <rect x="10" y="30" width="8" height="22" rx="3" fill={color} opacity="0.8" />
      <rect x="82" y="30" width="8" height="22" rx="3" fill={color} opacity="0.8" />
    </svg>);
  // 기본: 신문 한 장
  return (
    <svg width={S} height={S} viewBox="0 0 100 100" style={{ filter: `drop-shadow(0 0 24px ${color}66)` }}>
      <rect x="14" y="18" width="72" height="64" rx="6" fill="rgba(5,8,16,0.6)" stroke={color} strokeWidth="5" />
      <rect x="24" y="30" width="30" height="20" rx="2" fill={color} />
      {[34, 42, 50].map((y) => <line key={y} x1="60" y1={y} x2="76" y2={y} stroke={color} strokeWidth="4" />)}
      {[60, 68].map((y) => <line key={y} x1="24" y1={y} x2="76" y2={y} stroke={color} strokeWidth="4" opacity="0.7" />)}
    </svg>);
};

export const S4V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const pop = usePop();
  const { f, fps } = useT();
  const ev = (p as unknown as { event?: Ev }).event;
  const st = (ev?.stocks ?? []).slice(0, 6);
  const avg = st.length ? st.reduce((a, x) => a + x.pct, 0) / st.length : 0;
  const cl = cues ?? [];
  const t0 = cl[0]?.start ?? 0;
  const t1 = cl.find((c) => /평균|올랐|내렸|종목/.test(c.text))?.start ?? (cl[1]?.start ?? t0 + 3);
  const tone = toneOf(avg);
  const col = tone === "down" ? BLUE : tone === "up" ? RED : YEL;
  // 도입 큐(평균 전) 하나마다 그림 하나 — 말을 글로 띄우지 않는다(JJ 2026-09-14)
  const intro = cl.filter((c) => c.start < t1).slice(0, 3);
  const icons = (ev?.icons && ev.icons.length ? ev.icons : ["news"]);
  const fade = interpolate(f, [t1 * fps, (t1 + 0.35) * fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const many = st.length > 4;
  return (
    <Shell p={p} cues={cues} badge="오늘의 이슈" bg={<BgChip tone={tone} dim={0.55} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 240 }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: "#CFD6E4", letterSpacing: "0.02em", marginBottom: 14, ...pop(t0) }}>오늘의 이슈</div>
        <div style={{ fontSize: 84, fontWeight: 900, lineHeight: 1.14, letterSpacing: "-0.04em", wordBreak: "keep-all",
          textShadow: "0 6px 30px rgba(0,0,0,0.85)", ...pop(t0 + 0.2) }}>{ev?.label ?? ""}</div>
      </div>
      {/* 그림 무대 — 평균이 나오면 사라진다 */}
      <div style={{ position: "absolute", left: 64, right: 64, top: 520, height: 420, display: "flex", justifyContent: "center", alignItems: "center", gap: 60, opacity: fade }}>
        {intro.map((c, k) => (
          <div key={k} style={{ ...pop(c.start + 0.1) }}>
            <IssueIcon kind={icons[k % icons.length]} color={k % 2 ? YEL : col} size={intro.length > 2 ? 250 : 300} />
          </div>
        ))}
      </div>
      {st.length ? (
        <>
          <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(t1) }}>
            <div style={{ fontSize: 42, fontWeight: 800, color: "#CFD6E4" }}>{ev?.group ?? "관련주"} {st.length}종목 평균</div>
            <div style={{ fontSize: 148, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.04em", marginTop: 4 }}>
              <Grad tone={tone}>{sgn(avg)}{Math.abs(avg).toFixed(1)}%</Grad>
            </div>
          </div>
          <div style={{ position: "absolute", left: 64, right: 64, top: many ? 860 : 1010 }}>
            {st.map((x, i) => (
              <div key={x.name} style={{ ...pop(t1 + 0.35 + i * 0.28) }}>
                <Card color={colOf(x.pct)} style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: many ? 10 : 18, padding: many ? "12px 26px" : undefined }}>
                  <span style={{ fontSize: many ? 48 : 62, fontWeight: 800, letterSpacing: "-0.02em" }}>{x.name}</span>
                  <span style={{ fontSize: many ? 56 : 72, fontWeight: 900, color: colOf(x.pct), letterSpacing: "-0.03em" }}>{sgn(x.pct)}{Math.abs(x.pct).toFixed(1)}%</span>
                </Card>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </Shell>
  );
};

export const S5V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const a = ap(p);
  const pop = usePop();
  const ck = a.check!;
  const v = ck.verdict;
  const find = (re: RegExp, fb: number) => { const c = (cues ?? []).find((x) => re.test(x.text)); return c ? c.start : fb; };
  const resAt = find(/끊겼습니다|이어졌습니다|멈췄습니다/, 2);
  const recAt = find(/^지금까지/, 4);
  const nextAt = find(/테마 대신|하나만 봅니다|볼 것은|[을를] 봅니다\.$/, 7);
  // 판단 기준 눈금: '왜 이어지는지를 보는가'를 말하는 동안 화면이 멈춰 있지 않도록(JJ 2026-09-13)
  const { f, fps } = useT();
  const hasCrit = (cues ?? []).some((x) => /^하루 수급|^하루치 수급/.test(x.text));
  const whyAt = find(/^하루 수급|^하루치 수급/, resAt + 4);
  const critAt = find(/^이틀은|^사흘째까지|이어졌다면/, whyAt + 3);
  const STEPS: [string, string][] = [["1일", "그날 사정"], ["2일", "아직 이르다"], ["3일~", "자리 잡는 흐름"]];
  // 마무리 — 시청자에게 묻는 화면(2026-09-14). 댓글이 0인 이유는 우리가 한 번도 말을 걸지 않아서다.
  const cl = cues ?? [];
  const dIdx = cl.findIndex((x) => x.text.includes("댓글"));
  // TTS가 '…보시겠습니까?' / '댓글로 남겨 주세요.' 로 끊으면 댓글 큐에는 질문이 없다 — 앞 큐에서 가져온다.
  const stripD = (t: string) => t.replace(/\s*댓글(로|에)[^.?]*[.?]?\s*$/, "").trim();
  const askCue = dIdx < 0 ? undefined : (stripD(cl[dIdx].text) ? cl[dIdx] : cl[dIdx - 1] ?? cl[dIdx]);
  const askText = stripD(askCue?.text ?? "");
  const ctaCue = cl.find((x) => x.text.includes("좋아요"));
  const wd = v?.when ?? "어제";
  const ask = v ? (v.kind === "theme_continue" ? [`${wd} ${v.theme} 순매수`, `${daysKo(v.n)} 이어질까?`]
    : v.kind === "inv_continue" ? [`${wd} ${v.theme} ${(v.sign ?? -1) > 0 ? "순매수" : "순매도"}`, `${daysKo(v.n)} 이어질까?`.trim()]
    : v.kind === "theme_sell_stop" ? [`${wd} ${v.theme} 순매도`, "멈출까?"] : [`${wd} 확인한 것`, v.theme]) : null;
  const rec = ck.record;
  const nq = ck.next_q.replace(/가 (\S+째 )?이어지는지$/, (_m, d1) => `가 ${d1 ?? ""}이어지는지`).replace(/\s+/g, " ");
  const okCol = v && v.ok ? GREEN : RED;
  const wkCue = cl.find((x) => /주간 결산에선|주간 결산에서도/.test(x.text));
  const cauCue = cl.find((x) => /다른 숫자입니다/.test(x.text));
  const wkRows = (a as unknown as { weekend_watch?: { src: string; q: string; a: string }[] }).weekend_watch ?? [];
  if (askCue && f >= askCue.start * fps) {
    // 쌓인 카드를 다 내리고 질문만 남긴다. 사람들이 가장 많이 빠져나가는 자리라 화면을 한 번 리셋한다.
    return (
      <Shell p={p} cues={cues} hideSub bg={<BgMarket tone="neutral" dim={0.62} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(askCue.start, 30) }}>
          <div style={{ fontSize: 44, fontWeight: 800, color: "#CFD6E4", marginBottom: 22 }}>여러분 생각은</div>
          <div style={{ fontSize: 92, fontWeight: 900, lineHeight: 1.18, letterSpacing: "-0.04em", color: YEL, wordBreak: "keep-all",
            textShadow: "0 0 40px rgba(255,216,77,0.42), 0 6px 30px rgba(0,0,0,0.8)" }}>{askText}</div>
          <div style={{ fontSize: 46, fontWeight: 800, color: "#FFFFFF", marginTop: 34 }}>댓글로 남겨 주세요</div>
        </div>
        {ctaCue && f >= ctaCue.start * fps ? (
          <div style={{ position: "absolute", left: 64, right: 64, bottom: 300, ...pop(ctaCue.start, 22), display: "flex", gap: 18 }}>
            <div style={{ flex: 1, textAlign: "center", border: `2.5px solid ${RED}`, borderRadius: 20, padding: "20px 10px", background: "rgba(255,77,77,0.14)" }}>
              <div style={{ fontSize: 52, fontWeight: 900, color: RED }}>좋아요</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#CFD6E4", marginTop: 4 }}>도움이 됐다면</div>
            </div>
            <div style={{ flex: 1, textAlign: "center", border: `2.5px solid ${YEL}`, borderRadius: 20, padding: "20px 10px", background: "rgba(255,216,77,0.14)" }}>
              <div style={{ fontSize: 52, fontWeight: 900, color: YEL }}>구독</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#CFD6E4", marginTop: 4 }}>내일 답이 궁금하면</div>
            </div>
          </div>
        ) : null}
      </Shell>
    );
  }
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.45} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        {ask ? (
          <div style={pop(0.05)}>
            <div style={{ fontSize: 64, fontWeight: 800, lineHeight: 1.2, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>{ask[0]}</div>
            <div style={{ fontSize: 76, fontWeight: 900, lineHeight: 1.2, color: YEL, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>{ask[1]}</div>
          </div>
        ) : null}
        {v ? (
          <Card color={okCol} style={{ ...pop(resAt), marginTop: 34 }}>
            <span style={{ display: "inline-block", fontSize: 34, fontWeight: 800, background: okCol, color: "#0B0E16", padding: "4px 16px", borderRadius: 10 }}>결과는</span>
            <div style={{ fontSize: 124, fontWeight: 900, letterSpacing: "-0.04em", lineHeight: 1.1, marginTop: 10, color: okCol, textShadow: `0 0 26px ${okCol}88` }}>{v.ok ? "이어졌습니다." : "끊겼습니다."}</div>
            {v.amount != null ? <div style={{ fontSize: 50, fontWeight: 800, marginTop: 8 }}>{fmtEok(Math.abs(v.amount))} {v.amount > 0 ? "순매수" : "순매도"} <span style={{ color: colOf(v.amount) }}>{v.amount > 0 ? "▲" : "▼"}</span></div> : null}
          </Card>
        ) : null}
        {hasCrit ? (
          <div style={{ ...pop(whyAt), marginTop: 26 }}>
            <div style={{ fontSize: 34, fontWeight: 800, color: "#9FB0C9", marginBottom: 10, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>며칠째부터 흐름으로 보나</div>
            <div style={{ display: "flex", gap: 12 }}>
              {STEPS.map(([d, t], i) => {
                const now = (v?.n ?? 0) === i + 1;
                const lit = i === 2 ? f >= critAt * fps : now;
                const col = i === 2 ? GREEN : YEL;
                return (
                  <div key={d} style={{ flex: 1, border: `2px solid ${lit ? col : "rgba(255,255,255,0.18)"}`, borderRadius: 16,
                    background: lit ? `${col}22` : "rgba(10,14,26,0.72)", padding: "14px 10px", textAlign: "center",
                    boxShadow: lit ? `0 0 24px ${col}55` : "none" }}>
                    <div style={{ fontSize: 46, fontWeight: 900, color: lit ? col : "#E8EEF9" }}>{d}</div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: lit ? "#FFFFFF" : "#9FB0C9", marginTop: 4, wordBreak: "keep-all" }}>{t}</div>
                    {now ? <div style={{ fontSize: 24, fontWeight: 800, color: "#0B0E16", background: YEL, borderRadius: 8, marginTop: 8, padding: "2px 0" }}>오늘</div> : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
        {rec && rec.n ? (
          <div style={{ ...pop(recAt), fontSize: 46, fontWeight: 700, marginTop: 26, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>
            지금까지 확인 {rec.n}번 · 이어짐 <span style={{ color: GREEN, fontWeight: 900 }}>{rec.k}</span> · 끊김 <span style={{ color: RED, fontWeight: 900 }}>{rec.n - rec.k}</span>
          </div>
        ) : null}
        {wkCue && wkRows.length ? (
          <Card color={YEL} style={{ ...pop(wkCue.start), marginTop: 26 }}>
            <div style={{ fontSize: 34, fontWeight: 800, color: "#CFD6E4" }}>주말에 보자고 한 것</div>
            {wkRows.slice(0, 2).map((r) => (
              <div key={r.src} style={{ fontSize: 40, fontWeight: 800, marginTop: 6, wordBreak: "keep-all" }}>{r.src.replace(" 결산", "")} · {r.q}</div>
            ))}
          </Card>
        ) : null}
        {cauCue ? (
          <Card color={RED} style={{ ...pop(cauCue.start), marginTop: 26 }}>
            <div style={{ fontSize: 34, fontWeight: 800, color: "#CFD6E4" }}>읽을 때 조심할 것</div>
            <div style={{ fontSize: 44, fontWeight: 900, marginTop: 6 }}>하루 크기 ≠ 며칠째</div>
          </Card>
        ) : null}
        <Card color={YEL} style={{ ...pop(nextAt), marginTop: 40 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 40, fontWeight: 800, color: YEL }}>
            <svg width="40" height="40" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2.5" fill="none" stroke={YEL} strokeWidth="2" /><path d="M3 10h18M8 3v4M16 3v4" stroke={YEL} strokeWidth="2" /></svg>
            {ck.next_day} 볼 것
          </div>
          <div style={{ fontSize: 62, fontWeight: 900, lineHeight: 1.25, marginTop: 12, wordBreak: "keep-all" }}>{nq}</div>
        </Card>
      </div>
    </Shell>
  );
};

/* ───────── s6: 끝 ───────── */
export const S6V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const pop = usePop();
  // 끝 화면은 말과 같은 시각을 보여준다(JJ 2026-09-15: "마지막 멘트와 장면이 바뀌어야 해. 5시로!").
  // 시각은 대사에서 읽는다 — 대사가 '저녁 5시'면 화면도 '저녁 5시'. 대사에 없으면 기본값.
  const all = (cues || []).map((c) => c.text || "").join(" ");
  const when = (all.match(/매일\s*((?:아침|오후|저녁|밤)\s*\d+시(?:\s*\d+분)?)/) || [])[1] || "저녁 5시";
  const after = /애프터마켓/.test(all);                 // 이번 주만: 정규장 뒤 저녁 8시까지 거래된다는 안내
  const afterAt = (cues || []).find((c) => /애프터마켓/.test(c.text || ""));
  const sigAt = (cues || []).find((c) => /올라옵니다/.test(c.text || ""));
  const t0 = afterAt ? afterAt.start : 0.1;
  const t1 = sigAt ? sigAt.start : 0.1;
  return (
    <Shell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.2} />}>
      {after && (
        <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(t0, 30) }}>
          <div style={{ fontSize: 46, fontWeight: 700, opacity: 0.85, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>정규장이 끝나도</div>
          <div style={{ fontSize: 76, fontWeight: 900, letterSpacing: "-0.03em", textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>
            <span style={{ color: YEL }}>저녁 8시</span>까지 애프터마켓
          </div>
        </div>
      )}
      <div style={{ position: "absolute", left: 64, right: 64, top: after ? 700 : 560, ...pop(t1, 30) }}>
        <Logo scale={2.4} />
        <div style={{ fontSize: 64, fontWeight: 800, marginTop: 190, textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>국장 마감은 매일</div>
        <div style={{ fontSize: 120, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)" }}>{when}</div>
      </div>
    </Shell>
  );
};
