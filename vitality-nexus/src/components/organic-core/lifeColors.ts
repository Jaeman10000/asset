/**
 * lifeColors.ts — 전체 미학의 단일 소스 (OBSIDIAN VIOLET 팔레트, v0.3)
 *
 * 결정된 규칙 (7차 디자인 시안에서 확정):
 *   바이올렛(LIFE) = UI의 생명력·앰비언스. 오로라·파티클·카드 glow·활성 상태.
 *   크림슨(HEART) = 심장 전용. 보라 우주에서 유일한 붉은 생명체 — 주인공 대비.
 *   금색(EVENT)   = 사건의 색. 갱신 순간·랭킹 1위·★관심 등 "지금 주목" 신호.
 *   외국인=금 / 기관=에메랄드 (수급 주체 의미색 — investorColors 참고)
 *   상승=선명한 빨강 / 하락=밝은 파랑 (한국 관행, 토스증권 계열 채도)
 *
 * 이 파일 하나가 3D 씬과 CSS 양쪽의 색을 정한다.
 * CSS 쪽은 아래 값을 :root 변수로 복사해서 쓴다 (injectLifeColorsToCSS 참고).
 */

export const LIFE_COLOR = '#a78bfa'; // 바이올렛 — UI 생명력, 앰비언스, 전체 통일 광원
export const LIFE_COLOR_DEEP = '#7c5cf0'; // 바이올렛 딥 — 그라디언트 바닥
export const EVENT_COLOR = '#fbbf24'; // 금색 — 데이터 갱신·강조 신호에만

// 3D 심장 전용 — 실제 심장의 색. UI 바이올렛과 분리해 심장이 주인공이 되게 한다.
export const HEART_COLOR = '#e23a56'; // 크림슨
export const HEART_COLOR_DEEP = '#8f1430';

// 한국 시장 관례색 (정보 신호 — 생명력 색과 별개로 유지)
export const UP_COLOR = '#ff5d73'; // 상승 (선명한 코랄레드)
export const DOWN_COLOR = '#5b8cff'; // 하락 (밝은 블루)

// 수급 주체 의미색 — 호버 카드·섹터 레이더·수급 시그널이 공유
export const FOREIGN_COLOR = '#fbbf24'; // 외국인 (금)
export const INST_COLOR = '#34d399'; // 기관 (에메랄드)
export const INDIV_COLOR = '#7dd3fc'; // 개인 (아이스)

/**
 * CSS :root에 팔레트를 주입한다.
 * 앱 마운트 시 1회 호출하면, 대시보드 카드 CSS가 3D 씬과 같은 색을 공유한다.
 */
export function injectLifeColorsToCSS() {
  const root = document.documentElement;
  root.style.setProperty('--life', LIFE_COLOR);
  root.style.setProperty('--life-deep', LIFE_COLOR_DEEP);
  root.style.setProperty('--event', EVENT_COLOR);
  root.style.setProperty('--heart', HEART_COLOR);
  root.style.setProperty('--up', UP_COLOR);
  root.style.setProperty('--down', DOWN_COLOR);
  root.style.setProperty('--gold', FOREIGN_COLOR);
  root.style.setProperty('--emer', INST_COLOR);
  root.style.setProperty('--ice', INDIV_COLOR);
}
