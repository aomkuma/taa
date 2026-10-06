import { useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { AIOpinionStats } from './AINotes';
import { AIAssessmentsSchema, type AIAssessments, aiKeys } from './schemas';

const DAYS = [7, 30, 90, 366] as const;

function Summary({ data }: { data: AIAssessments }) {
  const { t } = useTranslation();
  const format = useFormat();
  const s = data.summary;
  const pct = (v: number | null) =>
    v === null ? '—' : format.percent(v * 100, { maximumFractionDigits: 0 });
  const usd = (v: number) => format.money(v, 'USD');
  const tiles: [string, string][] = [
    [t('ai.summary.calls'), format.number(s.calls)],
    [t('ai.summary.agreement'), pct(s.agreement_rate)],
    [t('ai.summary.vetoed'), format.number(s.vetoed)],
    [t('ai.summary.unavailable'), format.number(s.unavailable)],
    [t('ai.summary.right'), s.with_outcome ? `${pct(s.right_rate)} (${format.number(s.with_outcome)})` : '—'],
    [t('ai.summary.cost'), usd(s.cost_usd)],
    [t('ai.summary.costToday'), usd(s.cost_today_usd)],
    [
      t('ai.summary.latency'),
      s.avg_latency_ms === null
        ? '—'
        : t('ai.seconds', { n: format.number(s.avg_latency_ms / 1000, { maximumFractionDigits: 1 }) }),
    ],
  ];
  return (
    <>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {tiles.map(([label, value]) => (
          <div key={label} className="rounded border border-slate-200 p-2 dark:border-slate-800">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {s.with_outcome > 0 && (
        <p className="mt-2 text-sm">
          {t('ai.outcomes', { agree: pct(s.win_rate_when_agree), disagree: pct(s.win_rate_when_disagree) })}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-500">
        {t('ai.models', { models: s.models.join(', ') || '—' })} · {t('ai.simulated')}
      </p>
    </>
  );
}

/**
 * PLAN §A15 "AI" (TAA-1304): the AI's reviews of proposed entries, how often it agreed, how its verdicts
 * compare with what the signals did afterwards (simulated), and what it cost. The AI can only veto.
 */
export function AIPage() {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const id = engineId ?? '';
  const daysId = useId();
  const [days, setDays] = useState<number>(30);
  const list = useQuery({
    queryKey: aiKeys.list(id, days),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/ai-assessments?days=${String(days)}`, AIAssessmentsSchema, {
        signal,
      }),
    enabled: engineId !== null,
  });
  const data = list.data;
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.ai')}</h1>
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">{t('ai.intro')}</p>
      <div className="mb-4 flex items-center gap-1.5 text-sm">
        <label htmlFor={daysId}>{t('analytics.days.label')}</label>
        <select
          id={daysId}
          value={days}
          onChange={(e) => {
            setDays(Number(e.target.value));
          }}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900"
        >
          {DAYS.map((d) => (
            <option key={d} value={d}>
              {t('analytics.days.n', { n: d })}
            </option>
          ))}
        </select>
      </div>
      <div className="mb-4">
        <AIOpinionStats />
      </div>
      {data === undefined ? (
        <p className="text-sm text-slate-500">
          {list.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <Card title={t('ai.summary.title')}>
            {data.summary.calls === 0 && data.items.length === 0 ? (
              <p className="text-sm text-slate-500">{t('ai.none')}</p>
            ) : (
              <Summary data={data} />
            )}
          </Card>
          {data.items.length > 0 && (
            <Card title={t('ai.list')}>
              <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
                {data.items.map((a) => (
                  <li key={a.assessment_id} className="py-2">
                    <span className="flex flex-wrap justify-between gap-2">
                      <span>
                        <span className="font-medium">
                          {a.symbol} {a.side}
                        </span>{' '}
                        <span className="text-xs text-slate-500">
                          {translateCode(i18n, 'strategyName', a.strategy)} · {format.dateTime(a.created_at)}
                        </span>
                      </span>
                      <span className="font-medium">
                        {a.verdict
                          ? t(`ai.verdict.${a.verdict}`, { confidence: a.confidence ?? 0 })
                          : t('ai.status', { status: a.status })}{' '}
                        <span className="text-xs text-slate-500">
                          · {t(`ai.effect.${a.effect as 'PASSED'}`)}
                        </span>
                      </span>
                    </span>
                    {a.reasons.length > 0 && (
                      <ul className="mt-1 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">
                        {a.reasons.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    )}
                    {a.outcome && (
                      <span className="mt-1 block text-xs text-slate-500">
                        {t('ai.outcome', {
                          result: a.outcome.win === null ? '—' : a.outcome.win ? t('ai.won') : t('ai.lost'),
                          r: format.number(a.outcome.r, {
                            maximumFractionDigits: 2,
                            signDisplay: 'exceptZero',
                          }),
                        })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}
