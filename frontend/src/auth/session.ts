/**
 * The signed-in state of this browser (PLAN §A14: server-side sessions, 30 min idle, 12 h absolute).
 *
 * The cookie is HttpOnly, so the app learns about its session only from `GET /auth/session` and the login
 * response. The query cache holds an `AuthState` under `AUTH_QUERY_KEY`; signing out, an expired session and a
 * 401 `unauthenticated` all move it to `signed_out` with a reason the login page can show.
 */
import type { QueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { ApiError, apiGet, apiPost, apiPostEmpty, setCsrfToken } from '@/api/client';

const IsoDateTime = z.iso.datetime({ offset: true });

export const SessionSchema = z.object({
  user: z.object({
    id: z.string(),
    username: z.string(),
    role: z.string(),
    locale: z.string(),
    timezone: z.string(),
  }),
  csrf_token: z.string().min(1),
  expires_at: IsoDateTime,
  absolute_expires_at: IsoDateTime,
  idle_timeout_seconds: z.number().int().positive(),
  step_up_until: IsoDateTime.nullable(),
  server_time: IsoDateTime,
});

export type Session = z.infer<typeof SessionSchema>;

export type SignedOutReason = 'expired' | 'logged_out' | null;

export type AuthState =
  | {
      status: 'signed_in';
      session: Session;
      /** Server clock minus device clock when the session was read; limits are measured on the server clock. */
      clockOffsetMs: number;
    }
  | { status: 'signed_out'; reason: SignedOutReason };

export const AUTH_QUERY_KEY = ['auth', 'session'] as const;

export interface Credentials {
  username: string;
  password: string;
  code: string;
}

export function signedIn(session: Session, receivedAt: number = Date.now()): AuthState {
  setCsrfToken(session.csrf_token);
  return { status: 'signed_in', session, clockOffsetMs: Date.parse(session.server_time) - receivedAt };
}

/** The current state; a 401 means "signed out", any other failure is an error (the guard fails closed). */
export async function fetchAuthState(signal?: AbortSignal): Promise<AuthState> {
  try {
    const session = await apiGet('/auth/session', SessionSchema, {
      notifyUnauthenticated: false,
      ...(signal ? { signal } : {}),
    });
    return signedIn(session);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      setCsrfToken(null);
      return { status: 'signed_out', reason: null };
    }
    throw error;
  }
}

export function login(credentials: Credentials): Promise<Session> {
  return apiPost('/auth/login', credentials, SessionSchema, { notifyUnauthenticated: false });
}

export function logout(): Promise<void> {
  return apiPostEmpty('/auth/logout', undefined, { notifyUnauthenticated: false });
}

/** Moves to signed-out and drops every other cached response, so no data outlives the session. */
export function endSession(queryClient: QueryClient, reason: SignedOutReason): void {
  setCsrfToken(null);
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== AUTH_QUERY_KEY[0] });
  const state: AuthState = { status: 'signed_out', reason };
  queryClient.setQueryData(AUTH_QUERY_KEY, state);
}

/**
 * Device time at which the server will consider the session over: the idle timeout after the last request this
 * client made (every request refreshes the server's idle timer), capped by the absolute limit. The absolute limit
 * is converted with the clock offset, so a wrong device clock does not end or prolong the session.
 */
export function sessionDeadline(session: Session, lastActivity: number, clockOffsetMs: number): number {
  return Math.min(
    lastActivity + session.idle_timeout_seconds * 1000,
    Date.parse(session.absolute_expires_at) - clockOffsetMs,
  );
}

/** A `from` location that is safe to return to after login (same-origin path, not the login page). */
export function safeReturnPath(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/';
  return value.startsWith('/login') ? '/' : value;
}
