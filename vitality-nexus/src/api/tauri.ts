/**
 * Tauri 데스크톱 기능 래퍼 — 브라우저에서 열면 전부 no-op이 되도록 방어.
 * (같은 프론트 코드가 브라우저 dev와 Tauri 앱 양쪽에서 돌기 때문)
 */

export const isTauri =
  typeof window !== 'undefined' &&
  '__TAURI_INTERNALS__' in (window as unknown as Record<string, unknown>);

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(cmd, args);
}

export type PlacementMode = 'normal' | 'on-top' | 'desktop-widget';

export async function setPlacement(mode: PlacementMode): Promise<void> {
  if (!isTauri) return;
  await invoke('set_placement', { mode });
}

export async function setAutostart(enabled: boolean): Promise<void> {
  if (!isTauri) return;
  await invoke('set_autostart', { enabled });
}

export async function isAutostartEnabled(): Promise<boolean> {
  if (!isTauri) return false;
  try {
    return await invoke<boolean>('is_autostart');
  } catch {
    return false;
  }
}
