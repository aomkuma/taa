import { Link } from 'react-router';

export function NotFoundPage() {
  return (
    <section>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-2 inline-block underline">
        Back to home
      </Link>
    </section>
  );
}
