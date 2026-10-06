import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApiError } from '@/api/client';
import { useServerNow } from '@/app/useNow';
import { useEngine } from '@/engine/context';
import { evidenceName, translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';
import { AIOpinion } from '@/pages/ai/AINotes';

import { useOpportunity, useScoreboard } from './hooks';
import {
  chartLink,
  evidenceByRelation,
  splitContributions,
  supportingFamilies,
  trackRecord,
  windowState,
} from './opportunityModel';
import { Metrics, Money, Prices, SideBadge, StatusBadge } from './parts';
import type { Contribution, EvidenceRef, OpportunityDetail as Detail, Scoreboard } from './schemas';

/** A contribution in points as an SVG bar from the middle (supporting right, conflicting left). */
function PointsBar({ points, max }: { points: number; max: number }) {
  const half = max > 0 ? (Math.min(Math.abs(points), max) / max) * 50 : 0;
  return (
    <svg
      viewBox="0 0 100 4"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="mt-0.5 h-1.5 w-full rounded"
    >
      <rect width="100" height="4" className="fill-slate-100 dark:fill-slate-800" />
      <rect x="49.75" width="0.5" height="4" className="fill-slate-400" />
      <rect
        x={points >= 0 ? 50 : 50 - half}
        width={half}
        height="4"
        className={points >= 0 ? 'fill-emerald-500' : 'fill-red-500'}
      />
    </svg>
  );
}

function ContributionRow({
  c,
  max,
  detail,
  scoreboard,
  own,
}: {
  c: Contribution;
  max: number;
  detail: Detail;
  scoreboard: Scoreboard | undefined;
  own: boolean;
}) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const record = trackRecord(scoreboard, c.feature, detail.asset_class, detail.timeframe);
  const evidence = detail.evidence.find((e) => e.item.evidence.detector_id === c.detector);
  return (
    <li className="mb-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>
          {evidenceName(i18n, c.detector, evidence?.item.evidence.name ?? c.detector)}
          <span className="ml-1 text-xs text-slate-500">{translateCode(i18n, 'family', c.family)}</span>
        </span>
        <span
          className={`font-medium tabular-nums ${c.points >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}
        >
          {t('opportunities.why.points', {
            points: format.number(c.points, { maximumFractionDigits: 1, signDisplay: 'exceptZero' }),
          })}
        </span>
      </div>
      <PointsBar points={c.points} max={max} />
      <p className="text-xs text-slate-500">
        {record
          ? t('opportunities.why.record', {
              hit: format.percent(record.hitRate, { maximumFractionDigits: 0 }),
              n: record.n,
              r: format.number(record.expectancyR, { maximumFractionDigits: 2, signDisplay: 'exceptZero' }),
            })
          : t('opportunities.why.noRecord')}
        {own && evidence && (
          <>
            {' · '}
            <Link
              to={chartLink(detail.symbol, detail.opportunity_id, evidence.item.evidence.timeframe)}
              className="underline"
            >
              {t('opportunities.why.showOnChart', { tf: evidence.item.evidence.timeframe })}
            </Link>
          </>
        )}
      </p>
    </li>
  );
}

/** "Where the % comes from" (§A29): base rate → per-theory contributions with each theory's track record. */
function WhyPanel({ detail, own }: { detail: Detail; own: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  const { engineId } = useEngine();
  const scoreboard = useScoreboard(engineId ?? '');
  const p = detail.probability;
  const pct = (value: number | null | undefined) => format.percent(value, { maximumFractionDigits: 1 });
  const families = supportingFamilies(detail.evidence);
  return (
    <Card title={t('opportunities.why.title')}>
      {!p.available ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('opportunities.metric.notCalibrated')}
        </p>
      ) : p.contributions === null || p.base_rate === null ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('opportunities.why.bucketOnly', { p: pct(p.estimate.p) })}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm">
            {t('opportunities.why.summary', { base: pct(p.base_rate), p: pct(p.estimate.p) })}
          </p>
          {(() => {
            const { supporting, conflicting } = splitContributions(p.contributions);
            const max = Math.max(...p.contributions.map((c) => Math.abs(c.points)), 0);
            const list = (title: string, items: Contribution[]) =>
              items.length > 0 && (
                <section aria-label={title} className="mb-3">
                  <h3 className="mb-1 text-sm font-semibold">{title}</h3>
                  <ul>
                    {items.map((c) => (
                      <ContributionRow
                        key={c.feature}
                        c={c}
                        max={max}
                        detail={detail}
                        scoreboard={scoreboard.data}
                        own={own}
                      />
                    ))}
                  </ul>
                </section>
              );
            return (
              <>
                {list(t('opportunities.why.raise'), supporting)}
                {list(t('opportunities.why.lower'), conflicting)}
              </>
            );
          })()}
        </>
      )}
      <p className="mt-2 text-xs text-slate-500">
        {t('opportunities.why.families', { n: families })} {t('opportunities.why.hypothetical')}
      </p>
    </Card>
  );
}

function EvidenceList({ detail, own }: { detail: Detail; own: boolean }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const groups = evidenceByRelation(detail.evidence);
  const row = (e: EvidenceRef) => (
    <li
      key={`${e.item.evidence.detector_id}-${e.item.evidence.timeframe}-${e.item.evidence.name}`}
      className="border-b border-slate-100 py-1 last:border-0 dark:border-slate-800"
    >
      <span className="font-medium">
        {evidenceName(i18n, e.item.evidence.detector_id, e.item.evidence.name)}
      </span>{' '}
      <span className="text-xs text-slate-500">
        {translateCode(i18n, 'family', e.item.evidence.family)} · {e.item.evidence.timeframe} ·{' '}
        {t('opportunities.evidence.quality', {
          q: format.number(e.item.evidence.quality * 100, { maximumFractionDigits: 0 }),
        })}
      </span>
      {own && (
        <Link
          to={chartLink(detail.symbol, detail.opportunity_id, e.item.evidence.timeframe)}
          className="ml-2 text-xs underline"
        >
          {t('opportunities.why.showOnChart', { tf: e.item.evidence.timeframe })}
        </Link>
      )}
    </li>
  );
  return (
    <Card title={t('opportunities.evidence.title')}>
      {detail.evidence.length === 0 ? (
        <p className="text-sm text-slate-500">{t('opportunities.evidence.none')}</p>
      ) : (
        (['SUPPORTS', 'CONFLICTS', 'NEUTRAL'] as const).map(
          (relation) =>
            groups[relation].length > 0 && (
              <section
                key={relation}
                aria-label={t(`opportunities.evidence.${relation}`)}
                className="mb-3 text-sm"
              >
                <h3 className="mb-1 font-semibold">
                  {t(`opportunities.evidence.${relation}`)} ({groups[relation].length})
                </h3>
                <ul>{groups[relation].map(row)}</ul>
              </section>
            ),
        )
      )}
    </Card>
  );
}

/** The owner's entry plan (MT5 orders) or, on the feed, the opportunity sized for the user's own account. */
function SizingCard({ detail }: { detail: Detail }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (detail.my_sizing) {
    const s = detail.my_sizing;
    return (
      <Card title={t('opportunities.mySizing.title')}>
        {s.available && s.currency ? (
          <p className="text-sm">
            {t('opportunities.mySizing.body', {
              lot: format.number(s.lot ?? null, { maximumFractionDigits: 2 }),
              risk: format.money(s.risk_money ?? null, s.currency),
            })}
          </p>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('opportunities.mySizing.none')}</p>
        )}
      </Card>
    );
  }
  if (!detail.plan || detail.plan.length === 0) return null;
  return (
    <Card title={t('opportunities.plan.title')}>
      <ol className="text-sm">
        {detail.plan.map((part, i) => (
          <li key={i} className="border-b border-slate-100 py-1 last:border-0 dark:border-slate-800">
            {t('opportunities.plan.part', {
              n: i + 1,
              type: part.order_type,
              volume: String(part.volume),
              price: part.entry === null ? '—' : String(part.entry),
            })}
          </li>
        ))}
      </ol>
      {detail.heat_after != null && (
        <p className="mt-2 text-xs text-slate-500">
          {t('opportunities.plan.heat', {
            heat: format.percent(detail.heat_after, { maximumFractionDigits: 2 }),
          })}
        </p>
      )}
    </Card>
  );
}

/** `/opportunities/:id`: the card's facts, the % explanation, the evidence and the sizing (push deep link). */
export function OpportunityDetail({ engineId, id }: { engineId: string; id: string }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const { own } = useEngine();
  const now = useServerNow(1_000);
  const detail = useOpportunity(engineId, id);
  const back = (
    <Link to="/opportunities" className="text-sm underline">
      {t('opportunities.back')}
    </Link>
  );
  if (detail.data === undefined) {
    const missing = detail.error instanceof ApiError && detail.error.code === 'opportunity_not_found';
    return (
      <div>
        {back}
        <p role={detail.isError ? 'alert' : undefined} className="mt-2 text-sm text-slate-500">
          {missing
            ? t('opportunities.notFound')
            : detail.isError
              ? t('dashboard.loadFailed')
              : t('dashboard.loading')}
        </p>
      </div>
    );
  }
  const o = detail.data;
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        {back}
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold">{o.symbol}</h2>
          <SideBadge side={o.side} />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            {translateCode(i18n, 'strategyName', o.strategy)} · {o.timeframe}
          </span>
        </div>
        <StatusBadge opportunity={o} state={windowState(o, now)} />
        <p className="text-xs text-slate-500">
          {t('opportunities.found', { time: format.dateTime(o.created_at) })}
          {o.valid_until && ` · ${t('opportunities.validUntil', { time: format.dateTime(o.valid_until) })}`}
        </p>
        {own && (
          <Link to={chartLink(o.symbol, o.opportunity_id, o.timeframe)} className="text-sm underline">
            {t('symbols.openChart')}
          </Link>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('opportunities.summary')}>
          <div className="space-y-3">
            <Metrics opportunity={o} />
            <Prices opportunity={o} />
            {o.lot !== undefined && <Money opportunity={o} />}
            {o.warnings && o.warnings.length > 0 && (
              <ul className="text-xs text-amber-700 dark:text-amber-400">
                {o.warnings.map((w) => (
                  <li key={w}>{translateCode(i18n, 'reason', w)}</li>
                ))}
              </ul>
            )}
          </div>
        </Card>
        <WhyPanel detail={o} own={own} />
        <EvidenceList detail={o} own={own} />
        <SizingCard detail={o} />
        <AIOpinion note={o.ai} />
      </div>
      <p className="text-xs text-slate-500">{t('opportunities.advice')}</p>
    </div>
  );
}
