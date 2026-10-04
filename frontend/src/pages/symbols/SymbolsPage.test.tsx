import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import samples from '@/test/fixtures/api-samples.json';
import { apiError, json } from '@/test/api';
import { heartbeat, iso, owner, renderShell, status } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE"), served for engine e1.
const recorded = samples as Record<string, unknown>;
const sample = (route: string) => () => json(recorded[`engines/ENGINE/${route}`]);

const QUOTE_AT = iso(Date.now() - 2_000);

function quotes(spread = 8, time = QUOTE_AT) {
  return {
    at: time,
    received_at: time,
    quotes: [
      { symbol: 'EURUSD', bid: 1.1, ask: 1.10008, spread_points: spread, max_spread_points: 30, time },
      { symbol: 'XAUUSD', bid: 2650.1, ask: 2650.4, spread_points: 30, max_spread_points: 50, time },
    ],
  };
}

function setup(extra: Record<string, () => Response> = {}) {
  return owner({
    'GET /engines/e1/quotes': () => json(quotes()),
    'GET /engines/e1/symbols': sample('symbols'),
    'GET /engines/e1/symbols/EURUSD': sample('symbols/EURUSD'),
    'GET /engines/e1/decisions?symbol=EURUSD&limit=1': sample('decisions?limit=2'),
    'GET /engines/e1/decisions/d1': sample('decisions/d1'),
    'GET /engines/e1/breakers?limit=1': () =>
      json({
        states: [
          {
            name: 'SPREAD',
            scope_key: 'EURUSD',
            state: 'OPEN',
            latched: false,
            reason: 'spread 45 pts',
            opened_at: QUOTE_AT,
          },
          {
            name: 'SPREAD',
            scope_key: 'XAUUSD',
            state: 'OPEN',
            latched: false,
            reason: '',
            opened_at: QUOTE_AT,
          },
        ],
        events: { items: [], next_cursor: null },
      }),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

describe('symbols page', () => {
  it('lists the traded symbols with their spread and searches the catalog', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/symbols');
    const traded = await card('Symbols the engine trades');
    expect(await within(traded).findByText('XAUUSD')).toBeInTheDocument();
    expect(within(traded).getByText('Spread (points): 8 / 30')).toBeInTheDocument();
    const all = await card('All broker symbols');
    expect(await within(all).findByRole('link', { name: 'EURUSD' })).toHaveAttribute(
      'href',
      '/symbols?symbol=EURUSD',
    );
    await user.type(within(all).getByRole('searchbox', { name: 'Search symbols' }), 'zzz');
    expect(within(all).getByText('No symbols found.')).toBeInTheDocument();
    await user.clear(within(all).getByRole('searchbox', { name: 'Search symbols' }));
    await user.type(within(all).getByRole('searchbox', { name: 'Search symbols' }), 'euro');
    expect(within(all).getByRole('link', { name: 'EURUSD' })).toBeInTheDocument();
  });

  it('shows the quote with the spread against the limit, the spec, context and state', async () => {
    setup();
    renderShell('/symbols?symbol=EURUSD');
    const quote = await card('Latest quote');
    const spread = await within(quote).findByRole('meter', { name: 'Spread (points)' });
    expect(spread).toHaveAttribute('aria-valuenow', '8');
    expect(spread).toHaveAttribute('aria-valuemax', '30');
    const spec = await card('Specification');
    expect(await within(spec).findByText('Full trading')).toBeInTheDocument();
    expect(within(spec).getByText('EUR / USD / EUR')).toBeInTheDocument();
    const context = await card('Market context');
    expect(await within(context).findByText('London')).toBeInTheDocument();
    expect(within(context).getAllByText('Bullish')).toHaveLength(2);
    expect(within(context).getAllByText('Trending').length).toBeGreaterThan(0);
    const state = await card('State');
    expect(await within(state).findByText('Wide spread')).toBeInTheDocument();
    expect(within(state).getAllByText('Wide spread')).toHaveLength(1); // XAUUSD's breaker is not listed
    expect(screen.getByRole('link', { name: 'Open chart' })).toHaveAttribute('href', '/charts?symbol=EURUSD');
  });

  it('updates the quote from the stream', async () => {
    setup();
    const { sources } = renderShell('/symbols?symbol=EURUSD');
    const quote = await card('Latest quote');
    await within(quote).findByRole('meter', { name: 'Spread (points)' });
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      sources.last().emit('quotes', streamEvent(2, 'quotes', { at: QUOTE_AT, quotes: quotes(27).quotes }));
    });
    await waitFor(() => {
      expect(within(quote).getByRole('meter', { name: 'Spread (points)' })).toHaveAttribute(
        'aria-valuenow',
        '27',
      );
    });
    expect(within(quote).getByRole('meter').closest('[data-level]')).toHaveAttribute('data-level', 'danger');
  });

  it('marks a quote as stale while the market is open', async () => {
    const old = iso(Date.now() - 5 * 60_000);
    setup({ 'GET /engines/e1/quotes': () => json(quotes(8, old)) });
    renderShell('/symbols?symbol=EURUSD');
    const quote = await card('Latest quote');
    expect(await within(quote).findByText(/Not updated since/)).toBeInTheDocument();
  });

  it('does not call an old quote stale while the market is closed', async () => {
    const old = iso(Date.now() - 5 * 60_000);
    setup({
      'GET /engines/e1/quotes': () => json(quotes(8, old)),
      'GET /engines/e1/status': () => json(status('e1', { heartbeat: heartbeat({ market_open: false }) })),
    });
    renderShell('/symbols?symbol=EURUSD');
    const quote = await card('Latest quote');
    await within(quote).findByRole('meter');
    expect(within(quote).queryByText(/Not updated since/)).not.toBeInTheDocument();
  });

  it('handles a symbol without a quote, analysis or catalog entry', async () => {
    setup({
      'GET /engines/e1/symbols/NOPE': () => apiError(404, 'symbol_not_found'),
      'GET /engines/e1/decisions?symbol=NOPE&limit=1': () => json({ items: [], next_cursor: null }),
    });
    renderShell('/symbols?symbol=NOPE');
    expect(await screen.findByText(/No quote for this symbol yet/)).toBeInTheDocument();
    expect(await screen.findByText('No analysis of this symbol yet.')).toBeInTheDocument();
    expect(await screen.findByText("This symbol is not in the engine's catalog.")).toBeInTheDocument();
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/symbols?symbol=EURUSD', 'th');
    expect(await screen.findByRole('region', { name: 'ข้อมูลจำเพาะ' })).toBeInTheDocument();
    expect(await screen.findByText('ลอนดอน')).toBeInTheDocument();
  });
});
