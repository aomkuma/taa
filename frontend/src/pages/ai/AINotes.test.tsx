import { screen, within } from '@testing-library/react';

import { apiError, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';
import { renderWithI18n } from '@/test/render';

import { AIOpinion } from './AINotes';
import { type AINote, AINotesSchema } from './schemas';

const recorded = samples as Record<string, unknown>;
const opinions = AINotesSchema.parse(recorded['engines/ENGINE/ai-notes?kind=OPPORTUNITY&days=366']);

describe('AI notes (TAA-1305)', () => {
  it('shows the opinions’ accuracy and why the alert filter is not offered yet', async () => {
    owner({
      'GET /engines/e1/ai-assessments?days=30': () =>
        json(recorded['engines/ENGINE/ai-assessments?days=366']),
      'GET /engines/e1/ai-notes?kind=OPPORTUNITY&days=90': () => json(opinions),
    });
    renderShell('/ai');
    const card = await screen.findByRole('region', { name: 'AI opinions on opportunities' });
    expect(within(card).getByText(/The AI filter is not offered yet/)).toBeInTheDocument();
    expect(card).toHaveTextContent('Agreed');
    expect(card).toHaveTextContent('simulated trades');
  });

  it('hides the opinions without the plan’s AI feature', async () => {
    owner({
      'GET /engines/e1/ai-assessments?days=30': () =>
        json(recorded['engines/ENGINE/ai-assessments?days=366']),
      'GET /engines/e1/ai-notes?kind=OPPORTUNITY&days=90': () => apiError(403, 'plan_feature'),
    });
    renderShell('/ai');
    expect(await screen.findByRole('region', { name: 'Summary' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'AI opinions on opportunities' })).toBeNull();
  });

  it('labels an opinion as AI opinion, in the UI language', () => {
    const note = opinions.items[0] as AINote;
    renderWithI18n(<AIOpinion note={note} />, 'th');
    expect(screen.getByText('ความเห็นของ AI')).toBeInTheDocument();
    expect(screen.getByText(note.text_th)).toBeInTheDocument();
    expect(screen.getByText(/ความเห็นของ AI ไม่ใช่คำแนะนำ/)).toBeInTheDocument();
  });
});
