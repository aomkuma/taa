/**
 * JSON client for the FastAPI service (`/api/v1`, same origin, session cookie).
 *
 * - Every response is validated with a zod schema; a payload that does not match is an error, never rendered.
 * - Mutations carry the session's CSRF token (`X-CSRF-Token`), taken from the login or session response.
 * - A 401 with code `unauthenticated` means the server ended the session: the session listeners are told, so the
 *   app can return to the login page. Other 401s (a failed login) are ordinary errors.
 * - Every request counts as activity for the client-side idle timer (`lastActivityAt`).
 */
import { z } from 'zod';

export const API_BASE = '/api/v1';
export const CSRF_HEADER = 'X-CSRF-Token';

const ErrorBody = z.object({
  error: z.looseObject({
    code: z.string(),
    message: z.string(),
    retry_after: z.number().optional(),
  }),
});

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryAfter: number | null;

  constructor(status: number, code: string, message: string, retryAfter: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
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

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

const unauthenticatedListeners = new Set<() => void>();

/** Called whenever the server reports that the session has ended. Returns an unsubscribe function. */
export function onUnauthenticated(listener: () => void): () => void {
  unauthenticatedListeners.add(listener);
  return () => {
    unauthenticatedListeners.delete(listener);
  };
}

let lastActivity = Date.now();

export function lastActivityAt(): number {
  return lastActivity;
}

export interface RequestOptions {
  signal?: AbortSignal;
  /** False for requests that probe the session themselves (GET /auth/session, login). */
  notifyUnauthenticated?: boolean;
}

async function toApiError(response: Response, path: string): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (a proxy error page, for example): fall back to the status.
  }
  const parsed = ErrorBody.safeParse(body);
  if (parsed.success) {
    const { code, message, retry_after: retryAfter } = parsed.data.error;
    return new ApiError(response.status, code, message, retryAfter ?? null);
  }
  return new ApiError(response.status, `http_${String(response.status)}`, `${path} failed`);
}

async function request(
  method: 'GET' | 'POST' | 'PUT',
  path: string,
  body: unknown,
  options: RequestOptions,
): Promise<unknown> {
  lastActivity = Date.now();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && csrfToken) headers[CSRF_HEADER] = csrfToken;
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'same-origin',
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    ...(options.signal ? { signal: options.signal } : {}),
  });
  if (!response.ok) {
    const error = await toApiError(response, path);
    if (error.status === 401 && error.code === 'unauthenticated' && options.notifyUnauthenticated !== false) {
      for (const listener of unauthenticatedListeners) listener();
    }
    throw error;
  }
  return response.status === 204 ? undefined : response.json();
}

function validate<S extends z.ZodType>(path: string, schema: S, data: unknown): z.output<S> {
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new ApiSchemaError(path, parsed.error.issues);
  return parsed.data;
}

export async function apiGet<S extends z.ZodType>(
  path: string,
  schema: S,
  options: RequestOptions = {},
): Promise<z.output<S>> {
  return validate(path, schema, await request('GET', path, undefined, options));
}

export async function apiPost<S extends z.ZodType>(
  path: string,
  body: unknown,
  schema: S,
  options: RequestOptions = {},
): Promise<z.output<S>> {
  return validate(path, schema, await request('POST', path, body, options));
}

export async function apiPut<S extends z.ZodType>(
  path: string,
  body: unknown,
  schema: S,
  options: RequestOptions = {},
): Promise<z.output<S>> {
  return validate(path, schema, await request('PUT', path, body, options));
}

/** POST that answers 204 No Content. */
export async function apiPostEmpty(
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<void> {
  await request('POST', path, body, options);
}
