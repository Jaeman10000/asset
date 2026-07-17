/** 표시용 포맷 유틸 */

export function krw(value: number): string {
  return '₩' + Math.round(value).toLocaleString('ko-KR');
}

/** 큰 금액을 억/만 단위로 축약 (카드 공간 절약) */
export function krwCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e8) return '₩' + (value / 1e8).toFixed(2) + '억';
  if (abs >= 1e4) return '₩' + Math.round(value / 1e4).toLocaleString('ko-KR') + '만';
  return krw(value);
}

export function pct(value: number): string {
  return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
}

/** 숫자 배열(history)을 SVG polyline points 문자열로 변환 (0~width, 0~height) */
export function sparkPoints(history: number[], width = 70, height = 20): string {
  if (history.length < 2) return '';
  const min = Math.min(...history);
  const max = Math.max(...history);
  const range = max - min || 1;
  const step = width / (history.length - 1);
  return history
    .map((v, i) => {
      const x = i * step;
      // SVG는 위가 0이므로 값이 클수록 y가 작아야 함 (뒤집기)
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}
