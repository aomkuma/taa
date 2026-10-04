import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createMemoryRouter, RouterProvider } from 'react-router';

import { routes } from '@/app/routes';
import { createI18n } from '@/i18n';
import type { Language } from '@/i18n/languages';

/** Renders *ui* with an isolated i18n instance in *language*. */
export function renderWithI18n(ui: ReactElement, language: Language = 'th') {
  const i18n = createI18n(language);
  return { i18n, ...render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>) };
}

/** The whole app (routes, query cache, i18n) at *path*, with retries off so failures surface at once. */
export function renderApp(path: string, language: Language = 'th') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const result = renderWithI18n(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
    language,
  );
  return { ...result, router, queryClient };
}
