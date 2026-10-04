/**
 * Client of the engine's live stream, `GET /api/v1/engines/{id}/stream` (PLAN §A14 "TAA-804 decisions").
 *
 * - The server opens with `ready {cursor, resumed}` or `reset {cursor}`. `resumed: false` (a fresh start) and
 *   `reset` (the cursor is older than the kept events) mean events were missed: `onResync` tells the app to
 *   reload its pages through REST.
 * - Then one event per change, `event: <topic>`, data `{seq, type, key, at, item}`. A message that fails its
 *   schema is dropped and treated like a reset, so the pages reload from REST instead of showing a guess.
 * - The browser's EventSource reconnects by itself after a dropped connection and after the server's 10-minute
 *   close, sending `Last-Event-ID`. A refused request (429, 401, 5xx) closes it for good, so this client
 *   reopens it with `?cursor=` after a growing delay (3 s doubling to 60 s).
 * - `end {reason}` (the web session ended) stops the stream; the app's next request signs it out.
 *
 * The client is framework-free: `LiveProvider` binds it to React and the query cache.
 */
import { z } from 'zod';

export const TOPICS = ['status', 'quotes', 'positions', 'notifications', 'decisions'] as const;
export type Topic = (typeof TOPICS)[number];

export const RECONNECT_MIN_MS = 3_000;
export const RECONNECT_MAX_MS = 60_000;

/** `connecting`: first attempt; `live`: events flow; `reconnecting`: lost, retrying; `ended`: session over. */
export type StreamState = 'connecting' | 'live' | 'reconnecting' | 'ended';

const ReadySchema = z.object({ cursor: z.number().int().nonnegative(), resumed: z.boolean() });
const ResetSchema = z.object({ cursor: z.number().int().nonnegative() });
const EventSchema = z.object({
  seq: z.number().int().nonnegative(),
  type: z.string(),
  key: z.string(),
  at: z.iso.datetime({ offset: true }),
  item: z.unknown(),
});

export interface StreamEvent extends z.infer<typeof EventSchema> {
  topic: Topic;
}

export type ResyncReason = 'fresh' | 'reset' | 'invalid';

/** The subset of `EventSource` the client uses, so tests can drive it. */
export interface EventSourceLike {
  readonly readyState: number;
  onerror: ((this: EventSourceLike, event: Event) => unknown) | null;
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void;
  close(): void;
}

export type EventSourceFactory = (url: string) => EventSourceLike;

const CLOSED = 2;

export interface LiveStreamOptions {
  /** Stream URL without a query string. */
  url: string;
  onEvent: (event: StreamEvent) => void;
  onResync: (reason: ResyncReason) => void;
  onState: (state: StreamState) => void;
  createEventSource?: EventSourceFactory;
}

const browserEventSource: EventSourceFactory = (url) =>
  new EventSource(url, { withCredentials: true }) as unknown as EventSourceLike;

function parseJson(data: string): unknown {
  try {
    return JSON.parse(data) as unknown;
  } catch {
    return undefined;
  }
}

export class LiveStream {
  private readonly options: LiveStreamOptions;
  private source: EventSourceLike | null = null;
  private cursor: number | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryDelay = RECONNECT_MIN_MS;
  private wasLive = false;
  private stopped = false;
  private state: StreamState | null = null;

  constructor(options: LiveStreamOptions) {
    this.options = options;
  }

  start(): void {
    this.stopped = false;
    this.open();
  }

  /** Closes the stream for good (the page unmounts or the engine changes). */
  stop(): void {
    this.stopped = true;
    this.clearRetry();
    this.closeSource();
  }

  /** Reconnects at once, e.g. when the device comes back online; a live or ended stream is left alone. */
  retryNow(): void {
    if (this.stopped || this.state === 'live' || this.state === 'ended') return;
    this.clearRetry();
    this.retryDelay = RECONNECT_MIN_MS;
    this.open();
  }

  private open(): void {
    this.closeSource();
    this.setState(this.wasLive ? 'reconnecting' : 'connecting');
    const url = this.cursor === null ? this.options.url : `${this.options.url}?cursor=${String(this.cursor)}`;
    const source = (this.options.createEventSource ?? browserEventSource)(url);
    this.source = source;
    source.addEventListener('ready', (event) => {
      const data = ReadySchema.safeParse(parseJson(event.data));
      if (!data.success) {
        this.invalid();
        return;
      }
      this.cursor = data.data.cursor;
      this.connected();
      if (!data.data.resumed) this.options.onResync('fresh');
    });
    source.addEventListener('reset', (event) => {
      const data = ResetSchema.safeParse(parseJson(event.data));
      if (!data.success) {
        this.invalid();
        return;
      }
      this.cursor = data.data.cursor;
      this.connected();
      this.options.onResync('reset');
    });
    for (const topic of TOPICS) {
      source.addEventListener(topic, (event) => {
        const data = EventSchema.safeParse(parseJson(event.data));
        if (!data.success) {
          this.invalid();
          return;
        }
        this.cursor = data.data.seq;
        this.options.onEvent({ ...data.data, topic });
      });
    }
    source.addEventListener('end', () => {
      this.stop();
      this.setState('ended');
    });
    source.onerror = () => {
      if (this.stopped || this.source !== source) return;
      if (source.readyState === CLOSED) {
        // Refused (429, 401, 5xx) or unreachable: the browser gives up, so retry later with the last cursor.
        this.closeSource();
        this.scheduleRetry();
      }
      this.setState(this.wasLive ? 'reconnecting' : 'connecting');
    };
  }

  private connected(): void {
    this.wasLive = true;
    this.retryDelay = RECONNECT_MIN_MS;
    this.setState('live');
  }

  private invalid(): void {
    // The cursor may have moved past events this client could not read: start over from the head.
    this.cursor = null;
    this.options.onResync('invalid');
  }

  private scheduleRetry(): void {
    this.clearRetry();
    const delay = this.retryDelay;
    this.retryDelay = Math.min(this.retryDelay * 2, RECONNECT_MAX_MS);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      if (!this.stopped) this.open();
    }, delay);
  }

  private clearRetry(): void {
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.retryTimer = null;
  }

  private closeSource(): void {
    this.source?.close();
    this.source = null;
  }

  private setState(state: StreamState): void {
    if (state === this.state) return;
    this.state = state;
    this.options.onState(state);
  }
}
