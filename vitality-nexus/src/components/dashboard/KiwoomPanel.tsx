import { useEffect, useState } from 'react';
import { fetchKiwoomStatus, saveKiwoomConfig, type KiwoomStatus } from '../../api/client';

/**
 * 키움 증권 연동 — 터미널 없이 앱 안에서 앱키/시크릿을 붙여넣고 저장.
 * 값은 로컬 백엔드를 거쳐 OS 키체인(Windows 자격증명 관리자)에만 저장된다.
 * 저장 후 실계좌 잔고·시장 순위가 실데이터로 채워진다.
 */
export function KiwoomPanel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [appKey, setAppKey] = useState('');
  const [appSecret, setAppSecret] = useState('');
  const [accountNo, setAccountNo] = useState('');
  const [isMock, setIsMock] = useState(false);
  const [status, setStatus] = useState<KiwoomStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchKiwoomStatus()
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
    if (!appKey.trim() || !appSecret.trim()) {
      setMsg('앱키와 시크릿키를 모두 붙여넣어 주세요.');
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      await saveKiwoomConfig({
        app_key: appKey,
        app_secret: appSecret,
        is_mock: isMock,
        account_no: accountNo || undefined,
      });
      setMsg('저장됐습니다. 잠시 후 실계좌 데이터로 채워집니다.');
      onSaved();
      setTimeout(onClose, 1200);
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
        aria-label="키움 증권 연동"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="editor-header">
          <h2>키움 증권 연동</h2>
          <button type="button" className="editor-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <p className="editor-hint">
          <a href="https://openapi.kiwoom.com" target="_blank" rel="noreferrer">
            openapi.kiwoom.com
          </a>
          에서 발급받은 <b>앱키</b>·<b>시크릿키</b>를 붙여넣고 저장하면, 실계좌 잔고와 시장
          순위가 실데이터로 채워집니다. 값은 이 PC의 자격증명 저장소에만 보관됩니다.
        </p>

        <div className="kiwoom-form">
          <label className="kiwoom-field">
            <span>앱키 (App Key)</span>
            <input
              type="password"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              placeholder="발급받은 App Key 붙여넣기"
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <label className="kiwoom-field">
            <span>시크릿키 (Secret Key)</span>
            <input
              type="password"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
              placeholder="발급받은 Secret Key 붙여넣기"
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <label className="kiwoom-field">
            <span>계좌번호 (선택 — 모르면 비워두세요)</span>
            <input
              type="text"
              value={accountNo}
              onChange={(e) => setAccountNo(e.target.value)}
              placeholder="예: 12345678"
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <label className="settings-toggle">
            <input type="checkbox" checked={isMock} onChange={(e) => setIsMock(e.target.checked)} />
            <span>
              <strong>모의투자 계좌</strong>
              <span className="settings-hint">
                실제 계좌면 체크 해제 (기본). 모의투자용 키면 체크.
              </span>
            </span>
          </label>
        </div>

        {status && (
          <p className="settings-note">
            현재 상태: {status.configured ? '연동됨' : '미연동'}
            {status.configured && (status.isMock ? ' · 모의투자' : ' · 실전')}
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
