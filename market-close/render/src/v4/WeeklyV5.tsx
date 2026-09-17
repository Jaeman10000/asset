/** 주간 결산 v2 화면(토요일 w0~w6, JJ 2026-09-17) — 월~일 표를 w2~w5 가 같이 쓰고, 말하는 요일 줄을 밝힌다.
 * props = computed_weekly.json(days_detail · parked · history · inv · kospi · themes) + props_extra(riser_says).
 * 색: 한국식 — 빨강 = 순매수·상승, 파랑 = 순매도·하락, 노랑 = 질문·지금 말하는 줄. 화면을 말로 설명하지 않는다(말에 맞춰 켜질 뿐). */
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { FONT, FOOTER } from "../tokens";
import type { Props } from "../types";
import type { Cue } from "../Scenes";

const ease = Easing.out(Easing.cubic);
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const RED = "#FF4D4D";
const BLUE = "#3D7BFF";
const YEL = "#FFD84D";
const SUBC = "#B8C2D6";
const SH = "0 3px 14px rgba(0,0,0,0.85)";
const SH_Q = "0 0 30px rgba(255,216,77,0.35), 0 6px 26px rgba(0,0,0,0.8)";

type Out = { theme: string; net: number; foreign: number; inst: number; indiv?: number | null };
type In = Out & { top_stocks?: { name: string; fi: number; ret?: number | null }[] };
type Riser = { name: string; theme?: string; ret: number; foreign: number; inst: number; indiv?: number | null; verdict: { side: string; fi: number } };
type Day = { d: string; wd: string; kospi_pct?: number | null; kosdaq_pct?: number | null; outs: Out[]; ins: In[]; inst_ins?: { theme: string; inst: number }[]; risers: Riser[] };
type Park = { theme: string; net: number; top_stocks?: { name: string }[]; days_in?: number; last_wd?: string };
type Hist = { theme: string; basis: string; since: string; n: number; cont: number; next_top?: [string, number][] };
type W2 = { days_detail?: Day[]; parked?: Park; history?: Hist; inv?: { week?: Record<string, number> }; kospi?: { week_chg_pct?: number | null }; week_start?: string; week_end?: string;
  themes?: { week?: { theme: string; net: number }[] }; riser_says?: Record<string, { name: string; reason?: string }> };
const wk = (p: Props) => p as unknown as W2;

const useT = () => { const f = useCurrentFrame(); const { fps } = useVideoConfig(); return { f, fps, t: f / fps }; };
const usePop = () => {
  const { f, fps } = useT();
  return (sec: number, dy = 24) => {
    const x = interpolate(f, [sec * fps, (sec + 0.4) * fps], [0, 1], { ...CLAMP, easing: ease });
    return { opacity: x, transform: `translateY(${(1 - x) * dy}px)` } as React.CSSProperties;
  };
};
const short = (v: number) => {
  const a = Math.abs(v);
  if (a >= 10000) return `${(Math.round(a / 1000) / 10).toFixed(1).replace(/\.0$/, "")}조`;
  return `${(a >= 1000 ? Math.round(a / 100) * 100 : Math.round(a / 10) * 10).toLocaleString("ko-KR")}억`;
};
const sgn = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");
const col = (v?: number | null) => (v == null || v === 0 ? "#E6E6E3" : v > 0 ? RED : BLUE);
const pct = (v?: number | null) => (v == null ? "" : `${sgn(v)}${Math.abs(v).toFixed(2)}%`);
const md = (d?: string) => (d && d.length >= 8 ? `${+d.slice(4, 6)}/${+d.slice(6, 8)}` : "");
const WDS = ["월", "화", "수", "목", "금", "토", "일"];

const Logo: React.FC<{ scale?: number }> = ({ scale = 1 }) => (
  <div style={{ transform: `scale(${scale})`, transformOrigin: "left top" }}>
    <div style={{ fontFamily: FONT, fontWeight: 900, fontSize: 60, color: "#FFFFFF", transform: "skewX(-10deg)", letterSpacing: "-0.05em", lineHeight: 1, textShadow: "0 3px 16px rgba(0,0,0,0.7)" }}>누가샀나</div>
    <svg width="220" height="24" viewBox="0 0 220 24" style={{ display: "block", marginTop: 2 }}>
      <path d="M3 15 C 46 7, 120 3, 216 8 L 213 14 C 150 11, 90 13, 40 17 C 25 18, 12 20, 5 21 Z" fill="#E8362F" />
    </svg>
  </div>
);
const Card: React.FC<{ color: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ color, children, style }) => (
  <div style={{ border: `2.5px solid ${color}`, borderRadius: 22, background: "linear-gradient(180deg, rgba(10,14,26,0.88), rgba(6,9,18,0.94))",
    boxShadow: `0 0 30px ${color}55, inset 0 0 20px ${color}22`, padding: "22px 30px", ...style }}>{children}</div>
);
const Shell: React.FC<{ p: Props; cues?: Cue[]; bg?: string; hideSub?: boolean; children: React.ReactNode }> = ({ p, cues, bg = "city_neutral", hideSub, children }) => {
  const { t } = useT();
  const w = wk(p);
  const c = !hideSub && cues ? cues.find((x) => t >= x.start && t < x.end + 0.5) : undefined;
  return (
    <AbsoluteFill style={{ background: "#05070D", fontFamily: FONT, color: "#FFFFFF", fontVariantNumeric: "tabular-nums" }}>
      <AbsoluteFill><Img src={staticFile(`bg/${bg}.jpg`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /><AbsoluteFill style={{ background: "rgba(3,5,10,0.55)" }} /></AbsoluteFill>
      <div style={{ position: "absolute", left: 64, top: 64 }}><Logo /></div>
      <div style={{ position: "absolute", right: 64, top: 70, textAlign: "right", fontWeight: 800, lineHeight: 1.15, textShadow: SH }}>
        <div style={{ fontSize: 32, color: "#E6E6E3" }}>주간 결산</div>
        <div style={{ fontSize: 44 }}>{md(w.week_start)}–{md(w.week_end)}</div>
      </div>
      {children}
      {c ? <div style={{ position: "absolute", left: 64, right: 64, bottom: 128, fontSize: 40, fontWeight: 600, lineHeight: 1.42, color: "#F2F2F0", wordBreak: "keep-all", textShadow: "0 2px 8px rgba(0,0,0,0.95)" }}>{c.text}</div> : null}
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 52, fontSize: 26, color: "rgba(230,230,227,0.55)" }}>{FOOTER}</div>
    </AbsoluteFill>
  );
};
const cueAt = (cues: Cue[] | undefined, re: RegExp) => { const c = (cues ?? []).find((x) => re.test(x.text)); return c ? c.start : undefined; };

/* ───────── w0 훅: 한 주 내내 빠진 업종 ↔ 마지막 날 머문 업종 ───────── */
export const V0: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const w = wk(p);
  const pop = usePop();
  const dd = w.days_detail ?? [];
  const outs = dd.map((x) => x.outs?.[0]?.theme).filter(Boolean) as string[];
  const main = outs.length ? outs.sort((a, b) => outs.filter((x) => x === b).length - outs.filter((x) => x === a).length)[0] : "";
  const n = dd.filter((x) => x.outs?.[0]?.theme === main).length;
  const net = (w.themes?.week ?? []).find((x) => x.theme === main)?.net ?? 0;
  const park = w.parked;
  const b0 = cueAt(cues, /머문 곳/) ?? 2.6;
  return (
    <Shell p={p} cues={cues} hideSub bg="chip_down">
      <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(0.05) }}>
        <div style={{ fontSize: 58, fontWeight: 800, textShadow: SH }}>이번 주 {main}</div>
        <div style={{ fontSize: 132, fontWeight: 900, color: BLUE, letterSpacing: "-0.04em", textShadow: SH }}>{n}일 내내 빠짐</div>
        <div style={{ fontSize: 96, fontWeight: 900, color: BLUE, textShadow: SH }}>{sgn(net)}{short(net)}</div>
      </div>
      {park ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 900, ...pop(b0) }}>
          <div style={{ fontSize: 58, fontWeight: 800, textShadow: SH }}>{park.last_wd}요일 돈이 머문 곳</div>
          <div style={{ fontSize: 150, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: SH_Q }}>{park.theme}</div>
          <div style={{ fontSize: 80, fontWeight: 900, color: RED, textShadow: SH }}>+{short(park.net)}</div>
        </div>
      ) : null}
    </Shell>
  );
};

/* ───────── w1 질문 ───────── */
export const V1: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const pop = usePop();
  return (
    <Shell p={p} cues={cues} hideSub bg="market_neutral">
      <div style={{ position: "absolute", left: 64, right: 64, top: 420, ...pop(0.05, 30) }}>
        <div style={{ fontSize: 76, fontWeight: 900, textShadow: SH }}>한 주 동안 돈은</div>
        <div style={{ fontSize: 118, fontWeight: 900, color: YEL, lineHeight: 1.12, letterSpacing: "-0.04em", textShadow: SH_Q, wordBreak: "keep-all" }}>어디서 빠져 어디에 머물렀을까?</div>
        <div style={{ display: "flex", gap: 18, marginTop: 70 }}>
          {WDS.map((d, i) => (
            <div key={d} style={{ ...pop(0.6 + i * 0.12), width: 118, height: 118, borderRadius: 20, border: `2.5px solid ${i < 5 ? YEL : "rgba(230,230,227,0.3)"}`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 56, fontWeight: 900, color: i < 5 ? "#FFFFFF" : "rgba(230,230,227,0.4)" }}>{d}</div>
          ))}
        </div>
      </div>
    </Shell>
  );
};

/* ───────── 월~일 표(w2~w5) ───────── */
const ROW = 138;
const Table: React.FC<{ w: W2; active: number; reveal: number; allOn: boolean }> = ({ w, active, reveal, allOn }) => {
  const pop = usePop();
  const byWd: Record<string, Day> = {};
  (w.days_detail ?? []).forEach((x) => { byWd[x.wd] = x; });
  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: 236 }}>
      <div style={{ display: "flex", fontSize: 26, fontWeight: 800, color: SUBC, padding: "0 18px 8px" }}>
        <div style={{ width: 150 }}>요일·코스피</div><div style={{ width: 440 }}>돈이 빠진 곳</div><div style={{ flex: 1 }}>돈이 들어온 곳</div>
      </div>
      {WDS.map((wd, i) => {
        const x = byWd[wd];
        const on = allOn || i === active;
        const o = x?.outs?.[0];
        const inn = x?.ins?.[0];
        return (
          <div key={wd} style={{ ...pop(reveal + i * 0.08, 14), height: ROW - 10, marginBottom: 10, borderRadius: 16, padding: "10px 18px", display: "flex", alignItems: "center",
            border: `2.5px solid ${i === active ? YEL : "rgba(255,255,255,0.14)"}`, background: i === active ? "rgba(40,34,8,0.78)" : "rgba(8,11,20,0.78)",
            boxShadow: i === active ? `0 0 26px ${YEL}55` : undefined, opacity: x ? (on ? 1 : 0.5) : 0.32 }}>
            <div style={{ width: 150 }}>
              <div style={{ fontSize: 54, fontWeight: 900, lineHeight: 1 }}>{wd}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: col(x?.kospi_pct), marginTop: 6 }}>{x ? pct(x.kospi_pct) : "휴장"}</div>
            </div>
            <div style={{ width: 440, overflow: "hidden", paddingRight: 14, boxSizing: "border-box" }}>
              {o ? (
                <>
                  <div style={{ fontSize: 38, fontWeight: 900, whiteSpace: "nowrap" }}>{o.theme} <span style={{ color: BLUE }}>{sgn(o.net)}{short(o.net)}</span></div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: SUBC, marginTop: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "clip" }}>
                    외 <span style={{ color: col(o.foreign) }}>{sgn(o.foreign)}{short(o.foreign)}</span> · 기 <span style={{ color: col(o.inst) }}>{sgn(o.inst)}{short(o.inst)}</span>
                    {o.indiv != null ? <> · 개 <span style={{ color: col(o.indiv) }}>{sgn(o.indiv)}{short(o.indiv)}</span></> : null}
                  </div>
                </>
              ) : <div style={{ fontSize: 30, color: SUBC }}>{x ? "—" : ""}</div>}
            </div>
            <div style={{ flex: 1, overflow: "hidden", borderLeft: "1px solid rgba(255,255,255,0.12)", paddingLeft: 16 }}>
              {inn ? (
                <>
                  <div style={{ fontSize: 38, fontWeight: 900, whiteSpace: "nowrap" }}>{inn.theme} <span style={{ color: RED }}>+{short(inn.net)}</span></div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: "#F2D9D5", marginTop: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{(inn.top_stocks ?? []).map((s) => s.name).join(" · ")}</div>
                </>
              ) : x?.inst_ins?.length ? (
                <>
                  <div style={{ fontSize: 30, fontWeight: 800, color: SUBC }}>들어온 업종 없음</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: "#F2D9D5", marginTop: 4 }}>기관만 {x.inst_ins[0].theme} +{short(x.inst_ins[0].inst)}</div>
                </>
              ) : <div style={{ fontSize: 30, color: SUBC }}>{x ? "들어온 업종 없음" : ""}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const VERD: Record<string, string> = { money: "실제로 돈이 들어온 상승", half: "한쪽 돈만 들어온 상승", indiv: "개인이 끌어올린 상승", small: "큰돈이 만든 상승은 아님", down: "" };

const DayScene: React.FC<{ p: Props; cues?: Cue[]; days: string[]; allOn?: boolean; withPark?: boolean }> = ({ p, cues, days, allOn, withPark }) => {
  const w = wk(p);
  const { t } = useT();
  const pop = usePop();
  const list = cues ?? [];
  // 지금 말하는 요일: 지금까지 나온 문장 가운데 마지막으로 요일 이름이 나온 곳(없으면 이 장면의 첫 요일)
  let active = allOn ? -1 : WDS.indexOf(days[0] ?? "");
  let dayStart = 0;
  for (const c of list) {
    if (c.start > t) break;
    const m = c.text.match(/(월|화|수|목|금)요일/);
    if (m && days.includes(m[1])) { active = WDS.indexOf(m[1]); dayStart = c.start; }
  }
  const x = (w.days_detail ?? []).find((d) => d.wd === WDS[active]);
  // 이 요일에 말한 종목 카드
  const said = (w.riser_says ?? {})[x?.d ?? ""];
  const r = said ? x?.risers.find((z) => z.name === said.name) : undefined;
  const rAt = r ? list.find((c) => c.start >= dayStart - 0.01 && c.text.includes(r.name))?.start : undefined;
  const pk = w.parked;
  const pAt = withPark ? cueAt(cues, /머문 곳은/) : undefined;
  const h = w.history;
  const hAt = withPark ? cueAt(cues, /지난 \d+년/) : undefined;
  const showR = r && rAt != null && t >= rAt && !(pAt != null && t >= pAt);
  return (
    <Shell p={p} cues={cues} bg="market_neutral">
      <Table w={w} active={pAt != null && t >= pAt ? WDS.indexOf(pk?.last_wd ?? "") : active} reveal={0.05} allOn={!!allOn} />
      {showR && r ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1238, ...pop(rAt!) }}>
          <Card color={r.verdict.side === "money" ? RED : YEL} style={{ padding: "16px 28px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 20, whiteSpace: "nowrap" }}>
              <span style={{ fontSize: 44, fontWeight: 900 }}>{r.name}</span>
              <span style={{ fontSize: 44, fontWeight: 900, color: col(r.ret) }}>{pct(r.ret)}</span>
            </div>
            {said?.reason ? <div style={{ fontSize: 30, fontWeight: 800, color: SUBC, marginTop: 4 }}>{said.reason}</div> : null}
            <div style={{ fontSize: 32, fontWeight: 900, color: r.verdict.side === "money" ? RED : YEL, marginTop: 6 }}>
              외국인·기관 {sgn(r.verdict.fi)}{short(r.verdict.fi)} · {VERD[r.verdict.side] ?? ""}
            </div>
          </Card>
        </div>
      ) : null}
      {pk && pAt != null && t >= pAt ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1238, ...pop(pAt) }}>
          <Card color={YEL} style={{ padding: "16px 28px" }}>
            <div style={{ fontSize: 30, fontWeight: 800, color: SUBC }}>{pk.last_wd}요일 장이 끝났을 때 돈이 머문 곳</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 20 }}>
              <span style={{ fontSize: 60, fontWeight: 900, color: YEL }}>{pk.theme}</span>
              <span style={{ fontSize: 48, fontWeight: 900, color: RED }}>+{short(pk.net)}</span>
            </div>
            {h && hAt != null && t >= hAt ? (
              <div style={{ ...pop(hAt, 10), fontSize: 30, fontWeight: 800, marginTop: 6, color: "#E6E6E3" }}>
                지난 기록: 이렇게 끝난 {h.basis === "금요일" ? "금요일" : "날"} <span style={{ color: YEL }}>{h.n}번</span> → 다음 거래일도 유입 <span style={{ color: YEL }}>{h.cont}번</span>
              </div>
            ) : null}
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

const daysOf = (p: Props, sid: string) => {
  const dd = wk(p).days_detail ?? [];
  const head = dd.slice(0, -1);
  const cut = Math.ceil(head.length / 2);
  if (sid === "w3") return head.slice(0, cut).map((x) => x.wd);
  if (sid === "w4") return head.slice(cut).map((x) => x.wd);
  return dd.slice(-1).map((x) => x.wd);
};
export const V2: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => <DayScene p={p} cues={cues} days={[]} allOn />;
export const V3: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => <DayScene p={p} cues={cues} days={daysOf(p, "w3")} />;
export const V4: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => <DayScene p={p} cues={cues} days={daysOf(p, "w4")} />;
export const V5: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => <DayScene p={p} cues={cues} days={daysOf(p, "w5")} withPark />;

/* ───────── w6 다음 주 볼 것 + 끝 ───────── */
export const V6: React.FC<{ p: Props; sub: string; cues?: Cue[] }> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const list = cues ?? [];
  const endAt = cueAt(cues, /누가샀나/) ?? 1e9;
  if (t >= endAt) {
    return (
      <Shell p={p} cues={cues} hideSub bg="city_neutral">
        <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(endAt + 0.05, 30) }}>
          <Logo scale={2.4} />
          <div style={{ fontSize: 64, fontWeight: 800, marginTop: 190, textShadow: SH }}>국장 마감은 매일</div>
          <div style={{ fontSize: 120, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", textShadow: SH_Q }}>저녁 5시</div>
        </div>
      </Shell>
    );
  }
  const qs = list.filter((c) => /이어질 것인지/.test(c.text));
  return (
    <Shell p={p} cues={cues} bg="market_neutral">
      <div style={{ position: "absolute", left: 64, right: 64, top: 300 }}>
        <div style={{ ...pop(0.05), fontSize: 60, fontWeight: 900, textShadow: SH }}>다음 주 월요일에 볼 것</div>
        {qs.map((c, k) => (
          t >= c.start ? (
            <Card key={k} color={YEL} style={{ ...pop(c.start), marginTop: 26 }}>
              <div style={{ fontSize: 52, fontWeight: 900, lineHeight: 1.25, wordBreak: "keep-all" }}>{c.text.replace(/\.$/, "")}</div>
            </Card>
          ) : null
        ))}
      </div>
    </Shell>
  );
};

export const WEEKLY2_COMP: Record<string, React.FC<{ p: Props; sub: string; cues?: Cue[] }>> = { w0: V0, w1: V1, w2: V2, w3: V3, w4: V4, w5: V5, w6: V6 };
