import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { updateReady } from '@/app/swUpdate';
import { UpdateBanner } from '@/app/UpdateBanner';
import { renderWithI18n } from '@/test/render';

function show() {
  return renderWithI18n(<UpdateBanner />, 'en');
}

describe('update banner', () => {
  it('stays hidden until a new version is waiting', () => {
    show();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('activates the waiting version on reload', async () => {
    const activate = vi.fn(() => Promise.resolve());
    show();
    act(() => {
      updateReady(activate);
    });
    expect(screen.getByRole('status')).toHaveTextContent('A new version of TAA is available.');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reload' }));
    expect(activate).toHaveBeenCalledOnce();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('can be put off until the next update', async () => {
    const activate = vi.fn(() => Promise.resolve());
    show();
    act(() => {
      updateReady(activate);
    });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Later' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(activate).not.toHaveBeenCalled();
  });
});
