import { Outlet } from 'react-router';

/** Pages outside the signed-in shell (login, not found). */
export function PublicFrame() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6">
      <Outlet />
    </main>
  );
}
