import {
  dateLocale,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatPercent,
  MISSING,
  NaiveDateTimeError,
  parseDateTime,
} from '@/i18n/format';

// Wednesday 2026-09-30 10:00 UTC = 17:00 in Bangkok (UTC+7).
const INSTANT = '2026-09-30T10:00:00Z';

describe('dates', () => {
  it('uses the Gregorian calendar for Thai by default', () => {
    expect(dateLocale('th')).toBe('th-TH-u-ca-gregory');
    const text = formatDate(INSTANT, 'th');
    expect(text).toContain('2026');
    expect(text).not.toContain('2569');
    expect(text).toContain('ก.ย.');
  });

  it('shows the Buddhist era only when asked', () => {
    expect(formatDate(INSTANT, 'th', { calendar: 'buddhist' })).toContain('2569');
  });

  it('displays Asia/Bangkok time by default, 24-hour', () => {
    expect(formatDateTime(INSTANT, 'th')).toContain('17:00');
    expect(formatDateTime(INSTANT, 'en')).toContain('17:00');
  });

  it('honours another display timezone', () => {
    expect(formatDateTime(INSTANT, 'en', { timeZone: 'UTC' })).toContain('10:00');
  });

  it('crosses the date line in the display timezone', () => {
    // 20:00 UTC on 30 Sep is 03:00 on 1 Oct in Bangkok.
    expect(formatDate('2026-09-30T20:00:00Z', 'en', { dateStyle: 'long' })).toBe('1 October 2026');
  });

  it('accepts explicit offsets and rejects naive datetimes', () => {
    expect(parseDateTime('2026-09-30T13:00:00+03:00').toISOString()).toBe('2026-09-30T10:00:00.000Z');
    expect(() => parseDateTime('2026-09-30T10:00:00')).toThrow(NaiveDateTimeError);
  });

  it('renders missing values as a dash', () => {
    expect(formatDateTime(null, 'th')).toBe(MISSING);
    expect(formatDate(undefined, 'en')).toBe(MISSING);
  });
});

describe('numbers', () => {
  it('groups digits and keeps Latin digits in Thai', () => {
    expect(formatNumber(1234567.891, 'th')).toBe('1,234,567.89');
    expect(formatNumber(1234567.891, 'en')).toBe('1,234,567.89');
  });

  it('respects fraction digits', () => {
    expect(formatNumber(1.5, 'en', { minimumFractionDigits: 2 })).toBe('1.50');
    expect(formatNumber(1.23456, 'en', { maximumFractionDigits: 4 })).toBe('1.2346');
  });

  it('formats money with the currency code and minor units', () => {
    expect(formatMoney(1234.5, 'USD', 'en')).toMatch(/^USD\s1,234\.50$/);
    expect(formatMoney(1234.5, 'USD', 'th')).toMatch(/^USD\s1,234\.50$/);
    expect(formatMoney(-12, 'USD', 'en')).toContain('12.00');
  });

  it('takes percent units like the backend (0.5 means 0.5%)', () => {
    expect(formatPercent(0.5, 'en')).toBe('0.5%');
    expect(formatPercent(12.345, 'th')).toBe('12.35%');
  });

  it('renders missing and non-finite numbers as a dash, never as 0', () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(formatNumber(value, 'en')).toBe(MISSING);
      expect(formatMoney(value, 'USD', 'th')).toBe(MISSING);
      expect(formatPercent(value, 'th')).toBe(MISSING);
    }
  });
});
