import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json, makeSession } from '@/test/api';
import { iso, owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE", owner id "USER").
const recorded = samples as Record<string, unknown>;
const USERS = recorded['admin/users'] as { items: { id: string; username: string }[] };
const BOB = USERS.items.find((u) => u.username === 'bob')?.id ?? '';
const ENTITLEMENTS = recorded['me/entitlements'] as Record<string, unknown>;
const FREE = {
  ...(recorded['admin/users/USER/entitlements'] as object),
  plan: 'FREE',
  limits: {
    ALERTS_PER_DAY: 5,
    WATCHLISTS: 2,
    WATCHLIST_SYMBOLS: 10,
    BACKTESTS_PER_MONTH: 0,
    SHADOW_HISTORY_DAYS: 30,
  },
  features: { BACKTESTS: false, AI_NARRATIVES: false, DATA_EXPORT: false, API_ACCESS: false },
  asset_classes: ['FOREX_MAJOR', 'METAL'],
  families: ['TREND', 'LEVELS', 'FIBONACCI', 'CANDLESTICK'],
  overrides: ['WATCHLISTS'],
  override_rows: [
    {
      key: 'WATCHLISTS',
      value: 2,
      reason: 'beta tester',
      created_by: 'alice',
      created_at: '2026-10-01T12:00:00+00:00',
    },
  ],
};

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /me/account-profile': () => json(recorded['me/account-profile']),
    'GET /me/entitlements': () => json(ENTITLEMENTS),
    'GET /engines/e1/ranking': () => json(recorded['engines/ENGINE/ranking']),
    'GET /admin/users': () => json(USERS),
    'GET /admin/plans': () => json(recorded['admin/plans']),
    [`GET /admin/users/${BOB}/entitlements`]: () => json(FREE),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

describe('account page', () => {
  it('links the profile to the engine’s MT5 account and shows the plan and usage', async () => {
    const api = setup({
      'PUT /me/account-profile': (r) =>
        json({
          ...(r.body as object),
          equity: null,
          balance: null,
          currency: 'USD',
          leverage: null,
          risk_percent: null,
          updated_at: iso(Date.now()),
        }),
    });
    const user = userEvent.setup();
    renderShell('/account');
    const profile = await card('Account for sizing');
    expect(await within(profile).findByText(/Not set yet/)).toBeInTheDocument();
    expect(within(profile).getByLabelText("My engine's MT5 account")).toBeChecked();
    expect(await within(profile).findByText('1:500')).toBeInTheDocument();
    await user.click(within(profile).getByRole('button', { name: 'Save account' }));
    expect(await within(profile).findByRole('status')).toHaveTextContent('Saved.');
    expect(api.calls.find((c) => c.method === 'PUT')?.body).toEqual({
      source: 'LINKED_ENGINE',
      engine_id: 'e1',
    });

    const plan = await card('Plan & usage');
    expect(within(plan).getByText('Owner')).toBeInTheDocument();
    expect(within(plan).getByText('Alerts per day').closest('tr')).toHaveTextContent('0 used, no limit');
    expect(within(plan).getAllByText('All')).toHaveLength(2);
    // billing answers 404 while subscriptions are disabled: no plan picker
    expect(screen.queryByRole('region', { name: 'Change plan' })).not.toBeInTheDocument();
  });

  it('saves a manual account and shows the plan’s limits on the market feed', async () => {
    const api = owner({
      'GET /me/feed': () => json({ engine_id: 'feed', own: false }),
      'GET /me/account-profile': () => json({ source: null }),
      'GET /me/entitlements': () => json({ ...FREE, usage: { ALERTS_PER_DAY: 3, WATCHLISTS: 1 } }),
      'PUT /me/account-profile': (r) =>
        json({ engine_id: null, updated_at: iso(Date.now()), ...(r.body as object), balance: 1000 }),
      'GET /billing/plans': () =>
        json({ items: [{ code: 'PRO', name_th: 'โปร', name_en: 'Pro', spec: {} }] }),
      'POST /billing/checkout': () => apiError(503, 'billing_unavailable'),
    });
    const user = userEvent.setup();
    renderShell('/account');
    const profile = await card('Account for sizing');
    expect(within(profile).queryByLabelText("My engine's MT5 account")).not.toBeInTheDocument();
    const save = await within(profile).findByRole('button', { name: 'Save account' });
    expect(save).toBeDisabled();
    await user.type(within(profile).getByLabelText('Equity'), '1000');
    await user.type(within(profile).getByLabelText('Leverage (the x of 1:x)'), '200');
    await user.type(within(profile).getByLabelText('Risk per trade, % (optional)'), '3.5');
    expect(
      within(profile).getByText('Risk per trade: above 0 and at most 3%, or empty.'),
    ).toBeInTheDocument();
    await user.clear(within(profile).getByLabelText('Risk per trade, % (optional)'));
    await user.type(within(profile).getByLabelText('Risk per trade, % (optional)'), '0.5');
    await user.click(save);
    await waitFor(() => {
      expect(api.calls.find((c) => c.method === 'PUT')?.body).toEqual({
        source: 'MANUAL',
        equity: 1000,
        balance: null,
        currency: 'USD',
        leverage: 200,
        risk_percent: 0.5,
      });
    });

    const plan = await card('Plan & usage');
    expect(within(plan).getByText('Free')).toBeInTheDocument();
    expect(within(plan).getByText('Alerts per day').closest('tr')).toHaveTextContent('3 of 5');
    expect(within(plan).getByText('Watchlists').closest('tr')).toHaveTextContent('1 of 2 · adjusted for you');
    expect(within(plan).getByText('Forex majors, Metals')).toBeInTheDocument();
    const billing = await card('Change plan');
    await user.click(within(billing).getByRole('button', { name: 'Choose' }));
    expect(await within(billing).findByRole('alert')).toHaveTextContent(
      'Payments are not available right now.',
    );
  });
});

describe('users & plans page', () => {
  const stepped = () => json({ ...makeSession(), step_up_until: iso(Date.now() + 300_000) });

  it('lists users with plans and lets the owner assign a plan and overrides with step-up', async () => {
    const api = setup({
      'GET /auth/session': stepped,
      [`POST /admin/users/${BOB}/plan`]: () => json({ ...FREE, plan: 'PRO' }),
      [`PUT /admin/users/${BOB}/overrides/FAMILIES`]: () => json(FREE),
      [`DELETE /admin/users/${BOB}/overrides/WATCHLISTS`]: () => json(null, 204),
    });
    const user = userEvent.setup();
    renderShell('/admin');
    const users = await card('Users');
    expect((await within(users).findByRole('button', { name: 'bob' })).closest('tr')).toHaveTextContent(
      'Subscriber',
    );
    expect(within(users).getByRole('button', { name: 'alice' }).closest('tr')).toHaveTextContent('Owner');
    await user.click(within(users).getByRole('button', { name: 'bob' }));
    const bob = await card('bob');
    expect(await within(bob).findByText('beta tester')).toBeInTheDocument();
    expect(
      within(bob).getByRole('cell', { name: 'Allowed theory families' }).closest('tr'),
    ).toHaveTextContent('Trend');

    await user.selectOptions(within(bob).getByRole('combobox', { name: 'Assign a plan' }), 'PRO');
    await user.click(within(bob).getByRole('button', { name: 'Assign' }));
    const dialog = await screen.findByRole('dialog', { name: 'Assign a plan' });
    expect(dialog).toHaveTextContent('Give bob the PRO plan.');
    await user.click(within(dialog).getByRole('button', { name: 'Assign' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    await user.selectOptions(within(bob).getByLabelText('Setting'), 'FAMILIES');
    const families = within(bob).getByRole('group', { name: 'Allowed theory families' });
    await user.click(within(families).getByLabelText('Elliott waves'));
    await user.type(within(bob).getByLabelText('Reason'), 'tester');
    await user.click(within(bob).getByRole('button', { name: 'Save override' }));
    await user.click(
      within(await screen.findByRole('dialog', { name: 'Save an override' })).getByRole('button', {
        name: 'Save',
      }),
    );
    await user.click(within(bob).getByRole('button', { name: 'Remove the override of Watchlists' }));
    await user.click(
      within(await screen.findByRole('dialog', { name: 'Remove an override' })).getByRole('button', {
        name: 'Remove',
      }),
    );
    await waitFor(() => {
      expect(api.calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.path, c.body])).toEqual([
        ['POST', `/admin/users/${BOB}/plan`, { plan: 'PRO' }],
        [
          'PUT',
          `/admin/users/${BOB}/overrides/FAMILIES`,
          { value: ['TREND', 'LEVELS', 'FIBONACCI', 'CANDLESTICK', 'ELLIOTT'], reason: 'tester' },
        ],
        ['DELETE', `/admin/users/${BOB}/overrides/WATCHLISTS`, undefined],
      ]);
    });
  });

  it('is read-only for support and closed to subscribers', async () => {
    const support = { ...makeSession(), user: { ...makeSession().user, role: 'ADMIN' } };
    setup({ 'GET /auth/session': () => json(support) });
    const { unmount } = renderShell(`/admin?user=${BOB}`);
    const bob = await card('bob');
    expect(await within(bob).findByText(/Support accounts can look/)).toBeInTheDocument();
    expect(within(bob).queryByRole('button', { name: 'Assign' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Users & plans' })).toBeInTheDocument();
    unmount();

    const subscriber = { ...makeSession(), user: { ...makeSession().user, role: 'SUBSCRIBER' } };
    setup({ 'GET /auth/session': () => json(subscriber) });
    renderShell('/admin');
    expect(await screen.findByText(/Only the owner and support accounts/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Users & plans' })).not.toBeInTheDocument();
  });
});
