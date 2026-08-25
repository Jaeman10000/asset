/**
 * 백엔드 HTTP 클라이언트.
 *
 * 개발: Vite 프록시(/api → 127.0.0.1:8787)를 통한다.
 * 프로덕션(Tauri): VITE_API_BASE 환경변수로 백엔드 주소를 직접 지정한다.
 */
import type {
  InvestorFlow,
  InvestorPeriod,
  MasterStock,
  PortfolioSnapshot,
  SourceStatus,
  StockInfo,
} from './types';

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

// ── 종목 검색: 전 종목 마스터 (하루 1회 localStorage 캐시) ──

const MASTER_KEY = 'vn_master_v1';

export async function fetchStockMaster(signal?: AbortSignal): Promise<MasterStock[]> {
  const today = new Date().toISOString().slice(0, 10);
  try {
    const raw = localStorage.getItem(MASTER_KEY);
    if (raw) {
      const cached = JSON.parse(raw) as { date: string; items: MasterStock[] };
      if (cached.date === today && cached.items?.length) return cached.items;
    }
  } catch {
    /* 캐시 손상 → 새로 받기 */
  }
  const r = await getJSON<{ count: number; items: MasterStock[] }>('/stocks/master', signal, 30_000);
  const items = r.items ?? [];
  if (items.length) {
    try {
      localStorage.setItem(MASTER_KEY, JSON.stringify({ date: today, items }));
    } catch {
      /* localStorage 꽉참 등 — 캐시 없이 동작 */
    }
  }
  return items;
}

// ── 종목 기본정보 (ka10001) — 상세 헤더·52주·시총 ──

const _infoCache = new Map<string, { at: number; info: StockInfo | null }>();

export async function fetchStockInfo(code: string, signal?: AbortSignal): Promise<StockInfo | null> {
  const hit = _infoCache.get(code);
  if (hit && Date.now() - hit.at < 30_000) return hit.info;
  const r = await getJSON<{ info: StockInfo | null }>(`/stocks/info/${encodeURIComponent(code)}`, signal);
  _infoCache.set(code, { at: Date.now(), info: r.info });
  return r.info;
}

// ── ★ 관심종목 ──

export interface WatchItem {
  code: string;
  name: string;
}
export interface WatchQuote extends WatchItem {
  price?: number;
  ret?: number;
  spark?: number[];
}

export function fetchWatchlist(signal?: AbortSignal): Promise<{ items: WatchItem[] }> {
  return getJSON<{ items: WatchItem[] }>('/watchlist', signal);
}

export async function saveWatchlist(items: WatchItem[]): Promise<WatchItem[]> {
  const resp = await fetch(`${BASE}/watchlist`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
  if (!resp.ok) throw new Error(`관심종목 저장 실패: HTTP ${resp.status}`);
  return ((await resp.json()) as { items: WatchItem[] }).items;
}

export function fetchWatchlistQuotes(signal?: AbortSignal): Promise<{ items: WatchQuote[] }> {
  // 관심종목 수만큼 키움 조회가 돌 수 있어 넉넉히
  return getJSON<{ items: WatchQuote[] }>('/watchlist/quotes', signal, 30_000);
}

// ── 크립토 시장 지표 (도미넌스·공포탐욕·글로벌 시세) ──

export interface CryptoContext {
  global: { btcDominance: number; ethDominance: number } | null;
  fearGreed: { value: number; label: string } | null;
  coins: Record<string, { usd: number; krw: number }>;
}

let _cryptoCtx: { at: number; data: CryptoContext } | null = null;
// 지금까지 요청한 심볼 누적 — 코인게코 미지원 심볼(coins에 안 실림)을 계속 재요청하는
// 루프를 막고, 새 심볼 호버 시엔 누적분 전체로 한 번에 다시 받는다.
const _ctxSyms = new Set<string>();

export async function fetchCryptoContext(symbols: string[], signal?: AbortSignal): Promise<CryptoContext> {
  const want = symbols.map((s) => s.toUpperCase());
  const fresh = _cryptoCtx && Date.now() - _cryptoCtx.at < 180_000; // 3분 클라 캐시
  if (fresh && want.every((s) => s in _cryptoCtx!.data.coins || _ctxSyms.has(s))) {
    return _cryptoCtx!.data;
  }
  want.forEach((s) => _ctxSyms.add(s));
  const data = await getJSON<CryptoContext>(
    `/crypto/context?symbols=${encodeURIComponent([..._ctxSyms].join(','))}`,
    signal,
    15_000,
  );
  _cryptoCtx = { at: Date.now(), data };
  return data;
}

// ── 기간 손익 (도넛 카드 기간 칩) ──

export interface PerfPeriod {
  won: number;
  pct: number;
  baseTs: number;
  coveredDays: number;
}
export interface PerfResp {
  periods: Record<string, PerfPeriod>;
  total?: number;
  ts?: number;
}

let _perf: { at: number; data: PerfResp } | null = null;

export async function fetchPerf(signal?: AbortSignal): Promise<PerfResp> {
  if (_perf && Date.now() - _perf.at < 60_000) return _perf.data;
  const data = await getJSON<PerfResp>('/portfolio/perf', signal, 15_000);
  _perf = { at: Date.now(), data };
  return data;
}

// ── 마켓 뉴스 (언론사 RSS) ──

export interface NewsItem {
  source: string;
  title: string;
  link: string;
  ts: number;
}

let _news: { at: number; items: NewsItem[] } | null = null;

export async function fetchNews(signal?: AbortSignal): Promise<NewsItem[]> {
  if (_news && Date.now() - _news.at < 600_000) return _news.items;
  const r = await getJSON<{ items: NewsItem[] }>('/news', signal, 15_000);
  _news = { at: Date.now(), items: r.items ?? [] };
  return _news.items;
}

// ── 수급 시그널 (시장 전체/내 보유) ──

export interface SignalRow {
  code: string;
  name: string;
  foreign: number;
  inst: number;
  net: number;
}
export interface SignalResp {
  buys: SignalRow[];
  sells: SignalRow[];
}

export function fetchSignalTop(scope: 'market' | 'held', signal?: AbortSignal): Promise<SignalResp> {
  return getJSON<SignalResp>(`/signal/top?scope=${scope}`, signal, 15_000);
}

// ── 자금 흐름 (로컬 아카이브 + 예상 경로) ──

export interface FlowArchive {
  days: number;
  first: string | null;
  last: string | null;
  bytes: number;
  dir: string;
}
export interface FlowStatus {
  running: boolean;
  phase: string;
  done: number;
  total: number;
  lastError: string | null;
  archive: FlowArchive;
}
export interface SectorDay {
  foreign: number;
  inst: number;
  value: number;
  strength: number;
  leader: string | null;      // 표시용 종목명
  leaderCode?: string | null; // 클릭 시 상세 조회용 종목코드
}
export interface FlowHistory {
  dates: string[];
  byDate: Record<string, Record<string, SectorDay>>;
  archive: FlowArchive;
}
export interface ForecastLeader {
  code: string;
  name: string;
  net5d: number;
  ret: number;
}
export interface ForecastCandidate {
  theme: string;
  score: number;
  trans: number;
  transN: number;
  accel: number;
  room: number;
  slots: number;
  leaders: ForecastLeader[];
}
export interface Forecast {
  ready: boolean;
  reason?: string;
  asOf?: string;
  curLeader?: string | null;
  sampleN?: number;
  days: number;
  candidates?: ForecastCandidate[];
  backtest?: {
    n: number; top1: number; top3: number;
    top1pct: number; top3pct: number; base1: number; base3: number; themes: number;
  };
}

export function fetchFlowStatus(signal?: AbortSignal): Promise<FlowStatus> {
  return getJSON<FlowStatus>('/moneyflow/status', signal);
}

export function fetchFlowHistory(days = 120, signal?: AbortSignal): Promise<FlowHistory> {
  return getJSON<FlowHistory>(`/moneyflow/history?days=${days}`, signal, 20_000);
}

export interface MomentumTheme {
  theme: string;
  net: number;
  foreign: number;
  inst: number;
  value: number;
  strength: number | null;
  streak: number;   // 최근 연속 순매수일
  posDays: number;  // 창 안에서 순매수였던 날 수
  nDays: number;
  slots: number;
  leaders: { code: string; name: string; net: number; ret: number }[];
}
export interface Momentum {
  ready: boolean;
  reason?: string;
  days: number;
  from?: string;
  to?: string;
  archiveDays?: number;
  themes?: MomentumTheme[];
}

export function fetchMomentum(days = 20, signal?: AbortSignal): Promise<Momentum> {
  return getJSON<Momentum>(`/moneyflow/momentum?days=${days}`, signal, 20_000);
}

export function fetchForecast(signal?: AbortSignal): Promise<Forecast> {
  return getJSON<Forecast>('/moneyflow/forecast', signal, 30_000);
}

export interface CollectResult extends FlowStatus {
  saved?: number;
  scanned?: number;
  seconds?: number;
  skipped?: string;
  error?: string;
}

export async function collectFlow(pages: number): Promise<CollectResult> {
  const resp = await fetch(`${BASE}/moneyflow/collect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pages }),
  });
  if (!resp.ok) throw new Error(`수집 실패: HTTP ${resp.status}`);
  return (await resp.json()) as CollectResult;
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
