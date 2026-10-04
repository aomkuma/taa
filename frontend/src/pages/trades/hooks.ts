import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

import { engineKey } from '@/engine/schemas';
import { useLiveEvents } from '@/live/context';

/** The trade drawer's ticket lives in the URL (`?trade=`): a trade can be linked and Back closes it. */
export function useTradeDrawer() {
  const [params, setParams] = useSearchParams();
  const raw = params.get('trade');
  const ticket = raw !== null && /^\d+$/.test(raw) ? Number(raw) : null;
  const open = useCallback(
    (t: number) => {
      const next = new URLSearchParams(params);
      next.set('trade', String(t));
      setParams(next);
    },
    [params, setParams],
  );
  const close = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete('trade');
    setParams(next);
  }, [params, setParams]);
  return { ticket, open, close };
}

/** Refetch everything trade-related when positions or intents change on the stream. */
export function useLiveTrades(engineId: string) {
  const queryClient = useQueryClient();
  useLiveEvents('positions', () => {
    for (const part of ['positions', 'intents']) {
      void queryClient.invalidateQueries({ queryKey: [...engineKey(engineId), part] });
    }
  });
}
