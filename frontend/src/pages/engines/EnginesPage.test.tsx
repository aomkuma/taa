import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json, makeSession } from '@/test/api';
import { engine, iso, owner, renderShell } from '@/test/engine';

import { totp } from './totp';

const SECRET = 'hmac-secret-shown-once-0123456789abcdef';
const NEW_ID = 'eng_newengineid0000000000000';
const steppedUp = () => json({ ...makeSession(), step_up_until: iso(Date.now() + 300_000) });

function setup(extra: Record<string, Handler> = {}) {
  let created = false;
  let contacted = false;
  const listed = () => [
    {
      ...engine('e1'),
      created_at: iso(Date.now() - 10.5 * 86_400_000),
      first_seen_at: iso(Date.now() - 9 * 86_400_000),
      last_seen_at: iso(Date.now() - 30_000),
      rotated_at: null,
    },
    ...(created
      ? [
          {
            ...engine(NEW_ID),
            label: 'vps',
            created_at: iso(Date.now()),
            first_seen_at: contacted ? iso(Date.now()) : null,
            last_seen_at: contacted ? iso(Date.now()) : null,
          },
        ]
      : []),
  ];
  const api = owner({
    'GET /auth/session': steppedUp,
    'GET /engines': () => json({ items: listed() }),
    'POST /engines': () => {
      created = true;
      return json({ engine_id: NEW_ID, secret: SECRET, cloud_base_url: 'https://taa.example' }, 201);
    },
    ...extra,
  });
  return {
    api,
    contact: () => {
      contacted = true;
    },
  };
}

const card = (name: string | RegExp) => screen.findByRole('region', { name });
vi.setConfig({ testTimeout: 20_000 });

describe('engines page', () => {
  it('lists the engines with status and key age', async () => {
    setup();
    renderShell('/engines');
    const list = await card('Your engines');
    expect(await within(list).findByText('Connected')).toBeInTheDocument();
    expect(within(list).getByText(/Last seen/)).toHaveTextContent('key 10 days old');
  });

  it('adds an engine: keys once, a browser-made control code, the .env block, then first contact', async () => {
    const { api, contact } = setup();
    const user = userEvent.setup();
    const { queryClient } = renderShell('/engines');
    const add = await card('Connect an engine');
    expect(within(add).getByText(/PAPER or DEMO only/)).toBeInTheDocument();
    await user.type(within(add).getByLabelText('Name'), ' vps ');
    await user.click(within(add).getByRole('button', { name: 'Create keys' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create engine keys' });
    await user.click(within(dialog).getByRole('button', { name: 'Create keys' }));

    const wizard = await card('Set up vps');
    expect(api.calls.find((c) => c.method === 'POST')?.body).toEqual({ label: 'vps' });
    expect(within(wizard).getAllByText(SECRET)[0]).toBeInTheDocument();
    expect(within(wizard).getByText(/shown only this once/)).toBeInTheDocument();
    const env = () => within(wizard).getByText(/ENGINE_HMAC_SECRET=/);
    expect(env()).toHaveTextContent(
      `CLOUD_BASE_URL=https://taa.example ENGINE_ID=${NEW_ID} ENGINE_HMAC_SECRET=${SECRET}`,
    );
    expect(env()).not.toHaveTextContent('CONTROL_TOTP_SECRET');

    // the control code: made here, checked here
    expect(
      within(wizard).getByRole('img', { name: "QR code for the engine's control code" }),
    ).toBeInTheDocument();
    const controlSecret = within(wizard).getByText(/^[A-Z2-7]{32}$/).textContent;
    const right = await totp(controlSecret, Date.now() / 1000);
    const wrong = String((Number(right) + 1) % 1_000_000).padStart(6, '0');
    await user.type(within(wizard).getByLabelText('Code from the app'), wrong);
    await user.click(within(wizard).getByRole('button', { name: 'Check' }));
    expect(await within(wizard).findByText(/That code does not match/)).toBeInTheDocument();
    await user.clear(within(wizard).getByLabelText('Code from the app'));
    await user.type(within(wizard).getByLabelText('Code from the app'), right);
    await user.click(within(wizard).getByRole('button', { name: 'Check' }));
    expect(await within(wizard).findByText('The code matches.')).toBeInTheDocument();
    expect(env()).toHaveTextContent(`CONTROL_TOTP_SECRET=${controlSecret}`);
    // nothing about the control code went to the server, and no secret sits in the query cache
    expect(JSON.stringify(api.calls)).not.toContain(controlSecret);
    const cached = JSON.stringify(
      queryClient
        .getQueryCache()
        .getAll()
        .map((q) => q.state.data),
    );
    expect(cached).not.toContain(SECRET);
    expect(cached).not.toContain(controlSecret);

    expect(within(wizard).getByText(/investor \(read-only\) password/)).toBeInTheDocument();
    expect(within(wizard).getByText(/Waiting for first contact/)).toBeInTheDocument();
    contact();
    await waitFor(
      () => {
        expect(within(wizard).getByText(/Connected: the engine has reached this app/)).toBeInTheDocument();
      },
      { timeout: 8_000 },
    );
    await user.click(within(wizard).getByRole('button', { name: 'Done' }));
    expect(screen.queryByText(SECRET)).not.toBeInTheDocument();
  });

  it('rotates the key and revokes with a typed confirmation', async () => {
    const { api } = setup({
      'POST /engines/e1/rotate': () => json({ engine_id: 'e1', secret: 'rotated-secret-0123456789' }),
      'POST /engines/e1/revoke': () => json(null, 204),
    });
    const user = userEvent.setup();
    renderShell('/engines');
    const list = await card('Your engines');
    await user.click(await within(list).findByRole('button', { name: 'New key' }));
    await user.click(
      within(await screen.findByRole('dialog', { name: 'Make a new engine key' })).getByRole('button', {
        name: 'Make new key',
      }),
    );
    const rotated = await card('New key for e1 pc');
    expect(within(rotated).getByText(/ENGINE_HMAC_SECRET=rotated-secret-0123456789/)).toBeInTheDocument();

    await user.click(within(list).getByRole('button', { name: 'Revoke' }));
    const dialog = await screen.findByRole('dialog', { name: 'Revoke this engine?' });
    await user.type(within(dialog).getByLabelText(/Type the engine ID to confirm/), 'e2');
    await user.click(within(dialog).getByRole('button', { name: 'Revoke' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Type the engine ID exactly.');
    await user.clear(within(dialog).getByLabelText(/Type the engine ID to confirm/));
    await user.type(within(dialog).getByLabelText(/Type the engine ID to confirm/), 'e1');
    await user.click(within(dialog).getByRole('button', { name: 'Revoke' }));
    await waitFor(() => {
      expect(api.calls.find((c) => c.path === '/engines/e1/revoke')?.body).toEqual({ confirm: 'e1' });
    });
  });

  it('explains a refused registration', async () => {
    setup({ 'POST /engines': () => apiError(409, 'engine_limit_reached') });
    const user = userEvent.setup();
    renderShell('/engines');
    const add = await card('Connect an engine');
    await user.type(within(add).getByLabelText('Name'), 'second');
    await user.click(within(add).getByRole('button', { name: 'Create keys' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create engine keys' });
    await user.click(within(dialog).getByRole('button', { name: 'Create keys' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'You have reached the number of engines you can connect.',
    );
  });

  it('renders in Thai', async () => {
    setup();
    renderShell('/engines', 'th');
    expect(await card('เอนจินของคุณ')).toBeInTheDocument();
  });
});
