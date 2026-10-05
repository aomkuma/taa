import preferencesPy from '../../../../app/advisory/preferences.py?raw';
import { createI18n } from '@/i18n';
import { evidenceName, FAMILIES } from '@/i18n/codes';
import samples from '@/test/fixtures/api-samples.json';
import { pyStrEnumValues } from '@/test/python';
import { CONFLICT_POLICIES, type Theories } from '@/pages/watchlists/schemas';

import { CatalogSchema } from './schemas';
import {
  choosePreset,
  customized,
  detectorOn,
  familyOn,
  invalidParams,
  lockedFamilies,
  PRESETS,
  paramValue,
  resetParams,
  setDetector,
  setFamily,
  setParam,
  setSetup,
  setupOn,
  withinBound,
} from './theoryModel';

// The real `GET /advisory/detectors` of tests/web/test_api_samples.py.
const catalog = CatalogSchema.parse((samples as Record<string, unknown>)['advisory/detectors']);
const detectors = catalog.detectors;
function byId(id: string) {
  const found = detectors.find((d) => d.id === id);
  if (found === undefined) throw new Error(`no detector ${id} in the sample catalog`);
  return found;
}
const bound = (name: string) => {
  const found = RETRACEMENT.bounds[name];
  if (found === undefined) throw new Error(`no bound ${name}`);
  return found;
};
const RETRACEMENT = byId('fib.retracement');

const defaults = (): Theories => ({
  preset: 'ALL',
  families: {},
  detectors: {},
  params: {},
  pattern_strategies: {},
  min_supporting_families: 2,
  conflict_policy: 'PENALIZE',
});

describe('backend parity', () => {
  it('presets', () => {
    const block = preferencesPy.slice(
      preferencesPy.indexOf('PRESETS: dict'),
      preferencesPy.indexOf('class TheoryPreferences'),
    );
    const backend: Record<string, string[]> = {};
    for (const m of block.matchAll(/"([A-Z_]+)": frozenset\(\s*(?:\{([^}]*)\}|Family)\s*\)/g)) {
      const families =
        m[2] === undefined ? [...FAMILIES] : [...m[2].matchAll(/F\.([A-Z_]+)/g)].map((x) => x[1] ?? '');
      backend[m[1] ?? ''] = families.sort();
    }
    expect(Object.fromEntries(Object.entries(PRESETS).map(([k, v]) => [k, [...v].sort()]))).toEqual(backend);
  });

  it('conflict policies', () => {
    expect([...CONFLICT_POLICIES]).toEqual(pyStrEnumValues(preferencesPy, 'ConflictPolicy'));
  });

  it.each(['th', 'en'] as const)('every detector and bounded parameter has a %s text', (language) => {
    const i18n = createI18n(language);
    for (const d of detectors) {
      expect(evidenceName(i18n, d.id, ''), d.id).not.toBe('');
      for (const name of Object.keys(d.bounds)) {
        expect(i18n.exists(`theories.param.label.${name}`), `${d.id}.${name}`).toBe(true);
      }
    }
    for (const family of FAMILIES) expect(i18n.exists(`theories.about.${family}`), family).toBe(true);
  });
});

describe('selection', () => {
  it('follows the preset, then family and detector overrides', () => {
    const fib = choosePreset(defaults(), 'TREND_FOLLOWING');
    expect(familyOn(fib, 'FIBONACCI')).toBe(false);
    expect(familyOn(fib, 'TREND')).toBe(true);
    const on = setFamily(fib, 'FIBONACCI', true, detectors);
    expect(on.families).toEqual({ FIBONACCI: true });
    expect(detectorOn(on, RETRACEMENT)).toBe(true);
    const off = setDetector(on, RETRACEMENT, false);
    expect(off.detectors).toEqual({ 'fib.retracement': false });
    expect(customized(off)).toBe(true);
    // turning the family off again drops it back to the preset and clears its detectors' overrides
    expect(setFamily(off, 'FIBONACCI', false, detectors)).toMatchObject({ families: {}, detectors: {} });
    expect(setDetector(off, RETRACEMENT, true).detectors).toEqual({});
    expect(choosePreset(off, 'ALL')).toMatchObject({ preset: 'ALL', families: {}, detectors: {} });
  });

  it('keeps setup toggles minimal', () => {
    const off = setSetup(defaults(), 'setup_fib_pullback', false);
    expect(setupOn(off, 'setup_fib_pullback')).toBe(false);
    expect(setSetup(off, 'setup_fib_pullback', true).pattern_strategies).toEqual({});
  });

  it('lists the families a plan leaves out', () => {
    expect(lockedFamilies(null).size).toBe(0);
    expect([...lockedFamilies(['TREND', 'LEVELS'])]).toHaveLength(FAMILIES.length - 2);
  });
});

describe('parameters', () => {
  it('stores only the values that differ from the defaults', () => {
    const changed = setParam(defaults(), RETRACEMENT, 'tol_atr', 0.5);
    expect(changed.params).toEqual({ 'fib.retracement': { tol_atr: 0.5 } });
    expect(paramValue(changed, RETRACEMENT, 'tol_atr')).toBe(0.5);
    expect(paramValue(changed, RETRACEMENT, 'max_age_bars')).toBe(3);
    expect(setParam(changed, RETRACEMENT, 'tol_atr', 0.25).params).toEqual({});
    expect(resetParams(changed, 'fib.retracement').params).toEqual({});
  });

  it('checks the catalog bounds', () => {
    const tol = bound('tol_atr');
    expect(withinBound(tol, 2)).toBe(true);
    expect(withinBound(tol, 0)).toBe(false); // exclusive minimum
    expect(withinBound(bound('max_age_bars'), 2.5)).toBe(false); // integer
    expect(withinBound({ type: 'boolean' }, true)).toBe(true);
    const bad = setParam(defaults(), RETRACEMENT, 'tol_atr', 9);
    expect(invalidParams(bad, detectors)).toEqual(['fib.retracement']);
    expect(
      invalidParams({ ...defaults(), params: { 'fib.retracement': { levels: [0.5] } } }, detectors),
    ).toEqual(['fib.retracement']); // not a changeable parameter
  });
});
