/**
 * Engine health from its newest heartbeat (PLAN §A13 "TAA-705 decisions"). The rule matches the cloud watchdog:
 * offline means `stopped`, or no heartbeat for 60 s on the cloud clock. The browser measures the age on the
 * server clock (device time + the session's clock offset), so a wrong device clock does not flip the verdict.
 */
import type { Heartbeat } from './schemas';

export const OFFLINE_AFTER_MS = 60_000;

/**
 * - `unknown`: no heartbeat received yet
 * - `online`: running, recent heartbeat, MT5 connected
 * - `disconnected`: running and reporting, but not connected to the MT5 terminal
 * - `stopped`: deliberately stopped
 * - `silent`: no heartbeat for `OFFLINE_AFTER_MS`
 */
export type EngineHealth = 'unknown' | 'online' | 'disconnected' | 'stopped' | 'silent';

export function engineHealth(heartbeat: Heartbeat | null | undefined, serverNowMs: number): EngineHealth {
  if (!heartbeat) return 'unknown';
  if (heartbeat.state === 'stopped') return 'stopped';
  if (serverNowMs - Date.parse(heartbeat.received_at) >= OFFLINE_AFTER_MS) return 'silent';
  return heartbeat.connected ? 'online' : 'disconnected';
}
