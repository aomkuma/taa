import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { LanguageSwitcher } from '@/i18n/LanguageSwitcher';
import { loadLanguage } from '@/i18n/languages';
import { renderWithI18n } from '@/test/render';

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = 'th';
  });

  it('marks the current language as pressed', () => {
    renderWithI18n(<LanguageSwitcher />, 'th');
    expect(screen.getByRole('button', { name: 'ไทย' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches language, updates <html lang> and remembers the choice', async () => {
    const { i18n } = renderWithI18n(<LanguageSwitcher />, 'th');

    await userEvent.click(screen.getByRole('button', { name: 'English' }));

    expect(i18n.language).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    expect(loadLanguage()).toBe('en');
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
  });
});
