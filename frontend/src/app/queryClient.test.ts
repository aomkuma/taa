import { ApiError, ApiSchemaError } from '@/api/client';
import { createQueryClient, shouldRetry } from '@/app/queryClient';

describe('shouldRetry', () => {
  it('never retries schema mismatches or 4xx responses', () => {
    expect(shouldRetry(0, new ApiSchemaError('/x', []))).toBe(false);
    expect(shouldRetry(0, new ApiError(401, 'unauthenticated', 'x'))).toBe(false);
    expect(shouldRetry(0, new ApiError(404, 'not_found', 'x'))).toBe(false);
  });

  it('retries network and 5xx failures a bounded number of times', () => {
    expect(shouldRetry(0, new ApiError(503, 'unavailable', 'x'))).toBe(true);
    expect(shouldRetry(1, new TypeError('Failed to fetch'))).toBe(true);
    expect(shouldRetry(2, new TypeError('Failed to fetch'))).toBe(false);
  });
});

describe('createQueryClient', () => {
  it('does not retry mutations', () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });
});
