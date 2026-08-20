import { useEffect, useMemo, useState } from 'react';
import type { ChartTarget, MarketStock, PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, pct } from '../../util/format';
import { HoverCard, fromMarket, fromPosition, type HoverInfo, type HoverTarget } from './HoverCard';
import { ChartPanel } from './ChartPanel';
import { SearchPalette } from './SearchPalette';
import { PortfolioDonut } from './PortfolioDonut';
import { SectorRadar } from './SectorRadar';
import { SignalCard } from './SignalCard';
import { NewsCard } from './NewsCard';
import { WatchlistCard } from './WatchlistCard';
import type { RingSector } from '../organic-core/HoloSectorRings';
import { Spark, CoinIcon, StockBadge } from './shared';

/**
 * Dashboard — 심장이 중앙 무대(홀로그램), 정보가 주위에 떠 있는 구성.
 *   상단: 자산군 총합 4개 (크게, 갱신 시 금색 플래시)
 *   좌:   한국/미국/암호화폐 상세 (주가 흐름 스파크라인 + 수급 호버)
 *   중앙: SYSTEM PULSE — 3D 심장 + 홀로그램 섹터 궤도(배경 씬) + 총액 융합
 *         하단: 섹터 리드아웃 (KR 12 + US 11 전체 수치)
 *   우:   오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관)
 */

type RankTabKey = 'up' | 'down' | 'value' | 'foreign';

// 암호화폐 행에 어느 거래소인지 표기 (같은 코인이 업비트·빗썸 양쪽에 있으면 2행)
const EXCHANGE_LABEL: Record<string, string> = {
  upbit: '업비트',
  bithumb: '빗썸',
  manual: '수동',
};

// 기관 탭은 제거(키움 REST엔 '기관 순매수 상위 종목' 랭킹 TR이 아예 없음 — 종목별 조회만).
// 외국인 탭은 ka10034(외인기간별매매상위)로 복원: 응답이 순매수 '수량'만 주므로 백엔드가
// 순매수금액(억) ≈ 수량×현재가로 환산해 investors.foreign에 실어 준다. 그걸 여기서 정렬·표시.
// 기관 흐름은 SECTOR FLOW(테마별 외국인/기관 분리)에서 본다.
const RANK_TABS: { key: RankTabKey; label: string }[] = [
  { key: 'up', label: '상승' },
  { key: 'down', label: '하락' },
  // '거래량(주식 수)'이 아니라 '거래대금(돈)' 기준 — 주식 수로 줄 세우면 저가주가 무조건
  // 유리해서 왜곡된다(실측: 삼성전자 6.9조가 흥아해운 1,034억보다 아래로 밀림).
  { key: 'value', label: '거래대금' },
  { key: 'foreign', label: '외국인' },
];

/** 거래대금(억) — 백엔드 실제값 우선, 없으면 현재가×거래량으로 근사 */
function tradeValue(m: MarketStock): number {
  return m.value ?? (m.price * m.volume) / 1e8;
}

function sortRanking(list: MarketStock[], tab: RankTabKey): MarketStock[] {
  // 상승/하락/거래량은 '오늘의 시장 순위' 그 자체여야 하므로 키움 공식 랭킹
  // (ka10027/ka10030)에서 온 종목만 쓴다. flowOnly=대장주·외국인후보는 '외국인' 탭 전용.
  const out = tab === 'foreign' ? [...list] : list.filter((m) => !m.flowOnly);
  switch (tab) {
    case 'up':
      return out.sort((a, b) => b.ret - a.ret);
    case 'down':
      return out.sort((a, b) => a.ret - b.ret);
    case 'value':
      return out.sort((a, b) => tradeValue(b) - tradeValue(a));
    case 'foreign':
      return out.sort((a, b) => b.investors.foreign - a.investors.foreign);
  }
}

function rankMetric(m: MarketStock, tab: RankTabKey): { text: string; color: string } {
  const eok = (v: number) =>
    (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR') + '억';
  switch (tab) {
    case 'up':
    case 'down':
      return { text: pct(m.ret), color: m.ret >= 0 ? 'var(--up)' : 'var(--down)' };
    case 'value': {
      const v = tradeValue(m);
      // 1조 이상은 '조'로 접어서 표기 (삼성전자 6.9조 같은 값이 자릿수로 뭉개지지 않게)
      const text = v >= 10_000 ? (v / 10_000).toFixed(1) + '조' : Math.round(v).toLocaleString('ko-KR') + '억';
      return { text, color: 'var(--life)' };
    }
    case 'foreign':
      return {
        text: eok(m.investors.foreign),
        color: m.investors.foreign >= 0 ? 'var(--up)' : 'var(--down)',
      };
  }
}

function useHover() {
  const [target, setTarget] = useState<HoverTarget | null>(null);
  const onEnter = (info: HoverInfo) => (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    // enter가 연속 발생해도 같은 종목이면 리렌더하지 않는다 (불필요한 setState 방지).
    setTarget((prev) =>
      prev && prev.info.symbol === info.symbol
        ? prev
        : { info, x: r.right, left: r.left, y: r.top },
    );
  };
  const onLeave = () => setTarget(null);
  return { target, onEnter, onLeave };
}

/**
 * useRipple — 마우스가 행에 "들어온 지점"에서 물결이 퍼지게 한다(돌 던진 잔잔한 물).
 * DOM에 ripple span을 직접 붙이고 Web Animations API로 1회 재생 후 제거한다.
 * (React 리렌더에 애니메이션이 리셋되던 문제를 피하려고 명령형으로 구동 — 진입할
 * 때마다 확실히 처음부터 퍼진다.) 행의 rowWobble(꿈틀)과 함께 작동.
 */
function useRipple() {
  const trigger = (e: React.MouseEvent) => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    const host = e.currentTarget as HTMLElement;
    // 진행 중인 물결이 있으면 교체하지 않는다 — enter가 연속 발생해도(리렌더/히트테스트)
    // 첫 물결이 끝까지 퍼지도록 보장 (교체되어 0%에 갇히는 것 방지).
    if (host.querySelector('.ripple')) return;
    const r = host.getBoundingClientRect();
    const span = document.createElement('span');
    span.className = 'ripple';
    span.style.left = `${e.clientX - r.left}px`;
    span.style.top = `${e.clientY - r.top}px`;
    host.appendChild(span);
    const anim = span.animate(
      [
        { transform: 'scale(0)', opacity: 0.9 },
        { transform: 'scale(15)', opacity: 0 },
      ],
      { duration: 700, easing: 'ease-out' },
    );
    anim.onfinish = () => span.remove();
  };
  return { trigger };
}

/** 리스트 행 — 캡처 레퍼런스처럼 이름 · 라인그래프 · 값 · 등락%. 클릭 시 실시간 차트 */
function MiniRow({
  p,
  onEnter,
  onLeave,
  onSelect,
}: {
  p: Position;
  onEnter: (e: React.MouseEvent) => void;
  onLeave: () => void;
  onSelect: (p: Position) => void;
}) {
  const up = p.ret >= 0;
  const { trigger } = useRipple();
  return (
    <div
      className="mini-holding"
      title="클릭하면 실시간 차트"
      onMouseEnter={(e) => {
        trigger(e);
        onEnter(e);
      }}
      onMouseLeave={onLeave}
      onClick={(e) => {
        trigger(e);
        onSelect(p);
      }}
    >
      {/* v0.3 2줄 행 — 1줄: 로고·이름(절대 안 잘림)·수익률 / 2줄: 현재가·수량·평가금·스파크.
          유저 지적: 한 줄에 욱여넣으면 '두산에너빌리티' 같은 이름이 …으로 잘렸다. */}
      <div className="mh-l1">
        {p.assetType === 'crypto' ? (
          <CoinIcon symbol={p.symbol} />
        ) : (
          <StockBadge name={p.name} symbol={p.symbol} />
        )}
        <span className="mh-name">{p.name}</span>
        {/* 암호화폐는 종목명=심볼이라 코드 대신 거래소를 표기. 주식은 종목코드. */}
        {p.assetType === 'crypto' ? (
          <small className={`ex-tag ${p.exchange}`}>{EXCHANGE_LABEL[p.exchange] ?? p.exchange}</small>
        ) : (
          p.symbol !== p.name && <small className="mh-code">{p.symbol}</small>
        )}
        <span className={`mh-ret ${up ? 'up' : 'down'}`}>{pct(p.ret)}</span>
      </div>
      <div className="mh-l2">
        <span className="mh-price">
          {p.currency === 'USD' ? '$' + p.price.toLocaleString('en-US') : '₩' + p.price.toLocaleString('ko-KR')}
        </span>
        <span className="mh-qty">
          {p.qty.toLocaleString('ko-KR')}
          {p.assetType === 'crypto' ? '개' : '주'} · {krwCompact(p.value)}
        </span>
        <Spark history={p.history} color="auto" width={52} height={14} />
      </div>
    </div>
  );
}

function ListCard({
  title,
  exch,
  positions,
  empty,
  hover,
  onSelect,
}: {
  title: string;
  exch: string;
  positions: Position[];
  empty: string;
  hover: ReturnType<typeof useHover>;
  onSelect: (p: Position) => void;
}) {
  // 좁은 세로 칸에 전 종목을 욱여넣으면 행이 얇아져 안 보인다 → 페이지당 소수만
  // 보여주고 하단 점으로 넘긴다. 종목 수가 바뀌어도 페이지가 범위를 안 벗어나게 클램프.
  const PAGE_SIZE = 5;
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(positions.length / PAGE_SIZE));
  const cur = Math.min(page, pageCount - 1);
  const shown = positions.slice(cur * PAGE_SIZE, cur * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="card list-card">
      <h3>
        <span className="dot" />
        {title}
        <span className="exch">{exch}</span>
        {positions.length > PAGE_SIZE && (
          <span className="list-count">
            {cur * PAGE_SIZE + 1}–{cur * PAGE_SIZE + shown.length} / {positions.length}
          </span>
        )}
      </h3>
      <div className="list">
        {positions.length === 0 ? (
          <div className="list-empty">{empty}</div>
        ) : (
          shown.map((p) => (
            <MiniRow
              key={p.id}
              p={p}
              onEnter={hover.onEnter(fromPosition(p))}
              onLeave={hover.onLeave}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
      {pageCount > 1 && (
        <div className="list-dots" role="tablist" aria-label={`${title} 페이지`}>
          <button
            type="button"
            className="list-arrow"
            aria-label="이전"
            disabled={cur === 0}
            onClick={() => setPage(cur - 1)}
          >
            ‹
          </button>
          {Array.from({ length: pageCount }, (_, i) => (
            <button
              type="button"
              key={i}
              className={`list-dot ${i === cur ? 'on' : ''}`}
              aria-label={`${i + 1}페이지`}
              aria-selected={i === cur}
              onClick={() => setPage(i)}
            />
          ))}
          <button
            type="button"
            className="list-arrow"
            aria-label="다음"
            disabled={cur >= pageCount - 1}
            onClick={() => setPage(cur + 1)}
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

/** 랭킹 행 — 진입 물결(ripple) + 꿈틀(wobble) + 수급 호버 */
function RankRow({
  m,
  rank,
  held,
  tab,
  onEnter,
  onLeave,
  onOpen,
}: {
  m: MarketStock;
  rank: number;
  held: boolean;
  tab: RankTabKey;
  onEnter: (e: React.MouseEvent) => void;
  onLeave: () => void;
  /** 클릭 → 캔들 차트 상세 (유저 요청: 랭킹 종목도 눌러서 차트 본다) */
  onOpen: () => void;
}) {
  const metric = rankMetric(m, tab);
  const { trigger } = useRipple();
  const topClass = rank <= 3 ? `rank-top rank-${rank}` : '';
  return (
    <div
      className={`rank-row ${topClass}`}
      onMouseEnter={(e) => {
        trigger(e);
        onEnter(e);
      }}
      onMouseLeave={onLeave}
      onClick={onOpen}
    >
      <span className="rank-no">{rank}</span>
      <StockBadge name={m.name} symbol={m.symbol} size={18} />
      <div className="rank-mid">
        <div className="n">
          {m.name}
          <small>{m.symbol}</small>
          {held && <span className="held-chip">보유</span>}
        </div>
        <div className="v">
          ₩{m.price.toLocaleString('ko-KR')} · {(m.volume / 1e6).toFixed(1)}M
        </div>
      </div>
      <div className="p" style={{ color: metric.color }}>
        {metric.text}
      </div>
    </div>
  );
}

export function Dashboard({
  snapshot,
  bpm,
  usSectors,
}: {
  snapshot: PortfolioSnapshot;
  bpm: number;
  usSectors: RingSector[];
}) {
  const hover = useHover();
  const [rankTab, setRankTab] = useState<RankTabKey>('up');
  const [rankMore, setRankMore] = useState(false); // 5개 기본, 더보기로 6~10위
  const [selId, setSelId] = useState<string | null>(null);
  const [selTarget, setSelTarget] = useState<ChartTarget | null>(null);
  const [palOpen, setPalOpen] = useState(false);
  const t = snapshot.totals;
  // 섹터 flow·수급이 모의면 '샘플' 워터마크 (구버전 백엔드엔 없으므로 기본 false).
  const marketMock = snapshot.marketMock ?? false;
  // 랭킹은 별도 플래그 — 키움 연동되면 랭킹만 실데이터라 '샘플' 딱지가 사라진다.
  const rankingMock = snapshot.rankingMock ?? marketMock;
  // 레이더용 KR 테마 (members 포함 — 호버 패널이 추가 API 없이 그린다)
  const krFlows = useMemo(
    () => (snapshot.sectorFlows ?? []).filter((s) => s.region === 'KR'),
    [snapshot],
  );

  const { kr, us, crypto, heldSymbols } = useMemo(() => {
    const ps = [...snapshot.positions];
    const byVal = (a: Position, b: Position) => b.value - a.value;
    return {
      kr: ps.filter((p) => p.assetType === 'stock' && p.region === 'KR').sort(byVal),
      us: ps.filter((p) => p.assetType === 'stock' && p.region === 'US').sort(byVal),
      crypto: ps.filter((p) => p.assetType === 'crypto').sort(byVal),
      heldSymbols: new Set(ps.map((p) => p.symbol)),
    };
  }, [snapshot]);

  // 구버전 백엔드(사이드카 exe 등)엔 marketRanking이 없을 수 있음 — 방어
  const ranking = useMemo(
    () => sortRanking(snapshot.marketRanking ?? [], rankTab).slice(0, 10),
    [snapshot, rankTab],
  );

  // 실시간 차트로 선택된 대상 — 보유(selId, 폴링마다 최신 포지션으로 갱신) 또는
  // 외부 종목(selTarget: 랭킹·검색·관심종목).
  const selected: ChartTarget | null = useMemo(() => {
    if (selTarget) return selTarget;
    const p = snapshot.positions.find((pos) => pos.id === selId);
    if (!p) return null;
    return {
      symbol: p.symbol,
      name: p.name,
      assetType: p.assetType,
      region: p.region ?? undefined,
      currency: p.currency,
      price: p.price,
      ret: p.ret,
      history: p.history,
    };
  }, [snapshot, selId, selTarget]);
  // 차트를 열 때 호버 카드(수급)는 닫아 겹치지 않게 한다
  const openChart = (p: Position) => {
    hover.onLeave();
    setSelTarget(null);
    setSelId(p.id);
  };
  // 랭킹·검색·관심종목 등 '보유 아님' 종목 열기
  const openTarget = (t: ChartTarget) => {
    hover.onLeave();
    setSelId(null);
    setSelTarget(t);
  };
  const closeChart = () => {
    setSelId(null);
    setSelTarget(null);
  };

  // 검색 팔레트: '/' 단축키(입력 중엔 무시) + 상단바 캡슐(vn:search-open 이벤트)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/') return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
      e.preventDefault();
      setPalOpen(true);
    };
    const onOpen = () => setPalOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('vn:search-open', onOpen);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('vn:search-open', onOpen);
    };
  }, []);

  return (
    <div className="stage-wrap">
      <div className="stage">
        {/* ── 좌측: 3단 세로 리스트 (라인그래프, 클릭 시 실시간 차트) ── */}
        <div className="col-left">
          <ListCard title="한국 주식 상세" exch="실시간" positions={kr} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
          <ListCard title="미국 주식 상세" exch="실시간" positions={us} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
          <ListCard title="암호화폐 상세" exch="업비트 · 빗썸" positions={crypto} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
          <NewsCard />
        </div>

        {/* ── 중앙: 자산구성 도넛(심장 중앙) + 섹터 흐름 레이더 (v0.3 확정 레이아웃) ── */}
        <div className="col-center">
          <PortfolioDonut totals={t} bpm={bpm} refreshTick={snapshot.fetchedAt} />
          <SectorRadar krFlows={krFlows} usSectors={usSectors} mock={marketMock} onOpen={openTarget} />
        </div>

        {/* ── 우측: 오늘의 시장 랭킹 + ★관심종목 ── */}
        <div className="col-right">
        <div className={`card ranking-card${rankingMock ? ' is-mock' : ''}`}>
          <h3>
            <span className="dot" />
            오늘의 시장 랭킹
            {rankingMock ? (
              <span className="mock-badge">⚠ 샘플 데이터</span>
            ) : (
              <span className="exch">키움 실시간</span>
            )}
          </h3>
          <div className="ranking-tabs">
            {RANK_TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                className={rankTab === key ? 'on' : ''}
                onClick={() => setRankTab(key)}
              >
                {label}
              </button>
            ))}
            {/* 껍데기 상한가(거래대금 몇 천만원짜리)를 걸러냈다는 걸 숨기지 않고 표기 */}
            {rankTab !== 'foreign' && <span className="rank-note">거래대금 50억↑</span>}
          </div>
          <div className="ranking-list">
            {ranking.slice(0, rankMore ? 10 : 5).map((m, i) => {
              const held = heldSymbols.has(m.symbol);
              return (
                <RankRow
                  key={m.symbol}
                  m={m}
                  rank={i + 1}
                  held={held}
                  tab={rankTab}
                  onEnter={hover.onEnter(fromMarket(m, held))}
                  onLeave={hover.onLeave}
                  onOpen={() =>
                    openTarget({
                      symbol: m.symbol,
                      name: m.name,
                      assetType: 'stock',
                      region: 'KR',
                      currency: 'KRW',
                      price: m.price,
                      ret: m.ret,
                    })
                  }
                />
              );
            })}
            {ranking.length === 0 && <div className="list-empty">랭킹 로딩…</div>}
            {ranking.length > 5 && (
              <button type="button" className="rank-more" onClick={() => setRankMore((v) => !v)}>
                {rankMore ? '접기 ▴' : '더보기 6–10위 ▾'}
              </button>
            )}
          </div>
        </div>

        {/* ── ★ 관심종목 — 검색으로 찾은 종목 고정 ── */}
        <WatchlistCard onOpen={openTarget} refreshTick={snapshot.fetchedAt} />
        <SignalCard onOpen={openTarget} refreshTick={snapshot.fetchedAt} />
        </div>
      </div>

      <HoverCard target={hover.target} />
      <ChartPanel target={selected} tick={snapshot.fetchedAt} onClose={closeChart} />
      <SearchPalette
        open={palOpen}
        heldSymbols={heldSymbols}
        onSelect={openTarget}
        onClose={() => setPalOpen(false)}
      />
    </div>
  );
}
