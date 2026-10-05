import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const charts = vi.hoisted(() => ({ updates: [] as { kind: string; points: unknown[] }[] }));
vi.mock('@/pages/charts/chartAdapter', () => ({
  createSeriesChart: () => ({
    update: (data: { kind: string; points: unknown[] }) => {
      charts.updates.push(data);
    },
    setTheme: () => undefined,
    destroy: () => undefined,
  }),
}));

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const A = '0191a0a0-0000-7000-8000-0000000000b1';
const B = '0191a0a0-0000-7000-8000-0000000000b2';
const sample = (route: string) => recorded[`engines/ENGINE/${route}`] ?? {};
const BASE = '/engines/e1/backtests';
const trades = sample(`backtests/${A}/trades?limit=3`);

function setup(extra: Record<string, () => Response> = {}) {
  charts.updates.length = 0;
  return owner({
    [`GET ${BASE}?limit=50`]: () => json(sample('backtests')),
    [`GET ${BASE}/${A}`]: () => json(sample(`backtests/${A}`)),
    [`GET ${BASE}/${A}/trades?offset=0&limit=100`]: () => json(trades),
    [`GET ${BASE}/${A}/trades?offset=3&limit=100`]: () =>
      json({
        ...trades,
        items: [{ ...(trades.items as Record<string, unknown>[])[0], ticket: 99 }],
        offset: 3,
      }),
    [`GET ${BASE}/compare?ids=${A}%2C${B}`]: () => json(sample(`backtests/compare?ids=${A},${B}`)),
    [`GET ${BASE}/history`]: () => json(sample('backtests/history')),
    'GET /backtests/presets': () => json(recorded['backtests/presets']),
    'GET /engines/e1/strategies?days=30': () => json(sample('strategies')),
    ...extra,
  });
}

describe('backtests page', () => {
  it('lists runs with their status and headline figures', async () => {
    setup();
    renderShell('/backtests');
    // the first test loads the lazy page chunk cold; under load that can take more than findBy's 1 s
    expect(await screen.findAllByText(/Standard · EURUSD/, undefined, { timeout: 5_000 })).toHaveLength(2);
    expect(screen.getAllByText('Finished')).toHaveLength(2);
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText(/no M15 history for GBPUSD/)).toBeInTheDocument();
    expect(screen.getAllByText(/net \+387\.34 · 4 trades · win rate 100%/)).toHaveLength(2);
    expect(screen.getByText(/Backtest results are hypothetical/)).toBeInTheDocument();
  });

  it('compares two finished runs', async () => {
    setup();
    const user = userEvent.setup();
    const { router } = renderShell('/backtests');
    await screen.findByText(/High costs · EURUSD/);
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes[0]).toBeDisabled(); // the failed run (newest first)
    const compare = screen.getByRole('button', { name: 'Compare (0)' });
    expect(compare).toBeDisabled();
    await user.click(boxes[2] as HTMLElement); // A
    await user.click(boxes[1] as HTMLElement); // B
    await user.click(screen.getByRole('button', { name: 'Compare (2)' }));
    expect(router.state.location.search).toBe(`?compare=${A}%2C${B}`);
    const table = await screen.findByRole('table', { name: 'Comparison' });
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Metric', expect.stringMatching(/^Standard/), expect.stringMatching(/^High costs/)]);
    expect(within(within(table).getByRole('row', { name: /Net P\/L/ })).getAllByText('+387.34')).toHaveLength(
      2,
    );
    expect(screen.getByText(/past results do not predict future results/)).toBeInTheDocument();
  });

  it('shows a run: figures, curves, metrics, decisions, provenance and trades', async () => {
    setup();
    const user = userEvent.setup();
    renderShell(`/backtests?run=${A}`);
    expect(await screen.findByRole('heading', { name: 'Standard · EURUSD' })).toBeInTheDocument();
    expect(screen.getByText(/FBS-Demo/)).toBeInTheDocument();
    const tiles = screen
      .getAllByRole('definition')
      .slice(0, 6)
      .map((d) => d.textContent);
    expect(tiles).toEqual(['+387.34', '4', '100%', '—', '+1.94R', '0%']);
    await waitFor(() => {
      expect(charts.updates.map((u) => u.kind)).toEqual(['line', 'area']);
    });
    expect(charts.updates[0]?.points.length).toBeGreaterThan(100);
    expect(screen.getByText('6 signals · 4 accepted · 0 rejected')).toBeInTheDocument();
    expect(screen.getByText(/History used: .*2026.*–.*2026/)).toBeInTheDocument();
    expect(screen.queryByText(/No strategy signalled/)).not.toBeInTheDocument();
    expect(screen.getByText('example_trend_pullback', { selector: 'dd' })).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: 'Trades' });
    expect(within(table).getAllByRole('row')).toHaveLength(4); // header + 3
    expect(within(table).getAllByText('Take profit').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Load more' }));
    await waitFor(() => {
      expect(within(table).getAllByRole('row')).toHaveLength(5);
    });
    await user.click(screen.getByRole('button', { name: /All runs/ }));
    expect(await screen.findByRole('button', { name: 'New run' })).toBeInTheDocument();
  });

  it('starts a new run from a preset and opens it', async () => {
    const queued = {
      ...sample('backtests/' + A),
      run_id: 'r-new',
      status: 'QUEUED',
      progress: 0,
      metrics: null,
    };
    const api = setup({
      [`POST ${BASE}`]: () => json(queued, 202),
      [`GET ${BASE}/r-new`]: () => json({ ...queued, summary: {}, equity: [] }),
    });
    const user = userEvent.setup();
    const { router } = renderShell('/backtests');
    await user.click(await screen.findByRole('button', { name: 'New run' }));
    const form = await screen.findByRole('region', { name: 'New run' });
    await user.selectOptions(await within(form).findByRole('combobox', { name: 'Preset' }), 'high_costs');
    expect(within(form).getByText(/Three times the slippage/)).toBeInTheDocument();
    expect(within(form).getByRole('checkbox', { name: /EURUSD/ })).toBeChecked();
    fireEvent.change(within(form).getByLabelText('From'), { target: { value: '2026-09-30' } });
    fireEvent.change(within(form).getByLabelText('To'), { target: { value: '2026-10-01' } });
    await user.click(within(form).getByRole('checkbox', { name: 'example_trend_pullback' }));
    await user.type(within(form).getByRole('textbox', { name: 'Seed' }), '7');
    await user.click(within(form).getByRole('button', { name: 'Start backtest' }));
    await waitFor(() => {
      expect(router.state.location.search).toBe('?run=r-new');
    });
    const post = api.calls.find((c) => c.method === 'POST');
    expect(post?.body).toEqual({
      preset: 'high_costs',
      symbols: ['EURUSD'],
      start: '2026-09-30T00:00:00.000Z',
      end: '2026-10-02T00:00:00.000Z',
      strategies: ['example_trend_pullback'],
      seed: 7,
    });
    expect(post?.headers['x-csrf-token']).toBe('csrf-123');
    expect(await screen.findByText(/Waiting for the worker service to run it…/)).toBeInTheDocument();
  });

  it('explains a refused run and checks the form first', async () => {
    const api = setup({ [`POST ${BASE}`]: () => apiError(409, 'backtest_limit') });
    const user = userEvent.setup();
    renderShell('/backtests?new=1');
    const form = await screen.findByRole('region', { name: 'New run' });
    await user.click(await within(form).findByRole('checkbox', { name: /EURUSD/ })); // untick the only one
    await user.click(within(form).getByRole('button', { name: 'Start backtest' }));
    expect(within(form).getByRole('alert')).toHaveTextContent('Choose at least one symbol.');
    expect(api.calls.some((c) => c.method === 'POST')).toBe(false);
    await user.click(within(form).getByRole('checkbox', { name: /EURUSD/ }));
    fireEvent.change(within(form).getByLabelText('From'), { target: { value: '2026-09-01' } });
    fireEvent.change(within(form).getByLabelText('To'), { target: { value: '2026-09-02' } });
    await user.click(within(form).getByRole('button', { name: 'Start backtest' }));
    expect(await within(form).findByRole('alert')).toHaveTextContent('Too many runs are queued or running');
  });

  it('tells how to upload history when there is none', async () => {
    setup({ [`GET ${BASE}/history`]: () => json({ items: [] }) });
    renderShell('/backtests?new=1');
    expect(await screen.findByText(/download_history\.py --days 365 --upload/)).toBeInTheDocument();
  });

  it('warns when the history starts after the chosen start', async () => {
    setup();
    renderShell('/backtests?new=1');
    const form = await screen.findByRole('region', { name: 'New run' });
    await within(form).findByRole('checkbox', { name: /EURUSD/ });
    expect(within(form).queryByRole('status')).not.toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText('From'), { target: { value: '2026-09-01' } });
    expect(within(form).getByRole('status')).toHaveTextContent(
      /EURUSD: the uploaded history starts 30 Sept 2026/,
    );
  });

  it('explains a finished run without signals', async () => {
    const run = sample(`backtests/${A}`) as { summary: Record<string, unknown> };
    setup({
      [`GET ${BASE}/${A}`]: () => json({ ...run, summary: { ...run.summary, signals: 0, decisions: {} } }),
    });
    renderShell(`/backtests?run=${A}`);
    expect(await screen.findByText(/No strategy signalled in this period/)).toBeInTheDocument();
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/backtests', 'th');
    expect(await screen.findAllByText(/มาตรฐาน · EURUSD/)).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'รันใหม่' })).toBeInTheDocument();
  });
});
