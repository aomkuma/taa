import { engineKey } from '@/engine/schemas';

import { NOTIFICATIONS_QUERY_KEY } from './schemas';

export const RECENT = 5;

/** Query keys of the dashboard; engine data lives under `engineKey(id)`, so a stream resync refetches it. */
export const dashboardKeys = {
  positions: (engineId: string) => [...engineKey(engineId), 'positions', 'open', RECENT] as const,
  decisions: (engineId: string) => [...engineKey(engineId), 'decisions', 'recent', RECENT] as const,
  breakers: (engineId: string) => [...engineKey(engineId), 'breakers'] as const,
  notifications: [...NOTIFICATIONS_QUERY_KEY, 'recent', RECENT] as const,
};
