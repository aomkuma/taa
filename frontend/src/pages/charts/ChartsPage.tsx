import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useLiveEvents } from '@/live/context';
import { PositionsPageSchema } from '@/pages/dashboard/schemas';

import {
  buildChartModel,
  FAMILY_COLORS,
  type Indicator,
  INDICATORS,
  type ModelText,
  overlaysQuery,
  signalEvidence,
} from './model';
import { ChartAttribution, PriceChart } from './PriceChart';
import {
  type ChartTimeframe,
  CandlesSchema,
  SignalSourceSchema,
  SymbolsSchema,
  TIMEFRAME_SECONDS,
  TIMEFRAMES,
} from './schemas';

const BARS = 300;
const DEFAULT_INDICATORS: readonly Indicator[] = ['ema', 'rsi'];
/** Closed bars are streamed by the engine continuously; the chart looks for new ones once a minute. */
const CANDLE_REFRESH_MS = 60_000;

const isTimeframe = (value: string | null): value is ChartTimeframe =>
  value !== null && (TIMEFRAMES as readonly string[]).includes(value);

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
      {label}
    </label>
  );
}

const SELECT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';

/** PLAN §A15 charts (TAA-905): candles × timeframe, indicators, markers, SL/TP, S/R zones, signal evidence. */
export function ChartsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const base = `/engines/${encodeURIComponent(id)}`;
  const [params, setParams] = useSearchParams();
  const tfParam = params.get('tf');
  const timeframe: ChartTimeframe = isTimeframe(tfParam) ? tfParam : 'M15';
  const decisionId = params.get('decision');
  const opportunityId = params.get('opportunity');

  const [indicators, setIndicators] = useState<ReadonlySet<Indicator>>(new Set(DEFAULT_INDICATORS));
  const [zones, setZones] = useState(true);
  const [allDecisions, setAllDecisions] = useState(false);
  const [hiddenFamilies, setHiddenFamilies] = useState<ReadonlySet<string>>(new Set());

  const symbols = useQuery({
    queryKey: [...engineKey(id), 'symbols', 'enabled'],
    queryFn: ({ signal }) => apiGet(`${base}/symbols?enabled=true`, SymbolsSchema, { signal }),
  });
  const signalSource = useQuery({
    queryKey: [...engineKey(id), 'chart-signal', decisionId, opportunityId],
    queryFn: ({ signal }) =>
      apiGet(
        decisionId !== null
          ? `${base}/decisions/${encodeURIComponent(decisionId)}`
          : `${base}/opportunities/${encodeURIComponent(opportunityId ?? '')}`,
        SignalSourceSchema,
        { signal },
      ),
    enabled: decisionId !== null || opportunityId !== null,
  });
  const signalDoc = signalSource.data?.signal ?? null;
  const symbol = params.get('symbol') ?? signalDoc?.symbol ?? symbols.data?.items[0]?.symbol ?? null;

  const overlays = overlaysQuery(indicators);
  const candles = useQuery({
    queryKey: [...engineKey(id), 'candles', symbol, timeframe, overlays, zones],
    queryFn: ({ signal }) =>
      apiGet(
        `${base}/candles?symbol=${encodeURIComponent(symbol ?? '')}&timeframe=${timeframe}&limit=${String(BARS)}` +
          (overlays ? `&overlays=${overlays}` : '') +
          (zones ? '&zones=true' : ''),
        CandlesSchema,
        { signal },
      ),
    enabled: symbol !== null,
    refetchInterval: CANDLE_REFRESH_MS,
    placeholderData: (previous) => previous,
  });
  const positions = useQuery({
    queryKey: [...engineKey(id), 'positions', 'open', 'chart'],
    queryFn: ({ signal }) =>
      apiGet(`${base}/positions?status=OPEN&limit=200`, PositionsPageSchema, { signal }),
  });

  // New fills and decisions change the markers and lines.
  const refetch = (...key: readonly unknown[]) => {
    void queryClient.invalidateQueries({ queryKey: [...engineKey(id), ...key] });
  };
  useLiveEvents('positions', () => {
    refetch('positions');
    refetch('candles');
  });
  useLiveEvents('decisions', () => {
    refetch('candles');
  });

  const evidence = useMemo(() => signalEvidence(signalDoc), [signalDoc]);
  const families = useMemo(() => [...new Set(evidence.map((e) => e.family))].sort(), [evidence]);

  const text = useMemo<ModelText>(
    () => ({
      decision: (code) => translateCode(i18n, 'decision', code),
      support: (n) => t('charts.support', { n }),
      resistance: (n) => t('charts.resistance', { n }),
      zone: (n) => t('charts.zone', { n }),
      entry: (ticket, side) => t('charts.entry', { ticket, side }),
      stopLoss: (ticket) => (ticket === null ? t('charts.stopLoss') : t('charts.stopLossTicket', { ticket })),
      takeProfit: (ticket) =>
        ticket === null ? t('charts.takeProfit') : t('charts.takeProfitTicket', { ticket }),
      signalEntry: t('charts.signalEntry'),
      target: t('charts.target'),
      invalidation: t('charts.invalidation'),
    }),
    [t, i18n],
  );

  const model = useMemo(() => {
    if (!candles.data) return null;
    return buildChartModel(
      { candles: candles.data, positions: positions.data?.items ?? [], signal: signalDoc },
      {
        indicators,
        zones,
        allDecisions,
        families: new Set(families.filter((f) => !hiddenFamilies.has(f))),
        timeframeSeconds: TIMEFRAME_SECONDS[timeframe],
      },
      text,
    );
  }, [
    candles.data,
    positions.data,
    signalDoc,
    indicators,
    zones,
    allDecisions,
    families,
    hiddenFamilies,
    timeframe,
    text,
  ]);

  const setParam = (name: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(name);
    else next.set(name, value);
    setParams(next, { replace: true });
  };

  const symbolOptions = [
    ...new Set([...(symbol ? [symbol] : []), ...(symbols.data?.items ?? []).map((s) => s.symbol)]),
  ].sort();

  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.charts')}</h1>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-sm">
          {t('charts.symbol')}
          <select
            value={symbol ?? ''}
            onChange={(event) => {
              setParam('symbol', event.target.value);
            }}
            className={SELECT}
          >
            {symbolOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-sm">
          {t('charts.timeframe')}
          <select
            value={timeframe}
            onChange={(event) => {
              setParam('tf', event.target.value);
            }}
            className={SELECT}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="mb-3 flex flex-wrap gap-x-4 gap-y-1">
        <legend className="sr-only">{t('charts.indicators')}</legend>
        {INDICATORS.map((indicator) => (
          <Toggle
            key={indicator}
            label={t(`charts.indicator.${indicator}`)}
            checked={indicators.has(indicator)}
            onChange={(on) => {
              const next = new Set(indicators);
              if (on) next.add(indicator);
              else next.delete(indicator);
              setIndicators(next);
            }}
          />
        ))}
        <Toggle label={t('charts.zones')} checked={zones} onChange={setZones} />
        <Toggle label={t('charts.allDecisions')} checked={allDecisions} onChange={setAllDecisions} />
      </fieldset>

      {(decisionId !== null || opportunityId !== null) && (
        <div className="mb-3 rounded border border-slate-200 p-2 text-sm dark:border-slate-800">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">
              {signalDoc
                ? t('charts.signalShown', {
                    symbol: signalDoc.symbol,
                    action: signalDoc.action,
                    tf: signalDoc.timeframe,
                  })
                : signalSource.isError
                  ? t('charts.signalUnavailable')
                  : t('dashboard.loading')}
            </span>
            <button
              type="button"
              className="underline"
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete('decision');
                next.delete('opportunity');
                setParams(next, { replace: true });
              }}
            >
              {t('charts.hideSignal')}
            </button>
          </div>
          {families.length > 0 && (
            <fieldset className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              <legend className="mb-1 text-xs text-slate-500">{t('charts.evidence')}</legend>
              {families.map((family) => (
                <label key={family} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={!hiddenFamilies.has(family)}
                    onChange={(event) => {
                      const next = new Set(hiddenFamilies);
                      if (event.target.checked) next.delete(family);
                      else next.add(family);
                      setHiddenFamilies(next);
                    }}
                  />
                  <svg aria-hidden="true" viewBox="0 0 10 10" className="h-2.5 w-2.5">
                    <circle cx="5" cy="5" r="5" fill={FAMILY_COLORS[family] ?? '#64748b'} />
                  </svg>
                  {translateCode(i18n, 'family', family)}
                </label>
              ))}
            </fieldset>
          )}
        </div>
      )}

      {symbol === null ? (
        <p className="text-sm text-slate-500">
          {symbols.isError ? t('dashboard.loadFailed') : t('charts.noSymbols')}
        </p>
      ) : candles.isError && !candles.data ? (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {t('charts.noCandles')}
        </p>
      ) : model === null ? (
        <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
      ) : model.candles.length === 0 ? (
        <p className="text-sm text-slate-500">{t('charts.noCandles')}</p>
      ) : (
        <>
          <PriceChart model={model} />
          <ChartAttribution />
        </>
      )}
    </section>
  );
}
