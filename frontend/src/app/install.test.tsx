import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { owner, renderShell } from '@/test/engine';

import { listenForInstall, resetInstall } from './install';

/** A Chromium-like install offer: prompt() opens the dialog, userChoice says what the user chose. */
function offer(outcome: 'accepted' | 'dismissed') {
  const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: string }>;
  };
  event.prompt = vi.fn(() => Promise.resolve());
  event.userChoice = Promise.resolve({ outcome });
  return event;
}

describe('install prompt', () => {
  beforeAll(() => {
    listenForInstall();
  });
  afterEach(() => {
    resetInstall();
  });

  it('offers to install when the browser does, and shows the dialog on request', async () => {
    owner();
    const user = userEvent.setup();
    renderShell('/settings');
    const card = await screen.findByRole('region', { name: 'Install the app' });
    expect(within(card).getByText(/does not offer installing right now/)).toBeInTheDocument();
    const event = offer('dismissed');
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true); // no mini-infobar
    await user.click(await within(card).findByRole('button', { name: 'Install TAA' }));
    expect(event.prompt).toHaveBeenCalled();
    expect(await within(card).findByText(/install it later/)).toBeInTheDocument();
    window.dispatchEvent(new Event('appinstalled'));
    await waitFor(() => {
      expect(within(card).getByText('TAA is installed on this device.')).toBeInTheDocument();
    });
  });
});
