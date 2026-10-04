/**
 * Draws a `ChartModel` with Lightweight Charts 5 (TradingView, Apache-2.0). The only module that touches the
 * library, so page tests mock it (jsdom has no canvas).
 *
 * The library's own attribution logo is switched off: it injects a `<style>` element, which the strict CSP
 * (PLAN §A14, `style-src 'self'`) blocks. The page shows the attribution link itself (`ChartAttribution`).
 */
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  LineSeries,
  LineStyle as LwLineStyle,
  type SeriesMarker,
  TickMarkType,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';

import type { ChartModel, LineStyle } from './model';

export interface ChartTheme {
  dark: boolean;
  /** Crosshair label of a time (full date and time in the display timezone). */
  formatTime: (date: Date) => string;
  /** Axis tick label. */
  formatTick: (date: Date, part: 'year' | 'month' | 'day' | 'time') => string;
}

export interface ChartHandle {
  update: (model: ChartModel) => void;
  setTheme: (theme: ChartTheme) => void;
  destroy: () => void;
}

const STYLES: Record<LineStyle, LwLineStyle> = {
  solid: LwLineStyle.Solid,
  dashed: LwLineStyle.Dashed,
  dotted: LwLineStyle.Dotted,
};

const TICK_PART: Record<TickMarkType, 'year' | 'month' | 'day' | 'time'> = {
  [TickMarkType.Year]: 'year',
  [TickMarkType.Month]: 'month',
  [TickMarkType.DayOfMonth]: 'day',
  [TickMarkType.Time]: 'time',
  [TickMarkType.TimeWithSeconds]: 'time',
};

const ts = (time: number) => time as UTCTimestamp;
const toDate = (time: Time) => new Date((typeof time === 'number' ? time : 0) * 1000);

function themeOptions(theme: ChartTheme) {
  const text = theme.dark ? '#cbd5e1' : '#334155';
  const grid = theme.dark ? '#1e293b' : '#e2e8f0';
  return {
    layout: {
      background: { color: theme.dark ? '#0f172a' : '#ffffff' },
      textColor: text,
      attributionLogo: false,
      panes: { separatorColor: grid },
    },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    localization: { timeFormatter: (time: Time) => theme.formatTime(toDate(time)) },
    timeScale: {
      timeVisible: true,
      borderColor: grid,
      tickMarkFormatter: (time: Time, type: TickMarkType) => theme.formatTick(toDate(time), TICK_PART[type]),
    },
    rightPriceScale: { borderColor: grid },
  };
}

export function createPriceChart(container: HTMLElement, theme: ChartTheme): ChartHandle {
  const chart: IChartApi = createChart(container, { autoSize: true, ...themeOptions(theme) });
  let series: ISeriesApi<'Candlestick' | 'Line'>[] = [];
  let first = true;

  const clear = () => {
    for (const s of series) chart.removeSeries(s);
    series = [];
  };

  return {
    update(model) {
      const range = chart.timeScale().getVisibleLogicalRange();
      clear();
      const candles = chart.addSeries(CandlestickSeries, {
        upColor: '#16a34a',
        downColor: '#dc2626',
        borderVisible: false,
        wickUpColor: '#16a34a',
        wickDownColor: '#dc2626',
        priceFormat: { type: 'price', precision: model.precision, minMove: 10 ** -model.precision },
      });
      candles.setData(model.candles.map((c) => ({ ...c, time: ts(c.time) })));
      series.push(candles);
      for (const line of model.lines) {
        const s = chart.addSeries(
          LineSeries,
          {
            color: line.color,
            lineWidth: line.width,
            lineStyle: STYLES[line.style],
            priceLineVisible: false,
            lastValueVisible: line.pane > 0,
            crosshairMarkerVisible: false,
          },
          line.pane,
        );
        s.setData(line.points.map((p) => ({ time: ts(p.time), value: p.value })));
        series.push(s);
      }
      for (const p of model.priceLines) {
        candles.createPriceLine({
          price: p.price,
          color: p.color,
          title: p.title,
          lineStyle: STYLES[p.style],
          lineWidth: 1,
          axisLabelVisible: p.title !== '',
        });
      }
      const markers: SeriesMarker<Time>[] = model.markers.map((m) =>
        m.position === 'atPriceMiddle'
          ? {
              time: ts(m.time),
              position: m.position,
              price: m.price ?? 0,
              shape: m.shape,
              color: m.color,
              text: m.text,
            }
          : { time: ts(m.time), position: m.position, shape: m.shape, color: m.color, text: m.text },
      );
      createSeriesMarkers(candles, markers);
      const panes = chart.panes();
      panes.forEach((pane, i) => {
        pane.setStretchFactor(i === 0 ? 3 : 1);
      });
      if (first || range === null) {
        chart.timeScale().fitContent();
        first = false;
      } else {
        chart.timeScale().setVisibleLogicalRange(range);
      }
    },
    setTheme(next) {
      chart.applyOptions(themeOptions(next));
    },
    destroy() {
      chart.remove();
    },
  };
}
