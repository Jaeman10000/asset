import { useEffect, useState } from 'react';
import { fetchPerf, type PerfResp } from '../../api/client';
import type { Totals } from '../../api/types';
import { krw } from '../../util/format';
import { HeartOrb } from './HeartOrb';

/**
 * PortfolioDonut — 자산 구성 도넛 + 중앙 3D 심장 + 기간 손익 칩 (v0.3 중앙 상단 카드).
 * 기간 칩(일/주/월/6개월/1년/ALL)을 바꾸면 스냅샷 DB에서 계산한 기간 손익(₩·%)이 바뀐다.
 * (수익률 추이 차트는 유저가 엑셀로 관리 — 카드 삭제하고 칩만 이식하기로 확정)
 */

const PERIOD_CHIPS = [
  { key: 'D', label: '일' },
  { key: 'W', label: '주' },
  { key: 'M', label: '월' },
  { key: '6M', label: '6개월' },
  { key: '1Y', label: '1년' },
  { key: 'ALL', label: 'ALL' },
] as const;

const SEGMENTS: { key: 'us' | 'kr' | 'crypto'; label: string; color: string }[] = [
  { key: 'us', label: '미국 주식', color: '#a78bfa' },
  { key: 'kr', label: '한국 주식', color: '#5b8cff' },
  { key: 'crypto', label: '암호화폐', color: '#7dd3fc' },
];

export function PortfolioDonut({
  totals,
  bpm,
  refreshTick,
}: {
  totals: Totals;
  bpm: number;
  refreshTick: number;
}) {
  const [period, setPeriod] = useState<string>('D');
  const [perf, setPerf] = useState<PerfResp | null>(null);

  useEffect(() => {
    let alive = true;
    fetchPerf()
      .then((p) => alive && setPerf(p))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [refreshTick]);

  const total = totals.total.value || 1;
  // SVG 도넛 지오메트리 — r=86, 둘레 2πr. 세그먼트 사이 2px 갭.
  const R = 86;
  const CIRC = 2 * Math.PI * R;
  let acc = 0;
  const segs = SEGMENTS.map((s) => {
    const v = totals[s.key].value;
    const frac = Math.max(0, v / total);
    const seg = { ...s, v, frac, offset: acc };
    acc += frac;
    return seg;
  });

  const p = perf?.periods?.[period];
  const pUp = (p?.won ?? 0) >= 0;
  const chipLabel = PERIOD_CHIPS.find((c) => c.key === period)?.label ?? period;
  // DB가 기간을 다 못 덮으면 (예: 1년 선택인데 데이터 34일치) 정직하게 표기
  const spanDays: Record<string, number> = { D: 1, W: 7, M: 30, '6M': 182, '1Y': 365 };
  const short =
    p && period !== 'ALL' && p.coveredDays < (spanDays[period] ?? 0) * 0.9
      ? `· 실측 ${Math.round(p.coveredDays)}일치`
      : '';

  return (
    <div className="card donut-card">
      <h3>
        <span className="dot" />
        포트폴리오 구성
        <span className="vc-tabs">
          {PERIOD_CHIPS.map((c) => (
            <button
              type="button"
              key={c.key}
              className={period === c.key ? 'on' : ''}
              onClick={() => setPeriod(c.key)}
            >
              {c.label}
            </button>
          ))}
        </span>
      </h3>
      <div className="donut-flex">
        <div className="donut-hold">
          <svg width="210" height="210" viewBox="0 0 210 210">
            <circle cx="105" cy="105" r={R} fill="none" stroke="rgba(255,255,255,.05)" strokeWidth="16" />
            {segs.map(
              (s) =>
                s.frac > 0.001 && (
                  <circle
                    key={s.key}
                    cx="105"
                    cy="105"
                    r={R}
                    fill="none"
                    stroke={s.color}
                    strokeWidth="16"
                    strokeDasharray={`${Math.max(0, s.frac * CIRC - 2)} ${CIRC}`}
                    strokeDashoffset={-s.offset * CIRC}
                    transform="rotate(-90 105 105)"
                    style={{ transition: 'stroke-dasharray .8s ease, stroke-dashoffset .8s ease' }}
                  />
                ),
            )}
          </svg>
          {/* 도넛 구멍에서 실제 3D 심장이 뛴다 */}
          <HeartOrb bpm={bpm} size={150} />
          <div className="orb-bpm">● {bpm} BPM</div>
        </div>
        <div className="legend">
          {segs.map((s) => (
            <div className="li" key={s.key}>
              <i style={{ background: s.color }} />
              {s.label}
              <b>{krw(s.v)}</b>
              <small>{(s.frac * 100).toFixed(1)}%</small>
            </div>
          ))}
          <div className="psum">
            <div className="ps-line">
              <span className="k">TOTAL</span>
              <span className="won">{krw(totals.total.value)}</span>
            </div>
            <div className="ps-line">
              <span className="k">{chipLabel === 'ALL' ? '전체' : chipLabel + '간'} 손익</span>
              {p ? (
                <span className="pl" style={{ color: pUp ? 'var(--up)' : 'var(--down)' }}>
                  {(pUp ? '+' : '−') + Math.abs(p.won).toLocaleString('ko-KR')}원 ({pUp ? '+' : '−'}
                  {Math.abs(p.pct).toFixed(2)}%)
                </span>
              ) : (
                <span className="pl" style={{ color: 'var(--sub)' }}>
                  계산 중…
                </span>
              )}
            </div>
            <div className="ps-src">스냅샷 DB 기준 {short}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
