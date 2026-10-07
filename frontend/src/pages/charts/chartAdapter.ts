/**
 * Draws a `ChartModel` with Lightweight Charts 5 (TradingView, Apache-2.0). The only module that touches the
 * library, so page tests mock it (jsdom has no canvas).
 *
 * The library's own attribution logo is switched off: it injects a `<style>` element, which the strict CSP
 * (PLAN §A14, `style-src 'self'`) blocks. The page shows the attribution link itself (`ChartAttribution`).
 */
import {
  AreaSeries,
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  LineSeries,
  LineStyle as LwLineStyle,
  type LineWidth,
  TickMarkType,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';

import { type ChartModel, followRange, type LineStyle } from './model';

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

/**
 * The price chart. A data refresh (every few seconds while the engine streams the forming bar) updates the
 * series in place instead of rebuilding them, so the owner's zoom, scroll and chart shift, a hand-set price
 * scale and dragged pane heights stay as they were (TAA-925). Only another symbol or timeframe starts fresh.
 */
export function createPriceChart(container: HTMLElement, theme: ChartTheme): ChartHandle {
  const chart: IChartApi = createChart(container, { autoSize: true, ...themeOptions(theme) });
  let candles: ISeriesApi<'Candlestick'> | null = null;
  let markers: ISeriesMarkersPluginApi<Time> | null = null;
  let priceLines: IPriceLine[] = [];
  const lines = new Map<string, { series: ISeriesApi<'Line'>; pane: number }>();
  let view = ''; // symbol/timeframe on screen; another one starts zoomed to fit
  let times: number[] = [];
  let panes = 0;

  const candleSeries = () => {
    if (candles === null) {
      candles = chart.addSeries(CandlestickSeries, {
        upColor: '#16a34a',
        downColor: '#dc2626',
        borderVisible: false,
        wickUpColor: '#16a34a',
        wickDownColor: '#dc2626',
      });
      markers = createSeriesMarkers(candles, []);
    }
    return candles;
  };

  return {
    update(model) {
      const range = chart.timeScale().getVisibleLogicalRange();
      const fresh = model.view !== view;
      const series = candleSeries();
      series.applyOptions({
        priceFormat: { type: 'price', precision: model.precision, minMove: 10 ** -model.precision },
      });
      series.setData(model.candles.map((c) => ({ ...c, time: ts(c.time) })));

      // indicator and evidence lines: kept by id, so their panes (and the heights the owner gave them) stay
      const wanted = new Map(model.lines.map((l) => [l.id, l]));
      for (const [id, kept] of lines) {
        const line = wanted.get(id);
        if (line === undefined || line.pane !== kept.pane) {
          chart.removeSeries(kept.series);
          lines.delete(id);
        }
      }
      for (const line of model.lines) {
        const style = {
          color: line.color,
          lineWidth: line.width,
          lineStyle: STYLES[line.style],
          priceLineVisible: false,
          lastValueVisible: line.pane > 0,
          crosshairMarkerVisible: false,
        };
        let kept = lines.get(line.id);
        if (kept === undefined) {
          kept = { series: chart.addSeries(LineSeries, style, line.pane), pane: line.pane };
          lines.set(line.id, kept);
        } else {
          kept.series.applyOptions(style);
        }
        kept.series.setData(line.points.map((p) => ({ time: ts(p.time), value: p.value })));
      }

      for (const line of priceLines) series.removePriceLine(line);
      priceLines = model.priceLines.map((p) =>
        series.createPriceLine({
          price: p.price,
          color: p.color,
          title: p.title,
          lineStyle: STYLES[p.style],
          lineWidth: (p.width ?? 1) as LineWidth,
          axisLabelVisible: p.title !== '',
        }),
      );
      markers?.setMarkers(
        model.markers.map((m) =>
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
        ),
      );

      const paneList = chart.panes();
      if (fresh || paneList.length !== panes) {
        paneList.forEach((pane, i) => {
          pane.setStretchFactor(i === 0 ? 3 : 1);
        });
        panes = paneList.length;
      }
      const shown = model.candles.map((c) => c.time);
      if (range === null || fresh) {
        series.priceScale().setAutoScale(true);
        chart.timeScale().fitContent();
      } else {
        chart.timeScale().setVisibleLogicalRange(followRange(range, times, shown));
      }
      view = model.view;
      times = shown;
    },
    setTheme(next) {
      chart.applyOptions(themeOptions(next));
    },
    destroy() {
      chart.remove();
    },
  };
}

/** One value series over time (equity or drawdown of a backtest, TAA-910): a line, or an area under it. */
export interface SeriesData {
  points: { time: number; value: number }[];
  kind: 'line' | 'area';
  /** Line colour; the area fills with it, faded. */
  color: string;
  precision: number;
}

export interface SeriesChartHandle {
  update: (data: SeriesData) => void;
  setTheme: (theme: ChartTheme) => void;
  destroy: () => void;
}

export function createSeriesChart(container: HTMLElement, theme: ChartTheme): SeriesChartHandle {
  const chart: IChartApi = createChart(container, { autoSize: true, ...themeOptions(theme) });
  let series: ISeriesApi<'Line' | 'Area'> | null = null;
  return {
    update(data) {
      if (series) chart.removeSeries(series);
      const priceFormat = {
        type: 'price' as const,
        precision: data.precision,
        minMove: 10 ** -data.precision,
      };
      series =
        data.kind === 'area'
          ? chart.addSeries(AreaSeries, {
              lineColor: data.color,
              topColor: `${data.color}10`,
              bottomColor: `${data.color}55`,
              lineWidth: 2,
              priceLineVisible: false,
              priceFormat,
              invertFilledArea: true,
            })
          : chart.addSeries(LineSeries, {
              color: data.color,
              lineWidth: 2,
              priceLineVisible: false,
              priceFormat,
            });
      series.setData(data.points.map((p) => ({ time: ts(p.time), value: p.value })));
      chart.timeScale().fitContent();
    },
    setTheme(next) {
      chart.applyOptions(themeOptions(next));
    },
    destroy() {
      chart.remove();
    },
  };
}
