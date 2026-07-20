import { useEffect, useMemo, useState } from 'react';
import type { MarketStock, PortfolioSnapshot, Position } from '../../api/types';
import { krwCompact, krw, pct } from '../../util/format';
import { HoverCard, fromMarket, fromPosition, type HoverInfo, type HoverTarget } from './HoverCard';
import { ChartPanel } from './ChartPanel';
import { sectorHue, type RingSector } from '../organic-core/HoloSectorRings';
import { Spark, CoinIcon } from './shared';

/**
 * Dashboard — 심장이 중앙 무대(홀로그램), 정보가 주위에 떠 있는 구성.
 *   상단: 자산군 총합 4개 (크게, 갱신 시 금색 플래시)
 *   좌:   한국/미국/암호화폐 상세 (주가 흐름 스파크라인 + 수급 호버)
 *   중앙: SYSTEM PULSE — 3D 심장 + 홀로그램 섹터 궤도(배경 씬) + 총액 융합
 *         하단: 섹터 리드아웃 (KR 12 + US 11 전체 수치)
 *   우:   오늘의 시장 랭킹 (상승/하락/거래량/외국인/기관)
 */

type RankTabKey = 'up' | 'down' | 'volume' | 'foreign' | 'inst';

const RANK_TABS: { key: RankTabKey; label: string }[] = [
  { key: 'up', label: '상승' },
  { key: 'down', label: '하락' },
  { key: 'volume', label: '거래량' },
  { key: 'foreign', label: '외국인' },
  { key: 'inst', label: '기관' },
];

function sortRanking(list: MarketStock[], tab: RankTabKey): MarketStock[] {
  const out = [...list];
  switch (tab) {
    case 'up':
      return out.sort((a, b) => b.ret - a.ret);
    case 'down':
      return out.sort((a, b) => a.ret - b.ret);
    case 'volume':
      return out.sort((a, b) => b.volume - a.volume);
    case 'foreign':
      return out.sort((a, b) => b.investors.foreign - a.investors.foreign);
    case 'inst':
      return out.sort((a, b) => b.investors.inst - a.investors.inst);
  }
}

function rankMetric(m: MarketStock, tab: RankTabKey): { text: string; color: string } {
  const eok = (v: number) =>
    (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR') + '억';
  switch (tab) {
    case 'up':
    case 'down':
      return { text: pct(m.ret), color: m.ret >= 0 ? 'var(--up)' : 'var(--down)' };
    case 'volume':
      return { text: (m.volume / 1e6).toFixed(1) + 'M', color: 'var(--life)' };
    case 'foreign':
      return {
        text: eok(m.investors.foreign),
        color: m.investors.foreign >= 0 ? 'var(--up)' : 'var(--down)',
      };
    case 'inst':
      return {
        text: eok(m.investors.inst),
        color: m.investors.inst >= 0 ? 'var(--up)' : 'var(--down)',
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
      <div className="n">
        {/* 암호화폐만 코인 로고를 이름 앞에 */}
        {p.assetType === 'crypto' && <CoinIcon symbol={p.symbol} />}
        {p.name}
        {/* 암호화폐는 종목명=심볼이라 중복(BTC BTC) → 다를 때만 코드 표기 */}
        {p.symbol !== p.name && <small>{p.symbol}</small>}
      </div>
      <Spark history={p.history} color="auto" width={56} height={18} />
      <div className="v">{krwCompact(p.value)}</div>
      <div className={`p ${up ? 'up' : 'down'}`}>{pct(p.ret)}</div>
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
}: {
  m: MarketStock;
  rank: number;
  held: boolean;
  tab: RankTabKey;
  onEnter: (e: React.MouseEvent) => void;
  onLeave: () => void;
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
    >
      <span className="rank-no">{rank}</span>
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

/**
 * 하단 SECTOR FLOW — 각 섹터가 "수급이 흐르는 레인".
 *
 * 리스트가 아니라 흐름이다: 트랙 중앙(=수급 균형)을 기준으로 순매수는 우(→),
 * 순매도는 좌(←)로 색 막대가 뻗고, 그 위를 빛 입자가 방향대로 흐른다.
 * 강할수록 빠르고 밝게 — 오늘 돈이 크게 움직인 섹터가 저절로 눈에 들어온다.
 *   · 값/정렬 일치: KR = 외국인+기관 순매수(억원, App 정렬 기준과 동일한 값을 표시),
 *     US = 전일 등락률. 정렬은 부호값 내림차순 → 위=최대 순매수, 아래=최대 순매도.
 *   · dot 색 = 3D 궤도 노드와 동일(지배 투자자/등락 방향) → 링↔레인 상호참조.
 *   · 컴포지터 전용: 막대는 transform:scaleX(전환), 흐름은 translate3d(무한) 뿐.
 */
function SectorFlowLanes({ kr, us, mock }: { kr: RingSector[]; us: RingSector[]; mock: boolean }) {
  const krNet = (s: RingSector) => (s.foreign ?? 0) + (s.inst ?? 0);

  const col = (sectors: RingSector[], side: 'kr' | 'us', title: string, metricLabel: string) => {
    const val = (s: RingSector) => (side === 'kr' ? krNet(s) : s.ret);
    const maxAbs = Math.max(
      ...sectors.map((s) => Math.abs(val(s))),
      side === 'kr' ? 300 : 0.5, // 바닥값 — 조용한 날 막대가 폭주하지 않게
    );
    return (
      <div className="flow-col">
        <div className="flow-head">
          {title}
          <em>{metricLabel}</em>
        </div>
        {sectors.map((s, i) => {
          const v = val(s);
          const buy = v >= 0;
          const mag = Math.max(Math.abs(v) / maxAbs, 0.05); // 0.05~1 (막대 스케일·강도)
          const dur = `${(2.6 - mag * 1.75).toFixed(2)}s`; // 강할수록 빠름: 0.85s~2.51s
          const bright = (0.28 + mag * 0.5).toFixed(2); // 강할수록 밝음: 0.28~0.78
          const dirColor =
            side === 'kr'
              ? buy
                ? 'var(--life)'
                : 'var(--down)'
              : buy
                ? 'var(--up)'
                : 'var(--down)';
          const sign = v >= 0 ? '+' : '−';
          const valText =
            side === 'kr'
              ? sign + Math.abs(Math.round(v)).toLocaleString('ko-KR')
              : sign + Math.abs(v).toFixed(1) + '%';
          return (
            <div className="flow-lane" key={s.name}>
              <span className="fl-rk">{i + 1}</span>
              <i className="fl-dot" style={{ background: `hsl(${sectorHue(s, side)}, 82%, 60%)` }} />
              <span className="fl-name">{s.name}</span>
              <div className={`fl-track ${buy ? 'buy' : 'sell'}`}>
                <div className="fl-fill" style={{ ['--mag' as string]: mag, color: dirColor }} />
                <div
                  className="fl-belt"
                  style={{ ['--dur' as string]: dur, ['--bright' as string]: bright }}
                >
                  <span className="fl-belt-i" />
                </div>
              </div>
              <span className="fl-val" style={{ color: dirColor }}>
                {valText}
                {side === 'kr' && <em>억</em>}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className={`card sector-flow${mock ? ' is-mock' : ''}`}>
      <h3>
        <span className="dot" />
        SECTOR FLOW · 수급 흐름 레인
        {mock ? (
          <span className="mock-badge">⚠ 샘플 데이터</span>
        ) : (
          <span className="exch">순매수순</span>
        )}
      </h3>
      <div className="flow-cols">
        {col(kr, 'kr', '한국 · KRX', '외국인+기관 순매수')}
        {col(us, 'us', '미국 · SPDR', '전일 등락률')}
      </div>
    </div>
  );
}

export function Dashboard({
  snapshot,
  bpm,
  krSectors,
  usSectors,
}: {
  snapshot: PortfolioSnapshot;
  bpm: number;
  krSectors: RingSector[];
  usSectors: RingSector[];
}) {
  const hover = useHover();
  const [rankTab, setRankTab] = useState<RankTabKey>('up');
  const [flashIdx, setFlashIdx] = useState<number | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const t = snapshot.totals;
  // 섹터 flow·수급이 모의면 '샘플' 워터마크 (구버전 백엔드엔 없으므로 기본 false).
  const marketMock = snapshot.marketMock ?? false;
  // 랭킹은 별도 플래그 — 키움 연동되면 랭킹만 실데이터라 '샘플' 딱지가 사라진다.
  const rankingMock = snapshot.rankingMock ?? marketMock;

  // 데이터 갱신 순간 = 총합 카드 하나가 금색 플래시 (스펙: 갱신 순간만 발광)
  useEffect(() => {
    const idx = Math.floor(snapshot.fetchedAt / 1000) % 4;
    setFlashIdx(idx);
    const id = setTimeout(() => setFlashIdx(null), 900);
    return () => clearTimeout(id);
  }, [snapshot.fetchedAt]);

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

  // 실시간 차트로 선택된 종목 — 현재 스냅샷에서 다시 찾아 폴링마다 갱신되게 함
  const selected = useMemo(
    () => snapshot.positions.find((p) => p.id === selId) ?? null,
    [snapshot, selId],
  );
  // 차트를 열 때 호버 카드(수급)는 닫아 겹치지 않게 한다
  const openChart = (p: Position) => {
    hover.onLeave();
    setSelId(p.id);
  };

  // 심장과 동일하게 3~5초 주기로 느리게(총액 후광 맥동). 심박 시각 부담 완화.
  const beatSec = Math.min(5, Math.max(3, 5 - (bpm - 40) / 40));

  const tiles = [
    { lbl: 'KR 주식', b: t.kr },
    { lbl: 'US 주식', b: t.us },
    { lbl: '주식 총합', b: t.stock },
    { lbl: '암호화폐', b: t.crypto },
  ];

  return (
    <div className="stage-wrap">
      {/* ── 상단: 자산군 총합 4개 (크게) ── */}
      <div className="totals-row">
        {tiles.map((tile, i) => (
          <div key={tile.lbl} className={`card total-card ${flashIdx === i ? 'event-flash' : ''}`}>
            <div className="lbl">{tile.lbl}</div>
            <div className="amt">{krwCompact(tile.b.value)}</div>
            <div className="pct" style={{ color: tile.b.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
              {pct(tile.b.pnlPct)}
            </div>
          </div>
        ))}
      </div>

      <div className="stage">
        {/* ── 좌측: 3단 세로 리스트 (라인그래프, 클릭 시 실시간 차트) ── */}
        <div className="col-left">
          <ListCard title="한국 주식 상세" exch="실시간" positions={kr} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
          <ListCard title="미국 주식 상세" exch="실시간" positions={us} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
          <ListCard title="암호화폐 상세" exch="업비트 · 빗썸" positions={crypto} empty="보유 종목 없음" hover={hover} onSelect={openChart} />
        </div>

        {/* ── 중앙: 홀로그램 무대 (심장+궤도는 배경 씬) + 총액 + 섹터 리드아웃 ── */}
        <div className="col-center">
          <div className="heart-overlay">
            <div className="heart-label">
              <span className="dot" />
              SYSTEM PULSE
              <span className="bpm-badge">{bpm} BPM</span>
            </div>

            <div className="heart-space" />

            <div className="heart-center-info" style={{ ['--beat' as string]: `${beatSec}s` }}>
              <div className="total-halo" aria-hidden />
              <div className="lbl">TOTAL PORTFOLIO</div>
              <div className="total">{t.total.value > 0 ? krw(t.total.value) : '—'}</div>
              <div className="pnl" style={{ color: t.total.pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
                {pct(t.total.pnlPct)}
              </div>
            </div>
          </div>

          <SectorFlowLanes kr={krSectors} us={usSectors} mock={marketMock} />
        </div>

        {/* ── 우측: 오늘의 시장 랭킹 ── */}
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
          </div>
          <div className="ranking-list">
            {ranking.map((m, i) => {
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
                />
              );
            })}
            {ranking.length === 0 && <div className="list-empty">랭킹 로딩…</div>}
          </div>
        </div>
      </div>

      <HoverCard target={hover.target} />
      <ChartPanel position={selected} tick={snapshot.fetchedAt} onClose={() => setSelId(null)} />
    </div>
  );
}
