/** A scriptable EventSource for live-stream tests: `emit` delivers a server event, `fail` an error. */
import type { EventSourceLike } from '@/live/stream';

export class FakeEventSource implements EventSourceLike {
  readyState = 1;
  closed = false;
  onerror: ((this: EventSourceLike, event: Event) => unknown) | null = null;
  private readonly listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();

  constructor(readonly url: string) {}

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {
    this.closed = true;
    this.readyState = 2;
  }

  emit(type: string, data: unknown): void {
    const payload = typeof data === 'string' ? data : JSON.stringify(data);
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: payload }));
    }
  }

  /** An error; `closed: true` is a refused request (the browser gives up), else it retries by itself. */
  fail(closed: boolean): void {
    this.readyState = closed ? 2 : 0;
    this.onerror?.call(this, new Event('error'));
  }
}

/** A factory that records every EventSource it creates. */
export function fakeEventSources() {
  const created: FakeEventSource[] = [];
  const factory = (url: string) => {
    const source = new FakeEventSource(url);
    created.push(source);
    return source;
  };
  const last = (): FakeEventSource => {
    const source = created.at(-1);
    if (!source) throw new Error('no EventSource was created');
    return source;
  };
  return { created, factory, last };
}

export function streamEvent(seq: number, type: string, item: unknown, key = 'k') {
  return { seq, type, key, at: '2026-09-30T10:00:00+00:00', item };
}
