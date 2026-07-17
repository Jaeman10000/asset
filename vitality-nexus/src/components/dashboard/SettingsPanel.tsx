import { useEffect, useState } from 'react';
import {
  isTauri,
  setPlacement,
  setAutostart,
  isAutostartEnabled,
  type PlacementMode,
} from '../../api/tauri';

/**
 * 데스크톱 설정 패널 — Tauri 앱에서만 의미 있음 (배치 모드, 부팅 자동시작).
 * 브라우저에서는 isTauri=false라 렌더되지 않는다.
 */

const MODES: { key: PlacementMode; label: string; desc: string }[] = [
  { key: 'normal', label: '일반 창', desc: '테두리 있는 보통 창' },
  { key: 'on-top', label: '항상 위', desc: '다른 창 위에 고정' },
  { key: 'desktop-widget', label: '데스크톱 위젯', desc: '배경화면에 붙임 (테두리 없음)' },
];

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState<PlacementMode>('normal');
  const [autostart, setAuto] = useState(false);

  useEffect(() => {
    void isAutostartEnabled().then(setAuto);
  }, []);

  async function chooseMode(m: PlacementMode) {
    setMode(m);
    await setPlacement(m);
  }

  async function toggleAutostart() {
    const next = !autostart;
    setAuto(next);
    await setAutostart(next);
  }

  return (
    <div className="editor-backdrop" onClick={onClose}>
      <div className="settings-panel glass-card" onClick={(e) => e.stopPropagation()}>
        <div className="editor-header">
          <h2>데스크톱 설정</h2>
          <button type="button" className="editor-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <section className="settings-section">
          <span className="stat-label">배치 모드</span>
          <div className="mode-options">
            {MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                className={`mode-btn ${mode === m.key ? 'active' : ''}`}
                onClick={() => void chooseMode(m.key)}
              >
                <strong>{m.label}</strong>
                <span>{m.desc}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="settings-section">
          <label className="settings-toggle">
            <input type="checkbox" checked={autostart} onChange={() => void toggleAutostart()} />
            <span>
              <strong>부팅 시 자동 실행</strong>
              <span className="settings-hint">PC를 켜면 백그라운드에서 자동으로 시작</span>
            </span>
          </label>
        </section>

        <p className="settings-note">
          배치 모드는 시스템 트레이 아이콘 우클릭 메뉴에서도 바꿀 수 있습니다.
        </p>
      </div>
    </div>
  );
}

/** Tauri 앱일 때만 설정 버튼을 노출하기 위한 헬퍼 */
export const settingsAvailable = isTauri;
