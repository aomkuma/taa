/**
 * The theory selection as the backend reads it (`TheoryPreferences` in app/advisory/preferences.py): a preset
 * selects whole families, `families` overrides on top of it, `detectors` overrides per detector. Every edit
 * here keeps the document minimal: an override equal to what the layer below gives is removed.
 */
import { FAMILIES } from '@/i18n/codes';
import type { Theories } from '@/pages/watchlists/schemas';

import type { Bound, Detector } from './schemas';

/** `PRESETS` (parity in the tests). */
export const PRESETS: Record<string, readonly string[]> = {
  ALL: FAMILIES,
  CLASSIC_TA: ['LEVELS', 'TREND', 'CHART_PATTERN', 'CANDLESTICK', 'MOMENTUM', 'VOLATILITY_VOLUME'],
  PRICE_ACTION: ['LEVELS', 'CHART_PATTERN', 'CANDLESTICK', 'SMART_MONEY', 'SESSIONS'],
  FIB_HARMONICS: ['FIBONACCI', 'HARMONIC', 'ELLIOTT', 'LEVELS'],
  TREND_FOLLOWING: ['TREND', 'MOMENTUM', 'ICHIMOKU', 'VOLATILITY_VOLUME'],
};
export const PRESET_NAMES = Object.keys(PRESETS);

/** *record* with *key* set to *value*, or without *key* when *value* is undefined. */
function put<T>(record: Readonly<Record<string, T>>, key: string, value: T | undefined): Record<string, T> {
  const rest = Object.fromEntries(Object.entries(record).filter(([k]) => k !== key));
  return value === undefined ? rest : { ...rest, [key]: value };
}

const inPreset = (theories: Theories, family: string) =>
  theories.preset !== null && (PRESETS[theories.preset] ?? []).includes(family);

/** `enabled_families()`. */
export function familyOn(theories: Theories, family: string): boolean {
  return theories.families[family] ?? inPreset(theories, family);
}

/** `enabled_detectors()`: the family's state unless the detector has its own override. */
export function detectorOn(theories: Theories, detector: Pick<Detector, 'id' | 'family'>): boolean {
  return theories.detectors[detector.id] ?? familyOn(theories, detector.family);
}

/** Whether the user changed anything on top of the preset. */
export function customized(theories: Theories): boolean {
  return Object.keys(theories.families).length > 0 || Object.keys(theories.detectors).length > 0;
}

/** Choosing a preset starts again from it: the family and detector overrides go. */
export function choosePreset(theories: Theories, preset: string): Theories {
  return { ...theories, preset, families: {}, detectors: {} };
}

/** Turns a family on or off; its detectors follow it again (their overrides go). */
export function setFamily(theories: Theories, family: string, on: boolean, catalog: readonly Detector[]) {
  const families = put(theories.families, family, on === inPreset(theories, family) ? undefined : on);
  const ids = new Set(catalog.filter((d) => d.family === family).map((d) => d.id));
  const detectors = Object.fromEntries(Object.entries(theories.detectors).filter(([id]) => !ids.has(id)));
  return { ...theories, families, detectors };
}

export function setDetector(theories: Theories, detector: Pick<Detector, 'id' | 'family'>, on: boolean) {
  const off = on === familyOn(theories, detector.family);
  return { ...theories, detectors: put(theories.detectors, detector.id, off ? undefined : on) };
}

/** May this pattern setup alert? (A setup without a toggle may.) */
export function setupOn(theories: Theories, name: string): boolean {
  return theories.pattern_strategies[name] ?? true;
}

export function setSetup(theories: Theories, name: string, on: boolean): Theories {
  return { ...theories, pattern_strategies: put(theories.pattern_strategies, name, on ? undefined : false) };
}

/** The value a parameter has for the user: their own, else the catalog default. */
export function paramValue(theories: Theories, detector: Detector, name: string): unknown {
  return theories.params[detector.id]?.[name] ?? detector.params[name];
}

/** Sets one parameter; the default value removes the override (and an empty detector entry). */
export function setParam(theories: Theories, detector: Detector, name: string, value: unknown): Theories {
  const own = put(
    theories.params[detector.id] ?? {},
    name,
    value === detector.params[name] ? undefined : value,
  );
  const kept = Object.keys(own).length > 0 ? own : undefined;
  return { ...theories, params: put(theories.params, detector.id, kept) };
}

export function resetParams(theories: Theories, detectorId: string): Theories {
  return { ...theories, params: put<Record<string, unknown>>(theories.params, detectorId, undefined) };
}

/** Whether *value* is allowed by *bound* (integers whole, exclusive ends excluded). */
export function withinBound(bound: Bound, value: unknown): boolean {
  if (bound.type === 'boolean') return typeof value === 'boolean';
  if (typeof value !== 'number' || !Number.isFinite(value)) return false;
  if (bound.type === 'integer' && !Number.isInteger(value)) return false;
  const aboveMin = bound.min_exclusive ? value > bound.min : value >= bound.min;
  const belowMax = bound.max_exclusive ? value < bound.max : value <= bound.max;
  return aboveMin && belowMax;
}

/** Detectors whose parameters are out of bounds (the save stays disabled until they are fixed). */
export function invalidParams(theories: Theories, catalog: readonly Detector[]): string[] {
  return catalog
    .filter((d) =>
      Object.entries(theories.params[d.id] ?? {}).some(([name, value]) => {
        const bound = d.bounds[name];
        return bound === undefined || !withinBound(bound, value);
      }),
    )
    .map((d) => d.id);
}

/** Families the plan does not include (`null`: the plan includes every family). */
export function lockedFamilies(allowed: readonly string[] | null | undefined): Set<string> {
  if (allowed === null || allowed === undefined) return new Set();
  return new Set(FAMILIES.filter((f) => !allowed.includes(f)));
}
