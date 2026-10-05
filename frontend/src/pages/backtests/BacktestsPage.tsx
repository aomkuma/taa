import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';

import { ComparePanel } from './ComparePanel';
import { NewRunForm } from './NewRunForm';
import { PresetName, RunStatus } from './parts';
import { useMetricText } from './useMetricText';
import { RunDetail } from './RunDetail';
import { backtestKeys, OPEN_STATUSES, type Run, RunsPageSchema } from './schemas';

const PAGE = 50;
const MIN_COMPARE = 2;
const MAX_COMPARE = 4;
const POLL_MS = 3_000;

function RunList({
  engineId,
  onOpen,
  onCompare,
  onNew,
}: {
  engineId: string;
  onOpen: (runId: string) => void;
  onCompare: (ids: string[]) => void;
  onNew: () => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const metricText = useMetricText();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const runs = useInfiniteQuery({
    queryKey: backtestKeys.list(engineId),
    queryFn: ({ pageParam, signal }) =>
      apiGet(
        `/engines/${encodeURIComponent(engineId)}/backtests?limit=${String(PAGE)}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`,
        RunsPageSchema,
        { signal },
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // runs are cloud jobs, not engine events: poll while one is queued or running
    refetchInterval: (query) =>
      query.state.data?.pages.some((p) => p.items.some((r) => OPEN_STATUSES.has(r.status))) ? POLL_MS : false,
  });
  useLiveEvents('notifications', () => {
    void queryClient.invalidateQueries({ queryKey: backtestKeys.list(engineId) }); // BACKTEST_FINISHED
  });
  const rows = runs.data?.pages.flatMap((p) => p.items) ?? [];
  const toggle = (run: Run) => {
    setSelected((s) =>
      s.includes(run.run_id)
        ? s.filter((id) => id !== run.run_id)
        : s.length < MAX_COMPARE
          ? [...s, run.run_id]
          : s,
    );
  };
  const canCompare = selected.length >= MIN_COMPARE;
  return (
    <Card
      title={t('backtests.list')}
      action={
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!canCompare}
            onClick={() => {
              onCompare(selected);
            }}
            className="rounded border border-slate-300 px-3 py-1 text-sm disabled:opacity-50 dark:border-slate-700"
          >
            {t('backtests.compareSelected', { n: selected.length })}
          </button>
          <button
            type="button"
            onClick={onNew}
            className="rounded bg-slate-800 px-3 py-1 text-sm font-medium text-white hover:bg-slate-900 dark:bg-slate-700"
          >
            {t('backtests.new')}
          </button>
        </div>
      }
    >
      <p className="mb-2 text-xs text-slate-500">
        {t('backtests.compareHint', { min: MIN_COMPARE, max: MAX_COMPARE })}
      </p>
      {runs.data === undefined ? (
        <p className="text-sm text-slate-500">
          {runs.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('backtests.none')}</p>
      ) : (
        <>
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {rows.map((run) => {
              const m = run.metrics ?? null;
              const label = `${run.request.symbols.join(', ')} · ${format.date(run.request.start)} – ${format.date(run.request.end)}`;
              return (
                <li key={run.run_id} className="flex items-start gap-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    aria-label={t('backtests.select', { run: label })}
                    disabled={run.status !== 'DONE'}
                    checked={selected.includes(run.run_id)}
                    onChange={() => {
                      toggle(run);
                    }}
                    className="mt-1"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      onOpen(run.run_id);
                    }}
                    className="w-full text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <span className="flex flex-wrap justify-between gap-x-3">
                      <span className="font-medium">
                        <PresetName preset={run.preset} /> · {label}
                      </span>
                      <RunStatus run={run} />
                    </span>
                    <span className="block text-xs text-slate-500">
                      {format.dateTime(run.created_at)}
                      {m &&
                        ` · ${t('backtests.listMetrics', {
                          net: metricText('net_profit', m.net_profit),
                          trades: metricText('trades', m.trades),
                          winRate: metricText('win_rate', m.win_rate),
                          pf: metricText('profit_factor', m.profit_factor),
                        })}`}
                      {run.status === 'FAILED' && ` · ${run.error}`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {runs.hasNextPage && (
            <button
              type="button"
              disabled={runs.isFetchingNextPage}
              onClick={() => void runs.fetchNextPage()}
              className="mt-3 text-sm underline"
            >
              {t('trades.closed.more')}
            </button>
          )}
        </>
      )}
      <p className="mt-3 text-xs text-slate-500">{t('backtests.note')}</p>
    </Card>
  );
}

/** PLAN §A15 backtests (TAA-910): run list, run detail, comparison and a new run from presets. */
export function BacktestsPage() {
  const { t } = useTranslation();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const [params, setParams] = useSearchParams();
  const go = (next: Record<string, string>) => {
    setParams(new URLSearchParams(next));
  };
  const run = params.get('run');
  const compare = params.get('compare');
  const creating = params.get('new') === '1';
  const toList = () => {
    go({});
  };
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.backtests')}</h1>
      {run ? (
        <RunDetail engineId={id} runId={run} onBack={toList} />
      ) : compare ? (
        <ComparePanel engineId={id} ids={compare} onBack={toList} />
      ) : (
        <div className="space-y-4">
          {creating && (
            <NewRunForm
              engineId={id}
              onCreated={(runId) => {
                go({ run: runId });
              }}
              onCancel={toList}
            />
          )}
          <RunList
            engineId={id}
            onOpen={(runId) => {
              go({ run: runId });
            }}
            onCompare={(ids) => {
              go({ compare: ids.join(',') });
            }}
            onNew={() => {
              go({ new: '1' });
            }}
          />
        </div>
      )}
    </section>
  );
}
