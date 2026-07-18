import { useMemo, useState } from 'react';
import type { PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw, pct } from '../../util/format';
import { portfolioBpm } from '../../util/heart';
import { OrganicCoreScene } from '../organic-core/OrganicCoreScene';
import { MiniDonut } from './MiniDonut';
import { HoverCard, type HoverTarget } from './HoverCard';
import { SectorFlowOrbs, type OrbSector } from './SectorFlowOrbs';
import { Spark } from './shared';

export type AssetFilter = 'all' | 'stock' | 'crypto';
type SortMode = 'up' | 'down' | 'value';

/**
 * Dashboard — 프로토타입(full-dashboard-v2.html)의 3열 그리드 레이아웃을 복원.
 * 3D 심장·청록 색상은 유지. 좌측 3단 리스트 / 중앙 심장+총합+섹터플로우 / 우측 랭킹.
 * 리스트 항목 호버 시 정확한 값+기준시각(Truth Layer) 카드가 뜬다.
 */

/** 등락률 상위 섹터 이름 3개를 " · "로 (flow-labels용) */
function topSectorNames(sectors: OrbSector[]): string {
  return [...sectors]
    .sort((a, b) => b.ret - a.ret)
    .slice(0, 3)
    .map((s) => s.name)
    .join(' · ');
}

function useHover() {
  const [target, setTarget] = useState<HoverTarget | null>(null);
  const onEnter = (pos: Position) => (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setTarget({ pos, x: r.right, y: r.top });
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
            <MiniRow key={p.id} p={p} onEnter={hover.onEnter(p)} onLeave={hover.onLeave} />
          ))
        )}
      </div>
    </div>
  );
}

export function Dashboard({
  snapshot,
  assetFilter = 'all',
}: {
  snapshot: PortfolioSnapshot;
  assetFilter?: AssetFilter;
}) {
  const hover = useHover();
  const [sortMode, setSortMode] = useState<SortMode>('up');
  const t = snapshot.totals;
  const bpm = portfolioBpm(t.total.pnlPct);

  const { kr, us, crypto } = useMemo(() => {
    const ps = [...snapshot.positions];
    const byVal = (a: Position, b: Position) => b.value - a.value;
    return {
      kr: ps.filter((p) => p.assetType === 'stock' && p.region === 'KR').sort(byVal),
      us: ps.filter((p) => p.assetType === 'stock' && p.region === 'US').sort(byVal),
      crypto: ps.filter((p) => p.assetType === 'crypto').sort(byVal),
    };
  }, [snapshot]);

  // 우측 랭킹: 자산 필터 + 정렬 모드 적용 (상단/랭킹 탭)
  const ranked = useMemo(() => {
    let ps = snapshot.positions.filter((p) =>
      assetFilter === 'all' ? true : assetFilter === 'crypto' ? p.assetType === 'crypto' : p.assetType === 'stock',
    );
    ps = [...ps];
    if (sortMode === 'up') ps.sort((a, b) => b.ret - a.ret);
    else if (sortMode === 'down') ps.sort((a, b) => a.ret - b.ret);
    else ps.sort((a, b) => b.value - a.value);
    return ps;
  }, [snapshot, assetFilter, sortMode]);

  // 섹터 오브 데이터: US는 실 SPDR, KR은 보유 종목을 섹터별 평균 등락률로
  const usOrb: OrbSector[] = useMemo(
    () =>
      snapshot.sectorFlows
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .map((s) => ({ name: s.name, ret: s.ret ?? 0 })),
    [snapshot],
  );
  const krOrb: OrbSector[] = useMemo(() => {
    const bySector = new Map<string, { sum: number; n: number }>();
    for (const p of snapshot.positions) {
      if (p.assetType !== 'stock' || p.region !== 'KR') continue;
      const key = p.sector || '기타';
      const cur = bySector.get(key) ?? { sum: 0, n: 0 };
      cur.sum += p.ret;
      cur.n += 1;
      bySector.set(key, cur);
    }
    return [...bySector.entries()].map(([name, v]) => ({ name, ret: v.sum / v.n }));
  }, [snapshot]);

  const usSectors = usOrb;

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

      {/* ── 중앙 상단: 심장 + 자산군 총합 ── */}
      <div className="card heart-card">
        <div className="heart-label">
          <span className="dot" />
          SYSTEM PULSE
          <span className="bpm-badge">{bpm} BPM</span>
        </div>

        {/* 3D 심장 (카드 안에 담김) */}
        <div className="heart-canvas">
          <OrganicCoreScene bpm={bpm} />
        </div>

        <div className="heart-center-info">
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

      {/* ── 중앙 하단: 섹터 플로우 오브 (한국 + 미국) ── */}
      <div className="card flow-card">
        <SectorFlowOrbs kr={krOrb} us={usSectors} />
        <h3>
          <span className="dot" />
          SECTOR FLOW · 한국 + 미국(SPDR)
          <span className="exch">전일 대비</span>
        </h3>
        <div className="flow-labels">
          <div className="flow-side">
            <div className="flow-region">한국 · 보유 섹터</div>
            <b>{topSectorNames(krOrb) || '보유 없음'}</b>
          </div>
          <div className="flow-side">
            <div className="flow-region">미국 · SPDR</div>
            <b>{topSectorNames(usSectors) || '로딩…'}</b>
          </div>
        </div>
      </div>

      {/* ── 우측: 내 보유 랭킹 ── */}
      <div className="card ranking-card">
        <h3>
          <span className="dot" />
          내 종목 랭킹
        </h3>
        <div className="ranking-tabs">
          {([['up', '상승'], ['down', '하락'], ['value', '평가금액']] as const).map(([m, lbl]) => (
            <button
              key={m}
              type="button"
              className={sortMode === m ? 'on' : ''}
              onClick={() => setSortMode(m)}
            >
              {lbl}
            </button>
          ))}
        </div>
        <div className="ranking-list">
          {ranked.map((p, i) => {
            const up = p.ret >= 0;
            const topClass = i < 3 ? `rank-top rank-${i + 1}` : '';
            return (
              <div
                key={p.id}
                className={`rank-row ${topClass}`}
                onMouseEnter={hover.onEnter(p)}
                onMouseLeave={hover.onLeave}
              >
                <span className="rank-no">{i + 1}</span>
                <div className="rank-mid">
                  <div className="n">
                    {p.name}
                    <small>{p.symbol}</small>
                  </div>
                  {i < 3 ? (
                    <Spark history={p.history} color="auto" width={80} height={16} />
                  ) : (
                    <div className="v">{krwCompact(p.value)}</div>
                  )}
                </div>
                <div className={`p ${up ? 'up' : 'down'}`}>{pct(p.ret)}</div>
              </div>
            );
          })}
          {ranked.length === 0 && <div className="list-empty">보유 종목 없음</div>}
        </div>
      </div>

      <HoverCard target={hover.target} />
    </div>
  );
}
