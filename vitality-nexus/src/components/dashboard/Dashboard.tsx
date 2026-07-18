import { useMemo, useState } from 'react';
import type { MarketStock, PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw, pct } from '../../util/format';
import { MiniDonut } from './MiniDonut';
import { HoverCard, fromMarket, fromPosition, type HoverInfo, type HoverTarget } from './HoverCard';
import { SectorFlowOrbs, type OrbSector } from './SectorFlowOrbs';

/**
 * Dashboard — 프로토타입의 정보 구조 전체 + exe의 질감.
 *   좌: 한국/미국/암호화폐 상세 (미니도넛, 수급 호버)
 *   중앙: SYSTEM PULSE (3D 심장이 배경에서 비침, 심박 파장이 UI로 퍼짐, 총액 융합)
 *        + SECTOR FLOW 오브 (KR 12섹터 3색 수급 파티클 / US SPDR)
 *   우: 오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관)
 */

type RankTabKey = 'up' | 'down' | 'volume' | 'foreign' | 'inst';

const RANK_TABS: { key: RankTabKey; label: string }[] = [
  { key: 'up', label: '상승' },
  { key: 'down', label: '하락' },
  { key: 'volume', label: '거래량' },
  { key: 'foreign', label: '외국인' },
  { key: 'inst', label: '기관' },
];

function sortRanking(list: MarketStock[], tab: RankTabKey): MarketStock[] {
  const out = [...list];
  switch (tab) {
    case 'up':
      return out.sort((a, b) => b.ret - a.ret);
    case 'down':
      return out.sort((a, b) => a.ret - b.ret);
    case 'volume':
      return out.sort((a, b) => b.volume - a.volume);
    case 'foreign':
      return out.sort((a, b) => b.investors.foreign - a.investors.foreign);
    case 'inst':
      return out.sort((a, b) => b.investors.inst - a.investors.inst);
  }
}

/** 탭에 맞는 우측 지표 텍스트/색 */
function rankMetric(m: MarketStock, tab: RankTabKey): { text: string; color: string } {
  const eok = (v: number) =>
    (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR') + '억';
  switch (tab) {
    case 'up':
    case 'down':
      return { text: pct(m.ret), color: m.ret >= 0 ? 'var(--up)' : 'var(--down)' };
    case 'volume':
      return { text: (m.volume / 1e6).toFixed(1) + 'M', color: 'var(--life)' };
    case 'foreign':
      return {
        text: eok(m.investors.foreign),
        color: m.investors.foreign >= 0 ? 'var(--up)' : 'var(--down)',
      };
    case 'inst':
      return {
        text: eok(m.investors.inst),
        color: m.investors.inst >= 0 ? 'var(--up)' : 'var(--down)',
      };
  }
}

function useHover() {
  const [target, setTarget] = useState<HoverTarget | null>(null);
  const onEnter = (info: HoverInfo) => (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setTarget({ info, x: r.right, y: r.top });
  };
  const onLeave = () => setTarget(null);
  return { target, onEnter, onLeave };
}

function MiniRow({
  p,
  onEnter,
  onLeave,
}: {
  p: Position;
  onEnter: (e: React.MouseEvent) => void;
  onLeave: () => void;
}) {
  const up = p.ret >= 0;
  return (
    <div className="mini-holding" onMouseEnter={onEnter} onMouseLeave={onLeave}>
      <MiniDonut ret={p.ret} />
      <div className="mini-mid">
        <div className="n">
          {p.name}
          <small>{p.symbol}</small>
        </div>
        <div className="v">{krwCompact(p.value)}</div>
      </div>
      <div className={`p ${up ? 'up' : 'down'}`}>{pct(p.ret)}</div>
    </div>
  );
}

function ListCard({
  title,
  exch,
  positions,
  empty,
  hover,
}: {
  title: string;
  exch: string;
  positions: Position[];
  empty: string;
  hover: ReturnType<typeof useHover>;
}) {
  return (
    <div className="card list-card">
      <h3>
        <span className="dot" />
        {title}
        <span className="exch">{exch}</span>
      </h3>
      <div className="list">
        {positions.length === 0 ? (
          <div className="list-empty">{empty}</div>
        ) : (
          positions.map((p) => (
            <MiniRow
              key={p.id}
              p={p}
              onEnter={hover.onEnter(fromPosition(p))}
              onLeave={hover.onLeave}
            />
          ))
        )}
      </div>
    </div>
  );
}

export function Dashboard({ snapshot, bpm }: { snapshot: PortfolioSnapshot; bpm: number }) {
  const hover = useHover();
  const [rankTab, setRankTab] = useState<RankTabKey>('up');
  const t = snapshot.totals;

  const { kr, us, crypto, heldSymbols } = useMemo(() => {
    const ps = [...snapshot.positions];
    const byVal = (a: Position, b: Position) => b.value - a.value;
    return {
      kr: ps.filter((p) => p.assetType === 'stock' && p.region === 'KR').sort(byVal),
      us: ps.filter((p) => p.assetType === 'stock' && p.region === 'US').sort(byVal),
      crypto: ps.filter((p) => p.assetType === 'crypto').sort(byVal),
      heldSymbols: new Set(ps.map((p) => p.symbol)),
    };
  }, [snapshot]);

  const ranking = useMemo(
    () => sortRanking(snapshot.marketRanking, rankTab).slice(0, 10),
    [snapshot, rankTab],
  );

  // 섹터 오브: KR은 12개 섹터(수급 강도 포함 — 3색 파티클), US는 실 SPDR
  const krOrb: OrbSector[] = useMemo(
    () =>
      snapshot.sectorFlows
        .filter((s) => s.region === 'KR')
        .map((s) => ({
          name: s.name,
          ret: s.ret ?? 0,
          foreign: s.foreign ?? 0,
          inst: s.inst ?? 0,
          individual: s.individual ?? 0,
        })),
    [snapshot],
  );
  const usOrb: OrbSector[] = useMemo(
    () =>
      snapshot.sectorFlows
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .map((s) => ({ name: s.name, ret: s.ret ?? 0 })),
    [snapshot],
  );

  const beatSec = 60 / Math.max(bpm, 40);

  const tiles = [
    { lbl: '주식 · 한국', b: t.kr },
    { lbl: '주식 · 미국', b: t.us },
    { lbl: '주식 총합', b: t.stock },
    { lbl: '암호화폐', b: t.crypto },
  ];

  return (
    <div className="stage">
      {/* ── 좌측: 3단 세로 리스트 ── */}
      <div className="col-left">
        <ListCard title="한국 주식 상세" exch="실시간" positions={kr} empty="보유 종목 없음" hover={hover} />
        <ListCard title="미국 주식 상세" exch="실시간" positions={us} empty="보유 종목 없음" hover={hover} />
        <ListCard title="암호화폐 상세" exch="업비트 · 빗썸" positions={crypto} empty="보유 종목 없음" hover={hover} />
      </div>

      {/* ── 중앙 상단: SYSTEM PULSE — 심장(배경)과 총액이 하나의 생명체처럼 ── */}
      <div className="heart-overlay">
        <div className="heart-label">
          <span className="dot" />
          SYSTEM PULSE
          <span className="bpm-badge">{bpm} BPM</span>
        </div>

        {/* 심박 파장 — 심장에서 대시보드로 퍼지는 링 (bpm과 동기) */}
        <div className="beat-rings" style={{ ['--beat' as string]: `${beatSec}s` }}>
          <span />
          <span />
        </div>

        {/* 심장이 보이는 영역 (배경 3D가 비침) */}
        <div className="heart-space" />

        {/* 총액 — 심장 바로 아래, 심장의 빛을 이어받는 위치 */}
        <div className="heart-center-info" style={{ ['--beat' as string]: `${beatSec}s` }}>
          <div className="lbl">TOTAL PORTFOLIO</div>
          <div className="total">{t.total.value > 0 ? krw(t.total.value) : '—'}</div>
          <div className="pnl" style={{ color: t.total.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
            {pct(t.total.pnlPct)}
          </div>
        </div>

        <div className="asset-totals">
          {tiles.map((tile) => (
            <div className="asset-tile" key={tile.lbl}>
              <div className="lbl">{tile.lbl}</div>
              <div className="amt">{krwCompact(tile.b.value)}</div>
              <div className="pct" style={{ color: tile.b.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
                {pct(tile.b.pnlPct)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── 중앙 하단: 섹터 플로우 오브 ── */}
      <div className="card flow-card">
        <SectorFlowOrbs kr={krOrb} us={usOrb} />
        <h3>
          <span className="dot" />
          SECTOR FLOW · 한국(KRX) + 미국(SPDR)
          <span className="exch">KR 수급 · US 전일 · 모의</span>
        </h3>
        <div className="flow-labels">
          <div className="flow-side">
            <div className="flow-region">한국 · KRX</div>
            <b>{topNames(krOrb) || '로딩…'}</b>
          </div>
          <div className="flow-side">
            <div className="flow-region">미국 · SPDR</div>
            <b>{topNames(usOrb) || '로딩…'}</b>
          </div>
        </div>
      </div>

      {/* ── 우측: 오늘의 시장 랭킹 ── */}
      <div className="card ranking-card">
        <h3>
          <span className="dot" />
          오늘의 시장 랭킹
          <span className="exch">키움 연동 전 · 모의</span>
        </h3>
        <div className="ranking-tabs">
          {RANK_TABS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={rankTab === key ? 'on' : ''}
              onClick={() => setRankTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="ranking-list">
          {ranking.map((m, i) => {
            const metric = rankMetric(m, rankTab);
            const held = heldSymbols.has(m.symbol);
            const topClass = i < 3 ? `rank-top rank-${i + 1}` : '';
            return (
              <div
                key={m.symbol}
                className={`rank-row ${topClass}`}
                onMouseEnter={hover.onEnter(fromMarket(m, held))}
                onMouseLeave={hover.onLeave}
              >
                <span className="rank-no">{i + 1}</span>
                <div className="rank-mid">
                  <div className="n">
                    {m.name}
                    <small>{m.symbol}</small>
                    {held && <span className="held-chip">보유</span>}
                  </div>
                  <div className="v">
                    ₩{m.price.toLocaleString('ko-KR')} · {(m.volume / 1e6).toFixed(1)}M
                  </div>
                </div>
                <div className="p" style={{ color: metric.color }}>
                  {metric.text}
                </div>
              </div>
            );
          })}
          {ranking.length === 0 && <div className="list-empty">랭킹 로딩…</div>}
        </div>
      </div>

      <HoverCard target={hover.target} />
    </div>
  );
}

/** 등락률 상위 3개 이름 (flow-labels용) */
function topNames(sectors: OrbSector[]): string {
  return [...sectors]
    .sort((a, b) => b.ret - a.ret)
    .slice(0, 3)
    .map((s) => s.name)
    .join(' · ');
}
