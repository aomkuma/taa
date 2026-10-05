import type { RouteObject } from 'react-router';

import { Layout } from '@/app/Layout';
import { PublicFrame } from '@/app/PublicFrame';
import { AppShell } from '@/app/shell/AppShell';
import { NAV_ITEMS, type NavId } from '@/app/shell/nav';
import { RequireOwnEngine } from '@/app/shell/RequireOwnEngine';
import { RequireAuth } from '@/auth/RequireAuth';
import type { EventSourceFactory } from '@/live/stream';
import { DashboardPage } from '@/pages/dashboard/DashboardPage';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { PlaceholderPage } from '@/pages/PlaceholderPage';

/** Built pages; the others show `PlaceholderPage`. Heavy pages load lazily in their own chunk. */
const BUILT: Partial<Record<NavId, Omit<RouteObject, 'path' | 'index' | 'children'>>> = {
  charts: { lazy: async () => ({ Component: (await import('@/pages/charts/ChartsPage')).ChartsPage }) },
  positions: {
    lazy: async () => ({ Component: (await import('@/pages/trades/PositionsPage')).PositionsPage }),
  },
  history: { lazy: async () => ({ Component: (await import('@/pages/trades/HistoryPage')).HistoryPage }) },
  decisions: {
    lazy: async () => ({ Component: (await import('@/pages/decisions/DecisionsPage')).DecisionsPage }),
  },
  symbols: { lazy: async () => ({ Component: (await import('@/pages/symbols/SymbolsPage')).SymbolsPage }) },
  analytics: {
    lazy: async () => ({ Component: (await import('@/pages/analytics/AnalyticsPage')).AnalyticsPage }),
  },
  ai: { lazy: async () => ({ Component: (await import('@/pages/ai/AIPage')).AIPage }) },
  learning: {
    lazy: async () => ({ Component: (await import('@/pages/learning/LearningPage')).LearningPage }),
  },
  backtests: {
    lazy: async () => ({ Component: (await import('@/pages/backtests/BacktestsPage')).BacktestsPage }),
  },
  risk: { lazy: async () => ({ Component: (await import('@/pages/risk/RiskPage')).RiskPage }) },
  strategies: {
    lazy: async () => ({ Component: (await import('@/pages/strategies/StrategiesPage')).StrategiesPage }),
  },
  system: { lazy: async () => ({ Component: (await import('@/pages/system/SystemPage')).SystemPage }) },
  settings: {
    lazy: async () => ({ Component: (await import('@/pages/settings/SettingsPage')).SettingsPage }),
  },
  notifications: {
    lazy: async () => ({
      Component: (await import('@/pages/notifications/NotificationsPage')).NotificationsPage,
    }),
  },
  accuracy: {
    lazy: async () => ({ Component: (await import('@/pages/accuracy/AccuracyPage')).AccuracyPage }),
  },
  account: {
    lazy: async () => ({ Component: (await import('@/pages/account/AccountPage')).AccountPage }),
  },
  admin: { lazy: async () => ({ Component: (await import('@/pages/account/AdminPage')).AdminPage }) },
  engines: { lazy: async () => ({ Component: (await import('@/pages/engines/EnginesPage')).EnginesPage }) },
  profile: { lazy: async () => ({ Component: (await import('@/pages/profile/ProfilePage')).ProfilePage }) },
  theories: {
    lazy: async () => ({ Component: (await import('@/pages/theories/TheoriesPage')).TheoriesPage }),
  },
  watchlists: {
    lazy: async () => ({ Component: (await import('@/pages/watchlists/WatchlistsPage')).WatchlistsPage }),
  },
  ranking: { lazy: async () => ({ Component: (await import('@/pages/ranking/RankingPage')).RankingPage }) },
  opportunities: {
    lazy: async () => ({
      Component: (await import('@/pages/opportunities/OpportunitiesPage')).OpportunitiesPage,
    }),
  },
};

/** Pages that also answer `<path>/:<param>` (deep links from pushes, e.g. `/opportunities/<id>`). */
const DETAIL_PARAM: Partial<Record<NavId, string>> = { opportunities: 'opportunityId' };

const pages = (own: boolean): RouteObject[] =>
  NAV_ITEMS.filter((item) => item.own === own && item.id !== 'dashboard').flatMap((item) => {
    const page = BUILT[item.id] ?? { element: <PlaceholderPage id={item.id} /> };
    const param = DETAIL_PARAM[item.id];
    return [
      { path: item.path, ...page },
      ...(param && BUILT[item.id] ? [{ path: `${item.path}/:${param}`, ...page }] : []),
    ];
  });

export interface RouteOptions {
  /** Tests inject a fake EventSource for the live stream. */
  createEventSource?: EventSourceFactory;
}

export function createRoutes({ createEventSource }: RouteOptions = {}): RouteObject[] {
  return [
    {
      path: '/',
      element: <Layout />,
      children: [
        {
          element: <PublicFrame />,
          children: [
            { path: 'login', element: <LoginPage /> },
            { path: '*', element: <NotFoundPage /> },
          ],
        },
        {
          // Everything that shows account or trading data goes inside this guard.
          element: <RequireAuth />,
          children: [
            {
              element: <AppShell {...(createEventSource ? { createEventSource } : {})} />,
              children: [
                { index: true, element: <DashboardPage /> },
                ...pages(false),
                { element: <RequireOwnEngine />, children: pages(true) },
              ],
            },
          ],
        },
      ],
    },
  ];
}

export const routes = createRoutes();
