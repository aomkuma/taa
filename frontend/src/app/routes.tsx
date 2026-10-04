import type { RouteObject } from 'react-router';

import { Layout } from '@/app/Layout';
import { RequireAuth } from '@/auth/RequireAuth';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      {
        // Everything that shows account or trading data goes inside this guard.
        element: <RequireAuth />,
        children: [{ index: true, element: <HomePage /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
