import { z } from 'zod';

import { apiGet, ApiError, ApiSchemaError } from '@/api/client';

const Status = z.object({ mode: z.enum(['PAPER', 'DEMO']) });

function mockFetch(body: unknown, status = 200) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
    );
}

describe('apiGet', () => {
  it('returns validated data from the same-origin API', async () => {
    const fetchSpy = mockFetch({ mode: 'PAPER', extra: 1 });

    await expect(apiGet('/status', Status)).resolves.toEqual({ mode: 'PAPER' });
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/status',
      expect.objectContaining({ method: 'GET', credentials: 'same-origin' }),
    );
  });

  it('rejects a payload that does not match the schema', async () => {
    mockFetch({ mode: 'LIVE' });

    await expect(apiGet('/status', Status)).rejects.toBeInstanceOf(ApiSchemaError);
  });

  it('raises ApiError with the HTTP status on failure', async () => {
    mockFetch({ detail: 'nope' }, 401);

    await expect(apiGet('/status', Status)).rejects.toMatchObject({ name: 'ApiError', status: 401 });
  });

  it('passes the abort signal through', async () => {
    const fetchSpy = mockFetch({ mode: 'DEMO' });
    const controller = new AbortController();

    await apiGet('/status', Status, { signal: controller.signal });
    expect(fetchSpy.mock.calls[0]?.[1]).toMatchObject({ signal: controller.signal });
  });

  it('is an Error subclass', () => {
    expect(new ApiError(500, 'x')).toBeInstanceOf(Error);
  });
});
