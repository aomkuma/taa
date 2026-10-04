import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { EXPIRY_CHECK_MS } from '@/auth/hooks';
import { apiError, type FakeRequest, json, makeSession, mockApi } from '@/test/api';
import { renderApp } from '@/test/render';

const signedOut = () => apiError(401, 'unauthenticated');

async function fillAndSubmit(code = '123456') {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('ชื่อผู้ใช้'), 'owner');
  await user.type(screen.getByLabelText('รหัสผ่าน'), 'correct horse battery staple');
  await user.type(screen.getByLabelText('รหัสจากแอปยืนยันตัวตน'), code);
  await user.click(screen.getByRole('button', { name: 'เข้าสู่ระบบ' }));
}

describe('route guard', () => {
  it('sends a signed-out visitor to the login page and back after signing in', async () => {
    const { calls } = mockApi({
      'GET /auth/session': signedOut,
      'POST /auth/login': () => json(makeSession()),
    });
    const { router } = renderApp('/?tab=1');

    await screen.findByRole('heading', { name: 'เข้าสู่ระบบ' });
    expect(router.state.location.pathname).toBe('/login');

    await fillAndSubmit();

    await screen.findByText('เข้าสู่ระบบเป็น owner');
    expect(router.state.location.pathname + router.state.location.search).toBe('/?tab=1');
    const loginCall = calls.find((c: FakeRequest) => c.path === '/auth/login');
    expect(loginCall?.body).toEqual({
      username: 'owner',
      password: 'correct horse battery staple',
      code: '123456',
    });
  });

  it('shows nothing protected while the session check fails (fail closed)', async () => {
    mockApi({ 'GET /auth/session': () => apiError(503, 'unavailable') });
    renderApp('/');

    expect(await screen.findByRole('alert')).toHaveTextContent('ตรวจสอบการเข้าสู่ระบบไม่ได้');
    expect(screen.queryByRole('heading', { name: 'TAA' })).not.toBeInTheDocument();
  });

  it('skips the login page for a signed-in user', async () => {
    mockApi({ 'GET /auth/session': () => json(makeSession()) });
    const { router } = renderApp('/login');

    await screen.findByText('เข้าสู่ระบบเป็น owner');
    expect(router.state.location.pathname).toBe('/');
  });
});

describe('login errors', () => {
  it('does not say which factor was wrong and clears the code', async () => {
    mockApi({
      'GET /auth/session': signedOut,
      'POST /auth/login': () => apiError(401, 'invalid_credentials'),
    });
    renderApp('/login');

    await fillAndSubmit();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'ชื่อผู้ใช้ รหัสผ่าน หรือรหัสยืนยันไม่ถูกต้อง',
    );
    expect(screen.getByLabelText('รหัสจากแอปยืนยันตัวตน')).toHaveValue('');
  });

  it('shows the lockout wait in minutes', async () => {
    mockApi({
      'GET /auth/session': signedOut,
      'POST /auth/login': () => apiError(429, 'too_many_attempts', { retry_after: 121 }),
    });
    renderApp('/login');

    await fillAndSubmit();

    expect(await screen.findByRole('alert')).toHaveTextContent('กรุณาลองใหม่ในอีก 3 นาที');
  });

  it('reports a network failure', async () => {
    mockApi({
      'GET /auth/session': signedOut,
      'POST /auth/login': () => Promise.reject(new TypeError('Failed to fetch')),
    });
    renderApp('/login', 'en');

    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Username'), 'owner');
    await user.type(screen.getByLabelText('Password'), 'pw');
    await user.type(screen.getByLabelText('Authenticator code'), '123456');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server');
  });

  it('accepts digits only in the code field', async () => {
    mockApi({ 'GET /auth/session': signedOut });
    renderApp('/login');
    const user = userEvent.setup();
    const field = await screen.findByLabelText('รหัสจากแอปยืนยันตัวตน');

    await user.type(field, '12a3 4567');

    expect(field).toHaveValue('123456');
    expect(field).toHaveAttribute('autocomplete', 'one-time-code');
    expect(field).toHaveAttribute('inputmode', 'numeric');
  });
});

describe('session expiry', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns to the login page with a notice when a request finds the session gone', async () => {
    mockApi({ 'GET /auth/session': () => json(makeSession()), 'GET /positions': signedOut });
    const { router } = renderApp('/');
    await screen.findByText('เข้าสู่ระบบเป็น owner');

    const { apiGet } = await import('@/api/client');
    const { z } = await import('zod');
    await act(async () => {
      await expect(apiGet('/positions', z.object({}))).rejects.toMatchObject({ code: 'unauthenticated' });
    });

    expect(await screen.findByText('เซสชันหมดอายุแล้ว กรุณาเข้าสู่ระบบอีกครั้ง')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    expect(screen.queryByText('เข้าสู่ระบบเป็น owner')).not.toBeInTheDocument();
  });

  it('keeps the session when the device clock is days off', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-10-04T12:00:00Z'));
    // The server says it is 1 October: the absolute limit (1 Oct 24:00) is still 12 h away on its clock.
    mockApi({ 'GET /auth/session': () => json(makeSession(Date.parse('2026-10-01T12:00:00Z'))) });
    const { router } = renderApp('/');
    await screen.findByText('เข้าสู่ระบบเป็น owner');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2 * EXPIRY_CHECK_MS);
    });
    expect(router.state.location.pathname).toBe('/');
  });

  it('ends the session locally once the idle deadline passes without requests', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-10-01T12:00:00Z'));
    mockApi({ 'GET /auth/session': () => json(makeSession()) });
    const { router } = renderApp('/');
    await screen.findByText('เข้าสู่ระบบเป็น owner');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(29 * 60 * 1000);
    });
    expect(router.state.location.pathname).toBe('/');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60 * 1000 + EXPIRY_CHECK_MS);
    });
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/login');
    });
    expect(screen.getByText('เซสชันหมดอายุแล้ว กรุณาเข้าสู่ระบบอีกครั้ง')).toBeInTheDocument();
  });
});

describe('logout', () => {
  it('posts with the CSRF token and lands on the login page', async () => {
    const { calls } = mockApi({
      'GET /auth/session': () => json(makeSession()),
      'POST /auth/logout': () => json(null, 204),
    });
    const { router } = renderApp('/');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'ออกจากระบบ' }));

    expect(await screen.findByText('ออกจากระบบแล้ว')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    expect(calls.find((c) => c.path === '/auth/logout')?.headers['x-csrf-token']).toBe('csrf-123');
  });

  it('signs out locally even if the server already ended the session', async () => {
    mockApi({ 'GET /auth/session': () => json(makeSession()), 'POST /auth/logout': signedOut });
    const { router } = renderApp('/');
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'ออกจากระบบ' }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/login');
    });
  });
});
