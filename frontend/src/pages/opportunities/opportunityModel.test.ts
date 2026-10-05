import samples from '@/test/fixtures/api-samples.json';

import {
  activeCount,
  chartLink,
  countdown,
  evidenceByRelation,
  reasonKind,
  sortForCards,
  splitContributions,
  supportingFamilies,
  trackRecord,
  windowState,
} from './opportunityModel';
import {
  type Opportunity,
  OpportunitiesPageSchema,
  OpportunityDetailSchema,
  ScoreboardSchema,
} from './schemas';

const recorded = samples as Record<string, unknown>;
const OPP = 'ebf613a7581b7648eaca8328cdccb599d0751b14ec0d0d451901e2799917e5de';
const list = OpportunitiesPageSchema.parse(recorded['engines/ENGINE/opportunities?limit=50']).items;
const detail = OpportunityDetailSchema.parse(recorded[`engines/ENGINE/opportunities/${OPP}`]);
const scoreboard = ScoreboardSchema.parse(recorded['engines/ENGINE/theory-scoreboard']);

const at = (iso: string) => Date.parse(iso);
const window = {
  status: 'ACTIVE',
  created_at: '2026-09-30T10:00:00+00:00',
  valid_until: '2026-09-30T10:30:00+00:00',
};

describe('opportunity windows', () => {
  it('counts down, turns EXPIRING in the last 20% and EXPIRED at the end', () => {
    expect(windowState(window, at('2026-09-30T10:10:00Z'))).toEqual({
      status: 'ACTIVE',
      remainingMs: 20 * 60_000,
    });
    expect(windowState(window, at('2026-09-30T10:25:00Z')).status).toBe('EXPIRING');
    expect(windowState(window, at('2026-09-30T10:31:00Z'))).toEqual({ status: 'EXPIRED', remainingMs: 0 });
    expect(windowState({ ...window, status: 'INVALIDATED' }, at('2026-09-30T10:10:00Z'))).toEqual({
      status: 'INVALIDATED',
      remainingMs: null,
    });
    expect(windowState({ ...window, valid_until: null }, 0).remainingMs).toBeNull();
  });

  it('formats the countdown', () => {
    expect(countdown(65_000)).toBe('01:05');
    expect(countdown(3_725_000)).toBe('1:02:05');
    expect(countdown(-5)).toBe('00:00');
  });

  it('names the reason kind of terminal statuses', () => {
    expect(reasonKind('EXPIRED')).toBe('windowReason');
    expect(reasonKind('INVALIDATED')).toBe('invalidReason');
    expect(reasonKind('ACTIVE')).toBeNull();
  });

  it('puts open cards first (soonest end first) and counts the ACTIVE ones for the badge', () => {
    const shift = (o: Opportunity, minutes: number, status = o.status): Opportunity => ({
      ...o,
      status,
      valid_until: new Date(at('2026-09-30T10:00:00Z') + minutes * 60_000).toISOString(),
    });
    const [eur, xau] = list as [Opportunity, Opportunity];
    const now = at('2026-09-30T10:05:00Z');
    const items = [shift(eur, 40), shift(xau, 20), shift(eur, 1, 'EXPIRED')];
    expect(sortForCards(items, now).map((o) => o.valid_until)).toEqual([
      items[1]?.valid_until,
      items[0]?.valid_until,
      items[2]?.valid_until,
    ]);
    expect(activeCount(items, now)).toBe(1); // EURUSD is ACTIVE, XAUUSD a CANDIDATE
  });
});

describe('where the % comes from', () => {
  it('splits contributions into supporting and conflicting, largest first', () => {
    if (!detail.probability.available || !detail.probability.contributions) throw new Error('sample');
    const { supporting, conflicting } = splitContributions(detail.probability.contributions);
    expect(supporting.length).toBeGreaterThan(0);
    expect(supporting.every((c) => c.points > 0) && conflicting.every((c) => c.points < 0)).toBe(true);
    expect(supporting[0]?.detector).toBe('fib.retracement');
  });

  it('finds a theory’s record for the opportunity’s asset class and timeframe', () => {
    expect(trackRecord(scoreboard, 'ev:FIBONACCI:fib.retracement', 'FOREX_MAJOR', 'M15')).toEqual({
      n: 3,
      hitRate: 100,
      expectancyR: expect.closeTo(1.9067, 3) as number,
    });
    expect(trackRecord(scoreboard, 'ev:FIBONACCI:fib.retracement', 'METAL', 'M15')).toMatchObject({ n: 1 });
    expect(trackRecord(scoreboard, 'ev:FIBONACCI:fib.retracement', 'INDEX', 'M15')).toBeNull();
    expect(trackRecord(undefined, 'x', 'y', 'z')).toBeNull();
  });

  it('groups the evidence by relation and counts the supporting families', () => {
    const groups = evidenceByRelation(detail.evidence);
    expect(groups.SUPPORTS).toHaveLength(7);
    expect(groups.CONFLICTS).toHaveLength(4);
    expect(groups.NEUTRAL).toHaveLength(1);
    expect(supportingFamilies(detail.evidence)).toBeGreaterThan(1);
  });

  it('links to the chart with the opportunity on a timeframe', () => {
    expect(chartLink('EURUSD', 'o1', 'H1')).toBe('/charts?symbol=EURUSD&opportunity=o1&tf=H1');
  });
});
