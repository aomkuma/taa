/** Responses of the notifications page (TAA-806 API, app/web/routers/notifications.py). */
import { z } from 'zod';

import { NOTIFICATIONS_QUERY_KEY } from '@/pages/dashboard/schemas';

const IsoDateTime = z.iso.datetime({ offset: true });

export const NotificationItemSchema = z.object({
  notification_id: z.string(),
  engine_id: z.string().nullable(),
  type: z.string(),
  severity: z.string(),
  payload: z.record(z.string(), z.unknown()),
  created_at: IsoDateTime,
  read_at: IsoDateTime.nullable(),
  push_status: z.string().nullable(),
});
export type NotificationItem = z.infer<typeof NotificationItemSchema>;

export const NotificationListSchema = z.object({
  items: z.array(NotificationItemSchema),
  next_cursor: z.string().nullable(),
});

export const PushKeySchema = z.object({ public_key: z.string() });

export const DevicesSchema = z.object({
  items: z.array(
    z.object({
      subscription_id: z.string(),
      service: z.string().nullable(),
      label: z.string(),
      created_at: IsoDateTime,
      last_success_at: IsoDateTime.nullable(),
      active: z.boolean(),
    }),
  ),
});
export type Device = z.infer<typeof DevicesSchema>['items'][number];

export const PreferencesSchema = z.object({ types: z.array(z.string()), disabled: z.array(z.string()) });
export const SubscribedSchema = z.object({ subscription_id: z.string() });
export const TestQueuedSchema = z.object({ notification_id: z.string() });
export const ReadAllSchema = z.object({ updated: z.number().int() });

export const notificationKeys = {
  /** Under the dashboard's key, so a live `notifications` event refreshes both. */
  list: (unread: boolean) => [...NOTIFICATIONS_QUERY_KEY, 'centre', unread] as const,
  pushKey: ['me', 'push', 'key'] as const,
  devices: ['me', 'push', 'devices'] as const,
  preferences: ['me', 'notification-preferences'] as const,
};
