import { useEffect, useState } from 'react';
import { OrganicCoreScene } from './components/organic-core/OrganicCoreScene';
import { Dashboard } from './components/dashboard/Dashboard';
import { StatusBar } from './components/dashboard/StatusBar';
import { HoldingsEditor } from './components/dashboard/HoldingsEditor';
import { SettingsPanel, settingsAvailable } from './components/dashboard/SettingsPanel';
import { SceneBoundary } from './components/SceneBoundary';
import { usePortfolio } from './store/portfolio';
import { portfolioBpm } from './util/heart';

/**
 * App — Vitality Nexus 대시보드. 백엔드(localhost:8787)를 7초마다 폴링해서
 * 실 포트폴리오 데이터로 3D 심장 씬 + 유리 카드 오버레이를 구동한다.
 *
 * dev 토글: ?scene=1 을 붙이면 3D 씬만(오버레이 없이) 본다 (씬 디버깅용).
 */

function sceneOnly(): boolean {
  return new URLSearchParams(window.location.search).has('scene');
}

/** 우하단 실측 FPS (씬이 노출하는 __renderCount 기준) */
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
  const debugSceneOnly = sceneOnly();
  const { snapshot, sources, conn, updateTick, start, stop, refresh } = usePortfolio();
  const [editorOpen, setEditorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  const total = snapshot?.totals.total;
  const bpm = total ? portfolioBpm(total.pnlPct) : 72;
  const hasData = !!snapshot && snapshot.positions.length > 0;

  return (
    <div className="dashboard">
      <div className="scene-layer">
        <SceneBoundary>
          <OrganicCoreScene bpm={bpm} beatEnergy={undefined} />
        </SceneBoundary>
      </div>

      {!debugSceneOnly && (
        <>
          {hasData && snapshot && (
            <div className={snapshot.isEstimate ? 'overlay estimate' : 'overlay'}>
              <Dashboard snapshot={snapshot} flashKey={updateTick} />
            </div>
          )}

          {/* 데이터 없음(연결됐지만 보유종목 0) → 시작 안내 */}
          {conn === 'online' && !hasData && (
            <div className="empty-state glass-card">
              <h1>VITALITY NEXUS</h1>
              <p>보유 종목이 없습니다. API 키 없이도 종목을 직접 추가하면 대시보드가 채워집니다.</p>
              <button type="button" className="btn-primary" onClick={() => setEditorOpen(true)}>
                보유종목 추가
              </button>
            </div>
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
            <HoldingsEditor
              onClose={() => setEditorOpen(false)}
              onSaved={() => void refresh()}
            />
          )}

          {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
        </>
      )}

      <FpsMeter />
    </div>
  );
}
