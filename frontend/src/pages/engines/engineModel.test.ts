import { engineBadge, envBlock, keyAgeDays } from './engineModel';

const NOW = Date.parse('2026-10-05T12:00:00Z');
const engine = (over: Record<string, unknown> = {}) => ({
  engine_id: 'eng_x',
  label: 'home pc',
  status: 'ACTIVE',
  created_at: '2026-09-25T12:00:00+00:00',
  first_seen_at: '2026-09-25T13:00:00+00:00',
  last_seen_at: '2026-10-05T11:59:00+00:00',
  rotated_at: null,
  ...over,
});

describe('engine list', () => {
  it('derives the badge', () => {
    expect(engineBadge(engine(), NOW)).toBe('connected');
    expect(engineBadge(engine({ last_seen_at: '2026-10-05T11:50:00+00:00' }), NOW)).toBe('offline');
    expect(engineBadge(engine({ first_seen_at: null, last_seen_at: null }), NOW)).toBe('waiting');
    expect(engineBadge(engine({ status: 'REVOKED' }), NOW)).toBe('revoked');
  });

  it('counts the key age from the last rotation', () => {
    expect(keyAgeDays(engine(), NOW)).toBe(10);
    expect(keyAgeDays(engine({ rotated_at: '2026-10-03T12:00:00+00:00' }), NOW)).toBe(2);
  });

  it('writes the .env lines it has', () => {
    expect(
      envBlock({ cloudBaseUrl: 'https://taa.example', engineId: 'eng_x', hmacSecret: 's', controlTotp: 'T' }),
    ).toBe(
      'CLOUD_BASE_URL=https://taa.example\nENGINE_ID=eng_x\nENGINE_HMAC_SECRET=s\nCONTROL_TOTP_SECRET=T\n',
    );
    expect(envBlock({ engineId: 'eng_x', hmacSecret: 's' })).toBe('ENGINE_ID=eng_x\nENGINE_HMAC_SECRET=s\n');
  });
});
