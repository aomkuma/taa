import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { type FakeRequest, type Handler, json } from '@/test/api';
import { owner, renderShell, status } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';
import type { Preferences } from '@/pages/watchlists/schemas';

// The real `GET /advisory/preferences` of tests/web/test_api_samples.py (the defaults).
const PREFS = (samples as Record<string, unknown>)['advisory/preferences'] as Preferences;

/** What `POST /engines/{id}/entry-plan/preview` answers: the draft's parts on an example EURUSD trade. */
function preview(request: FakeRequest) {
  const body = request.body as { entry_plan: { mode: string; parts: number } };
  const parts = body.entry_plan.mode === 'SINGLE' ? 1 : body.entry_plan.parts;
  return json({
    available: true,
    example: { symbol: 'EURUSD', side: 'BUY', entry: 1.1, stop: 1.098, take_profit: 1.104 },
    currency: 'USD',
    equity: 1000,
    budget: 7.5,
    lot: 0.03 * parts,
    risk_money: 6 * parts,
    taps: 3 * parts,
    plan: Array.from({ length: parts }, (_, i) => ({
      entry: i === 0 ? '1.1' : '1.099',
      order_type: i === 0 ? 'MARKET' : 'LIMIT',
      take_profit: '1.104',
      volume: '0.03',
      taps: 3,
      risk_money: '6',
    })),
  });
}

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /advisory/preferences': () => json(PREFS),
    'POST /engines/e1/entry-plan/preview': preview,
    'PUT /advisory/preferences': (request) => json(request.body),
    ...extra,
  });
}

const region = (name: string) => screen.findByRole('region', { name });
// the engine's heartbeat as tests/web/test_api_samples.py records it: the owner's profile in a 0.5 % cage
const recordedStatus = (samples as Record<string, Record<string, unknown>>)['engines/ENGINE/status'] ?? {};
const withLimits = () => json(status('e1', { heartbeat: recordedStatus.heartbeat }));
// a large form: typing into it takes a while when the suite runs in parallel
vi.setConfig({ testTimeout: 20_000 });

describe('trading profile page', () => {
  it('shows the slider’s numbers live and lets a field be set by hand and reset', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/profile');
    const style = await region('Style');
    const risk = within(style).getByText('Risk per signal (all entries)').closest('tr') as HTMLElement;
    expect(risk).toHaveTextContent('0.75%');
    fireEvent.change(within(style).getByLabelText(/^Style/), { target: { value: '100' } });
    expect(risk).toHaveTextContent('1.5%');
    expect(within(style).getByText(/100 · Very offensive/)).toBeInTheDocument();
    expect(await region('Worth a second look')).toHaveTextContent('Risk per signal above 1% of equity.');

    await user.click(within(style).getByRole('button', { name: 'Set Min reward : risk yourself' }));
    const rr = within(style).getByRole('spinbutton', { name: 'Min reward : risk' });
    expect(rr).toHaveValue(1.2);
    await user.clear(rr);
    await user.type(rr, '0.5');
    expect(rr).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('button', { name: 'Save trading profile' })).toBeDisabled();
    await user.click(within(style).getByRole('button', { name: 'Reset Min reward : risk to the slider' }));
    expect(within(style).queryByRole('spinbutton', { name: 'Min reward : risk' })).not.toBeInTheDocument();
  });

  it('splits the entry, shows the example breakdown and saves both sections', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/profile');
    const plan = await region('Splitting an entry');
    const example = within(plan).getByRole('region', { name: 'Example' });
    expect(await within(example).findByText(/EURUSD BUY at 1.1/)).toBeInTheDocument();
    await user.click(within(plan).getByLabelText(/Scale in/));
    await user.click(within(plan).getByLabelText('Back-loaded (1:2:3)'));
    await waitFor(() => {
      expect(within(example).getAllByRole('row').slice(1)).toHaveLength(2);
    });
    expect(within(example).getByText('Limit')).toBeInTheDocument();
    expect(await region('Worth a second look')).toHaveTextContent(/Back-loaded scale-in/);
    const lastPreview = api.calls.filter((c) => c.path === '/engines/e1/entry-plan/preview').at(-1);
    expect(lastPreview?.body).toMatchObject({
      entry_plan: { mode: 'SCALE_IN', parts: 2, weights: 'BACK_LOADED' },
    });

    await user.selectOptions(within(await region('Habits')).getByLabelText('Holding style'), 'SWING');
    await user.click(screen.getByRole('button', { name: 'Save trading profile' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.');
    const put = api.calls.find((c) => c.method === 'PUT')?.body as Preferences;
    expect(put.entry_plan).toMatchObject({ mode: 'SCALE_IN', parts: 2, weights: 'BACK_LOADED' });
    expect(put.trading_profile.holding_style).toBe('SWING');
    expect(put.watchlists).toEqual(PREFS.watchlists); // the other sections are kept
  });

  it('checks partial take-profits and explains a missing account', async () => {
    setup({
      'POST /engines/e1/entry-plan/preview': () => json({ available: false, reason: 'no_account' }),
    });
    const user = userEvent.setup();
    renderShell('/profile');
    const plan = await region('Splitting an entry');
    expect(await within(plan).findByText('No account to size with yet.')).toBeInTheDocument();
    expect(within(plan).getByRole('link', { name: 'Set your account' })).toHaveAttribute('href', '/account');
    await user.click(within(plan).getByLabelText(/Several orders at one price/));
    const tp1 = within(plan).getByLabelText(/^TP1/);
    await user.clear(tp1);
    await user.type(tp1, '0');
    expect(within(plan).getByText(/One take-profit per order except the last/)).toBeInTheDocument();
    expect(within(plan).getByText('Fix the plan above to see an example.')).toBeInTheDocument();
  });

  it('renders in Thai', async () => {
    setup();
    renderShell('/profile', 'th');
    expect(await screen.findByRole('heading', { name: 'บุคลิกการเทรด' })).toBeInTheDocument();
    expect(await region('การแบ่งไม้')).toBeInTheDocument();
  });

  it('shows what the engine trades with and when it has not picked up a save yet', async () => {
    setup({ 'GET /engines/e1/status': withLimits });
    const user = userEvent.setup();
    renderShell('/profile');
    const inUse = await region('Risk limits in use');
    const perTrade = within(inUse).getByRole('row', { name: /Risk per trade/ });
    expect(perTrade).toHaveTextContent('limited by the engine machine');
    expect(within(inUse).queryByRole('status')).not.toBeInTheDocument(); // the saved style 50 is applied

    const style = await region('Style');
    fireEvent.change(within(style).getByLabelText(/^Style/), { target: { value: '100' } });
    await user.click(screen.getByRole('button', { name: 'Save trading profile' }));
    expect(await within(inUse).findByRole('status')).toHaveTextContent('within about a minute');
  });
});
