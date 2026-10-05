/**
 * The control API (TAA-805; app/web/routers/control.py): commands for the user's own engine. Posting needs a fresh
 * step-up (`StepUpDialog`); POSITION_CLOSE and FLATTEN_ALL also carry the **engine's** control TOTP code, which
 * only the engine can check (the cloud never knows that secret). Risk-increasing commands do not exist here.
 */
import { z } from 'zod';

import { apiPost } from '@/api/client';

import { engineKey } from './schemas';

const IsoDateTime = z.iso.datetime({ offset: true });

/** A queued control command as `public()` in app/sync/command_queue.py shows it (never with a code). */
export const CommandSchema = z.looseObject({
  id: z.string(),
  type: z.string(),
  params: z.record(z.string(), z.unknown()),
  created_by: z.string(),
  created_at: IsoDateTime,
  expires_at: IsoDateTime,
  status: z.string(),
  delivered_at: IsoDateTime.nullable(),
  completed_at: IsoDateTime.nullable(),
  result: z.looseObject({
    outcome: z.string().nullable().optional(),
    reason: z.string().nullable().optional(),
    detail: z.string().nullable().optional(),
  }),
});
export type Command = z.infer<typeof CommandSchema>;

export const CommandsPageSchema = z.object({
  items: z.array(CommandSchema),
  next_cursor: z.string().nullable(),
});

/** The format of the engine's control code; the engine itself checks the code. */
export const ENGINE_CODE = /^\d{6}$/;

export type CommandBody =
  | { type: 'KILL_SWITCH_ACTIVATE'; reason: string }
  | { type: 'STRATEGY_DISABLE'; strategy: string; reason?: string }
  | { type: 'POSITION_CLOSE'; ticket: number; code: string }
  | { type: 'FLATTEN_ALL'; reason: string; code: string };

export function postCommand(engineId: string, body: CommandBody): Promise<Command> {
  return apiPost(`/engines/${encodeURIComponent(engineId)}/commands`, body, CommandSchema);
}

/** Queries that a command changes: its list and the views that show command states. */
export const commandKeys = {
  list: (engineId: string, status: string) => [...engineKey(engineId), 'commands', status] as const,
  all: (engineId: string) => [...engineKey(engineId), 'commands'] as const,
};
