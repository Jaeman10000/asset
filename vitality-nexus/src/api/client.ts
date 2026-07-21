/**
 * 백엔드 HTTP 클라이언트.
 *
 * 개발: Vite 프록시(/api → 127.0.0.1:8787)를 통한다.
 * 프로덕션(Tauri): VITE_API_BASE 환경변수로 백엔드 주소를 직접 지정한다.
 */
import type { InvestorFlow, InvestorPeriod, PortfolioSnapshot, SourceStatus } from './types';

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

async function getJSON<T>(path: string, signal?: AbortSignal, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
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

export function fetchSnapshot(signal?: AbortSignal, fresh = false): Promise<PortfolioSnapshot> {
  // fresh=true: 백엔드 7초 캐시 + 수급/일봉 캐시까지 비우고 즉시 재조회(수동 새로고침).
  // 콜드 로딩 땐 보유 수급(ka10059)을 블로킹으로 다 받고 랭킹/대장주까지 채우느라
  // 수십 초 걸릴 수 있어 스냅샷만 타임아웃을 넉넉히(60초) 준다. 캐시가 데워진 뒤엔 즉시.
  return getJSON<PortfolioSnapshot>(`/portfolio/snapshot${fresh ? '?fresh=1' : ''}`, signal, 60_000);
}

export function fetchSourceStatus(signal?: AbortSignal): Promise<SourceStatus> {
  return getJSON<SourceStatus>('/config/sources', signal);
}

// ── 캔들 차트 (일/주/월봉, 키움 실데이터) ──

export type ChartPeriod = 'D' | 'W' | 'M';

export interface Candle {
  dt: string; // YYYYMMDD
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export function fetchChart(
  code: string,
  period: ChartPeriod,
  market: 'kr' | 'us' = 'kr',
  signal?: AbortSignal,
): Promise<{ code: string; period: ChartPeriod; candles: Candle[] }> {
  return getJSON(
    `/chart/${encodeURIComponent(code)}?period=${period}&market=${market}`,
    signal,
  );
}

// ── 종목별 수급 (호버 시 on-demand 조회) ──

export interface FlowResp {
  investors: InvestorFlow | null;
  investorPeriods: InvestorPeriod[];
}

// 클라 캐시(60초) — 같은 종목에 반복 호버해도 재요청/깜빡임 없이 즉시. 백엔드도 180초
// 캐시하므로 이중 캐시. null 결과(수급 없음/실패)도 캐시해 무한 재시도를 막는다.
const _flowCache = new Map<string, { at: number; data: FlowResp }>();

export async function fetchFlow(code: string, signal?: AbortSignal): Promise<FlowResp> {
  const hit = _flowCache.get(code);
  if (hit && Date.now() - hit.at < 60_000) return hit.data;
  const data = await getJSON<FlowResp>(`/flow/${encodeURIComponent(code)}`, signal);
  _flowCache.set(code, { at: Date.now(), data });
  return data;
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

// ── 암호화폐 거래소 연동 (업비트/빗썸 잔고) ──

export interface CryptoStatus {
  upbit: boolean;
  bithumb: boolean;
}

export function fetchCryptoStatus(signal?: AbortSignal): Promise<CryptoStatus> {
  return getJSON<CryptoStatus>('/config/crypto', signal);
}

export async function saveCryptoConfig(cfg: {
  upbit_access?: string;
  upbit_secret?: string;
  bithumb_key?: string;
  bithumb_secret?: string;
}): Promise<{ saved: string[] }> {
  const resp = await fetch(`${BASE}/config/crypto`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => '');
    throw new Error(`거래소 연동 저장 실패: HTTP ${resp.status} ${detail}`);
  }
  return (await resp.json()) as { saved: string[] };
}
