import { useEffect, useState } from 'react';
import { fetchCryptoStatus, saveCryptoConfig, type CryptoStatus } from '../../api/client';

/**
 * 거래소(업비트·빗썸) 연동 — 터미널 없이 앱 안에서 API 키를 붙여넣고 저장.
 * 값은 로컬 백엔드를 거쳐 OS 키체인에만 저장된다. 저장 후 실제 보유 코인이
 * 평가금액과 함께 채워진다. (조회 전용 키 권장 — 출금 권한 불필요)
 */
export function CryptoPanel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [upAccess, setUpAccess] = useState('');
  const [upSecret, setUpSecret] = useState('');
  const [bitKey, setBitKey] = useState('');
  const [bitSecret, setBitSecret] = useState('');
  const [status, setStatus] = useState<CryptoStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchCryptoStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function handleSave() {
    const hasUpbit = upAccess.trim() && upSecret.trim();
    const hasBithumb = bitKey.trim() && bitSecret.trim();
    if (!hasUpbit && !hasBithumb) {
      setMsg('업비트 또는 빗썸 중 하나 이상 키를 모두 입력해 주세요.');
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const r = await saveCryptoConfig({
        upbit_access: hasUpbit ? upAccess : undefined,
        upbit_secret: hasUpbit ? upSecret : undefined,
        bithumb_key: hasBithumb ? bitKey : undefined,
        bithumb_secret: hasBithumb ? bitSecret : undefined,
      });
      setMsg(`저장됐습니다 (${r.saved.join(', ') || '변경 없음'}). 잠시 후 보유 코인이 채워집니다.`);
      onSaved();
      setTimeout(onClose, 1400);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="editor-backdrop" onClick={onClose}>
      <div
        className="settings-panel glass-card"
        role="dialog"
        aria-modal="true"
        aria-label="거래소 연동"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="editor-header">
          <h2>거래소 연동 (암호화폐)</h2>
          <button type="button" className="editor-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <p className="editor-hint">
          업비트·빗썸에서 발급한 <b>조회 전용</b> API 키를 넣으면 실제 보유 코인이 채워집니다.
          <b> 출금 권한은 필요 없습니다</b>(자산 조회만). 값은 이 PC의 자격증명 저장소에만 보관됩니다.
          하나만 넣어도 됩니다.
        </p>

        <div className="kiwoom-form">
          <div className="crypto-group">
            <div className="crypto-group-title">
              업비트{' '}
              <a href="https://upbit.com/mypage/open_api_management" target="_blank" rel="noreferrer">
                키 발급
              </a>
            </div>
            <label className="kiwoom-field">
              <span>Access Key</span>
              <input
                type="password"
                value={upAccess}
                onChange={(e) => setUpAccess(e.target.value)}
                placeholder="업비트 Access Key"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            <label className="kiwoom-field">
              <span>Secret Key</span>
              <input
                type="password"
                value={upSecret}
                onChange={(e) => setUpSecret(e.target.value)}
                placeholder="업비트 Secret Key"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
          </div>

          <div className="crypto-group">
            <div className="crypto-group-title">
              빗썸{' '}
              <a href="https://www.bithumb.com/react/api-support/management-api" target="_blank" rel="noreferrer">
                키 발급
              </a>
            </div>
            <label className="kiwoom-field">
              <span>API Key</span>
              <input
                type="password"
                value={bitKey}
                onChange={(e) => setBitKey(e.target.value)}
                placeholder="빗썸 API Key"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            <label className="kiwoom-field">
              <span>Secret Key</span>
              <input
                type="password"
                value={bitSecret}
                onChange={(e) => setBitSecret(e.target.value)}
                placeholder="빗썸 Secret Key"
                autoComplete="off"
                spellCheck={false}
              />
            </label>
          </div>
        </div>

        {status && (
          <p className="settings-note">
            현재 상태: 업비트 {status.upbit ? '연동됨' : '미연동'} · 빗썸{' '}
            {status.bithumb ? '연동됨' : '미연동'}
          </p>
        )}
        {msg && <p className="editor-error">{msg}</p>}

        <div className="editor-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>
            취소
          </button>
          <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? '저장 중…' : '저장하고 연동'}
          </button>
        </div>
      </div>
    </div>
  );
}
