import { useEffect, useState } from 'react';
import type { Position } from '../../api/types';
import { krw, pct } from '../../util/format';

/**
 * Truth Layer 호버 카드 (스펙: "정확한 값 = Truth Layer: 호버 시 정확한 숫자 + 기준시각").
 * 리스트 항목에 마우스를 올리면 정확한 보유 수량/평단/현재가/평가금액/손익을
 * 소수점까지 보여준다. 커서 옆에 떠서 따라온다.
 */

export interface HoverTarget {
  pos: Position;
  x: number;
  y: number;
}

export function HoverCard({ target }: { target: HoverTarget | null }) {
  const [now, setNow] = useState('');
  useEffect(() => {
    if (!target) return;
    const d = new Date(target.pos.lastUpdated || Date.now());
    setNow(
      d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    );
  }, [target]);

  if (!target) return null;
  const p = target.pos;
  const isUp = p.ret >= 0;
  const curSym = p.currency === 'USD' ? '$' : '₩';

  // 화면 밖으로 안 나가게 좌/우 배치 결정
  const left = target.x + 300 > window.innerWidth ? target.x - 288 : target.x + 16;
  const top = Math.min(target.y, window.innerHeight - 220);

  return (
    <div className="truth-card" style={{ left, top }}>
      <div className="truth-head">
        <strong>{p.name}</strong>
        <span className="truth-sym">{p.symbol}</span>
        <span className="truth-badge">보유</span>
      </div>
      {p.sector && <div className="truth-sector">{p.sector}</div>}

      <div className="truth-grid">
        <span>수량</span>
        <b>{p.qty.toLocaleString('ko-KR')}</b>
        <span>평단</span>
        <b>
          {curSym}
          {p.avg.toLocaleString('ko-KR')}
        </b>
        <span>현재가</span>
        <b>
          {curSym}
          {p.price.toLocaleString('ko-KR')}
        </b>
        <span>평가금액</span>
        <b>{krw(p.value)}</b>
        <span>매수금액</span>
        <b>{krw(p.cost)}</b>
        <span>손익</span>
        <b style={{ color: isUp ? 'var(--up)' : 'var(--down)' }}>
          {krw(p.value - p.cost)} ({pct(p.ret)})
        </b>
      </div>

      <div className="truth-foot">기준 {now} · {p.exchange}</div>
    </div>
  );
}
