/**
 * The symbols page's trend (owner, 2026-10-15): the market-map states the setups' screens read
 * (`GET /engines/{id}/trends`), per setup group:
 *
 * - **M15 setups** (V1, F1): the H4 tide and the H1 wave (config.yaml `strategies`, `screen_h4`/`screen_h1`).
 * - **M1 scalp** (S1, gold only): the H1 tide and the M15 wave (config.yaml `lanes: s1`, `screen_tide_tf`/
 *   `screen_wave_tf`).
 *
 * Up or down only when both screens agree, as the setups require; both ranging is sideways; anything else (a
 * transition, the two disagreeing) is unclear; a symbol without the bars has no trend.
 */
import { z } from 'zod';

import { MAP_STATES } from '@/pages/charts/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });

export const TrendsSchema = z.object({
  items: z.array(
    z.object({
      symbol: z.string(),
      server: z.string(),
      at: IsoDateTime.nullable(),
      frames: z.record(z.string(), z.object({ state: z.enum(MAP_STATES), at: IsoDateTime })),
    }),
  ),
});
export type Trends = z.infer<typeof TrendsSchema>;
export type MapState = (typeof MAP_STATES)[number];

/** Each setup group's screens, the tide first. */
export const TREND_GROUPS = {
  m15: ['H4', 'H1'],
  m1: ['H1', 'M15'],
} as const;
export type TrendGroup = keyof typeof TREND_GROUPS;
export const TREND_GROUP_NAMES = Object.keys(TREND_GROUPS) as TrendGroup[];
export const TRENDS = ['UP', 'DOWN', 'SIDEWAYS', 'UNCLEAR', 'NONE'] as const;
export type Trend = (typeof TRENDS)[number];

export function summarize(frames: Partial<Record<string, { state: MapState }>>, group: TrendGroup): Trend {
  const [tide, wave] = TREND_GROUPS[group].map((tf) => frames[tf]?.state);
  if (tide === undefined || wave === undefined) return 'NONE';
  if (tide !== wave) return 'UNCLEAR';
  return tide === 'UP' || tide === 'DOWN' ? tide : tide === 'RANGE' ? 'SIDEWAYS' : 'UNCLEAR';
}

const STORAGE_KEY = 'taa.symbols.trendGroup';

export function loadTrendGroup(): TrendGroup {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'm1' ? 'm1' : 'm15';
  } catch {
    return 'm15';
  }
}

export function saveTrendGroup(group: TrendGroup): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, group);
  } catch {
    // Not remembered: the next visit starts with the M15 setups.
  }
}
