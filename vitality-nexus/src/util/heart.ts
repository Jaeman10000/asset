/**
 * 포트폴리오 상태 → 심장 BPM 매핑.
 *
 * 스펙: "BPM 68~103 (변동성 반영)". 손익률 절댓값이 클수록(=시장이 요동칠수록)
 * 심장이 빨리 뛴다. 평상시(손익 0 근처)엔 잔잔한 72.
 */
export function portfolioBpm(totalPnlPct: number): number {
  const base = 72;
  const swing = Math.min(Math.abs(totalPnlPct) * 3, 31); // 최대 +31 → 103
  return Math.round(base + swing);
}
