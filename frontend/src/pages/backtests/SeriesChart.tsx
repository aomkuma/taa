import { useEffect, useMemo, useRef } from 'react';

import { useDarkMode } from '@/app/theme';
import { useFormat } from '@/i18n/useFormat';
import { type ChartTheme, createSeriesChart, type SeriesChartHandle } from '@/pages/charts/chartAdapter';

import type { Point } from './backtestModel';

/** Colours checked with the dataviz palette validator against each mode's chart surface. */
const COLORS = {
  equity: { light: '#2563eb', dark: '#3b82f6' },
  drawdown: { light: '#dc2626', dark: '#ef4444' },
} as const;

/** One curve of a backtest (equity line or drawdown area), with the library's crosshair and tooltip. */
export function SeriesChart({
  points,
  kind,
  label,
  precision,
}: {
  points: Point[];
  kind: 'equity' | 'drawdown';
  label: string;
  precision: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  const handle = useRef<SeriesChartHandle | null>(null);
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
    const chart = createSeriesChart(container.current, themeRef.current);
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
    handle.current?.update({
      points,
      kind: kind === 'drawdown' ? 'area' : 'line',
      color: COLORS[kind][dark ? 'dark' : 'light'],
      precision,
    });
  }, [points, kind, dark, precision]);

  return <div ref={container} role="img" aria-label={label} className="h-56 w-full" />;
}
