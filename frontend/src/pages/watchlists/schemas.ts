/**
 * The advisory preferences document (`GET|PUT /advisory/preferences`, `app/advisory/preferences.py`) as far as
 * the watchlists, alert and theory settings read it (TAA-918, TAA-920). The other sections (trading profile,
 * entry plan) pass through untouched, so a PUT of the whole document keeps them.
 */
import { z } from 'zod';

/** `WatchlistKind`, `AlertMetric`, `RiskFullPolicy` (app/advisory/preferences.py; parity in the tests). */
export const WATCHLIST_KINDS = ['FAVOURITES', 'CUSTOM', 'AUTO_TOP_N'] as const;
export const ALERT_METRICS = ['WIN_PROBABILITY', 'SETUP_STRENGTH'] as const;
export const RISK_FULL_POLICIES = ['PAUSE', 'WARN'] as const;
export type WatchlistKind = (typeof WATCHLIST_KINDS)[number];
export type AlertMetric = (typeof ALERT_METRICS)[number];

/** `DEFAULT_THRESHOLDS`: the global x when the user has not set one. */
export const DEFAULT_THRESHOLD: Record<AlertMetric, number> = { WIN_PROBABILITY: 55, SETUP_STRENGTH: 75 };
/** Field bounds of the backend models. */
export const LIMITS = {
  lists: 20,
  listName: 40,
  listSymbols: 200,
  topN: [1, 60],
  lifetimeBars: [1, 20],
  windows: 14,
  alertsPerHour: [1, 60],
  cooldownMinutes: [0, 1440],
} as const;
/** An AUTO_TOP_N list without `top_n` takes this many ranks (`Watchlist.size`). */
export const DEFAULT_TOP_N = 30;
export const SYMBOL_PATTERN = /^[A-Za-z0-9#._-]{1,32}$/;

export const WatchlistSchema = z.object({
  name: z.string(),
  kind: z.enum(WATCHLIST_KINDS),
  symbols: z.array(z.string()),
  top_n: z.number().int().nullable(),
  alerts: z.boolean(),
  threshold: z.number().nullable(),
});
export type Watchlist = z.infer<typeof WatchlistSchema>;

/** `UserWindow`: start days (Monday = 0) and HH:MM times in the user's timezone; may span midnight. */
export const UserWindowSchema = z.object({
  days: z.array(z.number().int().min(0).max(6)),
  start: z.string(),
  end: z.string(),
});
export type UserWindow = z.infer<typeof UserWindowSchema>;

export const AlertPreferencesSchema = z.object({
  metric: z.enum(ALERT_METRICS),
  threshold: z.number().nullable(),
  signal_lifetime_bars: z.number().int(),
  respect_market_sessions: z.boolean(),
  timezone: z.string(),
  windows: z.array(UserWindowSchema),
  rate_limits: z.object({
    max_alerts_per_hour: z.number().int(),
    symbol_cooldown_minutes: z.number().int(),
  }),
  expiry_updates: z.boolean(),
  when_risk_full: z.enum(RISK_FULL_POLICIES),
  language: z.enum(['th', 'en']),
});
export type AlertPreferences = z.infer<typeof AlertPreferencesSchema>;

/** `ConflictPolicy` (app/advisory/preferences.py). */
export const CONFLICT_POLICIES = ['IGNORE', 'PENALIZE', 'BLOCK'] as const;

/** `TheoryPreferences`: a preset (null: custom) with family and detector overrides on top (TAA-920). */
export const TheoriesSchema = z.object({
  preset: z.string().nullable(),
  families: z.record(z.string(), z.boolean()),
  detectors: z.record(z.string(), z.boolean()),
  params: z.record(z.string(), z.record(z.string(), z.unknown())),
  pattern_strategies: z.record(z.string(), z.boolean()),
  min_supporting_families: z.number().int(),
  conflict_policy: z.enum(CONFLICT_POLICIES),
});
export type Theories = z.infer<typeof TheoriesSchema>;

export const PreferencesSchema = z.looseObject({
  watchlists: z.array(WatchlistSchema),
  alerts: AlertPreferencesSchema,
  theories: TheoriesSchema,
});
export type Preferences = z.infer<typeof PreferencesSchema>;

/** `POST /advisory/watchlists`, `PUT /advisory/watchlists/{name}`. */
export const WatchlistsSchema = z.object({ watchlists: z.array(WatchlistSchema) });

/** `POST /advisory/favourites/{symbol}` (a toggle). */
export const FavouriteToggleSchema = z.object({
  symbol: z.string(),
  favourite: z.boolean(),
  favourites: z.array(z.string()),
});

export const PREFERENCES_QUERY_KEY = ['advisory', 'preferences'] as const;
