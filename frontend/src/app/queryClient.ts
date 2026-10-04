import { QueryClient } from '@tanstack/react-query';

import { ApiError, ApiSchemaError } from '@/api/client';

/** Client errors and schema mismatches will not fix themselves; only network and 5xx failures are retried. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiSchemaError) return false;
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 5_000 },
      // Mutations are control actions; a silent retry could repeat one.
      mutations: { retry: false },
    },
  });
}
