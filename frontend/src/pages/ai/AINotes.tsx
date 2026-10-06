import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { useAINotes, useNoteText } from './hooks';
import type { AINote } from './schemas';

function Label({ note }: { note: AINote }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <p className="mt-2 text-xs text-slate-500">
      {t('aiNotes.label')} · {format.dateTime(note.created_at)}
      {note.model ? ` · ${note.model}` : ''}
    </p>
  );
}

/** The latest answered narrative of a ranking snapshot or of recent shadow results, labelled as AI opinion. */
export function AINarrative({ kind }: { kind: 'RANKING' | 'ANALYTICS' }) {
  const { t } = useTranslation();
  const notes = useAINotes(kind, 14);
  const note = notes.data?.items.find((n) => n.status === 'OK');
  if (note === undefined) return null;
  return (
    <Card title={t(`aiNotes.title.${kind}`)}>
      <NarrativeText note={note} />
    </Card>
  );
}

function NarrativeText({ note }: { note: AINote }) {
  const text = useNoteText(note);
  return (
    <>
      <p className="text-sm leading-relaxed">{text}</p>
      <Label note={note} />
    </>
  );
}

/** The AI's opinion on one opportunity (TAA-1305): verdict, reasons and narrative, labelled as opinion. */
export function AIOpinion({ note }: { note: AINote | null | undefined }) {
  const { t } = useTranslation();
  if (!note) return null;
  return (
    <Card title={t('aiNotes.title.OPPORTUNITY')}>
      {note.status === 'OK' && note.verdict ? (
        <>
          <p className="text-sm font-medium">
            {t(`ai.verdict.${note.verdict}`, { confidence: note.confidence ?? 0 })}
          </p>
          <OpinionBody note={note} />
        </>
      ) : (
        <p className="text-sm text-slate-500">{t('aiNotes.unavailable', { status: note.status })}</p>
      )}
    </Card>
  );
}

function OpinionBody({ note }: { note: AINote }) {
  const text = useNoteText(note);
  return (
    <>
      {text && <p className="mt-1 text-sm leading-relaxed">{text}</p>}
      {note.reasons.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">
          {note.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      <Label note={note} />
    </>
  );
}

/** The opinions' accuracy, calibration and the alert filter's evaluation (AI page). */
export function AIOpinionStats() {
  const { t } = useTranslation();
  const format = useFormat();
  const notes = useAINotes('OPPORTUNITY', 90);
  const data = notes.data;
  if (data === undefined || data.stats === null || data.filter === null) return null;
  const s = data.stats;
  const f = data.filter;
  const pct = (v: number | null) =>
    v === null ? '—' : format.percent(v * 100, { maximumFractionDigits: 0 });
  const r = (v: number | null) =>
    v === null ? '—' : format.number(v, { maximumFractionDigits: 2, signDisplay: 'exceptZero' });
  return (
    <Card title={t('aiNotes.stats.title')}>
      {data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('aiNotes.none')}</p>
      ) : (
        <div className="flex flex-col gap-3 text-sm">
          <p>
            {t('aiNotes.stats.summary', {
              n: format.number(s.judged),
              right: pct(s.right_rate),
              base: pct(s.base_win_rate),
            })}
          </p>
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 font-normal">{t('aiNotes.stats.verdict')}</th>
                <th className="py-1 font-normal">n</th>
                <th className="py-1 font-normal">{t('aiNotes.stats.winRate')}</th>
                <th className="py-1 font-normal">{t('aiNotes.stats.avgR')}</th>
              </tr>
            </thead>
            <tbody>
              {(['AGREE', 'DISAGREE', 'UNSURE'] as const).map((v) => {
                const row = s.verdicts[v];
                return (
                  <tr key={v} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1">{t(`aiNotes.verdict.${v}`)}</td>
                    <td className="py-1 tabular-nums">{format.number(row?.n ?? 0)}</td>
                    <td className="py-1 tabular-nums">{pct(row?.win_rate ?? null)}</td>
                    <td className="py-1 tabular-nums">{r(row?.avg_r ?? null)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {s.brier !== null && (
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('aiNotes.stats.brier', {
                ai: format.number(s.brier, { maximumFractionDigits: 3 }),
                base: format.number(s.brier_baseline, { maximumFractionDigits: 3 }),
              })}
            </p>
          )}
          {s.calibration.length > 0 && (
            <ul className="text-xs text-slate-600 dark:text-slate-400">
              {s.calibration.map((b) => (
                <li key={b.low}>
                  {t('aiNotes.stats.bucket', {
                    low: pct(b.low),
                    high: pct(b.high),
                    n: format.number(b.n),
                    implied: pct(b.implied),
                    observed: pct(b.observed),
                  })}
                </li>
              ))}
            </ul>
          )}
          <p>
            {f.offered
              ? t('aiNotes.filter.offered', { kept: r(f.avg_r_kept), all: r(f.avg_r_all) })
              : t('aiNotes.filter.notOffered', {
                  kept: format.number(f.n_kept),
                  all: format.number(f.n_all),
                  minKept: format.number(f.min_kept),
                  minAll: format.number(f.min_all),
                })}
          </p>
          <p className="text-xs text-slate-500">
            {t('aiNotes.stats.cost', { cost: format.money(data.cost_usd, 'USD') })} · {t('ai.simulated')}
          </p>
        </div>
      )}
    </Card>
  );
}
