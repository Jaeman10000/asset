import { useEffect, useMemo, useRef, useState } from 'react';
import type { Position } from '../../api/types';
import { pct } from '../../util/format';

/**
 * ChartPanel — 종목을 클릭하면 뜨는 큰 실시간 가격 차트.
 *
 * 스파크라인의 확대판: position.history(암호화폐=60분봉 종가, 주식=일봉 종가)를
 * 기준선으로 그리고, 폴링(tick=fetchedAt)마다 현재가를 라이브 버퍼에 이어붙여
 * 세션 동안 선이 자라난다. 외부 차트 라이브러리 없이 순수 SVG라 오프라인 Tauri·
 * CSP에 안전하고, 3D 심장 씬과 렌더 경로가 분리돼 성능 간섭이 없다.
 */
export function ChartPanel({
  position,
  tick,
  onClose,
}: {
  position: Position | null;
  tick: number; // snapshot.fetchedAt — 폴링마다 바뀜
  onClose: () => void;
}) {
  const [live, setLive] = useState<number[]>([]);
  const symRef = useRef<string | null>(null);
  const tickRef = useRef(0);

  // 선택 종목이 바뀌면 라이브 버퍼 리셋
  useEffect(() => {
    if (position && position.symbol !== symRef.current) {
      symRef.current = position.symbol;
      tickRef.current = 0;
      setLive([]);
    }
  }, [position]);

  // 폴링마다 현재가를 라이브 버퍼에 append (최근 120틱 유지)
  useEffect(() => {
    if (!position || !tick || tick === tickRef.current) return;
    tickRef.current = tick;
    setLive((prev) => [...prev, position.price].slice(-120));
  }, [tick, position]);

  // Esc로 닫기
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const series = useMemo(
    () => (position ? [...(position.history ?? []), ...live] : []),
    [position, live],
  );

  const geom = useMemo(() => {
    const W = 600;
    const H = 200;
    const PAD = 6;
    if (series.length < 2) return null;
    const min = Math.min(...series);
    const max = Math.max(...series);
    const range = max - min || 1;
    const stepX = (W - PAD * 2) / (series.length - 1);
    const y = (v: number) => PAD + (H - PAD * 2) * (1 - (v - min) / range);
    const pts = series.map((v, i) => [PAD + i * stepX, y(v)] as const);
    const line = pts.map(([x, py], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${py.toFixed(1)}`).join(' ');
    const area = `${line} L${pts[pts.length - 1][0].toFixed(1)} ${H - PAD} L${pts[0][0].toFixed(1)} ${H - PAD} Z`;
    const last = pts[pts.length - 1];
    return { W, H, PAD, min, max, line, area, last };
  }, [series]);

  if (!position) return null;

  const up = position.ret >= 0;
  const stroke = up ? 'var(--up)' : 'var(--down)';
  const curSym = position.currency === 'USD' ? '$' : '₩';
  const priceText = curSym + position.price.toLocaleString('ko-KR');

  const source =
    position.assetType === 'crypto'
      ? '업비트·빗썸 60분봉 · 현재가 7초 갱신'
      : position.region === 'KR'
        ? '한국거래소 일봉 · 현재가 7초 갱신'
        : 'Yahoo Finance 일봉 · 현재가 7초 갱신';

  return (
    <div className="chart-backdrop" onClick={onClose}>
      <div className="chart-panel" onClick={(e) => e.stopPropagation()}>
        <div className="chart-head">
          <div className="chart-title">
            <strong>{position.name}</strong>
            <span className="chart-sym">{position.symbol}</span>
            <span className="chart-live">
              <i />실시간
            </span>
          </div>
          <button type="button" className="chart-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <div className="chart-price">
          <span className="cp-now">{priceText}</span>
          <span className="cp-ret" style={{ color: stroke }}>
            {pct(position.ret)}
          </span>
        </div>

        <div className="chart-body">
          {geom ? (
            <svg
              className="chart-svg"
              viewBox={`0 0 ${geom.W} ${geom.H}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`${position.name} 가격 추이`}
            >
              <defs>
                <linearGradient id="cpFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
                  <stop offset="100%" stopColor={stroke} stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* min/max 가로 기준선 */}
              <line x1="0" x2={geom.W} y1={geom.PAD} y2={geom.PAD} className="cp-grid" />
              <line
                x1="0"
                x2={geom.W}
                y1={geom.H - geom.PAD}
                y2={geom.H - geom.PAD}
                className="cp-grid"
              />
              <path d={geom.area} fill="url(#cpFill)" />
              <path
                d={geom.line}
                fill="none"
                stroke={stroke}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
              {/* 라이브 마지막 점 (맥동) */}
              <circle
                className="cp-live-ring"
                cx={geom.last[0]}
                cy={geom.last[1]}
                r="5"
                fill="none"
                stroke={stroke}
              />
              <circle cx={geom.last[0]} cy={geom.last[1]} r="2.6" fill={stroke} />
            </svg>
          ) : (
            <div className="chart-empty">가격 데이터가 아직 없습니다 — 잠시 후 갱신됩니다.</div>
          )}
          {geom && (
            <div className="chart-axis">
              <span>{curSym}{Math.round(geom.max).toLocaleString('ko-KR')}</span>
              <span>{curSym}{Math.round(geom.min).toLocaleString('ko-KR')}</span>
            </div>
          )}
        </div>

        <div className="chart-foot">{source}</div>
      </div>
    </div>
  );
}
