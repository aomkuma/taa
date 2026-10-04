/** Supported UI languages (PLAN §A28): Thai is the default, English the alternative. */

export const LANGUAGES = ['th', 'en'] as const;
export type Language = (typeof LANGUAGES)[number];

export const DEFAULT_LANGUAGE: Language = 'th';

// The user's profile language (users.locale) will take precedence once the API exposes it (TAA-918).
const STORAGE_KEY = 'taa.language';

export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && (LANGUAGES as readonly string[]).includes(value);
}

/** The remembered language, or the default. Storage can be missing or throw (private mode, blocked site data). */
export function loadLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

export function saveLanguage(language: Language): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // A preference that cannot be stored only costs a re-selection next visit.
  }
}
