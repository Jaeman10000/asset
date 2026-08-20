import { useCallback, useEffect, useState } from 'react';
import { fetchSignalTop, type SignalResp, type SignalRow } from '../../api/client';
import type { ChartTarget } from '../../api/types';
import { StockBadge } from './shared';

/**
 * SignalCard — 수급 시그널 (v0.3 우측 하단).
 * 기본 = 시장 전체(수급 추적 풀 ≈90종목: 랭킹+테마 대장주+보유+관심 — 키움엔 전 종목
 * 기관 수급 랭킹 TR이 없어 전수 스캔은 불가, 그래서 풀 기준임을 표기).
 * [내 보유]로 전환 가능. 종목마다 외국인/기관 금액을 각각 표기(유저 확정: 묶지 말 것).
 */

const fmt = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(Math.round(v)).toLocaleString('ko-KR');

function Row({ r, max, onOpen }: { r: SignalRow; max: number; onOpen: (t: ChartTarget) => void }) {
  const cell = (v: number) => (
    <div className="cell">
      <b
        style={{
          width: `${Math.min(100, (Math.abs(v) / max) * 100)}%`,
          background: v >= 0 ? 'var(--up)' : 'var(--down)',
        }}
      />
      <span style={{ color: v >= 0 ? 'var(--up)' : 'var(--down)' }}>{fmt(v)}</span>
    </div>
  );
  return (
    <div
      className="srow"
      onClick={() =>
        onOpen({ symbol: r.code, name: r.name, assetType: 'stock', region: 'KR', currency: 'KRW' })
      }
    >
      <div className="nmw">
        <StockBadge name={r.name} symbol={r.code} size={17} />
        <span className="nm">{r.name}</span>
      </div>
      {cell(r.foreign)}
      {cell(r.inst)}
    </div>
  );
}

export function SignalCard({
  onOpen,
  refreshTick,
}: {
  onOpen: (t: ChartTarget) => void;
  refreshTick: number;
}) {
  const [scope, setScope] = useState<'market' | 'held'>('market');
  const [data, setData] = useState<SignalResp | null>(null);

  const load = useCallback(
    (s: 'market' | 'held') => {
      fetchSignalTop(s)
        .then(setData)
        .catch(() => {});
    },
    [],
  );

  useEffect(() => {
    load(scope);
    const id = setInterval(() => load(scope), 60_000);
    return () => clearInterval(id);
  }, [scope, load]);

  useEffect(() => {
    if (refreshTick) load(scope);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick]);

  const buys = data?.buys?.slice(0, 3) ?? [];
  const sells = data?.sells?.slice(0, 3) ?? [];
  const max = Math.max(
    1,
    ...[...buys, ...sells].flatMap((r) => [Math.abs(r.foreign), Math.abs(r.inst)]),
  );

  return (
    <div className="card sig">
      <h3>
        <span className="dot" />
        수급 시그널
        <span className="vc-tabs">
          <button type="button" className={scope === 'market' ? 'on' : ''} onClick={() => setScope('market')}>
            시장 전체
          </button>
          <button type="button" className={scope === 'held' ? 'on' : ''} onClick={() => setScope('held')}>
            내 보유
          </button>
        </span>
      </h3>
      <div className="head">
        <span />
        <em style={{ color: '#fbbf24' }}>외국인</em>
        <em style={{ color: '#34d399' }}>기관</em>
      </div>
      {!data && <div className="sig-empty">수급 수집 중… (워머가 채우면 나타납니다)</div>}
      {buys.length > 0 && <div className="grp buy">▲ 사는 중</div>}
      {buys.map((r) => (
        <Row key={r.code} r={r} max={max} onOpen={onOpen} />
      ))}
      {sells.length > 0 && <div className="grp sell">▼ 파는 중</div>}
      {sells.map((r) => (
        <Row key={r.code} r={r} max={max} onOpen={onOpen} />
      ))}
      <div className="note">
        {scope === 'market'
          ? '수급 추적 풀(랭킹+대장주+보유+관심 ≈90종목) 중 오늘 |외+기| 상위 · 억원 · 클릭=차트'
          : '내 보유 종목 중 오늘 순매수/순매도 상위 · 억원 · 클릭=차트'}
      </div>
    </div>
  );
}
