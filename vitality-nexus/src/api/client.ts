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

// 요청 타임아웃 — 절전 복귀/회선 블랙홀(RST 없이 끊김)로 소켓이 OS TCP 타임아웃
// (수 분)까지 살아있으면 폴링이 그 요청에 갇혀 stale 데이터를 "실시간"인 척 보인다.
// 10초 안에 응답 없으면 abort → 스토어가 '오프라인'으로 전환하고 다음 폴링이 재시도.
const REQUEST_TIMEOUT_MS = 10_000;

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  // 외부 signal(수동 새로고침/stop)도 이 요청을 중단시키도록 연결
  const onAbort = () => ctrl.abort();
  if (signal) {
    if (signal.aborted) ctrl.abort();
    else signal.addEventListener('abort', onAbort, { once: true });
  }
  try {
    const resp = await fetch(`${BASE}${path}`, { signal: ctrl.signal });
    if (!resp.ok) {
      throw new Error(`${path} → HTTP ${resp.status}`);
    }
    return (await resp.json()) as T;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
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

// ── 키움 증권 연동 (앱키/시크릿) ──

export interface KiwoomStatus {
  configured: boolean;
  isMock: boolean;
  hasAccount: boolean;
}

export function fetchKiwoomStatus(signal?: AbortSignal): Promise<KiwoomStatus> {
  return getJSON<KiwoomStatus>('/config/kiwoom', signal);
}

export async function saveKiwoomConfig(cfg: {
  app_key: string;
  app_secret: string;
  is_mock: boolean;
  account_no?: string;
}): Promise<void> {
  const resp = await fetch(`${BASE}/config/kiwoom`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => '');
    throw new Error(`키움 연동 저장 실패: HTTP ${resp.status} ${detail}`);
  }
}
