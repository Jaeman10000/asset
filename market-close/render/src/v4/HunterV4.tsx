/** 헌터 포맷 화면 S0~S6 (9장면: s0 s1 s2 s3a s3b s3c s4 s5 s6) — docs/HUNTER_FORMAT_DESIGN.md §6.2, 정본 docs/SCRIPT_SYSTEM_HUNTER_v1.0.md §4.
 * 화면은 p.hunter[id] 만 읽는다(대사 정규식에 기대지 않는다). 단계는 큐 순서로 넘긴다:
 *   scenes[].steps 에 단계 이름이 있으면 그 이름의 i번째 큐 start 에 켜고, 없으면 인덱스(또는 문장 안의 이름·고정 문구)로 잡는다.
 *   기대하는 단계 이름 —
 *     s0: a b (card) · s1: q · s2: naive admit turn reveal top · s3a: promise (stamp) meaning turn after q
 *     s3b: move row:0 row:1 … turn table q · s3c: stock:0 stock:1 … turn bar:0 bar:1 … q · s4: doc row:0 row:1 … calc
 *     s5: a b verdict condition limit · s6: intro watch:0 watch:1 … event after sig
 *   체인 질문(q)은 S3V4 의 다리 질문과 같이 카드를 내리고 노란 질문만 남긴다(질문은 질문만).
 * 시각 언어는 ScenesV4 와 같다(구운 야경 배경, Pretendard 800/900, 네온 카드, 노랑 질문, 빨강=순매수·상승, 파랑=순매도·하락). 자막은 Shell 이 그린다.
 * 렌더 비용: filter/drop-shadow 없음, 움직임은 opacity·transform·길이만. */
import React from "react";
import { AbsoluteFill, interpolate, Easing } from "remotion";
import { FONT, fmtEok, fmtIdx } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";
import { BgCity, BgChip, BgMarket, Card, Shell, YEL, GREEN, BLUE, RED, usePop, useT } from "./ScenesV4";

type SC = { p: Props; sub: string; cues?: Cue[] };
type Tone = "up" | "down" | "neutral";
const ease = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const SUBC = "#CFD6E4";
const GREY = "#8C99AD";
const LINE = "rgba(255,255,255,0.16)";
const SH = "0 3px 14px rgba(0,0,0,0.85)";
const SH_Q = "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)";
const toneOf = (v?: number | null): Tone => (v == null || v === 0 ? "neutral" : v > 0 ? "up" : "down");
const colOf = (v?: number | null) => (v == null || v === 0 ? "#E6E6E3" : v > 0 ? RED : BLUE);
/** '2.5조' / '4,600억' — 화면 큰 숫자(말과 같은 반올림, ScenesV4.short 와 동일) */
const short = (v: number) => {
  const a = Math.abs(v);
  if (a >= 10000) return `${(Math.round(a / 1000) / 10).toFixed(1).replace(/\.0$/, "")}조`;
  return `${(a >= 1000 ? Math.round(a / 100) * 100 : Math.round(a / 10) * 10).toLocaleString("ko-KR")}억`;
};
const sgn = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");
/** 막대 옆 숫자: 1,000억 미만은 그대로(937억 — 말과 같은 숫자), 그 위는 말의 반올림(8,300억·1.6조) */
const amt = (v: number) => (Math.abs(v) < 1000 ? fmtEok(v) : short(v));
/** 표 원본 칸의 숫자: −38,339 (단위는 표 머리에) */
const fmtRaw = (v: number) => `${v < 0 ? "−" : ""}${Math.abs(Math.round(v)).toLocaleString("ko-KR")}`;
const fmtPctS = (v: number) => `${sgn(v)}${Math.abs(v).toFixed(2).replace(/0$/, "")}%`;
const batchim = (w: string) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 ? (c - 0xac00) % 28 !== 0 : false; };
const iga = (w: string) => (batchim(w) ? "이" : "가");

/* ───────── p.hunter 의 모양(설계 §6.1). 숫자는 억 단위 정수(음수=순매도), pct 는 % ───────── */
type NV = { name: string; v: number };
type HNum = { label: string; value: string; num: number; unit?: string };
export type Hunter = {
  s0?: { kind?: string; a: HNum; b: HNum };
  s1?: { q: string; tail?: string | null };
  s2?: { naive: string; naive_name?: string | null; naive_v?: number | null; bars: NV[]; reveal?: { name: string; v: number; days?: number | null; top?: NV[] | null } | null };
  s3a?: { promise: string; result: string; ok: boolean; num?: number | null; head?: string | null;
          changed?: { label: string; before: string; after: string; before_label?: string | null } | null };
  s3b?: { title: string; rows: NV[]; table?: { title: string; rows: NV[] } | null };
  s3c?: { title: string; stocks: { name: string; pct: number }[]; bars: NV[] };
  s4?: { doc: string; rows: { label: string; v: number; hi?: boolean }[]; calc?: { expr: string; result: string; lhs?: number; rhs?: number; value?: number; kind?: string } | null };
  s5?: { a: string; b: string; verdict: "a" | "b"; condition: string; limit?: string | null; callback_num?: string | null };
  s6?: { watch: { q: string; threshold?: string | null }[]; event?: { label: string; when: string; note?: string | null } | null; after_market?: boolean; when?: string | null };
};
const hunterOf = (p: Props): Hunter => ((p as unknown as { hunter?: Hunter }).hunter ?? {});

/* ───────── 단계 = 큐 순서 ───────── */
const useSteps = (p: Props, id: string, cues?: Cue[]) => {
  const { t } = useT();
  const sc = p.scenes.find((s) => s.id === id);
  const steps = sc?.steps;
  // 단계 시각은 문장 경계(bounds, tts.py 가 문장마다 1개 저장)로 잡는다. cues 는 자막용이라 55자 넘는 문장을 ', ' 에서 쪼개므로
  // steps[i] 와 cues[i] 가 어긋날 수 있다(tts_typecast.cues_from_words · tts.make_cues). bounds 가 steps 와 개수가 맞을 때만 쓴다.
  const bounds = sc?.bounds;
  const list: Cue[] = bounds && bounds.length && (!steps || bounds.length === steps.length) ? bounds : (cues ?? []);
  /** name 단계의 시작 초. steps 에 이름이 있으면 그 큐, 없으면 fbIdx 번째 큐, 그것도 없으면 fbSec(기본 fbIdx×3초) */
  const at = (name: string, fbIdx: number, fbSec?: number) => {
    const k = steps ? steps.indexOf(name) : -1;
    if (k >= 0 && list[k]) return list[k].start;
    if (fbIdx >= 0 && list[fbIdx]) return list[fbIdx].start;
    return fbSec ?? Math.max(0, fbIdx) * 3;
  };
  /** 문장 안에 needle 이 처음 나오는 큐의 시작 초(없으면 undefined) */
  const say = (needle: string) => { const c = needle ? list.find((x) => x.text.includes(needle)) : undefined; return c ? c.start : undefined; };
  const ci = list.filter((c) => t >= c.start).length - 1;
  const cur = ci >= 0 ? list[ci] : undefined;
  const qk = steps ? steps.indexOf("q") : -1;
  const q = qk >= 0 && list[qk] ? list[qk] : list.find((c) => /\?$/.test(c.text.trim()));
  const inQ = !!q && t >= q.start;
  return { t, list, steps, at, say, ci, cur, q, inQ };
};

const Grad: React.FC<{ tone: Tone; children: React.ReactNode; style?: React.CSSProperties }> = ({ tone, children, style }) => {
  const g = tone === "down" ? "linear-gradient(180deg,#A8DCFF 0%,#4A8BFF 48%,#2554E6 100%)"
    : tone === "up" ? "linear-gradient(180deg,#FFC2B8 0%,#FF5A4E 46%,#E2242B 100%)" : "linear-gradient(180deg,#FFFFFF 0%,#CFD6E4 100%)";
  return <span style={{ backgroundImage: g, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", ...style }}>{children}</span>;
};

const Logo: React.FC<{ scale?: number }> = ({ scale = 1 }) => (
  <div style={{ transform: `scale(${scale})`, transformOrigin: "left top" }}>
    <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 60, color: "#FFFFFF", transform: "skewX(-10deg)", letterSpacing: "-0.05em", lineHeight: 1, textShadow: "0 3px 16px rgba(0,0,0,0.7)" }}>누가샀나</div>
    <svg width="220" height="24" viewBox="0 0 220 24" style={{ display: "block", marginTop: 2 }}>
      <path d="M3 15 C 46 7, 120 3, 216 8 L 213 14 C 150 11, 90 13, 40 17 C 25 18, 12 20, 5 21 Z" fill="#E8362F" />
      <path d="M40 18 C 90 15, 150 14, 205 13" stroke="#FF6A55" strokeWidth="2" fill="none" opacity="0.6" />
    </svg>
  </div>
);

/** 조용한 바탕(S1 질문 선언) — 그림 없이 어두운 빛 하나 */
const BgPlain: React.FC = () => <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 42%, #141C30 0%, #0A0E1A 55%, #05070D 100%)" }} />;

/** 데이터가 없을 때(hunter[id] 누락) — 빈 껍데기. 소리·자막은 그대로 간다 */
const Empty: React.FC<SC> = ({ p, cues }) => <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.4} />}>{null}</Shell>;

/** 체인 질문 화면 — 카드를 다 내리고 질문만(S3V4 다리 질문과 같은 리셋) */
const QOnly: React.FC<{ p: Props; cues?: Cue[]; q: Cue; bg: React.ReactNode }> = ({ p, cues, q, bg }) => {
  const pop = usePop();
  const text = q.text.trim().replace(/^그럼\s*/, "").replace(/요\?$/, "?");
  return (
    <Shell p={p} cues={cues} hideSub bg={bg}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 360, ...pop(q.start, 30), fontSize: 108, fontWeight: 900, lineHeight: 1.18, letterSpacing: "-0.04em",
        color: YEL, wordBreak: "keep-all", textShadow: SH_Q }}>{text}</div>
    </Shell>
  );
};

/** 세로 막대(기준선 위 순매수·아래 순매도). k번째 막대는 at[k]초에 자라고, slide[k] 면 오른쪽에서 밀려 들어온다. hi 는 노란 테두리 */
const VBars: React.FC<{ bars: NV[]; at: number[]; slide?: boolean[]; hi?: number; tags?: (string | null)[]; tagAt?: number[]; height?: number; cols?: number }> =
  ({ bars, at, slide, hi = -1, tags, tagAt, height = 660, cols }) => {
    const { t } = useT();
    const n = Math.max(1, cols ?? bars.length);
    const W = 952; const cw = W / n; const bw = Math.min(170, Math.round(cw * 0.62));
    const posMax = Math.max(0, ...bars.map((b) => b.v));
    const negMax = Math.max(0, ...bars.map((b) => -b.v));
    const TOP = 136, BOT = 130;   // 위: 태그+값 라벨 · 아래: 값 라벨+이름
    const scale = (height - TOP - BOT) / Math.max(1, posMax + negMax);
    const base = TOP + posMax * scale;
    return (
      <div style={{ position: "relative", width: W, height, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: base, height: 2, background: "rgba(255,255,255,0.28)" }} />
        {bars.map((b, k) => {
          const a = at[k] ?? 0;
          const grow = interpolate(t, [a, a + 0.6], [0, 1], { ...CLAMP, easing: ease });
          const op = interpolate(t, [a, a + 0.25], [0, 1], CLAMP);
          const sx = slide?.[k] ? interpolate(t, [a, a + 0.55], [W, 0], { ...CLAMP, easing: ease }) : 0;
          const len = Math.abs(b.v) * scale * grow;
          const col = colOf(b.v);
          const up = b.v >= 0;
          const lit = hi === k;
          const x = cw * k + (cw - bw) / 2;
          const valTop = up ? base - len - 66 : base + len + 10;
          const tag = tags?.[k];
          const showTag = !!tag && t >= (tagAt?.[k] ?? a);
          return (
            <div key={`${b.name}-${k}`} style={{ position: "absolute", left: x, top: 0, width: bw, height, transform: `translateX(${sx}px)`, opacity: op }}>
              <div style={{ position: "absolute", left: 0, width: bw, top: up ? base - len : base, height: len, borderRadius: 10,
                background: up ? `linear-gradient(180deg, ${col}, ${col}99)` : `linear-gradient(180deg, ${col}99, ${col})`,
                boxShadow: lit ? `0 0 34px ${col}, 0 0 0 4px ${YEL}` : `0 0 18px ${col}55` }} />
              <div style={{ position: "absolute", left: -70, width: bw + 140, textAlign: "center", top: valTop, fontSize: 48, fontWeight: 900, lineHeight: 1.15, color: col, textShadow: SH, whiteSpace: "nowrap" }}>{sgn(b.v)}{amt(b.v)}</div>
              {showTag ? (
                <div style={{ position: "absolute", left: -70, width: bw + 140, textAlign: "center", top: up ? valTop - 54 : valTop + 62 }}>
                  <span style={{ display: "inline-block", background: YEL, color: "#0B0E16", fontSize: 30, fontWeight: 900, padding: "3px 16px", borderRadius: 10, boxShadow: "0 0 20px rgba(255,216,77,0.5)" }}>{tag}</span>
                </div>
              ) : null}
              <div style={{ position: "absolute", left: -70, width: bw + 140, textAlign: "center", top: height - 54, fontSize: 40, fontWeight: 800, color: lit ? YEL : "#E6E6E3", textShadow: SH, whiteSpace: "nowrap" }}>{b.name}</div>
            </div>
          );
        })}
      </div>
    );
  };

/** 가로 막대(테마별). 길이는 |v| 비례(최소 10px), 색은 부호. hiName 줄은 노란 테두리 */
const HBars: React.FC<{ rows: NV[]; at: number[]; hiName?: string }> = ({ rows, at, hiName }) => {
  const { t } = useT();
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.v)));
  const BW = 450;
  return (
    <div style={{ width: 952 }}>
      {rows.map((r, k) => {
        const a = at[k] ?? 0;
        const grow = interpolate(t, [a, a + 0.6], [0, 1], { ...CLAMP, easing: ease });
        const op = interpolate(t, [a, a + 0.3], [0, 1], CLAMP);
        const w = Math.max(22, (Math.abs(r.v) / maxAbs) * BW) * grow;
        const col = colOf(r.v);
        const lit = !!hiName && r.name === hiName;
        return (
          <div key={`${r.name}-${k}`} style={{ display: "flex", alignItems: "center", height: 100, opacity: op, borderRadius: 16, padding: "0 16px", marginBottom: 8,
            background: lit ? "rgba(255,216,77,0.12)" : "transparent", boxShadow: lit ? `inset 0 0 0 3px ${YEL}` : "none" }}>
            <div style={{ width: 220, fontSize: 44, fontWeight: 800, color: lit ? YEL : "#FFFFFF", textShadow: SH, whiteSpace: "nowrap", overflow: "hidden" }}>{r.name}</div>
            <div style={{ width: BW, position: "relative", height: 44 }}>
              <div style={{ position: "absolute", left: 0, top: 0, height: 44, width: w, borderRadius: 8, background: `linear-gradient(90deg, ${col}, ${col}AA)`, boxShadow: `0 0 18px ${col}66` }} />
            </div>
            <div style={{ flex: 1, textAlign: "right", fontSize: 50, fontWeight: 900, color: col, textShadow: SH, whiteSpace: "nowrap" }}>{sgn(r.v)}{amt(r.v)}</div>
          </div>
        );
      })}
    </div>
  );
};

/* ───────── s0: 모순 후킹 — 숫자 A → 숫자 B 가 부딪힌다 → 지수 카드 ───────── */
export const S0H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s0;
  const { t, at } = useSteps(p, "s0", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const a0 = at("a", 0, 0);
  const b0 = at("b", 1, a0 + 3);
  const c0 = at("card", 2, b0 + 1.2);
  const ta = toneOf(h.a.num), tb = toneOf(h.b.num);
  const chg = p.kospi.chg_pct ?? 0;
  // 충돌: B 가 크게 들어와 제자리에 박히고, A 가 잠깐 흔들리고, 사이에 노란 금이 간다
  const d = Math.max(0, t - b0);
  const hit = t >= b0;
  const bScale = interpolate(t, [b0, b0 + 0.34], [1.7, 1], { ...CLAMP, easing: ease });
  const bOp = interpolate(t, [b0, b0 + 0.12], [0, 1], CLAMP);
  const shake = hit ? Math.sin(d * 46) * 22 * Math.exp(-d * 7) : 0;
  const burst = interpolate(t, [b0, b0 + 0.55], [0, 1], { ...CLAMP, easing: ease });
  const crack = interpolate(t, [b0 + 0.05, b0 + 0.3], [0, 1], CLAMP);
  const ring = 80 + burst * 1100;
  return (
    <Shell p={p} cues={cues} hideSub bg={<BgCity tone={ta} dim={0.15} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 240 }}>
        <div style={{ transform: `translateX(${shake}px)` }}>
          <div style={{ fontSize: 50, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(a0) }}>{h.a.label}</div>
          <div style={{ fontSize: 184, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", whiteSpace: "nowrap", ...pop(a0 + 0.3, 30) }}><Grad tone={ta}>{h.a.value}</Grad></div>
        </div>
        <div style={{ position: "relative", height: 90, margin: "18px 0 6px" }}>
          {hit ? <div style={{ position: "absolute", left: 476 - ring / 2, top: 45 - ring / 2, width: ring, height: ring, borderRadius: "50%", border: `6px solid ${YEL}`, boxShadow: `0 0 40px ${YEL}`, opacity: (1 - burst) * 0.9 }} /> : null}
          <div style={{ position: "absolute", left: 0, top: 42, width: 952 * crack, height: 8, background: YEL, boxShadow: `0 0 26px ${YEL}`, transform: "rotate(-2.5deg)", transformOrigin: "left center", borderRadius: 4 }} />
        </div>
        <div style={{ opacity: bOp, transform: `scale(${bScale})`, transformOrigin: "left center" }}>
          <div style={{ fontSize: 50, fontWeight: 800, color: YEL, textShadow: SH }}>{h.b.label}</div>
          <div style={{ fontSize: 184, fontWeight: 900, lineHeight: 1.02, letterSpacing: "-0.05em", whiteSpace: "nowrap" }}><Grad tone={tb}>{h.b.value}</Grad></div>
        </div>
      </div>
      {t >= c0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1010, ...pop(c0) }}>
          <Card color={colOf(chg)} style={{ display: "inline-block", minWidth: 640 }}>
            <div style={{ fontSize: 40, fontWeight: 800, color: SUBC, letterSpacing: "0.04em" }}>KOSPI</div>
            <div style={{ fontSize: 118, fontWeight: 800, lineHeight: 1.05, marginTop: 6 }}>{fmtIdx(p.kospi.close)}</div>
            <div style={{ fontSize: 64, fontWeight: 800, color: colOf(chg), marginTop: 6 }}>{chg > 0 ? "▲" : chg < 0 ? "▼" : "−"} {Math.abs(chg).toFixed(2)}%</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s1: 질문 선언 — 조용한 바탕에 노란 질문 한 줄 ───────── */
export const S1H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s1;
  const { at } = useSteps(p, "s1", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const q0 = at("q", 0, 0);
  return (
    <Shell p={p} cues={cues} hideSub bg={<BgPlain />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 640, ...pop(q0, 30) }}>
        <div style={{ width: 120, height: 8, borderRadius: 4, background: YEL, boxShadow: "0 0 22px rgba(255,216,77,0.6)", marginBottom: 34 }} />
        <div style={{ fontSize: 112, fontWeight: 900, lineHeight: 1.18, letterSpacing: "-0.04em", color: YEL, wordBreak: "keep-all", textShadow: SH_Q }}>{h.q}</div>
        {h.tail ? <div style={{ fontSize: 50, fontWeight: 800, color: "#FFFFFF", marginTop: 40, textShadow: SH, wordBreak: "keep-all", ...pop(q0 + 0.8) }}>{h.tail}</div> : null}
      </div>
    </Shell>
  );
};

/* ───────── s2: 대변 → 차단 — 막대 3개, '그런데'에 네 번째 막대가 오른쪽에서 들어온다 → 종목 카드 ───────── */
export const S2H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s2;
  const { t, at } = useSteps(p, "s2", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const n0 = at("naive", 0, 0);
  const n1 = at("admit", 1, n0 + 1.5);
  const n2 = at("turn", 2, n1 + 3);
  const n3 = at("reveal", 3, n2 + 0.9);
  const n4 = at("top", 4, n3 + 2.5);
  const rv = h.reveal ?? null;
  const naiveIdx = h.bars.findIndex((b) => b.name === (h.naive_name ?? ""));
  const bars: NV[] = rv ? [...h.bars, { name: rv.name, v: rv.v }] : h.bars;
  const rk = h.bars.length;   // 네 번째(공개) 막대의 자리
  const barAt = bars.map((_, k) => (rv && k === rk ? n2 : n0 + 0.35 + k * 0.2));
  const slide = bars.map((_, k) => !!rv && k === rk);
  const hi = rv && t >= n2 ? rk : t >= n1 ? naiveIdx : -1;
  const tags = bars.map((_, k) => (rv && k === rk && (rv.days ?? 0) >= 2 ? `${rv.days}일째` : null));
  const tagAt = bars.map(() => n3);
  const turned = t >= n2;
  const top = rv?.top ?? [];
  return (
    <Shell p={p} cues={cues} bg={<BgCity tone="neutral" dim={0.38} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, display: "flex", alignItems: "center", gap: 22, ...pop(n0) }}>
        <div style={{ fontSize: 78, fontWeight: 900, lineHeight: 1.1, letterSpacing: "-0.03em", wordBreak: "keep-all", color: turned ? GREY : YEL,
          textDecoration: turned ? "line-through" : "none", textShadow: turned ? SH : SH_Q }}>{h.naive}?</div>
        {turned ? <div style={{ ...pop(n2), fontSize: 40, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "8px 22px", borderRadius: 14, whiteSpace: "nowrap", boxShadow: "0 0 24px rgba(255,216,77,0.5)" }}>그런데</div> : null}
      </div>
      <div style={{ position: "absolute", left: 64, top: 340 }}>
        <VBars bars={bars} at={barAt} slide={slide} hi={hi} tags={tags} tagAt={tagAt} height={660} cols={bars.length} />
      </div>
      {rv && top.length && t >= n4 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1030 }}>
          <Card color={colOf(rv.v)} style={pop(n4)}>
            <div style={{ fontSize: 36, fontWeight: 700, color: SUBC }}>{rv.name}{iga(rv.name)} 가장 많이 {rv.v >= 0 ? "산" : "판"} 종목</div>
            {top.slice(0, 2).map((x, k) => (
              <div key={x.name} style={{ ...pop(n4 + 0.2 + k * 0.25), display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 16 }}>
                <span style={{ fontSize: 56, fontWeight: 900 }}>{x.name}</span>
                <span style={{ fontSize: 56, fontWeight: 900, color: colOf(x.v) }}>{sgn(x.v)}{fmtEok(x.v)}</span>
              </div>
            ))}
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s3a: 어제의 돈 — 약속 카드 + 도장(이어짐/끊김) → '그런데' 달라진 것(전→후) → 체인 질문 ───────── */
export const S3aH: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s3a;
  const { t, at, q, inQ } = useSteps(p, "s3a", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const tone = toneOf(h.num);
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgMarket tone={tone} dim={0.55} />} />;
  const p0 = at("promise", 0, 0);
  const s0 = at("stamp", -1, p0 + 1.1);
  const t0 = at("turn", 2, p0 + 6);
  const a0 = at("after", 3, t0 + 1.0);
  const okCol = h.ok ? GREEN : RED;
  const stampS = interpolate(t, [s0, s0 + 0.28], [2.6, 1], { ...CLAMP, easing: ease });
  const stampO = interpolate(t, [s0, s0 + 0.1], [0, 1], CLAMP);
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone={tone} dim={0.45} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        <div style={{ fontSize: 40, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(p0) }}>{h.head || "어제 보자고 한 것"}</div>
        <div style={{ position: "relative", marginTop: 14, ...pop(p0 + 0.15) }}>
          <Card color={YEL}>
            <div style={{ fontSize: 58, fontWeight: 900, lineHeight: 1.25, letterSpacing: "-0.02em", wordBreak: "keep-all", paddingRight: 240 }}>{h.promise}</div>
            {h.num != null ? <div style={{ fontSize: 44, fontWeight: 800, marginTop: 14, color: colOf(h.num) }}>오늘 {fmtEok(Math.abs(h.num))} {h.num < 0 ? "순매도" : "순매수"}</div> : null}
          </Card>
          {t >= s0 ? (
            <div style={{ position: "absolute", right: -6, top: -34, opacity: stampO, transform: `rotate(-12deg) scale(${stampS})`, transformOrigin: "center", fontSize: 72, fontWeight: 900,
              color: okCol, border: `7px solid ${okCol}`, borderRadius: 16, padding: "2px 22px", background: "rgba(5,8,16,0.6)", boxShadow: `0 0 30px ${okCol}88, inset 0 0 18px ${okCol}33`,
              letterSpacing: "0.04em", whiteSpace: "nowrap", lineHeight: 1.2 }}>{h.result}</div>
          ) : null}
        </div>
        {h.changed && t >= t0 ? (
          <Card color={BLUE} style={{ ...pop(t0), marginTop: 44 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <span style={{ fontSize: 32, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "4px 16px", borderRadius: 10 }}>그런데</span>
              <span style={{ fontSize: 40, fontWeight: 800, color: SUBC }}>{h.changed.label}{iga(h.changed.label)} 달라졌다</span>
            </div>
            {/* 전→후를 두 줄로: 한 줄에 넣으면 '기타법인 1조 6,431억'이 접힌다 */}
            <div style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 18 }}>
              <span style={{ minWidth: 76, fontSize: 30, fontWeight: 800, color: GREY, whiteSpace: "nowrap" }}>{h.changed.before_label || "어제"}</span>
              <span style={{ fontSize: 44, fontWeight: 700, color: GREY, textDecoration: "line-through", whiteSpace: "nowrap" }}>{h.changed.before}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 8, ...pop(a0) }}>
              <span style={{ minWidth: 76, fontSize: 30, fontWeight: 900, color: YEL, whiteSpace: "nowrap" }}>오늘</span>
              <span style={{ fontSize: 56, fontWeight: 900, color: "#FFFFFF", whiteSpace: "nowrap" }}>{h.changed.after}</span>
            </div>
          </Card>
        ) : null}
      </div>
    </Shell>
  );
};

/* ───────── s3b: 돈이 간 곳 — 테마 막대(말한 줄 강조) + 오른쪽 코스닥 표 → 체인 질문 ───────── */
export const S3bH: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s3b;
  const { t, cur, at, say, q, inQ } = useSteps(p, "s3b", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgMarket tone="neutral" dim={0.6} />} />;
  const m0 = at("move", 0, 0);
  const rowAt = h.rows.map((r, k) => at(`row:${k}`, -1, say(r.name) ?? m0 + 0.5 + k * 0.35));
  const tb = h.table ?? null;
  const tb0 = tb ? at("table", -1, say(tb.title) ?? Math.max(m0, ...rowAt) + 2.5) : 1e9;
  const hiTheme = cur ? h.rows.find((r) => cur.text.includes(r.name))?.name : undefined;
  const hiTb = cur && tb && t >= tb0 ? tb.rows.find((r) => cur.text.includes(r.name))?.name : undefined;
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(m0) }}>{h.title}</div>
        <div style={{ marginTop: 16 }}><HBars rows={h.rows} at={rowAt} hiName={hiTheme} /></div>
      </div>
      {tb && t >= tb0 ? (
        <div style={{ position: "absolute", left: 500, right: 64, top: 240 + 52 + h.rows.length * 108 + 40 }}>
          <Card color={YEL} style={{ ...pop(tb0), padding: "22px 30px" }}>
            <div style={{ fontSize: 36, fontWeight: 900, color: YEL }}>{tb.title}</div>
            {tb.rows.map((r) => {
              const lit = hiTb === r.name;
              return (
                <div key={r.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 12, padding: "4px 10px", borderRadius: 10,
                  background: lit ? "rgba(255,216,77,0.14)" : "transparent", boxShadow: lit ? `inset 0 0 0 2px ${YEL}` : "none" }}>
                  <span style={{ fontSize: 38, fontWeight: 800, color: lit ? YEL : "#E6E6E3" }}>{r.name}</span>
                  <span style={{ fontSize: 44, fontWeight: 900, color: colOf(r.v) }}>{fmtEok(r.v, true)}</span>
                </div>
              );
            })}
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s3c: 돈이 정체한 곳 — 종목 등락 칩 두 개 → 그 아래 막대 셋 → 체인 질문 ───────── */
export const S3cH: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s3c;
  const { t, at, say, q, inQ } = useSteps(p, "s3c", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgChip tone="neutral" dim={0.6} />} />;
  const stAt = h.stocks.map((s, k) => at(`stock:${k}`, -1, say(s.name) ?? k * 3));
  const turn = at("turn", h.stocks.length, Math.max(0, ...stAt) + 3);
  const barAt = h.bars.map((b, k) => at(`bar:${k}`, -1, say(b.name.split(/[+·]/)[0]) ?? turn + 0.3 + k * 0.3));
  return (
    <Shell p={p} cues={cues} bg={<BgChip tone="neutral" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(Math.min(...stAt, 0.05)) }}>{h.title}</div>
        <div style={{ display: "flex", gap: 20, marginTop: 16 }}>
          {h.stocks.map((s, k) => (
            <div key={s.name} style={{ flex: 1, ...pop(stAt[k]) }}>
              <Card color={colOf(s.pct)} style={{ padding: "18px 28px" }}>
                <div style={{ fontSize: 44, fontWeight: 900, whiteSpace: "nowrap", overflow: "hidden" }}>{s.name}</div>
                <div style={{ fontSize: 64, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.1, marginTop: 4, color: colOf(s.pct) }}>{fmtPctS(s.pct)}</div>
              </Card>
            </div>
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", left: 64, top: 470 }}>
        <VBars bars={h.bars} at={barAt} height={600} cols={h.bars.length} hi={-1} />
      </div>
    </Shell>
  );
};

/* ───────── s4: 1차 자료 한 칸 — 표 원본 느낌(칸에 테두리) + 계산식이 타자로 찍힌다 ───────── */
export const S4H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s4;
  const { t, at } = useSteps(p, "s4", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const d0 = at("doc", 0, 0);
  const rowAt = h.rows.map((_, k) => at(`row:${k}`, k + 1, d0 + 1.2 + k * 1.2));
  const c0 = h.calc ? at("calc", h.rows.length + 1, Math.max(d0, ...rowAt) + 3) : 1e9;
  const full = h.calc ? `${h.calc.expr} = ${h.calc.result}` : "";
  const nCh = Math.max(0, Math.floor((t - c0) / 0.06));
  const typed = full.slice(0, nCh);
  const typing = t >= c0 && nCh < full.length;
  const caret = typing && Math.floor(t * 5) % 2 === 0;
  const tableTop = 360;
  const calcTop = tableTop + 62 + h.rows.length * 113 + 44;
  return (
    <Shell p={p} cues={cues} badge="1차 자료" bg={<BgChip tone="neutral" dim={0.62} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, ...pop(d0) }}>
        <span style={{ display: "inline-block", fontSize: 36, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "6px 20px", borderRadius: 12 }}>직접 열어봤습니다</span>
        <div style={{ fontSize: 36, fontWeight: 700, color: SUBC, marginTop: 12, wordBreak: "keep-all", textShadow: SH }}>{h.doc}</div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: tableTop, ...pop(d0 + 0.3) }}>
        <div style={{ background: "rgba(14,18,30,0.92)", border: "2px solid rgba(255,255,255,0.28)", borderRadius: 10, overflow: "hidden", boxShadow: "0 10px 40px rgba(0,0,0,0.6)" }}>
          <div style={{ display: "flex", padding: "14px 26px", height: 62, boxSizing: "border-box", alignItems: "center", borderBottom: "2px solid rgba(255,255,255,0.28)", background: "rgba(255,255,255,0.06)",
            fontSize: 28, fontWeight: 800, color: GREY, letterSpacing: "0.04em" }}>
            <div style={{ flex: 1 }}>항목</div><div style={{ width: 300, textAlign: "right" }}>순매수 (억 원)</div>
          </div>
          {h.rows.map((r, k) => {
            const on = t >= rowAt[k];
            const lit = !!r.hi && on;
            return (
              <div key={k} style={{ display: "flex", alignItems: "center", padding: "0 26px", height: 112, boxSizing: "border-box", borderBottom: `1px solid ${LINE}`, opacity: on ? 1 : 0.55 }}>
                <div style={{ flex: 1, fontSize: 40, fontWeight: 700, color: lit ? "#FFFFFF" : SUBC, wordBreak: "keep-all", lineHeight: 1.2 }}>{r.label}</div>
                <div style={{ width: 300, textAlign: "right", fontSize: 58, fontWeight: 900, color: colOf(r.v), padding: "6px 14px", borderRadius: 8, boxSizing: "border-box",
                  boxShadow: lit ? `0 0 0 4px ${YEL}, 0 0 26px rgba(255,216,77,0.45)` : "none", background: lit ? "rgba(255,216,77,0.12)" : "transparent" }}>{fmtRaw(r.v)}</div>
              </div>
            );
          })}
        </div>
      </div>
      {h.calc && t >= c0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: calcTop, ...pop(c0) }}>
          <Card color={YEL}>
            <div style={{ fontSize: 34, fontWeight: 800, color: SUBC }}>이 칸으로 한 계산</div>
            <div style={{ fontSize: 78, fontWeight: 900, color: YEL, letterSpacing: "-0.02em", lineHeight: 1.15, marginTop: 8, whiteSpace: "nowrap", textShadow: "0 0 26px rgba(255,216,77,0.35)" }}>{typed}{caret ? "▌" : ""}</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s5: 양면 판정 + 조건 — A/B 카드, 판정 쪽이 켜지고 반대쪽은 흐려진다 → 뒤집히는 조건 → 한계 한 줄 ───────── */
export const S5H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s5;
  const { t, at } = useSteps(p, "s5", cues);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const a0 = at("a", 0, 0);
  const b0 = at("b", 1, a0 + 3);
  const v0 = at("verdict", 2, b0 + 3);
  const c0 = at("condition", 3, v0 + 3);
  const l0 = at("limit", 4, c0 + 3);
  const decided = t >= v0;
  const glow = interpolate(t, [v0, v0 + 0.5], [0, 1], { ...CLAMP, easing: ease });
  const cards: { k: "a" | "b"; text: string; at: number }[] = [{ k: "a", text: h.a, at: a0 }, { k: "b", text: h.b, at: b0 }];
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        <div style={{ fontSize: 40, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(a0) }}>오늘은 어느 쪽인가</div>
        <div style={{ display: "flex", gap: 24, marginTop: 16, alignItems: "stretch" }}>
          {cards.map((c) => {
            const win = decided && h.verdict === c.k;
            const lose = decided && h.verdict !== c.k;
            const ps = pop(c.at);
            const op = (ps.opacity as number) * (lose ? 1 - 0.62 * glow : 1);
            return (
              <div key={c.k} style={{ flex: 1, display: "flex", ...ps, opacity: op }}>
                <Card color={win ? GREEN : "#8FA7D9"} style={{ flex: 1, padding: "26px 28px", boxShadow: win ? `0 0 ${34 + 30 * glow}px ${GREEN}AA, inset 0 0 22px ${GREEN}33` : undefined }}>
                  <span style={{ display: "inline-block", fontSize: 30, fontWeight: 900, color: "#0B0E16", background: win ? GREEN : SUBC, padding: "4px 16px", borderRadius: 10 }}>{win ? "오늘은 이쪽" : c.k.toUpperCase()}</span>
                  <div style={{ fontSize: 54, fontWeight: 900, lineHeight: 1.25, letterSpacing: "-0.02em", wordBreak: "keep-all", marginTop: 16, color: win ? "#FFFFFF" : "#E6E6E3" }}>{c.text}</div>
                </Card>
              </div>
            );
          })}
        </div>
        {t >= c0 ? (
          <Card color={YEL} style={{ ...pop(c0), marginTop: 30 }}>
            <div style={{ fontSize: 34, fontWeight: 800, color: YEL }}>이 판정이 뒤집히는 조건</div>
            <div style={{ fontSize: 44, fontWeight: 800, lineHeight: 1.35, wordBreak: "keep-all", marginTop: 8 }}>{h.condition}</div>
          </Card>
        ) : null}
        {h.limit && t >= l0 ? (
          <div style={{ ...pop(l0), marginTop: 26, fontSize: 32, fontWeight: 600, color: GREY, lineHeight: 1.4, wordBreak: "keep-all", textShadow: SH }}>한계 · {h.limit}</div>
        ) : null}
      </div>
    </Shell>
  );
};

/* ───────── s6: 내일 관측값 + 시그니처 — 체크 줄(☐→☑) → 이벤트 시각 → 애프터마켓 → 로고 '저녁 5시'(S6V4 와 같은 블록) ───────── */
export const S6H: React.FC<SC> = ({ p, cues }) => {
  const h = hunterOf(p).s6;
  const { t, list, at, say } = useSteps(p, "s6", cues);
  const pop = usePop();
  const w = h?.watch ?? [];
  const i0 = at("intro", 0, 0);
  const wAt = w.map((_, k) => at(`watch:${k}`, k + 1, i0 + 1 + k * 1.6));
  const e0 = at("event", w.length + 1, (wAt.length ? wAt[wAt.length - 1] : i0) + 3);
  const a0 = at("after", -1, say("애프터마켓") ?? 1e9);
  const last = list.length ? list[list.length - 1].start : 0.1;
  const s0 = at("sig", -1, say("올라옵니다") ?? say("누가샀나") ?? last);
  const when = h?.when || "저녁 5시";
  const after = !!h?.after_market;
  if (t >= s0) {
    return (
      <Shell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.2} />}>
        {after ? (
          <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(s0, 30) }}>
            <div style={{ fontSize: 46, fontWeight: 700, opacity: 0.85, textShadow: SH }}>정규장이 끝나도</div>
            <div style={{ fontSize: 76, fontWeight: 900, letterSpacing: "-0.03em", textShadow: SH }}><span style={{ color: YEL }}>저녁 8시</span>까지 애프터마켓</div>
          </div>
        ) : null}
        <div style={{ position: "absolute", left: 64, right: 64, top: after ? 700 : 560, ...pop(s0, 30) }}>
          <Logo scale={2.4} />
          <div style={{ fontSize: 64, fontWeight: 800, marginTop: 190, textShadow: SH }}>국장 마감은 매일</div>
          <div style={{ fontSize: 120, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: SH_Q }}>{when}</div>
        </div>
      </Shell>
    );
  }
  return (
    <Shell p={p} cues={cues} bg={<BgCity tone="neutral" dim={0.34} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 220 }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH, ...pop(i0) }}>{p.next_label ?? "내일"} 볼 것</div>
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 22 }}>
          {w.map((x, k) => {
            const on = t >= wAt[k];
            const kk = interpolate(t, [wAt[k], wAt[k] + 0.35], [0, 1], { ...CLAMP, easing: ease });
            return (
              <div key={k} style={{ display: "flex", alignItems: "flex-start", gap: 24, ...pop(i0 + 0.3 + k * 0.2) }}>
                <div style={{ width: 64, height: 64, flex: "0 0 64px", boxSizing: "border-box", borderRadius: 14, border: `4px solid ${on ? GREEN : GREY}`, marginTop: 2,
                  background: on ? `rgba(47,210,122,${0.9 * kk})` : "rgba(10,14,26,0.6)", boxShadow: on ? `0 0 24px ${GREEN}88` : "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {on ? <svg width="40" height="40" viewBox="0 0 24 24"><path d="M4 12.5 L9.5 18 L20 6.5" fill="none" stroke="#0B0E16" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" style={{ strokeDasharray: 40, strokeDashoffset: 40 * (1 - kk) }} /></svg> : null}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 48, fontWeight: 800, lineHeight: 1.25, color: on ? "#FFFFFF" : SUBC, wordBreak: "keep-all", textShadow: SH }}>{x.q}</div>
                  {x.threshold ? <div style={{ marginTop: 10 }}><span style={{ display: "inline-block", fontSize: 30, fontWeight: 900, color: "#0B0E16", background: on ? YEL : GREY, padding: "4px 16px", borderRadius: 10 }}>기준 · {x.threshold}</span></div> : null}
                </div>
              </div>
            );
          })}
        </div>
        {h?.event && t >= e0 ? (
          <Card color={YEL} style={{ ...pop(e0), marginTop: 36 }}>
            <div style={{ fontSize: 36, fontWeight: 800, color: SUBC }}>{h.event.label}</div>
            <div style={{ fontSize: 84, fontWeight: 900, color: YEL, letterSpacing: "-0.03em", lineHeight: 1.1, marginTop: 6, textShadow: "0 0 26px rgba(255,216,77,0.35)" }}>{h.event.when}</div>
            {h.event.note ? <div style={{ fontSize: 34, fontWeight: 700, marginTop: 8, color: "#E6E6E3" }}>{h.event.note}</div> : null}
          </Card>
        ) : null}
        {after && t >= a0 ? (
          <div style={{ ...pop(a0), marginTop: 34 }}>
            <div style={{ fontSize: 40, fontWeight: 700, opacity: 0.85, textShadow: SH }}>정규장이 끝나도</div>
            <div style={{ fontSize: 64, fontWeight: 900, letterSpacing: "-0.03em", textShadow: SH }}><span style={{ color: YEL }}>저녁 8시</span>까지 애프터마켓</div>
          </div>
        ) : null}
      </div>
    </Shell>
  );
};

export const HUNTER_COMP: Record<string, React.FC<SC>> = { s0: S0H, s1: S1H, s2: S2H, s3a: S3aH, s3b: S3bH, s3c: S3cH, s4: S4H, s5: S5H, s6: S6H };
