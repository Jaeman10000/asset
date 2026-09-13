/** 제도 안내편 화면 (n0~n6) — 2026-09-14 한국거래소 애프터마켓.
 * 수급편과 달리 데이터 바인딩이 없다. 제도 사실은 고정값이고, 단계 전환만 말(큐)에 맞춘다.
 * 규칙은 평일편과 같다: 질문 화면엔 질문만, 한 컷이 8초를 넘기지 않게 무언가가 새로 켜진다.
 * 각 장면의 at(i)는 그 장면 i번째 문장이 시작하는 초다 — 대본 문장 순서가 바뀌면 여기 숫자도 같이 고친다. */
import React from "react";
import type { Props } from "../types";
import type { Cue } from "../Scenes";
import { BgCity, BgChip, BgMarket, Card, Shell, YEL, GREEN, BLUE, RED, usePop, useT } from "./ScenesV4";

const GREY = "#8C99AD";
const DIM = "rgba(255,255,255,0.16)";
type SC = { p: Props; sub: string; cues?: Cue[] };

const useAt = (cues?: Cue[]) => (i: number, fb: number) => (cues && cues[i] ? cues[i].start : fb);

const Head: React.FC<{ a: string; b?: string; top?: number }> = ({ a, b, top = 200 }) => (
  <div style={{ position: "absolute", left: 64, right: 64, top }}>
    <div style={{ fontSize: 56, fontWeight: 800, lineHeight: 1.2, textShadow: "0 3px 14px rgba(0,0,0,0.85)", wordBreak: "keep-all" }}>{a}</div>
    {b ? <div style={{ fontSize: 68, fontWeight: 900, lineHeight: 1.2, color: YEL, textShadow: "0 3px 14px rgba(0,0,0,0.85)", wordBreak: "keep-all" }}>{b}</div> : null}
  </div>
);

/** n0 훅 — 큰 글자 → 질문만 */
export const N0: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const q = (cues ?? []).find((c) => /\?$/.test(c.text.trim()));
  if (q && t >= q.start) {
    return (
      <Shell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.24} />}>
        <div style={{ position: "absolute", left: 64, right: 64, top: 560, ...pop(q.start, 30) }}>
          <div style={{ fontSize: 116, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", wordBreak: "keep-all", textShadow: "0 6px 30px rgba(0,0,0,0.75)" }}>네 시간을 더</div>
          <div style={{ fontSize: 116, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.04em", wordBreak: "keep-all", textShadow: "0 6px 30px rgba(0,0,0,0.75)" }}>거래하는데</div>
          <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1.12, letterSpacing: "-0.05em", color: YEL, wordBreak: "keep-all", marginTop: 18,
            textShadow: "0 0 36px rgba(255,216,77,0.45), 0 6px 30px rgba(0,0,0,0.75)" }}>종가는 그대로?</div>
        </div>
      </Shell>
    );
  }
  return (
    <Shell p={p} cues={cues} hideSub bg={<BgCity tone="neutral" dim={0.18} />}>
      <div style={{ position: "absolute", left: 64, right: 64, top: 300, ...pop(0.05, 30) }}>
        <div style={{ display: "inline-block", fontSize: 40, fontWeight: 900, color: "#0B0E16", background: YEL, padding: "10px 26px", borderRadius: 14 }}>내일, 9월 14일 월요일</div>
        <div style={{ fontSize: 148, fontWeight: 900, lineHeight: 1.06, letterSpacing: "-0.05em", marginTop: 34, textShadow: "0 8px 34px rgba(0,0,0,0.75)" }}>한국 증시가</div>
        <div style={{ fontSize: 172, fontWeight: 900, lineHeight: 1.06, letterSpacing: "-0.05em", color: YEL, textShadow: "0 0 36px rgba(255,216,77,0.4), 0 8px 34px rgba(0,0,0,0.75)" }}>밤 8시까지</div>
        <div style={{ fontSize: 148, fontWeight: 900, lineHeight: 1.06, letterSpacing: "-0.05em", textShadow: "0 8px 34px rgba(0,0,0,0.75)" }}>열립니다</div>
      </div>
    </Shell>
  );
};

/** 하루 시간축 09:00~20:00(11시간)을 952px에 그린다 */
const W = 952;
const x = (h: number) => ((h - 9) / 11) * W;
const Blk: React.FC<{ a: number; b: number; color: string; label: string; note?: string; on: boolean; grow?: number }> =
  ({ a, b, color, label, note, on, grow = 1 }) => (
    <div style={{ position: "absolute", left: x(a), width: (x(b) - x(a)) * grow, height: 96, borderRadius: 12, overflow: "hidden",
      background: on ? `${color}33` : "rgba(255,255,255,0.05)", border: `2.5px solid ${on ? color : DIM}`, boxShadow: on ? `0 0 26px ${color}55` : "none" }}>
      <div style={{ padding: "13px 14px", whiteSpace: "nowrap" }}>
        <div style={{ fontSize: 30, fontWeight: 900, color: on ? color : GREY }}>{label}</div>
        {note ? <div style={{ fontSize: 24, fontWeight: 700, color: on ? "#FFFFFF" : GREY, marginTop: 5 }}>{note}</div> : null}
      </div>
    </div>
  );
const Tick: React.FC<{ h: number; s: string }> = ({ h, s }) => (
  <div style={{ position: "absolute", left: x(h) - 44, width: 88, top: 104, textAlign: "center", fontSize: 26, fontWeight: 800, color: GREY }}>{s}</div>
);

/** n1 시간표 — 정규장은 그대로, 저녁에 시장이 하나 더 붙는다 */
export const N1: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const at = useAt(cues);
  const tAfter = at(1, 5), tSum = at(2, 11), tDef = at(4, 17);
  const grow = Math.max(0, Math.min(1, (t - tAfter) / 1.1));
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.52} />}>
      <Head a="한국 주식을 살 수 있는 시간이" b="이렇게 바뀝니다" />
      <div style={{ position: "absolute", left: 64, top: 430, width: W, height: 170 }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 96 }}>
          <Blk a={9} b={15.5} color={BLUE} label="정규장" note="09:00 ~ 15:30" on />
          <Blk a={16} b={20} color={YEL} label="애프터마켓" note="16:00 ~ 20:00 · 실시간 체결" on={t >= tAfter} grow={grow} />
        </div>
        <Tick h={9} s="09:00" /><Tick h={15.5} s="15:30" /><Tick h={20} s="20:00" />
      </div>
      {t >= tSum ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 680, ...pop(tSum) }}>
          <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
            <div style={{ fontSize: 58, fontWeight: 900, color: GREY }}>6시간 30분</div>
            <div style={{ fontSize: 58, fontWeight: 900, color: YEL }}>→</div>
            <div style={{ fontSize: 84, fontWeight: 900, color: YEL, textShadow: "0 0 26px rgba(255,216,77,0.4)" }}>10시간 30분</div>
          </div>
        </div>
      ) : null}
      {t >= tDef ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 840, ...pop(tDef) }}>
          <Card color={YEL}>
            <div style={{ fontSize: 44, fontWeight: 800, color: GREY, textDecoration: "line-through" }}>정규장이 길어진 것</div>
            <div style={{ fontSize: 62, fontWeight: 900, color: YEL, marginTop: 10, wordBreak: "keep-all" }}>저녁에 시장이 하나 더 생긴 것</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

const Row: React.FC<{ i: number; on: boolean; tag: string; from: string; to: string }> = ({ i, on, tag, from, to }) => (
  <div style={{ opacity: on ? 1 : 0.16, marginBottom: 34 }}>
    <div style={{ fontSize: 32, fontWeight: 900, color: on ? YEL : GREY }}>{i}. {tag}</div>
    <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 8 }}>
      <div style={{ flex: 1, fontSize: 36, fontWeight: 700, color: GREY, textDecoration: "line-through", wordBreak: "keep-all" }}>{from}</div>
      <div style={{ fontSize: 40, fontWeight: 900, color: on ? YEL : GREY }}>→</div>
      <div style={{ flex: 1.1, fontSize: 42, fontWeight: 900, color: on ? "#FFFFFF" : GREY, wordBreak: "keep-all" }}>{to}</div>
    </div>
  </div>
);

/** n2 없어지는 것과 넓어지는 것 — 한 줄 말할 때 한 줄씩 켜진다 */
export const N2: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const at = useAt(cues);
  const a1 = at(1, 3), a2 = at(2, 8), a3 = at(5, 19), aWide = at(4, 15);
  return (
    <Shell p={p} cues={cues} bg={<BgChip tone="neutral" dim={0.58} />}>
      <Head a="원래 있던 저녁 거래는" b="세 가지가 달라집니다" />
      <div style={{ position: "absolute", left: 64, right: 64, top: 470 }}>
        <Row i={1} on={t >= a1} tag="체결 방식" from="10분에 한 번씩 모아서" to="바로 체결" />
        <Row i={2} on={t >= a2} tag="움직일 수 있는 폭" from="그날 종가 위아래 10%" to="전날 종가 위아래 30%" />
        <Row i={3} on={t >= a3} tag="거래되는 것" from="ETF · ETN" to="코스피 · 코스닥 주식만" />
      </div>
      {t >= aWide ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 990 }}>
          <Card color={YEL}>
            <div style={{ fontSize: 48, fontWeight: 900, color: YEL, wordBreak: "keep-all" }}>낮과 같은 폭이 밤에 한 번 더 열립니다</div>
          </Card>
        </div>
      ) : null}
    </Shell>
  );
};

/** n3 종가 — 저녁에 움직여도 그날 종가는 오후 3시 반 것 */
export const N3: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const at = useAt(cues);
  const a1 = at(2, 4), a2 = at(3, 11);
  const a3 = a2 + 2.6;
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.58} />}>
      <Head a="밤 8시 가격이" b="그날 종가일까요?" />
      <div style={{ position: "absolute", left: 64, right: 64, top: 450, ...pop(a1 - 0.5) }}>
        <Card color={YEL}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "#CFD6E4" }}>공식 종가 · 다음 거래일 기준가격</div>
          <div style={{ fontSize: 116, fontWeight: 900, color: YEL, letterSpacing: "-0.04em", lineHeight: 1.1, marginTop: 8, textShadow: "0 0 28px rgba(255,216,77,0.4)" }}>오후 3시 30분</div>
          <div style={{ fontSize: 38, fontWeight: 800, marginTop: 10 }}>정규장 종가 그대로입니다</div>
        </Card>
      </div>
      {t >= a2 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 860, ...pop(a2) }}>
          <div style={{ border: `2.5px dashed ${GREY}`, borderRadius: 24, padding: "28px 34px", background: "rgba(10,14,26,0.74)" }}>
            <div style={{ fontSize: 36, fontWeight: 800, color: GREY }}>오후 4시 ~ 밤 8시에 움직인 값</div>
            <div style={{ fontSize: 72, fontWeight: 900, color: GREY, marginTop: 8 }}>공식 종가가 아닙니다</div>
          </div>
        </div>
      ) : null}
      {t >= a3 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1170, ...pop(a3) }}>
          <div style={{ fontSize: 50, fontWeight: 900, lineHeight: 1.32, wordBreak: "keep-all", textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>
            종가 <span style={{ color: RED }}>뒤에 따로 붙는</span> 가격인 셈입니다
          </div>
        </div>
      ) : null}
    </Shell>
  );
};

/** n4 주문과 공시 — 아무 값에나 체결되는 주문은 못 내고, 마지막 두 시간엔 새 공시가 없다 */
export const N4: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const at = useAt(cues);
  const a1 = at(1, 4), a2 = at(3, 12), a3 = at(4, 17);
  return (
    <Shell p={p} cues={cues} bg={<BgCity tone="down" dim={0.52} />}>
      <Head a="주문은 낮과" b="똑같이 들어갈까요?" />
      <div style={{ position: "absolute", left: 64, right: 64, top: 450, ...pop(a1 - 0.5) }}>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1, border: `2.5px solid ${RED}`, borderRadius: 20, padding: "22px 18px", background: "rgba(255,77,77,0.12)" }}>
            <div style={{ fontSize: 34, fontWeight: 900, color: RED }}>낼 수 없는 주문</div>
            <div style={{ fontSize: 42, fontWeight: 900, marginTop: 10, lineHeight: 1.3, wordBreak: "keep-all" }}>시장가<br />조건부지정가</div>
          </div>
          <div style={{ flex: 1, border: `2.5px solid ${GREEN}`, borderRadius: 20, padding: "22px 18px", background: "rgba(47,210,122,0.12)" }}>
            <div style={{ fontSize: 34, fontWeight: 900, color: GREEN }}>낼 수 있는 주문</div>
            <div style={{ fontSize: 42, fontWeight: 900, marginTop: 10, lineHeight: 1.3, wordBreak: "keep-all" }}>지정가 계열<br />값을 적는 주문</div>
          </div>
        </div>
      </div>
      {t >= a2 ? (
        <div style={{ position: "absolute", left: 64, top: 820, width: W, height: 250, ...pop(a2) }}>
          <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 96 }}>
            <Blk a={9} b={18} color={BLUE} label="기업 공시 접수" note="~ 저녁 6시" on />
          </div>
          <div style={{ position: "absolute", left: 0, top: 116, width: W, height: 96 }}>
            <Blk a={9} b={20} color={YEL} label="거래" note="~ 밤 8시" on />
          </div>
          <div style={{ position: "absolute", left: x(18) - 44, width: 88, top: 220, textAlign: "center", fontSize: 26, fontWeight: 800, color: GREY }}>18:00</div>
          <div style={{ position: "absolute", left: x(20) - 44, width: 88, top: 220, textAlign: "center", fontSize: 26, fontWeight: 800, color: GREY }}>20:00</div>
          {t >= a3 ? (
            <div style={{ position: "absolute", left: x(18), width: x(20) - x(18), top: -14, height: 240, borderRadius: 12,
              border: `3px dashed ${RED}`, boxShadow: `0 0 26px ${RED}44` }} />
          ) : null}
        </div>
      ) : null}
      {t >= a3 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1130, ...pop(a3) }}>
          <div style={{ fontSize: 52, fontWeight: 900, color: RED, wordBreak: "keep-all", textShadow: "0 3px 14px rgba(0,0,0,0.85)" }}>마지막 두 시간은 새 공시가 접수되지 않습니다</div>
        </div>
      ) : null}
    </Shell>
  );
};

/** n5 수급 — 우리 채널이 말하는 숫자가 어느 시간대 것인지 */
export const N5: React.FC<SC> = ({ p, cues }) => {
  const { t } = useT();
  const pop = usePop();
  const at = useAt(cues);
  const a1 = at(1, 4), a2 = at(3, 13), a3 = at(5, 22);
  return (
    <Shell p={p} cues={cues} bg={<BgMarket tone="neutral" dim={0.54} />}>
      <Head a="그럼 우리가 보는 숫자는" b="어떻게 달라질까요?" />
      <div style={{ position: "absolute", left: 64, right: 64, top: 450, ...pop(a1 - 0.5) }}>
        <Card color={YEL}>
          <div style={{ fontSize: 34, fontWeight: 800, color: "#CFD6E4" }}>투자자별 최종 매매 내역이 나오는 시각</div>
          <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 12 }}>
            <div style={{ fontSize: 76, fontWeight: 900, color: GREY, textDecoration: "line-through" }}>저녁 6시</div>
            <div style={{ fontSize: 58, fontWeight: 900, color: YEL }}>→</div>
            <div style={{ fontSize: 100, fontWeight: 900, color: YEL, textShadow: "0 0 28px rgba(255,216,77,0.4)" }}>밤 8시</div>
          </div>
        </Card>
      </div>
      {t >= a2 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 810, ...pop(a2) }}>
          <Card color={GREEN}>
            <span style={{ display: "inline-block", fontSize: 32, fontWeight: 900, background: GREEN, color: "#0B0E16", padding: "4px 16px", borderRadius: 10 }}>이 채널의 숫자</span>
            <div style={{ fontSize: 62, fontWeight: 900, marginTop: 12, color: GREEN }}>09:00 ~ 15:30</div>
            <div style={{ fontSize: 34, fontWeight: 700, color: "#CFD6E4", marginTop: 8, wordBreak: "keep-all" }}>코스피 정규장 체결 기준 · 대량매매 제외</div>
          </Card>
        </div>
      ) : null}
      {t >= a3 ? (
        <div style={{ position: "absolute", left: 64, right: 64, top: 1190, ...pop(a3) }}>
          <div style={{ fontSize: 46, fontWeight: 800, color: GREY, textDecoration: "line-through" }}>숫자가 틀린 것</div>
          <div style={{ fontSize: 58, fontWeight: 900, color: YEL, marginTop: 8, wordBreak: "keep-all" }}>몇 시 기준인지가 하나 더 붙는 것</div>
        </div>
      ) : null}
    </Shell>
  );
};

export const NOTICE_COMP: Record<string, React.FC<SC>> = { n0: N0, n1: N1, n2: N2, n3: N3, n4: N4, n5: N5 };
