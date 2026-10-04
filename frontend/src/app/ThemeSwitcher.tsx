import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { applyTheme, isTheme, loadTheme, onSystemThemeChange, saveTheme, type Theme, THEMES } from './theme';

export function ThemeSwitcher() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>(loadTheme);

  useEffect(() => {
    applyTheme(theme);
    if (theme !== 'system') return undefined;
    return onSystemThemeChange(() => {
      applyTheme('system');
    });
  }, [theme]);

  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="sr-only">{t('theme.label')}</span>
      <select
        value={theme}
        onChange={(event) => {
          const next = event.target.value;
          if (!isTheme(next)) return;
          saveTheme(next);
          setTheme(next);
        }}
        className="rounded border border-slate-300 bg-white px-1 py-1 dark:border-slate-700 dark:bg-slate-900"
      >
        {THEMES.map((value) => (
          <option key={value} value={value}>
            {t(`theme.${value}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
