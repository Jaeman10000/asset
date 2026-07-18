/**
 * 미니 도넛 — 리스트 항목 왼쪽의 작은 원형 지표.
 * 링이 손익률 크기에 비례해 차오르고, 상승은 주황/하락은 파랑.
 * (프로토타입의 mini-donut 대응, Canvas 대신 가벼운 SVG)
 */
export function MiniDonut({ ret, size = 22 }: { ret: number; size?: number }) {
  const r = size / 2 - 2;
  const c = 2 * Math.PI * r;
  // 손익률 절댓값을 0~1로 (최대 30%에서 꽉 참)
  const frac = Math.min(Math.abs(ret) / 30, 1);
  const color = ret >= 0 ? 'var(--up)' : 'var(--down)';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="mini-donut">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2.5" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray={`${frac * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  );
}
