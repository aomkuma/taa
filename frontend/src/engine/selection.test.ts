import type { EngineSummary } from './schemas';
import { activeOwnEngines, loadEngineChoice, saveEngineChoice, selectEngine } from './selection';

const engine = (engine_id: string, status = 'ACTIVE'): EngineSummary => ({
  engine_id,
  label: engine_id,
  status,
  last_seen_at: null,
});

describe('engine selection', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('keeps only ACTIVE engines for the picker', () => {
    expect(activeOwnEngines([engine('a'), engine('b', 'REVOKED')]).map((e) => e.engine_id)).toEqual(['a']);
  });

  it("uses a remembered choice only when it is one of the user's active engines", () => {
    const own = [engine('a'), engine('b')];
    const feed = { engine_id: 'a', own: true };
    expect(selectEngine(feed, own, 'b')).toEqual({ engineId: 'b', own: true });
    expect(selectEngine(feed, own, 'gone')).toEqual({ engineId: 'a', own: true });
    expect(selectEngine(feed, own, null)).toEqual({ engineId: 'a', own: true });
  });

  it('falls back to the market feed for a subscriber', () => {
    expect(selectEngine({ engine_id: 'owner', own: false }, [], 'owner')).toEqual({
      engineId: 'owner',
      own: false,
    });
    expect(selectEngine({ engine_id: null, own: false }, [], null)).toEqual({ engineId: null, own: false });
  });

  it('remembers the choice per device and survives blocked storage', () => {
    saveEngineChoice('b');
    expect(loadEngineChoice()).toBe('b');
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(loadEngineChoice()).toBeNull();
    spy.mockRestore();
  });
});
