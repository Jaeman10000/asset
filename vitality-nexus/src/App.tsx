import { useEffect, useState } from 'react';
import { Dashboard, type AssetFilter } from './components/dashboard/Dashboard';
import { StatusBar } from './components/dashboard/StatusBar';
import { HoldingsEditor } from './components/dashboard/HoldingsEditor';
import { SettingsPanel, settingsAvailable } from './components/dashboard/SettingsPanel';
import { usePortfolio } from './store/portfolio';

const ASSET_TABS: { key: AssetFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'stock', label: '주식' },
  { key: 'crypto', label: '암호화폐' },
];

/**
 * App — Vitality Nexus 대시보드 셸.
 * 백엔드(localhost:8787)를 7초마다 폴링해서 프로토타입 3열 그리드 레이아웃으로
 * 실 포트폴리오를 표시한다. 3D 심장은 중앙 카드 안에 담긴다(Dashboard).
 */

/** 우하단 실측 FPS (심장 씬이 노출하는 __renderCount 기준) */
function FpsMeter() {
  const [fps, setFps] = useState(0);
  useEffect(() => {
    const w = window as unknown as Record<string, number>;
    let last = w.__renderCount ?? 0;
    const id = setInterval(() => {
      const now = w.__renderCount ?? 0;
      setFps(now - last);
      last = now;
    }, 1000);
    return () => clearInterval(id);
  }, []);
  return <div className="fps-meter">{fps} fps</div>;
}

export default function App() {
  const { snapshot, sources, conn, start, stop, refresh } = usePortfolio();
  const [editorOpen, setEditorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [assetFilter, setAssetFilter] = useState<AssetFilter>('all');

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  return (
    <div className={snapshot?.isEstimate ? 'dashboard estimate' : 'dashboard'}>
      {/* 상단 바 */}
      <header className="topbar">
        <span className="brand">VITALITY NEXUS</span>
        <span className="brand-sub">LIVING DASHBOARD · HEART AT THE CENTER</span>
        <nav className="asset-tabs">
          {ASSET_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={assetFilter === tab.key ? 'on' : ''}
              onClick={() => setAssetFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {snapshot ? (
        <Dashboard snapshot={snapshot} assetFilter={assetFilter} />
      ) : (
        <div className="boot-msg">{conn === 'offline' ? '백엔드 연결 대기 중…' : '불러오는 중…'}</div>
      )}

      <StatusBar
        conn={conn}
        isEstimate={snapshot?.isEstimate ?? false}
        sources={sources}
        errors={snapshot?.errors ?? []}
        onOpenEditor={() => setEditorOpen(true)}
        onOpenSettings={settingsAvailable ? () => setSettingsOpen(true) : undefined}
      />

      {editorOpen && (
        <HoldingsEditor onClose={() => setEditorOpen(false)} onSaved={() => void refresh()} />
      )}
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}

      <FpsMeter />
    </div>
  );
}
