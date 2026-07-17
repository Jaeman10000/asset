import { useMemo } from 'react';
import type { PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw } from '../../util/format';
import { Pct, Spark } from './shared';

/**
 * Dashboard — 3D 씬 위에 얹히는 유리 카드 오버레이. 전부 실 스냅샷 기반.
 *
 * 레이아웃 (스펙 1장):
 *   상단: 자산군 총합 4개
 *   좌측: 국내 주식 상세 리스트
 *   우측 상단: 워치리스트(값 큰 종목 2개)
 *   우측 하단: 암호화폐 상세
 *   좌하단: 심장(BPM+총자산)
 *   중앙 하단: 미국 섹터 흐름
 */

const FLOAT = ['float-a', 'float-b', 'float-c', 'float-d'];

function totalsCards(snap: PortfolioSnapshot) {
  const t = snap.totals;
  return [
    { key: 'kr', label: 'KR 주식', bucket: t.kr },
    { key: 'us', label: 'US 주식', bucket: t.us },
    { key: 'stock', label: '주식 총합', bucket: t.stock },
    { key: 'crypto', label: '암호화폐', bucket: t.crypto },
  ];
}

function PositionRow({ p }: { p: Position }) {
  return (
    <li className="pos-row">
      <span className="pos-name" title={p.symbol}>
        {p.name}
      </span>
      <Spark history={p.history} color="auto" width={48} height={16} />
      <span className="pos-value">{krwCompact(p.value)}</span>
      <Pct value={p.ret} />
    </li>
  );
}

export function Dashboard({
  snapshot,
  flashKey,
}: {
  snapshot: PortfolioSnapshot;
  /** 갱신 순간마다 바뀌는 값 — 총합 카드 금색 플래시 트리거 */
  flashKey: number;
}) {
  const cards = totalsCards(snapshot);

  const { stocks, crypto, watchlist } = useMemo(() => {
    const positions = [...snapshot.positions];
    // 좌측 리스트: 주식 전체(국내+미국), 평가금액 순
    const stocks = positions
      .filter((p) => p.assetType === 'stock')
      .sort((a, b) => b.value - a.value);
    const crypto = positions
      .filter((p) => p.assetType === 'crypto')
      .sort((a, b) => b.value - a.value);
    // 워치리스트: 평가금액 상위 2종목 (스펙: 편집 가능한 큰 카드 2개 — 지금은 자동 선택)
    const watchlist = [...positions].sort((a, b) => b.value - a.value).slice(0, 2);
    return { stocks, crypto, watchlist };
  }, [snapshot]);

  const usSectors = useMemo(
    () =>
      snapshot.sectorFlows
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .sort((a, b) => (b.ret ?? 0) - (a.ret ?? 0)),
    [snapshot],
  );

  return (
    <>
      {/* 상단 자산군 총합 4개 */}
      <header className="totals-row">
        {cards.map((c, i) => (
          <div
            key={c.key}
            className={`glass-card stat-card ${FLOAT[i]} ${
              flashKey % cards.length === i && flashKey > 0 ? 'event-flash' : ''
            }`}
          >
            <span className="stat-label">{c.label}</span>
            <strong className="stat-value">{krwCompact(c.bucket.value)}</strong>
            <Pct value={c.bucket.pnlPct} />
          </div>
        ))}
      </header>

      {/* 좌측: 주식 상세 (국내+미국) */}
      {stocks.length > 0 && (
        <aside className="detail-col detail-left glass-card float-a">
          <span className="stat-label">주식</span>
          <ul className="pos-list">
            {stocks.map((p) => (
              <PositionRow key={p.id} p={p} />
            ))}
          </ul>
        </aside>
      )}

      {/* 우측 상단: 워치리스트 */}
      {watchlist.length > 0 && (
        <aside className="watchlist-col">
          {watchlist.map((w, i) => (
            <div key={w.id} className={`glass-card watch-card ${FLOAT[(i + 2) % 4]}`}>
              <span className="stat-label">Watchlist</span>
              <strong className="stat-value">{w.name}</strong>
              <Spark history={w.history} color="auto" />
              <div className="watch-bottom">
                <span>{krwCompact(w.value)}</span>
                <Pct value={w.ret} />
              </div>
            </div>
          ))}
        </aside>
      )}

      {/* 우측 하단: 암호화폐 상세 */}
      {crypto.length > 0 && (
        <aside className="detail-col detail-right glass-card float-c">
          <span className="stat-label">암호화폐</span>
          <ul className="pos-list">
            {crypto.map((p) => (
              <PositionRow key={p.id} p={p} />
            ))}
          </ul>
        </aside>
      )}

      {/* 중앙 하단: 미국 섹터 흐름 */}
      {usSectors.length > 0 && (
        <div className="sector-flow glass-card float-d">
          <span className="stat-label">US 섹터 (일간)</span>
          <div className="sector-bars">
            {usSectors.map((s) => {
              const r = s.ret ?? 0;
              const w = Math.min(Math.abs(r) * 12, 100);
              return (
                <div key={s.id} className="sector-bar-row" title={`${s.name} ${r}%`}>
                  <span className="sector-name">{s.name}</span>
                  <div className="sector-track">
                    <div
                      className="sector-fill"
                      style={{
                        width: `${w}%`,
                        background: r >= 0 ? 'var(--up)' : 'var(--down)',
                      }}
                    />
                  </div>
                  <span className="sector-pct" style={{ color: r >= 0 ? 'var(--up)' : 'var(--down)' }}>
                    {r >= 0 ? '+' : ''}
                    {r.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 좌하단: 심장(BPM + 총자산) */}
      <div className="glass-card bpm-card float-b">
        <span className="stat-label">Heart</span>
        <strong className="stat-value" style={{ color: 'var(--event)' }}>
          {snapshot.totals.total.value > 0 ? krw(snapshot.totals.total.value) : '—'}
        </strong>
        <span className="stat-sub">
          손익 <Pct value={snapshot.totals.total.pnlPct} />
        </span>
      </div>
    </>
  );
}
