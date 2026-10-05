/** The fake API of the smoke tests: recorded samples (tests/web/test_api_samples.py) behind `page.route`. */
import type { Page, Route } from '@playwright/test';

import samples from '../src/test/fixtures/api-samples.json' with { type: 'json' };

const recorded = samples as Record<string, unknown>;

function session() {
  const now = Date.now();
  const iso = (ms: number) => new Date(ms).toISOString();
  return {
    user: { id: 'USER', username: 'owner', role: 'OWNER', locale: 'th', timezone: 'Asia/Bangkok' },
    csrf_token: 'csrf',
    expires_at: iso(now + 30 * 60_000),
    absolute_expires_at: iso(now + 12 * 3_600_000),
    idle_timeout_seconds: 1800,
    step_up_until: null,
    server_time: iso(now),
  };
}

const problem = (route: Route, status: number, code: string) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify({ error: { code, message: code } }),
  });

/** Serves `/api/v1/*`: the session (signed in or not), then any recorded GET sample; anything else 404. */
export async function fakeApi(page: Page, { signedIn }: { signedIn: boolean }): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1\//, '') + url.search;
    if (path === 'auth/session') {
      return signedIn
        ? route.fulfill({ contentType: 'application/json', body: JSON.stringify(session()) })
        : problem(route, 401, 'unauthenticated');
    }
    if (path.endsWith('/stream')) return problem(route, 404, 'not_found'); // no live stream in smoke tests
    const sample = route.request().method() === 'GET' ? recorded[path] : undefined;
    return sample === undefined
      ? problem(route, 404, 'not_found')
      : route.fulfill({ contentType: 'application/json', body: JSON.stringify(sample) });
  });
}
