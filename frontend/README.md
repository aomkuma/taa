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
