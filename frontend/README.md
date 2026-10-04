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

## Sign-in and sessions (TAA-902, PLAN §A14)

- `/login` takes username, password and the 6-digit authenticator code. Users are created only on the server
  (`python -m app.cli web create-user <name>`); there is no sign-up page.
- `src/auth/session.ts` keeps the signed-in state in the query cache (`AUTH_QUERY_KEY`). The session cookie is
  HttpOnly, so the app reads its session from `GET /auth/session` and the login response.
- Pages with account or trading data are routes inside `RequireAuth` (`src/app/routes.tsx`). While the session
  check fails (server unreachable) nothing protected is shown.
- `apiPost` / `apiPostEmpty` add the `X-CSRF-Token` header. Any 401 `unauthenticated` ends the session in the app
  and the guard returns to `/login` with a "session ended" notice, then back to the original page after login.
- The app also ends the session once the server's limits pass without requests (30 min idle after the last
  request, 12 h absolute, measured on the server clock via `server_time`). `GET /auth/session` is not polled,
  because it would keep the session alive.
- Tests fake the API with `mockApi` (`src/test/api.ts`) and render the whole app with `renderApp`
  (`src/test/render.tsx`).

## App shell (TAA-903, PLAN §A15 "TAA-903 decisions")

- **Pages and navigation:** add a page to `src/app/shell/nav.ts` (id, group, `own`) and a `nav.<id>` label in both
  catalogs; `routes.tsx` creates its route. Replace its `PlaceholderPage` in `routes.tsx` when the page is built.
  `own: true` pages sit inside `RequireOwnEngine` and are hidden on the market feed.
- **Engine:** `useEngine()` (`src/engine/context.ts`) gives the shown engine (`engineId`, `own`) and the picker list;
  `useEngineStatus()` the status of the user's own engine. Engine queries use keys under `engineKey(id)` so the live
  stream's resync refetches them.
- **Live updates:** `useLiveEvents(topic, listener)` (`src/live/context.ts`) for stream events of the shown engine;
  `useLive()` for the stream state. Tests drive the stream with `fakeEventSources()` (`src/test/eventSource.ts`) via
  `renderApp(path, lang, { createEventSource })`.
- **Stale data:** show `<StaleBadge since={…} />` (`src/app/shell/StaleBadge.tsx`) when data stopped updating.
- **Themes:** `src/app/theme.ts`; style both themes with Tailwind's `dark:` variant (it follows the `dark` class).
  `useDarkMode()` tells canvas code (charts) which theme is applied.
- **Heavy pages** load lazily: add them to `BUILT` in `routes.tsx` with `lazy: () => import(...)`.
- **Charts:** only `src/pages/charts/chartAdapter.ts` imports `lightweight-charts`; page tests `vi.mock` it. Keep
  the library's attribution logo off (it injects a `<style>` the CSP blocks) and keep `ChartAttribution` under
  every chart.

## Localization (PLAN §A28)

Everything lives in `src/i18n/`.

- **Languages:** react-i18next with `th` (default) and `en`. `LanguageSwitcher` changes the language, sets
  `<html lang>` and remembers the choice in `localStorage` (`taa.language`); the profile language replaces this
  once the API has it.
- **Catalogs:** `locales/<lang>/<namespace>.json`, typed through `i18next.d.ts`. Namespaces: `common` (UI text)
  and `explain` (advisory explanations). Both languages must have the same keys and placeholders
  (`catalogs.test.ts`). Placeholders use i18next syntax, `{{name}}`.
- **Font:** Noto Sans Thai (variable, Thai + Latin subsets) is bundled from `@fontsource-variable/noto-sans-thai`
  and precached by the service worker. No Google Fonts CDN.
- **Formatting** (`format.ts`, or the `useFormat()` hook bound to the current language):
  - dates use `th-TH-u-ca-gregory` (Gregorian years; `calendar: 'buddhist'` opts into the Buddhist era) or
    `en-GB`, 24-hour, displayed in `Asia/Bangkok` by default
  - API datetimes must carry `Z` or an offset; a naive string throws `NaiveDateTimeError`
  - numbers and money are locale-aware (`formatMoney(value, 'USD', lang)` shows the currency code)
  - percent inputs are in percent units like the backend (`0.5` → `0.5%`)
  - missing or non-finite values render as `—`, never as `0`

### Translation keys for backend codes

| Backend source                                               | Key                                                                                |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `explain(key, params)` keys (`app/advisory/explanations.py`) | `explain:<key>`, rendered by `explain()` in `explain.ts`                           |
| `Reason` (`app/risk/reasons.py`) and strategy `ReasonCode`   | `codes:reason.<CODE>`                                                              |
| `Gate`, `GateStatus`                                         | `codes:gate.<G>`, `codes:gateStatus.<S>`                                           |
| `OpportunityStatus`, `WindowReason`, `InvalidReason`         | `codes:opportunityStatus.<S>`, `codes:windowReason.<R>`, `codes:invalidReason.<R>` |
| `ShadowStatus`, `ExitReason`                                 | `codes:shadowStatus.<S>`, `codes:exitReason.<CODE>`                                |
| `BreakerName`, `NotificationType`, `Decision`                | `codes:breaker.<NAME>`, `codes:notificationType.<TYPE>`, `codes:decision.<D>`      |
| `Family` (evidence theory families)                          | `codes:family.<FAMILY>`                                                            |

- Parameterized codes (`BREAKER_OPEN:daily_loss`) map to the key of the bare code, with the rest passed as
  `{{detail}}`.
- A code or explanation key without a translation renders as itself, so nothing is silently hidden.
- The `explain` catalogs were generated from `app/advisory/explanations.py` (`{x}` → `{{x}}`). Texts for the
  `codes` namespace are added with the pages that show them.
- Parity tests read the backend sources (read-only, via Vite `?raw`) and fail when the Python enums, explanation
  keys, placeholders or `MONEY_PARAMS` change without a matching frontend change.

## Rules

- The built page must work under the strict CSP of PLAN §A14: no inline scripts or styles, no CDNs. All assets
  (including fonts) are bundled.
- No profitability claims in any UI text.
- Use the `@/` import alias for `src/`.
