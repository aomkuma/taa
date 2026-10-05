import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, json, makeSession, mockApi } from '@/test/api';
import { engine, heartbeat, iso, owner, renderShell, status } from '@/test/engine';
import { fakeEventSources, streamEvent } from '@/test/eventSource';
import { renderApp } from '@/test/render';

const statusCalls = (calls: { path: string }[], engineId = 'e1') =>
  calls.filter((c) => c.path === `/engines/${engineId}/status`).length;

// Rendered on a page without engine widgets, so the shell's texts appear once.
describe('app shell', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('shows the mode banner, engine health and both navigations for the owner', async () => {
    owner();
    renderShell('/engines');
    expect(await screen.findByText(/PAPER mode: simulated orders only/)).toBeInTheDocument();
    expect(await screen.findByText('Engine online')).toBeInTheDocument();
    expect(screen.getByText('e1 pc')).toBeInTheDocument();
    const main = screen.getByRole('navigation', { name: 'Main menu' });
    expect(within(main).getByRole('link', { name: 'Positions' })).toHaveAttribute('href', '/positions');
    expect(within(main).getByRole('link', { name: 'Engines' })).toHaveAttribute('aria-current', 'page');
    const quick = screen.getByRole('navigation', { name: 'Quick menu' });
    expect(within(quick).getAllByRole('link')).toHaveLength(4);
  });

  it('opens the live stream of the own engine and goes live', async () => {
    const api = owner();
    const { sources } = renderShell('/engines');
    await screen.findByText('Engine online');
    expect(sources.last().url).toBe('/api/v1/engines/e1/stream');
    expect(screen.getByText('Connecting live updates…')).toBeInTheDocument();
    const before = statusCalls(api.calls);
    act(() => {
      sources.last().emit('ready', { cursor: 3, resumed: false });
    });
    expect(await screen.findByText('Live updates')).toBeInTheDocument();
    // A fresh start may have missed changes: the engine's queries are fetched again.
    await waitFor(() => {
      expect(statusCalls(api.calls)).toBeGreaterThan(before);
    });
  });

  it('applies heartbeats from the stream to the banner and the health', async () => {
    owner();
    const { sources } = renderShell('/engines');
    await screen.findByText('Engine online');
    act(() => {
      sources.last().emit('ready', { cursor: 3, resumed: true });
      sources
        .last()
        .emit('status', streamEvent(4, 'heartbeat', heartbeat({ mode: 'DEMO', connected: false })));
    });
    expect(await screen.findByText(/DEMO mode: orders go to a demo account/)).toBeInTheDocument();
    expect(screen.getByText('Engine running but not connected to MT5')).toBeInTheDocument();
  });

  it('refetches the status on other status changes', async () => {
    const api = owner();
    const { sources } = renderShell('/engines');
    await screen.findByText('Engine online');
    const before = statusCalls(api.calls);
    act(() => {
      sources.last().emit('ready', { cursor: 3, resumed: true });
      sources.last().emit('status', streamEvent(4, 'kill_switch_event', { action: 'ACTIVATE' }));
    });
    await waitFor(() => {
      expect(statusCalls(api.calls)).toBe(before + 1);
    });
  });

  it('marks an engine without recent heartbeats as offline, and a market that is closed', async () => {
    owner({
      'GET /engines/e1/status': () =>
        json(status('e1', { heartbeat: heartbeat({ received_at: iso(Date.now() - 5 * 60_000) }) })),
    });
    renderShell('/engines');
    expect(await screen.findByText(/No heartbeat from the engine since/)).toBeInTheDocument();
  });

  it('says when the market is closed', async () => {
    owner({
      'GET /engines/e1/status': () => json(status('e1', { heartbeat: heartbeat({ market_open: false }) })),
    });
    renderShell('/engines');
    expect(await screen.findByText('Market closed')).toBeInTheDocument();
  });

  it('shows a stale badge while live updates are lost', async () => {
    owner();
    const { sources } = renderShell('/engines');
    await screen.findByText('Engine online');
    act(() => {
      sources.last().emit('ready', { cursor: 3, resumed: true });
    });
    act(() => {
      sources.last().fail(false);
    });
    expect(await screen.findByText('Live updates lost, reconnecting')).toBeInTheDocument();
    expect(screen.getByText(/Not updated since/)).toBeInTheDocument();
  });

  it('shows the kill switch when it is active', async () => {
    owner({
      'GET /engines/e1/status': () => json(status('e1', { kill_switch: { active: true, last: null } })),
    });
    renderShell('/engines');
    expect(await screen.findByRole('alert')).toHaveTextContent('Kill switch active');
  });

  it('shows an unknown mode as it is', async () => {
    owner({
      'GET /engines/e1/status': () => json(status('e1', { heartbeat: heartbeat({ mode: 'TURBO' }) })),
    });
    renderShell('/engines');
    expect(await screen.findByText('Mode TURBO')).toBeInTheDocument();
  });

  it('reads the market feed without a stream or own-engine pages for a subscriber', async () => {
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: 'owner-engine', own: false }),
      'GET /engines': () => json({ items: [] }),
    });
    const { sources } = renderShell('/positions');
    expect(await screen.findByText(/Market data from the owner's engine/)).toBeInTheDocument();
    expect(screen.getByText('This page needs an engine of your own.')).toBeInTheDocument();
    const main = screen.getByRole('navigation', { name: 'Main menu' });
    expect(within(main).queryByRole('link', { name: 'Positions' })).not.toBeInTheDocument();
    expect(within(main).getByRole('link', { name: 'Opportunities' })).toBeInTheDocument();
    expect(sources.created).toHaveLength(0);
  });

  it('asks a user without an engine to link one', async () => {
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => json({ engine_id: null, own: false }),
      'GET /engines': () => json({ items: [] }),
    });
    renderShell('/engines');
    expect(await screen.findByText('No engine linked yet.')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Link an engine' })[0]).toHaveAttribute('href', '/engines');
  });

  it('fails closed when the feed cannot be read', async () => {
    mockApi({
      'GET /auth/session': () => json(makeSession()),
      'GET /me/feed': () => apiError(500, 'internal'),
    });
    renderShell('/positions');
    expect(await screen.findByText('Cannot read engine data right now.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Positions' })).not.toBeInTheDocument();
  });

  it('lets a user with several engines pick one and remembers it', async () => {
    const api = owner({
      'GET /engines': () => json({ items: [engine('e1'), engine('e2'), engine('e3', 'REVOKED')] }),
      'GET /engines/e2/status': () => json(status('e2', { heartbeat: heartbeat({ mode: 'DEMO' }) })),
    });
    const { sources } = renderShell('/engines');
    const picker = await screen.findByRole('combobox', { name: 'Engine' });
    expect(
      within(picker)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['e1 pc', 'e2 pc']);
    await userEvent.selectOptions(picker, 'e2');
    expect(await screen.findByText(/DEMO mode/)).toBeInTheDocument();
    expect(statusCalls(api.calls, 'e2')).toBe(1);
    expect(sources.created[0]?.closed).toBe(true);
    expect(sources.last().url).toBe('/api/v1/engines/e2/stream');
    expect(window.localStorage.getItem('taa.engine')).toBe('e2');
  });

  it('shows an offline banner while the device is offline', async () => {
    owner();
    const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    renderShell('/engines');
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(await screen.findByText(/You are offline/)).toBeInTheDocument();
    online.mockReturnValue(true);
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    await waitFor(() => {
      expect(screen.queryByText(/You are offline/)).not.toBeInTheDocument();
    });
    online.mockRestore();
  });

  it('opens every page from the More sheet on phones and closes it on navigation or Escape', async () => {
    owner();
    const user = userEvent.setup();
    const { router } = renderShell('/engines');
    await screen.findByText('Engine online');
    await user.click(screen.getByRole('button', { name: 'More' }));
    const sheet = screen.getByRole('dialog', { name: 'All pages' });
    await user.click(within(sheet).getByRole('link', { name: 'Backtests' }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/backtests'); // a lazily loaded page
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Backtests' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'More' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('switches to the dark theme', async () => {
    owner();
    const user = userEvent.setup();
    renderShell('/engines');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Theme' }), 'dark');
    expect(document.documentElement).toHaveClass('dark');
    expect(window.localStorage.getItem('taa.theme')).toBe('dark');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Theme' }), 'light');
    expect(document.documentElement).not.toHaveClass('dark');
  });

  it('is in Thai by default', async () => {
    owner();
    const sources = fakeEventSources();
    renderApp('/engines', 'th', { createEventSource: sources.factory });
    expect(await screen.findByText(/โหมด PAPER/)).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'เมนูหลัก' })).toBeInTheDocument();
  });
});
