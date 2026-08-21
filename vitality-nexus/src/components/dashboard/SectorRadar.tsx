import { useMemo, useState } from 'react';
import type { ChartTarget, SectorFlow } from '../../api/types';
import type { RingSector } from '../organic-core/HoloSectorRings';
import { StockBadge } from './shared';

/**
 * SectorRadar — 섹터 흐름 레이더 (v0.3 중앙 하단, ChatGPT 시안을 외/기 데이터로 재해석).
 *
 * · 레이더 = 고정 6축 (⚙로 교체, localStorage 유지) — 축이 고정돼야 어제와 모양 비교가 됨.
 * · 폴리곤 2개: 외국인(금) / 기관(에메랄드). 점선 링=0, 바깥=매수·안쪽=매도.
 * · 축/리스트 호버 → 그 테마 대장주별 수급 패널 (members: 스냅샷에 이미 실림 — API 0회).
 * · 옆 리스트 = 전체 테마 규모순(금은동) — 그날 특이 테마는 축에 없어도 안 놓침.
 */

const AXES_KEY = 'vn_radar_axes_v1';
const DEFAULT_AXES = ['반도체', '이차전지', '자동차', '바이오/제약', '방산', '금융'];
const GOLD = '#fbbf24';
const EMER = '#34d399';

function loadAxes(): string[] {
  try {
    const a = JSON.parse(localStorage.getItem(AXES_KEY) || '[]') as string[];
    if (Array.isArray(a) && a.length >= 3) return a.slice(0, 6);
  } catch {
    /* 기본값 */
  }
  return DEFAULT_AXES;
}

const fmt = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR');

export function SectorRadar({
  krFlows,
  usSectors,
  mock,
  onOpen,
}: {
  krFlows: SectorFlow[]; // KR 테마 (members 포함)
  usSectors: RingSector[];
  mock: boolean;
  onOpen: (t: ChartTarget) => void;
}) {
  const [axes, setAxes] = useState<string[]>(loadAxes);
  const [gearOpen, setGearOpen] = useState(false);
  const [hoverName, setHoverName] = useState<string | null>(null);

  const byName = useMemo(() => new Map(krFlows.map((s) => [s.name, s])), [krFlows]);
  const ranked = useMemo(
    () =>
      [...krFlows].sort(
        (a, b) => Math.abs((b.foreign ?? 0) + (b.inst ?? 0)) - Math.abs((a.foreign ?? 0) + (a.inst ?? 0)),
      ),
    [krFlows],
  );

  // ── 레이더 지오메트리 ──
  const N = axes.length;
  const CX = 130;
  const CY = 122;
  const R0 = 42; // 0 링
  const RMAX = 96;
  const RMIN = 8;
  const maxV = Math.max(
    300,
    ...axes.flatMap((n) => {
      const s = byName.get(n);
      return s ? [Math.abs(s.foreign ?? 0), Math.abs(s.inst ?? 0)] : [0];
    }),
  );
  const rOf = (v: number) =>
    v >= 0 ? R0 + (v / maxV) * (RMAX - R0) : R0 - (Math.abs(v) / maxV) * (R0 - RMIN);
  const pt = (i: number, r: number): [number, number] => {
    const ang = -Math.PI / 2 + (i * 2 * Math.PI) / N;
    return [CX + r * Math.cos(ang), CY + r * Math.sin(ang)];
  };
  const ring = (r: number) =>
    Array.from({ length: N }, (_, i) => pt(i, r).map((x) => x.toFixed(1)).join(',')).join(' ');
  const poly = (key: 'foreign' | 'inst') =>
    Array.from({ length: N }, (_, i) => {
      const s = byName.get(axes[i]);
      return pt(i, rOf(s?.[key] ?? 0)).map((x) => x.toFixed(1)).join(',');
    }).join(' ');
  const vertices = (key: 'foreign' | 'inst') =>
    Array.from({ length: N }, (_, i) => {
      const s = byName.get(axes[i]);
      return { xy: pt(i, rOf(s?.[key] ?? 0)), name: axes[i] };
    });

  const hover = hoverName ? byName.get(hoverName) : null;

  const toggleAxis = (name: string) => {
    setAxes((cur) => {
      let next = cur.includes(name) ? cur.filter((a) => a !== name) : [...cur, name];
      next = next.slice(0, 6);
      if (next.length >= 3) localStorage.setItem(AXES_KEY, JSON.stringify(next));
      return next.length >= 3 ? next : cur; // 최소 3축
    });
  };

  return (
    <div className={`card radar-card${mock ? ' is-mock' : ''}`}>
      <h3>
        <span className="dot" />
        섹터 흐름 레이더
        {mock ? (
          <span className="mock-badge">⚠ 샘플 데이터</span>
        ) : (
          <span className="r-legend">
            <span>
              <i style={{ background: GOLD }} />외국인
            </span>
            <span>
              <i style={{ background: EMER }} />기관
            </span>
            <span className="hint">점선 링=0 · 바깥=매수 · 안쪽=매도</span>
          </span>
        )}
        <button type="button" className="radar-gear" onClick={() => setGearOpen((v) => !v)} title="레이더 축 편집 (최대 6개)">
          ⚙
        </button>
      </h3>

      {gearOpen && (
        <div className="gear-pop">
          <div className="gp-t">레이더 축 선택 (3~6개 · 고정축이라 매일 모양 비교 가능)</div>
          <div className="gp-list">
            {krFlows.map((s) => (
              <button
                type="button"
                key={s.name}
                className={axes.includes(s.name) ? 'on' : ''}
                onClick={() => toggleAxis(s.name)}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="radar-wrap">
        <div className="radar-left">
          <svg width="312" height="293" viewBox="0 0 260 244">
            {/* 그리드 링 */}
            <polygon points={ring(RMAX)} fill="none" stroke="rgba(255,255,255,.06)" />
            <polygon points={ring((RMAX + R0) / 2)} fill="none" stroke="rgba(255,255,255,.05)" />
            <polygon points={ring(R0)} fill="none" stroke="rgba(236,238,244,.3)" strokeDasharray="3 4" />
            {/* 축선 + 라벨 */}
            {axes.map((n, i) => {
              const [x, y] = pt(i, RMAX);
              const [lx, ly] = pt(i, RMAX + 15);
              const active = hoverName === n;
              return (
                <g key={n}>
                  <line
                    x1={CX}
                    y1={CY}
                    x2={x}
                    y2={y}
                    stroke={active ? 'rgba(167,139,250,.55)' : 'rgba(255,255,255,.05)'}
                    strokeWidth={active ? 2 : 1}
                  />
                  <text
                    x={lx}
                    y={ly + 3}
                    textAnchor="middle"
                    fontSize="9.5"
                    fontWeight="700"
                    fill={active ? '#c4b5fd' : 'rgba(236,238,244,.75)'}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoverName(n)}
                  >
                    {n}
                  </text>
                </g>
              );
            })}
            {/* 기관 → 외국인 순서로 (외국인이 위에) */}
            <polygon
              points={poly('inst')}
              fill="rgba(52,211,153,.13)"
              stroke={EMER}
              strokeWidth="1.6"
              strokeLinejoin="round"
              style={{ transition: 'all .6s ease' }}
            />
            <polygon
              points={poly('foreign')}
              fill="rgba(251,191,36,.12)"
              stroke={GOLD}
              strokeWidth="1.6"
              strokeLinejoin="round"
              style={{ transition: 'all .6s ease' }}
            />
            {vertices('inst').map((v) => (
              <circle key={'i' + v.name} cx={v.xy[0]} cy={v.xy[1]} r={hoverName === v.name ? 4 : 2.5} fill={EMER} />
            ))}
            {vertices('foreign').map((v) => (
              <circle key={'f' + v.name} cx={v.xy[0]} cy={v.xy[1]} r={hoverName === v.name ? 4 : 2.5} fill={GOLD} />
            ))}
          </svg>

          {/* 호버 패널 — 해당 테마 대장주별 수급 (스냅샷 members: 추가 API 0회) */}
          {hover && hover.members && hover.members.length > 0 && (
            <div className="hoverpane" onMouseLeave={() => setHoverName(null)}>
              <div className="hp-t">
                {hover.name} — 구성 대장주 수급
                <small>순매수 큰 순 · 클릭=차트 · 억원</small>
              </div>
              {hover.members.map((m) => (
                <div
                  key={m.code}
                  className="hp-row"
                  onClick={() =>
                    onOpen({
                      symbol: m.code,
                      name: m.name,
                      assetType: 'stock',
                      region: 'KR',
                      currency: 'KRW',
                    })
                  }
                >
                  <StockBadge name={m.name} symbol={m.code} size={17} />
                  <span className="nm">{m.name}</span>
                  <span className="fv" style={{ color: m.foreign >= 0 ? 'var(--up)' : 'var(--down)' }}>
                    외 {fmt(m.foreign)}
                  </span>
                  <span className="ov" style={{ color: m.inst >= 0 ? 'var(--up)' : 'var(--down)' }}>
                    기 {fmt(m.inst)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 우: 전체 테마 규모순 리스트 (동적) */}
        <div className="rlist">
          <div className="row hd-row">
            <span />
            <span />
            <span className="hd" style={{ color: GOLD }}>
              외국인
            </span>
            <span className="hd" style={{ color: EMER }}>
              기관
            </span>
          </div>
          {/* 목록이 길어도 카드 밖으로 넘치지 않게 내부 스크롤 (US 필은 아래 고정) */}
          <div className="rl-scroll">
            {ranked.map((s, i) => (
              <div
                key={s.name}
                className={`row${i < 3 ? ` m${i + 1}` : ''}${hoverName === s.name ? ' hover' : ''}`}
                onMouseEnter={() => setHoverName(s.name)}
              >
                <span className="rk">{i + 1}</span>
                <span className="nm">{s.name}</span>
                <span className="fv" style={{ color: (s.foreign ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>
                  {fmt(s.foreign ?? 0)}
                </span>
                <span className="ov" style={{ color: (s.inst ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>
                  {fmt(s.inst ?? 0)}
                </span>
              </div>
            ))}
          </div>

          {/* US 섹터 필 (등락률) */}
          <div className="us-pills">
            <span className="us-lbl">US</span>
            {usSectors.slice(0, 5).map((s) => (
              <span key={s.name} className={s.ret >= 0 ? 'pu' : 'pd'}>
                {s.name} {(s.ret >= 0 ? '+' : '−') + Math.abs(s.ret).toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
