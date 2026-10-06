import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Pages load lazily and fetch through a mocked API; on a busy machine the first render of a route can take
// longer than Testing Library's default 1 s for findBy*/waitFor. A longer limit only delays a failing test.
configure({ asyncUtilTimeout: 3000 });
