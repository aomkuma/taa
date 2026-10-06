import { type ReactNode, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';

import { ApiError } from '@/api/client';
import { useFormat } from '@/i18n/useFormat';
import { useAINotes } from '@/pages/ai/hooks';
import { Card } from '@/pages/dashboard/cards';
import { usePreferences, useSaveAlerts } from '@/pages/watchlists/hooks';
import {
  ALERT_METRICS,
  type AlertPreferences,
  DEFAULT_THRESHOLD,
  LIMITS,
  RISK_FULL_POLICIES,
  type UserWindow,
} from '@/pages/watchlists/schemas';
import {
  type AlertProblem,
  alertProblems,
  globalThreshold,
  newWindow,
  toggleDay,
  weekdayNames,
  windowValid,
} from '@/pages/watchlists/watchlistModel';

const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const BAD = 'text-sm text-red-700 dark:text-red-400';
/** The element id the watchlists page links to. */
const ANCHOR = 'alert-settings';
const TIMEZONES = [
  'Asia/Bangkok',
  'UTC',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Europe/London',
  'America/New_York',
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
      <legend className="pr-2 text-sm font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function NumberField({
  label,
  value,
  range,
  onChange,
}: {
  label: string;
  value: number;
  range: readonly [number, number];
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="number"
        min={range[0]}
        max={range[1]}
        step={1}
        className={`${INPUT} w-24`}
        value={Number.isFinite(value) ? value : ''}
        onChange={(e) => {
          onChange(e.target.value === '' ? Number.NaN : Number(e.target.value));
        }}
      />
    </div>
  );
}

/** TAA-1305: the opt-in AI alert filter; it acts only while offered (it beat the baseline). */
function AIFilterToggle({ checked, onChange }: { checked: boolean; onChange: (on: boolean) => void }) {
  const { t } = useTranslation();
  const notes = useAINotes('OPPORTUNITY', 90);
  if (notes.isError && !checked) return null; // the plan has no AI feature
  const offered = notes.data?.filter?.offered ?? false;
  return (
    <div className="space-y-1">
      <Check label={t('alerts.delivery.aiFilter')} checked={checked} onChange={onChange} />
      <p className="pl-6 text-xs text-slate-500">
        {offered ? t('alerts.delivery.aiFilterOffered') : t('alerts.delivery.aiFilterNotOffered')}
      </p>
    </div>
  );
}

function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => {
          onChange(e.target.checked);
        }}
      />
      {label}
    </label>
  );
}

function WindowRow({
  index,
  window,
  onChange,
  onRemove,
}: {
  index: number;
  window: UserWindow;
  onChange: (window: UserWindow) => void;
  onRemove: () => void;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const names = weekdayNames(i18n.language === 'th' ? 'th-TH' : 'en-GB');
  return (
    <li
      aria-label={t('alerts.windows.window', { n: index + 1 })}
      className="space-y-1.5 rounded border border-slate-200 p-2 dark:border-slate-800"
    >
      <div className="flex flex-wrap gap-2 text-sm">
        {names.map((name, day) => (
          <label key={name} className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={window.days.includes(day)}
              onChange={() => {
                onChange({ ...window, days: toggleDay(window.days, day) });
              }}
            />
            {name}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor={`${id}-start`}>{t('alerts.windows.from')}</label>
        <input
          id={`${id}-start`}
          type="time"
          className={INPUT}
          value={window.start}
          onChange={(e) => {
            onChange({ ...window, start: e.target.value });
          }}
        />
        <label htmlFor={`${id}-end`}>{t('alerts.windows.to')}</label>
        <input
          id={`${id}-end`}
          type="time"
          className={INPUT}
          value={window.end}
          onChange={(e) => {
            onChange({ ...window, end: e.target.value });
          }}
        />
        <button type="button" className="ml-auto text-sm underline" onClick={onRemove}>
          {t('alerts.windows.remove')}
        </button>
      </div>
      {!windowValid(window) && (
        <p className={BAD}>
          {window.days.length === 0 ? t('alerts.windows.noDays') : t('alerts.windows.badTime')}
        </p>
      )}
    </li>
  );
}

function WindowsEditor({
  alerts,
  change,
}: {
  alerts: AlertPreferences;
  change: (patch: Partial<AlertPreferences>) => void;
}) {
  const { t } = useTranslation();
  const zoneId = useId();
  const zones = TIMEZONES.includes(alerts.timezone) ? TIMEZONES : [alerts.timezone, ...TIMEZONES];
  const setWindows = (windows: UserWindow[]) => {
    change({ windows });
  };
  return (
    <>
      <div className="flex items-center gap-2 text-sm">
        <label htmlFor={zoneId}>{t('alerts.windows.timezone')}</label>
        <select
          id={zoneId}
          className={INPUT}
          value={alerts.timezone}
          onChange={(e) => {
            change({ timezone: e.target.value });
          }}
        >
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </div>
      {alerts.windows.length === 0 ? (
        <p className="text-sm text-slate-500">{t('alerts.windows.anyTime')}</p>
      ) : (
        <ul className="space-y-2">
          {alerts.windows.map((window, i) => (
            <WindowRow
              // windows have no identity of their own; the position is the identity
              key={i}
              index={i}
              window={window}
              onChange={(w) => {
                setWindows(alerts.windows.map((old, j) => (j === i ? w : old)));
              }}
              onRemove={() => {
                setWindows(alerts.windows.filter((_, j) => j !== i));
              }}
            />
          ))}
        </ul>
      )}
      <button
        type="button"
        className={BUTTON}
        disabled={alerts.windows.length >= LIMITS.windows}
        onClick={() => {
          setWindows([...alerts.windows, newWindow()]);
        }}
      >
        {t('alerts.windows.add')}
      </button>
      <p className="text-xs text-slate-500">{t('alerts.windows.note')}</p>
    </>
  );
}

function AlertForm({ saved }: { saved: AlertPreferences }) {
  const { t } = useTranslation();
  const format = useFormat();
  const xId = useId();
  const langId = useId();
  const save = useSaveAlerts();
  const [draft, setDraft] = useState(saved);
  const [base, setBase] = useState(saved);
  if (JSON.stringify(base) !== JSON.stringify(saved)) {
    setBase(saved);
    setDraft(saved);
  }
  const change = (patch: Partial<AlertPreferences>) => {
    save.reset();
    setDraft((old) => ({ ...old, ...patch }));
  };
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const problems = alertProblems(draft);
  const x = globalThreshold(draft);
  const error = save.error;
  return (
    <div className="space-y-4">
      <Section title={t('alerts.metric.title')}>
        {ALERT_METRICS.map((metric) => (
          <div key={metric} className="text-sm">
            <label className="flex items-center gap-2 font-medium">
              <input
                type="radio"
                name={`${xId}-metric`}
                aria-describedby={`${xId}-${metric}`}
                checked={draft.metric === metric}
                onChange={() => {
                  change({ metric });
                }}
              />
              {t(`alerts.metric.${metric}.name`)}
            </label>
            <p id={`${xId}-${metric}`} className="pl-6 text-xs text-slate-500">
              {t(`alerts.metric.${metric}.about`)}
            </p>
          </div>
        ))}
      </Section>

      <Section title={t('alerts.threshold.title')}>
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor={xId} className="text-sm">
            {t('alerts.threshold.label')}
          </label>
          <input
            id={xId}
            type="range"
            min={0}
            max={100}
            step={1}
            className="w-56"
            value={x}
            onChange={(e) => {
              change({ threshold: Number(e.target.value) });
            }}
          />
          <span className="text-sm font-semibold tabular-nums">{format.percent(x)}</span>
          {draft.threshold === null ? (
            <span className="text-xs text-slate-500">{t('alerts.threshold.isDefault')}</span>
          ) : (
            <button
              type="button"
              className="text-sm underline"
              onClick={() => {
                change({ threshold: null });
              }}
            >
              {t('alerts.threshold.reset', { x: format.percent(DEFAULT_THRESHOLD[draft.metric]) })}
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">
          {draft.metric === 'WIN_PROBABILITY' ? t('alerts.threshold.floor') : t('alerts.threshold.strength')}
        </p>
        <p className="text-xs text-slate-500">{t('alerts.threshold.perList')}</p>
      </Section>

      <Section title={t('alerts.timing.title')}>
        <NumberField
          label={t('alerts.timing.lifetime')}
          value={draft.signal_lifetime_bars}
          range={LIMITS.lifetimeBars}
          onChange={(signal_lifetime_bars) => {
            change({ signal_lifetime_bars });
          }}
        />
        <Check
          label={t('alerts.timing.sessions')}
          checked={draft.respect_market_sessions}
          onChange={(respect_market_sessions) => {
            change({ respect_market_sessions });
          }}
        />
      </Section>

      <Section title={t('alerts.windows.title')}>
        <WindowsEditor alerts={draft} change={change} />
      </Section>

      <Section title={t('alerts.rate.title')}>
        <NumberField
          label={t('alerts.rate.perHour')}
          value={draft.rate_limits.max_alerts_per_hour}
          range={LIMITS.alertsPerHour}
          onChange={(max_alerts_per_hour) => {
            change({ rate_limits: { ...draft.rate_limits, max_alerts_per_hour } });
          }}
        />
        <NumberField
          label={t('alerts.rate.cooldown')}
          value={draft.rate_limits.symbol_cooldown_minutes}
          range={LIMITS.cooldownMinutes}
          onChange={(symbol_cooldown_minutes) => {
            change({ rate_limits: { ...draft.rate_limits, symbol_cooldown_minutes } });
          }}
        />
      </Section>

      <Section title={t('alerts.delivery.title')}>
        <Check
          label={t('alerts.delivery.expiry')}
          checked={draft.expiry_updates}
          onChange={(expiry_updates) => {
            change({ expiry_updates });
          }}
        />
        <p className="text-sm">{t('alerts.delivery.riskFull')}</p>
        {RISK_FULL_POLICIES.map((policy) => (
          <label key={policy} className="flex items-center gap-2 pl-4 text-sm">
            <input
              type="radio"
              name={`${xId}-risk`}
              checked={draft.when_risk_full === policy}
              onChange={() => {
                change({ when_risk_full: policy });
              }}
            />
            {t(`alerts.delivery.policy.${policy}`)}
          </label>
        ))}
        <AIFilterToggle
          checked={draft.ai_filter}
          onChange={(ai_filter) => {
            change({ ai_filter });
          }}
        />
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor={langId}>{t('alerts.delivery.language')}</label>
          <select
            id={langId}
            className={INPUT}
            value={draft.language}
            onChange={(e) => {
              change({ language: e.target.value === 'en' ? 'en' : 'th' });
            }}
          >
            <option value="th">ไทย</option>
            <option value="en">English</option>
          </select>
        </div>
      </Section>

      {problems.length > 0 && (
        <ul className={`${BAD} list-disc pl-5`}>
          {problems.map((p: AlertProblem) => (
            <li key={p}>{t(`alerts.problem.${p}`)}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={PRIMARY}
          disabled={!dirty || problems.length > 0 || save.isPending}
          onClick={() => {
            save.mutate(draft);
          }}
        >
          {t('alerts.save')}
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
            {t('alerts.undo')}
          </button>
        )}
        {save.isSuccess && !dirty && (
          <span role="status" className="text-sm text-slate-600 dark:text-slate-400">
            {t('alerts.saved')}
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className={BAD}>
          {error instanceof ApiError && error.code === 'invalid_preferences'
            ? t('alerts.invalid', { detail: error.message })
            : t('alerts.failed')}
        </p>
      )}
    </div>
  );
}

/** PLAN §A28 Alert settings (TAA-918): who gets an opportunity push, when, and how often (§A26). */
export function AlertSettingsCard() {
  const { t } = useTranslation();
  const prefs = usePreferences();
  const { hash } = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // the watchlists page links here (`/notifications#alert-settings`)
    const element = ref.current;
    if (hash === `#${ANCHOR}` && element && 'scrollIntoView' in element) element.scrollIntoView();
  }, [hash]);
  return (
    <div id={ANCHOR} ref={ref} className="scroll-mt-4">
      <Card title={t('alerts.title')}>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">{t('alerts.intro')}</p>
        {prefs.data === undefined ? (
          <p className="text-sm text-slate-500">
            {prefs.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
          </p>
        ) : (
          <AlertForm saved={prefs.data.alerts} />
        )}
      </Card>
    </div>
  );
}
