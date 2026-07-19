import { useEffect, useMemo, useRef, useState } from 'react';
import type { Position } from '../../api/types';
import { fetchChart, type Candle, type ChartPeriod } from '../../api/client';
import { pct } from '../../util/format';

/**
 * ChartPanel — 종목 클릭 시 뜨는 큰 차트.
 *
 * KR 주식(키움): 캔들스틱(OHLC 막대) + 일/주/월봉 전환(ka10081/82/83). 한국 관행대로
 *   상승=빨강, 하락=파랑. 오늘(마지막) 봉은 현재가로 라이브 갱신돼 숨쉰다.
 * 암호화폐·미국주식(캔들 미제공): position.history 종가 라인으로 폴백.
 * 외부 차트 라이브러리 없이 순수 SVG(오프라인 Tauri·CSP 안전, 심장 씬과 렌더 분리).
 */

const PERIODS: { key: ChartPeriod; label: string }[] = [
  { key: 'D', label: '일' },
  { key: 'W', label: '주' },
  { key: 'M', label: '월' },
];

const UP = '#ef5350'; // 상승(빨강)
const DOWN = '#3b82f6'; // 하락(파랑)

export function ChartPanel({
  position,
  tick,
  onClose,
}: {
  position: Position | null;
  tick: number; // snapshot.fetchedAt — 폴링마다 바뀜
  onClose: () => void;
}) {
  const [period, setPeriod] = useState<ChartPeriod>('D');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState<number[]>([]);
  const symRef = useRef<string | null>(null);
  const tickRef = useRef(0);

  // 캔들 지원 = 주식(KR=키움, US=Yahoo). 암호화폐만 라인 폴백.
  const supportsCandles =
    position?.assetType === 'stock' && (position?.region === 'KR' || position?.region === 'US');
  const market: 'kr' | 'us' = position?.region === 'US' ? 'us' : 'kr';

  // 선택 종목이 바뀌면 상태 리셋 + 기간 일봉으로
  useEffect(() => {
    if (position && position.symbol !== symRef.current) {
      symRef.current = position.symbol;
      tickRef.current = 0;
      setLive([]);
      setCandles([]);
      setPeriod('D');
    }
  }, [position]);

  // 캔들 로드 (종목·기간 변경 시). 지원 안 하면 스킵(라인 폴백).
  useEffect(() => {
    if (!position || !supportsCandles) {
      setCandles([]);
      return;
    }
    let alive = true;
    const ctrl = new AbortController();
    setLoading(true);
    fetchChart(position.symbol, period, market, ctrl.signal)
      .then((r) => {
        if (alive) setCandles(r.candles ?? []);
      })
      .catch(() => {
        if (alive) setCandles([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, [position, period, supportsCandles, market]);

  // 폴링마다 현재가를 라인 폴백 버퍼에 append (최근 120틱)
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

  // 오늘(마지막) 봉을 현재가로 라이브 갱신 → 숨쉬는 캔들
  const liveCandles = useMemo(() => {
    if (!candles.length || !position) return candles;
    const arr = candles.slice();
    const last = { ...arr[arr.length - 1] };
    const p = position.price;
    last.c = p;
    last.h = Math.max(last.h, p);
    last.l = Math.min(last.l, p);
    arr[arr.length - 1] = last;
    return arr;
  }, [candles, position]);

  // 라인 폴백 시리즈 (암호화폐/미국)
  const series = useMemo(
    () => (position ? [...(position.history ?? []), ...live] : []),
    [position, live],
  );

  // 캔들 지오메트리
  const candleGeom = useMemo(() => {
    const W = 680;
    const H = 240;
    const PADX = 10;
    const PADT = 10;
    const PADB = 10;
    if (liveCandles.length < 2) return null;
    const lo = Math.min(...liveCandles.map((c) => c.l));
    const hi = Math.max(...liveCandles.map((c) => c.h));
    const range = hi - lo || 1;
    const slot = (W - PADX * 2) / liveCandles.length;
    const bodyW = Math.max(1, Math.min(11, slot * 0.62));
    const y = (v: number) => PADT + (H - PADT - PADB) * (1 - (v - lo) / range);
    const bars = liveCandles.map((c, i) => {
      const cx = PADX + slot * (i + 0.5);
      const up = c.c >= c.o;
      const yo = y(c.o);
      const yc = y(c.c);
      const top = Math.min(yo, yc);
      const h = Math.max(1, Math.abs(yc - yo));
      return { cx, up, top, h, yh: y(c.h), yl: y(c.l), bodyW };
    });
    return { W, H, lo, hi, bars, lastClose: liveCandles[liveCandles.length - 1].c, y };
  }, [liveCandles]);

  // 라인 지오메트리 (폴백)
  const lineGeom = useMemo(() => {
    const W = 680;
    const H = 240;
    const PAD = 8;
    if (series.length < 2) return null;
    const min = Math.min(...series);
    const max = Math.max(...series);
    const range = max - min || 1;
    const stepX = (W - PAD * 2) / (series.length - 1);
    const y = (v: number) => PAD + (H - PAD * 2) * (1 - (v - min) / range);
    const pts = series.map((v, i) => [PAD + i * stepX, y(v)] as const);
    const line = pts.map(([x, py], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${py.toFixed(1)}`).join(' ');
    const area = `${line} L${pts[pts.length - 1][0].toFixed(1)} ${H - PAD} L${pts[0][0].toFixed(1)} ${H - PAD} Z`;
    return { W, H, PAD, min, max, line, area, last: pts[pts.length - 1] };
  }, [series]);

  if (!position) return null;

  const up = position.ret >= 0;
  const stroke = up ? 'var(--up)' : 'var(--down)';
  const curSym = position.currency === 'USD' ? '$' : '₩';
  const priceText = curSym + position.price.toLocaleString('ko-KR');

  const periodName = period === 'D' ? '일봉' : period === 'W' ? '주봉' : '월봉';
  const source = supportsCandles
    ? `${market === 'us' ? 'Yahoo' : '키움'} ${periodName} · 현재가 7초 갱신`
    : position.assetType === 'crypto'
      ? '업비트·빗썸 60분봉 · 현재가 7초 갱신'
      : 'Yahoo Finance 일봉 · 현재가 7초 갱신';

  const axisMax = candleGeom ? candleGeom.hi : lineGeom?.max;
  const axisMin = candleGeom ? candleGeom.lo : lineGeom?.min;

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
          <div className="chart-head-right">
            {supportsCandles && (
              <div className="chart-periods" role="tablist" aria-label="봉 주기">
                {PERIODS.map((p) => (
                  <button
                    type="button"
                    key={p.key}
                    className={`chart-period ${period === p.key ? 'on' : ''}`}
                    aria-selected={period === p.key}
                    onClick={() => setPeriod(p.key)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <button type="button" className="chart-close" onClick={onClose} aria-label="닫기">
              ✕
            </button>
          </div>
        </div>

        <div className="chart-price">
          <span className="cp-now">{priceText}</span>
          <span className="cp-ret" style={{ color: stroke }}>
            {pct(position.ret)}
          </span>
        </div>

        <div className="chart-body">
          {candleGeom ? (
            <svg
              className="chart-svg"
              viewBox={`0 0 ${candleGeom.W} ${candleGeom.H}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`${position.name} ${periodName}`}
            >
              <line x1="0" x2={candleGeom.W} y1="10" y2="10" className="cp-grid" />
              <line
                x1="0"
                x2={candleGeom.W}
                y1={candleGeom.H - 10}
                y2={candleGeom.H - 10}
                className="cp-grid"
              />
              {/* 마지막 종가 기준선 */}
              <line
                x1="0"
                x2={candleGeom.W}
                y1={candleGeom.y(candleGeom.lastClose)}
                y2={candleGeom.y(candleGeom.lastClose)}
                className="cp-lastline"
              />
              {candleGeom.bars.map((b, i) => {
                const color = b.up ? UP : DOWN;
                return (
                  <g key={i}>
                    <line
                      x1={b.cx}
                      x2={b.cx}
                      y1={b.yh}
                      y2={b.yl}
                      stroke={color}
                      strokeWidth="1"
                      vectorEffect="non-scaling-stroke"
                    />
                    <rect
                      x={b.cx - b.bodyW / 2}
                      y={b.top}
                      width={b.bodyW}
                      height={b.h}
                      fill={color}
                    />
                  </g>
                );
              })}
            </svg>
          ) : lineGeom ? (
            <svg
              className="chart-svg"
              viewBox={`0 0 ${lineGeom.W} ${lineGeom.H}`}
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
              <line x1="0" x2={lineGeom.W} y1={lineGeom.PAD} y2={lineGeom.PAD} className="cp-grid" />
              <line
                x1="0"
                x2={lineGeom.W}
                y1={lineGeom.H - lineGeom.PAD}
                y2={lineGeom.H - lineGeom.PAD}
                className="cp-grid"
              />
              <path d={lineGeom.area} fill="url(#cpFill)" />
              <path
                d={lineGeom.line}
                fill="none"
                stroke={stroke}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
              <circle
                className="cp-live-ring"
                cx={lineGeom.last[0]}
                cy={lineGeom.last[1]}
                r="5"
                fill="none"
                stroke={stroke}
              />
              <circle cx={lineGeom.last[0]} cy={lineGeom.last[1]} r="2.6" fill={stroke} />
            </svg>
          ) : (
            <div className="chart-empty">
              {loading ? '차트 불러오는 중…' : '가격 데이터가 아직 없습니다 — 잠시 후 갱신됩니다.'}
            </div>
          )}
          {(candleGeom || lineGeom) && axisMax != null && axisMin != null && (
            <div className="chart-axis">
              <span>
                {curSym}
                {Math.round(axisMax).toLocaleString('ko-KR')}
              </span>
              <span>
                {curSym}
                {Math.round(axisMin).toLocaleString('ko-KR')}
              </span>
            </div>
          )}
        </div>

        <div className="chart-foot">{source}</div>
      </div>
    </div>
  );
}
