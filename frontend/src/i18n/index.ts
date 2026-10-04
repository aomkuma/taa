/**
 * i18next setup (PLAN §A28). Resources are bundled, so initialization is synchronous and the first render is
 * already translated. Use `createI18n` in tests for an isolated instance.
 */
import i18next, { type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';

import { DEFAULT_LANGUAGE, type Language, LANGUAGES, loadLanguage, saveLanguage } from './languages';
import { NAMESPACES, resources } from './resources';

export function createI18n(language: Language = DEFAULT_LANGUAGE): I18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: language,
    // Catalogs are complete in both languages (parity test); English is the neutral fallback.
    fallbackLng: 'en',
    supportedLngs: LANGUAGES,
    ns: NAMESPACES,
    defaultNS: 'common',
    initAsync: false,
    // React escapes rendered text; escaping here as well would double-encode.
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  return instance;
}

/** Applies a language to i18next, the document and storage. */
export async function changeLanguage(instance: I18n, language: Language): Promise<void> {
  await instance.changeLanguage(language);
  document.documentElement.lang = language;
  saveLanguage(language);
}

export function initAppI18n(): I18n {
  const language = loadLanguage();
  document.documentElement.lang = language;
  return createI18n(language);
}
