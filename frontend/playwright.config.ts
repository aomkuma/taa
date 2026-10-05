/**
 * Playwright smoke tests (TAA-914): the built PWA served by `vite preview`, driven in the installed Google
 * Chrome (no browser download). The API is answered from the recorded samples (e2e/api.ts). Run with
 * `npm run build && npm run e2e`; not part of `npm run test`.
 */
import { defineConfig } from '@playwright/test';

const PORT = 4173;

export default defineConfig({
  testDir: 'e2e',
  timeout: 30_000,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    channel: 'chrome',
    serviceWorkers: 'allow',
  },
  webServer: {
    command: `npx vite preview --host 127.0.0.1 --port ${String(PORT)} --strictPort`,
    url: `http://127.0.0.1:${String(PORT)}`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
