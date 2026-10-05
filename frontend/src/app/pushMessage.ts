/**
 * The Web Push message the worker sends (app/worker/push.py `push_message`), as the service worker shows it.
 * Pure, so it is tested with the app; `src/sw/sw.ts` imports it.
 */

export interface PushMessage {
  title: string;
  body: string;
  tag: string;
  /** Same-origin path to open on click. */
  url: string;
  silent: boolean;
  renotify: boolean;
  /** Active-opportunity count for the app icon badge (R25), or null when the push carries none. */
  badge: number | null;
}

/** Only an in-app path: a push must never send the user to another site. */
export function safePath(url: unknown): string {
  return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.includes('\\')
    ? url
    : '/';
}

export function parsePushMessage(data: unknown): PushMessage | null {
  if (typeof data !== 'object' || data === null) return null;
  const d = data as Record<string, unknown>;
  if (typeof d.title !== 'string' || d.title === '') return null;
  const badge = d.badge;
  return {
    title: d.title,
    body: typeof d.body === 'string' ? d.body : '',
    tag: typeof d.tag === 'string' ? d.tag : '',
    url: safePath(d.url),
    silent: d.silent === true,
    renotify: d.renotify === true,
    badge: typeof badge === 'number' && Number.isInteger(badge) && badge >= 0 ? badge : null,
  };
}
