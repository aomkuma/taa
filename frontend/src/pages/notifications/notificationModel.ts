/**
 * What the notification centre shows for each notification (the same facts the worker's push carries,
 * app/worker/push.py): a translation key with its values, or the personalizer's finished text for
 * opportunities, plus where a click leads.
 */
import type { NotificationItem } from './schemas';

export type NotificationText =
  | { kind: 'key'; key: string; values: Record<string, string>; reason?: string; status?: string }
  | { kind: 'text'; title: string; body: string }
  | { kind: 'none' };

export interface NotificationView {
  text: NotificationText;
  /** In-app link, or null when the notification has no page of its own. */
  link: string | null;
}

const str = (value: unknown): string => (typeof value === 'string' ? value : '');

/** The prebuilt push (`payload.push`) of an opportunity alert, in the user's language when it was sent. */
function prebuilt(payload: Record<string, unknown>): { title: string; body: string } | null {
  const push = payload.push;
  if (typeof push !== 'object' || push === null) return null;
  const { title, body } = push as Record<string, unknown>;
  return typeof title === 'string' ? { title, body: str(body) } : null;
}

export function describe(n: NotificationItem): NotificationView {
  const p = n.payload;
  switch (n.type) {
    case 'ENGINE_OFFLINE':
      return {
        text: { kind: 'key', key: 'ENGINE_OFFLINE', values: { label: str(p.label) }, reason: str(p.reason) },
        link: '/',
      };
    case 'ENGINE_BACK':
      return { text: { kind: 'key', key: 'ENGINE_BACK', values: { label: str(p.label) } }, link: '/' };
    case 'BACKTEST_FINISHED': {
      const run = str(p.run_id);
      return {
        text: {
          kind: 'key',
          key: 'BACKTEST_FINISHED',
          values: { preset: str(p.preset) },
          status: str(p.status),
        },
        link: run ? `/backtests?run=${encodeURIComponent(run)}` : '/backtests',
      };
    }
    case 'OPPORTUNITY':
    case 'OPPORTUNITY_UPDATE': {
      const id = str(p.opportunity_id);
      const text = prebuilt(p);
      return {
        text: text ? { kind: 'text', ...text } : { kind: 'none' },
        link: id ? `/charts?opportunity=${encodeURIComponent(id)}` : null,
      };
    }
    case 'TEST':
      return { text: { kind: 'key', key: 'TEST', values: {} }, link: null };
    default:
      return { text: { kind: 'none' }, link: null };
  }
}
