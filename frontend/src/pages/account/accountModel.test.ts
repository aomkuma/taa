import configPy from '../../../../app/config.py?raw';
import entitlementsPy from '../../../../app/web/entitlements.py?raw';
import { pyStrEnumValues } from '@/test/python';

import { formOf, manualProblems, overrideKind, overrideValueOf } from './accountModel';
import { type Entitlements, FEATURES, LIMITS, RISK_CEILING } from './schemas';

const form = { equity: '1000', balance: '', currency: 'USD', leverage: '200', risk: '' };

describe('backend parity', () => {
  it('features, limits and the risk ceiling', () => {
    expect([...FEATURES]).toEqual(pyStrEnumValues(entitlementsPy, 'Feature'));
    expect([...LIMITS]).toEqual(pyStrEnumValues(entitlementsPy, 'Limit'));
    expect(Number(/^CEILING_RISK_PER_TRADE_PCT = ([\d.]+)/m.exec(configPy)?.[1])).toBe(RISK_CEILING);
  });
});

describe('manual account form', () => {
  it('needs equity, a currency and leverage; balance and risk are optional', () => {
    expect(manualProblems(form)).toEqual([]);
    expect(
      manualProblems({ equity: '0', balance: '-1', currency: 'usd', leverage: '5000', risk: '2.5' }),
    ).toEqual(['equity', 'balance', 'currency', 'leverage', 'risk']);
  });

  it('starts from the saved profile', () => {
    expect(formOf({ source: null })).toEqual({ ...form, equity: '', leverage: '' });
    expect(
      formOf({
        source: 'MANUAL',
        engine_id: null,
        equity: 500,
        balance: 500, // saved as equity when it was left empty
        currency: 'THB',
        leverage: 100,
        risk_percent: 0.5,
        updated_at: '2026-10-05T00:00:00+00:00',
      }),
    ).toEqual({ equity: '500', balance: '', currency: 'THB', leverage: '100', risk: '0.5' });
  });
});

describe('overrides', () => {
  const ent: Entitlements = {
    plan: 'FREE',
    features: { BACKTESTS: false },
    limits: { WATCHLISTS: 2, ALERTS_PER_DAY: null },
    asset_classes: ['FOREX_MAJOR'],
    families: null,
    overrides: [],
  };

  it('starts the editor from what the user has now', () => {
    expect(overrideKind('BACKTESTS')).toBe('feature');
    expect(overrideKind('WATCHLISTS')).toBe('limit');
    expect(overrideKind('FAMILIES')).toBe('allowList');
    expect(overrideValueOf('BACKTESTS', ent)).toBe(false);
    expect(overrideValueOf('WATCHLISTS', ent)).toBe(2);
    expect(overrideValueOf('ALERTS_PER_DAY', ent)).toBeNull();
    expect(overrideValueOf('ASSET_CLASSES', ent)).toEqual(['FOREX_MAJOR']);
    expect(overrideValueOf('FAMILIES', ent)).toBeNull(); // every family, not an empty list
  });
});
