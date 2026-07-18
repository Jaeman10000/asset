import { useEffect, useMemo, useState } from 'react';
import type { MarketStock, PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw, pct } from '../../util/format';
import { HoverCard, fromMarket, fromPosition, type HoverInfo, type HoverTarget } from './HoverCard';
import { sectorHue, type RingSector } from '../organic-core/HoloSectorRings';
import { Spark } from './shared';

/**
 * Dashboard — 심장이 중앙 무대(홀로그램), 정보가 주위에 떠 있는 구성.
 *   상단: 자산군 총합 4개 (크게, 갱신 시 금색 플래시)
 *   좌:   한국/미국/암호화폐 상세 (주가 흐름 스파크라인 + 수급 호버)
 *   중앙: SYSTEM PULSE — 3D 심장 + 홀로그램 섹터 궤도(배경 씬) + 총액 융합
 *         하단: 섹터 리드아웃 (KR 12 + US 11 전체 수치)
 *   우:   오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관)
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

/** 리스트 행 — 캡처 레퍼런스처럼 이름 · 라인그래프 · 값 · 등락% */
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
      <div className="n">
        {p.name}
        <small>{p.symbol}</small>
      </div>
      <Spark history={p.history} color="auto" width={56} height={18} />
      <div className="v">{krwCompact(p.value)}</div>
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

/** 하단 섹터 리드아웃 — 3D 링의 수치를 정확히 읽는 Truth Layer */
function SectorReadout({ kr, us }: { kr: RingSector[]; us: RingSector[] }) {
  const col = (sectors: RingSector[], side: 'kr' | 'us', title: string) => {
    const maxAbs = Math.max(...sectors.map((s) => Math.abs(s.ret)), 0.1);
    return (
      <div className="readout-col">
        <div className="readout-head">{title}</div>
        {sectors.map((s) => (
          <div className="readout-row" key={s.name}>
            <i style={{ background: `hsl(${sectorHue(s, side)}, 85%, 62%)` }} />
            <span className="rn">{s.name}</span>
            <div className="rt">
              <div
                className="rf"
                style={{
                  width: `${(Math.abs(s.ret) / maxAbs) * 100}%`,
                  background: s.ret >= 0 ? 'var(--up)' : 'var(--down)',
                }}
              />
            </div>
            <span className="rv" style={{ color: s.ret >= 0 ? 'var(--up)' : 'var(--down)' }}>
              {s.ret >= 0 ? '+' : ''}
              {s.ret.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    );
  };
  return (
    <div className="card sector-readout">
      <h3>
        <span className="dot" />
        SECTOR FLOW · 심장 궤도
        <span className="exch">KR 수급 · US 전일 · 모의</span>
      </h3>
      <div className="readout-cols">
        {col(kr, 'kr', '한국 · KRX')}
        {col(us, 'us', '미국 · SPDR')}
      </div>
    </div>
  );
}

export function Dashboard({
  snapshot,
  bpm,
  krSectors,
  usSectors,
}: {
  snapshot: PortfolioSnapshot;
  bpm: number;
  krSectors: RingSector[];
  usSectors: RingSector[];
}) {
  const hover = useHover();
  const [rankTab, setRankTab] = useState<RankTabKey>('up');
  const [flashIdx, setFlashIdx] = useState<number | null>(null);
  const t = snapshot.totals;

  // 데이터 갱신 순간 = 총합 카드 하나가 금색 플래시 (스펙: 갱신 순간만 발광)
  useEffect(() => {
    const idx = Math.floor(snapshot.fetchedAt / 1000) % 4;
    setFlashIdx(idx);
    const id = setTimeout(() => setFlashIdx(null), 900);
    return () => clearTimeout(id);
  }, [snapshot.fetchedAt]);

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

  // 구버전 백엔드(사이드카 exe 등)엔 marketRanking이 없을 수 있음 — 방어
  const ranking = useMemo(
    () => sortRanking(snapshot.marketRanking ?? [], rankTab).slice(0, 10),
    [snapshot, rankTab],
  );

  const beatSec = 60 / Math.max(bpm, 40);

  const tiles = [
    { lbl: 'KR 주식', b: t.kr },
    { lbl: 'US 주식', b: t.us },
    { lbl: '주식 총합', b: t.stock },
    { lbl: '암호화폐', b: t.crypto },
  ];

  return (
    <div className="stage-wrap">
      {/* ── 상단: 자산군 총합 4개 (크게) ── */}
      <div className="totals-row">
        {tiles.map((tile, i) => (
          <div key={tile.lbl} className={`card total-card ${flashIdx === i ? 'event-flash' : ''}`}>
            <div className="lbl">{tile.lbl}</div>
            <div className="amt">{krwCompact(tile.b.value)}</div>
            <div className="pct" style={{ color: tile.b.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
              {pct(tile.b.pnlPct)}
            </div>
          </div>
        ))}
      </div>

      <div className="stage">
        {/* ── 좌측: 3단 세로 리스트 (라인그래프) ── */}
        <div className="col-left">
          <ListCard title="한국 주식 상세" exch="실시간" positions={kr} empty="보유 종목 없음" hover={hover} />
          <ListCard title="미국 주식 상세" exch="실시간" positions={us} empty="보유 종목 없음" hover={hover} />
          <ListCard title="암호화폐 상세" exch="업비트 · 빗썸" positions={crypto} empty="보유 종목 없음" hover={hover} />
        </div>

        {/* ── 중앙: 홀로그램 무대 (심장+궤도는 배경 씬) + 총액 + 섹터 리드아웃 ── */}
        <div className="col-center">
          <div className="heart-overlay">
            <div className="heart-label">
              <span className="dot" />
              SYSTEM PULSE
              <span className="bpm-badge">{bpm} BPM</span>
            </div>

            <div className="beat-rings" style={{ ['--beat' as string]: `${beatSec}s` }}>
              <span />
              <span />
            </div>

            <div className="heart-space" />

            <div className="heart-center-info" style={{ ['--beat' as string]: `${beatSec}s` }}>
              <div className="total-halo" aria-hidden />
              <div className="lbl">TOTAL PORTFOLIO</div>
              <div className="total">{t.total.value > 0 ? krw(t.total.value) : '—'}</div>
              <div className="pnl" style={{ color: t.total.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
                {pct(t.total.pnlPct)}
              </div>
            </div>
          </div>

          <SectorReadout kr={krSectors} us={usSectors} />
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
      </div>

      <HoverCard target={hover.target} />
    </div>
  );
}
