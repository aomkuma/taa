/** Responses the charts page reads (TAA-803 candles/symbols/decisions, TAA-809 opportunities). */
import { z } from 'zod';

const IsoDateTime = z.iso.datetime({ offset: true });
const Value = z.number().nullable();

export const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'] as const;
export type ChartTimeframe = (typeof TIMEFRAMES)[number];

export const TIMEFRAME_SECONDS: Record<ChartTimeframe, number> = {
  M1: 60,
  M5: 300,
  M15: 900,
  M30: 1_800,
  H1: 3_600,
  H4: 14_400,
  D1: 86_400,
};

const DecisionMarker = z.looseObject({
  kind: z.literal('decision'),
  at: IsoDateTime,
  decision: z.string(),
  action: z.string(),
  strategy: z.string(),
  decision_id: z.string(),
  price: Value,
});
const EntryMarker = z.looseObject({
  kind: z.literal('entry'),
  at: IsoDateTime,
  side: z.string(),
  price: z.number(),
  ticket: z.number().int(),
  sl: Value,
  tp: Value,
});
const ExitMarker = z.looseObject({
  kind: z.literal('exit'),
  at: IsoDateTime,
  side: z.string(),
  price: Value,
  ticket: z.number().int(),
  reason: z.string().nullable(),
  net: Value,
});
export const MarkerSchema = z.discriminatedUnion('kind', [DecisionMarker, EntryMarker, ExitMarker]);
export type ChartMarker = z.infer<typeof MarkerSchema>;

export const ZoneSchema = z.object({
  low: z.number(),
  high: z.number(),
  touches: z.number().int(),
  role: z.enum(['SUPPORT', 'RESISTANCE', 'INSIDE']),
});
export type Zone = z.infer<typeof ZoneSchema>;

const Bar = z.tuple([IsoDateTime, z.number(), z.number(), z.number(), z.number(), z.number()]);

/** `GET /engines/{id}/candles`: bars are `[open_time, open, high, low, close, tick_volume]`, oldest first. */
export const CandlesSchema = z.object({
  server: z.string(),
  symbol: z.string(),
  timeframe: z.string(),
  bars: z.array(Bar),
  /** The bar still forming (live view only): drawn last, never used for indicators or decisions. */
  forming: Bar.nullable().optional(),
  overlays: z.record(z.string(), z.array(Value)),
  markers: z.array(MarkerSchema),
  zones: z.array(ZoneSchema).optional(),
});
export type Candles = z.infer<typeof CandlesSchema>;

export const MAP_STATES = ['UP', 'DOWN', 'RANGE', 'TRANSITION', 'UNKNOWN'] as const;

const MapZoneSchema = z.object({
  kind: z.enum(['DEMAND', 'SUPPLY']),
  source: z.enum(['SWING', 'BASE']),
  low: z.number(),
  high: z.number(),
  strength: z.number().int(),
  tests: z.number().int(),
  formed_at: IsoDateTime,
});
export type MapZone = z.infer<typeof MapZoneSchema>;

const TimeframeMapSchema = z.object({
  timeframe: z.string(),
  at: IsoDateTime,
  state: z.enum(MAP_STATES),
  raw_state: z.enum(MAP_STATES),
  adx: Value,
  efficiency: Value,
  atr: Value,
  close: z.number(),
  compression: z.boolean(),
  box: z
    .object({
      high: z.number(),
      low: z.number(),
      width_atr: z.number(),
      top_touches: z.number().int(),
      bottom_touches: z.number().int(),
    })
    .nullable(),
  zones: z.array(MapZoneSchema),
});
export type TimeframeMap = z.infer<typeof TimeframeMapSchema>;

/** `GET /engines/{id}/market-map`: the H4/D1 map the engine records on every signal (TAA-L809). */
export const MarketMapSchema = z.object({
  server: z.string(),
  symbol: z.string(),
  at: IsoDateTime.nullable(),
  map: z
    .object({
      near_atr: z.number(),
      room_cap_r: z.number(),
      frames: z.record(z.string(), TimeframeMapSchema),
    })
    .nullable(),
});
export type MarketMap = z.infer<typeof MarketMapSchema>;

/** `GET /engines/{id}/symbols`: the engine's symbol catalog. */
export const SymbolsSchema = z.object({
  items: z.array(
    z.looseObject({
      symbol: z.string(),
      enabled: z.boolean(),
      asset_class: z.string(),
      reason: z.string(),
      description: z.string(),
    }),
  ),
});

const KeyLevelSchema = z.object({ name: z.string(), price: z.number(), at: IsoDateTime.nullable() });

/** One technical evidence item (`Evidence.to_dict` in app/evidence/framework.py). */
export const EvidenceSchema = z.looseObject({
  evidence_id: z.string(),
  detector_id: z.string(),
  family: z.string(),
  name: z.string(),
  i18n_key: z.string(),
  timeframe: z.string(),
  direction: z.string(),
  detected_at: IsoDateTime,
  quality: z.number(),
  key_levels: z.array(KeyLevelSchema),
  invalidation: Value,
  targets: z.array(z.number()),
});
export type Evidence = z.infer<typeof EvidenceSchema>;

/** A signal document with its evidence (decisions and opportunities carry the same shape). */
const SignalSchema = z.looseObject({
  symbol: z.string(),
  timeframe: z.string(),
  action: z.string(),
  entry_price: Value.optional(),
  stop_loss: Value.optional(),
  take_profit: Value.optional(),
  evidence: z.array(
    z.looseObject({ item: z.looseObject({ evidence: EvidenceSchema }), relation: z.string() }),
  ),
});

export const SignalSourceSchema = z.looseObject({ signal: SignalSchema });
export type SignalSource = z.infer<typeof SignalSourceSchema>;
