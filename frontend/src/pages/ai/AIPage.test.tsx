import { screen, within } from '@testing-library/react';

import { json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const recorded = samples as Record<string, unknown>;

describe('AI review page', () => {
  it('shows agreement, cost and each review without promising anything', async () => {
    owner({
      'GET /engines/e1/ai-assessments?days=30': () =>
        json(recorded['engines/ENGINE/ai-assessments?days=366']),
    });
    renderShell('/ai');
    const summary = await screen.findByRole('region', { name: 'Summary' });
    expect(within(summary).getByText('Agreed').nextSibling).toHaveTextContent('100%');
    expect(summary).toHaveTextContent('claude-opus-5-5');
    expect(summary).toHaveTextContent('not real money');
    const reviews = await screen.findByRole('region', { name: 'Reviews' });
    expect(within(reviews).getByText(/Agrees \(80\)/)).toBeInTheDocument();
    expect(reviews).toHaveTextContent('H1 trend agrees');
    expect(reviews).toHaveTextContent('passed');
  });
});
