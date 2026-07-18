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

const POLL_INTERVAL_MS = 7000;

type ConnState = 'connecting' | 'online' | 'offline';

interface PortfolioStore {
  snapshot: PortfolioSnapshot | null;
  sources: SourceStatus | null;
  conn: ConnState;
  lastError: string | null;
  /** 데이터가 방금 갱신된 순간 — 카드 플래시 트리거용 (fetchedAt이 바뀔 때마다 증가) */
  updateTick: number;

  start: () => void;
  stop: () => void;
  refresh: () => Promise<void>;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;
let inFlight: AbortController | null = null;

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
  const poll = async (force: boolean) => {
    if (inFlight) {
      if (!force) return;
      inFlight.abort();
    }
    const ctrl = new AbortController();
    inFlight = ctrl;
    try {
      const snap = await fetchSnapshot(ctrl.signal);
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
      if (inFlight === ctrl) inFlight = null;
    }
  };

  return {
    snapshot: null,
    sources: null,
    conn: 'connecting',
    lastError: null,
    updateTick: 0,

    refresh: () => poll(true),

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
    },

    stop: () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      inFlight?.abort();
      inFlight = null;
    },
  };
});
