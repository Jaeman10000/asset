import { pct as fmtPct, sparkPoints } from '../../util/format';

/** 등락률 배지 — 상승 주황 / 하락 파랑 (한국 관례색) */
export function Pct({ value, className }: { value: number; className?: string }) {
  return (
    <span
      className={`stat-pct ${className ?? ''}`}
      style={{ color: value >= 0 ? 'var(--up)' : 'var(--down)' }}
    >
      {fmtPct(value)}
    </span>
  );
}

/** history 배열 → 스파크라인 SVG. 데이터가 없으면 아무것도 안 그림 */
export function Spark({
  history,
  color = 'var(--life)',
  width = 70,
  height = 20,
}: {
  history: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  const points = sparkPoints(history, width, height);
  if (!points) return null;
  const up = history[history.length - 1] >= history[0];
  return (
    <svg
      className="spark"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color === 'auto' ? (up ? 'var(--up)' : 'var(--down)') : color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.85"
      />
    </svg>
  );
}
