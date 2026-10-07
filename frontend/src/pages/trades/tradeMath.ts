/** Position arithmetic and CSV export for the positions and history pages (pure, tested). */
import type { Trade } from './schemas';

const direction = (side: string) => (side === 'SELL' ? -1 : 1);

/** Price distance to the initial stop, the "1R" of the trade (null without a usable stop). */
export function initialRisk(entry: number, initialStop: number | null | undefined): number | null {
  if (initialStop == null) return null;
  const risk = Math.abs(entry - initialStop);
  return risk > 0 ? risk : null;
}

/** Where the open position stands in R at its current price. */
export function openR(trade: Trade, risk: number | null): number | null {
  if (risk === null) return null;
  return ((trade.price_current - trade.entry_price) * direction(trade.side)) / risk;
}

/** MAE/MFE (price units) in R. */
export function excursionR(excursion: number, risk: number | null): number | null {
  return risk === null ? null : excursion / risk;
}

/** Whole minutes between entry and exit (null while open). */
export function heldMinutes(trade: Pick<Trade, 'entry_time' | 'exit_time'>): number | null {
  if (trade.exit_time === null) return null;
  return Math.max(0, Math.round((Date.parse(trade.exit_time) - Date.parse(trade.entry_time)) / 60_000));
}

export const CSV_COLUMNS = [
  'ticket',
  'symbol',
  'side',
  'volume',
  'entry_time',
  'entry_price',
  'exit_time',
  'exit_price',
  'exit_reason',
  'sl',
  'tp',
  'profit',
  'commission',
  'swap',
  'net',
  'r_multiple',
  'mae',
  'mfe',
  'bars_held',
] as const satisfies readonly (keyof Trade)[];

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  const text = String(value);
  // quote fields with separators or quotes; a leading =+-@ is prefixed so spreadsheets never run it as a formula
  const safe = /^[=+\-@]/.test(text) && Number.isNaN(Number(text)) ? `'${text}` : text;
  return /[",\r\n]/.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe;
}

/** Closed trades as CSV (UTC ISO times, raw numbers; one header row). */
export function tradesCsv(trades: readonly Trade[]): string {
  const lines = [CSV_COLUMNS.join(',')];
  for (const trade of trades) lines.push(CSV_COLUMNS.map((c) => cell(trade[c])).join(','));
  return `${lines.join('\r\n')}\r\n`;
}
