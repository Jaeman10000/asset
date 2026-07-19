import { Component, useEffect, useMemo, useState, type ReactNode } from 'react';
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

/**
 * SceneBoundary — 3D 심장 씬(WebGL/R3F)에서 던진 에러를 여기서 잡아 씬만 숨긴다.
 * 이 경계가 없으면 씬 오류가 RootErrorBoundary까지 올라가 앱 전체가 빈 화면이
 * 된다(CTO 지적). GPU가 약하거나 컨텍스트 로스트가 나도 대시보드는 계속 쓰인다.
 */
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn('[scene] 3D 씬 오류 — 씬 없이 계속 진행', error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

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

  // 커서 추종 스포트라이트 — 마우스가 카드 위를 지날 때 청록빛이 따라오게
  // (.card::before의 --mx/--my를 갱신). rAF 스로틀 + transform만 갱신 → 저부담.
  useEffect(() => {
    let raf = 0;
    let pending: { card: HTMLElement; x: number; y: number } | null = null;
    const apply = () => {
      raf = 0;
      if (!pending) return;
      pending.card.style.setProperty('--mx', `${pending.x}px`);
      pending.card.style.setProperty('--my', `${pending.y}px`);
    };
    const onMove = (e: MouseEvent) => {
      const el = e.target instanceof Element ? e.target.closest<HTMLElement>('.card') : null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      pending = { card: el, x: e.clientX - r.left, y: e.clientY - r.top };
      if (!raf) raf = requestAnimationFrame(apply);
    };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => {
      window.removeEventListener('mousemove', onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  const bpm = snapshot ? portfolioBpm(snapshot.totals.total.pnlPct) : 72;

  // 홀로그램 섹터 링 + 하단 리드아웃 공용 데이터.
  // 순서 = 수급 순위: KR은 (외국인+기관) 순매수 강도, US는 등락률 내림차순.
  // 링과 리드아웃이 같은 배열을 받으므로 "12시=1위, 시계방향" 규칙이 둘 다 동일하다.
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
        }))
        .sort((a, b) => (b.foreign! + b.inst!) - (a.foreign! + a.inst!)),
    [snapshot],
  );
  const usSectors: RingSector[] = useMemo(
    () =>
      (snapshot?.sectorFlows ?? [])
        .filter((s) => s.region === 'US' && typeof s.ret === 'number')
        .map((s) => ({ name: s.name, ret: s.ret ?? 0 }))
        .sort((a, b) => b.ret - a.ret),
    [snapshot],
  );

  return (
    <div className={snapshot?.isEstimate ? 'dashboard estimate' : 'dashboard'}>
      {/* 배경 1: 안개 (초저해상도 셰이더 + CSS 블러 → 렉 없이 고급 안개)
          디버그: ?noveil 로 끄고 격리 가능 */}
      {!new URLSearchParams(window.location.search).has('noveil') && <AuroraVeil />}
      {/* 배경 2: 3D 심장 + 홀로그램 섹터 링 + 파티클 (투명 캔버스).
          Bloom은 기본 OFF: (1) MeshTransmissionMaterial(유리 심장)을 매 프레임 재샘플·
          재증폭해 시간이 지나면 심장이 하얗게 뭉개지는 피드백 루프를 만들고,
          (2) 약한 GPU(Intel UHD)에서 fps를 절반으로 깎는다. 홀로그램 발광은 궤도·노드·
          파티클의 가산 스프라이트가 자체적으로 낸다. 실험용으로 ?bloom 로 켤 수 있음. */}
      <div className="scene-bg">
        <SceneBoundary>
          <OrganicCoreScene
            bpm={bpm}
            krSectors={krSectors}
            usSectors={usSectors}
            bloom={new URLSearchParams(window.location.search).has('bloom')}
          />
        </SceneBoundary>
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
      ) : conn === 'offline' ? (
        <div className="boot-msg">
          <div className="boot-offline">
            <strong>백엔드에 연결하지 못했습니다</strong>
            <span>로컬 데이터 서버(127.0.0.1:8787)가 아직 준비되지 않았어요.</span>
            <button type="button" className="btn-primary" onClick={() => void refresh()}>
              다시 시도
            </button>
          </div>
        </div>
      ) : (
        <div className="boot-msg">불러오는 중…</div>
      )}

      {/* 빈 포트폴리오 — 첫 유저를 보유종목 추가로 유도 (온보딩 CTA) */}
      {snapshot && snapshot.positions.length === 0 && (
        <div className="empty-cta">
          <strong>아직 보유 종목이 없어요</strong>
          <span>보유 종목을 추가하면 심장이 내 자산으로 뛰기 시작합니다.</span>
          <button type="button" className="btn-primary" onClick={() => setEditorOpen(true)}>
            + 보유종목 추가
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
        <HoldingsEditor onClose={() => setEditorOpen(false)} onSaved={() => void refresh()} />
      )}
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}

      <FpsMeter />
    </div>
  );
}
