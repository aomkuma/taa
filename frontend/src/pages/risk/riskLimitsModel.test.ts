import limitsPy from '../../../../app/risk/limits.py?raw';
import preferencesPy from '../../../../app/advisory/preferences.py?raw';
import heartbeatPy from '../../../../app/sync/heartbeat.py?raw';
import { GOVERNED_FIELDS, type RiskLimits } from '@/engine/schemas';

import { limitRows, PROFILE_FIELD, profilePending, riskOrigin } from './riskLimitsModel';

const base = {
  risk_per_trade_percent: 3,
  total_open_risk_percent: 6,
  max_open_positions: 3,
  max_daily_loss_percent: 6,
  min_risk_reward: 1.5,
};
const LIMITS: RiskLimits = {
  source: 'cloud',
  version: 'v1',
  age_seconds: 120,
  cage: base,
  profile: { ...base, risk_per_trade_percent: 1.5, max_open_positions: 5 },
  effective: { ...base, risk_per_trade_percent: 1.5 },
};

describe('engine risk limits', () => {
  it('follows the Python field names', () => {
    const governed = /def governed[\s\S]*?return \{([\s\S]*?)\n {4}\}/.exec(limitsPy)?.[1] ?? '';
    expect([...governed.matchAll(/"(\w+)":/g)].map((m) => m[1])).toEqual([...GOVERNED_FIELDS]);
    const wire = /class GovernedLimits[\s\S]*?\n\n\n/.exec(heartbeatPy)?.[0] ?? '';
    expect([...wire.matchAll(/^ {4}(\w+): /gm)].map((m) => m[1]).filter((n) => n !== 'model_config')).toEqual(
      [...GOVERNED_FIELDS],
    );
    const mapping = /def limits\(self\) -> ProfileLimits:[\s\S]*?\)\n/.exec(preferencesPy)?.[0] ?? '';
    for (const field of GOVERNED_FIELDS) {
      expect(mapping).toContain(`${field}=self.${PROFILE_FIELD[field]}`);
    }
  });

  it('marks the values the engine machine limits', () => {
    const rows = limitRows(LIMITS);
    expect(rows.find((r) => r.field === 'risk_per_trade_percent')?.clamped).toBe(false);
    expect(rows.find((r) => r.field === 'max_open_positions')).toMatchObject({ effective: 3, clamped: true });
  });

  it('knows when the engine has not picked up the saved profile yet', () => {
    const saved = {
      risk_per_signal_percent: 1.5,
      portfolio_heat_percent: 6,
      max_positions: 5,
      max_daily_loss_percent: 6,
      min_rr: 1.5,
    };
    expect(profilePending(LIMITS, saved)).toBe(false);
    expect(profilePending(LIMITS, { ...saved, risk_per_signal_percent: 2 })).toBe(true);
  });

  it('reads the origin of a decision record', () => {
    expect(riskOrigin('cloud:abc')).toBe('cloud');
    expect(riskOrigin('local:abc')).toBe('local');
    expect(riskOrigin(null)).toBeNull();
    expect(riskOrigin('other:x')).toBeNull();
  });
});
