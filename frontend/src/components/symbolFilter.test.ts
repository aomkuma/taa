import { filterSymbols } from './symbolFilter';

describe('filterSymbols', () => {
  const options = [
    { symbol: 'EURUSD' },
    { symbol: 'USDJPY', featured: true },
    { symbol: 'XAUUSD', featured: true },
    { symbol: 'AUDUSD' },
  ];
  const names = (q: string) => filterSymbols(options, q).map((o) => o.symbol);

  it('lists featured symbols first, each group alphabetical', () => {
    expect(names('')).toEqual(['USDJPY', 'XAUUSD', 'AUDUSD', 'EURUSD']);
  });

  it('matches case-insensitively, prefix matches before substring matches', () => {
    expect(names('usd')).toEqual(['USDJPY', 'XAUUSD', 'AUDUSD', 'EURUSD']);
    expect(names('au')).toEqual(['AUDUSD', 'XAUUSD']);
    expect(names(' xau ')).toEqual(['XAUUSD']);
    expect(names('btc')).toEqual([]);
  });
});
