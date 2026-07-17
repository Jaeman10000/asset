import { Component, type ReactNode } from 'react';

/**
 * 3D 씬(WebGL/R3F) 전용 에러 경계.
 *
 * WebView2에서 WebGL 컨텍스트 생성이 실패하거나 셰이더 컴파일이 throw하면,
 * 이 경계가 잡아서 대시보드(2D 오버레이)는 계속 뜨게 한다. 씬 하나 때문에
 * 앱 전체가 빈 화면("먹통")이 되는 것을 막는다.
 */
export class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error('[SceneBoundary] 3D 씬 렌더 실패 — 대시보드만 표시:', error);
  }

  render() {
    if (this.state.failed) {
      // 씬 대신 어두운 배경만 (대시보드 카드는 이 위에 그대로 뜬다)
      return (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(1200px 800px at 50% 42%, #0b1217 0%, #06090c 55%, #030507 100%)',
          }}
        />
      );
    }
    return this.props.children;
  }
}
