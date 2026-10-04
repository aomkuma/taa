import type { i18n as I18n } from 'i18next';

type DynamicT = (key: string, options: Readonly<Record<string, string>>) => string;

/**
 * `t` for keys built at runtime from backend codes. The typed `t` only accepts literal catalog keys; callers check
 * `i18n.exists(key)` first and handle a missing key themselves.
 */
export function translateDynamic(
  i18n: I18n,
  key: string,
  options: Readonly<Record<string, string>> = {},
): string {
  const t = i18n.t.bind(i18n) as unknown as DynamicT;
  return t(key, options);
}
