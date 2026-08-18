import { useCallback, useEffect, useState } from 'react';
import { fetchWatchlistQuotes, saveWatchlist, type WatchQuote } from '../../api/client';
import type { ChartTarget } from '../../api/types';

/**
 * ★ 관심종목 카드 — 검색/상세에서 ☆로 등록한 종목을 고정 표시.
 *
 * 시세는 /watchlist/quotes 한 방(서버가 ka10001 60초 캐시 + 일봉 스파크)으로 받고,
 * 60초 주기 + 상세 패널에서 별 토글 시(vn:watchlist-changed) 즉시 갱신.
 * 행 클릭 → 상세 차트. ✕ → 즉시 제거.
 */
export function WatchlistCard({
  onOpen,
  refreshTick,
}: {
  onOpen: (t: ChartTarget) => void;
  refreshTick: number; // snapshot.fetchedAt — 수동 새로고침 시에도 같이 갱신
}) {
  const [rows, setRows] = useState<WatchQuote[]>([]);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(() => {
    fetchWatchlistQuotes()
      .then((r) => {
        setRows(r.items);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    const onChanged = () => load();
    window.addEventListener('vn:watchlist-changed', onChanged);
    return () => {
      clearInterval(id);
      window.removeEventListener('vn:watchlist-changed', onChanged);
    };
  }, [load]);

  // 수동 새로고침 등 스냅샷 갱신에 편승
  useEffect(() => {
    if (refreshTick) load();
  }, [refreshTick, load]);

  const remove = async (code: string) => {
    const next = rows.filter((r) => r.code !== code).map((r) => ({ code: r.code, name: r.name }));
    setRows((cur) => cur.filter((r) => r.code !== code)); // 낙관적 반영
    try {
      await saveWatchlist(next);
    } catch {
      load(); // 실패 시 서버 상태로 복원
    }
  };

  if (loaded && rows.length === 0) {
    return (
      <div className="card watch-card">
        <h3>
          <span className="dot gold" />
          관심종목
        </h3>
        <div className="watch-empty">
          검색(<kbd>/</kbd>)으로 종목을 찾아 <b>☆ 관심 등록</b>하면 여기에 고정됩니다.
        </div>
      </div>
    );
  }

  return (
    <div className="card watch-card">
      <h3>
        <span className="dot gold" />
        관심종목
        <span className="exch">{rows.length}종목 · 키움 실시간</span>
      </h3>
      <div className="watch-list">
        {rows.map((r) => {
          const up = (r.ret ?? 0) >= 0;
          const spark = r.spark && r.spark.length > 1 ? r.spark : null;
          let path = '';
          if (spark) {
            const min = Math.min(...spark);
            const max = Math.max(...spark);
            const range = max - min || 1;
            path = spark
              .map(
                (v, i) =>
                  `${i ? 'L' : 'M'}${((i / (spark.length - 1)) * 64).toFixed(1)} ${(16 - ((v - min) / range) * 14 + 1).toFixed(1)}`,
              )
              .join(' ');
          }
          return (
            <div
              key={r.code}
              className="watch-row"
              onClick={() =>
                onOpen({
                  symbol: r.code,
                  name: r.name,
                  assetType: 'stock',
                  region: 'KR',
                  currency: 'KRW',
                  price: r.price,
                  ret: r.ret,
                })
              }
            >
              <span className="w-star">★</span>
              <span className="w-name">
                {r.name}
                <small>{r.code}</small>
              </span>
              {spark && (
                <svg className="w-spark" width="64" height="18" viewBox="0 0 64 18">
                  <path
                    d={path}
                    fill="none"
                    stroke={up ? 'var(--up)' : 'var(--down)'}
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              )}
              <span className="w-price">
                {r.price != null ? '₩' + r.price.toLocaleString('ko-KR') : '—'}
              </span>
              <span className="w-ret" style={{ color: up ? 'var(--up)' : 'var(--down)' }}>
                {r.ret != null ? (r.ret >= 0 ? '+' : '−') + Math.abs(r.ret).toFixed(2) + '%' : ''}
              </span>
              <button
                type="button"
                className="w-remove"
                title="관심종목에서 제거"
                onClick={(e) => {
                  e.stopPropagation();
                  void remove(r.code);
                }}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
