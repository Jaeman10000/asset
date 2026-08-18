import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchStockMaster } from '../../api/client';
import type { ChartTarget, MasterStock } from '../../api/types';

/**
 * SearchPalette — 시장의 모든 종목(KOSPI+KOSDAQ ≈4,300)을 이름·코드로 검색.
 *
 * 마스터 목록은 서버(ka10099, 하루 1회)→localStorage(당일)로 이중 캐시되어
 * 타이핑 중 API 호출이 0회다(키움 레이트리밋 안전). Enter/클릭 → 상세 차트 패널.
 * 열기: 상단바 검색 캡슐 클릭 또는 단축키 '/' (Dashboard가 관리).
 */

const RECENT_KEY = 'vn_recent_stocks';
const MAX_RESULTS = 8;

function loadRecent(): MasterStock[] {
  try {
    return (JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') as MasterStock[]).slice(0, 6);
  } catch {
    return [];
  }
}

function pushRecent(s: MasterStock) {
  const cur = loadRecent().filter((r) => r.code !== s.code);
  localStorage.setItem(RECENT_KEY, JSON.stringify([s, ...cur].slice(0, 6)));
}

/** 매칭 부분 청록 하이라이트 */
function Highlight({ name, q }: { name: string; q: string }) {
  const i = q ? name.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return <>{name}</>;
  return (
    <>
      {name.slice(0, i)}
      <b>{name.slice(i, i + q.length)}</b>
      {name.slice(i + q.length)}
    </>
  );
}

export function SearchPalette({
  open,
  heldSymbols,
  onSelect,
  onClose,
}: {
  open: boolean;
  heldSymbols: Set<string>;
  onSelect: (t: ChartTarget) => void;
  onClose: () => void;
}) {
  const [master, setMaster] = useState<MasterStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const recent = useMemo(loadRecent, [open]);

  // 열릴 때: 포커스 + 마스터 로드(1회)
  useEffect(() => {
    if (!open) return;
    setQ('');
    setSel(0);
    setError(false);
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    if (!master.length) {
      setLoading(true);
      fetchStockMaster()
        .then(setMaster)
        .catch(() => setError(true))
        .finally(() => setLoading(false));
    }
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const results = useMemo(() => {
    const query = q.trim();
    if (!query) return [];
    const lower = query.toLowerCase();
    const isCode = /^\d/.test(query);
    const starts: MasterStock[] = [];
    const includes: MasterStock[] = [];
    for (const s of master) {
      if (isCode) {
        if (s.code.startsWith(query)) starts.push(s);
      } else {
        const nl = s.name.toLowerCase();
        if (nl.startsWith(lower)) starts.push(s);
        else if (nl.includes(lower)) includes.push(s);
      }
      if (starts.length >= MAX_RESULTS) break;
    }
    return [...starts, ...includes].slice(0, MAX_RESULTS);
  }, [master, q]);

  const pick = (s: MasterStock) => {
    pushRecent(s);
    onSelect({
      symbol: s.code,
      name: s.name,
      assetType: 'stock',
      region: 'KR',
      currency: 'KRW',
      market: s.market,
      industry: s.industry,
    });
    onClose();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((v) => Math.min(v + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((v) => Math.max(v - 1, 0));
    } else if (e.key === 'Enter' && results[sel]) {
      pick(results[sel]);
    }
  };

  if (!open) return null;

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <div className="pal-input">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--life)" strokeWidth="2.4" strokeLinecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSel(0);
            }}
            onKeyDown={onKey}
            placeholder="종목 이름 또는 코드 — 예: 삼성, 하이닉스, 005930"
            spellCheck={false}
          />
          <span className="pal-hint">
            <kbd>↑↓</kbd>
            <kbd>Enter</kbd>
            <kbd>Esc</kbd>
          </span>
        </div>

        <div className="pal-list">
          {loading && <div className="pal-empty">종목 목록 불러오는 중… (첫 실행만)</div>}
          {error && <div className="pal-empty">종목 목록을 못 받았습니다 — 키움 연동을 확인해주세요.</div>}
          {!loading && !error && q.trim() && results.length === 0 && (
            <div className="pal-empty">"{q}" 검색 결과 없음</div>
          )}
          {results.map((s, i) => (
            <div
              key={s.code}
              className={`pal-item${i === sel ? ' sel' : ''}`}
              onMouseEnter={() => setSel(i)}
              onClick={() => pick(s)}
            >
              <div className="pal-main">
                <div className="pal-nm">
                  <Highlight name={s.name} q={q.trim()} />
                  {heldSymbols.has(s.code) && <span className="held-chip">보유</span>}
                </div>
                <div className="pal-meta">
                  <span>{s.code}</span>
                  <span className="mkt">{s.market}</span>
                  {s.industry && <span>{s.industry}</span>}
                </div>
              </div>
              <span className="pal-go">차트 →</span>
            </div>
          ))}
          {!q.trim() && recent.length > 0 && (
            <>
              <div className="pal-sect">최근 본 종목</div>
              {recent.map((s) => (
                <div key={s.code} className="pal-item" onClick={() => pick(s)}>
                  <div className="pal-main">
                    <div className="pal-nm">{s.name}</div>
                    <div className="pal-meta">
                      <span>{s.code}</span>
                      <span className="mkt">{s.market}</span>
                    </div>
                  </div>
                  <span className="pal-go">차트 →</span>
                </div>
              ))}
            </>
          )}
          {!q.trim() && recent.length === 0 && !loading && (
            <div className="pal-empty">
              시장 전체 {master.length ? master.length.toLocaleString('ko-KR') : '4,000+'}종목을 검색할 수 있습니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
