/** Responses of the account, plan and user-administration pages (TAA-8A1–8A3, 8A5; TAA-921). */
import { z } from 'zod';

const IsoDateTime = z.iso.datetime({ offset: true });

/** `Feature`, `Limit` (app/web/entitlements.py; parity in the tests). */
export const FEATURES = ['BACKTESTS', 'AI_NARRATIVES', 'DATA_EXPORT', 'API_ACCESS'] as const;
export const LIMITS = [
  'ALERTS_PER_DAY',
  'WATCHLISTS',
  'WATCHLIST_SYMBOLS',
  'BACKTESTS_PER_MONTH',
  'SHADOW_HISTORY_DAYS',
] as const;
/** Allow-list override keys (`ASSET_CLASSES_KEY`, `FAMILIES_KEY`). */
export const ALLOW_LISTS = ['ASSET_CLASSES', 'FAMILIES'] as const;
/** `CEILING_RISK_PER_TRADE_PCT` (app/config.py): the most a profile may risk per trade. */
export const RISK_CEILING = 2.0;

/** `GET|PUT /me/account-profile`: `source` null before the user set one. */
export const AccountProfileSchema = z.union([
  z.object({ source: z.null() }),
  z.object({
    source: z.enum(['LINKED_ENGINE', 'MANUAL']),
    engine_id: z.string().nullable(),
    equity: z.number().nullable(),
    balance: z.number().nullable(),
    currency: z.string(),
    leverage: z.number().nullable(),
    risk_percent: z.number().nullable(),
    updated_at: IsoDateTime,
  }),
]);
export type AccountProfile = z.infer<typeof AccountProfileSchema>;

/** Resolved entitlements (`Entitlements.to_dict`): null limits and allow-lists mean "no limit". */
export const EntitlementsSchema = z.object({
  plan: z.string(),
  features: z.record(z.string(), z.boolean()),
  limits: z.record(z.string(), z.number().int().nullable()),
  asset_classes: z.array(z.string()).nullable(),
  families: z.array(z.string()).nullable(),
  /** Keys an override changed. */
  overrides: z.array(z.string()),
});
export type Entitlements = z.infer<typeof EntitlementsSchema>;

/** `GET /me/entitlements`: plus this period's usage per limit. */
export const MyEntitlementsSchema = EntitlementsSchema.extend({
  usage: z.record(z.string(), z.number().int()),
});
export type MyEntitlements = z.infer<typeof MyEntitlementsSchema>;

export const OverrideRowSchema = z.object({
  key: z.string(),
  value: z.union([z.boolean(), z.number(), z.array(z.string()), z.null()]),
  reason: z.string(),
  created_by: z.string(),
  created_at: IsoDateTime,
});
export type OverrideRow = z.infer<typeof OverrideRowSchema>;

/** `GET /admin/users/{id}/entitlements`. */
export const UserEntitlementsSchema = EntitlementsSchema.extend({
  override_rows: z.array(OverrideRowSchema),
});
export type UserEntitlements = z.infer<typeof UserEntitlementsSchema>;

export const AdminUsersSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      username: z.string(),
      role: z.string(),
      disabled: z.boolean(),
      created_at: IsoDateTime,
      plan: z.string(),
    }),
  ),
});
export type AdminUser = z.infer<typeof AdminUsersSchema>['items'][number];

export const PlansSchema = z.object({
  items: z.array(
    z.looseObject({
      code: z.string(),
      name_th: z.string(),
      name_en: z.string(),
      active: z.boolean().optional(),
      spec: z.looseObject({}),
    }),
  ),
});
export type Plan = z.infer<typeof PlansSchema>['items'][number];

export const accountKeys = {
  profile: ['me', 'account-profile'] as const,
  entitlements: ['me', 'entitlements'] as const,
  billingPlans: ['billing', 'plans'] as const,
  users: ['admin', 'users'] as const,
  plans: ['admin', 'plans'] as const,
  user: (id: string) => ['admin', 'users', id] as const,
};
