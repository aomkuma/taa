import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json, makeSession } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import { streamEvent } from '@/test/eventSource';
import samples from '@/test/fixtures/api-samples.json';

// Real responses recorded by tests/web/test_api_samples.py, served for engine e1.
const recorded = samples as Record<string, Record<string, unknown>>;
const sample = (route: string) => recorded[`engines/ENGINE/${route}`] ?? {};
const status = sample('status') as { kill_switch: Record<string, unknown> };
const inactive = { ...status, kill_switch: { ...status.kill_switch, active: false } };
const COMMANDS = '/engines/e1/commands?limit=20';
const until = () => new Date(Date.now() + 300_000).toISOString().replace('Z', '+00:00');
const queued = (type: string) => ({
  ...(sample('commands?limit=20').items as Record<string, unknown>[])[0],
  id: 'c9',
  type,
  status: 'QUEUED',
  result: {},
});

function setup(extra: Record<string, () => Response> = {}, session: Record<string, unknown> = makeSession()) {
  return owner({
    'GET /auth/session': () => json(session),
    'GET /engines/e1/status': () => json(status),
    'GET /engines/e1/config': () => json(sample('config')),
    'GET /engines/e1/kill-switch?limit=20': () => json(sample('kill-switch?limit=20')),
    'GET /engines/e1/breakers?limit=20': () => json(sample('breakers?limit=20')),
    [`GET ${COMMANDS}`]: () => json(sample('commands?limit=20')),
    'POST /auth/step-up': () => json({ step_up_until: until() }),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

describe('risk & controls page', () => {
  it('shows the kill switch, limits, breakers and command history', async () => {
    setup();
    renderShell('/risk');
    const kill = await card('Kill switch');
    expect(
      await within(kill).findByText(/Kill switch ACTIVE \(Halt \(no new trades\)\)/),
    ).toBeInTheDocument();
    expect(within(kill).getByText(/Activated by owner \(cli\)/)).toBeInTheDocument();
    expect(within(kill).getByRole('button', { name: 'Activate kill switch' })).toBeDisabled(); // already on
    expect(within(kill).getByRole('button', { name: 'Flatten all' })).toBeEnabled();
    expect(
      within(kill).getAllByText('python -m app.cli kill --release --reason "..."').length,
    ).toBeGreaterThan(0);

    const limits = within(await card('Limits')).getByRole('table', { name: 'Limits' });
    const daily = within(limits).getByRole('row', { name: /Today's loss/ });
    expect(within(daily).getByText('0.1%')).toBeInTheDocument();
    expect(within(daily).getByText('2%')).toBeInTheDocument();
    expect(within(daily).getByText('OK')).toBeInTheDocument();
    expect(within(limits).getByRole('row', { name: /Open positions/ })).toHaveTextContent('120');

    const inUse = within(await card('Risk limits in use')).getByRole('table', { name: 'Risk limits in use' });
    const perTrade = within(inUse).getByRole('row', { name: /Risk per trade/ });
    expect(perTrade).toHaveTextContent('0.75%'); // the owner's profile …
    expect(perTrade).toHaveTextContent('limited by the engine machine'); // … capped at the 0.5 % config.yaml
    expect(within(inUse).getByRole('row', { name: /Open positions/ })).not.toHaveTextContent('limited');
    expect(
      screen.getByText(/your trading profile, received from the cloud. · confirmed 2 min ago/),
    ).toBeInTheDocument();

    const breakers = await card('Circuit breakers');
    expect(await within(breakers).findByText('Normal')).toBeInTheDocument();
    expect(within(breakers).getByText(/· Tripped/)).toBeInTheDocument();

    const commands = await card('Command history');
    expect(await within(commands).findByText('Disable strategy')).toBeInTheDocument();
    expect(within(commands).getByText('Done', { selector: 'span' })).toBeInTheDocument();
    expect(within(commands).getByText(/strategy: setup_breakout/)).toBeInTheDocument();
  });

  it('flattens all after the reason, the engine code and a fresh sign-in code', async () => {
    const api = setup({ 'POST /engines/e1/commands': () => json(queued('FLATTEN_ALL'), 202) });
    const user = userEvent.setup();
    renderShell('/risk');
    const kill = await card('Kill switch');
    await user.click(await within(kill).findByRole('button', { name: 'Flatten all' }));
    const dialog = await screen.findByRole('dialog', { name: 'Close every bot position?' });
    await user.click(within(dialog).getByRole('button', { name: 'Flatten all' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter a reason.');
    await user.type(within(dialog).getByRole('textbox', { name: 'Reason' }), 'news spike');
    await user.click(within(dialog).getByRole('button', { name: 'Flatten all' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter the 6-digit engine control code.');
    await user.type(within(dialog).getByRole('textbox', { name: 'Engine control code' }), '654321');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    await user.click(within(dialog).getByRole('button', { name: 'Flatten all' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(api.calls.filter((c) => c.method === 'POST').map((c) => [c.path, c.body])).toEqual([
      ['/auth/step-up', { code: '123456' }],
      ['/engines/e1/commands', { type: 'FLATTEN_ALL', reason: 'news spike', code: '654321' }],
    ]);
  });

  it('activates the kill switch with a valid step-up and shows the engine refusing a command', async () => {
    const session = { ...makeSession(), step_up_until: until() };
    const api = setup(
      {
        'GET /engines/e1/status': () => json(inactive),
        'POST /engines/e1/commands': () => json(queued('KILL_SWITCH_ACTIVATE'), 202),
      },
      session,
    );
    const user = userEvent.setup();
    const { sources } = renderShell('/risk');
    const kill = await card('Kill switch');
    expect(await within(kill).findByText(/Kill switch off/)).toBeInTheDocument();
    await user.click(within(kill).getByRole('button', { name: 'Activate kill switch' }));
    const dialog = await screen.findByRole('dialog', { name: 'Activate the kill switch?' });
    expect(within(dialog).queryByRole('textbox', { name: 'Engine control code' })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('textbox', { name: 'Authenticator code' })).not.toBeInTheDocument();
    await user.type(within(dialog).getByRole('textbox', { name: 'Reason' }), 'stop for today');
    await user.click(within(dialog).getByRole('button', { name: 'Activate kill switch' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({
      type: 'KILL_SWITCH_ACTIVATE',
      reason: 'stop for today',
    });
    const count = () => api.calls.filter((c) => c.path === COMMANDS).length;
    const before = count();
    act(() => {
      sources.last().emit('ready', { cursor: 1, resumed: true });
      sources.last().emit('status', streamEvent(2, 'command', queued('KILL_SWITCH_ACTIVATE')));
    });
    await waitFor(() => {
      expect(count()).toBeGreaterThan(before);
    });
  });

  it('explains when flatten is off on the engine and gives support accounts no controls', async () => {
    const config = sample('config') as { config: { env: Record<string, unknown> } };
    const off = {
      ...config,
      config: { ...config.config, env: { ...config.config.env, KILL_SWITCH_FLATTEN_ALLOWED: false } },
    };
    setup({ 'GET /engines/e1/config': () => json(off) });
    renderShell('/risk');
    const kill = await card('Kill switch');
    expect(await within(kill).findByText(/KILL_SWITCH_FLATTEN_ALLOWED=false/)).toBeInTheDocument();
    expect(within(kill).getByRole('button', { name: 'Flatten all' })).toBeDisabled();
  });

  it('shows no control buttons to an ADMIN', async () => {
    const session = makeSession();
    setup({}, { ...session, user: { ...session.user, role: 'ADMIN' } });
    renderShell('/risk');
    const kill = await card('Kill switch');
    expect(await within(kill).findByText('Support accounts have no trading controls.')).toBeInTheDocument();
    expect(within(kill).queryByRole('button')).not.toBeInTheDocument();
  });

  it('closes a position from the positions page with the engine code', async () => {
    const positions = recorded['engines/ENGINE/positions?status=OPEN'] ?? { items: [], next_cursor: null };
    const ticket = (positions.items as { ticket: number }[])[0]?.ticket ?? 0;
    const api = setup({
      'GET /engines/e1/positions?status=OPEN&limit=200': () => json(positions),
      'GET /engines/e1/intents?kind=paper&status=FILLED&limit=200': () =>
        json({ items: [], next_cursor: null }),
      'GET /engines/e1/intents?kind=paper&status=PENDING&limit=200': () =>
        json({ items: [], next_cursor: null }),
      'POST /engines/e1/commands': () => apiError(409, 'engine_revoked'),
    });
    const user = userEvent.setup();
    renderShell('/positions');
    await user.click(await screen.findByRole('button', { name: 'Close' }));
    const dialog = await screen.findByRole('dialog', { name: new RegExp(`Close #${String(ticket)}`) });
    await user.type(within(dialog).getByRole('textbox', { name: 'Engine control code' }), '111222');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    await user.click(within(dialog).getByRole('button', { name: 'Close position' }));
    expect(await within(dialog).findByRole('alert')).toBeInTheDocument(); // the refusal stays visible
    expect(api.calls.find((c) => c.path === '/engines/e1/commands')?.body).toEqual({
      type: 'POSITION_CLOSE',
      ticket,
      code: '111222',
    });
  });

  it('is in Thai by default', async () => {
    setup();
    renderShell('/risk', 'th');
    const kill = await screen.findByRole('region', { name: 'Kill switch' });
    expect(await within(kill).findByRole('button', { name: 'ปิดทุกโพซิชัน' })).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'ประวัติคำสั่ง' })).toBeInTheDocument();
  });
});
