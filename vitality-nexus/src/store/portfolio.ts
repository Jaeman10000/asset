/**
 * 포트폴리오 폴링 스토어 (zustand).
 *
 * 백엔드 캐시가 7초 TTL이므로 프론트도 7초마다 폴링한다 (더 자주 해도 캐시라
 * 의미 없음). 연결 상태(백엔드 살아있나)와 데이터 추정 상태(isEstimate)를
 * 구분해서 UI가 각각 다르게 반응하게 한다.
 */
import { create } from 'zustand';
import { fetchSnapshot, fetchSourceStatus } from '../api/client';
import type { PortfolioSnapshot, SourceStatus } from '../api/types';

// 7초 폴링은 키움 레이트리밋(실측 초당 ~1.25콜) 한계에 붙어 돌았고, 로딩 배지도 몇 초마다
// 깜빡였다. 60초면 호출이 1/8로 줄고 '실시간' 느낌은 남는다. 더 큰 절감은 백엔드가
// 장 마감 후엔 아예 재조회를 안 하는 것(services/market_hours.py) — 그때는 이 폴링이
// 캐시만 읽어오므로 키움 호출이 0회다. 즉시 갱신은 새로고침 버튼으로.
const POLL_INTERVAL_MS = 60_000;

type ConnState = 'connecting' | 'online' | 'offline';

interface PortfolioStore {
  snapshot: PortfolioSnapshot | null;
  sources: SourceStatus | null;
  conn: ConnState;
  lastError: string | null;
  /** 스냅샷 요청이 실제로 진행 중인지 — 새로고침 버튼 스피너/‘불러오는 중’ 문구용.
   *  콜드 로딩은 수급 사전조회 때문에 십수 초 걸리므로 정직한 진행 표시가 필요하다. */
  loading: boolean;
  /** 데이터가 방금 갱신된 순간 — 카드 플래시 트리거용 (fetchedAt이 바뀔 때마다 증가) */
  updateTick: number;

  start: () => void;
  stop: () => void;
  refresh: () => Promise<void>;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;
let inFlight: AbortController | null = null;
let onWake: (() => void) | null = null;

export const usePortfolio = create<PortfolioStore>((set, get) => {
  /**
   * 스냅샷 1회 폴링.
   *   force=false(주기 폴링): 이미 요청이 진행 중이면 스킵한다. 스냅샷이 폴링
   *     간격(7초)보다 오래 걸려도(콜드 캐시에서 업비트/빗썸/야후 실시세 조회)
   *     매 틱마다 이전 요청을 취소하다 영영 완료 못 하는 abort 루프를 방지 →
   *     첫 요청이 끝까지 돌아 캐시를 데우면 이후 폴링은 캐시 히트로 빨라진다.
   *   force=true(수동 새로고침, 예: 보유종목 저장 후): 진행 중 요청을 취소하고
   *     즉시 새 데이터를 받는다.
   */
  const poll = async (force: boolean, fresh = false) => {
    if (inFlight) {
      if (!force) return;
      inFlight.abort();
    }
    const ctrl = new AbortController();
    inFlight = ctrl;
    set({ loading: true });
    try {
      const snap = await fetchSnapshot(ctrl.signal, fresh);
      if (ctrl.signal.aborted) return;
      const prev = get().snapshot;
      const changed = !prev || prev.fetchedAt !== snap.fetchedAt;
      set((s) => ({
        snapshot: snap,
        conn: 'online',
        lastError: null,
        updateTick: changed ? s.updateTick + 1 : s.updateTick,
      }));
    } catch (err) {
      if (ctrl.signal.aborted) return;
      set({ conn: 'offline', lastError: err instanceof Error ? err.message : String(err) });
    } finally {
      // force 새로고침으로 교체된 경우엔 새 요청이 아직 진행 중이므로 loading을 끄지 않는다.
      if (inFlight === ctrl) {
        inFlight = null;
        set({ loading: false });
      }
    }
  };

  return {
    snapshot: null,
    sources: null,
    conn: 'connecting',
    lastError: null,
    loading: false,
    updateTick: 0,

    // 수동 새로고침 = 강제(진행중 취소) + fresh(백엔드 캐시·수급 캐시 비우고 즉시 최신)
    refresh: () => poll(true, true),

    start: () => {
      if (pollTimer) return; // 이미 폴링 중
      void poll(false);
      // 소스 상태는 자주 안 바뀌므로 시작 시 1회 + 폴링마다 가볍게 재확인
      void fetchSourceStatus()
        .then((sources) => set({ sources }))
        .catch(() => {});
      pollTimer = setInterval(() => {
        void poll(false);
        void fetchSourceStatus()
          .then((sources) => set({ sources }))
          .catch(() => {});
      }, POLL_INTERVAL_MS);

      // 절전 복귀·창 포커스·네트워크 복구 시 강제 새로고침 —
      // 진행 중 요청이 stuck이면 취소하고 즉시 최신 데이터를 받아 stale 상태를 푼다.
      onWake = () => {
        if (document.visibilityState === 'visible') void poll(true);
      };
      window.addEventListener('focus', onWake);
      window.addEventListener('online', onWake);
      document.addEventListener('visibilitychange', onWake);
    },

    stop: () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      if (onWake) {
        window.removeEventListener('focus', onWake);
        window.removeEventListener('online', onWake);
        document.removeEventListener('visibilitychange', onWake);
        onWake = null;
      }
      inFlight?.abort();
      inFlight = null;
    },
  };
});
