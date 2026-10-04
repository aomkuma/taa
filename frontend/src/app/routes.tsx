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
};

const pages = (own: boolean): RouteObject[] =>
  NAV_ITEMS.filter((item) => item.own === own && item.id !== 'dashboard').map((item) => ({
    path: item.path,
    ...(BUILT[item.id] ?? { element: <PlaceholderPage id={item.id} /> }),
  }));

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
