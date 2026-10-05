/**
 * Small SVG charts of the accuracy page (CSP-safe, no chart library): the calibration plot and the strength
 * buckets. One series each, so one hue (the app's sky) on recessive slate axes; every mark has a <title>
 * tooltip and the cards show the same numbers as a table.
 */
import { useTranslation } from 'react-i18next';

import { useFormat } from '@/i18n/useFormat';

import type { CalibrationPoint } from './accuracyModel';
import type { Summary } from './schemas';

const W = 300;
const H = 200;
const PAD = { left: 32, right: 8, top: 8, bottom: 28 };
const x = (pct: number) => PAD.left + ((W - PAD.left - PAD.right) * pct) / 100;
const y = (pct: number) => H - PAD.bottom - ((H - PAD.top - PAD.bottom) * pct) / 100;
const TICKS = [0, 25, 50, 75, 100];

function Axes({ xLabel, yLabel }: { xLabel: string; yLabel: string }) {
  return (
    <g className="fill-slate-500 stroke-slate-200 text-[9px] dark:stroke-slate-800">
      {TICKS.map((v) => (
        <g key={v}>
          <line x1={x(0)} x2={x(100)} y1={y(v)} y2={y(v)} />
          <text x={PAD.left - 4} y={y(v) + 3} textAnchor="end" stroke="none">
            {v}
          </text>
        </g>
      ))}
      <text x={(x(0) + x(100)) / 2} y={H - 4} textAnchor="middle" stroke="none">
        {xLabel}
      </text>
      <text
        x={10}
        y={(y(0) + y(100)) / 2}
        textAnchor="middle"
        stroke="none"
        transform={`rotate(-90 10 ${String((y(0) + y(100)) / 2)})`}
      >
        {yLabel}
      </text>
    </g>
  );
}

/** Predicted vs observed win rate per bin, the observed rate's 90% interval as a whisker; the diagonal is
 * perfect calibration. */
export function CalibrationPlot({ points }: { points: CalibrationPoint[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  const pct = (v: number) => format.percent(v, { maximumFractionDigits: 0 });
  return (
    <svg viewBox={`0 0 ${String(W)} ${String(H)}`} role="img" aria-label={t('accuracy.calibration.chart')}>
      <Axes xLabel={t('accuracy.calibration.predicted')} yLabel={t('accuracy.calibration.observed')} />
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(100)}
        y2={y(100)}
        strokeDasharray="4 3"
        className="stroke-slate-400 dark:stroke-slate-600"
      />
      {points.map((p) => (
        <g key={p.predicted} className="fill-sky-600 stroke-sky-600 dark:fill-sky-400 dark:stroke-sky-400">
          <title>
            {t('accuracy.calibration.point', {
              predicted: pct(p.predicted),
              observed: pct(p.observed),
              low: pct(p.low),
              high: pct(p.high),
              n: p.n,
            })}
          </title>
          <line x1={x(p.predicted)} x2={x(p.predicted)} y1={y(p.low)} y2={y(p.high)} strokeWidth={2} />
          <circle
            cx={x(p.predicted)}
            cy={y(p.observed)}
            r={4}
            strokeWidth={2}
            className="stroke-white dark:stroke-slate-900"
          />
        </g>
      ))}
    </svg>
  );
}

/** Hit rate per strength bucket with its 90% interval. */
export function BucketChart({ rows }: { rows: [string, Summary][] }) {
  const { t } = useTranslation();
  const format = useFormat();
  const pct = (v: number | null) => format.percent(v, { maximumFractionDigits: 0 });
  const slot = (x(100) - x(0)) / Math.max(rows.length, 1);
  const bar = Math.min(40, slot - 8);
  return (
    <svg viewBox={`0 0 ${String(W)} ${String(H)}`} role="img" aria-label={t('accuracy.buckets.chart')}>
      <Axes xLabel={t('accuracy.buckets.strength')} yLabel={t('accuracy.buckets.hitRate')} />
      {rows.map(([name, s], i) => {
        const cx = x(0) + slot * (i + 0.5);
        const rate = s.hit_rate ?? 0;
        return (
          <g key={name}>
            <title>
              {t('accuracy.buckets.point', {
                bucket: name,
                rate: pct(s.hit_rate),
                low: pct(s.hit_low),
                high: pct(s.hit_high),
                n: s.n,
              })}
            </title>
            <rect
              x={cx - bar / 2}
              y={y(rate)}
              width={bar}
              height={Math.max(y(0) - y(rate), 0)}
              rx={2}
              className="fill-sky-600/80 dark:fill-sky-400/80"
            />
            {s.hit_low !== null && s.hit_high !== null && (
              <line
                x1={cx}
                x2={cx}
                y1={y(s.hit_low)}
                y2={y(s.hit_high)}
                strokeWidth={2}
                className="stroke-slate-700 dark:stroke-slate-300"
              />
            )}
            <text x={cx} y={y(0) + 11} textAnchor="middle" className="fill-slate-500 text-[9px]">
              {name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
