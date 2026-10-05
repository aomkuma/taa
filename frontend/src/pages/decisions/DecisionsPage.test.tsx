import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const sample = (route: string) => recorded[`engines/ENGINE/${route}`] ?? {};
const base = (sample('decisions?limit=50&profile=EXECUTION').items as Record<string, unknown>[])[0] ?? {};
const detail = sample('decisions/d1');

const rejected = {
  ...base,
  decision_id: 'd9',
  decision: 'REJECT',
  symbol: 'XAUUSD',
  action: 'SELL',
  reason_codes: ['BREAKER_OPEN:daily_loss', 'SPREAD_TOO_HIGH'],
};
const log =
  (items: unknown[], next: string | null = null) =>
  () =>
    json({ items, next_cursor: next });

const LOG = '/engines/e1/decisions?limit=50&profile=EXECUTION';

function setup(extra: Record<string, () => Response> = {}) {
  return owner({
    [`GET ${LOG}`]: log([rejected, base], 'n2'),
    [`GET ${LOG}&cursor=n2`]: log([{ ...base, decision_id: 'd10', symbol: 'GBPUSD' }]),
    'GET /engines/e1/decisions/d1': () => json(detail),
    'GET /engines/e1/decisions/d9': () =>
      json({
        ...detail,
        ...rejected,
        checks: [
          {
            seq: 0,
            name: 'spread',
            reason: 'SPREAD_TOO_HIGH',
            passed: false,
            kind: 'HARD',
            value: 45,
            threshold: 30,
            detail: '',
          },
          {
            seq: 1,
            name: 'daily_loss',
            reason: 'DAILY_LOSS_LIMIT',
            passed: true,
            kind: 'ACCOUNT',
            value: -0.4,
            threshold: -2,
            detail: '',
          },
        ],
      }),
    ...extra,
  });
}

describe('signals & decisions page', () => {
  it('lists bot decisions with their translated reasons and loads more', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/decisions');
    expect(
      await screen.findByText(/Circuit breaker tripped: daily_loss · Spread too high/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /XAUUSD SELL · Rejected/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Load more' }));
    expect(await screen.findByText(/GBPUSD/)).toBeInTheDocument();
  });

  it('filters by result, profile, reason and symbol through the URL', async () => {
    const api = setup({
      'GET /engines/e1/decisions?limit=50&decision=REJECT&profile=EXECUTION': log([rejected]),
      'GET /engines/e1/decisions?limit=50&decision=REJECT&profile=EXECUTION&reason=SPREAD_TOO_HIGH': log([
        rejected,
      ]),
      'GET /engines/e1/decisions?limit=50&decision=REJECT&reason=SPREAD_TOO_HIGH': log([rejected]),
      'GET /engines/e1/decisions?limit=50&decision=REJECT&symbol=XAUUSD&reason=SPREAD_TOO_HIGH': log([]),
    });
    const user = userEvent.setup();
    const { router } = renderShell('/decisions');
    await screen.findByRole('button', { name: /XAUUSD SELL · Rejected/ });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Result' }), 'REJECT');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Reason' }), 'SPREAD_TOO_HIGH');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Profile' }), 'ALL');
    await user.type(screen.getByRole('searchbox', { name: 'Symbol' }), 'xauusd');
    expect(await screen.findByText('No decisions match these filters.')).toBeInTheDocument();
    const paths = api.calls.map((c) => c.path);
    expect(paths).toContain(
      '/engines/e1/decisions?limit=50&decision=REJECT&profile=EXECUTION&reason=SPREAD_TOO_HIGH',
    );
    expect(paths).toContain('/engines/e1/decisions?limit=50&decision=REJECT&reason=SPREAD_TOO_HIGH'); // all profiles
    expect(router.state.location.search).toContain('reason=SPREAD_TOO_HIGH');
  });

  it('opens a decision with every check, its measured value and threshold', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/decisions');
    await user.click(await screen.findByRole('button', { name: /XAUUSD SELL/ }));
    const dialog = await screen.findByRole('dialog', { name: 'XAUUSD SELL · Rejected' });
    expect(within(dialog).getByText('Checks: 1 of 2 passed')).toBeInTheDocument();
    const rows = within(within(dialog).getByRole('table', { name: 'Check-by-check results' })).getAllByRole(
      'row',
    );
    expect(within(rows[1] as HTMLElement).getByText('Fail')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('Spread too high')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('45')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('30')).toBeInTheDocument();
    expect(within(rows[2] as HTMLElement).getByText('Pass')).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'See on the chart' })).toHaveAttribute(
      'href',
      '/charts?symbol=XAUUSD&tf=M15&decision=d9',
    );
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('shows the recorded signal: score and conditions', async () => {
    setup();
    renderShell('/decisions?id=d1');
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText(/Score 72.5/)).toBeInTheDocument();
    expect(within(dialog).getByText('✓ htf_bias')).toBeInTheDocument();
    expect(within(dialog).getByText('✗ rsi_cross')).toBeInTheDocument();
  });

  it('refreshes the log when the engine makes a decision', async () => {
    const api = setup();
    const { sources } = renderShell('/decisions');
    await screen.findByRole('button', { name: /XAUUSD SELL · Rejected/ });
    const count = () => api.calls.filter((c) => c.path === LOG).length;
    const before = count();
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      sources.last().emit('decisions', streamEvent(2, 'decision', {}));
    });
    await waitFor(() => {
      expect(count()).toBe(before + 1);
    });
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/decisions', 'th');
    expect(await screen.findByText(/เบรกเกอร์ทำงาน: daily_loss · สเปรดสูงเกินไป/)).toBeInTheDocument();
  });
});
