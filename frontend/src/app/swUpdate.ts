/**
 * A new app version waiting in the service worker (vite-plugin-pwa, `registerType: 'prompt'`).
 *
 * The waiting worker takes over only when the user agrees ("Reload" in UpdateBanner); until then the open
 * pages keep the version they loaded. main.tsx registers the worker and reports here; this module has no
 * dependency on the plugin's virtual module, so tests can drive it directly.
 */
import { useSyncExternalStore } from 'react';

/** How often an open page asks the server for a newer service worker (browsers only check on navigation). */
export const UPDATE_CHECK_MS = 60 * 60 * 1000;

type Apply = () => Promise<void>;

let apply: Apply | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Called once a new version is installed and waiting; `activate` swaps it in and reloads the page. */
export function updateReady(activate: Apply): void {
  apply = activate;
  emit();
}

/** Activate the waiting version (the page reloads). */
export async function applyUpdate(): Promise<void> {
  const activate = apply;
  apply = null;
  emit();
  if (activate) await activate();
}

/** Hide the banner for this page load; a later update shows it again. */
export function dismissUpdate(): void {
  apply = null;
  emit();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useUpdateAvailable(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => apply !== null,
    () => false,
  );
}
