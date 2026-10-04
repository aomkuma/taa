import './index.css';

import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';

import { createQueryClient } from '@/app/queryClient';
import { routes } from '@/app/routes';

const container = document.getElementById('root');
if (!container) {
  throw new Error('#root element is missing from index.html');
}

const router = createBrowserRouter(routes);
const queryClient = createQueryClient();

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
