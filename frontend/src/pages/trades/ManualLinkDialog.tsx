import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiDelete, apiGet, apiPut } from '@/api/client';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';

import {
  CandidatesSchema,
  type LinkChoice,
  type ManualTrade,
  manualKeys,
  manualPath,
  ManualTradeSchema,
} from './manualSchemas';

/**
 * The owner corrects which signal a manual trade followed (TAA-1006): the engine's link is right, it was the
 * owner's own idea, or it followed another signal on the same symbol and side. Never changes trading.
 */
export function ManualLinkDialog({
  engineId,
  trade,
  onClose,
}: {
  engineId: string;
  trade: ManualTrade;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const queryClient = useQueryClient();
  const titleId = useId();
  const current = trade.effective;
  const initial: string =
    current.source === 'AUTO'
      ? current.followed
        ? 'CONFIRMED'
        : 'OWN_IDEA'
      : current.followed
        ? `S:${current.signal_key ?? ''}`
        : 'OWN_IDEA';
  const [picked, setPicked] = useState(initial);
  const candidates = useQuery({
    queryKey: manualKeys.candidates(engineId, trade.position_id),
    queryFn: ({ signal }) =>
      apiGet(manualPath(engineId, `/${String(trade.position_id)}/candidates`), CandidatesSchema, { signal }),
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);
  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: manualKeys.all(engineId) });
    onClose();
  };
  const save = useMutation({
    mutationFn: () => {
      const choice: LinkChoice = picked.startsWith('S:') ? 'SIGNAL' : (picked as LinkChoice);
      const body = choice === 'SIGNAL' ? { choice, signal_key: picked.slice(2) } : { choice };
      return apiPut(manualPath(engineId, `/${String(trade.position_id)}/link`), body, ManualTradeSchema);
    },
    onSuccess: done,
  });
  const reset = useMutation({
    mutationFn: () => apiDelete(manualPath(engineId, `/${String(trade.position_id)}/link`)),
    onSuccess: done,
  });
  const option = (value: string, label: string, hint?: string) => (
    <label key={value} className="flex items-start gap-2 py-1">
      <input
        type="radio"
        name={titleId}
        value={value}
        checked={picked === value}
        onChange={() => {
          setPicked(value);
        }}
        className="mt-1"
      />
      <span>
        {label}
        {hint && <span className="block text-xs text-slate-500">{hint}</span>}
      </span>
    </label>
  );
  const auto = trade.auto;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="absolute inset-0 h-full w-full bg-slate-900/50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded bg-white p-4 text-sm shadow-xl dark:bg-slate-900"
      >
        <h2 id={titleId} className="mb-2 text-lg font-semibold">
          {t('trades.manual.dialog.title', { symbol: trade.symbol, ticket: trade.ticket })}
        </h2>
        <p className="mb-2 text-slate-600 dark:text-slate-400">{t('trades.manual.dialog.body')}</p>
        <fieldset>
          <legend className="sr-only">
            {t('trades.manual.dialog.title', { symbol: trade.symbol, ticket: trade.ticket })}
          </legend>
          {auto.confidence !== 'UNMATCHED' &&
            auto.strategy !== null &&
            option(
              'CONFIRMED',
              t('trades.manual.dialog.confirm', {
                strategy: translateCode(i18n, 'strategyName', auto.strategy),
              }),
            )}
          {option('OWN_IDEA', t('trades.manual.dialog.own'))}
          {candidates.data === undefined ? (
            <p className="py-1 text-slate-500">
              {candidates.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
            </p>
          ) : (
            candidates.data.items
              .filter((c) => c.signal_key !== auto.opportunity_id || auto.confidence === 'UNMATCHED')
              .map((c) =>
                option(
                  `S:${c.signal_key}`,
                  t('trades.manual.dialog.signal', {
                    strategy: translateCode(i18n, 'strategyName', c.strategy),
                    entry: format.number(c.entry, { maximumFractionDigits: 6 }),
                    time: format.dateTime(c.issued_at),
                  }),
                  c.qualifies
                    ? t('trades.manual.dialog.fits', {
                        r: format.number(c.distance_r, { maximumFractionDigits: 2 }),
                      })
                    : t('trades.manual.dialog.outside', {
                        r: format.number(c.distance_r, { maximumFractionDigits: 2 }),
                      }),
                ),
              )
          )}
        </fieldset>
        {(save.isError || reset.isError) && (
          <p role="alert" className="mt-2 text-red-700 dark:text-red-400">
            {t('trades.manual.dialog.failed')}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={save.isPending || picked === ''}
            onClick={() => {
              save.mutate();
            }}
            className="rounded bg-slate-900 px-3 py-1.5 font-medium text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('trades.manual.dialog.save')}
          </button>
          {current.source === 'OWNER' && (
            <button
              type="button"
              disabled={reset.isPending}
              onClick={() => {
                reset.mutate();
              }}
              className="rounded border border-slate-300 px-3 py-1.5 dark:border-slate-700"
            >
              {t('trades.manual.dialog.reset')}
            </button>
          )}
          <button type="button" onClick={onClose} className="px-3 py-1.5 underline">
            {t('trades.manual.dialog.cancel')}
          </button>
        </div>
      </div>
    </div>
  );
}
