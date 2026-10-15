import { useTranslation } from 'react-i18next';

import {
  type MapState,
  summarize,
  type Trend,
  TREND_GROUP_NAMES,
  TREND_GROUPS,
  type TrendGroup,
} from './trend';

const ARROW: Record<MapState, string> = { UP: '▲', DOWN: '▼', RANGE: '▬', TRANSITION: '↔', UNKNOWN: '·' };
const TONE: Record<Trend, string> = {
  UP: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  DOWN: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  SIDEWAYS: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  UNCLEAR: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  NONE: 'text-slate-400',
};

type Frames = Partial<Record<string, { state: MapState }>>;

/** The group's trend as a chip, optionally with the state of each of its screens (tide, wave). */
export function TrendBadge({
  frames,
  group,
  detail,
}: {
  frames: Frames | undefined;
  group: TrendGroup;
  detail?: boolean;
}) {
  const { t } = useTranslation();
  const trend = frames === undefined ? 'NONE' : summarize(frames, group);
  if (trend === 'NONE' && !detail) return <span className="text-slate-400">—</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${TONE[trend]}`}>
        {t(`symbols.trend.value.${trend}`)}
      </span>
      {detail && frames !== undefined && (
        <span className="text-xs tabular-nums text-slate-500">
          {TREND_GROUPS[group].map((tf) => {
            const state = frames[tf]?.state;
            return (
              <span key={tf} className="mr-2" title={state ? t(`charts.map.states.${state}`) : undefined}>
                {tf} {state ? ARROW[state] : '–'}
              </span>
            );
          })}
        </span>
      )}
    </span>
  );
}

export function TrendGroupSwitch({
  group,
  onChange,
}: {
  group: TrendGroup;
  onChange: (group: TrendGroup) => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t('symbols.trend.group')}
      className="inline-flex rounded border border-slate-300 text-xs dark:border-slate-700"
    >
      {TREND_GROUP_NAMES.map((g) => (
        <button
          key={g}
          type="button"
          aria-pressed={group === g}
          onClick={() => {
            onChange(g);
          }}
          className={`px-2 py-1 ${group === g ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900' : ''}`}
        >
          {t(`symbols.trend.groups.${g}`)}
        </button>
      ))}
    </div>
  );
}
