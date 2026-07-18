import { useMemo, useState } from 'react';
import type { PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw, pct } from '../../util/format';
import { portfolioBpm } from '../../util/heart';
import { OrganicCoreScene } from '../organic-core/OrganicCoreScene';
import { MiniDonut } from './MiniDonut';
import { HoverCard, type HoverTarget } from './HoverCard';
import { Spark } from './shared';

/**
 * Dashboard — 프로토타입(full-dashboard-v2.html)의 3열 그리드 레이아웃을 복원.
 * 3D 심장·청록 색상은 유지. 좌측 3단 리스트 / 중앙 심장+총합+섹터플로우 / 우측 랭킹.
 * 리스트 항목 호버 시 정확한 값+기준시각(Truth Layer) 카드가 뜬다.
 */

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

export function Dashboard({ snapshot }: { snapshot: PortfolioSnapshot }) {
  const hover = useHover();
  const t = snapshot.totals;
  const bpm = portfolioBpm(t.total.pnlPct);

  const { kr, us, crypto, ranked } = useMemo(() => {
    const ps = [...snapshot.positions];
    const byVal = (a: Position, b: Position) => b.value - a.value;
    return {
      kr: ps.filter((p) => p.assetType === 'stock' && p.region === 'KR').sort(byVal),
      us: ps.filter((p) => p.assetType === 'stock' && p.region === 'US').sort(byVal),
      crypto: ps.filter((p) => p.assetType === 'crypto').sort(byVal),
      // 우측 랭킹: 내 보유 종목을 수익률 순으로 (시장 전체 랭킹은 데이터 소스 미연동)
      ranked: [...ps].sort((a, b) => b.ret - a.ret),
    };
  }, [snapshot]);

  const usSectors = useMemo(
    () =>
      snapshot.sectorFlows
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .sort((a, b) => (b.ret ?? 0) - (a.ret ?? 0)),
    [snapshot],
  );

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

      {/* ── 중앙 하단: 섹터 플로우 (미국 SPDR 일간) ── */}
      <div className="card flow-card">
        <h3>
          <span className="dot" />
          SECTOR FLOW · 미국(SPDR)
          <span className="exch">전일 대비</span>
        </h3>
        <div className="sector-cols">
          {usSectors.map((s) => {
            const r = s.ret ?? 0;
            const w = Math.min(Math.abs(r) * 14, 100);
            return (
              <div className="sector-bar-row" key={s.id} title={`${s.name} ${r}%`}>
                <span className="sector-name">{s.name}</span>
                <div className="sector-track">
                  <div
                    className="sector-fill"
                    style={{ width: `${w}%`, background: r >= 0 ? 'var(--up)' : 'var(--down)' }}
                  />
                </div>
                <span className="sector-pct" style={{ color: r >= 0 ? 'var(--up)' : 'var(--down)' }}>
                  {r >= 0 ? '+' : ''}
                  {r.toFixed(1)}
                </span>
              </div>
            );
          })}
          {usSectors.length === 0 && <div className="list-empty">섹터 데이터 로딩…</div>}
        </div>
      </div>

      {/* ── 우측: 내 보유 랭킹 ── */}
      <div className="card ranking-card">
        <h3>
          <span className="dot" />
          내 종목 랭킹
          <span className="exch">수익률 순</span>
        </h3>
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
