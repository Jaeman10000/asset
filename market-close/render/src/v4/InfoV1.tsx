/** 생활형 정보 쇼츠 화면 (i0~i5, i6 은 평일 끝 화면) — JJ 2026-09-19 "생활형 정보성 뉴스가 나오면 따로 영상을 만들어 밤에".
 * 안내편(NoticeV4)은 애프터마켓 한 주제에 맞춰 손으로 그린 화면이라, 이건 대본 파일(data/<날짜>/info_script.json)의 cards 로 그린다.
 * 카드 종류: hook(큰 글자 → 질문) · fact(큰 숫자 하나) · compare(전 → 후) · list(말할 때마다 한 줄씩) · note(주의 한 줄).
 * 규칙은 평일편과 같다: 0초부터 글자(첫 화면이 비면 넘긴다), 질문 화면엔 질문만, 한 컷이 8초를 넘기지 않게 새로 켜진다.
 * 시청자 45세 이상이 76%(CHANNEL_REVIEW_2W) — 글자는 평일편보다 크게. */
import React from "react";
import type { Props } from "../types";
import type { Cue } from "../Scenes";
import { BgChip, BgCity, BgMarket, Card, Shell, YEL, GREEN, BLUE, RED, usePop, useT } from "./ScenesV4";

const GREY = "#8C99AD";
const SUBC = "#C9D2E0";
const SH = "0 4px 18px rgba(0,0,0,0.85)";
type SC = { p: Props; sub: string; cues?: Cue[] };
type Line = { t: string; size?: number; color?: "yellow" | "white" | "red" | "blue" | "green" };
type CardT = {
  kind: "hook" | "fact" | "compare" | "list" | "note";
  badge?: string; lines?: Line[]; q?: Line[];
  head?: string; big?: string; sub?: string; color?: Line["color"];
  before?: { label: string; value: string }; after?: { label: string; value: string };
  items?: string[]; text?: string;
};
type Info = { bg?: "city" | "market" | "chip"; tone?: "up" | "down" | "neutral"; cards?: Record<string, CardT> };

const COL = (c?: Line["color"]) => (c === "yellow" ? YEL : c === "red" ? RED : c === "blue" ? BLUE : c === "green" ? GREEN : "#FFFFFF");
const infoOf = (p: Props) => ((p as unknown as { info?: Info }).info ?? {}) as Info;
const cueAt = (cues: Cue[] | undefined, i: number, fb: number) => (cues && cues[i] ? cues[i].start : fb);
const fit = (s: string, base: number, width = 952) => Math.max(56, Math.min(base, Math.floor((width / Math.max(1, s.length)) * 1.75)));

const Bg: React.FC<{ info: Info; dim?: number }> = ({ info, dim = 0.2 }) => {
  const tone = info.tone ?? "neutral";
  if (info.bg === "market") return <BgMarket tone={tone} dim={dim} />;
  if (info.bg === "chip") return <BgChip tone={tone} dim={dim} />;
  return <BgCity tone={tone} dim={dim} />;
};

const Head: React.FC<{ s?: string; at?: number }> = ({ s, at = 0 }) => {
  const pop = usePop();
  return s ? <div style={{ position: "absolute", left: 64, right: 64, top: 230, fontSize: 52, fontWeight: 800, color: SUBC, textShadow: SH, wordBreak: "keep-all", ...pop(at) }}>{s}</div> : null;
};

/** 훅 — 0초부터 큰 글자, 질문 문장이 시작되면 질문만 */
const HookCard: React.FC<SC & { c: CardT }> = ({ p, cues, c }) => {
  const { t } = useT();
  const pop = usePop();
  const info = infoOf(p);
  const q = (cues ?? []).find((x) => /\?$/.test(x.text.trim()));
  if (q && c.q?.length && t >= q.start) {
    return (
      <Shell p={p} cues={cues} hideSub bg={<Bg info={info} dim={0.26} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 520, ...pop(q.start, 30) }}>
          {c.q.map((l, i) => (
            <div key={i} style={{ fontSize: l.size ? 120 * l.size : 120, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", color: COL(l.color), wordBreak: "keep-all",
              textShadow: l.color === "yellow" ? "0 0 36px rgba(255,216,77,0.45), 0 6px 30px rgba(0,0,0,0.75)" : "0 6px 30px rgba(0,0,0,0.75)" }}>{l.t}</div>
          ))}
        </div>
      </Shell>
    );
  }
  return (
    <Shell p={p} cues={cues} hideSub bg={<Bg info={info} dim={0.18} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 300 }}>
        {c.badge ? <div style={{ display: "inline-block", fontSize: 42, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "10px 26px", borderRadius: 14 }}>{c.badge}</div> : null}
        {(c.lines ?? []).map((l, i) => (
          <div key={i} style={{ fontSize: 140 * (l.size ?? 1), fontWeight: 900, lineHeight: 1.08, letterSpacing: "-0.05em", marginTop: i === 0 ? 30 : 0, color: COL(l.color), wordBreak: "keep-all",
            textShadow: l.color === "yellow" ? "0 0 36px rgba(255,216,77,0.4), 0 8px 34px rgba(0,0,0,0.75)" : "0 8px 34px rgba(0,0,0,0.75)" }}>{l.t}</div>
        ))}
      </div>
    </Shell>
  );
};

/** 큰 숫자(또는 짧은 말) 하나 */
const FactCard: React.FC<SC & { c: CardT }> = ({ p, cues, c }) => {
  const pop = usePop();
  const big = c.big ?? "";
  const at1 = cueAt(cues, 1, 2.2);
  return (
    <Shell p={p} cues={cues} bg={<Bg info={infoOf(p)} dim={0.45} />}>
      <Head s={c.head} />
      <div style={{ position: "absolute", left: 64, right: 64, top: 360, ...pop(0.05, 30) }}>
        <div style={{ fontSize: fit(big, 190), fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.04em", color: COL(c.color ?? "yellow"), wordBreak: "keep-all",
          textShadow: "0 0 36px rgba(255,216,77,0.35), 0 8px 30px rgba(0,0,0,0.8)" }}>{big}</div>
        {c.sub ? <div style={{ fontSize: 54, fontWeight: 800, marginTop: 26, color: "#FFFFFF", textShadow: SH, wordBreak: "keep-all", ...pop(at1, 16) }}>{c.sub}</div> : null}
      </div>
    </Shell>
  );
};

/** 전 → 후 */
const CompareCard: React.FC<SC & { c: CardT }> = ({ p, cues, c }) => {
  const { t } = useT();
  const pop = usePop();
  const a1 = cueAt(cues, 1, 2.4);
  const Box: React.FC<{ label: string; value: string; on: boolean; hot: boolean; at: number }> = ({ label, value, on, hot, at }) => (
    <div style={{ ...pop(at, 20), opacity: on ? 1 : 0 }}>
      <Card color={hot ? YEL : GREY} style={{ padding: "22px 30px" }}>
        <div style={{ fontSize: 40, fontWeight: 800, color: hot ? YEL : SUBC }}>{label}</div>
        <div style={{ fontSize: fit(value, 104, 880), fontWeight: 900, lineHeight: 1.1, marginTop: 8, color: hot ? "#FFFFFF" : "#E6E6E3", wordBreak: "keep-all" }}>{value}</div>
      </Card>
    </div>
  );
  return (
    <Shell p={p} cues={cues} bg={<Bg info={infoOf(p)} dim={0.5} />}>
      <Head s={c.head} />
      <div style={{ position: "absolute", left: 64, right: 64, top: 330, display: "flex", flexDirection: "column", gap: 22 }}>
        {c.before ? <Box label={c.before.label} value={c.before.value} on hot={false} at={0.05} /> : null}
        <div style={{ fontSize: 80, fontWeight: 900, color: YEL, textAlign: "center", lineHeight: 1, opacity: t >= a1 ? 1 : 0.25 }}>↓</div>
        {c.after ? <Box label={c.after.label} value={c.after.value} on={t >= a1} hot at={a1} /> : null}
      </div>
    </Shell>
  );
};

/** 말할 때마다 한 줄씩 */
const ListCard: React.FC<SC & { c: CardT }> = ({ p, cues, c }) => {
  const { t } = useT();
  const pop = usePop();
  const items = (c.items ?? []).slice(0, 4);
  const offset = 0;          // 머리글은 처음부터 떠 있고, 항목 i 는 장면의 i번째 문장이 시작할 때 켜진다
  return (
    <Shell p={p} cues={cues} bg={<Bg info={infoOf(p)} dim={0.55} />}>
      <Head s={c.head} />
      <div style={{ position: "absolute", left: 64, right: 64, top: 330, display: "flex", flexDirection: "column", gap: 20 }}>
        {items.map((it, i) => {
          const at = cueAt(cues, i + offset, 0.3 + i * 2.4);
          const on = t >= at;
          const cur = on && (i === items.length - 1 || t < cueAt(cues, i + offset + 1, at + 2.4));
          return (
            <div key={i} style={{ ...pop(at, 18), opacity: on ? 1 : 0 }}>
              <Card color={cur ? YEL : GREY} style={{ padding: "20px 26px", display: "flex", gap: 22, alignItems: "center" }}>
                <div style={{ flex: "0 0 auto", width: 64, height: 64, borderRadius: 32, background: cur ? YEL : "rgba(255,255,255,0.14)", color: cur ? "#0B0E16" : "#FFFFFF",
                  fontSize: 38, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
                <div style={{ fontSize: 50, fontWeight: 800, lineHeight: 1.25, wordBreak: "keep-all", color: cur ? "#FFFFFF" : "#E6E6E3" }}>{it}</div>
              </Card>
            </div>
          );
        })}
      </div>
    </Shell>
  );
};

/** 주의 한 줄 */
const NoteCard: React.FC<SC & { c: CardT }> = ({ p, cues, c }) => {
  const pop = usePop();
  return (
    <Shell p={p} cues={cues} bg={<Bg info={infoOf(p)} dim={0.5} />}>
      <Head s={c.head} />
      <div style={{ position: "absolute", left: 64, right: 64, top: 360, ...pop(0.1, 24) }}>
        <Card color={YEL} style={{ padding: "30px 34px" }}>
          <div style={{ fontSize: 62, fontWeight: 900, lineHeight: 1.3, wordBreak: "keep-all" }}>{c.text}</div>
        </Card>
      </div>
    </Shell>
  );
};

const pick = (id: string): React.FC<SC> => ({ p, cues, sub }) => {
  const c = infoOf(p).cards?.[id];
  if (!c) return <Shell p={p} cues={cues} bg={<Bg info={infoOf(p)} dim={0.4} />}><></></Shell>;
  const X = c.kind === "hook" ? HookCard : c.kind === "fact" ? FactCard : c.kind === "compare" ? CompareCard : c.kind === "list" ? ListCard : NoteCard;
  return <X p={p} cues={cues} sub={sub} c={c} />;
};

/** 끝 화면 — 평일 S6V4 는 '내일 볼 것'부터 켜져 정보편에선 첫 몇 초가 빈다(9/19 시험 렌더). 0초부터 로고와 시간 */
const EndCard: React.FC<SC> = ({ p, cues }) => {
  const pop = usePop();
  return (
    <Shell p={p} cues={cues} hideSub bg={<Bg info={infoOf(p)} dim={0.3} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(0, 24) }}>
        <div style={{ fontSize: 150, fontWeight: 900, letterSpacing: "-0.05em", textShadow: "0 8px 34px rgba(0,0,0,0.75)" }}>누가샀나</div>
        <div style={{ height: 10, width: 330, background: RED, borderRadius: 6, marginTop: 6 }} />
        <div style={{ fontSize: 60, fontWeight: 800, marginTop: 40, color: SUBC }}>국장 마감은 매일</div>
        <div style={{ fontSize: 96, fontWeight: 900, color: YEL, textShadow: "0 0 30px rgba(255,216,77,0.4)" }}>저녁 5시</div>
      </div>
    </Shell>
  );
};

export const INFO_COMP: Record<string, React.FC<SC>> = { i0: pick("i0"), i1: pick("i1"), i2: pick("i2"), i3: pick("i3"), i4: pick("i4"), i5: pick("i5"), i6: EndCard };
