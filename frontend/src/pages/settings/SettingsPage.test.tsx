import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const SESSIONS = samples['auth/sessions'];
const CONFIG = samples['engines/ENGINE/config'];
const CURRENT = SESSIONS.items[0];
const PHONE = {
  ...CURRENT,
  session_id: 'phone-session',
  current: false,
  ip: '10.0.0.7',
  user_agent:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
};
const UNTIL = new Date(Date.now() + 300_000).toISOString().replace('Z', '+00:00');
const QR = 'data:image/svg+xml;base64,PHN2Zy8+';

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /auth/sessions': () => json({ items: [CURRENT, PHONE] }),
    'GET /engines/e1/config': () => json(CONFIG),
    'POST /auth/step-up': () => json({ step_up_until: UNTIL }),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });
const posts = (api: ReturnType<typeof setup>) =>
  api.calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.path, c.body]);

describe('settings page', () => {
  it('saves the notification language and time zone on the profile', async () => {
    const api = setup({
      'PUT /auth/profile': (req) => json(req.body),
    });
    const user = userEvent.setup();
    renderShell('/settings');
    const profile = await card('Language and time zone');
    await user.selectOptions(within(profile).getByRole('combobox', { name: 'Time zone' }), 'UTC');
    await waitFor(() => {
      expect(posts(api)).toContainEqual(['PUT', '/auth/profile', { locale: 'th', timezone: 'UTC' }]);
    });
  });

  it('changes the password after a step-up', async () => {
    const api = setup({ 'POST /auth/password': () => json({ other_sessions_revoked: 1 }) });
    const user = userEvent.setup();
    renderShell('/settings');
    const security = await card('Security');
    await user.click(within(security).getByRole('button', { name: 'Change password' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Current password'), 'old secret');
    await user.type(within(dialog).getByLabelText('New password'), 'new secret 1');
    await user.type(within(dialog).getByLabelText('New password again'), 'new secret 2');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    await user.click(within(dialog).getByRole('button', { name: 'Change password' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('The new passwords do not match.');
    expect(posts(api)).toEqual([]); // checked before any request
    await user.clear(within(dialog).getByLabelText('New password again'));
    await user.type(within(dialog).getByLabelText('New password again'), 'new secret 1');
    await user.click(within(dialog).getByRole('button', { name: 'Change password' }));
    expect(await within(security).findByRole('status')).toHaveTextContent(
      'Password changed; signed out on 1 other device(s).',
    );
    expect(posts(api)).toEqual([
      ['POST', '/auth/step-up', { code: '123456' }],
      ['POST', '/auth/password', { current_password: 'old secret', new_password: 'new secret 1' }],
    ]);
  });

  it('says when the current password is wrong', async () => {
    setup({ 'POST /auth/password': () => apiError(400, 'invalid_password') });
    const user = userEvent.setup();
    renderShell('/settings');
    await user.click(within(await card('Security')).getByRole('button', { name: 'Change password' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Current password'), 'not it');
    await user.type(within(dialog).getByLabelText('New password'), 'new secret 1');
    await user.type(within(dialog).getByLabelText('New password again'), 'new secret 1');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    await user.click(within(dialog).getByRole('button', { name: 'Change password' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'The current password is not correct.',
    );
  });

  it('enrols a new authenticator: password and step-up, then a code from the new app', async () => {
    const api = setup({
      'POST /auth/totp/enroll': () =>
        json({ secret: 'JBSWY3DPEHPK3PXP', otpauth_uri: 'otpauth://totp/x', qr_svg: QR }),
      'POST /auth/totp/confirm': () => json(null, 204),
    });
    const user = userEvent.setup();
    renderShell('/settings');
    const security = await card('Security');
    await user.click(within(security).getByRole('button', { name: 'Set up a new authenticator' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Current password'), 'old secret');
    await user.type(within(dialog).getByRole('textbox', { name: 'Authenticator code' }), '123456');
    await user.click(within(dialog).getByRole('button', { name: 'Continue' }));
    const qr = await within(security).findByRole('img', { name: 'QR code for the authenticator app' });
    expect(qr).toHaveAttribute('src', QR);
    expect(within(security).getByText('JBSWY3DPEHPK3PXP')).toBeInTheDocument();
    await user.type(within(security).getByLabelText('Code from the new app'), '654321');
    await user.click(within(security).getByRole('button', { name: 'Confirm' }));
    expect(await within(security).findByRole('status')).toHaveTextContent('The new authenticator is active');
    expect(posts(api).slice(-1)).toEqual([['POST', '/auth/totp/confirm', { code: '654321' }]]);
  });

  it('lists signed-in devices and signs out the others', async () => {
    const api = setup({
      'POST /auth/sessions/phone-session/revoke': () => json(null, 204),
      'POST /auth/sessions/revoke-others': () => json({ revoked: 1 }),
    });
    const user = userEvent.setup();
    renderShell('/settings');
    const sessions = await card('Signed-in devices');
    expect(await within(sessions).findByText('Safari · iOS')).toBeInTheDocument();
    expect(within(sessions).getByText('this device')).toBeInTheDocument();
    expect(within(sessions).getByText(/IP 10\.0\.0\.7/)).toBeInTheDocument();
    expect(within(sessions).getAllByRole('button', { name: 'Sign out' })).toHaveLength(1); // not this one
    await user.click(within(sessions).getByRole('button', { name: 'Sign out' }));
    await user.click(within(sessions).getByRole('button', { name: 'Sign out all other devices' }));
    await waitFor(() => {
      expect(posts(api)).toEqual([
        ['POST', '/auth/sessions/phone-session/revoke', undefined],
        ['POST', '/auth/sessions/revoke-others', {}],
      ]);
    });
  });

  it('shows the effective configuration with secrets masked, and the attributions', async () => {
    setup();
    const user = userEvent.setup();
    renderShell('/settings');
    const config = await card('Effective configuration (read-only)');
    await user.click(await within(config).findByText('Environment (secrets masked)'));
    expect(within(config).getByText(/"MT5_PASSWORD": "\*\*\*"/)).toBeInTheDocument();
    expect(within(config).getByText(/"MT5_LOGIN": "\*\*\*\*\*678"/)).toBeInTheDocument();
    expect(within(config).getByText('risk')).toBeInTheDocument();
    const about = await card('About');
    expect(within(about).getByRole('link', { name: 'TradingView Lightweight Charts™' })).toBeInTheDocument();
    expect(within(about).getByText(/No profit is promised/)).toBeInTheDocument();
  });
});
