import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  collectFlow,
  fetchFlowHistory,
  fetchForecast,
  fetchMomentum,
  type FlowHistory,
  type Forecast,
  type ForecastCandidate,
  type Momentum,
  type MomentumTheme,
} from '../../api/client';
import { StockBadge } from './shared';
import { ChartPanel } from './ChartPanel';
import type { ChartTarget, SectorFlow } from '../../api/types';
import { usePortfolio } from '../../store/portfolio';

/** 아카이브의 종목(코드+이름)을 상세 패널이 받는 형태로. 시세·정보는 패널이 직접 받아온다. */
function toTarget(code: string, name: string): ChartTarget {
  return { symbol: code, name, assetType: 'stock', region: 'KR', currency: 'KRW' };
}

/**
 * 자금 흐름 — 로컬에 쌓인 일별 아카이브(장 마감 후 자동 저장)를 읽어
 *   ① 예상 경로(다음 거래일 유입 후보 3테마 + 주도주 5) + 실측 적중률
 *   ② 테마×날짜 히트맵 (강도% / 절대 순매수 토글)
 *   ③ 주도주 계보 (날짜별 1위 테마와 그날의 대장주)
 * 를 보여준다.
 *
 * 원칙: 예측 점수 옆에 반드시 백테스트 적중률을 같이 놓는다. 근거 없는 숫자는
 * 안 보여주는 것보다 나쁘다 — 믿게 되니까.
 */

const DAY_OPTIONS = [30, 60, 120, 250] as const;

function fmtEok(v: number): string {
  const a = Math.abs(v);
  if (a >= 10_000) return `${(v / 10_000).toFixed(1)}조`;
  return `${Math.round(v).toLocaleString()}억`;
}

function fmtMB(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

/** 백엔드는 날짜를 'YYYYMMDD'로 준다(파일명만 'YYYY-MM-DD'). 둘 다 받아준다. */
function parts(d: string): [string, string, string] | null {
  if (/^\d{8}$/.test(d)) return [d.slice(0, 4), d.slice(4, 6), d.slice(6, 8)];
  const p = d.split('-');
  return p.length === 3 ? [p[0], p[1], p[2]] : null;
}
function fmtDate(d: string): string {
  const p = parts(d);
  return p ? `${Number(p[1])}/${Number(p[2])}` : d;
}
function fmtFull(d: string | null | undefined): string {
  if (!d) return '—';
  const p = parts(d);
  return p ? `${p[0]}-${p[1]}-${p[2]}` : d;
}

function signed(v: number): string {
  return `${v >= 0 ? '+' : '−'}${fmtEok(Math.abs(v))}`;
}

/** 값 → 셀 색. 유입(+)=크림슨, 유출(−)=블루. 알파는 |값|/max 로 정규화. */
function cellStyle(v: number, max: number): React.CSSProperties {
  if (!max || !Number.isFinite(v)) return { background: 'rgba(255,255,255,.04)' };
  const t = Math.min(1, Math.abs(v) / max);
  const a = 0.08 + t * 0.82;
  return { background: v >= 0 ? `rgba(255,93,115,${a})` : `rgba(91,140,255,${a})` };
}

// ── 예상 경로 ──

function SignalBar({ label, value, max, tone }: { label: string; value: number; max: number; tone: string }) {
  const w = max > 0 ? Math.min(100, (Math.max(0, value) / max) * 100) : 0;
  return (
    <div className="mf-sig">
      <span className="mf-sig-lb">{label}</span>
      <span className="mf-sig-track">
        <i style={{ width: `${w}%`, background: tone }} />
      </span>
      <span className="mf-sig-v">{value.toFixed(1)}</span>
    </div>
  );
}

function CandidateCard({
  c,
  rank,
  onPick,
}: {
  c: ForecastCandidate;
  rank: number;
  onPick: (t: ChartTarget) => void;
}) {
  // 세 신호의 '가중 후' 기여도를 같은 축에서 비교 — 어떤 신호가 이 후보를 밀어올렸는지 보이게
  const wTrans = c.trans * 0.45;
  const wAccel = Math.max(0, c.accel) * 2.2;
  const wRoom = Math.max(0, c.room) * 0.8;
  const maxSig = Math.max(1, wTrans, wAccel, wRoom);
  return (
    <div className={`mf-cand rank${rank}`}>
      <div className="mf-cand-hd">
        <span className="mf-rank">{rank}</span>
        <span className="mf-cand-name">{c.theme}</span>
        <span className="mf-cand-score">{c.score.toFixed(1)}</span>
      </div>
      <div className="mf-sigs">
        <SignalBar label="전이" value={wTrans} max={maxSig} tone="var(--gold)" />
        <SignalBar label="가속" value={wAccel} max={maxSig} tone="var(--emer)" />
        <SignalBar label="여력" value={wRoom} max={maxSig} tone="var(--ice)" />
      </div>
      <div className="mf-sig-note">
        전이 {c.trans.toFixed(1)}% ({c.transN}회) · 가속 {c.accel.toFixed(1)} · 여력 {c.room.toFixed(1)}
      </div>
      <ul className="mf-leaders">
        {c.leaders.length === 0 && <li className="mf-empty-li">주도주 데이터 없음</li>}
        {c.leaders.map((l) => (
          <li key={l.code}>
            <button type="button" onClick={() => onPick(toTarget(l.code, l.name))} title={`${l.name} 상세`}>
              <StockBadge name={l.name} symbol={l.code} size={18} />
              <span className="mf-ld-name">{l.name}</span>
              <span className={`mf-ld-net ${l.net5d >= 0 ? 'pos' : 'neg'}`}>{signed(l.net5d)}</span>
              <span className={`mf-ld-ret ${l.ret >= 0 ? 'pos' : 'neg'}`}>
                {l.ret >= 0 ? '+' : ''}
                {l.ret.toFixed(2)}%
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ForecastPanel({ fc, onPick }: { fc: Forecast | null; onPick: (t: ChartTarget) => void }) {
  if (!fc) return <div className="mf-skel">예상 경로 계산 중…</div>;
  if (!fc.ready) return <div className="mf-empty">{fc.reason ?? '데이터가 부족합니다.'}</div>;
  const bt = fc.backtest;
  const edge = bt && bt.base3 > 0 ? bt.top3pct / bt.base3 : 0;
  return (
    <>
      <div className="mf-fc-top">
        <div className="mf-fc-meta">
          <span className="mf-fc-lead">
            직전 거래일 1위 <b>{fc.curLeader ?? '—'}</b>
          </span>
          <span className="mf-dim">
            기준 {fmtFull(fc.asOf)} · 학습 {fc.days}일 · 전이 표본 {fc.sampleN}회
          </span>
        </div>
        {bt && (
          <div className={`mf-bt${edge >= 1.5 ? ' good' : edge >= 1.1 ? ' mid' : ' bad'}`}>
            <div className="mf-bt-row">
              <span>Top3 적중</span>
              <b>{bt.top3pct.toFixed(1)}%</b>
              <em>랜덤 {bt.base3.toFixed(1)}%</em>
            </div>
            <div className="mf-bt-row">
              <span>Top1 적중</span>
              <b>{bt.top1pct.toFixed(1)}%</b>
              <em>랜덤 {bt.base1.toFixed(1)}%</em>
            </div>
            <div className="mf-bt-foot">
              워크포워드 검증 {bt.n}일 · 랜덤 대비 {edge.toFixed(1)}배
            </div>
          </div>
        )}
      </div>
      <div className="mf-cands">
        {(fc.candidates ?? []).map((c, i) => (
          <CandidateCard key={c.theme} c={c} rank={i + 1} onPick={onPick} />
        ))}
      </div>
      <p className="mf-disclaimer">
        점수는 전이확률·단기가속·순환여력 세 신호의 가중합입니다. 위 적중률은 예측 시점 이후 데이터를
        전혀 쓰지 않은 워크포워드 검증 결과이며, 투자 판단의 근거가 아니라 관측 기록입니다.
      </p>
    </>
  );
}

// ── 오늘(장중) 실시간 ──

/**
 * 아카이브는 마감 확정치라 '직전 거래일'까지만 보여준다. 오늘 장중 흐름은 대시보드가
 * 이미 30초마다 받아오고 있으므로(snapshot.sectorFlows) 같은 데이터를 여기서도 쓴다.
 * 강도% 정의는 아카이브와 동일하게 (외+기)/거래대금×100 — 두 화면의 숫자가 같은 뜻이 되게.
 */
function TodayLive({ onPick }: { onPick: (t: ChartTarget) => void }) {
  const snapshot = usePortfolio((st) => st.snapshot);
  const rows = useMemo(() => {
    const kr = (snapshot?.sectorFlows ?? []).filter((f: SectorFlow) => f.region === 'KR');
    return kr
      .map((f) => {
        const net = (f.foreign ?? 0) + (f.inst ?? 0);
        const val = f.value ?? 0;
        return {
          theme: f.name,
          foreign: f.foreign ?? 0,
          inst: f.inst ?? 0,
          net,
          // 거래대금을 못 받은 구버전 백엔드/콜드 상태면 강도는 계산하지 않는다(허수 방지)
          strength: val > 0 ? (net / val) * 100 : null,
          leader: f.members?.[0] ?? null,
          covered: f.covered ?? null,
          slots: f.slots ?? null,
        };
      })
      .sort((a, b) => {
        if (a.strength != null && b.strength != null) return b.strength - a.strength;
        return b.net - a.net;
      });
  }, [snapshot]);

  if (!snapshot) return <div className="mf-skel">실시간 수급 불러오는 중…</div>;
  if (rows.length === 0) return <div className="mf-empty">실시간 섹터 수급이 아직 없습니다.</div>;

  const open = snapshot.krSession ?? false;
  const noStrength = rows.every((r) => r.strength == null);
  return (
    <>
      <div className="mf-live-note">
        <span className={`mf-live-dot${open ? ' on' : ''}`} />
        {open
          ? '장중 미확정 — 30초마다 갱신되며, 마감 후 확정치가 아카이브에 저장됩니다'
          : '장 마감 — 오늘 최종 수급(아카이브 저장 전)'}
      </div>
      <ol className="mf-live">
        {rows.slice(0, 8).map((r, i) => (
          <li key={r.theme}>
            <span className="mf-live-rank">{i + 1}</span>
            <span className="mf-live-theme">{r.theme}</span>
            <span className="mf-live-str">
              {r.strength == null ? '—' : `${r.strength >= 0 ? '+' : ''}${r.strength.toFixed(1)}%`}
            </span>
            <span className="mf-live-f" title="외국인 순매수">{signed(r.foreign)}</span>
            <span className="mf-live-i" title="기관 순매수">{signed(r.inst)}</span>
            <span className="mf-live-ld">
              {r.covered != null && r.slots != null && r.covered < r.slots && (
                <em className="mf-partial" title={`구성 ${r.slots}종목 중 ${r.covered}종목만 집계됨`}>
                  {r.covered}/{r.slots}
                </em>
              )}
              {r.leader ? (
                <button type="button" className="mf-link" onClick={() => onPick(toTarget(r.leader!.code, r.leader!.name))}>
                  {r.leader.name}
                </button>
              ) : (
                '—'
              )}
            </span>
          </li>
        ))}
      </ol>
      {noStrength && (
        <p className="mf-note">
          거래대금을 아직 못 받아 강도%를 계산하지 못했습니다 — 순매수 금액순으로 정렬했습니다.
        </p>
      )}
    </>
  );
}

// ── 지금 주도 ──

type MomSort = 'net' | 'strength';
const MOM_DAYS = [5, 20, 60] as const;

/**
 * 예상 경로가 '아직 안 들어온 곳'을 찾는 반면, 이건 '이미 들어와서 끌고 가는 곳'이다.
 *
 * 정렬을 두 가지로 두는 이유(실측): 해운은 최근 20일 순매수 2,274억으로 금액순 6위지만
 * 거래대금이 1.3조뿐이라 강도로는 +17.2%로 1위다. 반대로 바이오/제약은 5,718억으로
 * 금액 1위지만 거래대금 9.9조라 강도는 +5.8%. 어느 쪽이 '주도'인지는 보는 사람이 정한다.
 */
function MomentumPanel({
  mom,
  days,
  setDays,
  onPick,
}: {
  mom: Momentum | null;
  days: number;
  setDays: (d: number) => void;
  onPick: (t: ChartTarget) => void;
}) {
  const [sort, setSort] = useState<MomSort>('net');
  const [open, setOpen] = useState<string | null>(null);

  const rows = useMemo(() => {
    const ts = [...(mom?.themes ?? [])];
    if (sort === 'strength') {
      // 강도가 없는 테마(거래대금 0)는 뒤로
      ts.sort((a, b) => (b.strength ?? -Infinity) - (a.strength ?? -Infinity));
    } else {
      ts.sort((a, b) => b.net - a.net);
    }
    return ts;
  }, [mom, sort]);

  const max = useMemo(() => {
    let m = 0;
    rows.forEach((t) => {
      const v = sort === 'strength' ? t.strength ?? 0 : t.net;
      m = Math.max(m, Math.abs(v));
    });
    return m || 1;
  }, [rows, sort]);

  const controls = (
    <div className="mf-mom-ctl">
      <div className="mf-seg">
        {MOM_DAYS.map((d) => (
          <button key={d} type="button" className={days === d ? 'on' : ''} onClick={() => setDays(d)}>
            {d}일
          </button>
        ))}
      </div>
      <div className="mf-seg">
        <button type="button" className={sort === 'net' ? 'on' : ''} onClick={() => setSort('net')}>
          금액순
        </button>
        <button type="button" className={sort === 'strength' ? 'on' : ''} onClick={() => setSort('strength')}>
          강도순
        </button>
      </div>
      {mom?.from && (
        <span className="mf-dim">
          {fmtFull(mom.from)} ~ {fmtFull(mom.to)}
        </span>
      )}
    </div>
  );

  // 로딩/실패에도 기간·정렬 칩은 계속 붙여둔다 — 안 그러면 칩을 누른 순간 칩이 사라져
  // 레이아웃이 튀고 연속으로 기간을 바꿀 수가 없다.
  if (!mom) {
    return (
      <>
        {controls}
        <div className="mf-skel">지금 주도 계산 중…</div>
      </>
    );
  }
  if (!mom.ready) {
    return (
      <>
        {controls}
        <div className="mf-empty">{mom.reason ?? '데이터가 부족합니다.'}</div>
      </>
    );
  }

  return (
    <>
      {controls}
      <ol className="mf-mom">
        {rows.map((t, i) => (
          <MomRow
            key={t.theme}
            t={t}
            rank={i + 1}
            sort={sort}
            max={max}
            open={open === t.theme}
            onToggle={() => setOpen(open === t.theme ? null : t.theme)}
            onPick={onPick}
          />
        ))}
      </ol>
      <p className="mf-note">
        금액순은 절대 순매수(외국인+기관), 강도순은 거래대금 대비 비율입니다. 대형 테마는 금액이
        크고 소형 테마는 강도가 높게 나오므로 둘을 같이 봐야 합니다. 테마를 누르면 주도주가 열립니다.
      </p>
    </>
  );
}

function MomRow({
  t,
  rank,
  sort,
  max,
  open,
  onToggle,
  onPick,
}: {
  t: MomentumTheme;
  rank: number;
  sort: MomSort;
  max: number;
  open: boolean;
  onToggle: () => void;
  onPick: (t: ChartTarget) => void;
}) {
  const v = sort === 'strength' ? t.strength ?? 0 : t.net;
  const w = Math.min(100, (Math.abs(v) / max) * 100);
  return (
    <li className={open ? 'open' : ''}>
      <button type="button" className="mf-mom-hd" onClick={onToggle} aria-expanded={open}>
        <span className="mf-mom-rank">{rank}</span>
        <span className="mf-mom-theme">{t.theme}</span>
        <span className="mf-mom-bar">
          <i className={v >= 0 ? 'pos' : 'neg'} style={{ width: `${w}%` }} />
        </span>
        <span className={`mf-mom-net ${t.net >= 0 ? 'pos' : 'neg'}`}>{signed(t.net)}</span>
        <span className="mf-mom-str">
          {t.strength == null ? '—' : `${t.strength >= 0 ? '+' : ''}${t.strength.toFixed(1)}%`}
        </span>
        <span className="mf-mom-days" title={`${t.nDays}일 중 ${t.posDays}일 순매수`}>
          {t.streak > 0 && <em className="mf-streak">{t.streak}일 연속</em>}
          {t.posDays}/{t.nDays}
        </span>
      </button>
      {open && (
        <ul className="mf-leaders mf-mom-leaders">
          {t.leaders.length === 0 && <li className="mf-empty-li">주도주 데이터 없음</li>}
          {t.leaders.map((l) => (
            <li key={l.code}>
              <button type="button" onClick={() => onPick(toTarget(l.code, l.name))} title={`${l.name} 상세`}>
                <StockBadge name={l.name} symbol={l.code} size={18} />
                <span className="mf-ld-name">{l.name}</span>
                <span className={`mf-ld-net ${l.net >= 0 ? 'pos' : 'neg'}`}>{signed(l.net)}</span>
                <span className={`mf-ld-ret ${l.ret >= 0 ? 'pos' : 'neg'}`}>
                  {l.ret >= 0 ? '+' : ''}
                  {l.ret.toFixed(2)}%
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

// ── 히트맵 ──

type Metric = 'strength' | 'net';
type Tip = { date: string; theme: string; text: string; x: number; y: number };

function Heatmap({
  hist,
  metric,
  onHover,
}: {
  hist: FlowHistory;
  metric: Metric;
  onHover: (t: Tip | null) => void;
}) {
  const { dates, byDate } = hist;

  const themes = useMemo(() => {
    const last = dates.length ? byDate[dates[dates.length - 1]] ?? {} : {};
    const names = new Set<string>();
    dates.forEach((d) => Object.keys(byDate[d] ?? {}).forEach((t) => names.add(t)));
    // 최신일 강도 내림차순 — 지금 돈이 몰린 테마가 맨 위로
    return [...names].sort((a, b) => (last[b]?.strength ?? -999) - (last[a]?.strength ?? -999));
  }, [dates, byDate]);

  const pick = useCallback(
    (d: string, t: string): number | null => {
      const c = byDate[d]?.[t];
      if (!c) return null;
      return metric === 'strength' ? c.strength : c.foreign + c.inst;
    },
    [byDate, metric],
  );

  // 스케일 상한: 최대 절대값의 60%. 하루짜리 이상치(삼성전자 수조 원)가 나머지를
  // 전부 무채색으로 눌러버리는 걸 막는다 — 넘는 값은 그냥 최대 채도로 잘린다.
  const max = useMemo(() => {
    let m = 0;
    dates.forEach((d) =>
      themes.forEach((t) => {
        const v = pick(d, t);
        if (v != null) m = Math.max(m, Math.abs(v));
      }),
    );
    return m * 0.6 || 1;
  }, [dates, themes, pick]);

  const step = Math.max(1, Math.ceil(dates.length / 12));

  return (
    <div className="mf-hm-scroll">
      <div className="mf-hm" style={{ gridTemplateColumns: `88px repeat(${dates.length}, minmax(6px, 1fr))` }}>
        {themes.map((t) => (
          <div key={t} style={{ display: 'contents' }}>
            <div className="mf-hm-lb">{t}</div>
            {dates.map((d) => {
              const v = pick(d, t);
              const cell = byDate[d]?.[t];
              return (
                <div
                  key={`${t}-${d}`}
                  className="mf-hm-c"
                  style={v == null ? { background: 'rgba(255,255,255,.03)' } : cellStyle(v, max)}
                  onMouseEnter={(e) => {
                    if (!cell) return;
                    onHover({
                      date: d,
                      theme: t,
                      text: `외 ${signed(cell.foreign)} · 기 ${signed(cell.inst)} · 강도 ${cell.strength.toFixed(
                        2,
                      )}%${cell.leader ? ` · 대장 ${cell.leader}` : ''}`,
                      x: e.clientX,
                      y: e.clientY,
                    });
                  }}
                  onMouseLeave={() => onHover(null)}
                />
              );
            })}
          </div>
        ))}
        <div className="mf-hm-lb" />
        {dates.map((d, i) => (
          <div className="mf-hm-x" key={`x-${d}`}>
            {i % step === 0 ? fmtDate(d) : ''}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 주도주 계보 ──

type LeaderRef = { code: string; name: string };

function Lineage({ hist, onPick }: { hist: FlowHistory; onPick: (t: ChartTarget) => void }) {
  // 날짜별 1위 테마 → 같은 테마 연속 구간을 하나로 묶어 '며칠째'로 표시.
  // 순환(돈이 테마를 옮겨 다니는 것)이 목록만 봐도 보이게 하려는 것.
  const runs = useMemo(() => {
    const daily: { date: string; theme: string; leader: LeaderRef | null }[] = [];
    for (const d of [...hist.dates].reverse()) {
      const day = hist.byDate[d];
      if (!day) continue;
      let best: { theme: string; s: number; leader: LeaderRef | null } | null = null;
      for (const [t, c] of Object.entries(day)) {
        if (best && c.strength <= best.s) continue;
        best = {
          theme: t,
          s: c.strength,
          leader: c.leaderCode && c.leader ? { code: c.leaderCode, name: c.leader } : null,
        };
      }
      if (best) daily.push({ date: d, theme: best.theme, leader: best.leader });
    }
    const out: { theme: string; from: string; to: string; n: number; leaders: LeaderRef[] }[] = [];
    for (const r of daily.slice(0, 30)) {
      const last = out[out.length - 1];
      if (last && last.theme === r.theme) {
        last.n += 1;
        last.from = r.date;
        if (r.leader && !last.leaders.some((x) => x.code === r.leader!.code)) last.leaders.push(r.leader);
      } else {
        out.push({ theme: r.theme, from: r.date, to: r.date, n: 1, leaders: r.leader ? [r.leader] : [] });
      }
    }
    return out;
  }, [hist]);

  return (
    <ol className="mf-lineage">
      {runs.length === 0 && <li className="mf-empty-li">아직 저장된 날짜가 없습니다.</li>}
      {runs.map((r, i) => (
        <li key={`${r.theme}-${r.to}-${i}`}>
          <span className="mf-ln-date">
            {r.from === r.to ? fmtDate(r.to) : `${fmtDate(r.from)}~${fmtDate(r.to)}`}
          </span>
          <span className="mf-ln-theme">{r.theme}</span>
          {r.n > 1 && <span className="mf-ln-run">{r.n}일</span>}
          <span className="mf-ln-leaders">
            {r.leaders.length === 0 && '—'}
            {r.leaders.slice(0, 3).map((l, k) => (
              <span key={l.code}>
                {k > 0 && ' · '}
                <button type="button" className="mf-link" onClick={() => onPick(toTarget(l.code, l.name))}>
                  {l.name}
                </button>
              </span>
            ))}
          </span>
        </li>
      ))}
    </ol>
  );
}

// ── 화면 ──

export function MoneyFlow() {
  const [days, setDays] = useState<number>(120);
  const [hist, setHist] = useState<FlowHistory | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  // 예상 경로(순환) ↔ 지금 주도(추세) — 일부러 반대 방향을 보므로 탭으로 나란히 둔다
  const [pathTab, setPathTab] = useState<'forecast' | 'momentum'>('forecast');
  const [momDays, setMomDays] = useState(20);
  const [mom, setMom] = useState<Momentum | null>(null);
  const [metric, setMetric] = useState<Metric>('strength');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  // 종목 클릭 → 상세 패널(캔들·52주·시총·PER·외인소진율·수급·★관심).
  // tick=0이면 실시간 append를 끈다 — 여긴 아카이브 화면이라 폴링 시세가 없다.
  const [sel, setSel] = useState<ChartTarget | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async (d: number) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setErr(null);
    try {
      const [h, f] = await Promise.all([fetchFlowHistory(d, ctrl.signal), fetchForecast(ctrl.signal)]);
      if (ctrl.signal.aborted) return;
      setHist(h);
      setFc(f);
    } catch (e) {
      if (!ctrl.signal.aborted) setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load(days);
    return () => abortRef.current?.abort();
  }, [days, load]);

  // 지금 주도 — 기간이 바뀔 때만 다시 받는다(탭 전환 시 재요청 없음)
  useEffect(() => {
    const ctrl = new AbortController();
    setMom(null);
    fetchMomentum(momDays, ctrl.signal)
      .then((m) => !ctrl.signal.aborted && setMom(m))
      .catch((e) => {
        if (!ctrl.signal.aborted) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => ctrl.abort();
  }, [momDays]);

  const collect = useCallback(async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await collectFlow(1);
      if (r.error) setErr(r.error);
      else if (r.skipped) setMsg(r.skipped);
      else if (r.saved) setMsg(`${r.saved}일 새로 저장 (${r.seconds ?? 0}초)`);
      else setMsg('새로 저장할 날짜가 없습니다 — 이미 최신입니다.');
      await load(days);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [days, load]);

  const arc = hist?.archive;

  return (
    <div className="mf-wrap">
      <section className="card mf-card">
        <h3>
          <span className="dot" />
          자금 흐름 아카이브
          <span className="exch">로컬 보관 · 마감 후 자동 저장</span>
        </h3>
        <div className="mf-arc-body">
          <dl className="mf-arc-stats">
            <div>
              <dt>저장 일수</dt>
              <dd>{arc ? `${arc.days.toLocaleString()}일` : '—'}</dd>
            </div>
            <div>
              <dt>기간</dt>
              <dd className="sm">{arc ? `${fmtFull(arc.first)} ~ ${fmtFull(arc.last)}` : '—'}</dd>
            </div>
            <div>
              <dt>용량</dt>
              <dd>{arc ? fmtMB(arc.bytes) : '—'}</dd>
            </div>
          </dl>
          {/* 이 칩은 아카이브가 아니라 아래 히트맵·계보가 보는 창을 바꾼다 — 라벨로 명시 */}
          <div className="mf-arc-ctl">
            <span className="mf-arc-ctl-lb">히트맵 기간</span>
            <div className="mf-seg">
              {DAY_OPTIONS.map((d) => (
                <button key={d} type="button" className={days === d ? 'on' : ''} onClick={() => setDays(d)}>
                  {d}일
                </button>
              ))}
            </div>
            <button type="button" className="mf-btn" onClick={() => void collect()} disabled={busy}>
              {busy ? '수집 중…' : '오늘 수집'}
            </button>
            {msg && <div className="mf-arc-msg">{msg}</div>}
          </div>
        </div>
      </section>

      {err && <div className="mf-err">불러오지 못했습니다 — {err}</div>}

      <section className="card mf-card">
        <h3>
          <span className="dot" />
          오늘 · 실시간
          <span className="exch">장중 미확정 · 강도% 기준</span>
        </h3>
        <TodayLive onPick={setSel} />
      </section>

      <section className="card mf-card">
        <h3>
          <span className="dot" />
          {pathTab === 'forecast' ? '예상 경로' : '지금 주도'}
          <span className="exch">
            {pathTab === 'forecast' ? '아직 안 들어온 곳 · 적중률 동반' : '이미 들어와 끌고 가는 곳'}
          </span>
          <div className="mf-seg sm">
            <button
              type="button"
              className={pathTab === 'forecast' ? 'on' : ''}
              onClick={() => setPathTab('forecast')}
            >
              예상 경로
            </button>
            <button
              type="button"
              className={pathTab === 'momentum' ? 'on' : ''}
              onClick={() => setPathTab('momentum')}
            >
              지금 주도
            </button>
          </div>
        </h3>
        {pathTab === 'forecast' ? (
          <ForecastPanel fc={fc} onPick={setSel} />
        ) : (
          <MomentumPanel mom={mom} days={momDays} setDays={setMomDays} onPick={setSel} />
        )}
      </section>

      <section className="card mf-card">
        <h3>
          <span className="dot" />
          자금 흐름 히트맵
          <span className="exch">빨강 유입 / 파랑 유출</span>
          <div className="mf-seg sm">
            <button
              type="button"
              className={metric === 'strength' ? 'on' : ''}
              onClick={() => setMetric('strength')}
            >
              강도%
            </button>
            <button type="button" className={metric === 'net' ? 'on' : ''} onClick={() => setMetric('net')}>
              절대금액
            </button>
          </div>
        </h3>
        {hist ? (
          hist.dates.length ? (
            <Heatmap hist={hist} metric={metric} onHover={setTip} />
          ) : (
            <div className="mf-empty">저장된 날짜가 없습니다. ‘오늘 수집’을 눌러보세요.</div>
          )
        ) : (
          <div className="mf-skel">히트맵 불러오는 중…</div>
        )}
        <p className="mf-note">
          강도% = (외국인+기관 순매수) ÷ 거래대금 × 100. 절대금액은 삼성전자 한 종목이 하루 수조 원을
          움직여 반도체가 항상 압도하므로, 테마 간 비교는 강도%가 맞습니다.
        </p>
      </section>

      <section className="card mf-card">
        <h3>
          <span className="dot" />
          주도주 계보
          <span className="exch">날짜별 1위 테마 · 최근순</span>
        </h3>
        {hist ? <Lineage hist={hist} onPick={setSel} /> : <div className="mf-skel">불러오는 중…</div>}
      </section>

      <ChartPanel target={sel} tick={0} onClose={() => setSel(null)} />

      {tip && (
        <div
          className="mf-tip"
          style={{ left: Math.min(tip.x + 14, window.innerWidth - 340), top: tip.y + 14 }}
        >
          <b>
            {tip.theme} · {fmtFull(tip.date)}
          </b>
          <span>{tip.text}</span>
        </div>
      )}
    </div>
  );
}
