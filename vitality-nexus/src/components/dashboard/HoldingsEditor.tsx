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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHoldings()
      .then((data) => setRows(data.positions))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  function update(i: number, patch: Partial<HoldingInput>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((rs) => [...rs, { ...EMPTY_ROW }]);
  }

  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    // 심볼/수량/평단이 유효한 행만 저장
    const valid = rows.filter((r) => r.symbol.trim() && r.qty > 0 && r.avg > 0);
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
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}
