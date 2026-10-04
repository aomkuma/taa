# TAA frontend (PWA)

React + TypeScript + Vite PWA for the TAA web service (PLAN §A15). Run every command from `frontend/`.

```powershell
npm install            # once
npm run dev            # http://127.0.0.1:5173, proxies /api to the FastAPI service
npm run lint           # ESLint (type-aware) + Prettier check
npm run typecheck      # tsc for the app and for vite.config.ts
npm run test           # Vitest (jsdom)
npm run build          # type-check + production build into dist/ (served by FastAPI)
npm run format         # Prettier write
```

A change is done only when `lint`, `typecheck`, `test` and `build` are all green.

## Dev proxy

`npm run dev` forwards `/api/*` to `http://127.0.0.1:8000`, the local FastAPI web service. Set `TAA_API_TARGET` to
point elsewhere. In production the API and the app share one origin, so there is no CORS.

## Stack

- Vite, React, TypeScript (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)
- Tailwind CSS 4 (`@tailwindcss/vite`, CSS-first config in `src/index.css`)
- React Router (`src/app/routes.tsx`), TanStack Query (`src/app/queryClient.ts`)
- zod: every API response is validated in `src/api/client.ts`; a mismatch is an error, never rendered
- vite-plugin-pwa (Workbox `generateSW`): precaches the app shell; `/api/` is never answered from the shell.
  API caching rules, icons and the install prompt belong to TAA-914.

TypeScript stays on 6.0.x until typescript-eslint supports TypeScript 7.

## Rules

- The built page must work under the strict CSP of PLAN §A14: no inline scripts or styles, no CDNs. All assets
  (including fonts) are bundled.
- No profitability claims in any UI text.
- Use the `@/` import alias for `src/`.
