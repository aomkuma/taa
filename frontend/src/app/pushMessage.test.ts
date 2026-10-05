import { parsePushMessage, safePath } from './pushMessage';

describe('push message', () => {
  it('reads what the worker sends', () => {
    expect(
      parsePushMessage({
        notification_id: 'n1',
        type: 'OPPORTUNITY',
        severity: 'INFO',
        title: 'XAUUSD ซื้อ',
        body: 'line 1\nline 2',
        tag: 'o1',
        url: '/opportunities/o1',
        silent: false,
        renotify: true,
        badge: 2,
      }),
    ).toEqual({
      title: 'XAUUSD ซื้อ',
      body: 'line 1\nline 2',
      tag: 'o1',
      url: '/opportunities/o1',
      silent: false,
      renotify: true,
      badge: 2,
    });
  });

  it('fills in what a plain push leaves out', () => {
    expect(parsePushMessage({ title: 'Test notification', url: '/notifications' })).toEqual({
      title: 'Test notification',
      body: '',
      tag: '',
      url: '/notifications',
      silent: false,
      renotify: false,
      badge: null,
    });
  });

  it('drops pushes without a title', () => {
    expect(parsePushMessage(null)).toBeNull();
    expect(parsePushMessage('text')).toBeNull();
    expect(parsePushMessage({ body: 'x' })).toBeNull();
  });

  it('keeps clicks inside the app', () => {
    expect(safePath('/charts?opportunity=o1')).toBe('/charts?opportunity=o1');
    expect(safePath('https://evil.example/')).toBe('/');
    expect(safePath('//evil.example/')).toBe('/');
    expect(safePath('/\\evil.example')).toBe('/');
    expect(safePath(42)).toBe('/');
  });
});
