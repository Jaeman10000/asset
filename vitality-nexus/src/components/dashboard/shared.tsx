import { useState } from 'react';
import { pct as fmtPct, sparkPoints } from '../../util/format';

/**
 * CoinIcon — 암호화폐 로고. 실제 코인 아이콘(jsDelivr의 cryptocurrency-icons)을
 * 시도하고, 없거나 오프라인이면 심볼 첫 글자 컬러 뱃지로 폴백한다(항상 뭔가는 뜸).
 * CDN 도메인은 tauri.conf.json CSP img-src에 등록돼 있어야 패키지 앱에서도 로드됨.
 */
function coinHue(symbol: string): number {
  let h = 0;
  for (let i = 0; i < symbol.length; i++) h = (h * 31 + symbol.charCodeAt(i)) % 360;
  return h;
}

export function CoinIcon({ symbol, size = 18 }: { symbol: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const sym = symbol.toLowerCase();
  if (failed) {
    return (
      <span
        className="coin-badge"
        style={{
          width: size,
          height: size,
          background: `hsl(${coinHue(symbol)}, 55%, 42%)`,
          fontSize: size * 0.42,
        }}
        aria-hidden
      >
        {symbol.slice(0, 3)}
      </span>
    );
  }
  return (
    <img
      className="coin-icon"
      src={`https://cdn.jsdelivr.net/npm/cryptocurrency-icons@0.18.1/svg/color/${sym}.svg`}
      width={size}
      height={size}
      alt={symbol}
      onError={() => setFailed(true)}
    />
  );
}

/**
 * StockBadge — 종목 로고 배지 (v0.3 디자인).
 * 공식 무료 로고 소스가 없으므로 1차는 종목별 고정 색 이니셜 배지(토스 스타일).
 * 색은 심볼 해시로 고정되어 같은 종목은 항상 같은 색 → 스캔 시 로고처럼 기능한다.
 */
export function StockBadge({ name, symbol, size = 20 }: { name: string; symbol: string; size?: number }) {
  const h = coinHue(symbol || name);
  // 첫 글자(한글 1자 또는 영문 1~2자). 'LG전자'→'LG', '삼성전자'→'삼', 'SCHD'→'SC'
  const m = name.trim().match(/^[A-Za-z]{1,2}/);
  const initial = m ? m[0].toUpperCase() : name.trim().slice(0, 1);
  return (
    <span
      className="stock-badge"
      style={{
        width: size,
        height: size,
        fontSize: initial.length > 1 ? size * 0.38 : size * 0.5,
        background: `linear-gradient(135deg, hsl(${h}, 52%, 52%), hsl(${h}, 60%, 30%))`,
      }}
      aria-hidden
    >
      {initial}
    </span>
  );
}

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
