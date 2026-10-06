import { ASSET_CLASSES } from '@/i18n/codes';
import samples from '@/test/fixtures/api-samples.json';

import {
  defaultDirection,
  explainParams,
  filterItems,
  isEligible,
  presentClasses,
  requiredEquity,
  sortItems,
  topEligible,
} from './rankingModel';
import { type RankingItem, RankingSchema } from './schemas';

const ranking = RankingSchema.parse((samples as Record<string, unknown>)['engines/ENGINE/ranking']);
const items = ranking.items;
const bySymbol = (symbol: string) => {
  const found = items.find((i) => i.symbol === symbol);
  if (!found) throw new Error(symbol);
  return found;
};
const ALL = { assetClass: null, eligibleOnly: false, search: '' };

describe('ranking model', () => {
  it('keeps the server order for rank and sorts scores high first by default', () => {
    expect(sortItems(items, 'rank', 'asc').map((i) => i.symbol)).toEqual(items.map((i) => i.symbol));
    expect(sortItems(items, 'rank', 'desc')[0]).toBe(items[items.length - 1]);
    const overall = sortItems(items, 'overall', defaultDirection('overall')).map((i) => i.overall);
    expect(overall).toEqual([...overall].sort((a, b) => b - a));
    expect(sortItems(items, 'symbol', 'asc')[0]?.symbol).toBe('AAPL');
    expect(defaultDirection('rank')).toBe('asc');
  });

  it('filters by class, eligibility and name', () => {
    expect(filterItems(items, { ...ALL, assetClass: 'METAL' }).map((i) => i.symbol)).toEqual([
      'XAUUSD',
      'XAGUSD',
    ]);
    expect(filterItems(items, { ...ALL, eligibleOnly: true }).every(isEligible)).toBe(true);
    expect(filterItems(items, { ...ALL, search: ' usd' }).length).toBeGreaterThan(5);
    expect(presentClasses(items, ASSET_CLASSES)).toEqual([
      'FOREX_MAJOR',
      'FOREX_MINOR',
      'METAL',
      'INDEX',
      'ENERGY',
      'CRYPTO',
      'STOCK',
    ]);
  });

  it('hints the equity the minimum lot needs only when G2 fails', () => {
    expect(requiredEquity(bySymbol('XAUUSD'))).toEqual({ value: 1538.004848, currency: 'USD' });
    expect(requiredEquity(bySymbol('EURUSD'))).toBeNull(); // affordable
    expect(requiredEquity(bySymbol('AAPL'))).toBeNull(); // fails G6 (data), not G2
  });

  it('uses the user’s own affordability on the market feed', () => {
    const feed: RankingItem = {
      ...bySymbol('XAUUSD'),
      gates: [],
      metrics: {},
      personal: { eligible: false, currency: 'EUR', affordable: false, required_equity: 2000 },
    };
    expect(isEligible(feed)).toBe(false);
    expect(requiredEquity(feed)).toEqual({ value: 2000, currency: 'EUR' });
    expect(isEligible({ ...feed, eligible: false, personal: { eligible: true, currency: 'EUR' } })).toBe(
      true,
    );
    expect(requiredEquity({ ...feed, personal: { eligible: null, currency: null } })).toBeNull();
  });

  it('passes strings and finite numbers to explanations', () => {
    expect(explainParams({ a: 1, b: 'x', c: null, d: Number.NaN, e: [1] })).toEqual({ a: 1, b: 'x' });
  });

  it('takes the top eligible symbols in rank order', () => {
    expect(topEligible(items, 3).map((i) => i.symbol)).toEqual(['USDJPY', 'AUDUSD', 'EURUSD']);
  });
});
