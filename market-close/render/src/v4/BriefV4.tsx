/** 수급 브리핑 화면(docs/BRIEF_FORMAT_DESIGN.md §1·§3) — 9장면 s0 s1 s2 s3a s3b s3c s4 s5 s6, 체인 순서는 매일 고정.
 *  s0·s1·s2·s6 은 헌터 화면(S0H·S1H·S2H·S6H)을 그대로 쓰고, s3a·s3b·s3c·s4·s5 는 여기서 새로 그린다. 화면은 p.hunter[id] 만 읽는다(대사 정규식은 마지막 수단).
 *  단계 이름(문장 i번째 = scenes[].steps[i]) — 없으면 문장 안의 이름·숫자로 잡는다:
 *    s2(S2H): naive · bar:0 bar:1 bar:2(외국인·기관·개인) · turn · reveal · top(자사주 문장: 종목 카드 + 막대 밑 '자사주 99%' 칩) · q
 *    s3a: kosdaq · bar:0 bar:1 bar:2 · index · verdict · promise(콜백 카드, 도장은 이어졌/끊겼 문장) · turn · q
 *    s3b: row:0 · split(외/기 칩) · streak(N일째·어제 칩) · leaders(그런데 — 대장주 등락 카드 둘) · support(자사주 받침 막대) · rest 또는 row:1 row:2 …(나머지 유출 행) · q
 *    s3c: move · row:0 · names:0 · row:1 · names:1 · more:0 … · ratio · q
 *    s4: doc · row:0 · driver:0 · row:1 · driver:1 · calc  (칸 강조는 그 문장에 나온 외국인/기관/개인/거래대금/% 칸)
 *    s5: news:0 news:1 · a · b · verdict:0 verdict:1(업종별 판정 칩) · condition · callback · limit
 *    s6(S6H): intro · watch:k · event · after · sig
 *  세로 자리는 고정 슬롯(늦게 뜨는 카드가 앞 줄을 밀지 않는다, 자막은 bottom 128 위 ~1,620까지 비워 둔다). 시각 언어·렌더 비용 규칙은 HunterV4 와 같다(filter 없음, opacity·transform·길이만). */
import React from "react";
import { interpolate, Easing } from "remotion";
import { fmtIdx } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";
import { BgCity, BgChip, BgMarket, Card, Shell, YEL, GREEN, BLUE, RED, usePop, useT } from "./ScenesV4";
import { S0H, S1H, S2H, S6H, VBars, HBars, useSteps, spoken, fmtPctS, amt, sgn, colOf, toneOf, fmtRaw, QOnly, Empty, DKO } from "./HunterV4";
import type { NV } from "./HunterV4";

type SC = { p: Props; sub: string; cues?: Cue[] };
const ease = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const SUBC = "#CFD6E4";
const GREY = "#8C99AD";
const LINE = "rgba(255,255,255,0.16)";
const SH = "0 3px 14px rgba(0,0,0,0.85)";
const AMBER = "#FFB347";       // 유입 막대의 기관 몫(외국인은 빨강) — 둘 다 순매수라 빨강 계열 두 색
const PALE = "#8FA7D9";        // 판정 전 카드 테두리(헌터 S5 와 같다)
/** 말과 같은 연속일 수사(narrate_hunter.dko): 5→닷새째 · 11→11일째. 2 미만은 없음 */
const dTag = (n?: number | null) => { const a = Math.abs(n ?? 0); return a >= 2 ? `${a}일째` : null; };   // JJ 2026-09-17: 엿새째 대신 6일째
const dRe = (n: number) => new RegExp(`(?:${DKO[n] || "\\u0000"}|${n}일)째`);
/** 등락은 말한 그대로 두 자리(3.98% · 29.8%) — 표 칸용 */
const fmtPct2 = (v: number) => `${sgn(v)}${Math.abs(v).toFixed(2).replace(/0$/, "")}%`;

/* ───────── p.hunter 의 브리핑 키(설계 §3). 숫자는 억 단위 정수(음수=순매도), pct·ret 는 % ───────── */
type Idx = { name: string; close: number; chg_pct: number };
type OutRow = { theme: string; v: number; foreign?: number | null; inst?: number | null; ret?: number | null; streak?: number | null; y?: number | null };
type InRow = { theme: string; v: number; foreign?: number | null; inst?: number | null; ret?: number | null; names?: string[] | null; streak?: number | null };
type Stock = { name: string; role: string; theme?: string | null; pct: number; foreign?: number | null; inst?: number | null; indiv?: number | null; value?: number | null; driver?: string | null };
export type Brief = {
  s3a?: { kosdaq?: { bars: NV[] } | null; index?: Idx[] | null; verdict?: string | null; head?: string | null;
          promise?: string | null; result?: string | null; ok?: boolean | null; num?: number | null;
          changed?: { label: string; before: string; after: string; before_label?: string | null } | null };
  s3b?: { title?: string | null; out: OutRow[]; leaders?: { name: string; pct: number }[] | null; support?: { label: string; v: number } | null };
  s3c?: { title?: string | null; in: InRow[]; more?: NV[] | null; ratio?: { out_theme: string; out: number; in: number; text: string } | null; none?: string | null };
  s4?: { doc: string; date?: string | null; stocks: Stock[]; calc?: { expr: string; result: string; lhs?: number; rhs?: number; value?: number; kind?: string; verified?: boolean } | null };
  s5?: { news?: { title: string; source?: string | null; theme?: string | null }[] | null; a: string; b: string;
         verdicts?: { theme: string; side: "a" | "b"; text?: string | null }[] | null; verdict: "a" | "b"; condition: string; limit?: string | null;
         support?: { label: string; value: string } | null; callback?: { a: string; b?: string | null; text?: string | null } | null };
};
const briefOf = (p: Props): Brief => ((p as unknown as { hunter?: Brief }).hunter ?? {});

/** useSteps 위에 얹는 두 가지: 단계 이름이 있을 때만 그 시각(없으면 undefined) · 어느 시각 뒤에 처음 그 말이 나오는 문장 */
const mkFind = (st: ReturnType<typeof useSteps>) => ({
  stepAt: (nm: string) => { const k = st.steps ? st.steps.indexOf(nm) : -1; return k >= 0 && st.list[k] ? st.list[k].start : undefined; },
  sayAfter: (needle: string | RegExp, after: number) => {
    const c = st.list.find((x) => x.start >= after - 0.01 && (typeof needle === "string" ? x.text.includes(needle) : needle.test(x.text)));
    return c ? c.start : undefined;
  },
});

const Chip: React.FC<{ color?: string; solid?: boolean; size?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ color = YEL, solid, size = 30, children, style }) => (
  <span style={{ display: "inline-block", fontSize: size, fontWeight: 900, lineHeight: 1.2, padding: "5px 16px", borderRadius: 12, whiteSpace: "nowrap", boxSizing: "border-box",
    color: solid ? "#0B0E16" : color, background: solid ? color : "rgba(8,11,20,0.72)", border: solid ? "2.5px solid transparent" : `2.5px solid ${color}`,
    boxShadow: solid ? `0 0 20px ${color}88` : `0 0 14px ${color}44`, ...style }}>{children}</span>
);

/* ───────── s3a: 코스닥 수급 3 + 지수 카드 2 → 한 줄 판정 → 어제 보자고 한 숫자(도장) → 그런데 → 체인 질문 ───────── */
export const S3aB: React.FC<SC> = ({ p, cues }) => {
  const h = briefOf(p).s3a;
  const st = useSteps(p, "s3a", cues);
  const { t, at, say, find, q, inQ } = st;
  const { stepAt } = mkFind(st);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const kb = (h.kosdaq?.bars ?? []).slice(0, 3);
  const idx = (h.index ?? []).slice(0, 2);
  const tone = toneOf(idx[0]?.chg_pct ?? h.num ?? 0);
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgMarket tone={tone} dim={0.55} />} />;
  const k0 = at("kosdaq", 0, 0);
  const barAt = kb.map((b, k) => stepAt(`bar:${k}`) ?? say(b.name) ?? k0 + 0.4 + k * 0.3);
  let hiBar = -1;
  kb.forEach((_, k) => { if (t >= barAt[k] && (hiBar < 0 || barAt[k] >= barAt[hiBar])) hiBar = k; });
  const i0 = stepAt("index") ?? say("지수") ?? find(/코스피[^.]*코스닥|코스닥[^.]*코스피/) ?? Math.max(k0, ...barAt) + 3;
  const v0 = stepAt("verdict") ?? find(/받은 날|판 날|산 날|빼고/) ?? i0 + 3;
  const hasP = !!h.promise;
  const p0 = hasP ? stepAt("promise") ?? say("보자고") ?? say("어제") ?? v0 + 3 : 1e9;
  const s0 = hasP ? Math.max(p0, stepAt("stamp") ?? find(/이어졌|끊겼|멈췄|돌아섰|이어짐|끊김/) ?? p0 + 1.0) : 1e9;
  const t0 = stepAt("turn") ?? find(/^그런데/) ?? 1e9;
  const okCol = h.ok ? GREEN : RED;
  const stampS = interpolate(t, [s0, s0 + 0.28], [2.6, 1], { ...CLAMP, easing: ease });
  const stampO = interpolate(t, [s0, s0 + 0.1], [0, 1], CLAMP);
  const BW = 620, BH = 500;
  const vTop = 268 + BH + 20;            // 판정 카드 788
  const cbTop = vTop + 150 + 24;         // 콜백 카드 962
  const vLen = (h.verdict ?? "").length;
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone={tone} dim={0.45} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, display: "flex", alignItems: "center", gap: 18, ...pop(k0) }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH }}>코스닥 수급</div>
        {!hasP && t >= t0 ? <Chip solid size={32} style={pop(t0, 12)}>그런데</Chip> : null}
      </div>
      <div style={{ position: "absolute", left: 64, top: 268 }}>
        {kb.length ? <VBars bars={kb} at={barAt} hi={hiBar} height={BH} cols={3} width={BW} /> : null}
      </div>
      <div style={{ position: "absolute", left: 64 + BW + 24, right: 64, top: 268 }}>
        {idx.map((x, k) => (
          <div key={x.name} style={{ ...pop(i0 + k * 0.25), marginBottom: 20, opacity: t >= i0 ? (pop(i0 + k * 0.25).opacity as number) : 0 }}>
            <Card color={colOf(x.chg_pct)} style={{ padding: "18px 22px" }}>
              <div style={{ fontSize: 32, fontWeight: 800, color: SUBC, letterSpacing: "0.02em" }}>{x.name}</div>
              <div style={{ fontSize: 56, fontWeight: 900, lineHeight: 1.1, marginTop: 4, letterSpacing: "-0.02em", whiteSpace: "nowrap" }}>{fmtIdx(x.close)}</div>
              <div style={{ fontSize: 44, fontWeight: 900, color: colOf(x.chg_pct), marginTop: 4, whiteSpace: "nowrap" }}>{x.chg_pct > 0 ? "▲" : x.chg_pct < 0 ? "▼" : "−"} {Math.abs(x.chg_pct).toFixed(2)}%</div>
            </Card>
          </div>
        ))}
      </div>
      {h.verdict && t >= v0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: vTop, height: 150, ...pop(v0) }}>
          <Card color={PALE} style={{ padding: "18px 28px", boxSizing: "border-box", height: 150, overflow: "hidden" }}>
            <div style={{ fontSize: vLen > 48 ? 36 : 40, fontWeight: 800, lineHeight: 1.35, wordBreak: "keep-all", color: "#FFFFFF" }}>{h.verdict}</div>
          </Card>
        </div>
      ) : null}
      {hasP && t >= p0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: cbTop }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18, ...pop(p0) }}>
            <div style={{ fontSize: 36, fontWeight: 800, color: SUBC, textShadow: SH }}>{h.head || "어제 보자고 한 것"}</div>
            {t >= t0 ? <Chip solid size={32} style={pop(t0, 12)}>그런데</Chip> : null}
          </div>
          <div style={{ position: "relative", marginTop: 12, ...pop(p0 + 0.15) }}>
            <Card color={YEL}>
              <div style={{ fontSize: 50, fontWeight: 900, lineHeight: 1.25, letterSpacing: "-0.02em", wordBreak: "keep-all", paddingRight: 230 }}>{h.promise}</div>
              {h.num != null ? <div style={{ fontSize: 40, fontWeight: 800, marginTop: 12, color: colOf(h.num) }}>오늘 {amt(h.num)} {h.num < 0 ? "순매도" : "순매수"}</div> : null}
            </Card>
            {h.result && t >= s0 ? (
              <div style={{ position: "absolute", right: 12, top: -30, opacity: stampO, transform: `rotate(-12deg) scale(${stampS})`, transformOrigin: "center", fontSize: 68, fontWeight: 900,
                color: okCol, border: `7px solid ${okCol}`, borderRadius: 16, padding: "2px 22px", background: "rgba(5,8,16,0.6)", boxShadow: `0 0 30px ${okCol}88, inset 0 0 18px ${okCol}33`,
                letterSpacing: "0.04em", whiteSpace: "nowrap", lineHeight: 1.2 }}>{h.result}</div>
            ) : null}
          </div>
        </div>
      ) : null}
      {h.changed && t >= t0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: hasP ? cbTop + 250 : cbTop }}>
          <Card color={BLUE} style={{ ...pop(t0), padding: "20px 30px" }}>
            <div style={{ fontSize: 36, fontWeight: 800, color: SUBC }}>{h.changed.label} — {h.changed.before_label || "어제"} <span style={{ color: GREY, textDecoration: "line-through" }}>{h.changed.before}</span></div>
            <div style={{ fontSize: 52, fontWeight: 900, color: "#FFFFFF", marginTop: 6, whiteSpace: "nowrap" }}>오늘 {h.changed.after}</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s3b: 돈이 빠진 곳·정체된 곳 — 유출 가로막대(1위 강조) → 외/기 칩 → N일째·어제 칩 → 그런데 대장주 등락 둘 → 자사주 받침 → 나머지 유출 → 체인 질문 ───────── */
export const S3bB: React.FC<SC> = ({ p, cues }) => {
  const h = briefOf(p).s3b;
  const st = useSteps(p, "s3b", cues);
  const { t, at, say, find, q, inQ } = st;
  const { stepAt } = mkFind(st);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgChip tone="down" dim={0.6} />} />;
  const out = h.out.slice(0, 4);
  const top = out[0];
  const leaders = (h.leaders ?? []).slice(0, 2);
  const r0 = at("row:0", 0, (top ? say(top.theme) : undefined) ?? 0);
  const sp0 = stepAt("split") ?? find(/외국인[^.]*기관|기관[^.]*외국인/) ?? r0 + 2.5;
  const streakN = Math.abs(top?.streak ?? 0);
  const st0 = stepAt("streak") ?? (streakN >= 2 ? find(dRe(streakN)) : undefined) ?? say("어제") ?? sp0 + 2.5;
  const l0 = leaders.length ? stepAt("leaders") ?? stepAt("turn") ?? say(leaders[0].name) ?? find(/^그런데/) ?? st0 + 3 : 1e9;
  const su0 = h.support ? stepAt("support") ?? say(h.support.label) ?? (l0 < 1e9 ? l0 + 3 : st0 + 3) : 1e9;
  // 나머지 유출 행: row:k 단계 → rest 단계(차례로) → 이름을 말하는 문장 → 마지막으로 말한 행 뒤에 차례로(가운데 구멍 금지)
  const rest0 = stepAt("rest");
  const saidAt = out.map((r, k) => (k === 0 ? r0 : stepAt(`row:${k}`) ?? (rest0 != null ? rest0 + 0.3 * (k - 1) : undefined) ?? say(r.theme)));
  const known = saidAt.filter((x): x is number => x != null);
  const lastSaid = known.length ? Math.max(...known) : r0;
  let miss = 0;
  const spokenAt = saidAt.map((s) => (s != null ? s : lastSaid + 0.35 * ++miss));
  // 나머지 행은 1위 행 뒤에 흐리게 미리 서 있다가(자리만) 말하는 문장에 밝아진다 — 칩·대장주 카드가 그 밑에 오므로 빈 구멍을 두지 않는다
  const rowAt = spokenAt.map((s, k) => (k === 0 ? r0 : Math.min(s, r0 + 0.25 * k)));
  const dimUntil = spokenAt.map((s, k) => (k === 0 ? undefined : s));
  const rows: NV[] = out.map((r) => ({ name: r.theme, v: r.v }));
  const rowsTop = 276;
  const chipsTop = rowsTop + out.length * 108 + 8;
  const ldTop = chipsTop + 84;
  const supTop = ldTop + (leaders.length ? 226 : 0);
  const sv = h.support?.v ?? 0;
  const sc = colOf(sv);
  const supGrow = interpolate(t, [su0, su0 + 0.6], [0, 1], { ...CLAMP, easing: ease });
  const supW = Math.max(12, Math.min(1, Math.abs(sv) / Math.max(1, Math.abs(top?.v ?? sv))) * 330) * supGrow;   // 유출 1위 대비 길이(최대 330px)
  return (
    <Shell p={p} cues={cues} bg={<BgChip tone="down" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, ...pop(r0), fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH }}>{h.title || "돈이 빠진 곳"}</div>
      <div style={{ position: "absolute", left: 64, top: rowsTop }}><HBars rows={rows} at={rowAt} hiName={top?.theme} dimUntil={dimUntil} /></div>
      {top ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: chipsTop, height: 64, display: "flex", gap: 12, alignItems: "center" }}>
          {top.foreign != null && t >= sp0 ? <Chip color={colOf(top.foreign)} style={pop(sp0, 12)}>외국인 {sgn(top.foreign)}{amt(top.foreign)}</Chip> : null}
          {top.inst != null && t >= sp0 + 0.2 ? <Chip color={colOf(top.inst)} style={pop(sp0 + 0.2, 12)}>기관 {sgn(top.inst)}{amt(top.inst)}</Chip> : null}
          {dTag(top.streak) && t >= st0 ? <Chip solid style={pop(st0, 12)}>{dTag(top.streak)}</Chip> : null}
          {top.y != null && t >= st0 + 0.2 ? <Chip color={GREY} style={pop(st0 + 0.2, 12)}>어제 {sgn(top.y)}{amt(top.y)}</Chip> : null}
        </div>
      ) : null}
      {leaders.length && t >= l0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: ldTop, ...pop(l0) }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <Chip solid size={30}>그런데</Chip>
            <div style={{ fontSize: 34, fontWeight: 800, color: SUBC, textShadow: SH, whiteSpace: "nowrap" }}>값은 안 빠졌는데 · {top?.theme} 대장주</div>
          </div>
          <div style={{ display: "flex", gap: 20, marginTop: 12 }}>
            {leaders.map((s, k) => (
              <div key={s.name} style={{ flex: 1, ...pop(l0 + 0.2 * k) }}>
                <Card color={colOf(s.pct)} style={{ padding: "14px 26px" }}>
                  <div style={{ fontSize: 40, fontWeight: 900, whiteSpace: "nowrap", overflow: "hidden" }}>{s.name}</div>
                  <div style={{ fontSize: 60, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.1, marginTop: 2, color: colOf(s.pct) }}>{fmtPctS(s.pct)}</div>
                </Card>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {h.support && t >= su0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: supTop, ...pop(su0) }}>
          <Card color={sc} style={{ padding: "16px 28px", display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ width: 170, fontSize: 40, fontWeight: 900, whiteSpace: "nowrap" }}>{h.support.label}</div>
            <div style={{ width: 330, height: 40, position: "relative" }}>
              <div style={{ position: "absolute", left: 0, top: 0, height: 40, width: supW, borderRadius: 8, background: `linear-gradient(90deg, ${sc}, ${sc}AA)`, boxShadow: `0 0 18px ${sc}66` }} />
            </div>
            <div style={{ flex: 1, textAlign: "right", fontSize: 50, fontWeight: 900, color: sc, whiteSpace: "nowrap", textShadow: SH }}>{sgn(sv)}{amt(sv)}</div>
            <Chip solid size={28}>정체</Chip>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s3c: 돈이 들어온 곳 — 유입 가로막대(외국인 빨강 + 기관 호박색) → 강조 행 밑 종목 이름·업종 등락 → 유출 1위 대비 비율 칩 → 체인 질문 ───────── */
type Row2 = { name: string; v: number; foreign?: number | null; inst?: number | null; ret?: number | null; names?: string[] | null; dim?: boolean };
const HBars2: React.FC<{ rows: Row2[]; at: number[]; hi: number; subAt: number[] }> = ({ rows, at, hi, subAt }) => {
  const { t } = useT();
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.v)));
  const BW = 450;
  return (
    <div style={{ width: 952 }}>
      {rows.map((r, k) => {
        const a = at[k] ?? 0;
        const grow = interpolate(t, [a, a + 0.6], [0, 1], { ...CLAMP, easing: ease });
        const op = interpolate(t, [a, a + 0.3], [0, 1], CLAMP);
        const len = Math.max(22, (Math.abs(r.v) / maxAbs) * BW) * grow;
        const lit = hi === k;
        const parts = r.foreign != null && r.inst != null ? [{ v: r.foreign, c: RED }, { v: r.inst, c: AMBER }] : [{ v: r.v, c: colOf(r.v) }];
        const sum = parts.reduce((s, x) => s + Math.abs(x.v), 0) || 1;
        const showSub = lit && t >= (subAt[k] ?? 1e9) && !!(r.names?.length || r.ret != null);
        const subOp = showSub ? interpolate(t, [subAt[k], subAt[k] + 0.35], [0, 1], CLAMP) : 0;
        let x = 0;
        return (
          <div key={`${r.name}-${k}`} style={{ position: "relative", height: 100, opacity: op * (r.dim ? 0.6 : 1), borderRadius: 16, marginBottom: 8, boxSizing: "border-box",
            background: lit ? "rgba(255,216,77,0.12)" : "transparent", boxShadow: lit ? `inset 0 0 0 3px ${YEL}` : "none" }}>
            <div style={{ display: "flex", alignItems: "center", height: 100, padding: "0 16px", transform: `translateY(${-20 * subOp}px)` }}>
              <div style={{ width: 220, fontSize: 44, fontWeight: 800, color: lit ? YEL : "#FFFFFF", textShadow: SH, whiteSpace: "nowrap", overflow: "hidden" }}>{r.name}</div>
              <div style={{ width: BW, position: "relative", height: 44 }}>
                {parts.map((pt, i) => {
                  const w = (Math.abs(pt.v) / sum) * len; const left = x; x += w;
                  const c = pt.v < 0 ? BLUE : pt.c;
                  const rad = parts.length === 1 ? "8px" : i === 0 ? "8px 0 0 8px" : "0 8px 8px 0";
                  return <div key={i} style={{ position: "absolute", left, top: 0, height: 44, width: w, borderRadius: rad, background: `linear-gradient(90deg, ${c}, ${c}CC)`, boxShadow: `0 0 18px ${c}55` }} />;
                })}
              </div>
              <div style={{ flex: 1, textAlign: "right", fontSize: 50, fontWeight: 900, color: colOf(r.v), textShadow: SH, whiteSpace: "nowrap" }}>{sgn(r.v)}{amt(r.v)}</div>
            </div>
            {showSub ? (
              <div style={{ position: "absolute", left: 16, right: 16, bottom: 6, opacity: subOp, display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{ flex: 1, fontSize: 28, fontWeight: 700, color: SUBC, textShadow: SH, whiteSpace: "nowrap", overflow: "hidden", lineHeight: 1.15 }}>{(r.names ?? []).slice(0, 4).join(" · ")}</div>
                {r.ret != null ? <span style={{ fontSize: 28, fontWeight: 900, color: colOf(r.ret), whiteSpace: "nowrap", textShadow: SH }}>업종 {fmtPctS(r.ret)}</span> : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
};

export const S3cB: React.FC<SC> = ({ p, cues }) => {
  const h = briefOf(p).s3c;
  const st = useSteps(p, "s3c", cues);
  const { t, at, say, find, q, inQ } = st;
  const { stepAt } = mkFind(st);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  if (inQ && q) return <QOnly p={p} cues={cues} q={q} bg={<BgChip tone="up" dim={0.6} />} />;
  const ins = (h.in ?? []).slice(0, 2);
  const more = (h.more ?? []).slice(0, 2);
  const m0 = at("move", 0, 0);
  // 단계 이름은 narrate 가 t1/t2(업종)·names(종목 이름)로 준다. row:k/names:k 는 예전 이름이라 둘 다 본다.
  // say(theme) 로 떨어지면 "이차전지와 로봇입니다" 같은 도입 문장에 둘째 업종까지 걸려 말보다 먼저 켜진다(9/15 실측) — 그래서 단계 이름이 먼저다.
  const inAt = ins.map((r, k) => stepAt(`row:${k}`) ?? stepAt(k === 0 ? "t1" : "t2") ?? (k === 0 ? say(r.theme) : undefined) ?? m0 + 1 + k * 4);
  const subAt = ins.map((r, k) => stepAt(`names:${k}`) ?? (k === 0 ? stepAt("names") : undefined) ?? (r.names?.[0] ? say(r.names[0]) : undefined) ?? inAt[k] + 2.5);
  const lastIn = Math.max(m0, ...inAt, ...subAt);
  const moreAt = more.map((r, k) => stepAt(`more:${k}`) ?? say(r.name) ?? lastIn + 0.3 * (k + 1));
  const ratio = h.ratio ?? null;
  const r0 = ratio ? stepAt("ratio") ?? say(ratio.text) ?? find(/분의|전부 유출/) ?? lastIn + 3 : 1e9;
  let hi = -1;
  ins.forEach((_, k) => { if (t >= inAt[k] && (hi < 0 || inAt[k] >= inAt[hi])) hi = k; });
  const rows: Row2[] = [...ins.map((r) => ({ name: r.theme, v: r.v, foreign: r.foreign, inst: r.inst, ret: r.ret, names: r.names })), ...more.map((m) => ({ name: m.name, v: m.v, dim: true }))];
  const rowAt = [...inAt, ...moreAt];
  const split = ins.some((r) => r.foreign != null && r.inst != null);
  const title = h.title || (ins.length ? "돈이 들어온 곳" : "들어온 곳이 없었습니다");
  const ratioTop = 276 + rows.length * 108 + 16;
  const rg = interpolate(t, [r0, r0 + 0.7], [0, 1], { ...CLAMP, easing: ease });
  const inFrac = ratio ? Math.min(1, Math.abs(ratio.in) / Math.max(1, Math.abs(ratio.out))) : 0;
  const inLabel = ins.length === 2 ? "두 곳에 들어온 돈" : ins.length === 1 ? `${ins[0].theme}에 들어온 돈` : "들어온 돈";
  return (
    <Shell p={p} cues={cues} bg={<BgChip tone="up" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, display: "flex", alignItems: "center", gap: 16, ...pop(m0) }}>
        <div style={{ flex: 1, fontSize: 44, fontWeight: 800, color: SUBC, textShadow: SH, whiteSpace: "nowrap", overflow: "hidden" }}>{title}</div>
        {split ? (
          <div style={{ display: "flex", gap: 14, alignItems: "center", fontSize: 28, fontWeight: 800, color: SUBC, textShadow: SH, whiteSpace: "nowrap" }}>
            <span style={{ display: "inline-block", width: 26, height: 26, borderRadius: 6, background: RED, marginRight: -4 }} /><span>외국인</span>
            <span style={{ display: "inline-block", width: 26, height: 26, borderRadius: 6, background: AMBER, marginRight: -4 }} /><span>기관</span>
          </div>
        ) : null}
      </div>
      {h.none && !ins.length ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 276, ...pop(m0 + 0.2) }}>
          <Card color={PALE}><div style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.35, wordBreak: "keep-all" }}>{h.none}</div></Card>
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, top: 276 }}><HBars2 rows={rows} at={rowAt} hi={hi} subAt={subAt} /></div>
      {ratio && t >= r0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: ratioTop, ...pop(r0) }}>
          <Card color={YEL} style={{ padding: "18px 28px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: GREY, whiteSpace: "nowrap", overflow: "hidden" }}>{ratio.out_theme}에서 나간 돈</div>
                <div style={{ fontSize: 54, fontWeight: 900, color: colOf(ratio.out), lineHeight: 1.1, whiteSpace: "nowrap", textShadow: SH }}>{sgn(ratio.out)}{amt(ratio.out)}</div>
              </div>
              <Chip solid size={40} style={{ padding: "8px 22px", ...pop(r0 + 0.3, 10) }}>{ratio.text}</Chip>
              <div style={{ flex: 1, minWidth: 0, textAlign: "right" }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: GREY, whiteSpace: "nowrap", overflow: "hidden" }}>{inLabel}</div>
                <div style={{ fontSize: 54, fontWeight: 900, color: colOf(ratio.in), lineHeight: 1.1, whiteSpace: "nowrap", textShadow: SH }}>{sgn(ratio.in)}{amt(ratio.in)}</div>
              </div>
            </div>
            <div style={{ marginTop: 14, position: "relative", height: 14, borderRadius: 7, background: "rgba(255,255,255,0.08)" }}>
              <div style={{ position: "absolute", left: 0, top: 0, height: 14, borderRadius: 7, width: `${100 * rg}%`, background: `linear-gradient(90deg, ${BLUE}, ${BLUE}AA)` }} />
              <div style={{ position: "absolute", left: 0, top: 0, height: 14, borderRadius: 7, width: Math.max(10, 896 * inFrac) * rg, background: RED, boxShadow: `0 0 16px ${RED}` }} />
            </div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s4: 1차 자료 한 칸 — 키움 종목별 투자자 표(종목 2행 × 등락/외국인/기관/개인/거래대금) + 말하는 칸 강조 + 주도 칩 + 검산 계산식 타자 ───────── */
type ColKey = "pct" | "foreign" | "inst" | "indiv" | "value";
const COLS: { key: ColKey; label: string; w: number; re: RegExp }[] = [
  { key: "pct", label: "등락", w: 128, re: /%|올랐|내렸|상한가|하한가/ },
  { key: "foreign", label: "외국인", w: 128, re: /외국인/ },
  { key: "inst", label: "기관", w: 128, re: /기관/ },
  { key: "indiv", label: "개인", w: 128, re: /개인/ },
  { key: "value", label: "거래대금", w: 148, re: /거래대금|거래된/ },
];
export const S4B: React.FC<SC> = ({ p, cues }) => {
  const h = briefOf(p).s4;
  const st = useSteps(p, "s4", cues);
  const { t, cur, at, say } = st;
  const { stepAt, sayAfter } = mkFind(st);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const stocks = h.stocks.slice(0, 2);
  const d0 = at(["doc", "open"], 0, 0);
  const rowAt = stocks.map((s, k) => stepAt(`row:${k}`) ?? say(s.name) ?? d0 + 1.5 + k * 4);
  const drvAt = stocks.map((s, k) => (s.driver ? stepAt(`driver:${k}`) ?? sayAfter(/밀어|주도|큰손/, rowAt[k]) ?? rowAt[k] + 2.5 : 1e9));
  const c0 = h.calc ? stepAt("calc") ?? say("검산") ?? say("나누") ?? say("나눠") ?? Math.max(d0, ...rowAt) + 6 : 1e9;
  let active = -1;
  stocks.forEach((_, k) => { if (t >= rowAt[k] && (active < 0 || rowAt[k] >= rowAt[active])) active = k; });
  // 검산 문장에서는 계산에 쓴 숫자(lhs·rhs)가 든 행으로 강조를 옮긴다(둘째 종목을 말한 뒤 첫 종목으로 검산하는 날). % 칸은 검산 결과라 켜지 않는다
  const inCalc = !!h.calc && t >= c0;
  if (inCalc && h.calc) {
    const { lhs, rhs } = h.calc;
    const m = stocks.findIndex((s) => [s.foreign, s.inst, s.indiv, s.value].some((v) => v != null && (Math.abs(v) === lhs || Math.abs(v) === rhs)));
    if (m >= 0) active = m;
  }
  const curText = cur?.text ?? "";
  const litKeys = active >= 0 ? COLS.filter((c) => (!inCalc || c.key !== "pct") && c.re.test(curText)).map((c) => c.key) : [];
  const full = h.calc ? `${h.calc.expr} = ${h.calc.result}` : "";
  const nCh = Math.max(0, Math.floor((t - c0) / 0.06));
  const typed = full.slice(0, nCh);
  const typing = t >= c0 && nCh < full.length;
  const caret = typing && Math.floor(t * 5) % 2 === 0;
  const tableTop = 350, HEAD = 56, ROW = 150;
  const calcTop = tableTop + HEAD + stocks.length * ROW + 30;
  const cellText = (s: Stock, key: ColKey) => {
    const v = s[key];
    if (v == null) return "—";
    return key === "pct" ? fmtPct2(v) : fmtRaw(v);
  };
  const cellCol = (s: Stock, key: ColKey) => (key === "value" ? "#E6E6E3" : colOf(s[key] ?? 0));
  return (
    <Shell p={p} cues={cues} badge="1차 자료" bg={<BgChip tone="neutral" dim={0.62} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, ...pop(d0) }}>
        <span style={{ display: "inline-block", fontSize: 36, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "6px 20px", borderRadius: 12 }}>직접 열어봤습니다</span>
        <div style={{ fontSize: 34, fontWeight: 700, color: SUBC, marginTop: 12, wordBreak: "keep-all", textShadow: SH, whiteSpace: "nowrap", overflow: "hidden" }}>{h.doc}<span style={{ color: GREY }}> · 단위 억 원</span></div>
      </div>
      <div style={{ position: "absolute", left: 64, right: 64, top: tableTop, ...pop(d0 + 0.3) }}>
        <div style={{ background: "rgba(14,18,30,0.92)", border: "2px solid rgba(255,255,255,0.28)", borderRadius: 10, overflow: "hidden", boxShadow: "0 10px 40px rgba(0,0,0,0.6)" }}>
          <div style={{ display: "flex", alignItems: "center", padding: "0 16px", height: HEAD, boxSizing: "border-box", borderBottom: "2px solid rgba(255,255,255,0.28)", background: "rgba(255,255,255,0.06)",
            fontSize: 26, fontWeight: 800, color: GREY, letterSpacing: "0.04em" }}>
            <div style={{ flex: 1 }}>종목</div>
            {COLS.map((c) => <div key={c.key} style={{ width: c.w, textAlign: "right" }}>{c.label}</div>)}
          </div>
          {stocks.map((s, k) => {
            const on = t >= rowAt[k];
            const isA = active === k;
            return (
              <div key={s.name} style={{ display: "flex", alignItems: "center", padding: "0 16px", height: ROW, boxSizing: "border-box", borderBottom: k < stocks.length - 1 ? `1px solid ${LINE}` : "none", opacity: on ? 1 : 0.45 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 26, fontWeight: 800, color: isA ? YEL : GREY, whiteSpace: "nowrap" }}>{s.role}{s.theme ? ` · ${s.theme}` : ""}</div>
                  <div style={{ fontSize: 36, fontWeight: 900, lineHeight: 1.15, marginTop: 4, color: isA ? "#FFFFFF" : SUBC, whiteSpace: "nowrap", overflow: "hidden" }}>{s.name}</div>
                  <div style={{ height: 40, marginTop: 6 }}>
                    {s.driver && t >= drvAt[k] ? <Chip solid size={24} style={{ padding: "3px 12px", ...pop(drvAt[k], 10) }}>주도 · {s.driver}</Chip> : null}
                  </div>
                </div>
                {COLS.map((c) => {
                  const lit = isA && litKeys.includes(c.key);
                  const v = s[c.key];
                  return (
                    <div key={c.key} style={{ width: c.w, textAlign: "right", padding: "4px 8px", boxSizing: "border-box", borderRadius: 8,
                      boxShadow: lit ? `0 0 0 3px ${YEL}, 0 0 22px rgba(255,216,77,0.45)` : "none", background: lit ? "rgba(255,216,77,0.12)" : "transparent" }}>
                      <div style={{ fontSize: 38, fontWeight: 900, lineHeight: 1.1, color: lit ? cellCol(s, c.key) : on ? cellCol(s, c.key) : SUBC, whiteSpace: "nowrap" }}>{cellText(s, c.key)}</div>
                      {/* 강조 칸 아래 '= 말한 숫자': 원본 413 과 말의 '410억' 을 잇는다(100억 미만은 말과 같아 생략) */}
                      <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1, marginTop: 2, color: GREY, whiteSpace: "nowrap", height: 24 }}>{lit && c.key !== "pct" && v != null && Math.abs(v) >= 100 ? `= ${spoken(v)}` : ""}</div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
      {h.calc && t >= c0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: calcTop, ...pop(c0) }}>
          <Card color={YEL}>
            <div style={{ fontSize: 32, fontWeight: 800, color: SUBC }}>검산 하나{h.calc.kind === "share" ? " · 주도 주체 순매수 ÷ 거래대금" : h.calc.kind === "ratio" ? " · 큰손 합 ÷ 개인 순매도" : ""}</div>
            <div style={{ fontSize: Math.min(72, Math.floor(1400 / Math.max(1, full.length))), fontWeight: 900, color: YEL, letterSpacing: "-0.02em", lineHeight: 1.15, marginTop: 8, whiteSpace: "nowrap", textShadow: "0 0 26px rgba(255,216,77,0.35)" }}>{typed}{caret ? "▌" : ""}</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── s5: 뉴스와 맞물렸나 — 뉴스 카드 ≤2 → 양면 카드(뉴스가 올린 값 / 돈이 올린 값) + 업종별 판정 칩 → 뒤집히는 조건 → S0 숫자 콜백 → 한계
 *  세로 자리 고정: 머리글 214 · 뉴스 266/462 · 양면 658 · 조건 910 · 콜백 1112 · 한계 1190 ───────── */
export const S5B: React.FC<SC> = ({ p, cues }) => {
  const h = briefOf(p).s5;
  const st = useSteps(p, "s5", cues);
  const { t, at, say, find } = st;
  const { stepAt, sayAfter } = mkFind(st);
  const pop = usePop();
  if (!h) return <Empty p={p} sub="" cues={cues} />;
  const news = (h.news ?? []).slice(0, 2);
  const nAt = news.map((n, k) => stepAt(`news:${k}`) ?? (n.theme ? say(n.theme) : undefined) ?? k * 3.5);
  const n0 = news.length ? Math.min(...nAt) : at("news", 0, 0);
  const verdicts = (h.verdicts ?? []).slice(0, 2);
  // 양면 프레임 문장(a·b)이 길이 예산으로 빠진 날: 두 칸은 늦어도 첫 판정 문장 직전에 다 서 있어야 한다(판정 칩이 빈 칸에 붙지 않게)
  const vSteps = verdicts.map((_, k) => stepAt(`verdict:${k}`)).filter((x): x is number => x != null);
  const vCap = vSteps.length ? Math.min(...vSteps) - 0.3 : 1e9;
  const a0 = stepAt("a") ?? stepAt("A") ?? say(h.a) ?? say("뉴스가 올린") ?? Math.min(vCap, news.length ? Math.max(...nAt) + 4 : 3);
  const b0 = stepAt("b") ?? stepAt("B") ?? say(h.b) ?? say("돈이 올린") ?? Math.min(vCap, a0 + 3);
  const vAt = verdicts.map((v, k) => stepAt(`verdict:${k}`) ?? sayAfter(v.theme, b0) ?? b0 + 3 + k * 3);
  const v0 = stepAt("verdict") ?? (vAt.length ? Math.min(...vAt) : sayAfter("쪽입니다", b0) ?? b0 + 3);
  const c0 = stepAt("condition") ?? say("뒤집") ?? (vAt.length ? Math.max(...vAt) : v0) + 3;
  const cb = h.callback ?? null;
  const k0 = cb ? stepAt("callback") ?? sayAfter(cb.a, b0) ?? c0 + 3 : 1e9;
  const l0 = h.limit ? stepAt("limit") ?? say("한계") ?? sayAfter(/보이지 않|안 보입|없습니다\.$/, c0 + 0.1) ?? Math.max(c0, k0 < 1e9 ? k0 : 0) + 3 : 1e9;
  const decided = t >= v0;
  const glow = interpolate(t, [v0, v0 + 0.5], [0, 1], { ...CLAMP, easing: ease });
  const cards: { k: "a" | "b"; text: string; sub: string; at: number }[] = [
    { k: "a", text: h.a, sub: "큰손 돈은 작다", at: a0 }, { k: "b", text: h.b, sub: "외국인·기관이 같이 산다", at: b0 }];
  const cbAnswer = cb ? (cb.text || cb.b || "") : "";
  const cbSize = Math.max(26, Math.min(40, Math.floor(600 / Math.max(1, cbAnswer.length))));
  const NT = 266, NH = 184, NG = 12, ABT = NT + 2 * (NH + NG), ABH = 232, CT = ABT + ABH + 20, KT = CT + 200, LT = KT + 78;
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.5} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 214, ...pop(Math.min(n0, a0)), fontSize: 40, fontWeight: 800, color: SUBC, textShadow: SH }}>뉴스와 맞물렸나</div>
      {news.length ? news.map((n, k) => (
        t >= nAt[k] ? (
          <div key={k} style={{ position: "absolute", left: 64, right: 64, top: NT + k * (NH + NG), ...pop(nAt[k]) }}>
            <Card color={PALE} style={{ padding: "16px 26px", height: NH, boxSizing: "border-box", overflow: "hidden" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                {n.theme ? <Chip size={24} style={{ padding: "3px 12px" }}>{n.theme}</Chip> : <span />}
                <span style={{ fontSize: 26, fontWeight: 700, color: GREY, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.source ?? ""}</span>
              </div>
              <div style={{ fontSize: 34, fontWeight: 800, lineHeight: 1.3, marginTop: 10, wordBreak: "keep-all", overflow: "hidden", maxHeight: 88 }}>{n.title}</div>
            </Card>
          </div>
        ) : null
      )) : (
        <div style={{ position: "absolute", left: 64, right: 64, top: NT, ...pop(n0) }}>
          <Card color={GREY} style={{ padding: "18px 26px" }}><div style={{ fontSize: 38, fontWeight: 800, color: SUBC }}>뉴스 없이 수급만 움직인 날</div></Card>
        </div>
      )}
      <div style={{ position: "absolute", left: 64, right: 64, top: ABT, display: "flex", gap: 24, alignItems: "stretch" }}>
        {cards.map((c) => {
          const win = decided && h.verdict === c.k;
          const ps = pop(c.at);
          const mine = verdicts.map((v, i) => ({ v, i })).filter((x) => x.v.side === c.k);
          return (
            <div key={c.k} style={{ flex: 1, display: "flex", ...ps }}>
              <Card color={win ? GREEN : PALE} style={{ flex: 1, padding: "18px 24px", height: ABH, boxSizing: "border-box", boxShadow: win ? `0 0 ${34 + 30 * glow}px ${GREEN}AA, inset 0 0 22px ${GREEN}33` : undefined }}>
                <Chip solid color={win ? GREEN : SUBC} size={26} style={{ padding: "3px 14px" }}>{win ? "오늘은 이쪽" : c.k.toUpperCase()}</Chip>
                <div style={{ fontSize: 44, fontWeight: 900, lineHeight: 1.2, letterSpacing: "-0.02em", wordBreak: "keep-all", marginTop: 10, color: win ? "#FFFFFF" : "#E6E6E3", whiteSpace: "nowrap", overflow: "hidden" }}>{c.text}</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: SUBC, marginTop: 4, whiteSpace: "nowrap", overflow: "hidden" }}>{c.sub}</div>
                <div style={{ display: "flex", gap: 10, marginTop: 12, minHeight: 46, flexWrap: "nowrap", overflow: "hidden" }}>
                  {mine.map(({ v, i }) => (t >= vAt[i] ? <Chip key={v.theme} solid size={28} style={pop(vAt[i], 10)}>{v.theme}</Chip> : null))}
                </div>
              </Card>
            </div>
          );
        })}
      </div>
      {t >= c0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: CT }}>
          <Card color={YEL} style={{ ...pop(c0), padding: "18px 30px" }}>
            <div style={{ fontSize: 32, fontWeight: 800, color: YEL }}>이 판정이 뒤집히는 조건</div>
            <div style={{ fontSize: h.condition.length > 30 ? 36 : 40, fontWeight: 800, lineHeight: 1.35, wordBreak: "keep-all", marginTop: 6, maxHeight: 110, overflow: "hidden" }}>{h.condition}</div>
          </Card>
        </div>
      ) : null}
      {cb && t >= k0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: KT, display: "flex", alignItems: "center", gap: 16, ...pop(k0) }}>
          <Chip solid size={30} style={{ padding: "6px 18px" }}>처음 숫자 · {cb.a}</Chip>
          <span style={{ fontSize: 40, fontWeight: 900, color: YEL, textShadow: SH }}>→</span>
          <span style={{ fontSize: cbSize, fontWeight: 900, color: "#FFFFFF", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", textShadow: SH, flex: 1 }}>{cbAnswer}</span>
        </div>
      ) : null}
      {h.limit && t >= l0 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: LT, ...pop(l0), fontSize: 34, fontWeight: 600, color: GREY, lineHeight: 1.4, wordBreak: "keep-all", textShadow: SH }}>한계 · {h.limit}</div>
      ) : null}
    </Shell>
  );
};

export const BRIEF_COMP: Record<string, React.FC<SC>> = { s0: S0H, s1: S1H, s2: S2H, s3a: S3aB, s3b: S3bB, s3c: S3cB, s4: S4B, s5: S5B, s6: S6H };
