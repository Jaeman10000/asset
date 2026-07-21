import { useState } from 'react';
import type { SourceError, SourceStatus } from '../../api/types';

/**
 * 우상단 상태 표시 — 연결/추정치/소스 설정 상태를 조용히 알린다.
 * 스펙: "isEstimate 플래그: 캐시된 값이면 UI에서 흐리게", "UI에 정직하게 표시".
 */

type ConnState = 'connecting' | 'online' | 'offline';

const SOURCE_LABELS: Record<string, string> = {
  kiwoom: '키움',
  kis: 'KIS',
  upbit: '업비트',
  bithumb: '빗썸',
  manual: '수동입력',
};

export function StatusBar({
  conn,
  loading,
  isEstimate,
  sources,
  errors,
  onOpenEditor,
  onOpenKiwoom,
  onOpenCrypto,
  onOpenSettings,
  onRefresh,
}: {
  conn: ConnState;
  /** 실제 요청 진행 중 여부 — 버튼 스피너/문구를 진짜 완료 시점까지 유지한다. */
  loading: boolean;
  isEstimate: boolean;
  sources: SourceStatus | null;
  errors: SourceError[];
  onOpenEditor: () => void;
  onOpenKiwoom: () => void;
  onOpenCrypto: () => void;
  /** 수동 새로고침 — 캐시 무시하고 지금 이 순간의 최신 수급/시세 재조회 */
  onRefresh: () => void;
  /** Tauri 앱일 때만 전달됨 (브라우저에선 undefined → 설정 버튼 숨김) */
  onOpenSettings?: () => void;
}) {
  // 예전엔 1.2초 타이머로 '가짜' 스핀만 돌렸다 — 실제 로딩(콜드 십수 초)과 안 맞아
  // 다 받은 줄 착각하게 됐다. 이제 스토어의 진짜 loading을 그대로 쓴다.
  const [open, setOpen] = useState(false);
  const connLabel =
    conn === 'online' ? '연결됨' : conn === 'connecting' ? '연결 중…' : '백엔드 오프라인';
  const connColor =
    conn === 'online' ? 'var(--life)' : conn === 'connecting' ? 'var(--event)' : 'var(--down)';

  return (
    <div className={`status-bar${open ? ' open' : ''}`}>
      {/* 평소엔 작은 상태 점만(우하단). 클릭하면 패널이 펼쳐지고, 다시 누르면 숨는다. */}
      <button
        type="button"
        className="status-toggle"
        onClick={() => setOpen((o) => !o)}
        title={open ? '숨기기' : '상태·설정 열기'}
      >
        <span className={`status-dot${loading ? ' loading' : ''}`} style={{ background: connColor }} />
        {/* 접혀 있어도 로딩 중이면 문구를 보여준다(작은 점만으론 진행 중인지 알 수 없다) */}
        {!open && loading && <span className="status-label">불러오는 중…</span>}
        {open && <span className="status-label">{loading ? '불러오는 중…' : connLabel}</span>}
        {open && isEstimate && <span className="status-estimate">추정치</span>}
      </button>

      {open && (
        <div className="status-panel">
          <div className="status-actions">
            <button
              type="button"
              className={`status-edit-btn refresh-btn${loading ? ' spinning' : ''}`}
              onClick={onRefresh}
              disabled={loading}
              title="지금 이 순간의 최신 수급·시세로 갱신 (캐시 무시)"
            >
              <span className="refresh-ico">↻</span> {loading ? '불러오는 중…' : '새로고침'}
            </button>
            <button type="button" className="status-edit-btn" onClick={onOpenEditor}>
              보유종목 편집
            </button>
            <button
              type="button"
              className="status-edit-btn"
              onClick={onOpenKiwoom}
              title="키움 앱키/시크릿 입력 (실계좌 연동)"
            >
              키움 연동
            </button>
            <button
              type="button"
              className="status-edit-btn"
              onClick={onOpenCrypto}
              title="업비트/빗썸 API 키 입력 (보유 코인 연동)"
            >
              거래소 연동
            </button>
            {onOpenSettings && (
              <button
                type="button"
                className="status-edit-btn"
                onClick={onOpenSettings}
                title="데스크톱 설정"
              >
                ⚙
              </button>
            )}
          </div>

          {sources && (
            <div className="source-chips">
              {(['manual', 'upbit', 'bithumb', 'kiwoom'] as const).map((k) => (
                <span
                  key={k}
                  className={`source-chip ${sources[k] ? 'on' : 'off'}`}
                  title={sources[k] ? '설정됨' : '미설정 (API 키 필요)'}
                >
                  {SOURCE_LABELS[k]}
                </span>
              ))}
            </div>
          )}

          {conn === 'offline' && (
            <div className="status-help">
              백엔드가 꺼져 있습니다. <code>backend/</code>에서
              <br />
              <code>uvicorn app.main:app --port 8787</code> 실행
            </div>
          )}

          {errors.length > 0 && conn === 'online' && (
            <details className="status-errors">
              <summary>{errors.length}개 소스 대기/오류</summary>
              <ul>
                {errors.map((e, i) => (
                  <li key={i}>
                    <b>{SOURCE_LABELS[e.source] ?? e.source}</b>: {e.message}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
