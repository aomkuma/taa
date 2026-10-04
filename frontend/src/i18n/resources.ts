import enCodes from './locales/en/codes.json';
import enCommon from './locales/en/common.json';
import enExplain from './locales/en/explain.json';
import thCodes from './locales/th/codes.json';
import thCommon from './locales/th/common.json';
import thExplain from './locales/th/explain.json';

import type { Language } from './languages';

export const NAMESPACES = ['common', 'explain', 'codes'] as const;

export const resources = {
  en: { common: enCommon, explain: enExplain, codes: enCodes },
  th: { common: thCommon, explain: thExplain, codes: thCodes },
} as const satisfies Record<Language, Record<(typeof NAMESPACES)[number], object>>;
