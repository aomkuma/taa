/** Responses of the theories & conditions page (TAA-809 catalog, TAA-8A2 entitlements; TAA-920). */
import { z } from 'zod';

/** A changeable parameter: a number with both bounds, or a switch (`param_bounds` in app/web/advisory.py). */
export const BoundSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('boolean') }),
  z.object({
    type: z.enum(['integer', 'number']),
    min: z.number(),
    max: z.number(),
    min_exclusive: z.boolean(),
    max_exclusive: z.boolean(),
  }),
]);
export type Bound = z.infer<typeof BoundSchema>;

export const DetectorSchema = z.object({
  id: z.string(),
  name: z.string(),
  family: z.string(),
  tier: z.enum(['T1', 'T2', 'T3']),
  depends_on: z.array(z.string()),
  params: z.record(z.string(), z.unknown()),
  bounds: z.record(z.string(), BoundSchema),
});
export type Detector = z.infer<typeof DetectorSchema>;

/** `GET /advisory/detectors`. */
export const CatalogSchema = z.object({
  detectors: z.array(DetectorSchema),
  pattern_strategies: z.array(z.string()),
});
export type Catalog = z.infer<typeof CatalogSchema>;

/** `GET /me/entitlements`: `families` null means every family. */
export const EntitlementsSchema = z.looseObject({
  plan: z.string(),
  families: z.array(z.string()).nullable(),
  asset_classes: z.array(z.string()).nullable(),
});
export type Entitlements = z.infer<typeof EntitlementsSchema>;

export const CATALOG_QUERY_KEY = ['advisory', 'detectors'] as const;
export const ENTITLEMENTS_QUERY_KEY = ['me', 'entitlements'] as const;
