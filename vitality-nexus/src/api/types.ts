/**
 * 백엔드(backend/app/schemas.py)의 PortfolioSnapshot을 미러링한 TS 타입.
 * 필드명이 백엔드와 1:1로 일치해야 한다 — 바꿀 땐 양쪽을 같이 바꿀 것.
 */

export type Exchange = 'kiwoom' | 'kis' | 'upbit' | 'bithumb' | 'manual';
export type AssetType = 'stock' | 'crypto';
export type Region = 'KR' | 'US';
export type Currency = 'KRW' | 'USD';

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
  lastUpdated: number;
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
