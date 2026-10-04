import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { StaleBadge } from '@/app/shell/StaleBadge';
import { useServerNow } from '@/app/useNow';
import { Gauge } from '@/components/Gauge';
import { useEngine, useEngineStatus } from '@/engine/context';
import { engineKey } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';
import { dashboardKeys } from '@/pages/dashboard/keys';
import { BreakersSchema } from '@/pages/dashboard/schemas';
import { SymbolsSchema } from '@/pages/charts/schemas';

import {
  DecisionMarketSchema,
  DecisionRefsSchema,
  type Quote,
  type Quotes,
  QuotesEventSchema,
  QuotesSchema,
  type Spec,
  SymbolDetailSchema,
  symbolKeys,
} from './schemas';

/** A quote older than this while the market is open is shown as stale (the engine's stale-data rule is 60 s). */
const QUOTE_STALE_MS = 60_000;
const MAX_LISTED = 50;

const FILLING_NAMES: [number, string][] = [
  [1, 'FOK'],
  [2, 'IOC'],
  [4, 'BOC'],
];

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-1 text-sm last:border-0 dark:border-slate-800">
      <dt className="text-slate-600 dark:text-slate-400">{label}</dt>
      <dd className="text-right font-medium tabular-nums">{children}</dd>
    </div>
  );
}

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return error ? (
    <p role="alert" className="text-sm text-red-700 dark:text-red-400">
      {t('dashboard.loadFailed')}
    </p>
  ) : (
    <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
  );
}

/** Quotes from REST, kept current by the stream's `quotes` events. */
function useQuotes(engineId: string) {
  const queryClient = useQueryClient();
  const key = symbolKeys.quotes(engineId);
  const quotes = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/quotes`, QuotesSchema, { signal }),
  });
  useLiveEvents('quotes', (event) => {
    const update = QuotesEventSchema.safeParse(event.item);
    if (!update.success) {
      void queryClient.invalidateQueries({ queryKey: key });
      return;
    }
    queryClient.setQueryData<Quotes>(key, (old) => ({
      at: update.data.at,
      received_at: old?.received_at ?? null,
      quotes: update.data.quotes,
    }));
  });
  return quotes;
}

function QuoteCard({ quote }: { quote: Quote | undefined }) {
  const { t } = useTranslation();
  const format = useFormat();
  const status = useEngineStatus();
  const serverNow = useServerNow(5_000);
  const marketOpen = status.data?.heartbeat?.market_open === true;
  return (
    <Card title={t('symbols.quote.title')}>
      {quote === undefined ? (
        <p className="text-sm text-slate-500">{t('symbols.quote.none')}</p>
      ) : (
        <>
          <dl className="mb-3">
            <Row label={t('symbols.quote.bid')}>{format.number(quote.bid, { maximumFractionDigits: 6 })}</Row>
            <Row label={t('symbols.quote.ask')}>{format.number(quote.ask, { maximumFractionDigits: 6 })}</Row>
            <Row label={t('symbols.quote.time')}>
              <span className="flex items-center justify-end gap-2">
                {format.dateTime(quote.time)}
                {marketOpen && serverNow - Date.parse(quote.time) > QUOTE_STALE_MS && (
                  <StaleBadge since={quote.time} />
                )}
              </span>
            </Row>
          </dl>
          {quote.max_spread_points != null ? (
            <Gauge
              label={t('symbols.quote.spread')}
              used={quote.spread_points}
              limit={quote.max_spread_points}
              value={format.number(quote.spread_points, { maximumFractionDigits: 1 })}
              limitText={format.number(quote.max_spread_points, { maximumFractionDigits: 1 })}
            />
          ) : (
            <dl>
              <Row label={t('symbols.quote.spread')}>
                {format.number(quote.spread_points, { maximumFractionDigits: 1 })}
              </Row>
            </dl>
          )}
        </>
      )}
    </Card>
  );
}

function SpecCard({ spec }: { spec: Spec }) {
  const { t } = useTranslation();
  const format = useFormat();
  const n = (value: number) => format.number(value, { maximumFractionDigits: 8 });
  const filling = FILLING_NAMES.filter(([bit]) => (spec.filling_mode & bit) !== 0).map(([, name]) => name);
  const tradeMode = String(spec.trade_mode);
  const tradeModeText = ['0', '1', '2', '3', '4'].includes(tradeMode)
    ? t(`symbols.tradeMode.${tradeMode as '0' | '1' | '2' | '3' | '4'}`)
    : tradeMode;
  return (
    <Card title={t('symbols.spec.title')}>
      <dl>
        <Row label={t('symbols.spec.tradeMode')}>{tradeModeText}</Row>
        <Row label={t('symbols.spec.digits')}>{spec.digits}</Row>
        <Row label={t('symbols.spec.point')}>{n(spec.point)}</Row>
        <Row label={t('symbols.spec.tickSize')}>{n(spec.tick_size)}</Row>
        <Row label={t('symbols.spec.tickValue')}>
          {n(spec.tick_value)} {spec.currency_profit}
        </Row>
        <Row label={t('symbols.spec.contractSize')}>{n(spec.contract_size)}</Row>
        <Row label={t('symbols.spec.volumeMin')}>{n(spec.volume_min)}</Row>
        <Row label={t('symbols.spec.volumeMax')}>{n(spec.volume_max)}</Row>
        <Row label={t('symbols.spec.volumeStep')}>{n(spec.volume_step)}</Row>
        <Row label={t('symbols.spec.stopsLevel')}>{spec.stops_level}</Row>
        <Row label={t('symbols.spec.freezeLevel')}>{spec.freeze_level}</Row>
        <Row label={t('symbols.spec.filling')}>{filling.length ? filling.join(', ') : '—'}</Row>
        <Row label={t('symbols.spec.spreadFloat')}>
          {t(spec.spread_float ? 'symbols.spec.yes' : 'symbols.spec.no')}
        </Row>
        <Row label={t('symbols.spec.swapLong')}>{n(spec.swap_long)}</Row>
        <Row label={t('symbols.spec.swapShort')}>{n(spec.swap_short)}</Row>
        <Row label={t('symbols.spec.currencies')}>
          {spec.currency_base} / {spec.currency_profit} / {spec.currency_margin}
        </Row>
      </dl>
    </Card>
  );
}

/** HTF trend, regime and volatility from the newest decision on the symbol (its market snapshot). */
function ContextCard({ engineId, symbol }: { engineId: string; symbol: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const base = `/engines/${encodeURIComponent(engineId)}`;
  const latest = useQuery({
    queryKey: symbolKeys.latestDecision(engineId, symbol),
    queryFn: ({ signal }) =>
      apiGet(`${base}/decisions?symbol=${encodeURIComponent(symbol)}&limit=1`, DecisionRefsSchema, {
        signal,
      }),
  });
  const decisionId = latest.data?.items[0]?.decision_id ?? null;
  const detail = useQuery({
    queryKey: symbolKeys.decision(engineId, decisionId ?? ''),
    queryFn: ({ signal }) =>
      apiGet(`${base}/decisions/${encodeURIComponent(decisionId ?? '')}`, DecisionMarketSchema, { signal }),
    enabled: decisionId !== null,
  });
  const price = (value: number | undefined) => format.number(value ?? null, { maximumFractionDigits: 6 });
  let body: ReactNode;
  if (latest.data === undefined) body = <Loading error={latest.isError} />;
  else if (decisionId === null) body = <p className="text-sm text-slate-500">{t('symbols.context.none')}</p>;
  else if (detail.data === undefined) body = <Loading error={detail.isError} />;
  else {
    const market = detail.data.market;
    body = (
      <>
        <dl className="mb-3">
          <Row label={t('symbols.context.session')}>{translateCode(i18n, 'session', market.session)}</Row>
          <Row label={t('symbols.context.support')}>{price(market.support_levels[0])}</Row>
          <Row label={t('symbols.context.resistance')}>{price(market.resistance_levels[0])}</Row>
        </dl>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 pr-3 font-normal">{t('symbols.context.timeframe')}</th>
                <th className="py-1 pr-3 font-normal">{t('symbols.context.trend')}</th>
                <th className="py-1 pr-3 font-normal">{t('symbols.context.regime')}</th>
                <th className="py-1 pr-3 font-normal">{t('symbols.context.volatility')}</th>
                <th className="py-1 font-normal">{t('symbols.context.structure')}</th>
              </tr>
            </thead>
            <tbody>
              {market.states.map((s) => (
                <tr key={s.timeframe} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1 pr-3 font-medium">{s.timeframe}</td>
                  <td className="py-1 pr-3">{translateCode(i18n, 'trend', s.trend)}</td>
                  <td className="py-1 pr-3">{translateCode(i18n, 'regime', s.regime)}</td>
                  <td className="py-1 pr-3">{translateCode(i18n, 'volatility', s.volatility)}</td>
                  <td className="py-1">{s.structure ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {t('symbols.context.asOf', { time: format.dateTime(detail.data.created_at) })}
        </p>
      </>
    );
  }
  return <Card title={t('symbols.context.title')}>{body}</Card>;
}

function StateCard({
  engineId,
  symbol,
  enabled,
  reason,
}: {
  engineId: string;
  symbol: string;
  enabled: boolean;
  reason: string;
}) {
  const { t, i18n } = useTranslation();
  const breakers = useQuery({
    queryKey: dashboardKeys.breakers(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/breakers?limit=1`, BreakersSchema, { signal }),
  });
  const tripped = breakers.data?.states.filter((s) => s.scope_key === symbol && s.state !== 'CLOSED') ?? [];
  return (
    <Card title={t('symbols.state.title')}>
      <dl className="mb-3">
        <Row label={t('symbols.state.catalog')}>
          <span
            className={enabled ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}
          >
            {t(enabled ? 'symbols.enabled' : 'symbols.disabled')}
          </span>
          {reason && <span className="block text-xs font-normal text-slate-500">{reason}</span>}
        </Row>
      </dl>
      <p className="mb-1 text-sm text-slate-600 dark:text-slate-400">{t('symbols.state.breakers')}</p>
      {breakers.data === undefined ? (
        <Loading error={breakers.isError} />
      ) : tripped.length === 0 ? (
        <p className="text-sm text-slate-500">{t('symbols.state.noBreakers')}</p>
      ) : (
        <ul>
          {tripped.map((s) => (
            <li key={s.name} className="text-sm text-red-700 dark:text-red-400">
              {translateCode(i18n, 'breaker', s.name)}
              {s.reason && <span className="ml-2 text-xs text-slate-500">{s.reason}</span>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SymbolDetail({
  engineId,
  symbol,
  quote,
}: {
  engineId: string;
  symbol: string;
  quote: Quote | undefined;
}) {
  const { t } = useTranslation();
  const detail = useQuery({
    queryKey: symbolKeys.detail(engineId, symbol),
    queryFn: ({ signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/symbols/${encodeURIComponent(symbol)}`,
        SymbolDetailSchema,
        {
          signal,
        },
      ),
  });
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <Link to="/symbols" className="text-sm underline">
            {t('symbols.back')}
          </Link>
          <h2 className="text-xl font-semibold">
            {symbol}
            {detail.data?.description && (
              <span className="ml-2 text-base font-normal text-slate-500">{detail.data.description}</span>
            )}
          </h2>
        </div>
        <Link to={`/charts?symbol=${encodeURIComponent(symbol)}`} className="text-sm underline">
          {t('symbols.openChart')}
        </Link>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <QuoteCard quote={quote} />
        {detail.data ? (
          <StateCard
            engineId={engineId}
            symbol={symbol}
            enabled={detail.data.enabled}
            reason={detail.data.reason}
          />
        ) : (
          <Card title={t('symbols.state.title')}>
            {detail.isError ? (
              <p className="text-sm text-slate-500">{t('symbols.notFound')}</p>
            ) : (
              <Loading error={false} />
            )}
          </Card>
        )}
        <ContextCard engineId={engineId} symbol={symbol} />
        {detail.data && <SpecCard spec={detail.data.spec} />}
      </div>
    </div>
  );
}

function SymbolList({ engineId, quotes }: { engineId: string; quotes: Quote[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  const [filter, setFilter] = useState('');
  const catalog = useQuery({
    queryKey: symbolKeys.all(engineId),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(engineId)}/symbols`, SymbolsSchema, { signal }),
  });
  const matches = useMemo(() => {
    const needle = filter.trim().toUpperCase();
    return (catalog.data?.items ?? []).filter(
      (s) =>
        !needle || s.symbol.toUpperCase().includes(needle) || s.description.toUpperCase().includes(needle),
    );
  }, [catalog.data, filter]);
  return (
    <div className="grid gap-4">
      <Card title={t('symbols.traded')}>
        {quotes.length === 0 ? (
          <p className="text-sm text-slate-500">{t('symbols.noTraded')}</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {quotes.map((q) => (
              <li key={q.symbol}>
                <Link
                  to={`/symbols?symbol=${encodeURIComponent(q.symbol)}`}
                  className="block rounded border border-slate-200 p-2 text-sm hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800"
                >
                  <span className="font-semibold">{q.symbol}</span>
                  <span className="ml-2 tabular-nums text-slate-600 dark:text-slate-400">
                    {format.number(q.bid, { maximumFractionDigits: 6 })} /{' '}
                    {format.number(q.ask, { maximumFractionDigits: 6 })}
                  </span>
                  <span className="block text-xs text-slate-500">
                    {t('symbols.quote.spread')}:{' '}
                    {format.number(q.spread_points, { maximumFractionDigits: 1 })}
                    {q.max_spread_points != null &&
                      ` / ${format.number(q.max_spread_points, { maximumFractionDigits: 1 })}`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title={t('symbols.all')}>
        <label className="mb-3 block">
          <span className="sr-only">{t('symbols.search')}</span>
          <input
            type="search"
            value={filter}
            placeholder={t('symbols.search')}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
            className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
        {catalog.data === undefined ? (
          <Loading error={catalog.isError} />
        ) : matches.length === 0 ? (
          <p className="text-sm text-slate-500">{t('symbols.none')}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="py-1 pr-3 font-normal">{t('symbols.search')}</th>
                    <th className="py-1 pr-3 font-normal">{t('symbols.assetClass')}</th>
                    <th className="py-1 font-normal">{t('symbols.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.slice(0, MAX_LISTED).map((s) => (
                    <tr key={s.symbol} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1 pr-3">
                        <Link
                          to={`/symbols?symbol=${encodeURIComponent(s.symbol)}`}
                          className="font-medium underline"
                        >
                          {s.symbol}
                        </Link>
                        {s.description && (
                          <span className="ml-2 text-xs text-slate-500">{s.description}</span>
                        )}
                      </td>
                      <td className="py-1 pr-3">{s.asset_class}</td>
                      <td className="py-1">{t(s.enabled ? 'symbols.enabled' : 'symbols.disabled')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {t('symbols.matches', { shown: Math.min(MAX_LISTED, matches.length), total: matches.length })}
            </p>
          </>
        )}
      </Card>
    </div>
  );
}

/** PLAN §A15 symbols (TAA-906): specification, live quote and spread against its limit, context and state. */
export function SymbolsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [params] = useSearchParams();
  const symbol = params.get('symbol');
  const quotes = useQuotes(id);
  useLiveEvents('decisions', () => {
    void queryClient.invalidateQueries({ queryKey: [...engineKey(id), 'decisions'] });
  });
  useLiveEvents('status', (event) => {
    if (event.type.startsWith('breaker'))
      void queryClient.invalidateQueries({ queryKey: dashboardKeys.breakers(id) });
  });
  const items = quotes.data?.quotes ?? [];
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.symbols')}</h1>
      {symbol === null ? (
        <SymbolList engineId={id} quotes={items} />
      ) : (
        <SymbolDetail engineId={id} symbol={symbol} quote={items.find((q) => q.symbol === symbol)} />
      )}
    </section>
  );
}
