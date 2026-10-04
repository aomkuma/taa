/**
 * Minimal JSON client for the FastAPI service (`/api/v1`, same origin).
 *
 * Every response is validated with a zod schema before the UI sees it: a payload that does not match is an error,
 * never "best effort" rendering of unknown data. CSRF headers and session-expiry handling arrive with TAA-902.
 */
import type { z } from 'zod';

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class ApiSchemaError extends Error {
  readonly issues: z.core.$ZodIssue[];

  constructor(path: string, issues: z.core.$ZodIssue[]) {
    super(`Response from ${path} failed validation`);
    this.name = 'ApiSchemaError';
    this.issues = issues;
  }
}

export async function apiGet<S extends z.ZodType>(
  path: string,
  schema: S,
  init: { signal?: AbortSignal } = {},
): Promise<z.output<S>> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    ...(init.signal ? { signal: init.signal } : {}),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with HTTP ${response.status}`);
  }
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ApiSchemaError(path, parsed.error.issues);
  }
  return parsed.data;
}
