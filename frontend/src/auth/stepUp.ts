/**
 * Step-up (PLAN §A14): control actions need an authenticator code confirmed within the last 5 minutes.
 *
 * `POST /auth/step-up {code}` answers `{step_up_until}`; the session cached under `AUTH_QUERY_KEY` is updated so
 * every control dialog knows the step-up is fresh. The window is measured on the server clock (the session's
 * clock offset). A control route that still answers 403 `step_up_required` (the window ran out in between) makes
 * the dialog ask for a code again.
 */
import { type QueryClient, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { z } from 'zod';

import { apiPost } from '@/api/client';
import { useServerNow } from '@/app/useNow';

import { useAuthState } from './hooks';
import { AUTH_QUERY_KEY, type AuthState } from './session';

const StepUpSchema = z.object({ step_up_until: z.iso.datetime({ offset: true }) });

/** Whether *state*'s step-up is still valid at *serverNow* (with a few seconds' margin for the request). */
export function stepUpActive(state: AuthState | undefined, serverNow: number, marginMs = 5_000): boolean {
  if (state?.status !== 'signed_in') return false;
  const until = state.session.step_up_until;
  return until !== null && Date.parse(until) - marginMs > serverNow;
}

function storeStepUp(queryClient: QueryClient, until: string | null): void {
  queryClient.setQueryData<AuthState>(AUTH_QUERY_KEY, (state) =>
    state?.status === 'signed_in' ? { ...state, session: { ...state.session, step_up_until: until } } : state,
  );
}

export function useStepUp() {
  const queryClient = useQueryClient();
  const { data } = useAuthState();
  const serverNow = useServerNow(5_000);
  const verify = useCallback(
    async (code: string) => {
      const { step_up_until } = await apiPost('/auth/step-up', { code }, StepUpSchema);
      storeStepUp(queryClient, step_up_until);
    },
    [queryClient],
  );
  /** The server said the step-up is gone: forget it, so the next attempt asks for a code. */
  const expire = useCallback(() => {
    storeStepUp(queryClient, null);
  }, [queryClient]);
  return { active: stepUpActive(data, serverNow), verify, expire };
}
