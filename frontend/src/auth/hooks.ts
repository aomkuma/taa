import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { lastActivityAt, onUnauthenticated } from '@/api/client';

import { AUTH_QUERY_KEY, endSession, fetchAuthState, sessionDeadline } from './session';

/** How often the idle deadline is checked; also catches up after the device sleeps. */
export const EXPIRY_CHECK_MS = 10_000;

export function useAuthState() {
  return useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: ({ signal }) => fetchAuthState(signal),
    // GET /auth/session refreshes the server's idle timer, so it must not run on its own (focus, intervals):
    // only real requests should keep a session alive.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

/**
 * Ends the session in the app when the server reports it gone (any 401 `unauthenticated`) or when the idle or
 * absolute deadline passes without requests. The server enforces the same limits; this only stops showing data
 * from a session that no longer exists.
 */
export function useSessionExpiry(): void {
  const queryClient = useQueryClient();
  const { data } = useAuthState();
  const signedIn = data?.status === 'signed_in' ? data : null;

  useEffect(
    () =>
      onUnauthenticated(() => {
        endSession(queryClient, 'expired');
      }),
    [queryClient],
  );

  useEffect(() => {
    if (!signedIn) return;
    const { session, clockOffsetMs } = signedIn;
    const check = () => {
      if (Date.now() >= sessionDeadline(session, lastActivityAt(), clockOffsetMs)) {
        endSession(queryClient, 'expired');
      }
    };
    check();
    const timer = window.setInterval(check, EXPIRY_CHECK_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [queryClient, signedIn]);
}
