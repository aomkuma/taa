import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';

import { createI18n } from '@/i18n';
import type { Language } from '@/i18n/languages';

/** Renders *ui* with an isolated i18n instance in *language*. */
export function renderWithI18n(ui: ReactElement, language: Language = 'th') {
  const i18n = createI18n(language);
  return { i18n, ...render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>) };
}
