import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type FakeRequest, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

import type { Preferences, Watchlist } from './schemas';

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE"), served for engine e1.
const recorded = samples as Record<string, unknown>;
const PREFS = recorded['advisory/preferences'] as Preferences;

/** A fake preferences store behind the watchlist routes, as app/web/routers/advisory.py answers them. */
function setup(extra: Record<string, Handler> = {}) {
  let lists: Watchlist[] = PREFS.watchlists.map((w) =>
    w.kind === 'FAVOURITES' ? { ...w, symbols: ['EURUSD'] } : w,
  );
  const named = (path: string) => decodeURIComponent(path.split('/').pop() ?? '');
  const put: Handler = (request: FakeRequest) => {
    const name = named(request.path);
    lists = lists.map((w) => (w.name === name ? (request.body as Watchlist) : w));
    return json({ watchlists: lists });
  };
  const api = owner({
    'GET /engines/e1/ranking': () => json(recorded['engines/ENGINE/ranking']),
    'GET /advisory/preferences': () => json({ ...PREFS, watchlists: lists }),
    'PUT /advisory/watchlists/Favourites': put,
    'PUT /advisory/watchlists/Top%2030': put,
    'PUT /advisory/watchlists/Metals': put,
    'POST /advisory/watchlists': (request) => {
      lists = [...lists, request.body as Watchlist];
      return json({ watchlists: lists }, 201);
    },
    'DELETE /advisory/watchlists/Top%2030': () => {
      lists = lists.filter((w) => w.name !== 'Top 30');
      return json(null, 204);
    },
    ...extra,
  });
  return api;
}

const card = (name: string) => screen.findByRole('region', { name });

describe('watchlists page', () => {
  it('shows each list with its alert state and the global rule', async () => {
    setup();
    renderShell('/watchlists');
    const favourites = await card('Favourites');
    expect(within(favourites).getByText('Alerts at ≥ 55%')).toBeInTheDocument();
    expect(within(favourites).getByRole('list', { name: 'Symbols in the list' })).toHaveTextContent('EURUSD');
    const top = await card('Top 30');
    expect(within(top).getByText('Auto top N')).toBeInTheDocument();
    // the sample ranking holds 11 symbols, best first
    expect(
      await within(top).findByText(/Right now: USDJPY, EURUSD, AUDUSD, GBPUSD, EURGBP, XAUUSD/),
    ).toHaveTextContent(
      'Right now: USDJPY, EURUSD, AUDUSD, GBPUSD, EURGBP, XAUUSD, BTCUSD, USOIL, XAGUSD, AAPL, US30',
    );
    const rule = screen.getByRole('region', { name: 'Alert rule' });
    expect(within(rule).getByText('Alert when Win probability ≥ 55%')).toBeInTheDocument();
    expect(within(rule).getByRole('link', { name: 'Change the alert settings' })).toHaveAttribute(
      'href',
      '/notifications#alert-settings',
    );
  });

  it('adds and removes favourites and saves the list', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/watchlists');
    const favourites = await card('Favourites');
    const save = within(favourites).getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();
    await user.type(within(favourites).getByLabelText('Symbols to add'), 'XAUUSD, bad/name');
    await user.click(within(favourites).getByRole('button', { name: 'Add' }));
    expect(within(favourites).getByRole('alert')).toHaveTextContent('Not a valid symbol name: bad/name');
    await user.click(within(favourites).getByRole('button', { name: 'Remove EURUSD' }));
    await user.click(save);
    await waitFor(() => {
      expect(api.calls.some((c) => c.method === 'PUT')).toBe(true);
    });
    const request = api.calls.find((c) => c.method === 'PUT');
    expect(request?.path).toBe('/advisory/watchlists/Favourites');
    expect(request?.body).toEqual({ ...PREFS.watchlists[0], symbols: ['XAUUSD'] });
    expect(await within(favourites).findByRole('status')).toHaveTextContent('Saved.');
    expect(within(favourites).getByRole('list', { name: 'Symbols in the list' })).toHaveTextContent('XAUUSD');
  });

  it('turns alerts off, overrides the threshold and changes top N', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/watchlists');
    const top = await card('Top 30');
    const n = within(top).getByLabelText('Take the top');
    await user.clear(n);
    await user.type(n, '61');
    expect(within(top).getByText('Take between 1 and 60 symbols.')).toBeInTheDocument();
    expect(within(top).getByRole('button', { name: 'Save' })).toBeDisabled();
    await user.clear(n);
    await user.type(n, '3');
    expect(within(top).getByText(/Right now: USDJPY, EURUSD, AUDUSD$/)).toBeInTheDocument();
    await user.click(within(top).getByLabelText('Own threshold for this list'));
    expect(within(top).getByLabelText('Threshold for this list')).toHaveValue('55');
    await user.click(within(top).getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(api.calls.find((c) => c.method === 'PUT')?.body).toMatchObject({ top_n: 3, threshold: 55 });
    });
    expect(await within(top).findByText('Alerts at ≥ 55%')).toBeInTheDocument();

    await user.click(within(top).getByLabelText('Alerts for this list'));
    expect(within(top).queryByLabelText('Own threshold for this list')).not.toBeInTheDocument();
    await user.click(within(top).getByRole('button', { name: 'Undo changes' }));
    expect(within(top).getByLabelText('Alerts for this list')).toBeChecked();
  });

  it('creates a custom list and deletes a list after confirming', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/watchlists');
    const create = await card('New list');
    // one AUTO_TOP_N list exists already
    expect(within(create).getByLabelText('Auto top N')).toBeDisabled();
    await user.type(within(create).getByLabelText('List name'), 'top 30');
    expect(within(create).getByText('Another list already has this name.')).toBeInTheDocument();
    await user.clear(within(create).getByLabelText('List name'));
    await user.type(within(create).getByLabelText('List name'), ' Metals ');
    await user.click(within(create).getByRole('button', { name: 'Create list' }));
    expect(await card('Metals')).toBeInTheDocument();
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({
      name: 'Metals',
      kind: 'CUSTOM',
      symbols: [],
      top_n: null,
      alerts: true,
      threshold: null,
    });
    expect(within(create).getByLabelText('List name')).toHaveValue('');

    const top = await card('Top 30');
    await user.click(within(top).getByRole('button', { name: 'Delete list' }));
    await user.click(within(top).getByRole('button', { name: 'Delete "Top 30" now' }));
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: 'Top 30' })).not.toBeInTheDocument();
    });
    expect(within(await card('Favourites')).queryByRole('button', { name: 'Delete list' })).toBeNull();
  });

  it('explains the plan limit', async () => {
    setup({ 'POST /advisory/watchlists': () => apiError(403, 'plan_limit', { key: 'WATCHLISTS' }) });
    const user = userEvent.setup();
    renderShell('/watchlists');
    const create = await card('New list');
    await user.type(within(create).getByLabelText('List name'), 'Metals');
    await user.click(within(create).getByRole('button', { name: 'Create list' }));
    expect(await within(create).findByRole('alert')).toHaveTextContent(
      "Your plan's watchlist limit is reached.",
    );
  });

  it('renders in Thai', async () => {
    setup();
    renderShell('/watchlists', 'th');
    expect(await card('รายการโปรด')).toBeInTheDocument();
    expect(screen.getByText('แจ้งเตือนเมื่อโอกาสชนะ ≥ 55%')).toBeInTheDocument();
  });
});
