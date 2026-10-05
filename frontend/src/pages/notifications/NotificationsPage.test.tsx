import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const LIST = samples['notifications?limit=20'];
const PREFS = samples['notifications/preferences'];
const DEVICES = samples['push/subscriptions'];
const RUN_A = '0191a0a0-0000-7000-8000-0000000000b1';
const ENDPOINT = 'https://fcm.googleapis.com/fcm/send/this-device';

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /notifications?limit=20': () => json(LIST),
    'GET /notifications/preferences': () => json(PREFS),
    'GET /push/subscriptions': () => json(DEVICES),
    'GET /push/key': () => json({ public_key: 'BAEC_w' }),
    ...extra,
  });
}

/** A browser with Web Push: a registered worker whose push manager subscribes on request. */
function pushBrowser(permission: NotificationPermission = 'granted') {
  let subscription: PushSubscription | null = null;
  const sub = {
    endpoint: ENDPOINT,
    toJSON: () => ({ endpoint: ENDPOINT, keys: { p256dh: 'p'.repeat(87), auth: 'a'.repeat(22) } }),
    unsubscribe: () => {
      subscription = null;
      return Promise.resolve(true);
    },
  } as unknown as PushSubscription;
  const pushManager = {
    getSubscription: () => Promise.resolve(subscription),
    subscribe: vi.fn(() => {
      subscription = sub;
      return Promise.resolve(sub);
    }),
  };
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { getRegistration: () => Promise.resolve({ pushManager }) },
  });
  vi.stubGlobal('PushManager', function PushManager() {}); // only its presence is checked
  vi.stubGlobal('Notification', { requestPermission: vi.fn(() => Promise.resolve(permission)) });
  return pushManager;
}

const card = (name: string) => screen.getByRole('region', { name });

describe('notifications page', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, 'serviceWorker');
  });

  it('lists notifications with their texts, links and unread state', async () => {
    setup();
    renderShell('/notifications');
    const centre = await screen.findByRole('region', { name: 'Notification centre' });
    await within(centre).findByText('alice pc: no heartbeat for over a minute while its market is open');
    expect(within(centre).getByText('alice pc is running again')).toBeInTheDocument();
    expect(within(centre).getByText('Backtest (standard): done')).toBeInTheDocument();
    expect(within(centre).getByText(/EURUSD ซื้อ/)).toBeInTheDocument(); // the push text, as it was sent
    expect(within(centre).getByText('Notifications work on this device')).toBeInTheDocument();
    const links = within(centre)
      .getAllByRole('link', { name: 'Open' })
      .map((a) => a.getAttribute('href'));
    expect(links).toContain(`/backtests?run=${RUN_A}`);
    expect(links).toContain('/charts?opportunity=o1');
    // ENGINE_BACK was read already: no "mark as read" for it
    expect(within(centre).getAllByRole('button', { name: 'Mark as read' })).toHaveLength(4);
  });

  it('marks one or all notifications read and filters the unread ones', async () => {
    const api = setup({
      'POST /notifications/0191a0a0-0000-7000-8000-0000000000a4/read': () => json(null, 204),
      'POST /notifications/read-all': () => json({ updated: 3 }),
      'GET /notifications?limit=20&unread=true': () => json({ items: [], next_cursor: null }),
    });
    const user = userEvent.setup();
    renderShell('/notifications');
    const centre = await screen.findByRole('region', { name: 'Notification centre' });
    await within(centre).findByText('Notifications work on this device');
    await user.click(within(centre).getAllByRole('button', { name: 'Mark as read' })[0] as HTMLElement);
    await user.click(within(centre).getByRole('button', { name: 'Mark all read' }));
    await waitFor(() => {
      expect(api.calls.map((c) => `${c.method} ${c.path}`)).toEqual(
        expect.arrayContaining([
          'POST /notifications/0191a0a0-0000-7000-8000-0000000000a4/read',
          'POST /notifications/read-all',
        ]),
      );
    });
    await user.click(within(centre).getByRole('button', { name: 'Unread' }));
    expect(await within(centre).findByText('No unread notifications.')).toBeInTheDocument();
  });

  it('switches push types on and off', async () => {
    const api = setup({
      'PUT /notifications/preferences': (req) =>
        json({ types: PREFS.types, disabled: (req.body as { disabled: string[] }).disabled }),
    });
    const user = userEvent.setup();
    renderShell('/notifications');
    const prefs = await screen.findByRole('region', { name: 'Types to push' });
    const backtest = await within(prefs).findByRole('checkbox', { name: 'Backtest finished' });
    expect(backtest).not.toBeChecked();
    await user.click(within(prefs).getByRole('checkbox', { name: 'Engine offline' }));
    await waitFor(() => {
      expect(within(prefs).getByRole('checkbox', { name: 'Engine offline' })).not.toBeChecked();
    });
    expect(api.calls.find((c) => c.method === 'PUT')?.body).toEqual({
      disabled: ['BACKTEST_FINISHED', 'ENGINE_OFFLINE'],
    });
  });

  it('lists the devices that receive pushes', async () => {
    setup();
    renderShell('/notifications');
    const devices = await screen.findByRole('region', { name: 'Devices receiving notifications' });
    expect(await within(devices).findByText('Edge · Windows')).toBeInTheDocument();
    expect(within(devices).getByText('active')).toBeInTheDocument();
  });

  it('says when the browser cannot receive pushes', async () => {
    setup();
    renderShell('/notifications');
    expect(await screen.findByText('This browser does not support push notifications.')).toBeInTheDocument();
  });

  it('turns push on for this device, sends a test and turns it off again', async () => {
    const manager = pushBrowser();
    const api = setup({
      'POST /push/subscribe': () => json({ subscription_id: 's1' }, 201),
      'POST /push/test': () => json({ notification_id: 'n9' }, 202),
      'POST /push/unsubscribe': () => json(null, 204),
    });
    const user = userEvent.setup();
    renderShell('/notifications');
    const push = await screen.findByRole('region', { name: 'Push on this device' });
    await user.click(await within(push).findByRole('button', { name: 'Turn on notifications' }));
    expect(await within(push).findByText('Notifications are on for this device.')).toBeInTheDocument();
    expect(manager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({
        userVisibleOnly: true,
        applicationServerKey: new Uint8Array([4, 1, 2, 255]),
      }),
    );
    const subscribe = api.calls.find((c) => c.path === '/push/subscribe');
    expect(subscribe?.body).toEqual({
      endpoint: ENDPOINT,
      keys: { p256dh: 'p'.repeat(87), auth: 'a'.repeat(22) },
      label: expect.any(String) as string,
    });
    expect(await within(push).findByText('On for this device')).toBeInTheDocument();

    await user.click(within(push).getByRole('button', { name: 'Send a test notification' }));
    expect(await within(push).findByText(/Test notification sent/)).toBeInTheDocument();

    await user.click(within(push).getByRole('button', { name: 'Turn off notifications' }));
    expect(await within(push).findByText('Notifications are off for this device.')).toBeInTheDocument();
    expect(api.calls.find((c) => c.path === '/push/unsubscribe')?.body).toEqual({ endpoint: ENDPOINT });
  });

  it('explains a blocked permission and a server without push', async () => {
    pushBrowser('denied');
    setup();
    const user = userEvent.setup();
    const { unmount } = renderShell('/notifications');
    const push = await screen.findByRole('region', { name: 'Push on this device' });
    await user.click(await within(push).findByRole('button', { name: 'Turn on notifications' }));
    expect(await within(push).findByRole('alert')).toHaveTextContent(/blocked notifications/);
    unmount();

    setup({ 'GET /push/key': () => apiError(404, 'push_not_configured') });
    renderShell('/notifications');
    expect(
      await screen.findByText('Push notifications are not set up on the server (VAPID).'),
    ).toBeInTheDocument();
  });

  it('shows iPhone users how to add the app to the Home Screen first', async () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1',
    );
    setup();
    renderShell('/notifications');
    expect(await screen.findByText(/Add to Home Screen/)).toBeInTheDocument();
    expect(card('Push on this device')).not.toHaveTextContent('Turn on notifications');
  });
});
