/** Matching for the symbol picker (SymbolCombobox). */

export interface SymbolOption {
  symbol: string;
  /** Shown first and marked: e.g. the symbol has chart data. */
  featured?: boolean;
}

/** Rendering hundreds of broker symbols at once is slow on phones; typing narrows the list instead. */
export const MAX_SHOWN = 100;

/** Featured first, then prefix matches before substring matches, each alphabetical. */
export function filterSymbols(options: readonly SymbolOption[], query: string): SymbolOption[] {
  const q = query.trim().toUpperCase();
  const rank = (o: SymbolOption) => {
    const name = o.symbol.toUpperCase();
    const match = q === '' || name.startsWith(q) ? 0 : name.includes(q) ? 1 : 2;
    return match * 2 + (o.featured ? 0 : 1);
  };
  return options
    .map((o) => ({ o, r: rank(o) }))
    .filter(({ r }) => r < 4)
    .sort((a, b) => a.r - b.r || a.o.symbol.localeCompare(b.o.symbol))
    .map(({ o }) => o);
}
