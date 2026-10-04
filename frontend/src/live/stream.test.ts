import { fakeEventSources, streamEvent } from '@/test/eventSource';

import { LiveStream, RECONNECT_MAX_MS, RECONNECT_MIN_MS, type StreamEvent, type StreamState } from './stream';

const URL = '/api/v1/engines/e1/stream';

function setup() {
  const sources = fakeEventSources();
  const states: StreamState[] = [];
  const events: StreamEvent[] = [];
  const resyncs: string[] = [];
  const stream = new LiveStream({
    url: URL,
    createEventSource: sources.factory,
    onEvent: (event) => events.push(event),
    onResync: (reason) => resyncs.push(reason),
    onState: (state) => states.push(state),
  });
  stream.start();
  return { stream, sources, states, events, resyncs };
}

describe('LiveStream', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('asks for a resync on a fresh start and goes live', () => {
    const { sources, states, resyncs } = setup();
    expect(sources.last().url).toBe(URL);
    expect(states).toEqual(['connecting']);
    sources.last().emit('ready', { cursor: 7, resumed: false });
    expect(states).toEqual(['connecting', 'live']);
    expect(resyncs).toEqual(['fresh']);
  });

  it('does not resync when the server resumed the cursor', () => {
    const { sources, resyncs } = setup();
    sources.last().emit('ready', { cursor: 7, resumed: true });
    expect(resyncs).toEqual([]);
  });

  it('delivers topic events with their topic and resyncs on reset', () => {
    const { sources, events, resyncs } = setup();
    const source = sources.last();
    source.emit('ready', { cursor: 1, resumed: true });
    source.emit('positions', streamEvent(2, 'paper_position', { ticket: 10 }, '10'));
    expect(events).toEqual([expect.objectContaining({ topic: 'positions', seq: 2, item: { ticket: 10 } })]);
    source.emit('reset', { cursor: 90 });
    expect(resyncs).toEqual(['reset']);
  });

  it('drops a message that fails its schema and resyncs instead', () => {
    const { sources, events, resyncs } = setup();
    const source = sources.last();
    source.emit('ready', { cursor: 1, resumed: true });
    source.emit('status', { seq: 'two' });
    source.emit('status', 'not json');
    expect(events).toEqual([]);
    expect(resyncs).toEqual(['invalid', 'invalid']);
  });

  it('leaves a dropped connection to the browser', () => {
    const { sources, states } = setup();
    sources.last().emit('ready', { cursor: 1, resumed: true });
    sources.last().fail(false);
    expect(states.at(-1)).toBe('reconnecting');
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sources.created).toHaveLength(1);
  });

  it('reopens a refused stream from the last cursor with a growing delay', () => {
    const { sources, states } = setup();
    sources.last().emit('ready', { cursor: 1, resumed: true });
    sources.last().emit('quotes', streamEvent(5, 'quotes', {}));
    sources.last().fail(true);
    expect(sources.created[0]?.closed).toBe(true);
    expect(states.at(-1)).toBe('reconnecting');
    vi.advanceTimersByTime(RECONNECT_MIN_MS - 1);
    expect(sources.created).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sources.last().url).toBe(`${URL}?cursor=5`);
    sources.last().fail(true);
    vi.advanceTimersByTime(RECONNECT_MIN_MS);
    expect(sources.created).toHaveLength(2); // the delay doubled
    vi.advanceTimersByTime(RECONNECT_MIN_MS);
    expect(sources.created).toHaveLength(3);
    sources.last().emit('ready', { cursor: 5, resumed: true }); // back: the delay starts over
    expect(states.at(-1)).toBe('live');
    sources.last().fail(true);
    vi.advanceTimersByTime(RECONNECT_MIN_MS);
    expect(sources.created).toHaveLength(4);
  });

  it('caps the delay', () => {
    const { sources } = setup();
    for (let i = 0; i < 8; i++) {
      sources.last().fail(true);
      vi.advanceTimersByTime(RECONNECT_MAX_MS);
    }
    const before = sources.created.length;
    sources.last().fail(true);
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sources.created).toHaveLength(before + 1);
  });

  it('retries at once when asked, e.g. back online', () => {
    const { stream, sources } = setup();
    sources.last().fail(true);
    stream.retryNow();
    expect(sources.created).toHaveLength(2);
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sources.created).toHaveLength(2); // the scheduled retry was cancelled
  });

  it('stops for good when the session ended', () => {
    const { stream, sources, states } = setup();
    sources.last().emit('ready', { cursor: 1, resumed: true });
    sources.last().emit('end', { reason: 'session_ended' });
    expect(states.at(-1)).toBe('ended');
    expect(sources.last().closed).toBe(true);
    stream.retryNow();
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sources.created).toHaveLength(1);
  });

  it('stop closes the source and cancels a pending retry', () => {
    const { stream, sources } = setup();
    sources.last().fail(true);
    stream.stop();
    vi.advanceTimersByTime(RECONNECT_MAX_MS);
    expect(sources.created).toHaveLength(1);
    expect(sources.last().closed).toBe(true);
  });
});
