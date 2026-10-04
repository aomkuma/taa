import { screen } from '@testing-library/react';

import { apiError, json, makeSession, mockApi } from '@/test/api';
import { renderApp } from '@/test/render';

describe('routes', () => {
  it('renders the home page at / for a signed-in user', async () => {
    mockApi({ 'GET /auth/session': () => json(makeSession()) });
    renderApp('/');
    expect(await screen.findByRole('heading', { level: 1, name: 'TAA' })).toBeInTheDocument();
  });

  it('renders the not-found page for unknown paths, in Thai by default', async () => {
    mockApi({ 'GET /auth/session': () => apiError(401, 'unauthenticated') });
    renderApp('/does-not-exist');
    expect(await screen.findByRole('heading', { name: 'ไม่พบหน้านี้' })).toBeInTheDocument();
  });

  it('renders English when the language is en', async () => {
    mockApi({ 'GET /auth/session': () => apiError(401, 'unauthenticated') });
    renderApp('/does-not-exist', 'en');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('shows the language switcher in the header', async () => {
    mockApi({ 'GET /auth/session': () => apiError(401, 'unauthenticated') });
    renderApp('/login');
    expect(await screen.findByRole('group', { name: 'ภาษา' })).toBeInTheDocument();
  });
});
