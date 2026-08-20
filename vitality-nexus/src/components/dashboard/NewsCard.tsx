import { useEffect, useState } from 'react';
import { fetchNews, type NewsItem } from '../../api/client';

/**
 * NewsCard — 마켓 뉴스 요약 (v0.3 좌측 하단, ChatGPT 시안에서 채택).
 * 언론사 공개 RSS(한경·매경·연합)를 백엔드가 10분 캐시로 수집 — 가짜 뉴스 없음.
 * 클릭 시 기본 브라우저로 원문 (Tauri에선 shell open, 브라우저 dev에선 새 탭).
 */

function timeAgo(ts: number): string {
  if (!ts) return '';
  const m = Math.max(1, Math.round((Date.now() - ts) / 60000));
  if (m < 60) return `${m}분 전`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.round(h / 24)}일 전`;
}

async function openLink(url: string) {
  if (!url) return;
  const w = window as unknown as Record<string, unknown>;
  if ('__TAURI_INTERNALS__' in w) {
    try {
      const shell = await import('@tauri-apps/plugin-shell');
      await shell.open(url);
      return;
    } catch {
      /* 폴백 */
    }
  }
  window.open(url, '_blank', 'noopener');
}

export function NewsCard() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchNews()
        .then((r) => {
          if (alive) {
            setItems(r);
            setLoaded(true);
          }
        })
        .catch(() => alive && setLoaded(true));
    load();
    const id = setInterval(load, 600_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (loaded && items.length === 0) return null; // 피드 전멸 시 카드 자체를 숨김 (빈 껍데기 금지)

  return (
    <div className="card news">
      <h3>
        <span className="dot" />
        마켓 뉴스
        <span className="exch">언론사 RSS · 10분</span>
      </h3>
      {items.slice(0, 4).map((n, i) => (
        <div className="nrow" key={i} onClick={() => void openLink(n.link)} title={n.title}>
          <i />
          <span className="tt">{n.title}</span>
          <span className="meta">
            {n.source} · {timeAgo(n.ts)}
          </span>
        </div>
      ))}
    </div>
  );
}
