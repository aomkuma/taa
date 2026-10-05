import configPy from '../../../../app/config.py?raw';
import preferencesPy from '../../../../app/advisory/preferences.py?raw';
import positionSizerPy from '../../../../app/risk/position_sizer.py?raw';
// TradingProfile(style=s).resolve() for a few styles, printed by the backend (see the profile page decisions)
import resolvedByPython from '@/test/fixtures/profile-resolved.json';
import { pyStrEnumValues } from '@/test/python';
import {
  HOLDING_STYLES,
  SPLIT_MODES,
  STOP_PLACEMENTS,
  type EntryPlan,
  type TradingProfile,
  WEIGHT_SCHEMES,
} from '@/pages/watchlists/schemas';

import {
  CEILINGS,
  fillTakeProfits,
  overrideValid,
  planProblems,
  PROFILE_ANCHORS,
  resolve,
  setMode,
  setOverride,
  warnings,
} from './profileModel';

const NO_OVERRIDES = {
  risk_per_signal_percent: null,
  portfolio_heat_percent: null,
  max_positions: null,
  max_daily_loss_percent: null,
  min_rr: null,
  min_win_probability: null,
  min_supporting_families: null,
  conflict_policy: null,
  require_htf_alignment: null,
};
const profile = (style: number): TradingProfile => ({
  style,
  overrides: { ...NO_OVERRIDES },
  holding_style: 'DAY',
  max_signals_per_day: 10,
  avoid_news: true,
  hold_over_weekend: false,
  stop_placement: 'STRUCTURE',
});
const plan = (over: Partial<EntryPlan> = {}): EntryPlan => ({
  lot_unit: null,
  mode: 'SINGLE',
  parts: 1,
  weights: 'EQUAL',
  spacing_atr: 0.5,
  partial_tp_r: [1, 2],
  ...over,
});

describe('backend parity', () => {
  it('enums', () => {
    expect([...HOLDING_STYLES]).toEqual(pyStrEnumValues(preferencesPy, 'HoldingStyle'));
    expect([...STOP_PLACEMENTS]).toEqual(pyStrEnumValues(preferencesPy, 'StopPlacement'));
    expect([...SPLIT_MODES]).toEqual(pyStrEnumValues(positionSizerPy, 'SplitMode'));
    expect([...WEIGHT_SCHEMES]).toEqual(pyStrEnumValues(positionSizerPy, 'WeightScheme'));
  });

  it('anchors and ceilings', () => {
    const block = preferencesPy.slice(
      preferencesPy.indexOf('PROFILE_ANCHORS'),
      preferencesPy.indexOf('INT_DEFENSIVE'),
    );
    for (const [field, values] of Object.entries(PROFILE_ANCHORS)) {
      const match = new RegExp(String.raw`"${field}": \(([^)]*)\)`, 's').exec(block);
      const python = (match?.[1] ?? '')
        .split(',')
        .map((v) => v.trim())
        .filter((v) => v !== '')
        .map((v) =>
          v === 'True'
            ? true
            : v === 'False'
              ? false
              : v.startsWith('ConflictPolicy.')
                ? v.slice(15)
                : Number(v),
        );
      expect(python, field).toEqual([...values]);
    }
    const ceiling = (name: string) =>
      Number(new RegExp(String.raw`^${name} = ([\d.]+)`, 'm').exec(configPy)?.[1]);
    expect(CEILINGS).toEqual({
      risk_per_signal_percent: ceiling('CEILING_RISK_PER_TRADE_PCT'),
      portfolio_heat_percent: ceiling('CEILING_TOTAL_OPEN_RISK_PCT'),
      max_daily_loss_percent: ceiling('CEILING_DAILY_LOSS_PCT'),
    });
  });

  it.each(Object.entries(resolvedByPython))('style %s resolves as the backend does', (style, expected) => {
    expect(resolve(profile(Number(style))).values).toEqual(expected);
  });
});

describe('overrides', () => {
  it('replace the slider and are bounded', () => {
    const custom = setOverride(profile(50), 'min_rr', 3);
    const { values, custom: fields } = resolve(custom);
    expect(values.min_rr).toBe(3);
    expect([...fields]).toEqual(['min_rr']);
    expect(overrideValid('risk_per_signal_percent', 0)).toBe(false); // above 0
    expect(overrideValid('risk_per_signal_percent', 2)).toBe(true);
    expect(overrideValid('max_positions', 2.5)).toBe(false);
    expect(overrideValid('conflict_policy', 'BLOCK')).toBe(true);
  });

  it('warns about offensive settings and back-loaded scale-in', () => {
    expect(warnings(resolve(profile(50)).values, plan())).toEqual([]);
    expect(
      warnings(resolve(profile(100)).values, plan({ mode: 'SCALE_IN', parts: 3, weights: 'BACK_LOADED' })),
    ).toEqual(['risk', 'heat', 'dailyLoss', 'rr', 'conflict', 'htf', 'backLoaded']);
    const custom = { ...profile(50), overrides: { ...NO_OVERRIDES, risk_per_signal_percent: 2.5 } };
    expect(warnings(resolve(custom).values, plan())).toEqual(['riskVeryHigh']);
  });
});

describe('entry plan', () => {
  it('keeps the plan coherent across mode changes', () => {
    expect(setMode(plan(), 'SCALE_IN').parts).toBe(2);
    expect(setMode(plan({ mode: 'SCALE_IN', parts: 4 }), 'SINGLE').parts).toBe(1);
    expect(setMode(plan({ parts: 1 }), 'SAME_PRICE').partial_tp_r).toEqual([1, 2]);
    expect(fillTakeProfits([1], 4)).toEqual([1, 2, 3]);
  });

  it('checks the backend rules', () => {
    expect(planProblems(plan())).toEqual([]);
    expect(planProblems(plan({ mode: 'SAME_PRICE', parts: 3, partial_tp_r: [2, 1] }))).toEqual([
      'takeProfits',
    ]);
    expect(planProblems(plan({ mode: 'SCALE_IN', parts: 6, spacing_atr: 5, lot_unit: 0 }))).toEqual([
      'parts',
      'lotUnit',
      'spacing',
    ]);
  });
});
