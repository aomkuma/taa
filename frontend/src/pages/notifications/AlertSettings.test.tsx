import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Preferences } from '@/pages/watchlists/schemas';
import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

// The real `GET /advisory/preferences` of tests/web/test_api_samples.py (the defaults).
const PREFS = (samples as Record<string, unknown>)['advisory/preferences'] as Preferences;

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /notifications?limit=20': () => json({ items: [], next_cursor: null }),
    'GET /notifications/preferences': () => json(samples['notifications/preferences']),
    'GET /push/subscriptions': () => json({ items: [] }),
    'GET /advisory/preferences': () => json(PREFS),
    'PUT /advisory/preferences': (request) => json(request.body),
    ...extra,
  });
}

const settings = () => screen.findByRole('region', { name: 'Opportunity alert settings' });

describe('alert settings', () => {
  it('shows the defaults', async () => {
    setup();
    renderShell('/notifications');
    const card = await settings();
    expect(await within(card).findByLabelText('Win probability')).toBeChecked();
    expect(within(card).getByLabelText('Alert at or above')).toHaveValue('55');
    expect(within(card).getByText('default')).toBeInTheDocument();
    expect(within(card).getByText(/Never below break-even plus 2 points/)).toBeInTheDocument();
    expect(within(card).getByLabelText('Signal stays valid for (entry bars)')).toHaveValue(2);
    expect(within(card).getByLabelText("Only while the symbol's market session is open")).toBeChecked();
    expect(within(card).getByText('Any time (no windows set).')).toBeInTheDocument();
    expect(within(card).getByLabelText('At most alerts per hour')).toHaveValue(6);
    expect(within(card).getByLabelText('Do not push; show it in the app with the reason')).toBeChecked();
    expect(within(card).getByLabelText('Alert language')).toHaveValue('th');
    expect(within(card).getByRole('button', { name: 'Save alert settings' })).toBeDisabled();
  });

  it('saves the metric, x, a time window, rate limits and delivery choices with the rest of the document', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/notifications');
    const card = await settings();
    await user.click(await within(card).findByLabelText('Setup strength'));
    const x = within(card).getByLabelText('Alert at or above');
    expect(x).toHaveValue('75'); // the setup-strength default
    fireEvent.change(x, { target: { value: '80' } });
    expect(within(card).getByRole('button', { name: 'Back to the default (75%)' })).toBeInTheDocument();

    await user.click(within(card).getByRole('button', { name: 'Add a time window' }));
    const window = within(card).getByRole('listitem', { name: 'Window 1' });
    await user.click(within(window).getByLabelText('Sat'));
    await user.click(within(window).getByLabelText('Sun'));
    fireEvent.change(within(window).getByLabelText('From'), { target: { value: '22:00' } });
    fireEvent.change(within(window).getByLabelText('to'), { target: { value: '02:00' } });

    const perHour = within(card).getByLabelText('At most alerts per hour');
    await user.clear(perHour);
    await user.type(perHour, '61');
    expect(within(card).getByText('Alerts per hour: 1 to 60.')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Save alert settings' })).toBeDisabled();
    await user.clear(perHour);
    await user.type(perHour, '3');

    await user.click(within(card).getByLabelText('Push anyway, with a warning'));
    await user.selectOptions(within(card).getByLabelText('Alert language'), 'en');
    await user.click(within(card).getByRole('button', { name: 'Save alert settings' }));
    expect(await within(card).findByRole('status')).toHaveTextContent('Saved.');

    const put = api.calls.find((c) => c.method === 'PUT' && c.path === '/advisory/preferences');
    expect(put?.body).toEqual({
      ...PREFS,
      alerts: {
        ...PREFS.alerts,
        metric: 'SETUP_STRENGTH',
        threshold: 80,
        windows: [{ days: [0, 1, 2, 3, 4], start: '22:00', end: '02:00' }],
        rate_limits: { max_alerts_per_hour: 3, symbol_cooldown_minutes: 30 },
        when_risk_full: 'WARN',
        language: 'en',
      },
    });
    expect(within(card).getByRole('button', { name: 'Save alert settings' })).toBeDisabled();
  });

  it('blocks a window without days and shows a rejected save', async () => {
    setup({ 'PUT /advisory/preferences': () => apiError(400, 'invalid_preferences') });
    const user = userEvent.setup();
    renderShell('/notifications');
    const card = await settings();
    await user.click(await within(card).findByRole('button', { name: 'Add a time window' }));
    const window = within(card).getByRole('listitem', { name: 'Window 1' });
    for (const day of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']) {
      await user.click(within(window).getByLabelText(day));
    }
    expect(within(window).getByText('Pick at least one day.')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Save alert settings' })).toBeDisabled();
    await user.click(within(window).getByRole('button', { name: 'Remove' }));
    await user.click(
      within(card).getByLabelText('Update the alert when its suitable time passes or it is invalidated'),
    );
    await user.click(within(card).getByRole('button', { name: 'Save alert settings' }));
    expect(await within(card).findByRole('alert')).toHaveTextContent(
      'The server rejected the settings: invalid_preferences',
    );
    await user.click(within(card).getByRole('button', { name: 'Undo changes' }));
    await waitFor(() => {
      expect(within(card).queryByRole('alert')).not.toBeInTheDocument();
    });
  });
});
