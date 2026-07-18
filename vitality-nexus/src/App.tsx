import { useEffect, useMemo, useState } from 'react';
import { Dashboard } from './components/dashboard/Dashboard';
import { StatusBar } from './components/dashboard/StatusBar';
import { HoldingsEditor } from './components/dashboard/HoldingsEditor';
import { SettingsPanel, settingsAvailable } from './components/dashboard/SettingsPanel';
import { AuroraVeil } from './components/dashboard/AuroraVeil';
import { OrganicCoreScene } from './components/organic-core/OrganicCoreScene';
import type { RingSector } from './components/organic-core/HoloSectorRings';
import { usePortfolio } from './store/portfolio';
import { portfolioBpm } from './util/heart';

/**
 * App — Vitality Nexus.
 * 배경(아래→위): AuroraVeil(초저해상도 안개, 렉 없음) → 3D 심장 씬(투명) → 글래스 UI.
 * 프로토타입의 정보 구조(3열 그리드, 시장 랭킹, 수급 호버)를 exe의 질감으로 렌더.
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

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  const bpm = snapshot ? portfolioBpm(snapshot.totals.total.pnlPct) : 72;

  // 홀로그램 섹터 링 + 하단 리드아웃 공용 데이터
  const krSectors: RingSector[] = useMemo(
    () =>
      (snapshot?.sectorFlows ?? [])
        .filter((s) => s.region === 'KR')
        .map((s) => ({
          name: s.name,
          ret: s.ret ?? 0,
          foreign: s.foreign ?? 0,
          inst: s.inst ?? 0,
          individual: s.individual ?? 0,
        })),
    [snapshot],
  );
  const usSectors: RingSector[] = useMemo(
    () =>
      (snapshot?.sectorFlows ?? [])
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .map((s) => ({ name: s.name, ret: s.ret ?? 0 })),
    [snapshot],
  );

  return (
    <div className={snapshot?.isEstimate ? 'dashboard estimate' : 'dashboard'}>
      {/* 배경 1: 안개 (초저해상도 셰이더 + CSS 블러 → 렉 없이 고급 안개)
          디버그: ?noveil 로 끄고 격리 가능 */}
      {!new URLSearchParams(window.location.search).has('noveil') && <AuroraVeil />}
      {/* 배경 2: 3D 심장 + 홀로그램 섹터 링 + 파티클 + Bloom (투명 캔버스) */}
      <div className="scene-bg">
        <OrganicCoreScene bpm={bpm} krSectors={krSectors} usSectors={usSectors} />
      </div>

      {/* 상단 바 (프로토타입: 브랜드 + 마켓 상태 필) */}
      <header className="topbar">
        <span className="brand">VITALITY NEXUS</span>
        <span className="brand-sub">LIVING DASHBOARD · HEART AT THE CENTER</span>
        <div className="market-pills">
          <span className="pill">
            <i />KR 주식
          </span>
          <span className="pill">
            <i />US 주식
          </span>
          <span className="pill live">
            <i />CRYPTO 24H
          </span>
        </div>
      </header>

      {snapshot ? (
        <Dashboard snapshot={snapshot} bpm={bpm} krSectors={krSectors} usSectors={usSectors} />
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
