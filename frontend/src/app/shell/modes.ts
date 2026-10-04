/** Trading modes (`TradingMode` in app/core/enums.py; parity test in modes.test.ts). */
export const TRADING_MODES = ['BACKTEST', 'PAPER', 'DEMO', 'LIVE'] as const;
export type TradingMode = (typeof TRADING_MODES)[number];

export function isTradingMode(value: unknown): value is TradingMode {
  return typeof value === 'string' && (TRADING_MODES as readonly string[]).includes(value);
}
