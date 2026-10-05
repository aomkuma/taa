/** Responses of the System and Settings pages (TAA-803 `/status`, `/config`, `/audit/verify`; TAA-913 auth). */
import { z } from 'zod';

import { engineKey } from '@/engine/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });

/** `/status` with the fields the System page shows (the shell's schema keeps only what every page needs). */
export const SystemStatusSchema = z.object({
  engine: z.looseObject({ engine_id: z.string(), label: z.string(), status: z.string() }),
  run: z
    .looseObject({
      run_id: z.string(),
      mode: z.string(),
      status: z.string(),
      started_at: IsoDateTime,
      version: z.string().nullable().optional(),
      config_hash: z.string().nullable().optional(),
    })
    .nullable(),
  last_received_at: IsoDateTime.nullable(),
  heartbeat: z
    .looseObject({
      at: IsoDateTime,
      received_at: IsoDateTime,
      state: z.string(),
      connected: z.boolean(),
      clock_verified: z.boolean(),
      market_open: z.boolean(),
      market_change_at: IsoDateTime.nullable(),
      cycles: z.number().int(),
      outbox_pending: z.number().int().nullable().optional(),
      watch_status: z.string().optional(),
    })
    .nullable(),
  audit: z
    .looseObject({
      status: z.string(),
      verified_seq: z.number().int().nullable(),
      max_seq: z.number().int().nullable(),
      first_bad_seq: z.number().int().nullable(),
      updated_at: IsoDateTime.nullable(),
    })
    .nullable(),
});
export type SystemStatus = z.infer<typeof SystemStatusSchema>;

/** `/config`: the engine's `Settings.summary()` (secrets masked by the engine before it left the PC). */
export const MaskedConfigSchema = z.object({
  config_hash: z.string(),
  created_at: IsoDateTime,
  config: z.object({
    env: z.record(z.string(), z.unknown()),
    config: z.record(z.string(), z.unknown()),
  }),
});
export type MaskedConfig = z.infer<typeof MaskedConfigSchema>;

export const AuditVerifySchema = z.object({
  chain: z.string(),
  ok: z.boolean(),
  events_checked: z.number().int(),
  first_bad_seq: z.number().int().nullable(),
  detail: z.string(),
});

export const SessionsSchema = z.object({
  items: z.array(
    z.object({
      session_id: z.string(),
      created_at: IsoDateTime,
      last_seen_at: IsoDateTime,
      expires_at: IsoDateTime,
      ip: z.string(),
      user_agent: z.string(),
      current: z.boolean(),
    }),
  ),
});

export const EnrollmentSchema = z.object({
  secret: z.string(),
  otpauth_uri: z.string(),
  qr_svg: z.string().startsWith('data:image/svg+xml;base64,'),
});
export type Enrollment = z.infer<typeof EnrollmentSchema>;

export const ProfileSchema = z.object({ locale: z.string(), timezone: z.string() });
export const PasswordChangedSchema = z.object({ other_sessions_revoked: z.number().int() });
export const RevokedOthersSchema = z.object({ revoked: z.number().int() });

export const systemKeys = {
  status: (engineId: string) => [...engineKey(engineId), 'system', 'status'] as const,
  config: (engineId: string) => [...engineKey(engineId), 'system', 'config'] as const,
  sessions: ['me', 'sessions'] as const,
};
