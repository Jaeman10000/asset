import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// glass-cards.css(카드 기본)를 먼저, index.css(레이아웃 오버라이드)를 나중에 —
// 같은 특이성일 때 레이아웃 쪽 position이 이기도록 순서 유지
import './styles/glass-cards.css'
import './index.css'
import { injectLifeColorsToCSS } from './components/organic-core/lifeColors'
import App from './App.tsx'

// 3D 씬(LIFE_COLOR)과 대시보드 CSS(--life/--event)가 같은 색을 공유하도록
// :root 변수를 주입 — "하나의 광원" 색 통일의 핵심 (GUIDE.md ③)
injectLifeColorsToCSS()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
