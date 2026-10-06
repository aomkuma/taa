import { type ReactNode, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { ApiError } from '@/api/client';
import { useEngine } from '@/engine/context';
import { ASSET_CLASSES, translateCode } from '@/i18n/codes';
import { explain } from '@/i18n/explain';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { useFavourites } from '@/pages/watchlists/hooks';
import { AINarrative } from '@/pages/ai/AINotes';

import { useRanking } from './hooks';
import {
  defaultDirection,
  explainParams,
  filterItems,
  isEligible,
  presentClasses,
  requiredEquity,
  type SortDirection,
  type SortKey,
  sortItems,
} from './rankingModel';
import { RankingDrawer } from './RankingDrawer';
import type { Ranking, RankingItem } from './schemas';

const PAGE = 100;

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{children}</dd>
    </div>
  );
}

/** Equity, balance, leverage and risk per trade the ranking was sized for (PLAN §A28 account header). */
function AccountHeader({ ranking }: { ranking: Ranking }) {
  const { t } = useTranslation();
  const format = useFormat();
  const account = ranking.account;
  const currency = account?.currency ?? 'USD';
  const personal = ranking.personal === true;
  return (
    <Card
      title={t('ranking.account.title')}
      action={
        ranking.computed_at && (
          <span className="text-xs text-slate-500">
            {t('ranking.account.asOf', { time: format.dateTime(ranking.computed_at) })}
          </span>
        )
      }
    >
      {account == null || (personal && account.equity == null) ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t(personal ? 'ranking.account.noProfile' : 'ranking.account.unknown')}
        </p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Figure label={t('ranking.account.equity')}>{format.money(account.equity, currency)}</Figure>
            <Figure label={t('ranking.account.balance')}>{format.money(account.balance, currency)}</Figure>
            <Figure label={t('ranking.account.leverage')}>
              {account.leverage != null
                ? t('ranking.account.leverageValue', { leverage: format.number(account.leverage) })
                : '—'}
            </Figure>
            <Figure label={t('ranking.account.riskPercent')}>{format.percent(account.risk_percent)}</Figure>
          </dl>
          {personal && <p className="mt-2 text-xs text-slate-500">{t('ranking.account.yours')}</p>}
          {ranking.universe != null && ranking.items.length < ranking.universe && (
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
              {t('ranking.account.partial', { ranked: ranking.items.length, universe: ranking.universe })}
            </p>
          )}
        </>
      )}
    </Card>
  );
}

function Chip({
  tone,
  title,
  children,
}: {
  tone: 'ok' | 'bad' | 'muted';
  title?: string;
  children: ReactNode;
}) {
  const colour = {
    ok: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
    bad: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
    muted: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  }[tone];
  return (
    <span title={title} className={`inline-block rounded px-1.5 py-0.5 text-xs ${colour}`}>
      {children}
    </span>
  );
}

/** Gate chips (the gates that did not pass, with their explanation as the title), the equity hint, flags. */
function GateChips({ item }: { item: RankingItem }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const needs = requiredEquity(item);
  const ownBlock = item.personal && item.personal.eligible === false && item.personal.affordable === false;
  return (
    <div className="flex flex-wrap gap-1">
      {item.gates.length === 0 && !ownBlock && (
        <Chip tone={isEligible(item) ? 'ok' : 'muted'}>
          {t(isEligible(item) ? 'ranking.allPassed' : 'ranking.notRated')}
        </Chip>
      )}
      {item.gates.map((g) => (
        <Chip
          key={g.gate}
          tone={g.status === 'FAIL' ? 'bad' : 'muted'}
          title={explain(i18n, g.key, explainParams(g.params))}
        >
          {translateCode(i18n, 'gate', g.gate)}
        </Chip>
      ))}
      {ownBlock && <Chip tone="bad">{translateCode(i18n, 'gate', 'G2_MIN_LOT')}</Chip>}
      {needs && (
        <span className="text-xs text-red-700 dark:text-red-400">
          {t('ranking.needsEquity', { amount: format.money(needs.value, needs.currency) })}
        </span>
      )}
      {item.market_open === false && <Chip tone="muted">{t('ranking.marketClosed')}</Chip>}
    </div>
  );
}

function SortHeader({
  column,
  label,
  sort,
  onSort,
  className = '',
}: {
  column: SortKey;
  label: string;
  sort: { key: SortKey; direction: SortDirection };
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const { t } = useTranslation();
  const active = sort.key === column;
  const ariaSort = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none';
  return (
    <th aria-sort={ariaSort} className={`py-1 pr-3 font-normal ${className}`}>
      <button
        type="button"
        onClick={() => {
          onSort(column);
        }}
        className="underline-offset-2 hover:underline"
        title={t('ranking.sortBy', { column: label })}
      >
        {label}
        {active && <span aria-hidden="true">{sort.direction === 'asc' ? ' ▲' : ' ▼'}</span>}
      </button>
    </th>
  );
}

function FavouriteButton({
  symbol,
  on,
  busy,
  onToggle,
}: {
  symbol: string;
  on: boolean;
  busy: boolean;
  onToggle: (symbol: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={t(on ? 'ranking.favourite.remove' : 'ranking.favourite.add', { symbol })}
      disabled={busy}
      onClick={() => {
        onToggle(symbol);
      }}
      className={`text-lg leading-none ${on ? 'text-amber-500' : 'text-slate-400 hover:text-amber-500'}`}
    >
      {on ? '★' : '☆'}
    </button>
  );
}

function RankingTable({
  items,
  personal,
  onOpen,
}: {
  items: RankingItem[];
  personal: boolean;
  onOpen: (symbol: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { favourites, toggle } = useFavourites();
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: 'rank',
    direction: 'asc',
  });
  const [shown, setShown] = useState(PAGE);
  const sorted = useMemo(() => sortItems(items, sort.key, sort.direction), [items, sort]);
  const onSort = (key: SortKey) => {
    setSort((old) =>
      old.key === key
        ? { key, direction: old.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: defaultDirection(key) },
    );
  };
  const score = (value: number) => format.number(value, { maximumFractionDigits: 1 });
  const toggleError =
    toggle.error instanceof ApiError && toggle.error.code === 'plan_limit'
      ? 'ranking.favourite.planLimit'
      : toggle.isError
        ? 'ranking.favourite.failed'
        : null;
  return (
    <>
      {toggleError && (
        <p role="alert" className="mb-2 text-sm text-red-700 dark:text-red-400">
          {t(toggleError)}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-1 pr-2 font-normal">
                <span className="sr-only">{t('ranking.col.favourite')}</span>
              </th>
              <SortHeader column="rank" label={t('ranking.col.rank')} sort={sort} onSort={onSort} />
              <SortHeader column="symbol" label={t('ranking.col.symbol')} sort={sort} onSort={onSort} />
              <SortHeader
                column="now"
                label={t('ranking.col.now')}
                sort={sort}
                onSort={onSort}
                className="text-right"
              />
              <SortHeader
                column="overall"
                label={t('ranking.col.overall')}
                sort={sort}
                onSort={onSort}
                className="text-right"
              />
              <th className="py-1 pr-3 font-normal">{t('ranking.col.gates')}</th>
              {!personal && <th className="py-1 text-right font-normal">{t('ranking.col.lot')}</th>}
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, shown).map((item) => (
              <tr
                key={item.symbol}
                className={`border-t border-slate-100 align-top dark:border-slate-800 ${isEligible(item) ? '' : 'text-slate-500'}`}
              >
                <td className="py-1 pr-2">
                  <FavouriteButton
                    symbol={item.symbol}
                    on={favourites.has(item.symbol)}
                    busy={toggle.isPending && toggle.variables === item.symbol}
                    onToggle={(symbol) => {
                      toggle.mutate(symbol);
                    }}
                  />
                </td>
                <td className="py-1 pr-3 tabular-nums">{item.rank}</td>
                <td className="py-1 pr-3">
                  <button
                    type="button"
                    onClick={() => {
                      onOpen(item.symbol);
                    }}
                    className="font-medium text-slate-900 underline dark:text-slate-100"
                  >
                    {item.symbol}
                  </button>
                  <span className="block text-xs text-slate-500">
                    {translateCode(i18n, 'assetClass', item.asset_class)}
                  </span>
                </td>
                <td className="py-1 pr-3 text-right font-semibold tabular-nums">{score(item.now_score)}</td>
                <td className="py-1 pr-3 text-right tabular-nums">{score(item.overall)}</td>
                <td className="py-1 pr-3">
                  <GateChips item={item} />
                </td>
                {!personal && (
                  <td className="py-1 text-right tabular-nums">
                    {format.number(item.metrics.lot, { maximumFractionDigits: 2 })}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>{t('ranking.shown', { shown: Math.min(shown, sorted.length), total: sorted.length })}</span>
        {shown < sorted.length && (
          <button
            type="button"
            onClick={() => {
              setShown((n) => n + PAGE);
            }}
            className="rounded border border-slate-300 px-2 py-0.5 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
          >
            {t('ranking.showMore')}
          </button>
        )}
      </div>
    </>
  );
}

function RankingList({ ranking, onOpen }: { ranking: Ranking; onOpen: (symbol: string) => void }) {
  const { t, i18n } = useTranslation();
  const [assetClass, setAssetClass] = useState<string | null>(null);
  const [eligibleOnly, setEligibleOnly] = useState(false);
  const [search, setSearch] = useState('');
  const classes = useMemo(() => presentClasses(ranking.items, ASSET_CLASSES), [ranking.items]);
  const items = useMemo(
    () => filterItems(ranking.items, { assetClass, eligibleOnly, search }),
    [ranking.items, assetClass, eligibleOnly, search],
  );
  const eligible = ranking.items.filter(isEligible).length;
  const input =
    'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';
  return (
    <Card
      title={t('ranking.list.title')}
      action={
        <span className="text-xs text-slate-500">
          {t('ranking.list.eligible', { eligible, total: ranking.items.length })}
        </span>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-xs text-slate-500">{t('ranking.filter.class')}</span>
          <select
            value={assetClass ?? ''}
            onChange={(event) => {
              setAssetClass(event.target.value || null);
            }}
            className={input}
          >
            <option value="">{t('ranking.filter.allClasses')}</option>
            {classes.map((c) => (
              <option key={c} value={c}>
                {translateCode(i18n, 'assetClass', c)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="sr-only">{t('ranking.filter.search')}</span>
          <input
            type="search"
            value={search}
            placeholder={t('ranking.filter.search')}
            onChange={(event) => {
              setSearch(event.target.value);
            }}
            className={input}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={eligibleOnly}
            onChange={(event) => {
              setEligibleOnly(event.target.checked);
            }}
          />
          {t('ranking.filter.eligibleOnly')}
        </label>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('ranking.list.none')}</p>
      ) : (
        <RankingTable
          key={`${assetClass ?? ''}|${String(eligibleOnly)}|${search}`}
          items={items}
          personal={ranking.personal === true}
          onOpen={onOpen}
        />
      )}
      <p className="mt-3 text-xs text-slate-500">{t('ranking.advice')}</p>
    </Card>
  );
}

/** PLAN §A25/§A28 symbol ranking (TAA-916): account header, sortable Now/Overall table, gates and a drawer. */
export function RankingPage() {
  const { t } = useTranslation();
  const { engineId, state } = useEngine();
  const id = engineId ?? '';
  const [params, setParams] = useSearchParams();
  const open = params.get('symbol');
  const ranking = useRanking(id);
  const setOpen = useCallback(
    (symbol: string | null) => {
      setParams(
        (old) => {
          const next = new URLSearchParams(old);
          if (symbol === null) next.delete('symbol');
          else next.set('symbol', symbol);
          return next;
        },
        { replace: symbol === null },
      );
    },
    [setParams],
  );
  const onClose = useCallback(() => {
    setOpen(null);
  }, [setOpen]);
  const notYet = ranking.error instanceof ApiError && ranking.error.code === 'advisory_not_found';
  let body: ReactNode;
  if (state === 'ready' && engineId === null)
    body = <p className="text-sm text-slate-500">{t('ranking.noEngine')}</p>;
  else if (notYet || ranking.data?.items.length === 0)
    body = <p className="text-sm text-slate-500">{t('ranking.empty')}</p>;
  else if (ranking.data === undefined)
    body = ranking.isError ? (
      <p role="alert" className="text-sm text-red-700 dark:text-red-400">
        {t('dashboard.loadFailed')}
      </p>
    ) : (
      <p className="text-sm text-slate-500">{t('dashboard.loading')}</p>
    );
  else
    body = (
      <div className="grid gap-4">
        <AccountHeader ranking={ranking.data} />
        <RankingList ranking={ranking.data} onOpen={setOpen} />
      </div>
    );
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.ranking')}</h1>
      <div className="mb-4">
        <AINarrative kind="RANKING" />
      </div>
      {body}
      {open !== null && engineId !== null && (
        <RankingDrawer
          engineId={engineId}
          symbol={open}
          item={ranking.data?.items.find((i) => i.symbol === open)}
          onClose={onClose}
        />
      )}
    </section>
  );
}
