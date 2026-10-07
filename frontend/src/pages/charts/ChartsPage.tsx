import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { SymbolCombobox } from '@/components/SymbolCombobox';
import type { SymbolOption } from '@/components/symbolFilter';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useLiveEvents } from '@/live/context';
import { backtestKeys, HistorySchema } from '@/pages/backtests/schemas';
import { PositionsPageSchema } from '@/pages/dashboard/schemas';

import { EvidenceList } from './EvidenceList';
import {
  buildChartModel,
  focusEvidence,
  type Indicator,
  INDICATORS,
  type ModelText,
  overlaysQuery,
  relatedEvidence,
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
/** The engine's heartbeat carries the forming bar every second (`sync.heartbeat_seconds`); the chart follows it. */
const CANDLE_REFRESH_MS = 10_000;

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

/**
 * PLAN §A15 charts (TAA-905): candles × timeframe, indicators, markers, SL/TP, S/R zones, signal evidence.
 * Opened from a signal it starts focused (TAA-925): the signal's plan and its strongest supporting evidence,
 * no S/R zones and no invalidation levels; the evidence list adds the rest one item at a time.
 */
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
  const fromSignal = decisionId !== null || opportunityId !== null;
  const sourceKey = `${decisionId ?? ''}|${opportunityId ?? ''}`;

  const [indicators, setIndicators] = useState<ReadonlySet<Indicator>>(new Set(DEFAULT_INDICATORS));
  const [zones, setZones] = useState(!fromSignal);
  const [allDecisions, setAllDecisions] = useState(false);
  // the owner's evidence choice belongs to one signal; another signal starts focused again
  const [picked, setPicked] = useState<{ key: string; ids: ReadonlySet<string> } | null>(null);
  const [invalidations, setInvalidations] = useState(false);

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
  // which symbols and timeframes have closed bars in the cloud (the engine streams only the ones it trades)
  const coverage = useQuery({
    queryKey: backtestKeys.history(id),
    queryFn: ({ signal }) => apiGet(`${base}/backtests/history`, HistorySchema, { signal }),
  });
  const charted = useMemo(() => {
    const items = coverage.data?.items ?? [];
    const any = new Set(items.map((i) => i.symbol));
    const here = items.filter((i) => i.timeframe === timeframe).map((i) => i.symbol);
    return { any, first: [...here].sort()[0] ?? [...any].sort()[0] ?? null };
  }, [coverage.data, timeframe]);

  const signalDoc = signalSource.data?.signal ?? null;
  // without a choice, open a symbol that has bars (the catalog's first entry rarely does)
  const symbol =
    params.get('symbol') ??
    signalDoc?.symbol ??
    (coverage.isPending ? null : (charted.first ?? symbols.data?.items[0]?.symbol ?? null));

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

  const related = useMemo(() => relatedEvidence(signalDoc), [signalDoc]);
  const focus = useMemo(() => focusEvidence(related), [related]);
  const shownEvidence = picked?.key === sourceKey ? picked.ids : focus;

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

  // the bot's open broker positions (DEMO/LIVE, TAA-1211) get the same entry/SL/TP lines as paper ones
  const engineStatus = useEngineStatus();
  const botPositions = engineStatus.data?.heartbeat?.account?.bot_positions;
  const open = useMemo(
    () => [
      ...(positions.data?.items ?? []),
      ...(botPositions ?? []).map((p) => ({
        ticket: p.ticket,
        symbol: p.symbol,
        side: p.side,
        entry_price: p.price_open,
        sl: p.sl,
        tp: p.tp,
      })),
    ],
    [positions.data, botPositions],
  );

  const model = useMemo(() => {
    if (!candles.data) return null;
    return buildChartModel(
      { candles: candles.data, positions: open, signal: signalDoc },
      {
        indicators,
        zones,
        allDecisions,
        evidence: shownEvidence,
        invalidations,
        timeframeSeconds: TIMEFRAME_SECONDS[timeframe],
      },
      text,
    );
  }, [
    candles.data,
    open,
    signalDoc,
    indicators,
    zones,
    allDecisions,
    shownEvidence,
    invalidations,
    timeframe,
    text,
  ]);

  const setParam = (name: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(name);
    else next.set(name, value);
    setParams(next, { replace: true });
  };

  const symbolOptions = useMemo<SymbolOption[]>(() => {
    const names = new Set([
      ...(symbol ? [symbol] : []),
      ...charted.any,
      ...(symbols.data?.items ?? []).map((s) => s.symbol),
    ]);
    return [...names].map((name) => ({ symbol: name, featured: charted.any.has(name) }));
  }, [symbol, charted, symbols.data]);

  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.charts')}</h1>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <SymbolCombobox
          label={t('charts.symbol')}
          value={symbol}
          options={symbolOptions}
          featuredLabel={t('charts.hasCandles')}
          onChange={(next) => {
            setParam('symbol', next);
          }}
        />
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

      {fromSignal && (
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
          {signalDoc && (
            <EvidenceList
              items={related}
              shown={shownEvidence}
              focus={focus}
              onChange={(ids) => {
                setPicked({ key: sourceKey, ids });
              }}
              invalidations={invalidations}
              onInvalidations={setInvalidations}
            />
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
          {zones && <p className="mt-1 text-xs text-slate-500">{t('charts.zoneLegend')}</p>}
          <ChartAttribution />
        </>
      )}
    </section>
  );
}
