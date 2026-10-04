import { z } from 'zod';

import {
  apiGet,
  ApiError,
  apiPost,
  apiPostEmpty,
  ApiSchemaError,
  CSRF_HEADER,
  lastActivityAt,
  onUnauthenticated,
  setCsrfToken,
} from '@/api/client';
import { apiError, json, mockApi } from '@/test/api';

const Status = z.object({ mode: z.enum(['PAPER', 'DEMO']) });

afterEach(() => {
  setCsrfToken(null);
});

describe('apiGet', () => {
  it('returns validated data from the same-origin API', async () => {
    const { spy } = mockApi({ 'GET /status': () => json({ mode: 'PAPER', extra: 1 }) });

    await expect(apiGet('/status', Status)).resolves.toEqual({ mode: 'PAPER' });
    expect(spy).toHaveBeenCalledWith(
      '/api/v1/status',
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' }),
    );
  });

  it('rejects a payload that does not match the schema', async () => {
    mockApi({ 'GET /status': () => json({ mode: 'LIVE' }) });

    await expect(apiGet('/status', Status)).rejects.toBeInstanceOf(ApiSchemaError);
  });

  it('reads the error code, message and retry hint from the error body', async () => {
    mockApi({ 'GET /status': () => apiError(429, 'too_many_attempts', { retry_after: 120 }) });

    await expect(apiGet('/status', Status)).rejects.toMatchObject({
      name: 'ApiError',
      status: 429,
      code: 'too_many_attempts',
      retryAfter: 120,
    });
  });

  it('falls back to the status when the error body is not ours', async () => {
    mockApi({ 'GET /status': () => new Response('<html>Bad gateway</html>', { status: 502 }) });

    await expect(apiGet('/status', Status)).rejects.toMatchObject({ status: 502, code: 'http_502' });
  });

  it('passes the abort signal through', async () => {
    const { spy } = mockApi({ 'GET /status': () => json({ mode: 'DEMO' }) });
    const controller = new AbortController();

    await apiGet('/status', Status, { signal: controller.signal });
    expect(spy.mock.calls[0]?.[1]).toMatchObject({ signal: controller.signal });
  });

  it('never sends the CSRF token on reads', async () => {
    setCsrfToken('csrf-1');
    const { calls } = mockApi({ 'GET /status': () => json({ mode: 'DEMO' }) });

    await apiGet('/status', Status);
    expect(calls[0]?.headers).not.toHaveProperty(CSRF_HEADER.toLowerCase());
  });

  it('records activity for the idle timer', async () => {
    mockApi({ 'GET /status': () => json({ mode: 'DEMO' }) });
    const before = Date.now();

    await apiGet('/status', Status);
    expect(lastActivityAt()).toBeGreaterThanOrEqual(before);
  });
});

describe('mutations', () => {
  it('send JSON with the CSRF token', async () => {
    setCsrfToken('csrf-1');
    const { calls } = mockApi({ 'POST /thing': () => json({ mode: 'PAPER' }) });

    await expect(apiPost('/thing', { a: 1 }, Status)).resolves.toEqual({ mode: 'PAPER' });
    expect(calls[0]).toMatchObject({
      method: 'POST',
      body: { a: 1 },
      headers: { 'content-type': 'application/json', 'x-csrf-token': 'csrf-1' },
    });
  });

  it('accept 204 No Content', async () => {
    mockApi({ 'POST /thing': () => json(null, 204) });

    await expect(apiPostEmpty('/thing')).resolves.toBeUndefined();
  });
});

describe('session end', () => {
  it('tells the listeners when the server says the session is gone', async () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthenticated(listener);
    mockApi({ 'GET /status': () => apiError(401, 'unauthenticated') });

    await expect(apiGet('/status', Status)).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    unsubscribe();
  });

  it('stays quiet for other 401s and when asked to', async () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthenticated(listener);
    mockApi({
      'POST /auth/login': () => apiError(401, 'invalid_credentials'),
      'GET /auth/session': () => apiError(401, 'unauthenticated'),
    });

    await expect(apiPost('/auth/login', {}, Status)).rejects.toMatchObject({ code: 'invalid_credentials' });
    await expect(apiGet('/auth/session', Status, { notifyUnauthenticated: false })).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });
});
