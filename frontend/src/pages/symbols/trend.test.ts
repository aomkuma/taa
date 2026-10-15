import { summarize } from './trend';

const f = (states: Record<string, string>) =>
  Object.fromEntries(Object.entries(states).map(([tf, state]) => [tf, { state: state as 'UP' }]));

describe('trend summary per setup group', () => {
  it('M15 setups need H4 and H1 to agree', () => {
    expect(summarize(f({ H4: 'UP', H1: 'UP' }), 'm15')).toBe('UP');
    expect(summarize(f({ H4: 'DOWN', H1: 'DOWN', M15: 'UP' }), 'm15')).toBe('DOWN');
    expect(summarize(f({ H4: 'RANGE', H1: 'RANGE' }), 'm15')).toBe('SIDEWAYS');
    expect(summarize(f({ H4: 'UP', H1: 'DOWN' }), 'm15')).toBe('UNCLEAR');
    expect(summarize(f({ H4: 'TRANSITION', H1: 'TRANSITION' }), 'm15')).toBe('UNCLEAR');
    expect(summarize(f({ H1: 'UP' }), 'm15')).toBe('NONE');
  });

  it('the M1 scalp reads H1 and M15', () => {
    expect(summarize(f({ H4: 'DOWN', H1: 'UP', M15: 'UP' }), 'm1')).toBe('UP');
    expect(summarize(f({ H1: 'UP', M15: 'RANGE' }), 'm1')).toBe('UNCLEAR');
    expect(summarize(f({ H4: 'UP', H1: 'UP' }), 'm1')).toBe('NONE');
  });
});
