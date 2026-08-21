import { useEffect, useMemo, useState } from 'react';
import { Dashboard } from './components/dashboard/Dashboard';
import { StatusBar } from './components/dashboard/StatusBar';
import { HoldingsEditor } from './components/dashboard/HoldingsEditor';
import { KiwoomPanel } from './components/dashboard/KiwoomPanel';
import { CryptoPanel } from './components/dashboard/CryptoPanel';
import { SettingsPanel, settingsAvailable } from './components/dashboard/SettingsPanel';
import { AuroraVeil } from './components/dashboard/AuroraVeil';
import type { RingSector } from './components/organic-core/HoloSectorRings';
import { usePortfolio } from './store/portfolio';
import { portfolioBpm } from './util/heart';
import { startUiScale } from './util/uiScale';

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

/**
 * 값이 true로 '연속 ms 이상' 유지될 때만 true가 되는 플래그.
 * 캐시 히트로 0.1초 만에 끝나는 폴링까지 '불러오는 중' 배지를 띄우면 몇 초마다 깜빡여
 * 거슬린다(유저 지적) → 실제로 오래 걸릴 때만 보이게 한다.
 */
function useDelayedFlag(value: boolean, ms: number): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!value) {
      setOn(false);
      return;
    }
    const t = setTimeout(() => setOn(true), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return on;
}

export default function App() {
  const { snapshot, sources, conn, loading, start, stop, refresh } = usePortfolio();
  const showLoading = useDelayedFlag(loading, 400);
  const [editorOpen, setEditorOpen] = useState(false);
  const [kiwoomOpen, setKiwoomOpen] = useState(false);
  const [cryptoOpen, setCryptoOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  // 큰 모니터에서 UI가 작아 보이지 않게 창 크기에 맞춰 웹뷰를 확대 (util/uiScale)
  useEffect(() => startUiScale(), []);

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

  // 레이더 US 필용 — KR 테마는 Dashboard가 snapshot.sectorFlows에서 직접 쓴다(members 포함).
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
      {/* 상단 바 (프로토타입: 브랜드 + 마켓 상태 필) */}
      <header className="topbar">
        <span className="brand">VITALITY NEXUS</span>
        <span className="brand-sub">LIVING DASHBOARD · HEART AT THE CENTER</span>
        {/* 종목 검색 진입점 — 클릭 또는 '/' 로 팔레트 열기 (Dashboard가 이벤트 수신) */}
        <button
          type="button"
          className="search-capsule"
          onClick={() => window.dispatchEvent(new CustomEvent('vn:search-open'))}
          title="시장 전체 종목 검색"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          종목 검색
          <kbd>/</kbd>
        </button>
        <div className="market-pills">
          {/* 로딩 중엔 상단에 항상 보이게 — 콜드/새로고침이 십수 초 걸리므로
              "멈춘 게 아니라 받아오는 중"이 눈에 보여야 한다. */}
          {showLoading && (
            <span className="pill loading-pill">
              <i className="load-spin" />정보 불러오는 중…
            </span>
          )}
          {/* v0.3: 탭처럼 보이던 필 → 장 상태 표시등. 초록=개장(실시간 갱신 중),
              회색=마감(장외 갱신 억제 정책으로 캐시 유지 — "왜 안 움직이지?"를 설명). */}
          <span className={`session-pill${snapshot?.krSession ? ' open' : ''}`}>
            <i />KR장 {snapshot?.krSession ? '개장중' : '마감'}
          </span>
          <span className={`session-pill${snapshot?.usSession ? ' open' : ''}`}>
            <i />US장 {snapshot?.usSession ? '개장중' : '마감'}
          </span>
          <span className="session-pill open">
            <i />CRYPTO 24H
          </span>
        </div>
      </header>

      {snapshot ? (
        <Dashboard snapshot={snapshot} bpm={bpm} usSectors={usSectors} />
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
        loading={showLoading}
        isEstimate={snapshot?.isEstimate ?? false}
        sources={sources}
        errors={snapshot?.errors ?? []}
        onOpenEditor={() => setEditorOpen(true)}
        onOpenKiwoom={() => setKiwoomOpen(true)}
        onOpenCrypto={() => setCryptoOpen(true)}
        onRefresh={() => void refresh()}
        onOpenSettings={settingsAvailable ? () => setSettingsOpen(true) : undefined}
      />

      {editorOpen && (
        <HoldingsEditor onClose={() => setEditorOpen(false)} onSaved={() => void refresh()} />
      )}
      {kiwoomOpen && (
        <KiwoomPanel onClose={() => setKiwoomOpen(false)} onSaved={() => void refresh()} />
      )}
      {cryptoOpen && (
        <CryptoPanel onClose={() => setCryptoOpen(false)} onSaved={() => void refresh()} />
      )}
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}

      <FpsMeter />
    </div>
  );
}
