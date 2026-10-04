import { useQuery } from '@tanstack/react-query';
import { createContext, useContext } from 'react';

import { apiGet } from '@/api/client';

import { type EngineStatus, EngineStatusSchema, type EngineSummary, engineStatusKey } from './schemas';

export interface EngineContextValue {
  /** `loading` until `/me/feed` answers; `error` when it cannot be read (nothing engine-specific is shown). */
  state: 'loading' | 'error' | 'ready';
  engineId: string | null;
  own: boolean;
  /** The user's ACTIVE engines; the picker appears when there are several. */
  engines: EngineSummary[];
  select: (engineId: string) => void;
}

export const EngineContext = createContext<EngineContextValue | null>(null);

export function useEngine(): EngineContextValue {
  const value = useContext(EngineContext);
  if (value === null) throw new Error('useEngine() needs an <EngineProvider>');
  return value;
}

/** `GET /engines/{id}/status` of the user's own engine; the live stream keeps its heartbeat current. */
export function useEngineStatus() {
  const { engineId, own } = useEngine();
  return useQuery<EngineStatus>({
    queryKey: engineStatusKey(engineId ?? ''),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId ?? '')}/status`, EngineStatusSchema, { signal }),
    enabled: engineId !== null && own,
  });
}
