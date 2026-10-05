import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import recommendationsPy from '../../../../app/analytics/recommendations.py?raw';
import reportPy from '../../../../app/analytics/report.py?raw';
import { type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';
import { pyStrEnumValues } from '@/test/python';

import { backtestPeriod } from './analyticsModel';
import { DIMENSIONS, RECOMMENDATION_KINDS } from './schemas';

const charts = vi.hoisted(() => ({ kinds: [] as string[] }));
vi.mock('@/pages/charts/chartAdapter', () => ({
  createSeriesChart: () => ({
    update: (data: { kind: string }) => {
      charts.kinds.push(data.kind);
    },
    setTheme: () => undefined,
    destroy: () => undefined,
  }),
}));

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const RUN = '0191a0a0-0000-7000-8000-0000000000b1';
const sample = (route: string) => recorded[`engines/ENGINE/${route}`] ?? {};

const REC = {
  kind: 'EARLIER_BREAK_EVEN',
  key: 'analytics.recommendation.EARLIER_BREAK_EVEN',
  sample_size: 20,
  enough: false,
  min_samples: 30,
  evidence: { losers: 20, gave_back: 12, share: 0.6, mfe_r: 1.0 },
  segment: null,
  ci: null,
  change: { kind: 'break_even_trigger_r', value: 0.75, strategy: null },
  backtest: { symbols: ['EURUSD'], change: { kind: 'break_even_trigger_r', value: 0.75 } },
};

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /engines/e1/analytics?scope=PAPER&days=90': () => json(sample('analytics?scope=PAPER&days=366')),
    'GET /engines/e1/recommendations?scope=PAPER&days=90': () =>
      json({ ...sample(`recommendations?scope=BACKTEST&days=366&run=${RUN}`), scope: 'PAPER', items: [REC] }),
    'GET /engines/e1/backtests': () => json(sample('backtests')),
    [`GET /engines/e1/analytics?scope=BACKTEST&days=90&run=${RUN}`]: () =>
      json(sample(`analytics?scope=BACKTEST&days=366&run=${RUN}`)),
    [`GET /engines/e1/recommendations?scope=BACKTEST&days=90&run=${RUN}`]: () =>
      json(sample(`recommendations?scope=BACKTEST&days=366&run=${RUN}`)),
    ...extra,
  });
}

const region = (name: string) => screen.findByRole('region', { name });
vi.setConfig({ testTimeout: 20_000 });

describe('analytics page', () => {
  it('follows the Python names of kinds and style dimensions', () => {
    expect([...RECOMMENDATION_KINDS]).toEqual(pyStrEnumValues(recommendationsPy, 'Kind'));
    const segment =
      /SEGMENT_DIMENSIONS: tuple\[str, \.\.\.\] = \(([\s\S]*?)\)/.exec(recommendationsPy)?.[1] ?? '';
    const names = [...segment.matchAll(/"(\w+)"/g)].map((m) => m[1]);
    expect(reportPy).toContain('STYLE_DIMENSIONS: tuple[str, ...] = (*SEGMENT_DIMENSIONS, "weekday")');
    expect([...DIMENSIONS]).toEqual([...names, 'weekday']);
  });

  it('shows a backtest run: key figures, curves, styles and attribution', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/analytics');
    await user.selectOptions(await screen.findByLabelText('Results of'), 'BACKTEST');
    expect(await screen.findByText('Pick a finished backtest run.', { selector: 'p' })).toBeInTheDocument();
    const runs = await screen.findByLabelText('Run');
    await waitFor(() => {
      expect(within(runs).getAllByRole('option').length).toBeGreaterThan(1);
    });
    await user.selectOptions(runs, RUN);
    expect(await screen.findByRole('note')).toHaveTextContent('Simulated results');
    const kpis = await region('Key figures');
    expect(within(kpis).getByText('Trades').nextSibling).toHaveTextContent('4');
    expect(within(kpis).getByText('Average per trade').nextSibling).toHaveTextContent('+1.94R');
    expect(within(kpis).getByText('Win rate').nextSibling).toHaveTextContent('100%');
    expect(await region('Why trades won or lost')).toHaveTextContent('Win (no specific pattern)');
    expect(within(await region('By style')).getByRole('table')).toHaveTextContent('Trend pullback');
    expect(await region('Recommendations')).toHaveTextContent('Nothing to recommend from 4 trades.');
    await waitFor(() => {
      expect(charts.kinds).toEqual(expect.arrayContaining(['line', 'area'])); // the lazy curves
    });
  });

  it('offers a recommendation as a backtest job, never as a setting', async () => {
    const api = setup({
      'POST /engines/e1/backtests': () =>
        json({ ...sample('backtests'), run_id: 'r-new', status: 'QUEUED' }, 202),
    });
    const user = userEvent.setup();
    renderShell('/analytics');
    const recs = await region('Recommendations');
    expect(
      await within(recs).findByText(/12 of 20 losing trades \(60%\) were at least 1R/),
    ).toBeInTheDocument();
    expect(recs).toHaveTextContent('Only 20 trades (at least 30 are needed');
    expect(recs).toHaveTextContent("never change the engine's settings");
    await user.click(within(recs).getByRole('button', { name: 'Backtest this change' }));
    await waitFor(() => {
      expect(api.calls.some((c) => c.method === 'POST')).toBe(true);
    });
    const post = api.calls.find((c) => c.method === 'POST');
    expect(post?.body).toMatchObject({
      symbols: ['EURUSD'],
      change: { kind: 'break_even_trigger_r', value: 0.75 },
      ...backtestPeriod(new Date(), 90),
    });
  });
});
