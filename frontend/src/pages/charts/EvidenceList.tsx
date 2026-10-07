import { useTranslation } from 'react-i18next';

import { evidenceName } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';

import { FAMILY_COLORS, FOCUS_EVIDENCE, RELATIONS, type RelatedEvidence, type Relation } from './model';

const BUTTON = 'rounded border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-700';

/**
 * A signal's evidence, grouped by how it relates to the signal (TAA-925): each item is drawn only while it is
 * ticked, and a signal opens with its strongest supporting items. Conflicting and neutral items stay folded
 * until one of them is shown.
 */
export function EvidenceList({
  items,
  shown,
  focus,
  onChange,
  invalidations,
  onInvalidations,
}: {
  items: readonly RelatedEvidence[];
  shown: ReadonlySet<string>;
  focus: ReadonlySet<string>;
  onChange: (ids: ReadonlySet<string>) => void;
  invalidations: boolean;
  onInvalidations: (on: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  if (items.length === 0) return <p className="mt-2 text-xs text-slate-500">{t('charts.evidenceNone')}</p>;

  const toggle = (id: string, on: boolean) => {
    const next = new Set(shown);
    if (on) next.add(id);
    else next.delete(id);
    onChange(next);
  };
  const group = (relation: Relation, list: readonly RelatedEvidence[]) => (
    <ul className="mt-1 grid gap-x-4 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
      {list.map(({ evidence: e }) => (
        <li key={e.evidence_id}>
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={shown.has(e.evidence_id)}
              onChange={(event) => {
                toggle(e.evidence_id, event.target.checked);
              }}
            />
            <svg aria-hidden="true" viewBox="0 0 10 10" className="h-2.5 w-2.5 shrink-0">
              <circle cx="5" cy="5" r="5" fill={FAMILY_COLORS[e.family] ?? '#64748b'} />
            </svg>
            <span className={relation === 'CONFLICTS' ? 'text-red-700 dark:text-red-400' : undefined}>
              {evidenceName(i18n, e.detector_id, e.name)}
            </span>
            <span className="text-xs whitespace-nowrap text-slate-500">
              {t('charts.evidenceMeta', {
                tf: e.timeframe,
                quality: format.number(e.quality * 100, { maximumFractionDigits: 0 }),
              })}
            </span>
          </label>
        </li>
      ))}
    </ul>
  );

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500">{t('charts.evidence')}</span>
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            onChange(new Set(focus));
          }}
        >
          {t('charts.evidenceFocus')}
        </button>
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            onChange(new Set(items.map((e) => e.evidence.evidence_id)));
          }}
        >
          {t('charts.evidenceAll')}
        </button>
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            onChange(new Set());
          }}
        >
          {t('charts.evidenceHideAll')}
        </button>
        <label className="ml-auto flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={invalidations}
            onChange={(event) => {
              onInvalidations(event.target.checked);
            }}
          />
          {t('charts.showInvalidations')}
        </label>
      </div>
      <p className="mt-1 text-xs text-slate-500">{t('charts.evidenceHint', { n: FOCUS_EVIDENCE })}</p>
      {RELATIONS.map((relation) => {
        const list = items.filter((e) => e.relation === relation);
        if (list.length === 0) return null;
        const title = t(`charts.relation.${relation}`, { n: list.length });
        if (relation === 'SUPPORTS') {
          return (
            <fieldset key={relation} className="mt-2">
              <legend className="text-xs font-medium">{title}</legend>
              {group(relation, list)}
            </fieldset>
          );
        }
        return (
          <details key={relation} className="mt-2" open={list.some((e) => shown.has(e.evidence.evidence_id))}>
            <summary className="cursor-pointer text-xs font-medium">{title}</summary>
            {group(relation, list)}
          </details>
        );
      })}
    </div>
  );
}
