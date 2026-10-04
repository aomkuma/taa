/**
 * Tiny readers for backend Python sources, used by parity tests so frontend catalogs fail loudly when the
 * backend enums or explanation texts change. Sources are imported with Vite's `?raw` suffix.
 */

/** The string values of `class <name>(StrEnum)` in *source*. */
export function pyStrEnumValues(source: string, className: string): string[] {
  const lines = source.split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith(`class ${className}(StrEnum):`));
  if (start < 0) throw new Error(`class ${className}(StrEnum) not found`);
  const values: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.trim() !== '' && !/^\s/.test(line)) break;
    const match = /^\s+[A-Z][A-Z0-9_]* = "([^"]+)"/.exec(line);
    if (match?.[1]) values.push(match[1]);
  }
  return values;
}

/** Explanation keys in `TEXTS` with the placeholder names used by each (both languages together). */
export function pyExplanationPlaceholders(source: string): Map<string, Set<string>> {
  const body = source.slice(source.indexOf('TEXTS'), source.indexOf('MONEY_PARAMS'));
  const keyPattern = /^ {4}"([a-z0-9_]+\.[a-z0-9_]+)": \{/gm;
  const starts = [...body.matchAll(keyPattern)];
  const result = new Map<string, Set<string>>();
  starts.forEach((match, i) => {
    const key = match[1] ?? '';
    const block = body.slice(match.index, starts[i + 1]?.index ?? body.length);
    result.set(key, new Set([...block.matchAll(/\{([a-z_]+)\}/g)].map((m) => m[1] ?? '')));
  });
  return result;
}

/** The names inside `MONEY_PARAMS = frozenset({...})`. */
export function pyMoneyParams(source: string): string[] {
  const match = /MONEY_PARAMS = frozenset\(\{([^}]*)\}\)/.exec(source);
  if (!match?.[1]) throw new Error('MONEY_PARAMS not found');
  return [...match[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1] ?? '');
}
