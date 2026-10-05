import baseStrategyPy from '../../../../app/strategy/base_strategy.py?raw';
import exampleStrategyPy from '../../../../app/strategy/example_strategy.py?raw';
import rulesPy from '../../../../app/strategy/rules.py?raw';
import setupsPy from '../../../../app/strategy/setups.py?raw';

import en from '@/i18n/locales/en/common.json';
import th from '@/i18n/locales/th/common.json';
import { pyLiteralValues, pyParamFields } from '@/test/python';

const sorted = (values: Iterable<string>) => [...new Set(values)].sort();

describe('strategy parameter texts', () => {
  const fields = sorted(
    [baseStrategyPy, rulesPy, exampleStrategyPy, setupsPy].flatMap((source) => pyParamFields(source)),
  );

  it('name every parameter of the strategy models in both languages', () => {
    expect(fields).toContain('adx_min');
    expect(sorted(Object.keys(en.strategies.param))).toEqual(fields);
    expect(sorted(Object.keys(th.strategies.param))).toEqual(fields);
  });

  it('name every stop and target choice', () => {
    for (const catalog of [en, th]) {
      expect(sorted(Object.keys(catalog.strategies.paramValue.stop_mode))).toEqual(
        sorted(pyLiteralValues(setupsPy, 'StopMode')),
      );
      expect(sorted(Object.keys(catalog.strategies.paramValue.target_mode))).toEqual(
        sorted(pyLiteralValues(setupsPy, 'TargetMode')),
      );
    }
  });
});
