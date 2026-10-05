import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const charts = vi.hoisted(() => ({ updates: [] as { kind: string; points: { value: number }[] }[] }));
vi.mock('@/pages/charts/chartAdapter', () => ({
  createSeriesChart: () => ({
    update: (data: { kind: string; points: { value: number }[] }) => {
      charts.updates.push(data);
    },
    setTheme: () => undefined,
    destroy: () => undefined,
  }),
}));

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE"), served for engine e1.
const recorded = samples as Record<string, unknown>;
const sample = (route: string) => recorded[`engines/ENGINE/${route}`];
const SHADOWS = sample('shadow-trades?limit=20') as {
  items: { status: string; source: string; variant: string }[];
};

/** The closed shadow trades of one source and variant, as `shadow-trades?status=CLOSED&...` answers. */
const history =
  (source: string, variant = 'PLAN'): Handler =>
  () =>
    json({
      items: SHADOWS.items.filter(
        (i) => i.status === 'CLOSED' && i.source === source && i.variant === variant,
      ),
      next_cursor: null,
    });

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /engines/e1/accuracy?variant=PLAN': () => json(sample('accuracy')),
    'GET /engines/e1/accuracy?variant=PLAN&mine=true': () => json(sample('accuracy?mine=true')),
    'GET /engines/e1/calibration': () => json(sample('calibration')),
    'GET /engines/e1/shadow-trades?status=CLOSED&source=LIVE&variant=PLAN&limit=25': history('LIVE'),
    'GET /engines/e1/shadow-trades?status=CLOSED&source=REPLAY&variant=PLAN&limit=25': history('REPLAY'),
    'GET /advisory/preferences': () => json(recorded['advisory/preferences']),
    ...extra,
  });
}

const region = (name: string) => screen.findByRole('region', { name });

describe('signal accuracy page', () => {
  beforeEach(() => {
    charts.updates.length = 0;
  });

  it('shows the live KPIs, curve, calibration, buckets, breakdowns and history', async () => {
    setup();
    renderShell('/accuracy');
    expect(await screen.findByRole('note')).toHaveTextContent(/Hypothetical results/);
    const kpis = await region('Key figures');
    // 5 live trades, 2 wins: 40% with the backend's 90% Wilson interval 14–73%
    expect(within(kpis).getByText('5')).toBeInTheDocument();
    expect(within(kpis).getByText(/40%/)).toHaveTextContent('40% (14–73%)');
    expect(within(kpis).getByText('+0.35 R')).toBeInTheDocument();
    expect(within(kpis).getByText(/^USD\s21\.50$/)).toBeInTheDocument();
    expect(within(kpis).getByText('4 of 5 trades in money')).toBeInTheDocument();

    await waitFor(() => {
      expect(charts.updates.at(-1)?.points.map((p) => p.value)).toEqual([19, 8, 32, 32, 21.5]);
    });

    const calibration = await region('Calibration');
    expect(
      within(calibration).getByRole('img', { name: 'Predicted against observed win rate' }),
    ).toBeInTheDocument();
    expect(within(calibration).getByText(/Brier 0.214/)).toHaveTextContent('1500 live and 0 replay');

    const buckets = await region('Setup strength against hit rate');
    expect(within(buckets).getByRole('img').querySelectorAll('rect')).toHaveLength(3);

    const breakdown = await region('Breakdowns');
    const table = within(breakdown).getByRole('table');
    expect(
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) => r.firstChild?.textContent),
    ).toEqual(['EURUSD', 'XAUUSD', 'GBPUSD']);
    await userEvent.setup().selectOptions(within(breakdown).getByLabelText('By'), 'alerted');
    expect(within(breakdown).getByText('Not alerted')).toBeInTheDocument();

    const outcomes = await region('Outcome history');
    const rows = within(await within(outcomes).findByRole('table'))
      .getAllByRole('row')
      .slice(1);
    expect(rows).toHaveLength(5);
    const timeStop = rows.find((r) => r.textContent.includes('GBPUSD')) as HTMLElement;
    expect(within(timeStop).getByText('R only (lot too large)')).toBeInTheDocument();
    expect(timeStop).toHaveTextContent('—'); // no money for a trade not tradable at the capital
  });

  it('switches to replay results and to my alerts', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/accuracy');
    await region('Key figures');
    await user.click(screen.getByRole('button', { name: 'Replay (history)' }));
    const kpis = await region('Key figures');
    await waitFor(() => {
      expect(within(kpis).getByText('3')).toBeInTheDocument();
    });
    expect(api.calls.some((c) => c.path.includes('source=REPLAY'))).toBe(true);

    await user.click(screen.getByRole('button', { name: 'My alerts' }));
    expect(await screen.findByText(/Only the opportunities you were alerted to/)).toBeInTheDocument();
    expect(await screen.findAllByText('No closed outcomes yet.')).not.toHaveLength(0);
  });

  it('marks the threshold explorer in-sample and the theory scoreboard per group', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/accuracy');
    await region('Key figures');
    await user.click(screen.getByRole('tab', { name: 'Threshold explorer' }));
    const explorer = await region('Threshold explorer');
    expect(within(explorer).getByRole('note')).toHaveTextContent(/In-sample/);
    expect(
      within(explorer).getByText('"Follow every opportunity with Setup strength ≥ x" for each x.'),
    ).toBeInTheDocument();
    expect(within(explorer).getAllByRole('row').slice(1)).toHaveLength(10); // x = 50, 55, …, 95

    await user.click(screen.getByRole('tab', { name: 'Theory scoreboard' }));
    const theories = await region('Theory scoreboard');
    const forex = within(theories).getByRole('region', { name: 'Forex majors M15' });
    expect(within(forex).getByText('Fibonacci')).toBeInTheDocument();
    await user.click(within(theories).getByRole('button', { name: 'Detectors' }));
    expect(within(theories).getAllByText('fib.retracement')).not.toHaveLength(0);
  });

  it('explains a missing calibration and shows only my alerts on the market feed', async () => {
    owner({
      'GET /me/feed': () => json({ engine_id: 'feed', own: false }),
      'GET /engines/feed/accuracy?variant=PLAN&mine=true': () => json(sample('accuracy?mine=true')),
      'GET /engines/feed/calibration': () => apiError(404, 'calibration_not_found'),
      'GET /engines/feed/shadow-trades?status=CLOSED&source=LIVE&variant=PLAN&limit=25': history('LIVE'),
    });
    renderShell('/accuracy');
    expect(
      await within(await region('Calibration')).findByText('No calibration has been built yet.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'All opportunities' })).not.toBeInTheDocument();
    const outcomes = await region('Outcome history');
    expect(within(outcomes).getByText(/in R \(the feed shows no account money\)/)).toBeInTheDocument();
    expect(within(outcomes).queryByText('Hypothetical P/L')).not.toBeInTheDocument();
  });

  it('explains a calibration built before any outcome (as on a fresh engine)', async () => {
    const empty = sample('calibration') as { reliability: { n: number }[] };
    setup({
      'GET /engines/e1/calibration': () =>
        json({
          ...empty,
          n_live: 0,
          n_replay: 0,
          brier: null,
          reliability: empty.reliability.map((b) => ({ ...b, n: 0, mean_predicted: null, observed: null })),
        }),
    });
    renderShell('/accuracy');
    const calibration = await region('Calibration');
    expect(await within(calibration).findByText(/built before enough trades had closed/)).toBeInTheDocument();
    expect(within(calibration).queryByRole('img')).not.toBeInTheDocument();
  });

  it('renders in Thai', async () => {
    setup();
    renderShell('/accuracy', 'th');
    expect(await region('ตัวเลขสำคัญ')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'สำรวจเกณฑ์' })).toBeInTheDocument();
  });
});
