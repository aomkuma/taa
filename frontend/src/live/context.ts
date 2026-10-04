import { createContext, useContext, useEffect, useRef } from 'react';

import type { StreamEvent, StreamState, Topic } from './stream';

export type LiveState = StreamState | 'idle';

export interface LiveContextValue {
  /** `idle`: no stream (no engine of the user's own; the market feed has no live stream). */
  state: LiveState;
  /** Device time at which live updates stopped (null while live, idle or before the first connection). */
  pausedSince: number | null;
  subscribe: (topic: Topic, listener: (event: StreamEvent) => void) => () => void;
}

export const LiveContext = createContext<LiveContextValue | null>(null);

export function useLive(): LiveContextValue {
  const value = useContext(LiveContext);
  if (value === null) throw new Error('useLive() needs a <LiveProvider>');
  return value;
}

/** Calls *listener* for every stream event of *topic* (the latest listener; no resubscribe on each render). */
export function useLiveEvents(topic: Topic, listener: (event: StreamEvent) => void): void {
  const { subscribe } = useLive();
  const latest = useRef(listener);
  useEffect(() => {
    latest.current = listener;
  });
  useEffect(
    () =>
      subscribe(topic, (event) => {
        latest.current(event);
      }),
    [subscribe, topic],
  );
}
