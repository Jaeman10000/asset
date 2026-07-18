/**
 * 백엔드(backend/app/schemas.py)의 PortfolioSnapshot을 미러링한 TS 타입.
 * 필드명이 백엔드와 1:1로 일치해야 한다 — 바꿀 땐 양쪽을 같이 바꿀 것.
 */

export type Exchange = 'kiwoom' | 'kis' | 'upbit' | 'bithumb' | 'manual';
export type AssetType = 'stock' | 'crypto';
export type Region = 'KR' | 'US';
export type Currency = 'KRW' | 'USD';

/** 투자자별 순매수 (억원). 키움/KRX 연동 전엔 모의 데이터 */
export interface InvestorFlow {
  foreign: number; // 외국인
  inst: number; // 기관
  individual: number; // 개인
  program: number; // 프로그램
}

export interface Position {
  id: string;
  exchange: Exchange;
  assetType: AssetType;
  region?: Region | null;
  symbol: string;
  name: string;
  qty: number;
  avg: number;
  price: number;
  currency: Currency;
  value: number; // KRW 환산 평가금액
  cost: number; // KRW 환산 매수금액
  ret: number; // 수익률 %
  history: number[];
  sector?: string | null;
  investors?: InvestorFlow | null; // KR 주식 수급 (호버 표시)
  lastUpdated: number;
}

/** 오늘의 시장 랭킹 항목 (보유 여부와 무관) */
export interface MarketStock {
  symbol: string;
  name: string;
  price: number;
  ret: number;
  volume: number;
  investors: InvestorFlow;
}

export interface SectorFlow {
  region: Region;
  id: string;
  name: string;
  foreign?: number | null;
  inst?: number | null;
  individual?: number | null;
  ret?: number | null;
  volume?: number | null;
}

export interface TotalsBucket {
  value: number;
  cost: number;
  pnl: number;
  pnlPct: number;
}

export interface Totals {
  kr: TotalsBucket;
  us: TotalsBucket;
  stock: TotalsBucket;
  crypto: TotalsBucket;
  total: TotalsBucket;
}

export interface SourceError {
  source: string;
  message: string;
}

export interface PortfolioSnapshot {
  totals: Totals;
  positions: Position[];
  sectorFlows: SectorFlow[];
  /** 오늘의 시장 랭킹 (키움 연동 전엔 모의) */
  marketRanking: MarketStock[];
  fetchedAt: number;
  errors: SourceError[];
  isEstimate: boolean;
}

/** 각 소스가 설정됐는지 (GET /config/sources) */
export interface SourceStatus {
  kiwoom: boolean;
  kis: boolean;
  upbit: boolean;
  bithumb: boolean;
  manual: boolean;
}
