import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json, makeSession } from '@/test/api';
import { heartbeat, owner, renderShell } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const overview = recorded['engines/ENGINE/strategies'] ?? {};
const PATH = '/engines/e1/strategies?days=30';
const EXAMPLE = 'example_trend_pullback';

const queued = {
  id: 'c9',
  type: 'STRATEGY_DISABLE',
  params: { strategy: EXAMPLE },
  created_by: 'owner',
  created_at: '2026-09-30T10:00:00+00:00',
  expires_at: '2026-09-30T10:02:00+00:00',
  status: 'QUEUED',
  delivered_at: null,
  completed_at: null,
  result: {},
};

function setup(extra: Record<string, () => Response> = {}, session: Record<string, unknown> = makeSession()) {
  return owner({
    'GET /auth/session': () => json(session),
    [`GET ${PATH}`]: () => json(overview),
    'GET /engines/e1/strategies?days=7': () => json(recorded['engines/ENGINE/strategies?days=7']),
    ...extra,
  });
}

const card = async (name: string) => screen.findByRole('region', { name });

describe('strategies page', () => {
  it('shows each strategy with its state, decisions and paper performance', async () => {
    setup();
    renderShell('/strategies');
    const example = await card(EXAMPLE);
    expect(within(example).getByText('Enabled')).toBeInTheDocument();
    expect(within(example).getByText(/pullback to the fast EMA/)).toBeInTheDocument();
    expect(within(example).getByText(/demonstration, unproven/)).toBeInTheDocument();
    const perf = within(example).getByLabelText(`Paper trades of ${EXAMPLE}`);
    expect(within(perf).getByText('1 (1 won / 0 lost)')).toBeInTheDocument();
    expect(within(perf).getByText('100%')).toBeInTheDocument();
    expect(within(perf).getByText('+1R (1 trades)')).toBeInTheDocument();
    const decisions = within(example).getByLabelText(`Decisions of ${EXAMPLE}`);
    expect(within(decisions).getAllByRole('definition')[0]).toHaveTextContent('1');
    expect(within(example).getByRole('button', { name: 'Disable' })).toBeInTheDocument();

    const off = await card('setup_breakout');
    expect(within(off).getByText('Disabled from the app')).toBeInTheDocument();
    expect(within(off).getByText(/Disable command: Done · alice/)).toBeInTheDocument();
    expect(within(off).getByText('python -m app.cli strategy enable setup_breakout')).toBeInTheDocument();
    expect(within(off).queryByRole('button', { name: 'Disable' })).not.toBeInTheDocument();
    const config = await card('setup_fib_pullback');
    expect(within(config).getByText('Off in config')).toBeInTheDocument();
    expect(within(config).getByText(/Switched off in config.yaml/)).toBeInTheDocument();
    expect(screen.getByText(/Paper results are hypothetical/)).toBeInTheDocument();
    expect(screen.getByText(/trend H1, entry M15 · cooldown 4 bars/)).toBeInTheDocument();
  });

  it('lists the effective parameters read-only', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/strategies');
    const example = await card(EXAMPLE);
    await user.click(within(example).getByText('Parameters (13)'));
    const table = within(example).getByRole('table', { name: `Parameters of ${EXAMPLE}` });
    const adx = within(table).getByRole('row', { name: /adx_min/ });
    expect(within(adx).getByText('20')).toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /session_start_utc/ })).toHaveTextContent('07:00');
    expect(within(table).queryByText('config.yaml')).not.toBeInTheDocument(); // nothing overridden
    expect(within(example).queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('switches the performance period through the URL', async () => {
    const api = setup();
    const user = userEvent.setup();
    const { router } = renderShell('/strategies');
    await card(EXAMPLE);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Period' }), '7');
    await waitFor(() => {
      expect(api.calls.map((c) => c.path)).toContain('/engines/e1/strategies?days=7');
    });
    expect(router.state.location.search).toBe('?days=7');
  });

  it('disables a strategy after a fresh authenticator code', async () => {
    const until = new Date(Date.now() + 300_000).toISOString().replace('Z', '+00:00');
    const api = setup({
      'POST /auth/step-up': () => json({ step_up_until: until }),
      'POST /engines/e1/commands': () => json(queued, 202),
    });
    const user = userEvent.setup();
    renderShell('/strategies');
    await user.click(within(await card(EXAMPLE)).getByRole('button', { name: 'Disable' }));
    const dialog = await screen.findByRole('dialog', { name: `Disable ${EXAMPLE}?` });
    expect(within(dialog).getByText(/stops opening new trades/)).toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: 'Reason (optional)' }), ' too many losses ');
    await user.click(within(dialog).getByRole('button', { name: 'Disable strategy' }));
    expect(
      await within(dialog).findByText('Enter the 6 digits from your authenticator app.'),
    ).toBeInTheDocument();
    expect(api.calls.some((c) => c.method === 'POST')).toBe(false);
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    const before = api.calls.filter((c) => c.path === PATH).length;
    await user.click(within(dialog).getByRole('button', { name: 'Disable strategy' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    const posts = api.calls.filter((c) => c.method === 'POST');
    expect(posts.map((c) => [c.path, c.body])).toEqual([
      ['/auth/step-up', { code: '123456' }],
      ['/engines/e1/commands', { type: 'STRATEGY_DISABLE', strategy: EXAMPLE, reason: 'too many losses' }],
    ]);
    expect(posts[1]?.headers['x-csrf-token']).toBe('csrf-123');
    expect(api.calls.filter((c) => c.path === PATH).length).toBeGreaterThan(before); // refreshed
  });

  it('skips the code while a step-up is valid and asks again when the server says it ran out', async () => {
    const session = {
      ...makeSession(),
      step_up_until: new Date(Date.now() + 120_000).toISOString().replace('Z', '+00:00'),
    };
    const answer = apiError(403, 'step_up_required');
    const api = setup({ 'POST /engines/e1/commands': () => answer }, session);
    const user = userEvent.setup();
    renderShell('/strategies');
    await user.click(within(await card(EXAMPLE)).getByRole('button', { name: 'Disable' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).queryByRole('textbox', { name: 'Authenticator code' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Disable strategy' }));
    expect(
      await within(dialog).findByText('Your confirmation has expired. Enter a new code.'),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole('textbox', { name: 'Authenticator code' })).toBeInTheDocument();
    expect(api.calls.filter((c) => c.path === '/engines/e1/commands')).toHaveLength(1);
  });

  it('reports a wrong code and keeps the dialog open', async () => {
    setup({ 'POST /auth/step-up': () => apiError(400, 'invalid_code') });
    const user = userEvent.setup();
    renderShell('/strategies');
    await user.click(within(await card(EXAMPLE)).getByRole('button', { name: 'Disable' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '000000');
    await user.click(within(dialog).getByRole('button', { name: 'Disable strategy' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The code is incorrect');
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows a pending command instead of the button', async () => {
    const strategies = (overview.strategies as Record<string, unknown>[]).map((s) =>
      s.name === EXAMPLE ? { ...s, last_command: queued } : s,
    );
    setup({ [`GET ${PATH}`]: () => json({ ...overview, strategies }) });
    renderShell('/strategies');
    const example = await card(EXAMPLE);
    expect(within(example).getByText('Disable command sent; waiting for the engine…')).toBeInTheDocument();
    expect(within(example).getByText(/Disable command: Queued · owner/)).toBeInTheDocument();
    expect(within(example).queryByRole('button', { name: 'Disable' })).not.toBeInTheDocument();
  });

  it('refreshes on command results and on a heartbeat whose disabled list differs', async () => {
    const api = setup();
    const { sources } = renderShell('/strategies');
    await card(EXAMPLE);
    const count = () => api.calls.filter((c) => c.path === PATH).length;
    const before = count();
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      // the same list as shown: nothing to do
      sources
        .last()
        .emit('status', streamEvent(2, 'heartbeat', heartbeat({ disabled_strategies: ['setup_breakout'] })));
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(count()).toBe(before);
    act(() => {
      sources.last().emit('status', streamEvent(3, 'heartbeat', heartbeat({ disabled_strategies: [] })));
    });
    await waitFor(() => {
      expect(count()).toBe(before + 1);
    });
    act(() => {
      sources.last().emit('status', streamEvent(4, 'command', queued));
    });
    await waitFor(() => {
      expect(count()).toBe(before + 2);
    });
  });

  it('says when the engine has not reported strategies yet', async () => {
    setup({ [`GET ${PATH}`]: () => json({ ...overview, strategies: [], remote_known: false }) });
    renderShell('/strategies');
    expect(await screen.findByText(/has not reported its strategies yet/)).toBeInTheDocument();
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/strategies', 'th');
    const example = await card(EXAMPLE);
    expect(within(example).getByText('เปิดใช้งาน')).toBeInTheDocument();
    expect(within(example).getByRole('button', { name: 'ปิดใช้งาน' })).toBeInTheDocument();
    expect(within(await card('setup_breakout')).getByText('ปิดจากแอป')).toBeInTheDocument();
  });
});
