import type { InvestorFlow, MarketStock, Position } from '../../api/types';
import { krwCompact, pct } from '../../util/format';

/**
 * Truth Layer 호버 카드 — 프로토타입 showStockHover 복원.
 * 핵심은 수급현황(외국인/기관/개인/프로그램 순매수 바). 리스트 행에 이미 보이는
 * 손익%는 중복해서 크게 보여주지 않고, 필수 수치만 압축해서 담는다.
 */

export interface HoverInfo {
  name: string;
  symbol: string;
  sector?: string | null;
  held: boolean;
  price: number;
  currency: 'KRW' | 'USD';
  ret: number;
  qty?: number;
  avg?: number;
  value?: number; // KRW 평가금액
  volume?: number | null;
  investors?: InvestorFlow | null;
  lastUpdated?: number;
}

export function fromPosition(p: Position): HoverInfo {
  return {
    name: p.name,
    symbol: p.symbol,
    sector: p.sector,
    held: true,
    price: p.price,
    currency: p.currency,
    ret: p.ret,
    qty: p.qty,
    avg: p.avg,
    value: p.value,
    investors: p.investors,
    lastUpdated: p.lastUpdated,
  };
}

export function fromMarket(m: MarketStock, held: boolean): HoverInfo {
  return {
    name: m.name,
    symbol: m.symbol,
    held,
    price: m.price,
    currency: 'KRW',
    ret: m.ret,
    volume: m.volume,
    investors: m.investors,
  };
}

export interface HoverTarget {
  info: HoverInfo;
  /** 행의 오른쪽 끝 (카드를 오른쪽에 놓을 기준) */
  x: number;
  /** 행의 왼쪽 끝 (오른쪽에 못 놓을 때 카드를 이 왼쪽에 놓음) */
  left: number;
  y: number;
}

// 프로토타입의 투자자 색 (스펙: 파티클 색 정보 인코딩과 동일 계열)
const INVESTOR_ROWS: { key: keyof InvestorFlow; label: string; color: string }[] = [
  { key: 'foreign', label: '외국인', color: 'hsl(45, 90%, 65%)' },
  { key: 'inst', label: '기관', color: 'hsl(175, 80%, 60%)' },
  { key: 'individual', label: '개인', color: 'hsl(220, 60%, 65%)' },
  { key: 'program', label: '프로그램', color: 'hsl(280, 60%, 70%)' },
];

function fmtEok(v: number): string {
  return (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR') + '억';
}

function InvestorBars({ inv }: { inv: InvestorFlow }) {
  const maxAbs = Math.max(...INVESTOR_ROWS.map((r) => Math.abs(inv[r.key])), 1);
  return (
    <div className="inv-section">
      <div className="inv-title">수급 · 당일 순매수</div>
      {INVESTOR_ROWS.map((r) => {
        const v = inv[r.key];
        const w = (Math.abs(v) / maxAbs) * 100;
        return (
          <div className="inv-row" key={r.key}>
            <span className="inv-name">
              <i style={{ background: r.color }} />
              {r.label}
            </span>
            <div className="inv-bar">
              {/* color도 지정 — CSS 글로우가 box-shadow: currentColor 로 참조 */}
              <div
                className="inv-fill"
                style={{ width: `${w}%`, background: r.color, color: r.color }}
              />
            </div>
            <span className="inv-val" style={{ color: v >= 0 ? 'var(--up)' : 'var(--down)' }}>
              {fmtEok(v)}
            </span>
          </div>
        );
      })}
      <div className="inv-note">외국인·기관은 당일 장중 잠정치 · 모의 데이터</div>
    </div>
  );
}

export function HoverCard({ target }: { target: HoverTarget | null }) {
  if (!target) return null;
  const h = target.info;
  const curSym = h.currency === 'USD' ? '$' : '₩';
  const time = new Date(h.lastUpdated || Date.now()).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  // 카드를 행 오른쪽에 놓되(기본), 화면을 넘으면(랭킹처럼 우측 컬럼) 행 왼쪽에 놓아
  // 종목을 가리지 않게 한다. 왼쪽으로도 화면 밖이면 최소 8px로 클램프.
  const W = 272;
  const GAP = 14;
  const placeRight = target.x + GAP + W <= window.innerWidth;
  const left = Math.max(8, placeRight ? target.x + GAP : target.left - GAP - W);
  const top = Math.min(target.y, window.innerHeight - 280);

  return (
    <div className="truth-card" style={{ left, top }}>
      <div className="truth-head">
        <strong>{h.name}</strong>
        <span className="truth-sym">{h.symbol}</span>
        <span className={`truth-badge ${h.held ? 'held' : ''}`}>{h.held ? '보유' : '미보유'}</span>
      </div>
      {h.sector && <div className="truth-sector">{h.sector}</div>}

      {/* 필수 수치만 한 줄씩 (손익%는 행에 이미 보이므로 중복 강조 안 함) */}
      <div className="truth-line">
        <span>현재가</span>
        <b>
          {curSym}
          {h.price.toLocaleString('ko-KR')}
          <em style={{ color: h.ret >= 0 ? 'var(--up)' : 'var(--down)' }}> {pct(h.ret)}</em>
        </b>
      </div>
      {h.held && h.value !== undefined && (
        <div className="truth-line">
          <span>평가금액</span>
          <b>{krwCompact(h.value)}</b>
        </div>
      )}
      {h.held && h.qty !== undefined && h.avg !== undefined && (
        <div className="truth-line sub">
          <span>보유</span>
          <b>
            {h.qty.toLocaleString('ko-KR')} × {curSym}
            {h.avg.toLocaleString('ko-KR')}
          </b>
        </div>
      )}
      {!h.held && h.volume != null && (
        <div className="truth-line sub">
          <span>거래량</span>
          <b>{(h.volume / 1e6).toFixed(1)}M</b>
        </div>
      )}

      {/* 수급현황 — 이 카드의 주인공 */}
      {h.investors && <InvestorBars inv={h.investors} />}

      <div className="truth-foot">기준 {time}</div>
    </div>
  );
}
