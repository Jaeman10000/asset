import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
// glass-cards.css(카드 기본)를 먼저, index.css(레이아웃 오버라이드)를 나중에 —
// 같은 특이성일 때 레이아웃 쪽 position이 이기도록 순서 유지
import './styles/glass-cards.css'
import './index.css'
import { injectLifeColorsToCSS } from './components/organic-core/lifeColors'
import App from './App.tsx'

/**
 * 진단 보고 — WebView 화면이 멈춰도 원인을 알 수 있게 백엔드로 전송.
 * sendBeacon은 no-cors 파이어앤포겟이라 CORS/멈춤과 무관하게 전달된다.
 * 백엔드 data/clientlog.txt 에 쌓인다.
 */
function report(msg: string) {
  try {
    const url = 'http://127.0.0.1:8787/clientlog';
    const body = `[${location.href}] ${msg}`;
    if (navigator.sendBeacon) navigator.sendBeacon(url, body);
    else fetch(url, { method: 'POST', body, mode: 'no-cors' }).catch(() => {});
  } catch {
    /* noop */
  }
}

// 스크립트가 실행되기 시작한 시점 (JS 번들 자체가 도는지 확인)
report('boot: script start, UA=' + navigator.userAgent);

// WebGL이 이 WebView에서 생성되는지 확인 (검은 화면의 흔한 원인)
try {
  const c = document.createElement('canvas');
  const gl = c.getContext('webgl2') || c.getContext('webgl');
  if (gl) {
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unknown';
    report('webgl: OK renderer=' + renderer);
  } else {
    report('webgl: FAILED to create context (검은 화면 원인 가능)');
  }
} catch (e) {
  report('webgl: exception ' + String(e));
}

/**
 * 화면에 에러를 직접 띄우는 오버레이 — Tauri 패키지 앱은 devtools가 없어서
 * JS 에러가 나면 흰/검은 빈 화면("먹통")만 보인다. 그걸 진단 가능하게 만든다.
 */
function showFatalOverlay(title: string, detail: string) {
  report('FATAL: ' + title + ' :: ' + detail.slice(0, 500));
  const existing = document.getElementById('fatal-overlay')
  if (existing) return // 첫 에러만 표시
  const el = document.createElement('div')
  el.id = 'fatal-overlay'
  el.style.cssText =
    'position:fixed;inset:0;z-index:99999;background:#0a0e12;color:#e6f0f0;' +
    'font:13px/1.6 ui-monospace,Consolas,monospace;padding:24px;overflow:auto;white-space:pre-wrap'
  el.textContent = `⚠ ${title}\n\n${detail}\n\n(이 화면을 캡처해서 개발자에게 보내세요)`
  document.body.appendChild(el)
}

window.addEventListener('error', (e) => {
  showFatalOverlay(
    'JS 오류 (window.error)',
    `${e.message}\n${e.filename}:${e.lineno}:${e.colno}\n${e.error?.stack ?? ''}`,
  )
})
window.addEventListener('unhandledrejection', (e) => {
  const r = e.reason
  showFatalOverlay(
    'Promise 거부 (unhandledrejection)',
    typeof r === 'object' ? `${r?.message ?? ''}\n${r?.stack ?? JSON.stringify(r)}` : String(r),
  )
})

/** React 렌더 트리에서 throw된 에러를 잡아 화면에 표시하는 경계 */
class RootErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    showFatalOverlay('React 렌더 오류', `${error.message}\n${error.stack ?? ''}\n\n${info.componentStack ?? ''}`)
  }
  render() {
    if (this.state.error) return null // 오버레이가 대신 표시됨
    return this.props.children
  }
}

injectLifeColorsToCSS()

try {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <RootErrorBoundary>
        <App />
      </RootErrorBoundary>
    </StrictMode>,
  )
  report('react: createRoot().render() 호출 완료')
  // 마운트 후 실제로 DOM이 채워졌는지 (빈 화면 감지)
  setTimeout(() => {
    const root = document.getElementById('root')
    report('mount-check: root children=' + (root?.children.length ?? -1) +
      ' canvas=' + document.querySelectorAll('canvas').length)
  }, 3000)
} catch (err) {
  showFatalOverlay('마운트 실패', err instanceof Error ? `${err.message}\n${err.stack}` : String(err))
}
