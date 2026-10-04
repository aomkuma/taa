import { useEffect, useState } from 'react';

import { useAuthState } from '@/auth/hooks';

/** The device time, re-rendering every *intervalMs*. */
export function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, intervalMs);
    return () => {
      window.clearInterval(timer);
    };
  }, [intervalMs]);
  return now;
}

/** The server's time (device time + the offset measured when the session was read). */
export function useServerNow(intervalMs: number): number {
  const now = useNow(intervalMs);
  const { data } = useAuthState();
  return now + (data?.status === 'signed_in' ? data.clockOffsetMs : 0);
}
