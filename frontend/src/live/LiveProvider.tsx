import { useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { API_BASE } from '@/api/client';
import { useEngine } from '@/engine/context';
import { type EngineStatus, engineKey, engineStatusKey, HeartbeatSchema } from '@/engine/schemas';

import { LiveContext, type LiveContextValue, type LiveState } from './context';
import { type EventSourceFactory, LiveStream, type StreamEvent, type Topic } from './stream';

interface Props {
  children: ReactNode;
  /** Tests inject a fake EventSource. */
  createEventSource?: EventSourceFactory;
}

/**
 * Runs the live stream of the user's own engine and feeds the query cache: a resync refetches every query under
 * `['engine', id]`, a heartbeat updates the cached status in place, other status changes refetch it. Pages
 * subscribe to topics with `useLiveEvents`.
 */
export function LiveProvider({ children, createEventSource }: Props) {
  const queryClient = useQueryClient();
  const { engineId, own } = useEngine();
  const streamed = own ? engineId : null;
  // Tagged with the engine it describes, so a change of engine reads as idle until its own stream reports.
  const [status, setStatus] = useState<{
    engineId: string | null;
    state: LiveState;
    pausedSince: number | null;
  }>({ engineId: null, state: 'idle', pausedSince: null });
  const listeners = useRef(new Map<Topic, Set<(event: StreamEvent) => void>>());

  useEffect(() => {
    if (streamed === null) return undefined;
    const statusKey = engineStatusKey(streamed);
    const stream = new LiveStream({
      url: `${API_BASE}/engines/${encodeURIComponent(streamed)}/stream`,
      ...(createEventSource ? { createEventSource } : {}),
      onState: (state) => {
        setStatus((previous) => ({
          engineId: streamed,
          state,
          pausedSince:
            state === 'live' || state === 'connecting'
              ? null
              : ((previous.engineId === streamed ? previous.pausedSince : null) ?? Date.now()),
        }));
        // The server ended the stream because the session is over: the refetch gets the 401 that signs out.
        if (state === 'ended') void queryClient.invalidateQueries({ queryKey: statusKey });
      },
      onResync: () => {
        void queryClient.invalidateQueries({ queryKey: engineKey(streamed) });
      },
      onEvent: (event) => {
        if (event.topic === 'status') {
          const heartbeat = event.type === 'heartbeat' ? HeartbeatSchema.safeParse(event.item) : null;
          if (heartbeat?.success) {
            queryClient.setQueryData<EngineStatus>(statusKey, (old) =>
              old === undefined ? old : { ...old, heartbeat: heartbeat.data },
            );
          } else {
            void queryClient.invalidateQueries({ queryKey: statusKey });
          }
        }
        for (const listener of listeners.current.get(event.topic) ?? []) listener(event);
      },
    });
    stream.start();
    const online = () => {
      stream.retryNow();
    };
    window.addEventListener('online', online);
    return () => {
      window.removeEventListener('online', online);
      stream.stop();
    };
  }, [streamed, queryClient, createEventSource]);

  const subscribe = useCallback((topic: Topic, listener: (event: StreamEvent) => void) => {
    const set = listeners.current.get(topic) ?? new Set();
    set.add(listener);
    listeners.current.set(topic, set);
    return () => {
      set.delete(listener);
    };
  }, []);

  const current = streamed !== null && status.engineId === streamed;
  const value = useMemo<LiveContextValue>(
    () => ({
      state: current ? status.state : 'idle',
      pausedSince: current ? status.pausedSince : null,
      subscribe,
    }),
    [current, status, subscribe],
  );
  return <LiveContext value={value}>{children}</LiveContext>;
}
