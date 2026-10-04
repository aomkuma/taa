import enCommon from './locales/en/common.json';
import enExplain from './locales/en/explain.json';
import thCommon from './locales/th/common.json';
import thExplain from './locales/th/explain.json';

import type { Language } from './languages';

export const NAMESPACES = ['common', 'explain'] as const;

export const resources = {
  en: { common: enCommon, explain: enExplain },
  th: { common: thCommon, explain: thExplain },
} as const satisfies Record<Language, Record<(typeof NAMESPACES)[number], object>>;
