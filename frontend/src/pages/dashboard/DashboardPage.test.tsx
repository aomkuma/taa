import { act, screen, waitFor, within } from '@testing-library/react';

import { json, makeSession, mockApi } from '@/test/api';
import { heartbeat, iso, owner, renderShell, status } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

function account(overrides: Record<string, unknown> = {}) {
  return {
    as_of: iso(Date.now() - 2_000),
    backend: 'paper',
    currency: 'USD',
    balance: 10_000,
    equity: 9_900,
    margin: 120,
    margin_free: 9_780,
    day_pnl: -100,
    day_pnl_percent: -1,
    week_pnl: 50,
    week_pnl_percent: 0.5,
    drawdown_percent: 1.8,
    open_risk: 130,
    heat_percent: 1.3131,
    unknown_risk_positions: 0,
    consecutive_losses: 4,
    limits: {
      daily_loss_percent: 2,
      weekly_loss_percent: 4,
      drawdown_percent: 10,
      heat_percent: 1.5,
      consecutive_losses: 4,
    },
    ...overrides,
  };
}

const position = {
  ticket: 10,
  symbol: 'EURUSD',
  side: 'BUY',
  volume: 0.1,
  entry_price: 1.1,
  entry_time: iso(Date.now() - 600_000),
  sl: 1.095,
  tp: 1.11,
  price_current: 1.102,
};

const decision = {
  decision_id: 'd1',
  created_at: iso(Date.now() - 60_000),
  symbol: 'XAUUSD',
  strategy: 'example_trend_pullback',
  action: 'SELL',
  decision: 'REJECT',
  reason_codes: ['SPREAD_TOO_WIDE'],
};

const page = (items: unknown[]) => json({ items, next_cursor: null });

const POSITIONS = '/engines/e1/positions?status=OPEN&limit=5';
const DECISIONS = '/engines/e1/decisions?profile=EXECUTION&limit=5';
const BREAKERS = '/engines/e1/breakers?limit=1';
const ALERTS = '/notifications?limit=5';

function ownerWithData(overrides: Record<string, () => Response> = {}) {
  return owner({
    'GET /engines/e1/status': () =>
      json(status('e1', { heartbeat: heartbeat({ account: account(), open_positions: 1 }) })),
    [`GET ${POSITIONS}`]: () => page([position]),
    [`GET ${DECISIONS}`]: () => page([decision]),
    [`GET ${BREAKERS}`]: () =>
      json({
        states: [
          {
            name: 'SPREAD',
            scope_key: 'XAUUSD',
            state: 'OPEN',
            latched: false,
            reason: 'spread 80 pts',
            opened_at: iso(Date.now()),
          },
          { name: 'CLOCK', scope_key: '', state: 'CLOSED', latched: false, reason: '', opened_at: null },
        ],
        events: { items: [], next_cursor: null },
      }),
    [`GET ${ALERTS}`]: () =>
      page([
        {
          notification_id: 'n1',
          engine_id: 'e1',
          type: 'ENGINE_OFFLINE',
          severity: 'CRITICAL',
          payload: {},
          created_at: iso(Date.now() - 3_600_000),
          read_at: null,
        },
      ]),
    ...overrides,
  });
}

const card = (name: string) => screen.findByRole('region', { name });
const level = (meter: HTMLElement) => meter.closest('[data-level]')?.getAttribute('data-level');

describe('dashboard', () => {
  it('shows equity and every limit gauge from the account snapshot', async () => {
    ownerWithData();
    renderShell('/');
    const region = await card('Account and risk limits');
    expect(await within(region).findByText('USD 9,900.00')).toBeInTheDocument();
    const day = within(region).getByRole('meter', { name: "Today's P/L" });
    expect(day).toHaveAttribute('aria-valuenow', '1');
    expect(level(day)).toBe('warn');
    expect(within(region).getByText('-USD 100.00 (-1%)')).toBeInTheDocument();
    // A gain uses none of the weekly loss limit.
    expect(within(region).getByRole('meter', { name: "This week's P/L" })).toHaveAttribute(
      'aria-valuenow',
      '0',
    );
    expect(level(within(region).getByRole('meter', { name: 'Open risk' }))).toBe('danger');
    expect(level(within(region).getByRole('meter', { name: 'Consecutive losses' }))).toBe('breached');
    expect(within(region).getByText('Limit reached')).toBeInTheDocument();
  });

  it('lists positions, open breakers, recent decisions and alerts', async () => {
    ownerWithData();
    renderShell('/');
    const positions = await card('Open positions');
    expect(await within(positions).findByText('EURUSD BUY 0.1')).toBeInTheDocument();
    expect(within(positions).getByText('1 open')).toBeInTheDocument();
    const breakers = await card('Breakers and kill switch');
    expect(await within(breakers).findByText('Wide spread · XAUUSD')).toBeInTheDocument();
    expect(within(breakers).queryByText('Server time')).not.toBeInTheDocument();
    expect(within(breakers).getByText('Kill switch off')).toBeInTheDocument();
    const decisions = await card('Recent decisions');
    expect(await within(decisions).findByText('XAUUSD SELL · Rejected')).toBeInTheDocument();
    const alerts = await card('Recent notifications');
    expect(await within(alerts).findByText('Engine offline')).toBeInTheDocument();
  });

  it('shows open opportunities and the signal track record', async () => {
    const recorded = samples as Record<string, unknown>;
    ownerWithData({
      'GET /engines/e1/opportunities?limit=50': () => json(recorded['engines/ENGINE/opportunities?limit=50']),
      'GET /engines/e1/accuracy?variant=PLAN': () => json(recorded['engines/ENGINE/accuracy']),
    });
    renderShell('/');
    const open = await card('Open opportunities');
    expect(await within(open).findByRole('link', { name: 'EURUSD BUY' })).toBeInTheDocument();
    expect(within(open).queryByText(/XAUUSD/)).not.toBeInTheDocument(); // a candidate is not open
    const track = await card('Signal track record');
    expect(await within(track).findByText('40%')).toBeInTheDocument();
    expect(track).toHaveTextContent('+0.35R');
    expect(track).toHaveTextContent('Simulated');
  });

  it('shows system health from the heartbeat', async () => {
    ownerWithData({
      'GET /engines/e1/status': () =>
        json(status('e1', { heartbeat: heartbeat({ clock_verified: false, outbox_pending: 12 }) })),
    });
    renderShell('/');
    const health = await card('System health');
    expect(await within(health).findByText('Not verified')).toBeInTheDocument();
    expect(within(health).getByText('Connected')).toBeInTheDocument();
    expect(within(health).getByText('12')).toBeInTheDocument();
  });

  it('says when the engine has not sent account data yet', async () => {
    ownerWithData({ 'GET /engines/e1/status': () => json(status('e1')) });
    renderShell('/');
    expect(await screen.findByText('No account data from the engine yet.')).toBeInTheDocument();
  });

  it('marks the account as stale when the engine went silent', async () => {
    ownerWithData({
      'GET /engines/e1/status': () =>
        json(
          status('e1', {
            heartbeat: heartbeat({ account: account(), received_at: iso(Date.now() - 10 * 60_000) }),
          }),
        ),
    });
    renderShell('/');
    const region = await card('Account and risk limits');
    expect(await within(region).findByText(/Not updated since/)).toBeInTheDocument();
  });

  it('warns about positions with unknown risk and shows missing figures as a dash', async () => {
    ownerWithData({
      'GET /engines/e1/status': () =>
        json(
          status('e1', {
            heartbeat: heartbeat({
              account: account({ unknown_risk_positions: 2, heat_percent: null, open_risk: null }),
            }),
          }),
        ),
    });
    renderShell('/');
    const region = await card('Account and risk limits');
    expect(await within(region).findByText(/2 position\(s\) with unknown risk/)).toBeInTheDocument();
    expect(within(region).getByText('— (—)')).toBeInTheDocument();
  });

  it('refreshes the widgets from the live stream', async () => {
    const api = ownerWithData();
    const { sources } = renderShell('/');
    await screen.findByText('EURUSD BUY 0.1');
    await screen.findByText('Engine offline');
    const count = (path: string) => api.calls.filter((c) => c.path === path).length;
    const before = [POSITIONS, DECISIONS, BREAKERS, ALERTS].map(count);
    act(() => {
      const source = sources.last();
      source.emit('ready', { cursor: 1, resumed: true });
      source.emit('positions', streamEvent(2, 'paper_position', {}));
      source.emit('decisions', streamEvent(3, 'decision', {}));
      source.emit('status', streamEvent(4, 'breaker', {}));
      source.emit('notifications', streamEvent(5, 'notification', {}));
    });
    await waitFor(() => {
      expect([POSITIONS, DECISIONS, BREAKERS, ALERTS].map(count)).toEqual(before.map((n) => n + 1));
    });
    // A heartbeat updates the account in place, without a request.
    act(() => {
      sources
        .last()
        .emit('status', streamEvent(6, 'heartbeat', heartbeat({ account: account({ equity: 9_800 }) })));
    });
    expect(await screen.findByText('USD 9,800.00')).toBeInTheDocument();
  });

  it('shows the market feed without account widgets to a subscriber', async () => {
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: 'owner-engine', own: false }),
      'GET /engines': () => json({ items: [] }),
      [`GET ${ALERTS}`]: () => page([]),
    });
    renderShell('/');
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Account and risk limits' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Opportunities' }).length).toBeGreaterThan(0);
  });
});
