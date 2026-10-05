import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/client';
import { useEngine } from '@/engine/context';
import { evidenceName, FAMILIES, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { useScoreboard } from '@/pages/opportunities/hooks';
import type { Scoreboard } from '@/pages/opportunities/schemas';
import { usePreferences } from '@/pages/watchlists/hooks';
import { CONFLICT_POLICIES, type Theories } from '@/pages/watchlists/schemas';

import { FamilyDiagram } from './diagrams';
import { useCatalog, useEntitlements, useSaveTheories } from './hooks';
import type { Bound, Detector } from './schemas';
import {
  choosePreset,
  customized,
  detectorOn,
  familyOn,
  invalidParams,
  lockedFamilies,
  PRESET_NAMES,
  paramValue,
  resetParams,
  setDetector,
  setFamily,
  setParam,
  setSetup,
  setupOn,
  withinBound,
} from './theoryModel';

const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const INPUT =
  'w-24 rounded border border-slate-300 bg-white px-2 py-0.5 text-sm dark:border-slate-700 dark:bg-slate-950';
const BADGE = 'rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800';
const RECORDS = 3;

function TierBadge({ tier }: { tier: Detector['tier'] }) {
  const { t } = useTranslation();
  return (
    <span className={BADGE} title={t(`theories.tier.${tier}`)}>
      {tier}
      <span className="sr-only">: {t(`theories.tier.${tier}`)}</span>
    </span>
  );
}

/** A theory's hypothetical record per asset class and timeframe (the scoreboard's rows for it). */
function Records({ scoreboard, theory }: { scoreboard: Scoreboard | undefined; theory: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const rows = (scoreboard?.items ?? []).filter((r) => r.theory === theory).sort((a, b) => b.n - a.n);
  if (rows.length === 0) return <p className="text-xs text-slate-500">{t('theories.record.none')}</p>;
  return (
    <ul className="text-xs text-slate-600 dark:text-slate-400">
      {rows.slice(0, RECORDS).map((row) => {
        const [assetClass = '', timeframe = ''] = row.group;
        return (
          <li key={`${assetClass}|${timeframe}`}>
            {t('theories.record.row', {
              group: `${translateCode(i18n, 'assetClass', assetClass)} ${timeframe}`,
              rate: format.percent(row.hit_rate, { maximumFractionDigits: 0 }),
              n: row.n,
              lift:
                typeof row.lift === 'number'
                  ? `×${format.number(row.lift, { maximumFractionDigits: 2 })}`
                  : '—',
            })}
          </li>
        );
      })}
    </ul>
  );
}

function ParamField({
  name,
  bound,
  value,
  onChange,
}: {
  name: string;
  bound: Bound;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const label = i18n.exists(`theories.param.label.${name}`)
    ? t(`theories.param.label.${name as 'max_age_bars'}`)
    : name;
  if (bound.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(e) => {
            onChange(e.target.checked);
          }}
        />
        {label}
      </label>
    );
  }
  const ok = withinBound(bound, value);
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor={id} className="min-w-40">
        {label}
      </label>
      <input
        id={id}
        type="number"
        className={`${INPUT} ${ok ? '' : 'border-red-500'}`}
        min={bound.min}
        max={bound.max}
        step={bound.type === 'integer' ? 1 : 'any'}
        aria-invalid={!ok}
        value={typeof value === 'number' && Number.isFinite(value) ? value : ''}
        onChange={(e) => {
          onChange(e.target.value === '' ? Number.NaN : Number(e.target.value));
        }}
      />
      <span className={`text-xs ${ok ? 'text-slate-500' : 'text-red-700 dark:text-red-400'}`}>
        {t('theories.param.range', {
          min: `${bound.min_exclusive ? '>' : ''}${String(bound.min)}`,
          max: `${bound.max_exclusive ? '<' : ''}${String(bound.max)}`,
        })}
      </span>
    </div>
  );
}

function DetectorRow({
  detector,
  theories,
  locked,
  own,
  scoreboard,
  change,
}: {
  detector: Detector;
  theories: Theories;
  locked: boolean;
  own: boolean;
  scoreboard: Scoreboard | undefined;
  change: (next: Theories) => void;
}) {
  const { t } = useTranslation();
  const { i18n } = useTranslation();
  const name = evidenceName(i18n, detector.id, detector.name);
  const bounds = Object.entries(detector.bounds);
  const changed = theories.params[detector.id] !== undefined;
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            disabled={locked}
            checked={!locked && detectorOn(theories, detector)}
            onChange={(e) => {
              change(setDetector(theories, detector, e.target.checked));
            }}
          />
          {name}
        </label>
        <TierBadge tier={detector.tier} />
      </div>
      <div className="pl-6">
        <Records scoreboard={scoreboard} theory={`ev:${detector.family}:${detector.id}`} />
        {own && bounds.length > 0 && (
          <details className="mt-1">
            <summary className="cursor-pointer text-xs text-slate-600 dark:text-slate-400">
              {t('theories.param.title')}
              {changed && ` · ${t('theories.param.changed')}`}
            </summary>
            <div className="mt-2 space-y-1.5">
              {bounds.map(([param, bound]) => (
                <ParamField
                  key={param}
                  name={param}
                  bound={bound}
                  value={paramValue(theories, detector, param)}
                  onChange={(value) => {
                    change(setParam(theories, detector, param, value));
                  }}
                />
              ))}
              <button
                type="button"
                className="text-xs underline disabled:opacity-50"
                disabled={!changed}
                onClick={() => {
                  change(resetParams(theories, detector.id));
                }}
              >
                {t('theories.param.reset')}
              </button>
            </div>
          </details>
        )}
      </div>
    </li>
  );
}

function FamilyCard({
  family,
  detectors,
  theories,
  locked,
  own,
  scoreboard,
  change,
}: {
  family: string;
  detectors: Detector[];
  theories: Theories;
  locked: boolean;
  own: boolean;
  scoreboard: Scoreboard | undefined;
  change: (next: Theories) => void;
}) {
  const { t, i18n } = useTranslation();
  const name = translateCode(i18n, 'family', family);
  const on = !locked && familyOn(theories, family);
  const active = detectors.filter((d) => !locked && detectorOn(theories, d)).length;
  return (
    <Card
      title={name}
      action={
        locked ? (
          <span className={BADGE}>🔒 {t('theories.locked')}</span>
        ) : (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={on}
              onChange={(e) => {
                change(setFamily(theories, family, e.target.checked, detectors));
              }}
            />
            {t('theories.familyOn')}
          </label>
        )
      }
    >
      <div className="flex gap-3">
        <FamilyDiagram family={family} label={t('theories.diagram', { family: name })} />
        <div className="space-y-1">
          <p className="text-sm text-slate-700 dark:text-slate-300">
            {t(`theories.about.${family as 'LEVELS'}`)}
          </p>
          <Records scoreboard={scoreboard} theory={family} />
        </div>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-sm">
          {t('theories.detectors', { on: active, total: detectors.length })}
        </summary>
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {detectors.map((d) => (
            <DetectorRow
              key={d.id}
              detector={d}
              theories={theories}
              locked={locked}
              own={own}
              scoreboard={scoreboard}
              change={change}
            />
          ))}
        </ul>
      </details>
    </Card>
  );
}

function RulesCard({ theories, change }: { theories: Theories; change: (next: Theories) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const n = theories.min_supporting_families;
  return (
    <Card title={t('theories.rules.title')}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={id}>{t('theories.rules.minSupporting')}</label>
          <input
            id={id}
            type="number"
            min={1}
            max={FAMILIES.length}
            step={1}
            className={INPUT}
            value={Number.isFinite(n) ? n : ''}
            onChange={(e) => {
              change({
                ...theories,
                min_supporting_families: e.target.value === '' ? Number.NaN : Number(e.target.value),
              });
            }}
          />
        </div>
        <fieldset className="space-y-1">
          <legend className="mb-1">{t('theories.rules.conflict')}</legend>
          {CONFLICT_POLICIES.map((policy) => (
            <label key={policy} className="flex items-center gap-2">
              <input
                type="radio"
                name={`${id}-conflict`}
                checked={theories.conflict_policy === policy}
                onChange={() => {
                  change({ ...theories, conflict_policy: policy });
                }}
              />
              {t(`theories.rules.policy.${policy}`)}
            </label>
          ))}
        </fieldset>
        <p className="text-xs text-slate-500">{t('theories.rules.profile')}</p>
      </div>
    </Card>
  );
}

function PresetsCard({ theories, change }: { theories: Theories; change: (next: Theories) => void }) {
  const { t } = useTranslation();
  return (
    <Card
      title={t('theories.presets.title')}
      action={customized(theories) && <span className={BADGE}>{t('theories.presets.customized')}</span>}
    >
      <div role="group" aria-label={t('theories.presets.title')} className="flex flex-wrap gap-2">
        {PRESET_NAMES.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={theories.preset === preset && !customized(theories)}
            className={`${BUTTON} ${theories.preset === preset ? 'border-sky-600 font-medium' : ''}`}
            onClick={() => {
              change(choosePreset(theories, preset));
            }}
          >
            {t(`theories.presets.name.${preset as 'ALL'}`)}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-500">{t('theories.presets.note')}</p>
    </Card>
  );
}

function SetupsCard({
  names,
  theories,
  change,
}: {
  names: string[];
  theories: Theories;
  change: (next: Theories) => void;
}) {
  const { t, i18n } = useTranslation();
  return (
    <Card title={t('theories.setups.title')}>
      <p className="mb-2 text-xs text-slate-500">{t('theories.setups.note')}</p>
      <div className="space-y-1">
        {names.map((name) => (
          <label key={name} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={setupOn(theories, name)}
              onChange={(e) => {
                change(setSetup(theories, name, e.target.checked));
              }}
            />
            {translateCode(i18n, 'strategyName', name)}
          </label>
        ))}
      </div>
    </Card>
  );
}

function TheoriesForm({ saved }: { saved: Theories }) {
  const { t } = useTranslation();
  const { engineId, own } = useEngine();
  const catalog = useCatalog();
  const entitlements = useEntitlements();
  const scoreboard = useScoreboard(engineId ?? '');
  const save = useSaveTheories();
  const [draft, setDraft] = useState(saved);
  const [base, setBase] = useState(saved);
  if (JSON.stringify(base) !== JSON.stringify(saved)) {
    setBase(saved);
    setDraft(saved);
  }
  const change = (next: Theories) => {
    save.reset();
    setDraft(next);
  };
  if (catalog.data === undefined) {
    return (
      <p className="text-sm text-slate-500">
        {catalog.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
      </p>
    );
  }
  const detectors = catalog.data.detectors;
  const locked = lockedFamilies(entitlements.data?.families);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const badParams = invalidParams(draft, detectors);
  const n = draft.min_supporting_families;
  const badN = !Number.isInteger(n) || n < 1 || n > FAMILIES.length;
  const error = save.error;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <PresetsCard theories={draft} change={change} />
        <RulesCard theories={draft} change={change} />
      </div>
      {locked.size > 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('theories.lockedNote')}</p>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {FAMILIES.map((family) => (
          <FamilyCard
            key={family}
            family={family}
            detectors={detectors.filter((d) => d.family === family)}
            theories={draft}
            locked={locked.has(family)}
            own={own}
            scoreboard={scoreboard.data}
            change={change}
          />
        ))}
      </div>
      <SetupsCard names={catalog.data.pattern_strategies} theories={draft} change={change} />
      {!own && <p className="text-xs text-slate-500">{t('theories.param.feed')}</p>}
      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-slate-200 bg-white/95 py-2 dark:border-slate-800 dark:bg-slate-950/95">
        <button
          type="button"
          className={PRIMARY}
          disabled={!dirty || badN || badParams.length > 0 || save.isPending}
          onClick={() => {
            save.mutate(draft);
          }}
        >
          {t('theories.save')}
        </button>
        {dirty && (
          <button
            type="button"
            className={BUTTON}
            onClick={() => {
              save.reset();
              setDraft(saved);
            }}
          >
            {t('theories.undo')}
          </button>
        )}
        {save.isSuccess && !dirty && (
          <span role="status" className="text-sm text-slate-600 dark:text-slate-400">
            {t('theories.saved')}
          </span>
        )}
        {badN && (
          <span className="text-sm text-red-700 dark:text-red-400">
            {t('theories.rules.badN', { max: FAMILIES.length })}
          </span>
        )}
        {badParams.length > 0 && (
          <span className="text-sm text-red-700 dark:text-red-400">{t('theories.param.invalid')}</span>
        )}
        {error && (
          <span role="alert" className="text-sm text-red-700 dark:text-red-400">
            {error instanceof ApiError && error.code === 'invalid_preferences'
              ? t('theories.invalid', { detail: error.message })
              : t('theories.failed')}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * PLAN §A30 theory & condition selection (TAA-920): presets, family and detector toggles with tiers, each
 * theory's hypothetical record, the minimum supporting families, the conflict policy, which pattern setups may
 * alert and the bounded detector parameters (the engine owner's only: they change the shared scan).
 */
export function TheoriesPage() {
  const { t } = useTranslation();
  const prefs = usePreferences();
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.theories')}</h1>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{t('theories.intro')}</p>
      {prefs.data === undefined ? (
        <p className="text-sm text-slate-500">
          {prefs.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
        </p>
      ) : (
        <TheoriesForm saved={prefs.data.theories} />
      )}
    </section>
  );
}
