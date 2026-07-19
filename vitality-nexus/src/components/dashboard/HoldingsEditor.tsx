import { useEffect, useState } from 'react';
import { fetchHoldings, saveHoldings, type HoldingInput } from '../../api/client';

/**
 * 보유종목 편집 패널 — holdings.json을 손으로 안 고치고 UI로 추가/삭제.
 * API 키 없이 쓰는 사용자의 핵심 입력 경로. 저장은 로컬 파일에만 쓴다.
 */

const EMPTY_ROW: HoldingInput = {
  exchange: 'manual',
  assetType: 'crypto',
  market: 'upbit',
  symbol: '',
  name: '',
  qty: 0,
  avg: 0,
};

export function HoldingsEditor({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [rows, setRows] = useState<HoldingInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 미완성 행이 있을 때, 한 번 경고한 뒤 두 번째 클릭에서만 저장(조용한 삭제 방지)
  const [confirmDrop, setConfirmDrop] = useState(false);

  useEffect(() => {
    fetchHoldings()
      .then((data) => setRows(data.positions))
      .catch((e) => {
        setLoadFailed(true);
        setError('보유종목을 불러오지 못했습니다: ' + String(e));
      })
      .finally(() => setLoading(false));
  }, []);

  function update(i: number, patch: Partial<HoldingInput>) {
    setConfirmDrop(false);
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setConfirmDrop(false);
    setRows((rs) => [...rs, { ...EMPTY_ROW }]);
  }

  function removeRow(i: number) {
    setConfirmDrop(false);
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }

  async function handleSave() {
    // 불러오기 실패 상태에서 저장하면 rows=[]로 기존 파일을 통째로 덮어쓸 수 있다 → 차단
    if (loadFailed) {
      setError('기존 보유종목을 못 불러와서 저장을 막았습니다 (덮어쓰기·전량 소실 방지). 편집기를 다시 열어 주세요.');
      return;
    }
    // 심볼/수량/평단이 유효한 행만 저장
    const valid = rows.filter((r) => r.symbol.trim() && r.qty > 0 && r.avg > 0);
    const dropped = rows.length - valid.length;
    // 미완성 행이 있으면 한 번 경고 (조용히 사라지지 않게)
    if (dropped > 0 && !confirmDrop) {
      setConfirmDrop(true);
      setError(`미완성 행 ${dropped}개(심볼·수량·평단 누락)는 저장에서 제외됩니다. 계속하려면 "제외하고 저장"을 누르세요.`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveHoldings(valid);
      onSaved();
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="editor-backdrop" onClick={onClose}>
      <div className="editor-panel glass-card" onClick={(e) => e.stopPropagation()}>
        <div className="editor-header">
          <h2>보유종목 편집</h2>
          <button type="button" className="editor-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <p className="editor-hint">
          API 키가 없어도 여기에 보유 종목을 적으면 대시보드가 채워집니다. 암호화폐·주식
          현재가는 공개 시세로 자동 갱신됩니다. (미국 주식은 USD→KRW 자동 환산)
        </p>

        {loading ? (
          <div className="editor-loading">불러오는 중…</div>
        ) : (
          <div className="editor-rows">
            {rows.map((r, i) => (
              <div key={i} className="editor-row">
                <select
                  value={r.assetType}
                  onChange={(e) => {
                    const assetType = e.target.value as HoldingInput['assetType'];
                    update(i, {
                      assetType,
                      // 타입 바꾸면 관련 필드 초기화
                      market: assetType === 'crypto' ? 'upbit' : undefined,
                      region: assetType === 'stock' ? 'KR' : undefined,
                    });
                  }}
                >
                  <option value="crypto">암호화폐</option>
                  <option value="stock">주식</option>
                </select>

                {r.assetType === 'crypto' ? (
                  <select
                    value={r.market ?? 'upbit'}
                    onChange={(e) => update(i, { market: e.target.value as 'upbit' | 'bithumb' })}
                  >
                    <option value="upbit">업비트</option>
                    <option value="bithumb">빗썸</option>
                  </select>
                ) : (
                  <select
                    value={r.region ?? 'KR'}
                    onChange={(e) => update(i, { region: e.target.value as 'KR' | 'US' })}
                  >
                    <option value="KR">국내</option>
                    <option value="US">미국</option>
                  </select>
                )}

                <input
                  className="in-symbol"
                  placeholder={r.assetType === 'crypto' ? 'BTC' : r.region === 'US' ? 'AAPL' : '005930'}
                  value={r.symbol}
                  onChange={(e) => update(i, { symbol: e.target.value.trim() })}
                />
                <input
                  className="in-name"
                  placeholder="이름"
                  value={r.name}
                  onChange={(e) => update(i, { name: e.target.value })}
                />
                <input
                  className="in-num"
                  type="number"
                  placeholder="수량"
                  value={r.qty || ''}
                  onChange={(e) => update(i, { qty: Number(e.target.value) })}
                />
                <input
                  className="in-num"
                  type="number"
                  placeholder="평단"
                  value={r.avg || ''}
                  onChange={(e) => update(i, { avg: Number(e.target.value) })}
                />
                <button type="button" className="row-remove" onClick={() => removeRow(i)}>
                  ✕
                </button>
              </div>
            ))}
            <button type="button" className="editor-add" onClick={addRow}>
              + 종목 추가
            </button>
          </div>
        )}

        {error && <div className="editor-error">{error}</div>}

        <div className="editor-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>
            취소
          </button>
          <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? '저장 중…' : confirmDrop ? '제외하고 저장' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
