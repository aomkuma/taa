/**
 * Which engine the shell shows. A user with several ACTIVE engines of their own (PLAN §A32) picks one; the
 * choice is remembered per device. Without a usable choice the shell shows `GET /me/feed`'s engine: the user's
 * oldest ACTIVE engine, or the owner's market feed for a subscriber (TAA-8A4).
 */
import type { EngineSummary, Feed } from './schemas';

const STORAGE_KEY = 'taa.engine';

export interface Selection {
  engineId: string | null;
  /** The user's own engine (account data, controls and the live stream), not the market feed. */
  own: boolean;
}

export function activeOwnEngines(engines: readonly EngineSummary[]): EngineSummary[] {
  return engines.filter((engine) => engine.status === 'ACTIVE');
}

export function selectEngine(feed: Feed, own: readonly EngineSummary[], stored: string | null): Selection {
  if (stored !== null && own.some((engine) => engine.engine_id === stored)) {
    return { engineId: stored, own: true };
  }
  return { engineId: feed.engine_id, own: feed.own };
}

export function loadEngineChoice(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function saveEngineChoice(engineId: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, engineId);
  } catch {
    // Not remembered: the next visit shows the default engine.
  }
}
