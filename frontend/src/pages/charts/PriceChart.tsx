import { useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useDarkMode } from '@/app/theme';
import { useFormat } from '@/i18n/useFormat';

import { type ChartHandle, type ChartTheme, createPriceChart } from './chartAdapter';
import type { ChartModel } from './model';

/** The chart canvas; the library is created once per mount and redrawn when the model changes. */
export function PriceChart({ model }: { model: ChartModel }) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const handle = useRef<ChartHandle | null>(null);
  const dark = useDarkMode();
  const format = useFormat();
  const theme = useMemo<ChartTheme>(
    () => ({
      dark,
      formatTime: (date) => format.dateTime(date),
      formatTick: (date, part) => format.axis(date, part),
    }),
    [dark, format],
  );
  const themeRef = useRef(theme);

  useEffect(() => {
    if (!container.current) return undefined;
    const chart = createPriceChart(container.current, themeRef.current);
    handle.current = chart;
    return () => {
      chart.destroy();
      handle.current = null;
    };
  }, []);

  useEffect(() => {
    themeRef.current = theme;
    handle.current?.setTheme(theme);
  }, [theme]);

  useEffect(() => {
    handle.current?.update(model);
  }, [model]);

  // Taller with each indicator pane.
  const height = ['h-[420px]', 'h-[520px]', 'h-[600px]', 'h-[680px]'][Math.min(3, model.panes - 1)];
  return (
    <div
      ref={container}
      role="img"
      aria-label={t('charts.chartLabel')}
      className={`w-full ${height ?? ''}`}
    />
  );
}

/** The attribution Lightweight Charts asks for (its NOTICE), shown as a plain link (the library's logo is off). */
export function ChartAttribution() {
  const { t } = useTranslation();
  return (
    <p className="mt-2 text-xs text-slate-500">
      {t('charts.attribution')}{' '}
      <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer" className="underline">
        TradingView Lightweight Charts™
      </a>
    </p>
  );
}
