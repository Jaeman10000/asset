/**
 * 백엔드 HTTP 클라이언트.
 *
 * 개발: Vite 프록시(/api → 127.0.0.1:8787)를 통한다.
 * 프로덕션(Tauri): VITE_API_BASE 환경변수로 백엔드 주소를 직접 지정한다.
 */
import type { PortfolioSnapshot, SourceStatus } from './types';

/**
 * 백엔드 주소 결정:
 *  - Tauri 안(데스크톱 앱): 프로덕션 빌드엔 Vite 프록시가 없으므로 백엔드에 직접 연결
 *  - 브라우저 dev: Vite 프록시(/api → 8787) 사용
 *  - VITE_API_BASE 환경변수가 있으면 그걸 최우선
 */
const isTauri =
  typeof window !== 'undefined' &&
  '__TAURI_INTERNALS__' in (window as unknown as Record<string, unknown>);

const BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (isTauri ? 'http://127.0.0.1:8787' : '/api');

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { signal });
  if (!resp.ok) {
    throw new Error(`${path} → HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export function fetchSnapshot(signal?: AbortSignal): Promise<PortfolioSnapshot> {
  return getJSON<PortfolioSnapshot>('/portfolio/snapshot', signal);
}

export function fetchSourceStatus(signal?: AbortSignal): Promise<SourceStatus> {
  return getJSON<SourceStatus>('/config/sources', signal);
}

// ── 보유종목 편집 (holdings.json) ──

export interface HoldingInput {
  exchange: 'manual';
  assetType: 'stock' | 'crypto';
  region?: 'KR' | 'US';
  market?: 'upbit' | 'bithumb';
  yahoo?: string;
  symbol: string;
  name: string;
  qty: number;
  avg: number;
  sector?: string;
}

export function fetchHoldings(signal?: AbortSignal): Promise<{ positions: HoldingInput[] }> {
  return getJSON<{ positions: HoldingInput[] }>('/holdings', signal);
}

export async function saveHoldings(positions: HoldingInput[]): Promise<void> {
  const resp = await fetch(`${BASE}/holdings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ positions }),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => '');
    throw new Error(`보유종목 저장 실패: HTTP ${resp.status} ${detail}`);
  }
}
