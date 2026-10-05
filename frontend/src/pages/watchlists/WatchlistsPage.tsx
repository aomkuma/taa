import { type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApiError } from '@/api/client';
import { useEngine } from '@/engine/context';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { useRanking } from '@/pages/ranking/hooks';

import { usePreferences, useWatchlistMutations } from './hooks';
import { type AlertPreferences, DEFAULT_TOP_N, LIMITS, type Watchlist } from './schemas';
import {
  addSymbols,
  globalThreshold,
  type ListProblem,
  listProblems,
  listThreshold,
  parseSymbols,
  topSymbols,
} from './watchlistModel';

const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const BAD = 'text-sm text-red-700 dark:text-red-400';
const PREVIEW = 12;

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

/** A failed save in words: the plan limit, a taken name, a rejected document, or a plain failure. */
function SaveError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const code = error instanceof ApiError ? error.code : '';
  const text =
    code === 'plan_limit'
      ? t('watchlists.error.planLimit')
      : code === 'watchlist_exists'
        ? t('watchlists.error.exists')
        : code === 'watchlist_not_found'
          ? t('watchlists.error.notFound')
          : code === 'invalid_preferences' && error instanceof ApiError
            ? t('watchlists.error.invalid', { detail: error.message })
            : t('watchlists.error.failed');
  return (
    <p role="alert" className={BAD}>
      {text}
    </p>
  );
}

function Problems({ problems }: { problems: ListProblem[] }) {
  const { t } = useTranslation();
  if (problems.length === 0) return null;
  return (
    <ul className={`${BAD} list-disc pl-5`}>
      {problems.map((p) => (
        <li key={p}>
          {t(`watchlists.problem.${p}`, {
            max: p === 'tooMany' ? LIMITS.listSymbols : LIMITS.listName,
            min: LIMITS.topN[0],
            top: LIMITS.topN[1],
          })}
        </li>
      ))}
    </ul>
  );
}

/** "Alert when win probability ≥ 55%", with a link to the alert settings. */
function Summary({ alerts }: { alerts: AlertPreferences }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <Card title={t('watchlists.summary.title')}>
      <p className="text-sm">
        {t('watchlists.summary.rule', {
          metric: t(`alerts.metric.${alerts.metric}.name`),
          x: format.percent(globalThreshold(alerts)),
        })}
      </p>
      <p className="mt-1 text-xs text-slate-500">{t('watchlists.summary.how')}</p>
      <Link to="/notifications#alert-settings" className="mt-2 inline-block text-sm underline">
        {t('watchlists.summary.edit')}
      </Link>
    </Card>
  );
}

function ThresholdField({
  list,
  alerts,
  onChange,
}: {
  list: Watchlist;
  alerts: AlertPreferences;
  onChange: (threshold: number | null) => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const id = useId();
  const own = list.threshold !== null;
  return (
    <div className="space-y-1">
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={own}
          onChange={(e) => {
            onChange(e.target.checked ? globalThreshold(alerts) : null);
          }}
        />
        {t('watchlists.list.ownThreshold')}
      </label>
      {own ? (
        <div className="flex items-center gap-2">
          <label htmlFor={id} className="sr-only">
            {t('watchlists.list.threshold')}
          </label>
          <input
            id={id}
            type="range"
            min={0}
            max={100}
            step={1}
            value={list.threshold ?? 0}
            className="w-48"
            onChange={(e) => {
              onChange(Number(e.target.value));
            }}
          />
          <span className="text-sm tabular-nums">{format.percent(list.threshold)}</span>
        </div>
      ) : (
        <p className="text-xs text-slate-500">
          {t('watchlists.list.usesGlobal', { x: format.percent(globalThreshold(alerts)) })}
        </p>
      )}
    </div>
  );
}

function SymbolEditor({
  list,
  suggestions,
  onChange,
}: {
  list: Watchlist;
  suggestions: readonly string[];
  onChange: (symbols: string[]) => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [text, setText] = useState('');
  const [invalid, setInvalid] = useState<string[]>([]);
  const add = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = parseSymbols(text);
    setInvalid(parsed.invalid);
    if (parsed.valid.length > 0) onChange(addSymbols(list.symbols, parsed.valid));
    setText(parsed.invalid.join(' '));
  };
  return (
    <div className="space-y-2">
      {list.symbols.length === 0 ? (
        <p className="text-sm text-slate-500">
          {list.kind === 'FAVOURITES' ? t('watchlists.list.noFavourites') : t('watchlists.list.empty')}
        </p>
      ) : (
        <ul className="flex flex-wrap gap-1.5" aria-label={t('watchlists.list.symbols')}>
          {list.symbols.map((symbol) => (
            <li
              key={symbol}
              className="flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-sm dark:bg-slate-800"
            >
              {symbol}
              <button
                type="button"
                className="text-slate-500 hover:text-red-700"
                aria-label={t('watchlists.list.remove', { symbol })}
                onClick={() => {
                  onChange(list.symbols.filter((s) => s !== symbol));
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="flex flex-wrap gap-2" onSubmit={add}>
        <label htmlFor={id} className="sr-only">
          {t('watchlists.list.addLabel')}
        </label>
        <input
          id={id}
          className={`${INPUT} w-48`}
          list={`${id}-symbols`}
          placeholder={t('watchlists.list.addPlaceholder')}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
        />
        <datalist id={`${id}-symbols`}>
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <button type="submit" className={BUTTON} disabled={text.trim() === ''}>
          {t('watchlists.list.add')}
        </button>
      </form>
      {invalid.length > 0 && (
        <p role="alert" className={BAD}>
          {t('watchlists.list.invalidSymbols', { symbols: invalid.join(', ') })}
        </p>
      )}
    </div>
  );
}

function TopNEditor({
  list,
  ranked,
  onChange,
}: {
  list: Watchlist;
  ranked: { symbol: string; rank: number }[] | undefined;
  onChange: (topN: number) => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const n = list.top_n ?? DEFAULT_TOP_N;
  const now = ranked === undefined ? null : topSymbols(ranked, n);
  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-2">
        <label htmlFor={id}>{t('watchlists.list.topN')}</label>
        <input
          id={id}
          type="number"
          min={LIMITS.topN[0]}
          max={LIMITS.topN[1]}
          step={1}
          className={`${INPUT} w-20`}
          value={Number.isFinite(n) ? n : ''}
          onChange={(e) => {
            onChange(e.target.value === '' ? Number.NaN : Number(e.target.value));
          }}
        />
      </div>
      <p className="text-xs text-slate-500">{t('watchlists.list.topNHow')}</p>
      {now !== null &&
        (now.length === 0 ? (
          <p className="text-xs text-slate-500">{t('watchlists.list.noRanking')}</p>
        ) : (
          <p className="text-xs">
            {t('watchlists.list.topNow', {
              symbols: now.slice(0, PREVIEW).join(', '),
              more: now.length > PREVIEW ? t('watchlists.list.andMore', { n: now.length - PREVIEW }) : '',
            })}
          </p>
        ))}
    </div>
  );
}

function ListCard({
  saved,
  alerts,
  others,
  ranked,
}: {
  saved: Watchlist;
  alerts: AlertPreferences;
  others: string[];
  ranked: { symbol: string; rank: number }[] | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const nameId = useId();
  const { replace, remove } = useWatchlistMutations();
  const [draft, setDraft] = useState(saved);
  const [base, setBase] = useState(saved);
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (JSON.stringify(base) !== JSON.stringify(saved)) {
    // saved here or changed elsewhere (a favourite toggled on the ranking page): start again from it
    setBase(saved);
    setDraft(saved);
    setConfirmDelete(false);
  }
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const problems = listProblems(draft, others);
  const change = (patch: Partial<Watchlist>) => {
    replace.reset();
    setDraft((old) => ({ ...old, ...patch }));
  };
  const suggestions = ranked?.map((r) => r.symbol).filter((s) => !draft.symbols.includes(s)) ?? [];
  return (
    <Card
      title={saved.kind === 'FAVOURITES' ? t('watchlists.kind.FAVOURITES') : saved.name}
      action={
        <span className="flex items-center gap-2 text-xs">
          {saved.kind !== 'FAVOURITES' && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 dark:bg-slate-800">
              {t(`watchlists.kind.${saved.kind}`)}
            </span>
          )}
          <span className={saved.alerts ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500'}>
            {saved.alerts
              ? t('watchlists.list.alertsAt', { x: format.percent(listThreshold(saved, alerts)) })
              : t('watchlists.list.alertsOff')}
          </span>
        </span>
      }
    >
      <div className="space-y-3">
        {saved.kind !== 'FAVOURITES' && (
          <div className="text-sm">
            <label htmlFor={nameId} className="block font-medium">
              {t('watchlists.list.name')}
            </label>
            <input
              id={nameId}
              className={`${INPUT} mt-1 w-64`}
              maxLength={LIMITS.listName}
              value={draft.name}
              onChange={(e) => {
                change({ name: e.target.value });
              }}
            />
          </div>
        )}
        {saved.kind === 'AUTO_TOP_N' ? (
          <TopNEditor
            list={draft}
            ranked={ranked}
            onChange={(topN) => {
              change({ top_n: topN });
            }}
          />
        ) : (
          <SymbolEditor
            list={draft}
            suggestions={suggestions}
            onChange={(symbols) => {
              change({ symbols });
            }}
          />
        )}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.alerts}
            onChange={(e) => {
              change({ alerts: e.target.checked });
            }}
          />
          {t('watchlists.list.alerts')}
        </label>
        {draft.alerts && (
          <ThresholdField
            list={draft}
            alerts={alerts}
            onChange={(threshold) => {
              change({ threshold });
            }}
          />
        )}
        <Problems problems={problems} />
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={PRIMARY}
            disabled={!dirty || problems.length > 0 || replace.isPending}
            onClick={() => {
              replace.mutate({ name: saved.name, list: { ...draft, name: draft.name.trim() } });
            }}
          >
            {t('watchlists.list.save')}
          </button>
          {dirty && (
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                replace.reset();
                setDraft(saved);
              }}
            >
              {t('watchlists.list.undo')}
            </button>
          )}
          {saved.kind !== 'FAVOURITES' &&
            (confirmDelete ? (
              <>
                <button
                  type="button"
                  className={`${BUTTON} text-red-700 dark:text-red-400`}
                  disabled={remove.isPending}
                  onClick={() => {
                    remove.mutate(saved.name);
                  }}
                >
                  {t('watchlists.list.confirmDelete', { name: saved.name })}
                </button>
                <button
                  type="button"
                  className="text-sm underline"
                  onClick={() => {
                    setConfirmDelete(false);
                  }}
                >
                  {t('watchlists.list.keep')}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="ml-auto text-sm text-red-700 underline dark:text-red-400"
                onClick={() => {
                  setConfirmDelete(true);
                }}
              >
                {t('watchlists.list.delete')}
              </button>
            ))}
        </div>
        {replace.isSuccess && !dirty && (
          <p role="status" className="text-sm text-slate-600 dark:text-slate-400">
            {t('watchlists.list.saved')}
          </p>
        )}
        {(replace.error ?? remove.error) && <SaveError error={replace.error ?? remove.error} />}
      </div>
    </Card>
  );
}

function NewListCard({ lists }: { lists: Watchlist[] }) {
  const { t } = useTranslation();
  const nameId = useId();
  const { create } = useWatchlistMutations();
  const hasTop = lists.some((w) => w.kind === 'AUTO_TOP_N');
  const [name, setName] = useState('');
  const [kind, setKind] = useState<'CUSTOM' | 'AUTO_TOP_N'>('CUSTOM');
  const list: Watchlist = {
    name: name.trim(),
    kind,
    symbols: [],
    top_n: kind === 'AUTO_TOP_N' ? DEFAULT_TOP_N : null,
    alerts: true,
    threshold: null,
  };
  const problems =
    name === ''
      ? []
      : listProblems(
          list,
          lists.map((w) => w.name),
        );
  const full = lists.length >= LIMITS.lists;
  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    create.mutate(list, {
      onSuccess: () => {
        setName('');
        setKind('CUSTOM');
      },
    });
  };
  return (
    <Card title={t('watchlists.new.title')}>
      {full ? (
        <p className="text-sm text-slate-500">{t('watchlists.new.full', { n: LIMITS.lists })}</p>
      ) : (
        <form className="space-y-2" onSubmit={submit}>
          <div className="text-sm">
            <label htmlFor={nameId} className="block font-medium">
              {t('watchlists.list.name')}
            </label>
            <input
              id={nameId}
              className={`${INPUT} mt-1 w-64`}
              maxLength={LIMITS.listName}
              value={name}
              onChange={(e) => {
                create.reset();
                setName(e.target.value);
              }}
            />
          </div>
          <fieldset className="flex flex-wrap gap-4 text-sm">
            <legend className="sr-only">{t('watchlists.new.kind')}</legend>
            {(['CUSTOM', 'AUTO_TOP_N'] as const).map((k) => (
              <label key={k} className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name={`${nameId}-kind`}
                  checked={kind === k}
                  disabled={k === 'AUTO_TOP_N' && hasTop}
                  onChange={() => {
                    setKind(k);
                  }}
                />
                {t(`watchlists.kind.${k}`)}
              </label>
            ))}
          </fieldset>
          {hasTop && <p className="text-xs text-slate-500">{t('watchlists.new.oneTop')}</p>}
          <Problems problems={problems} />
          <button
            type="submit"
            className={PRIMARY}
            disabled={name.trim() === '' || problems.length > 0 || create.isPending}
          >
            {t('watchlists.new.create')}
          </button>
          {create.error && <SaveError error={create.error} />}
        </form>
      )}
    </Card>
  );
}

/**
 * PLAN §A28 Watchlists (TAA-918): favourites, custom lists and the auto top-N, each with its alert switch and
 * an optional threshold override. Lists decide which symbols may alert the user; they never change what the
 * bot trades (§A26).
 */
export function WatchlistsPage() {
  const { t } = useTranslation();
  const { engineId } = useEngine();
  const prefs = usePreferences();
  const ranking = useRanking(engineId ?? '');
  const ranked = ranking.data?.items;
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.watchlists')}</h1>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{t('watchlists.intro')}</p>
      {prefs.data === undefined ? (
        <Loading error={prefs.isError} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="flex flex-col gap-4">
            {prefs.data.watchlists.map((list, index) => (
              <ListCard
                // by position, so a rename keeps the card (and its "saved" note)
                key={index}
                saved={list}
                alerts={prefs.data.alerts}
                others={prefs.data.watchlists.filter((w) => w !== list).map((w) => w.name)}
                ranked={ranked}
              />
            ))}
          </div>
          <div className="flex flex-col gap-4">
            <Summary alerts={prefs.data.alerts} />
            <NewListCard lists={prefs.data.watchlists} />
          </div>
        </div>
      )}
    </section>
  );
}
