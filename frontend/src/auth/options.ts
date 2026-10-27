/**
 * What the server asks for when signing in and when confirming a control action.
 *
 * `WEB_REQUIRE_TOTP=false` (a development service only; app/config.py refuses it in production) turns the
 * authenticator code off. The pages must ask rather than assume: a form that insists on six digits the
 * server no longer issues locks the owner out of the kill switch, which is how this hook came to exist.
 *
 * When the question cannot be answered, the answer is "a code is required" - the stricter of the two is
 * the safe default.
 */
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';

import { apiGet } from '@/api/client';

export const AuthOptions = z.object({ totp_required: z.boolean() });

export const AUTH_OPTIONS_KEY = ['auth', 'options'] as const;

export function useTotpRequired(): boolean {
  const options = useQuery({
    queryKey: AUTH_OPTIONS_KEY,
    queryFn: () => apiGet('/auth/options', AuthOptions),
    staleTime: Infinity,
    retry: false,
  });
  return options.data?.totp_required ?? true;
}
