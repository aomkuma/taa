import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { searchForWorkspaceRoot } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { defineConfig } from 'vitest/config';

// Local FastAPI web service (python -m app.cli web ...). Same-origin in production: FastAPI serves dist/.
const API_TARGET = process.env.TAA_API_TARGET ?? 'http://127.0.0.1:8000';
const BACKEND_DIR = fileURLToPath(new URL('../app', import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',
      // Registered from main.tsx (bundled, so the strict CSP holds: no inline scripts, PLAN §A14), which also
      // shows the "new version" banner (src/app/swUpdate.ts).
      injectRegister: false,
      manifest: {
        name: 'TAA',
        short_name: 'TAA',
        description: 'TAA trading assistant',
        lang: 'th',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      // Our own worker (src/sw/sw.ts) for Web Push; it also does the app-shell precache and navigation
      // fallback the generated worker did (`/api/` is never answered with index.html).
      strategies: 'injectManifest',
      srcDir: 'src/sw',
      filename: 'sw.ts',
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: false },
    },
    // Parity tests read backend enums and explanation texts from ../app (read-only, `?raw` imports).
    // The dev server itself never serves files outside frontend/.
    ...(process.env.VITEST ? { fs: { allow: [searchForWorkspaceRoot(process.cwd()), BACKEND_DIR] } } : {}),
  },
  build: {
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
