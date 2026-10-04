import { useQuery } from '@tanstack/react-query';
import { type ReactNode, useMemo, useState } from 'react';

import { apiGet } from '@/api/client';

import { EngineContext, type EngineContextValue } from './context';
import { ENGINES_QUERY_KEY, EngineListSchema, FEED_QUERY_KEY, FeedSchema } from './schemas';
import { activeOwnEngines, loadEngineChoice, saveEngineChoice, selectEngine } from './selection';

export function EngineProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<string | null>(loadEngineChoice);
  const feed = useQuery({
    queryKey: FEED_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/me/feed', FeedSchema, { signal }),
  });
  const engines = useQuery({
    queryKey: ENGINES_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/engines', EngineListSchema, { signal }),
  });

  const value = useMemo<EngineContextValue>(() => {
    const select = (engineId: string) => {
      saveEngineChoice(engineId);
      setStored(engineId);
    };
    if (feed.isError) return { state: 'error', engineId: null, own: false, engines: [], select };
    if (feed.data === undefined) return { state: 'loading', engineId: null, own: false, engines: [], select };
    // Without the engine list (still loading or failed) the feed's engine is shown and no picker.
    const own = activeOwnEngines(engines.data?.items ?? []);
    return { state: 'ready', ...selectEngine(feed.data, own, stored), engines: own, select };
  }, [feed.isError, feed.data, engines.data, stored]);

  return <EngineContext value={value}>{children}</EngineContext>;
}
