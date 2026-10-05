import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';

import { formatOf } from './backtestModel';

/** A metric value in its format; missing values are "—". */
export function useMetricText() {
  const { t } = useTranslation();
  const format = useFormat();
  return useCallback(
    (key: string, value: number | null | undefined): string => {
      if (value === null || value === undefined) return '—';
      switch (formatOf(key)) {
        case 'money':
          return format.number(value, {
            maximumFractionDigits: 2,
            signDisplay: key === 'net_profit' ? 'exceptZero' : 'auto',
          });
        case 'percent':
          return format.percent(value, { maximumFractionDigits: 1 });
        case 'r':
          return `${format.number(value, { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}R`;
        case 'days':
          return t('backtests.days', { n: format.number(value, { maximumFractionDigits: 1 }) });
        case 'int':
          return format.number(value, { maximumFractionDigits: 0 });
        default:
          return format.number(value, { maximumFractionDigits: 2 });
      }
    },
    [format, t],
  );
}
