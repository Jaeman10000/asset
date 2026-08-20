import { useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchChart,
  fetchFlow,
  fetchStockInfo,
  fetchWatchlist,
  saveWatchlist,
  type Candle,
  type ChartPeriod,
  type FlowResp,
} from '../../api/client';
import type { ChartTarget, StockInfo } from '../../api/types';
import { pct } from '../../util/format';

/**
 * ChartPanel — 종목 클릭/검색 시 뜨는 상세 패널.
 *
 * v0.2: Position뿐 아니라 어떤 종목이든(랭킹·검색·관심종목) ChartTarget으로 받는다.
 * KR 주식이면 캔들 옆에 상세 사이드(수급 + 52주/시총/PER/외인소진율)와
 * ★관심 등록 버튼이 붙는다. 시세가 없는 대상(검색 결과)은 ka10001로 채운다.
 *
 * KR 캔들: 키움 ka10081~83(일/주/월). US: Yahoo. 암호화폐: history 라인 폴백.
 * 순수 SVG (오프라인 Tauri·CSP 안전).
 */

const PERIODS: { key: ChartPeriod; label: string }[] = [
  { key: 'D', label: '일' },
  { key: 'W', label: '주' },
  { key: 'M', label: '월' },
];

const UP = '#ff5d73'; // 상승(코랄레드 — lifeColors.UP_COLOR와 동일)
const DOWN = '#5b8cff'; // 하락(블루 — lifeColors.DOWN_COLOR와 동일)

const fmtEok = (v: number) =>
  v >= 10_000 ? (v / 10_000).toFixed(1) + '조' : Math.round(v).toLocaleString('ko-KR') + '억';
const fmtNum = (v: number) =>
  (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR');

export function ChartPanel({
  target,
  tick,
  onClose,
}: {
  target: ChartTarget | null;
  tick: number; // snapshot.fetchedAt — 폴링마다 바뀜
  onClose: () => void;
}) {
  const [period, setPeriod] = useState<ChartPeriod>('D');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(false);
  const [live, setLive] = useState<number[]>([]);
  const [info, setInfo] = useState<StockInfo | null>(null);
  const [flow, setFlow] = useState<FlowResp | null>(null);
  const [starred, setStarred] = useState(false);
  const symRef = useRef<string | null>(null);
  const tickRef = useRef(0);

  // 캔들 지원 = 주식(KR=키움, US=Yahoo). 암호화폐만 라인 폴백.
  const supportsCandles =
    target?.assetType === 'stock' && (target?.region === 'KR' || target?.region === 'US');
  const market: 'kr' | 'us' = target?.region === 'US' ? 'us' : 'kr';
  const isKRStock = target?.assetType === 'stock' && target?.region === 'KR';

  // 선택 종목이 바뀌면 상태 리셋
  useEffect(() => {
    if (target && target.symbol !== symRef.current) {
      symRef.current = target.symbol;
      tickRef.current = 0;
      setLive([]);
      setCandles([]);
      setInfo(null);
      setFlow(null);
      setPeriod('D');
    }
  }, [target]);

  // 캔들 로드 (종목·기간 변경 시)
  useEffect(() => {
    if (!target || !supportsCandles) {
      setCandles([]);
      return;
    }
    let alive = true;
    const ctrl = new AbortController();
    setLoading(true);
    fetchChart(target.symbol, period, market, ctrl.signal)
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
  }, [target, period, supportsCandles, market]);

  // KR 주식이면 기본정보(52주·시총·PER·외인소진율) + 수급 + 관심 여부 로드
  useEffect(() => {
    if (!target || !isKRStock) return;
    let alive = true;
    fetchStockInfo(target.symbol)
      .then((i) => alive && setInfo(i))
      .catch(() => {});
    fetchFlow(target.symbol)
      .then((f) => alive && setFlow(f))
      .catch(() => {});
    fetchWatchlist()
      .then((w) => alive && setStarred(w.items.some((it) => it.code === target.symbol)))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [target, isKRStock]);

  const toggleStar = async () => {
    if (!target) return;
    try {
      const cur = (await fetchWatchlist()).items;
      const next = starred
        ? cur.filter((it) => it.code !== target.symbol)
        : [...cur, { code: target.symbol, name: target.name }];
      await saveWatchlist(next);
      setStarred(!starred);
      // 관심종목 카드에 즉시 반영
      window.dispatchEvent(new CustomEvent('vn:watchlist-changed'));
    } catch {
      /* 저장 실패 — 상태 유지 */
    }
  };

  // 폴링마다 현재가를 라인 폴백 버퍼에 append (최근 120틱)
  useEffect(() => {
    if (!target || !tick || tick === tickRef.current) return;
    tickRef.current = tick;
    if (target.price != null) setLive((prev) => [...prev, target.price!].slice(-120));
  }, [tick, target]);

  // Esc로 닫기
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // 표시 시세: 대상이 들고 온 값(보유/랭킹=폴링 갱신) 우선, 없으면 ka10001(검색)
  const price = target?.price ?? info?.price;
  const ret = target?.ret ?? info?.ret;

  // 오늘(마지막) 봉을 현재가로 라이브 갱신
  const liveCandles = useMemo(() => {
    if (!candles.length || price == null) return candles;
    const arr = candles.slice();
    const last = { ...arr[arr.length - 1] };
    last.c = price;
    last.h = Math.max(last.h, price);
    last.l = Math.min(last.l, price);
    arr[arr.length - 1] = last;
    return arr;
  }, [candles, price]);

  // 라인 폴백 시리즈 (암호화폐)
  const series = useMemo(
    () => (target ? [...(target.history ?? []), ...live] : []),
    [target, live],
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

  if (!target) return null;

  const up = (ret ?? 0) >= 0;
  const stroke = up ? 'var(--up)' : 'var(--down)';
  const curSym = target.currency === 'USD' ? '$' : '₩';
  const priceText = price != null ? curSym + price.toLocaleString('ko-KR') : '—';

  const periodName = period === 'D' ? '일봉' : period === 'W' ? '주봉' : '월봉';
  const source = supportsCandles
    ? `${market === 'us' ? 'Yahoo' : '키움'} ${periodName} · 실데이터`
    : target.assetType === 'crypto'
      ? '업비트·빗썸 시세 라인'
      : 'Yahoo Finance 일봉';

  const axisMax = candleGeom ? candleGeom.hi : lineGeom?.max;
  const axisMin = candleGeom ? candleGeom.lo : lineGeom?.min;

  // 수급 막대 스케일 — 당일+20/60일 최대치 공통
  const invRows = flow?.investors
    ? ([
        ['외국인', '#fbbf24', flow.investors.foreign] as const,
        ['기관', '#34d399', flow.investors.inst] as const,
        ['개인', '#7dd3fc', flow.investors.individual] as const,
      ] as const)
    : null;
  const invMax = invRows
    ? Math.max(
        ...invRows.map(([, , v]) => Math.abs(v)),
        ...(flow?.investorPeriods ?? []).flatMap((p) => [
          Math.abs(p.foreign),
          Math.abs(p.inst),
          Math.abs(p.individual),
        ]),
        1,
      )
    : 1;
  const indivPending =
    !!flow?.investors &&
    flow.investors.individual === 0 &&
    (flow.investors.foreign !== 0 || flow.investors.inst !== 0);

  return (
    <div className="chart-backdrop" onClick={onClose}>
      <div className={`chart-panel${isKRStock ? ' detail' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="chart-head">
          <div className="chart-title">
            <strong>{target.name}</strong>
            <span className="chart-sym">{target.symbol}</span>
            {(target.market || target.industry) && (
              <span className="chart-tag">
                {[target.market, target.industry].filter(Boolean).join(' · ')}
              </span>
            )}
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
            {isKRStock && (
              <button
                type="button"
                className={`chart-star${starred ? ' on' : ''}`}
                onClick={toggleStar}
                title={starred ? '관심종목에서 제거' : '관심종목에 추가'}
              >
                {starred ? '★ 관심 중' : '☆ 관심 등록'}
              </button>
            )}
            <button type="button" className="chart-close" onClick={onClose} aria-label="닫기">
              ✕
            </button>
          </div>
        </div>

        <div className="chart-price">
          <span className="cp-now">{priceText}</span>
          {ret != null && (
            <span className="cp-ret" style={{ color: stroke }}>
              {pct(ret)}
            </span>
          )}
          {info && (
            <span className="cp-sub">
              거래대금 {fmtEok(info.value)} · 거래량 {(info.volume / 1e6).toFixed(1)}M
            </span>
          )}
        </div>

        <div className={isKRStock ? 'chart-detail-grid' : undefined}>
          <div className="chart-body">
            {candleGeom ? (
              <svg
                className="chart-svg"
                viewBox={`0 0 ${candleGeom.W} ${candleGeom.H}`}
                preserveAspectRatio="none"
                role="img"
                aria-label={`${target.name} ${periodName}`}
              >
                <line x1="0" x2={candleGeom.W} y1="10" y2="10" className="cp-grid" />
                <line
                  x1="0"
                  x2={candleGeom.W}
                  y1={candleGeom.H - 10}
                  y2={candleGeom.H - 10}
                  className="cp-grid"
                />
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
                aria-label={`${target.name} 가격 추이`}
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

          {isKRStock && (
            <div className="chart-side">
              <div className="cs-title">
                수급 · 순매수 <small>억원 · 키움 실데이터</small>
              </div>
              {invRows ? (
                <div className="cs-inv">
                  <span />
                  <em>당일</em>
                  <em>20일</em>
                  <em>60일</em>
                  {invRows.map(([label, color, v], ri) => {
                    const p20 = flow?.investorPeriods?.[0];
                    const p60 = flow?.investorPeriods?.[1];
                    const keys = ['foreign', 'inst', 'individual'] as const;
                    const k = keys[ri];
                    return (
                      <div key={label} className="cs-inv-row">
                        <span className="who">
                          <i style={{ background: color }} />
                          {label}
                          <span className="bar">
                            <b
                              style={{
                                width: `${(Math.abs(v) / invMax) * 100}%`,
                                background: color,
                              }}
                            />
                          </span>
                        </span>
                        {indivPending && k === 'individual' ? (
                          <span className="v pending">집계 전</span>
                        ) : (
                          <span className="v" style={{ color: v >= 0 ? 'var(--up)' : 'var(--down)' }}>
                            {fmtNum(v)}
                          </span>
                        )}
                        <span
                          className="v"
                          style={{ color: (p20?.[k] ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}
                        >
                          {p20 ? fmtNum(p20[k]) : '—'}
                        </span>
                        <span
                          className="v"
                          style={{ color: (p60?.[k] ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}
                        >
                          {p60 ? fmtNum(p60[k]) : '—'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="cs-empty">수급 불러오는 중…</div>
              )}

              <div className="cs-meta">
                <span className="k">52주 최고</span>
                <span className="v">{info ? '₩' + info.w52h.toLocaleString('ko-KR') : '—'}</span>
                <span className="k">52주 최저</span>
                <span className="v">{info ? '₩' + info.w52l.toLocaleString('ko-KR') : '—'}</span>
                <span className="k">시가총액</span>
                <span className="v">{info ? fmtEok(info.marketCap) : '—'}</span>
                <span className="k">외국인 소진율</span>
                <span className="v">{info ? info.foreignRate.toFixed(1) + '%' : '—'}</span>
                <span className="k">PER / PBR</span>
                <span className="v">
                  {info ? `${info.per.toFixed(1)} / ${info.pbr.toFixed(2)}` : '—'}
                </span>
                <span className="k">ROE</span>
                <span className="v">{info ? info.roe.toFixed(1) + '%' : '—'}</span>
              </div>
            </div>
          )}
        </div>

        <div className="chart-foot">{source}</div>
      </div>
    </div>
  );
}
