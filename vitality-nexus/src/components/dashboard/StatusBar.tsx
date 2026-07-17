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
  isEstimate,
  sources,
  errors,
  onOpenEditor,
  onOpenSettings,
}: {
  conn: ConnState;
  isEstimate: boolean;
  sources: SourceStatus | null;
  errors: SourceError[];
  onOpenEditor: () => void;
  /** Tauri 앱일 때만 전달됨 (브라우저에선 undefined → 설정 버튼 숨김) */
  onOpenSettings?: () => void;
}) {
  const connLabel =
    conn === 'online' ? '연결됨' : conn === 'connecting' ? '연결 중…' : '백엔드 오프라인';
  const connColor =
    conn === 'online' ? 'var(--life)' : conn === 'connecting' ? 'var(--event)' : 'var(--down)';

  return (
    <div className="status-bar">
      <div className="status-line">
        <span className="status-dot" style={{ background: connColor }} />
        <span>{connLabel}</span>
        {isEstimate && <span className="status-estimate">추정치</span>}
        <button type="button" className="status-edit-btn" onClick={onOpenEditor}>
          보유종목 편집
        </button>
        {onOpenSettings && (
          <button type="button" className="status-edit-btn" onClick={onOpenSettings} title="데스크톱 설정">
            ⚙
          </button>
        )}
      </div>

      {sources && (
        <div className="source-chips">
          {(['manual', 'upbit', 'bithumb', 'kis', 'kiwoom'] as const).map((k) => (
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

      {/* 진짜 실패(설정 대기 제외)만 접어서 보여줌 */}
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
  );
}
