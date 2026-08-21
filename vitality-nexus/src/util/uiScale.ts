/**
 * uiScale — 큰 모니터에서 UI가 깨알같이 작아지는 문제 해결 (유저 요청: 화면에 딱 맞게).
 *
 * 대시보드는 폭 ~1500px / 높이 ~860px 기준으로 밀도를 잡았다. 2560·3840 같은 넓은
 * 화면에서는 같은 px 폰트가 상대적으로 훨씬 작아 보이고 아래쪽에 빈 공간이 남는다.
 * → 화면 크기 ÷ 기준 크기 만큼 **웹뷰 자체를 확대**한다(브라우저 Ctrl+= 와 동일).
 *
 * 왜 CSS zoom이 아니라 Tauri setZoom인가:
 *   CSS `zoom`을 쓰면 getBoundingClientRect()가 돌려준 좌표를 fixed 요소에 그대로
 *   쓸 때 zoom이 한 번 더 곱해져 호버 카드·차트 패널이 어긋난다(실측: rect 2716 →
 *   실제 4074). 네이티브 웹뷰 줌은 innerWidth·rect·vw가 모두 같은 좌표계로 움직여
 *   그런 부작용이 없다.
 */
import { getCurrentWebview } from '@tauri-apps/api/webview';

/** 이 밀도로 디자인된 기준 해상도 */
const BASE_W = 1500;
const BASE_H = 860;
const MIN = 1;
const MAX = 2.2; // 그 이상은 정보량이 너무 줄어 위젯 의미가 없어짐

const isTauri = () =>
  typeof window !== 'undefined' &&
  '__TAURI_INTERNALS__' in (window as unknown as Record<string, unknown>);

export function computeScale(w: number, h: number): number {
  // 가로·세로 중 더 빡빡한 쪽에 맞춘다 — 확대해도 세로가 잘리지 않게.
  const raw = Math.min(w / BASE_W, h / BASE_H);
  return Math.min(MAX, Math.max(MIN, Math.round(raw * 20) / 20)); // 0.05 단위로 스냅
}

/**
 * 현재 창 크기에 맞춰 웹뷰 줌을 적용하고, 창 크기가 바뀌면 다시 맞춘다.
 * 반환값은 정리 함수(리스너 해제).
 */
export function startUiScale(): () => void {
  if (!isTauri()) return () => {}; // 브라우저 dev에선 브라우저 줌을 존중해 건드리지 않음

  let applied = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const apply = () => {
    // 이미 줌이 걸린 상태의 innerWidth는 축소된 논리 px이므로, 물리 크기로 환산해
    // 계산해야 반복 적용 시 값이 튀지 않는다.
    const physW = window.innerWidth * (applied || 1);
    const physH = window.innerHeight * (applied || 1);
    const z = computeScale(physW, physH);
    if (Math.abs(z - applied) < 0.01) return;
    applied = z;
    void getCurrentWebview()
      .setZoom(z)
      .catch(() => {
        /* 권한 없거나 미지원 — 배율 1로 그냥 동작 */
      });
  };

  const onResize = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(apply, 180); // 리사이즈 중 연속 호출 방지
  };

  apply();
  window.addEventListener('resize', onResize);
  return () => {
    if (timer) clearTimeout(timer);
    window.removeEventListener('resize', onResize);
  };
}
