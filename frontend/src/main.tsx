import '@fontsource-variable/noto-sans-thai/wght.css';
import './index.css';

import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { registerSW } from 'virtual:pwa-register';

import { listenForInstall } from '@/app/install';
import { createQueryClient } from '@/app/queryClient';
import { routes } from '@/app/routes';
import { UPDATE_CHECK_MS, updateReady } from '@/app/swUpdate';
import { applyTheme, loadTheme } from '@/app/theme';
import { initAppI18n } from '@/i18n';

const container = document.getElementById('root');
if (!container) {
  throw new Error('#root element is missing from index.html');
}

listenForInstall();
// Before the first render, so the page does not flash in the wrong theme.
applyTheme(loadTheme());
const i18n = initAppI18n();
const router = createBrowserRouter(routes);
const queryClient = createQueryClient();

// A new version waits until the user agrees (UpdateBanner); open pages look for one every hour.
const updateServiceWorker = registerSW({
  onNeedRefresh: () => {
    updateReady(() => updateServiceWorker(true));
  },
  onRegisteredSW: (_url, registration) => {
    if (!registration) return;
    setInterval(() => {
      void registration.update();
    }, UPDATE_CHECK_MS);
  },
});

createRoot(container).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </I18nextProvider>
  </StrictMode>,
);
