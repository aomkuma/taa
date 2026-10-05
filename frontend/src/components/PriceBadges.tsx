import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';

const TONE = {
  entry: 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200',
  sl: 'border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-200',
  tp: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  rr: 'border-slate-300 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200',
} as const;

function Badge({
  tone,
  label,
  value,
  sub,
}: {
  tone: keyof typeof TONE;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className={`rounded-md border px-2.5 py-1 ${TONE[tone]}`}>
      <div className="text-xs opacity-80">{label}</div>
      <div className="font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-xs tabular-nums opacity-80">{sub}</div>}
    </div>
  );
}

/**
 * The price ladder: the risk range (stop loss → entry, red) and the reward range (entry → take profit, green)
 * to scale, lowest price on the left. SVG attributes only (strict CSP: no inline styles).
 */
function RangeBar({
  entry,
  stop,
  target,
}: {
  entry: number;
  stop: number;
  target: number | null | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const points = [entry, stop, ...(target != null ? [target] : [])];
  const low = Math.min(...points);
  const span = Math.max(...points) - low;
  if (!(span > 0)) return null;
  const x = (value: number) => ((value - low) / span) * 100;
  const range = (a: number, b: number) => ({ x: Math.min(x(a), x(b)), width: Math.abs(x(a) - x(b)) });
  const risk = range(stop, entry);
  const reward = target != null ? range(entry, target) : null;
  const price = (value: number) => format.number(value, { maximumFractionDigits: 6 });
  const label = [
    t('prices.riskRange', { from: price(Math.min(stop, entry)), to: price(Math.max(stop, entry)) }),
    ...(target != null
      ? [
          t('prices.rewardRange', {
            from: price(Math.min(entry, target)),
            to: price(Math.max(entry, target)),
          }),
        ]
      : []),
  ].join(' · ');
  return (
    <figure className="mt-2">
      <svg
        role="img"
        aria-label={label}
        viewBox="0 0 100 6"
        preserveAspectRatio="none"
        className="h-3 w-full"
      >
        <rect width="100" height="6" rx="1" className="fill-slate-100 dark:fill-slate-800" />
        <rect x={risk.x} width={risk.width} height="6" className="fill-red-400 dark:fill-red-600" />
        {reward && (
          <rect
            x={reward.x}
            width={reward.width}
            height="6"
            className="fill-emerald-400 dark:fill-emerald-600"
          />
        )}
        <rect
          x={Math.min(Math.max(x(entry) - 0.4, 0), 99.2)}
          width="0.8"
          height="6"
          className="fill-sky-700 dark:fill-sky-300"
        />
      </svg>
      <figcaption className="mt-1 flex flex-wrap justify-between gap-x-3 text-xs">
        <span className="text-red-700 dark:text-red-400">
          {t('prices.riskRange', { from: price(Math.min(stop, entry)), to: price(Math.max(stop, entry)) })}
        </span>
        {target != null && (
          <span className="text-emerald-700 dark:text-emerald-400">
            {t('prices.rewardRange', {
              from: price(Math.min(entry, target)),
              to: price(Math.max(entry, target)),
            })}
          </span>
        )}
      </figcaption>
    </figure>
  );
}

/** Entry, stop loss and take profit as coloured badges, with each distance from the entry and the RR. */
export function PriceBadges({
  entry,
  stop,
  target,
}: {
  entry: number | null | undefined;
  stop: number | null | undefined;
  target: number | null | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const price = (value: number | null | undefined) => format.number(value, { maximumFractionDigits: 6 });
  const distance = (value: number | null | undefined) =>
    entry != null && value != null
      ? format.number(Math.abs(value - entry), { maximumFractionDigits: 6 })
      : undefined;
  const risk = entry != null && stop != null ? Math.abs(entry - stop) : null;
  const reward = entry != null && target != null ? Math.abs(target - entry) : null;
  const rr = risk && reward != null ? reward / risk : null;
  return (
    <div role="group" aria-label={t('prices.label')}>
      <div className="flex flex-wrap gap-2 text-sm">
        <Badge tone="entry" label={t('prices.entry')} value={price(entry)} />
        <Badge
          tone="sl"
          label={t('prices.stop')}
          value={price(stop)}
          {...(distance(stop) ? { sub: t('prices.distance', { d: distance(stop) }) } : {})}
        />
        <Badge
          tone="tp"
          label={t('prices.target')}
          value={price(target)}
          {...(distance(target) ? { sub: t('prices.distance', { d: distance(target) }) } : {})}
        />
        {rr !== null && (
          <Badge
            tone="rr"
            label={t('prices.rr')}
            value={`1:${format.number(rr, { maximumFractionDigits: 2 })}`}
          />
        )}
      </div>
      {entry != null && stop != null && <RangeBar entry={entry} stop={stop} target={target} />}
    </div>
  );
}
