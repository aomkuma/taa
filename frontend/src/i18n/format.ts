/**
 * Locale-aware formatting of dates, numbers, money and percentages (PLAN §A28, R27).
 *
 * - Thai dates use `th-TH-u-ca-gregory` (Gregorian years) unless the Buddhist era is requested explicitly.
 * - Times are displayed in Asia/Bangkok by default; the API speaks timezone-aware UTC ISO strings.
 * - Percent inputs are in percent units, as in the backend (`0.5` means 0.5%).
 * - A missing or non-finite number renders as an em dash, never as 0, so absent data is visible.
 */
import type { Language } from './languages';

export const DEFAULT_TIME_ZONE = 'Asia/Bangkok';
export const MISSING = '—';

export type Calendar = 'gregory' | 'buddhist';

export class NaiveDateTimeError extends Error {
  constructor(value: string) {
    super(`Datetime without a timezone offset: ${value}`);
    this.name = 'NaiveDateTimeError';
  }
}

export function dateLocale(language: Language, calendar: Calendar = 'gregory'): string {
  return language === 'th' ? `th-TH-u-ca-${calendar}` : 'en-GB';
}

export function numberLocale(language: Language): string {
  // th-TH formats with Latin digits by default; Thai digits would need -u-nu-thai.
  return language === 'th' ? 'th-TH' : 'en-GB';
}

const OFFSET_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/**
 * Parses an API datetime. A string without `Z` or an offset is rejected: the backend only emits aware UTC, and
 * guessing the zone of a naive value would silently shift times.
 */
export function parseDateTime(value: Date | string): Date {
  if (value instanceof Date) return value;
  if (!OFFSET_SUFFIX.test(value.trim())) throw new NaiveDateTimeError(value);
  return new Date(value);
}

export interface DateTimeOptions {
  timeZone?: string;
  calendar?: Calendar;
  dateStyle?: Intl.DateTimeFormatOptions['dateStyle'];
  timeStyle?: Intl.DateTimeFormatOptions['timeStyle'];
}

const formatters = new Map<string, Intl.DateTimeFormat | Intl.NumberFormat>();

function cached<F extends Intl.DateTimeFormat | Intl.NumberFormat>(key: string, create: () => F): F {
  let formatter = formatters.get(key);
  if (!formatter) {
    formatter = create();
    formatters.set(key, formatter);
  }
  return formatter as F;
}

function dateTimeFormat(locale: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  return cached(`dt|${locale}|${JSON.stringify(options)}`, () => new Intl.DateTimeFormat(locale, options));
}

function numberFormat(locale: string, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  return cached(`nf|${locale}|${JSON.stringify(options)}`, () => new Intl.NumberFormat(locale, options));
}

/** Date and time. Defaults: medium date, short time (24 h), Asia/Bangkok, Gregorian. */
export function formatDateTime(
  value: Date | string | null | undefined,
  language: Language,
  options: DateTimeOptions = {},
): string {
  if (value == null) return MISSING;
  const date = parseDateTime(value);
  if (Number.isNaN(date.getTime())) return MISSING;
  const {
    timeZone = DEFAULT_TIME_ZONE,
    calendar = 'gregory',
    dateStyle = 'medium',
    timeStyle = 'short',
  } = options;
  return dateTimeFormat(dateLocale(language, calendar), {
    timeZone,
    dateStyle,
    timeStyle,
    hourCycle: 'h23',
  }).format(date);
}

export function formatDate(
  value: Date | string | null | undefined,
  language: Language,
  options: Omit<DateTimeOptions, 'timeStyle'> = {},
): string {
  if (value == null) return MISSING;
  const date = parseDateTime(value);
  if (Number.isNaN(date.getTime())) return MISSING;
  const { timeZone = DEFAULT_TIME_ZONE, calendar = 'gregory', dateStyle = 'medium' } = options;
  return dateTimeFormat(dateLocale(language, calendar), { timeZone, dateStyle }).format(date);
}

export type AxisPart = 'year' | 'month' | 'day' | 'time';

const AXIS_OPTIONS: Record<AxisPart, Intl.DateTimeFormatOptions> = {
  year: { year: 'numeric' },
  month: { month: 'short', year: '2-digit' },
  day: { day: 'numeric', month: 'short' },
  time: { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' },
};

/** A short label for a chart axis tick (year, month, day or time of day) in the display timezone. */
export function formatAxis(
  value: Date,
  language: Language,
  part: AxisPart,
  options: Pick<DateTimeOptions, 'timeZone' | 'calendar'> = {},
): string {
  if (Number.isNaN(value.getTime())) return MISSING;
  const { timeZone = DEFAULT_TIME_ZONE, calendar = 'gregory' } = options;
  return dateTimeFormat(dateLocale(language, calendar), { timeZone, ...AXIS_OPTIONS[part] }).format(value);
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export interface NumberOptions {
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
  signDisplay?: Intl.NumberFormatOptions['signDisplay'];
}

export function formatNumber(
  value: number | null | undefined,
  language: Language,
  options: NumberOptions = {},
): string {
  if (!isFiniteNumber(value)) return MISSING;
  const { minimumFractionDigits = 0, maximumFractionDigits = Math.max(2, minimumFractionDigits) } = options;
  return numberFormat(numberLocale(language), {
    minimumFractionDigits,
    maximumFractionDigits,
    ...(options.signDisplay ? { signDisplay: options.signDisplay } : {}),
  }).format(value);
}

/** Money in an ISO 4217 currency (the account currency, e.g. USD) with that currency's minor units. */
export function formatMoney(
  value: number | null | undefined,
  currency: string,
  language: Language,
  options: Pick<NumberOptions, 'signDisplay'> = {},
): string {
  if (!isFiniteNumber(value)) return MISSING;
  return numberFormat(numberLocale(language), {
    style: 'currency',
    currency,
    currencyDisplay: 'code',
    ...(options.signDisplay ? { signDisplay: options.signDisplay } : {}),
  }).format(value);
}

/** A value in percent units (`0.5` → "0.5%"). */
export function formatPercent(
  value: number | null | undefined,
  language: Language,
  options: NumberOptions = {},
): string {
  if (!isFiniteNumber(value)) return MISSING;
  const { minimumFractionDigits = 0, maximumFractionDigits = Math.max(2, minimumFractionDigits) } = options;
  return numberFormat(numberLocale(language), {
    style: 'percent',
    minimumFractionDigits,
    maximumFractionDigits,
    ...(options.signDisplay ? { signDisplay: options.signDisplay } : {}),
  }).format(value / 100);
}
