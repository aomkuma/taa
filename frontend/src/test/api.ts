/**
 * A tiny fake of the FastAPI service for component tests: `fetch` is replaced by handlers keyed by
 * `"METHOD /path"` (path without `/api/v1`). Unknown routes answer 404, as the real service does.
 */

export interface FakeRequest {
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
}

export type Handler = (request: FakeRequest) => Response | Promise<Response>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

export function apiError(status: number, code: string, extra: Record<string, unknown> = {}): Response {
  return json({ error: { code, message: code, ...extra } }, status);
}

export function mockApi(handlers: Record<string, Handler>) {
  const calls: FakeRequest[] = [];
  const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const request: FakeRequest = {
      method: init?.method ?? 'GET',
      path: url.replace(/^\/api\/v1/, ''),
      headers: Object.fromEntries(new Headers(init?.headers).entries()),
      body: typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined,
    };
    calls.push(request);
    const handler = handlers[`${request.method} ${request.path}`];
    return handler ? handler(request) : apiError(404, 'not_found');
  });
  return { spy, calls };
}

/** A session payload as the server sends it right after login at *serverNow*. */
export function makeSession(serverNow: number = Date.now()) {
  const iso = (ms: number) => new Date(ms).toISOString().replace('Z', '+00:00');
  return {
    user: { id: 'u1', username: 'owner', role: 'OWNER', locale: 'th', timezone: 'Asia/Bangkok' },
    csrf_token: 'csrf-123',
    expires_at: iso(serverNow + 30 * 60_000),
    absolute_expires_at: iso(serverNow + 12 * 3_600_000),
    idle_timeout_seconds: 1800,
    step_up_until: null,
    server_time: iso(serverNow),
  };
}
