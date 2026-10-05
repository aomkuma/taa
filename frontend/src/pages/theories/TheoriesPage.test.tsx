import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';
import type { Preferences } from '@/pages/watchlists/schemas';

// Real responses recorded by tests/web/test_api_samples.py (engine id "ENGINE"), served for engine e1.
const recorded = samples as Record<string, unknown>;
const PREFS = recorded['advisory/preferences'] as Preferences;

function setup(extra: Record<string, Handler> = {}, entitlements: Record<string, unknown> = {}) {
  return owner({
    'GET /advisory/preferences': () => json(PREFS),
    'GET /advisory/detectors': () => json(recorded['advisory/detectors']),
    'GET /me/entitlements': () => json({ ...(recorded['me/entitlements'] as object), ...entitlements }),
    'GET /engines/e1/theory-scoreboard': () => json(recorded['engines/ENGINE/theory-scoreboard']),
    'PUT /advisory/preferences/theories': (request) => json({ ...PREFS, theories: request.body }),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

// a large form: typing into it takes a while when the suite runs in parallel
vi.setConfig({ testTimeout: 20_000 });

describe('theories page', () => {
  it('shows every family with its diagram, explanation, record and theories with tiers', async () => {
    setup();
    renderShell('/theories');
    const fib = await card('Fibonacci');
    expect(within(fib).getByRole('img', { name: 'Fibonacci: an example sketch' })).toBeInTheDocument();
    expect(within(fib).getByText(/Ratios of the last swing/)).toBeInTheDocument();
    expect(within(fib).getByLabelText('On')).toBeChecked();
    // the family's hypothetical record from the theory scoreboard
    expect((await within(fib).findAllByText(/Forex majors M15: hit rate 100% of 3/))[0]).toBeInTheDocument();
    await userEvent.setup().click(within(fib).getByText('Theories (5 of 5 on)'));
    const retracement = within(fib).getByLabelText('Fibonacci retracement');
    expect(retracement).toBeChecked();
    expect(within(fib).getAllByText('T1')[0]).toHaveAttribute(
      'title',
      'T1: objective, an exact formula or rule',
    );
    expect(await card('Elliott waves')).toHaveTextContent('T3');
  });

  it('switches families and theories, picks a preset and saves the selection', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/theories');
    const harmonic = await card('Harmonics');
    await user.click(within(harmonic).getByLabelText('On'));
    const fib = await card('Fibonacci');
    await user.click(within(fib).getByText('Theories (5 of 5 on)'));
    await user.click(within(fib).getByLabelText('Fibonacci cluster'));
    expect(within(fib).getByText('Theories (4 of 5 on)')).toBeInTheDocument();
    const presets = await card('Presets');
    expect(within(presets).getByText('customized')).toBeInTheDocument();

    const rules = await card('Conditions');
    const n = within(rules).getByLabelText('Alert only when at least this many families support the trade');
    await user.clear(n);
    await user.type(n, '3');
    await user.click(within(rules).getByLabelText('Do not alert on a strong conflict'));
    const setups = await card('Pattern setups that may alert');
    await user.click(within(setups).getAllByRole('checkbox')[0] as HTMLElement);

    await user.click(screen.getByRole('button', { name: 'Save theories' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Saved. Applies from the next closed bar.');
    const body = api.calls.find((c) => c.method === 'PUT')?.body as Record<string, unknown>;
    expect(body).toMatchObject({
      preset: 'ALL',
      families: { HARMONIC: false },
      detectors: { 'fib.cluster': false },
      min_supporting_families: 3,
      conflict_policy: 'BLOCK',
      pattern_strategies: { setup_breakout: false },
    });

    await user.click(within(presets).getByRole('button', { name: 'Trend following' }));
    expect(within(await card('Fibonacci')).getByLabelText('On')).not.toBeChecked();
    expect(within(presets).queryByText('customized')).not.toBeInTheDocument();
  });

  it('edits bounded parameters within their range and resets them', async () => {
    const api = setup();
    const user = userEvent.setup();
    renderShell('/theories');
    const fib = await card('Fibonacci');
    await user.click(within(fib).getByText('Theories (5 of 5 on)'));
    await user.click(within(fib).getAllByText('Advanced parameters')[0] as HTMLElement);
    const tol = within(fib).getAllByLabelText('Tolerance (× ATR)')[0] as HTMLElement;
    expect(tol).toHaveValue(0.25);
    await user.clear(tol);
    await user.type(tol, '3');
    expect(tol).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Some parameters are outside their allowed range.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save theories' })).toBeDisabled();
    await user.clear(tol);
    await user.type(tol, '0.5');
    await user.click(screen.getByRole('button', { name: 'Save theories' }));
    await waitFor(() => {
      expect((api.calls.find((c) => c.method === 'PUT')?.body as { params: unknown }).params).toEqual({
        'fib.retracement': { tol_atr: 0.5 },
      });
    });
    await user.click(within(fib).getAllByRole('button', { name: 'Back to the defaults' })[0] as HTMLElement);
    expect(tol).toHaveValue(0.25);
  });

  it('locks the families the plan leaves out and hides parameters on the market feed', async () => {
    owner({
      'GET /me/feed': () => json({ engine_id: 'feed', own: false }),
      'GET /advisory/preferences': () => json(PREFS),
      'GET /advisory/detectors': () => json(recorded['advisory/detectors']),
      'GET /me/entitlements': () =>
        json({ ...(recorded['me/entitlements'] as object), plan: 'FREE', families: ['TREND', 'FIBONACCI'] }),
      'GET /engines/feed/theory-scoreboard': () => json({ hypothetical: true, items: [] }),
    });
    const user = userEvent.setup();
    renderShell('/theories');
    const harmonic = await card('Harmonics');
    expect(await within(harmonic).findByText(/Not in your plan/)).toBeInTheDocument();
    expect(within(harmonic).queryByLabelText('On')).not.toBeInTheDocument();
    const fib = await card('Fibonacci');
    await user.click(within(fib).getByText('Theories (5 of 5 on)'));
    expect(within(fib).queryByText('Advanced parameters')).not.toBeInTheDocument();
    expect(screen.getByText(/set by the engine's owner/)).toBeInTheDocument();
  });

  it('shows a rejected save', async () => {
    setup({ 'PUT /advisory/preferences/theories': () => apiError(400, 'invalid_preferences') });
    const user = userEvent.setup();
    renderShell('/theories');
    await user.click(within(await card('Harmonics')).getByLabelText('On'));
    await user.click(screen.getByRole('button', { name: 'Save theories' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The server rejected the selection');
  });

  it('renders in Thai', async () => {
    setup();
    renderShell('/theories', 'th');
    expect(await screen.findByRole('heading', { name: 'ทฤษฎีและเงื่อนไข' })).toBeInTheDocument();
    expect(await card('ชุดตั้งค่าสำเร็จรูป')).toBeInTheDocument();
  });
});
