import samples from '@/test/fixtures/api-samples.json';
import { AccountSnapshotSchema } from '@/engine/schemas';

import { controlsOf, measuredLimits, sortBreakers } from './riskModel';
import { EngineConfigSchema } from './schemas';

const recorded = samples as Record<string, Record<string, unknown>>;
const config = EngineConfigSchema.parse(recorded['engines/ENGINE/config']);
const status = recorded['engines/ENGINE/status'] as { heartbeat: { account: unknown } };
const account = AccountSnapshotSchema.parse(status.heartbeat.account);

describe('limits against current values', () => {
  it('measures each limit from the heartbeat; a gain uses none of a loss limit', () => {
    const rows = measuredLimits({ ...account, week_pnl_percent: 1.5 }, 2, config.config.config?.risk);
    expect(rows.map((r) => [r.key, r.used, r.limit, r.level])).toEqual([
      ['daily', 0.1, 2, 'ok'],
      ['weekly', 0, 4, 'ok'],
      ['drawdown', 0.1, 10, 'ok'],
      ['heat', 0.2, 1.5, 'ok'],
      ['losses', 1, 4, 'ok'],
      ['positions', 2, 3, 'warn'],
    ]);
  });

  it('marks the levels and leaves unmeasured values unknown', () => {
    const rows = measuredLimits(
      { ...account, day_pnl_percent: -1.7, drawdown_percent: null, consecutive_losses: 4 },
      null,
      undefined,
    );
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));
    expect(byKey.daily?.level).toBe('danger');
    expect(byKey.drawdown).toMatchObject({ used: null, level: 'unknown' });
    expect(byKey.losses?.level).toBe('breached');
    expect(byKey.positions).toMatchObject({ used: null, limit: null, level: 'unknown' });
    expect(measuredLimits(null, null, undefined).every((r) => r.level === 'unknown')).toBe(true);
  });
});

describe('controls', () => {
  it('reads flatten permission and the control code from the masked config', () => {
    expect(controlsOf(config)).toEqual({ flattenAllowed: true, engineCode: true });
    const env = { ...config.config.env, KILL_SWITCH_FLATTEN_ALLOWED: false, CONTROL_TOTP_SECRET: null };
    expect(controlsOf({ ...config, config: { ...config.config, env } })).toEqual({
      flattenAllowed: false,
      engineCode: false,
    });
    expect(controlsOf(undefined)).toEqual({ flattenAllowed: false, engineCode: false });
  });

  it('lists tripped breakers first', () => {
    const rows = [
      { name: 'SPREAD', scope_key: 'EURUSD', state: 'CLOSED' },
      { name: 'DAILY_LOSS', scope_key: '', state: 'HALF_OPEN' },
      { name: 'CLOCK', scope_key: '', state: 'OPEN' },
      { name: 'CLOCK', scope_key: '', state: 'CLOSED' },
    ];
    expect(sortBreakers(rows).map((r) => `${r.name}:${r.state}`)).toEqual([
      'CLOCK:OPEN',
      'DAILY_LOSS:HALF_OPEN',
      'CLOCK:CLOSED',
      'SPREAD:CLOSED',
    ]);
  });
});
