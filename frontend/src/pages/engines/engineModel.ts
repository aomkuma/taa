/** Pure helpers of the engines page (TAA-923). */
import type { EngineSummary } from '@/engine/schemas';

/** `last_seen_at` is written at most once a minute, so "connected" allows a few minutes of silence. */
export const CONNECTED_WITHIN_MS = 3 * 60_000;

export type EngineBadge = 'waiting' | 'connected' | 'offline' | 'revoked';

export function engineBadge(engine: EngineSummary, nowMs: number): EngineBadge {
  if (engine.status === 'REVOKED') return 'revoked';
  if (!engine.first_seen_at) return 'waiting';
  const seen = engine.last_seen_at ? Date.parse(engine.last_seen_at) : Number.NaN;
  return Number.isFinite(seen) && nowMs - seen <= CONNECTED_WITHIN_MS ? 'connected' : 'offline';
}

/** Days since the secret was issued (the last rotation, else the registration); null when unknown. */
export function keyAgeDays(engine: EngineSummary, nowMs: number): number | null {
  const issued = engine.rotated_at ?? engine.created_at;
  if (!issued) return null;
  return Math.max(0, Math.floor((nowMs - Date.parse(issued)) / 86_400_000));
}

export interface EnvValues {
  cloudBaseUrl?: string | undefined;
  engineId: string;
  hmacSecret?: string | undefined;
  controlTotp?: string | undefined;
}

/** The `.env` lines for the engine machine (only the values given). */
export function envBlock(values: EnvValues): string {
  const lines = [
    values.cloudBaseUrl !== undefined ? `CLOUD_BASE_URL=${values.cloudBaseUrl}` : null,
    `ENGINE_ID=${values.engineId}`,
    values.hmacSecret !== undefined ? `ENGINE_HMAC_SECRET=${values.hmacSecret}` : null,
    values.controlTotp !== undefined ? `CONTROL_TOTP_SECRET=${values.controlTotp}` : null,
  ];
  return `${lines.filter((l) => l !== null).join('\n')}\n`;
}
