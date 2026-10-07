import samples from '@/test/fixtures/api-samples.json';

import { type Trade, TradesPageSchema } from './schemas';
import { botR, CSV_COLUMNS, excursionR, heldMinutes, initialRisk, openR, tradesCsv } from './tradeMath';

const closed = TradesPageSchema.parse(
  (samples as Record<string, unknown>)['engines/ENGINE/trades?limit=2'],
).items;
const open = TradesPageSchema.parse(
  (samples as Record<string, unknown>)['engines/ENGINE/positions?status=OPEN'],
).items[0] as Trade;

describe('trade math', () => {
  it('measures 1R from the initial stop', () => {
    expect(initialRisk(1.1, 1.095)).toBeCloseTo(0.005);
    expect(initialRisk(1.1, null)).toBeNull();
    expect(initialRisk(1.1, 1.1)).toBeNull();
  });

  it('puts an open position in R at its current price, for buys and sells', () => {
    const buy = { ...open, side: 'BUY', entry_price: 1.1, price_current: 1.105 };
    expect(openR(buy, 0.005)).toBeCloseTo(1);
    expect(openR({ ...buy, side: 'SELL' }, 0.005)).toBeCloseTo(-1);
    expect(openR(buy, null)).toBeNull();
    expect(excursionR(0.0025, 0.005)).toBeCloseTo(0.5);
  });

  it('counts the minutes a closed trade was held', () => {
    expect(heldMinutes(closed[0] as Trade)).toBe(30);
    expect(heldMinutes(open)).toBeNull();
  });
});

describe('tradesCsv', () => {
  it('writes a header and one row per trade with raw values', () => {
    const lines = tradesCsv(closed).trimEnd().split('\r\n');
    expect(lines[0]).toBe(CSV_COLUMNS.join(','));
    expect(lines).toHaveLength(closed.length + 1);
    const first = closed[0] as Trade;
    expect(lines[1]?.startsWith(`${String(first.ticket)},${first.symbol},${first.side},`)).toBe(true);
  });

  it('quotes separators and defuses spreadsheet formulas', () => {
    const tricky = { ...(closed[0] as Trade), symbol: 'A,"B"', exit_reason: '=HYPERLINK("x")' };
    const row = tradesCsv([tricky]).split('\r\n')[1] ?? '';
    expect(row).toContain('"A,""B"""');
    expect(row).toContain(`"'=HYPERLINK(""x"")"`);
    expect(tradesCsv([{ ...(closed[0] as Trade), net: -5 }])).toContain(',-5,');
  });
});

describe('botR', () => {
  const base = {
    ticket: 1,
    symbol: 'EURUSD',
    volume: 0.1,
    sl: null,
    tp: null,
    profit: 0,
    swap: 0,
    opened_at: '2026-10-07T08:00:00+00:00',
    magic: 7310002,
    strategy: null,
    risk_to_stop: null,
  };
  it('measures R from the first stop on either side', () => {
    expect(
      botR({ ...base, side: 'BUY', price_open: 1.1, price_current: 1.105, sl_initial: 1.095 }),
    ).toBeCloseTo(1);
    expect(
      botR({ ...base, side: 'SELL', price_open: 1.1, price_current: 1.105, sl_initial: 1.105 }),
    ).toBeCloseTo(-1);
    expect(botR({ ...base, side: 'BUY', price_open: 1.1, price_current: 1.2, sl_initial: null })).toBeNull();
  });
});
