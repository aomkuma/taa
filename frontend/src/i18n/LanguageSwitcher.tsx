import { useTranslation } from 'react-i18next';

import { changeLanguage } from './index';
import { LANGUAGES } from './languages';

const BASE = 'rounded px-2 py-1';
const ACTIVE = `${BASE} font-semibold bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900`;
const INACTIVE = `${BASE} text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800`;

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  return (
    <div role="group" aria-label={t('language.label')} className="flex gap-1 text-sm">
      {LANGUAGES.map((language) => {
        const active = i18n.language === language;
        return (
          <button
            key={language}
            type="button"
            lang={language}
            aria-pressed={active}
            onClick={() => void changeLanguage(i18n, language)}
            className={active ? ACTIVE : INACTIVE}
          >
            {t(`language.${language}`)}
          </button>
        );
      })}
    </div>
  );
}
