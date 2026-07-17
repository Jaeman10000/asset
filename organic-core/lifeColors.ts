/**
 * lifeColors.ts — 전체 미학의 단일 소스 (하이브리드 색 시스템)
 *
 * 결정된 규칙:
 *   청록(LIFE) = 생명력의 색. 평상시. 심장·오로라·파티클·바닥반사·카드 기본 glow.
 *   금색(EVENT) = 사건의 색. 갱신 순간·랭킹 1위·BPM 등 "지금 주목" 신호에만.
 *
 * 이 파일 하나가 3D 씬과 CSS 양쪽의 색을 정한다.
 * CSS 쪽은 아래 값을 :root 변수로 복사해서 쓴다 (injectLifeColorsToCSS 참고).
 */

export const LIFE_COLOR = '#2be6c8';   // 청록 — 생명력, 평상시, 전체 통일 광원
export const LIFE_COLOR_DEEP = '#1a9e8c'; // 청록 딥 — 그라디언트 바닥
export const EVENT_COLOR = '#f2d675';  // 금색 — 데이터 갱신·강조 신호에만

// 한국 시장 관례색 (정보 신호 — 생명력 색과 별개로 유지)
export const UP_COLOR = '#f0a878';     // 상승 (따뜻한 주황)
export const DOWN_COLOR = '#7fa3c9';   // 하락 (차가운 파랑)

/**
 * CSS :root에 생명력 색을 주입한다.
 * 앱 마운트 시 1회 호출하면, 대시보드 카드 CSS가 3D 씬과 같은 색을 공유한다.
 * 이렇게 해야 "심장에서 나온 빛이 카드 테두리까지 물든다"는 통일감이 생긴다.
 */
export function injectLifeColorsToCSS() {
  const root = document.documentElement;
  root.style.setProperty('--life', LIFE_COLOR);
  root.style.setProperty('--life-deep', LIFE_COLOR_DEEP);
  root.style.setProperty('--event', EVENT_COLOR);
  root.style.setProperty('--up', UP_COLOR);
  root.style.setProperty('--down', DOWN_COLOR);
}
