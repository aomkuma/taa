import { describe as view } from './notificationModel';
import type { NotificationItem } from './schemas';

const item = (type: string, payload: Record<string, unknown>): NotificationItem => ({
  notification_id: 'n1',
  engine_id: 'e1',
  type,
  severity: 'INFO',
  payload,
  created_at: '2026-10-05T04:00:00+00:00',
  read_at: null,
  push_status: 'SENT',
});

describe('notification view', () => {
  it('describes engine and backtest notifications with translation keys and links', () => {
    expect(view(item('ENGINE_OFFLINE', { label: 'home pc', reason: 'SILENT' }))).toEqual({
      text: { kind: 'key', key: 'ENGINE_OFFLINE', values: { label: 'home pc' }, reason: 'SILENT' },
      link: '/',
    });
    expect(view(item('BACKTEST_FINISHED', { run_id: 'r 1', preset: 'standard', status: 'DONE' }))).toEqual({
      text: { kind: 'key', key: 'BACKTEST_FINISHED', values: { preset: 'standard' }, status: 'DONE' },
      link: '/backtests?run=r%201',
    });
    expect(view(item('TEST', {})).link).toBeNull();
  });

  it('shows the prebuilt opportunity text and links to its chart', () => {
    const push = { title: 'XAUUSD ซื้อ', body: 'line 1\nline 2', tag: 'o1' };
    expect(view(item('OPPORTUNITY', { push, opportunity_id: 'o1' }))).toEqual({
      text: { kind: 'text', title: 'XAUUSD ซื้อ', body: 'line 1\nline 2' },
      link: '/charts?opportunity=o1',
    });
    expect(view(item('OPPORTUNITY_UPDATE', { opportunity_id: 'o1' })).text).toEqual({ kind: 'none' });
  });

  it('ignores types it does not know', () => {
    expect(view(item('SOMETHING_NEW', { a: 1 }))).toEqual({ text: { kind: 'none' }, link: null });
  });
});
