import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { json, makeSession, mockApi } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE"), served for engine e1.
const recorded = samples as Record<string, unknown>;
const RANKING = recorded['engines/ENGINE/ranking'] as {
  items: { symbol: string; overall: number; [key: string]: unknown }[];
  [key: string]: unknown;
};
const PREFS = recorded['advisory/preferences'] as Record<string, unknown>;

function setup() {
  let favourites: string[] = [];
  const api = owner({
    'GET /engines/e1/ranking': () => json(RANKING),
    'GET /engines/e1/ranking/XAUUSD': () => json(recorded['engines/ENGINE/ranking/XAUUSD']),
    'GET /advisory/preferences': () =>
      json({
        ...PREFS,
        watchlists: [
          {
            name: 'Favourites',
            kind: 'FAVOURITES',
            symbols: favourites,
            top_n: null,
            alerts: true,
            threshold: null,
          },
        ],
      }),
    'POST /advisory/favourites/EURUSD': () => {
      const added = !favourites.includes('EURUSD');
      favourites = added ? [...favourites, 'EURUSD'] : favourites.filter((s) => s !== 'EURUSD');
      return json({ symbol: 'EURUSD', favourite: added, favourites });
    },
  });
  return api;
}

const rows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1);
const firstCellSymbols = (table: HTMLElement) =>
  rows(table).map((row) => within(row).getAllByRole('button')[1]?.textContent);

describe('symbol ranking page', () => {
  it('shows the account the ranking was sized for and the ranked symbols with their checks', async () => {
    setup();
    renderShell('/ranking');
    const account = await screen.findByRole('region', { name: 'Account used for the ranking' });
    expect(within(account).getByText('1:500')).toBeInTheDocument();
    expect(within(account).getByText('0.5%')).toBeInTheDocument();
    expect(within(account).getAllByText(/1,000\.00/)).toHaveLength(2); // equity and balance
    const list = screen.getByRole('region', { name: 'Symbols' });
    expect(within(list).getByText('5 of 11 suitable')).toBeInTheDocument();
    const table = within(list).getByRole('table');
    expect(firstCellSymbols(table).slice(0, 3)).toEqual(['USDJPY', 'AUDUSD', 'EURUSD']);
    const gold = within(table).getByRole('button', { name: 'XAUUSD' }).closest('tr') as HTMLElement;
    expect(within(gold).getByText('Minimum lot')).toHaveAttribute(
      'title',
      expect.stringContaining('needs equity ≥ 1,538.00 USD') as string,
    );
    expect(within(gold).getByText(/needs equity ≥ USD\s1,538\.00/)).toBeInTheDocument();
    const apple = within(table).getByRole('button', { name: 'AAPL' }).closest('tr') as HTMLElement;
    expect(within(apple).getByText('Data')).toBeInTheDocument();
    expect(within(apple).getByText('Market closed')).toBeInTheDocument();
    const eur = within(table).getByRole('button', { name: 'EURUSD' }).closest('tr') as HTMLElement;
    expect(within(eur).getByText('All checks passed')).toBeInTheDocument();
    expect(within(eur).getByText('Forex majors')).toBeInTheDocument();
    expect(within(list).getByText(/Advice only/)).toBeInTheDocument();
  });

  it('sorts by the Now and Overall scores', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/ranking');
    const table = await screen.findByRole('table');
    await user.click(within(table).getByRole('button', { name: 'Overall' }));
    const best = [...RANKING.items].sort((a, b) => b.overall - a.overall)[0]?.symbol;
    expect(firstCellSymbols(table)[0]).toBe(best);
    expect(within(table).getByRole('columnheader', { name: /Overall/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
    await user.click(within(table).getByRole('button', { name: /Overall/ }));
    expect(within(table).getByRole('columnheader', { name: /Overall/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );
    await user.click(within(table).getByRole('button', { name: 'Now' }));
    expect(firstCellSymbols(table)[0]).toBe('USDJPY'); // the highest Now score
  });

  it('filters by asset class, suitability and name', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/ranking');
    const list = await screen.findByRole('region', { name: 'Symbols' });
    await within(list).findByRole('table');
    await user.selectOptions(within(list).getByRole('combobox', { name: 'Asset class' }), 'Metals');
    expect(firstCellSymbols(within(list).getByRole('table'))).toEqual(['XAUUSD', 'XAGUSD']);
    await user.click(within(list).getByRole('checkbox', { name: 'Suitable only' }));
    expect(within(list).getByText('No symbols match the filters.')).toBeInTheDocument();
    await user.selectOptions(within(list).getByRole('combobox', { name: 'Asset class' }), 'All classes');
    expect(rows(within(list).getByRole('table'))).toHaveLength(5);
    await user.type(within(list).getByRole('searchbox', { name: 'Search symbols' }), 'gbp');
    expect(firstCellSymbols(within(list).getByRole('table'))).toEqual(['GBPUSD', 'EURGBP']);
  });

  it('adds a symbol to the favourites', async () => {
    const { calls } = setup();
    const user = userEvent.setup();
    renderShell('/ranking');
    const star = await screen.findByRole('button', { name: 'Add EURUSD to favourites' });
    expect(star).toHaveAttribute('aria-pressed', 'false');
    await user.click(star);
    const on = await screen.findByRole('button', { name: 'Remove EURUSD from favourites' });
    expect(on).toHaveAttribute('aria-pressed', 'true');
    const post = calls.find((c) => c.method === 'POST');
    expect(post?.path).toBe('/advisory/favourites/EURUSD');
    expect(post?.headers['x-csrf-token']).toBe('csrf-123');
  });

  it('opens the score drawer with every score, gate and metric', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/ranking');
    await user.click(await screen.findByRole('button', { name: 'XAUUSD' }));
    const dialog = await screen.findByRole('dialog', { name: 'XAUUSD · rank 6' });
    expect(within(dialog).getAllByRole('meter')).toHaveLength(9);
    expect(within(dialog).getByRole('meter', { name: 'Sizing room' })).toHaveAttribute('aria-valuenow', '0');
    expect(within(dialog).getAllByText('(Overall)')).toHaveLength(5);
    const checks = within(dialog).getByRole('region', { name: 'Checks' });
    expect(within(checks).getAllByText('Passed')).toHaveLength(5);
    expect(within(checks).getByText('Failed')).toBeInTheDocument();
    expect(within(checks).getByText(/needs equity ≥ 1,538\.00 USD/)).toBeInTheDocument();
    const sizing = within(dialog).getByRole('region', { name: 'Sizing and costs' });
    expect(within(sizing).getByText('Equity the minimum lot needs')).toBeInTheDocument();
    expect(within(dialog).getByText(/Too few past outcomes/)).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Open chart' })).toHaveAttribute(
      'href',
      '/charts?symbol=XAUUSD',
    );
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('opens the drawer from a link and says when a symbol has no ranking', async () => {
    setup();
    renderShell('/ranking?symbol=NOPE');
    const dialog = await screen.findByRole('dialog', { name: 'NOPE' });
    expect(await within(dialog).findByText('No ranking details for this symbol.')).toBeInTheDocument();
  });

  it('ranks on the market feed for the user’s own account', async () => {
    const personal = {
      ...RANKING,
      personal: true,
      account: {
        source: 'MANUAL',
        equity: 500,
        balance: 500,
        leverage: 100,
        currency: 'EUR',
        risk_percent: 1,
      },
      items: RANKING.items.map((item) => ({
        ...item,
        gates: [],
        metrics: {},
        personal:
          item.symbol === 'XAUUSD'
            ? { eligible: false, currency: 'EUR', affordable: false, required_equity: 770 }
            : { eligible: true, currency: 'EUR', affordable: true, lot: 0.01 },
      })),
    };
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: 'feed', own: false }),
      'GET /engines': () => json({ items: [] }),
      'GET /engines/feed/ranking': () => json(personal),
      'GET /advisory/preferences': () => json(PREFS),
    });
    renderShell('/ranking');
    const account = await screen.findByRole('region', { name: 'Account used for the ranking' });
    expect(within(account).getByText('Sized for your own account profile.')).toBeInTheDocument();
    expect(within(account).getByText('1:100')).toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).queryByRole('columnheader', { name: 'Lot' })).not.toBeInTheDocument();
    const gold = within(table).getByRole('button', { name: 'XAUUSD' }).closest('tr') as HTMLElement;
    expect(within(gold).getByText(/needs equity ≥ EUR\s770\.00/)).toBeInTheDocument();
    expect(screen.getByText('10 of 11 suitable')).toBeInTheDocument();
  });

  it('says when only part of the universe is ranked yet (after a restart)', async () => {
    owner({
      'GET /engines/e1/ranking': () => json({ ...RANKING, universe: 541 }),
      'GET /advisory/preferences': () => json(PREFS),
    });
    renderShell('/ranking');
    expect(await screen.findByText(/Ranked 11 of 541 symbols so far/)).toBeInTheDocument();
  });

  it('says when the engine has not ranked yet', async () => {
    owner({
      'GET /engines/e1/ranking': () => json({ computed_at: null, account: null, items: [] }),
    });
    renderShell('/ranking');
    expect(await screen.findByText(/No ranking yet/)).toBeInTheDocument();
  });
});

describe('dashboard top-ranked widget', () => {
  it('lists the top five suitable symbols on the market feed', async () => {
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: 'e1', own: false }),
      'GET /engines': () => json({ items: [] }),
      'GET /engines/e1/ranking': () => json(RANKING),
    });
    renderShell('/');
    const card = await screen.findByRole('region', { name: 'Top ranked symbols' });
    await within(card).findByRole('link', { name: 'USDJPY' });
    const links = within(card).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual([
      'Full ranking',
      'USDJPY',
      'AUDUSD',
      'EURUSD',
      'GBPUSD',
      'EURGBP',
    ]);
    expect(links[1]).toHaveAttribute('href', '/ranking?symbol=USDJPY');
  });
});
