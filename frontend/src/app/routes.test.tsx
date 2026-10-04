import { screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';

import { routes } from '@/app/routes';
import type { Language } from '@/i18n/languages';
import { renderWithI18n } from '@/test/render';

function renderAt(path: string, language: Language = 'th') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return renderWithI18n(<RouterProvider router={router} />, language);
}

describe('routes', () => {
  it('renders the home page at /', () => {
    renderAt('/');
    expect(screen.getByRole('heading', { level: 1, name: 'TAA' })).toBeInTheDocument();
  });

  it('renders the not-found page for unknown paths, in Thai by default', () => {
    renderAt('/does-not-exist');
    expect(screen.getByRole('heading', { name: 'ไม่พบหน้านี้' })).toBeInTheDocument();
  });

  it('renders English when the language is en', () => {
    renderAt('/does-not-exist', 'en');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('shows the language switcher in the header', () => {
    renderAt('/');
    expect(screen.getByRole('group', { name: 'ภาษา' })).toBeInTheDocument();
  });
});
