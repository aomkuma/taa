import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json, makeSession, mockApi } from '@/test/api';
import { iso, owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py (the engine's scanner on FakeMT5), served for e1 with
// their windows moved to now.
const recorded = samples as Record<string, Record<string, unknown>>;
const OPP = 'ebf613a7581b7648eaca8328cdccb599d0751b14ec0d0d451901e2799917e5de';
const LIST = recorded['engines/ENGINE/opportunities?limit=50'] as { items: Record<string, unknown>[] };
const DETAIL = recorded[`engines/ENGINE/opportunities/${OPP}`] ?? {};
const SCOREBOARD = recorded['engines/ENGINE/theory-scoreboard'];

/** Window: found 10 minutes ago, *left* minutes left. */
function live(o: Record<string, unknown>, left: number) {
  const now = Date.now();
  return { ...o, created_at: iso(now - 10 * 60_000), valid_until: iso(now + left * 60_000) };
}

function lists(left = 20) {
  const [eur, xau] = LIST.items as [Record<string, unknown>, Record<string, unknown>];
  const expired = {
    ...eur,
    opportunity_id: 'old',
    symbol: 'GBPUSD',
    status: 'EXPIRED',
    status_reason: 'SESSION_END:LONDON',
  };
  return { items: [live(eur, left), live(xau, 1), expired], next_cursor: null };
}

function setup(left = 20) {
  return owner({
    'GET /engines/e1/opportunities?limit=50': () => json(lists(left)),
    [`GET /engines/e1/opportunities/${OPP}`]: () => json(live(DETAIL, left)),
    'GET /engines/e1/theory-scoreboard': () => json(SCOREBOARD),
  });
}

const card = (symbol: string, side = 'BUY') => screen.findByRole('article', { name: `${symbol} ${side}` });

describe('opportunities page', () => {
  it('shows live cards with both metrics, prices, money, theories and the countdown', async () => {
    setup();
    renderShell('/opportunities');
    const eur = await card('EURUSD');
    expect(within(eur).getByText('Active')).toBeInTheDocument();
    expect(within(eur).getByText(/^(19|20):\d\d left$/)).toBeInTheDocument();
    expect(within(eur).getByText('Win probability')).toBeInTheDocument();
    expect(within(eur).getByText('insufficient data')).toBeInTheDocument();
    expect(within(eur).getByText('Setup strength')).toBeInTheDocument();
    expect(within(eur).getByText('Random baseline')).toBeInTheDocument();
    expect(within(eur).getByText('Break-even')).toBeInTheDocument();
    expect(within(eur).getByText('Expected value')).toBeInTheDocument();
    expect(within(eur).getByText('1:2')).toBeInTheDocument();
    expect(within(eur).getByText(/USD\s48\.72/)).toBeInTheDocument(); // risk
    expect(within(eur).getByText('7 theories support · 4 conflict')).toBeInTheDocument();
    expect(within(eur).getByText('Daily loss limit reached')).toBeInTheDocument();
    expect(within(eur).getByRole('link', { name: 'Details' })).toHaveAttribute(
      'href',
      `/opportunities/${OPP}`,
    );
    expect(within(eur).getByRole('link', { name: 'Open chart' })).toHaveAttribute(
      'href',
      `/charts?symbol=EURUSD&opportunity=${OPP}&tf=M15`,
    );
    // XAUUSD has 1 minute of a 11-minute window left: ending soon; it is listed first
    const gold = await card('XAUUSD');
    expect(within(gold).getByText('Ending soon')).toBeInTheDocument();
    expect(screen.getAllByRole('article')[0]).toBe(gold);
    expect(screen.queryByRole('article', { name: 'GBPUSD BUY' })).not.toBeInTheDocument(); // not open
  });

  it('lists ended ones with their reason under All', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/opportunities');
    await card('EURUSD');
    await user.click(screen.getByRole('button', { name: 'All recent (3)' }));
    const old = await card('GBPUSD');
    expect(within(old).getByText('Suitable time has passed')).toBeInTheDocument();
    expect(within(old).getByText('the LONDON session ended')).toBeInTheDocument();
  });

  it('marks a card expired when its window passes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      setup(0.05); // 3 s left
      renderShell('/opportunities');
      await card('EURUSD');
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5_000);
      });
      await waitFor(() => {
        expect(screen.queryByRole('article', { name: 'EURUSD BUY' })).not.toBeInTheDocument();
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it('sets the app badge to the active count where supported', async () => {
    const setAppBadge = vi.fn(() => Promise.resolve());
    const clearAppBadge = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { setAppBadge, clearAppBadge });
    try {
      setup();
      renderShell('/opportunities');
      await card('EURUSD');
      await waitFor(() => {
        expect(setAppBadge).toHaveBeenCalledWith(1);
      });
    } finally {
      Reflect.deleteProperty(navigator, 'setAppBadge');
      Reflect.deleteProperty(navigator, 'clearAppBadge');
    }
  });

  it('explains where the % comes from on the detail page (push deep link)', async () => {
    setup();
    renderShell(`/opportunities/${OPP}`);
    const why = await screen.findByRole('region', { name: 'Where the % comes from' });
    expect(within(why).getByText(/Starting from the base rate of/)).toBeInTheDocument();
    const raise = within(why).getByRole('region', { name: 'Theories that raise it' });
    const first = within(raise).getAllByRole('listitem')[0] as HTMLElement;
    expect(await within(first).findByText(/Track record here: hit 100% of 3/)).toBeInTheDocument();
    expect(within(why).getAllByText(/No track record here yet/).length).toBeGreaterThan(0);
    expect(within(why).getByText(/theory families support it/)).toBeInTheDocument();
    const evidence = screen.getByRole('region', { name: 'Evidence' });
    expect(within(evidence).getByRole('region', { name: 'Supports' })).toBeInTheDocument();
    expect(within(evidence).getByRole('heading', { name: 'Conflicts (4)' })).toBeInTheDocument();
    expect(within(evidence).getAllByRole('link', { name: /show on chart/ })[0]).toHaveAttribute(
      'href',
      expect.stringContaining(`opportunity=${OPP}`) as string,
    );
    const plan = screen.getByRole('region', { name: 'Entry plan (MT5)' });
    expect(within(plan).getByText(/MARKET 0\.28 lot at 1\.12652/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '← All opportunities' })).toHaveAttribute(
      'href',
      '/opportunities',
    );
  });

  it('says when an opportunity no longer exists', async () => {
    owner({ 'GET /engines/e1/opportunities/nope': () => apiError(404, 'opportunity_not_found') });
    renderShell('/opportunities/nope');
    expect(await screen.findByText('This opportunity no longer exists.')).toBeInTheDocument();
  });

  it('shows the user’s own sizing on the market feed, without chart links', async () => {
    const feedDetail = {
      ...live(DETAIL, 20),
      lot: undefined,
      risk_money: undefined,
      reward_money: undefined,
      warnings: undefined,
      plan: undefined,
      my_sizing: { available: true, currency: 'EUR', lot: 0.02, risk_money: 5 },
    };
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: 'feed', own: false }),
      'GET /engines': () => json({ items: [] }),
      [`GET /engines/feed/opportunities/${OPP}`]: () =>
        json(JSON.parse(JSON.stringify(feedDetail)) as unknown),
      'GET /engines/feed/theory-scoreboard': () => json(SCOREBOARD),
    });
    renderShell(`/opportunities/${OPP}`);
    const mine = await screen.findByRole('region', { name: 'For your account' });
    expect(within(mine).getByText(/Lot 0\.02, risking EUR\s5\.00/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /chart/ })).not.toBeInTheDocument();
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/opportunities', 'th');
    const eur = await screen.findByRole('article', { name: 'EURUSD BUY' });
    expect(within(eur).getByText('ใช้งานอยู่')).toBeInTheDocument();
    expect(within(eur).getByText('ความน่าจะเป็นที่จะชนะ')).toBeInTheDocument();
  });
});
