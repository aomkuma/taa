import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import {
  type DateTimeOptions,
  DEFAULT_TIME_ZONE,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatPercent,
  type NumberOptions,
} from './format';
import { DEFAULT_LANGUAGE, isLanguage, type Language } from './languages';

/**
 * Formatters bound to the current UI language and display timezone. The timezone is Asia/Bangkok until the
 * user's profile timezone (users.timezone) is available from the API.
 */
export function useFormat(timeZone: string = DEFAULT_TIME_ZONE) {
  const { i18n } = useTranslation();
  const language: Language = isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE;
  return useMemo(
    () => ({
      language,
      timeZone,
      dateTime: (value: Date | string | null | undefined, options: DateTimeOptions = {}) =>
        formatDateTime(value, language, { timeZone, ...options }),
      date: (value: Date | string | null | undefined, options: Omit<DateTimeOptions, 'timeStyle'> = {}) =>
        formatDate(value, language, { timeZone, ...options }),
      number: (value: number | null | undefined, options?: NumberOptions) =>
        formatNumber(value, language, options),
      money: (
        value: number | null | undefined,
        currency: string,
        options?: Pick<NumberOptions, 'signDisplay'>,
      ) => formatMoney(value, currency, language, options),
      percent: (value: number | null | undefined, options?: NumberOptions) =>
        formatPercent(value, language, options),
    }),
    [language, timeZone],
  );
}
