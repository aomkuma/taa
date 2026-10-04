import { safeReturnPath, sessionDeadline, SessionSchema, signedIn } from '@/auth/session';
import { makeSession } from '@/test/api';

const SERVER_NOW = Date.parse('2026-10-01T12:00:00Z');

describe('SessionSchema', () => {
  it('accepts the server payload', () => {
    expect(SessionSchema.parse(makeSession(SERVER_NOW)).user.username).toBe('owner');
    expect(
      SessionSchema.parse({ ...makeSession(), expires_at: '2026-10-01T12:30:00.123456+00:00' }).expires_at,
    ).toContain('.123456');
  });

  it('rejects naive datetimes and a missing CSRF token', () => {
    expect(SessionSchema.safeParse({ ...makeSession(), expires_at: '2026-10-01T12:30:00' }).success).toBe(
      false,
    );
    expect(SessionSchema.safeParse({ ...makeSession(), csrf_token: '' }).success).toBe(false);
  });
});

describe('sessionDeadline', () => {
  const session = SessionSchema.parse(makeSession(SERVER_NOW));

  it('is the last request plus the idle timeout', () => {
    const last = SERVER_NOW + 60_000;
    expect(sessionDeadline(session, last, 0)).toBe(last + 30 * 60_000);
  });

  it('never passes the absolute limit', () => {
    const last = SERVER_NOW + 12 * 3_600_000 - 60_000;
    expect(sessionDeadline(session, last, 0)).toBe(SERVER_NOW + 12 * 3_600_000);
  });

  it('measures the absolute limit on the server clock', () => {
    // The device clock runs three days ahead of the server.
    const skew = 3 * 24 * 3_600_000;
    const state = signedIn(session, SERVER_NOW + skew);
    if (state.status !== 'signed_in') throw new Error('expected signed in');
    expect(state.clockOffsetMs).toBe(-skew);
    const last = SERVER_NOW + skew + 12 * 3_600_000 - 60_000;
    expect(sessionDeadline(session, last, state.clockOffsetMs)).toBe(SERVER_NOW + skew + 12 * 3_600_000);
  });
});

describe('safeReturnPath', () => {
  it.each([
    ['/positions?tab=open', '/positions?tab=open'],
    ['/', '/'],
    ['//evil.example.com', '/'],
    ['https://evil.example.com', '/'],
    ['/login', '/'],
    [42, '/'],
    [undefined, '/'],
  ])('%s -> %s', (value, expected) => {
    expect(safeReturnPath(value)).toBe(expected);
  });
});
