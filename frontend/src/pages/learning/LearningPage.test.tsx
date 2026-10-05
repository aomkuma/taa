import { screen, within } from '@testing-library/react';

import { json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const recorded = samples as Record<string, unknown>;

describe('Learning page', () => {
  it('shows why trades lost, the expectancy levers and manual-trade patterns, labelled hypothetical', async () => {
    owner({
      'GET /engines/e1/learning/timing?scope=SHADOW&days=90': () =>
        json(recorded['engines/ENGINE/learning/timing?scope=SHADOW&days=366']),
      'GET /engines/e1/learning/expectancy?scope=SHADOW&days=90': () =>
        json(recorded['engines/ENGINE/learning/expectancy?scope=SHADOW&days=183']),
      'GET /engines/e1/learning/behavior?days=90': () =>
        json(recorded['engines/ENGINE/learning/behavior?days=366']),
    });
    renderShell('/learning');
    const timing = await screen.findByRole('region', { name: 'Why losing trades lost' });
    expect(await within(timing).findByText(/Not yet: price went nowhere/)).toBeInTheDocument();
    expect(timing).toHaveTextContent('random walk');
    const expectancy = await screen.findByRole('region', { name: 'Expected result per trade' });
    expect(expectancy).toHaveTextContent('Win share (before costs)');
    expect(expectancy).toHaveTextContent('Trend pullback (example) · EURUSD');
    expect(expectancy).toHaveTextContent('Average loss0.81R');
    const behavior = await screen.findByRole('region', { name: 'Your manual trades' });
    expect(behavior).toHaveTextContent('Traded without a matching signal');
    expect(behavior).toHaveTextContent('not a grade');
    expect(screen.getByText(/past results do not predict future results/)).toBeInTheDocument();
  });
});
