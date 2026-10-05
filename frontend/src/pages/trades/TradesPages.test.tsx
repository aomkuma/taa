import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { json } from '@/test/api';
import { heartbeat, owner, renderShell, status } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const sample = (route: string) => recorded[`engines/ENGINE/${route}`] ?? {};
const serve = (route: string) => () => json(sample(route));

const closedItems = sample('trades?limit=2').items as Record<string, unknown>[];
const openItems = sample('positions?status=OPEN').items as Record<string, unknown>[];
const openOne: Record<string, unknown> = {
  ...openItems[0],
  price_current: 1.1025,
  profit: 25,
  mae: 0.001,
  mfe: 0.003,
};
const filledIntent = { ...(sample('intents?kind=paper').items as Record<string, unknown>[])[0] };

function setup(extra: Record<string, () => Response> = {}) {
  return owner({
    'GET /engines/e1/positions?status=OPEN&limit=200': () => json({ items: [openOne], next_cursor: null }),
    'GET /engines/e1/intents?kind=paper&status=FILLED&limit=200': () =>
      json({ items: [{ ...filledIntent, intent_id: openOne.intent_id, sl: 1.095 }], next_cursor: null }),
    'GET /engines/e1/intents?kind=paper&status=PENDING&limit=200': () =>
      json({
        items: [{ ...filledIntent, intent_id: 'p9', status: 'PENDING', entry_type: 'LIMIT', price: 1.098 }],
        next_cursor: null,
      }),
    'GET /engines/e1/intents?kind=broker&limit=50': serve('intents?kind=broker'),
    'GET /engines/e1/trades?limit=50': () => json({ items: closedItems, next_cursor: 'c2' }),
    'GET /engines/e1/trades?limit=50&cursor=c2': () =>
      json({ items: closedItems.slice(0, 1).map((t) => ({ ...t, ticket: 99 })), next_cursor: null }),
    'GET /engines/e1/trades/1': serve('trades/1'),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

const ACCOUNT = (recorded['engines/ENGINE/status']?.heartbeat as { account: Record<string, unknown> })
  .account;
const MANUAL = {
  ticket: 4242,
  symbol: 'BTCUSD',
  side: 'BUY',
  volume: 0.1,
  price_open: 60000,
  price_current: 61000,
  sl: 59000,
  tp: null,
  profit: 100,
  swap: -2.5,
  opened_at: '2026-09-29T08:00:00+00:00',
  magic: 0,
  comment: 'by hand',
  risk_to_stop: 100,
  counted: true,
};
const withAccount = (account: Record<string, unknown>) => () =>
  json(status('e1', { heartbeat: heartbeat({ account: { ...ACCOUNT, ...account } }) }));

describe('manual positions', () => {
  it('lists the account’s manual positions read-only and how they count toward the limits', async () => {
    setup({
      'GET /engines/e1/status': withAccount({
        foreign_positions: [
          {
            ...MANUAL,
            link: {
              confidence: 'HIGH',
              strategy: 'setup_candle_reversal',
              decision_id: 'd2',
              opportunity_id: null,
              distance_r: 0.28,
            },
          },
          {
            ...MANUAL,
            ticket: 4243,
            sl: null,
            risk_to_stop: null,
            side: 'SELL',
            link: {
              confidence: 'UNMATCHED',
              strategy: null,
              decision_id: null,
              opportunity_id: null,
              distance_r: null,
            },
          },
        ],
        effective_leverage: 118.3,
        max_effective_leverage: 10,
      }),
    });
    renderShell('/positions');
    const manual = await card('Manual positions on the MT5 account');
    const rows = within(await within(manual).findByRole('table'))
      .getAllByRole('row')
      .slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('#4242');
    expect(rows[0]).toHaveTextContent(/\+USD\s97\.50/); // profit + swap
    expect(rows[1]).toHaveTextContent('none');
    // the signal each one followed, as the engine matched it (TAA-1006)
    const follows = within(rows[0] as HTMLElement).getByRole('link', { name: /Follows the .* signal/ });
    expect(follows).toHaveAttribute('href', '/decisions?profile=ALL&id=d2');
    expect(rows[0]).toHaveTextContent('(sure)');
    expect(rows[1]).toHaveTextContent('Not from a signal: your own idea');
    expect(
      within(manual).getByText(/count toward the bot's limits: USD\s100\.00 of open risk/),
    ).toBeInTheDocument();
    expect(within(manual).getByRole('alert')).toHaveTextContent('1 position(s) without a stop');
  });

  it('shows the effective leverage on the dashboard and the manual positions there', async () => {
    setup({
      'GET /engines/e1/status': withAccount({
        foreign_positions: [MANUAL],
        effective_leverage: 118.3,
        max_effective_leverage: 10,
      }),
    });
    renderShell('/');
    expect(await screen.findByText('Effective leverage')).toBeInTheDocument();
    expect(screen.getByText('118.3×')).toBeInTheDocument();
    expect(await card('Manual positions on the MT5 account')).toHaveTextContent('BTCUSD');
  });

  it('names the simulated paper book and shows the real MT5 account next to it', async () => {
    setup({
      'GET /engines/e1/status': withAccount({
        broker_account: {
          currency: 'USD',
          balance: 1105.05,
          equity: 1105.05,
          margin_free: 1100,
          leverage: 200,
        },
      }),
    });
    renderShell('/');
    expect(await screen.findByText(/The bot's PAPER book: a simulated account/)).toBeInTheDocument();
    const mt5 = await card('MT5 account (real demo account)');
    expect(mt5).toHaveTextContent(/USD\s1,105\.05/);
    expect(mt5).toHaveTextContent('1:200');
  });

  it('says when the engine does not report them yet', async () => {
    setup({ 'GET /engines/e1/status': withAccount({}) });
    renderShell('/positions');
    expect(
      await within(await card('Manual positions on the MT5 account')).findByText(/has not reported/),
    ).toBeInTheDocument();
  });
});

describe('positions page', () => {
  it('shows open positions with floating P/L, R from the initial stop and excursions', async () => {
    setup();
    renderShell('/positions');
    const region = await card('Open positions');
    const row = (await within(region).findByRole('button', { name: /#10 EURUSD BUY/ })).closest('tr');
    if (!row) throw new Error('no row');
    const cells = within(row)
      .getAllByRole('cell')
      .map((c) => c.textContent);
    expect(cells).toContain('+25'); // floating P/L
    expect(cells).toContain('+0.5'); // (1.1025 − 1.1) / 0.005
    expect(cells).toContain('-0.2 / +0.6'); // MAE / MFE in R
  });

  it('lists pending orders, and broker orders only in DEMO', async () => {
    setup();
    renderShell('/positions');
    const pending = await card('Pending orders');
    expect(await within(pending).findByText(/EURUSD BUY 0.1 · LIMIT 1.098/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Broker orders (DEMO)' })).not.toBeInTheDocument();
  });

  it('shows broker order states in DEMO', async () => {
    setup({ 'GET /engines/e1/status': () => json(status('e1', { heartbeat: heartbeat({ mode: 'DEMO' }) })) });
    renderShell('/positions');
    const broker = await card('Broker orders (DEMO)');
    const state = String((sample('intents?kind=broker').items as { state: string }[])[0]?.state);
    expect(state).not.toBe('undefined');
    expect(await within(broker).findByText(new RegExp(`EURUSD BUY 0.1 ·`))).toBeInTheDocument();
  });

  it('refreshes on position changes from the stream', async () => {
    const api = setup();
    const { sources } = renderShell('/positions');
    await within(await card('Open positions')).findByRole('button', { name: /#10/ });
    const count = () =>
      api.calls.filter((c) => c.path === '/engines/e1/positions?status=OPEN&limit=200').length;
    const before = count();
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      sources.last().emit('positions', streamEvent(2, 'paper_position', {}));
    });
    await waitFor(() => {
      expect(count()).toBe(before + 1);
    });
  });
});

describe('history page', () => {
  it('lists closed trades and loads more pages', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/history');
    const region = await card('Closed trades');
    expect(await within(region).findByRole('button', { name: /#5 EURUSD BUY/ })).toBeInTheDocument();
    expect(within(region).getAllByText('Take profit').length).toBeGreaterThan(0);
    expect(within(region).getAllByText('0 h 30 min').length).toBeGreaterThan(0);
    await user.click(within(region).getByRole('button', { name: 'Load more' }));
    expect(await within(region).findByRole('button', { name: /#99/ })).toBeInTheDocument();
    expect(within(region).queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });

  it('filters by symbol', async () => {
    const api = setup({
      'GET /engines/e1/trades?limit=50&symbol=XAUUSD': () => json({ items: [], next_cursor: null }),
    });
    const user = userEvent.setup();
    renderShell('/history');
    const region = await card('Closed trades');
    await within(region).findByRole('button', { name: /#5/ });
    await user.type(within(region).getByRole('searchbox', { name: 'Symbol' }), 'xauusd');
    expect(await within(region).findByText('No closed trades yet.')).toBeInTheDocument();
    expect(api.calls.map((c) => c.path)).toContain('/engines/e1/trades?limit=50&symbol=XAUUSD');
  });

  it('exports every closed trade as CSV', async () => {
    setup({
      'GET /engines/e1/trades?limit=200': () => json({ items: closedItems, next_cursor: 'x' }),
      'GET /engines/e1/trades?limit=200&cursor=x': () =>
        json({ items: [{ ...closedItems[0], ticket: 77 }], next_cursor: null }),
    });
    const blobs: Blob[] = [];
    const create = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return 'blob:csv';
    });
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const user = userEvent.setup();
    renderShell('/history');
    const region = await card('Closed trades');
    await within(region).findByRole('button', { name: /#5/ });
    await user.click(within(region).getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => {
      expect(click).toHaveBeenCalledTimes(1);
    });
    const text = await (blobs[0] as Blob).text();
    const lines = text.trimEnd().split('\r\n');
    expect(lines[0]?.startsWith('ticket,symbol,side')).toBe(true);
    expect(lines).toHaveLength(closedItems.length + 2);
    expect(lines.at(-1)?.startsWith('77,')).toBe(true);
    click.mockRestore();
    vi.unstubAllGlobals();
  });

  it('opens the trade drawer with its timeline from the URL', async () => {
    setup();
    renderShell('/history?trade=1');
    const drawer = await screen.findByRole('dialog', { name: '#1 EURUSD BUY' });
    const steps = within(await within(drawer).findByRole('list', { name: 'Trade timeline' })).getAllByRole(
      'listitem',
    );
    const titles = steps.map((s) => s.querySelector('p')?.textContent);
    // (the sample's signal is stamped later than its fill, so only membership is checked, not order)
    expect(titles.some((t) => t?.startsWith('Signal from example_trend_pullback'))).toBe(true);
    expect(titles.some((t) => t?.startsWith('Decision:'))).toBe(true);
    expect(titles).toEqual(
      expect.arrayContaining(['Opened BUY 0.1', 'Stop moved: Break-even', 'Closed: Take profit']),
    );
    expect(within(drawer).getByRole('link', { name: 'See this trade on the chart' })).toHaveAttribute(
      'href',
      '/charts?symbol=EURUSD&decision=d1',
    );
  });

  it('closes the drawer with Escape', async () => {
    setup();
    const user = userEvent.setup();
    const { router } = renderShell('/history');
    const region = await card('Closed trades');
    await user.click(await within(region).findByRole('button', { name: /#5 EURUSD BUY/ }));
    expect(router.state.location.search).toBe('?trade=5');
    await screen.findByRole('dialog');
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
