import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApiError, apiGet, apiPost, apiPostEmpty, apiPut } from '@/api/client';
import { translateCode } from '@/i18n/codes';
import { translateDynamic } from '@/i18n/dynamic';
import { useFormat } from '@/i18n/useFormat';
import { useLiveEvents } from '@/live/context';
import { Card } from '@/pages/dashboard/cards';
import { NOTIFICATIONS_QUERY_KEY } from '@/pages/dashboard/schemas';

import { AlertSettingsCard } from './AlertSettings';
import { describe, type NotificationText } from './notificationModel';
import { currentEndpoint, disablePush, enablePush, PushSetupError, pushSupport } from './push';
import {
  DevicesSchema,
  type NotificationItem,
  NotificationListSchema,
  notificationKeys,
  PreferencesSchema,
  PushKeySchema,
  ReadAllSchema,
  SubscribedSchema,
  TestQueuedSchema,
} from './schemas';

const PAGE = 20;
const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const SEVERITY: Record<string, string> = {
  CRITICAL: 'text-red-700 dark:text-red-400',
  WARNING: 'text-amber-700 dark:text-amber-400',
};
const PUSH_QUERIES = ['me', 'push'] as const;

function Loading({ error }: { error: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-500">{error ? t('dashboard.loadFailed') : t('dashboard.loading')}</p>
  );
}

/** A backend code through its translation key when one exists, else the raw code. */
function useCodeText() {
  const { i18n } = useTranslation();
  return (key: string, raw: string) => (i18n.exists(key) ? translateDynamic(i18n, key) : raw);
}

function Text({ text }: { text: NotificationText }) {
  const { i18n } = useTranslation();
  const code = useCodeText();
  if (text.kind === 'none') return null;
  if (text.kind === 'text') {
    return (
      <p className="text-sm whitespace-pre-line text-slate-700 dark:text-slate-300">
        <span className="font-medium">{text.title}</span>
        {text.body && `\n${text.body}`}
      </p>
    );
  }
  const values: Record<string, string> = { ...text.values };
  if (text.reason !== undefined) values.reason = code(`notifications.reason.${text.reason}`, text.reason);
  if (text.status !== undefined) values.status = code(`notifications.status.${text.status}`, text.status);
  return (
    <p className="text-sm text-slate-700 dark:text-slate-300">
      {translateDynamic(i18n, `notifications.text.${text.key}`, values)}
    </p>
  );
}

// --- push on this device ------------------------------------------------------------------------------------

function PushMessage({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (error instanceof PushSetupError) {
    return (
      <>{error.reason === 'denied' ? t('notifications.push.denied') : t('notifications.push.noWorker')}</>
    );
  }
  if (error instanceof ApiError && error.code === 'push_subscription_limit') {
    return <>{t('notifications.push.limit')}</>;
  }
  return <>{t('notifications.push.failed')}</>;
}

function IosGuide() {
  const { t } = useTranslation();
  return (
    <div className="space-y-1 text-sm">
      <p>{t('notifications.push.ios.intro')}</p>
      <ol className="list-decimal space-y-0.5 pl-5">
        <li>{t('notifications.push.ios.share')}</li>
        <li>{t('notifications.push.ios.add')}</li>
        <li>{t('notifications.push.ios.open')}</li>
      </ol>
    </div>
  );
}

function PushCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [support] = useState(pushSupport);
  const [done, setDone] = useState<string | null>(null);
  const key = useQuery({
    queryKey: notificationKeys.pushKey,
    queryFn: ({ signal }) => apiGet('/push/key', PushKeySchema, { signal }),
    retry: false,
    enabled: support === 'supported',
  });
  const endpoint = useQuery({
    queryKey: [...PUSH_QUERIES, 'endpoint'],
    queryFn: currentEndpoint,
    enabled: support === 'supported',
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: PUSH_QUERIES });

  const enable = useMutation({
    mutationFn: async (publicKey: string) => {
      const body = await enablePush(publicKey);
      await apiPost('/push/subscribe', body, SubscribedSchema);
    },
    onSuccess: async () => {
      setDone(t('notifications.push.enabled'));
      await refresh();
    },
  });
  const disable = useMutation({
    mutationFn: async () => {
      const gone = await disablePush();
      if (gone) await apiPostEmpty('/push/unsubscribe', { endpoint: gone });
    },
    onSuccess: async () => {
      setDone(t('notifications.push.disabled'));
      await refresh();
    },
  });
  const test = useMutation({
    mutationFn: () => apiPost('/push/test', {}, TestQueuedSchema),
    onSuccess: () => {
      setDone(t('notifications.push.testQueued'));
    },
  });
  const reset = () => {
    setDone(null);
    enable.reset();
    disable.reset();
    test.reset();
  };
  const failure = enable.error ?? disable.error ?? test.error;

  let body;
  if (support === 'ios-install') {
    body = <IosGuide />;
  } else if (support === 'unsupported') {
    body = <p className="text-sm">{t('notifications.push.unsupported')}</p>;
  } else if (key.error instanceof ApiError && key.error.code === 'push_not_configured') {
    body = <p className="text-sm">{t('notifications.push.notConfigured')}</p>;
  } else if (key.data === undefined || endpoint.data === undefined) {
    body = <Loading error={key.isError || endpoint.isError} />;
  } else {
    const publicKey = key.data.public_key;
    const on = endpoint.data !== null;
    const busy = enable.isPending || disable.isPending;
    body = (
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm">{on ? t('notifications.push.on') : t('notifications.push.off')}</span>
        {on ? (
          <button
            type="button"
            className={BUTTON}
            disabled={busy}
            onClick={() => {
              reset();
              disable.mutate();
            }}
          >
            {t('notifications.push.disable')}
          </button>
        ) : (
          <button
            type="button"
            className={PRIMARY}
            disabled={busy}
            onClick={() => {
              reset();
              // enablePush asks for permission first, still inside this click (iOS needs the gesture)
              enable.mutate(publicKey);
            }}
          >
            {t('notifications.push.enable')}
          </button>
        )}
        <button
          type="button"
          className={BUTTON}
          disabled={test.isPending}
          onClick={() => {
            reset();
            test.mutate();
          }}
        >
          {t('notifications.push.test')}
        </button>
      </div>
    );
  }
  return (
    <Card title={t('notifications.push.title')}>
      {body}
      {failure ? (
        <p role="alert" className="mt-2 text-sm text-red-700 dark:text-red-400">
          <PushMessage error={failure} />
        </p>
      ) : (
        done !== null && (
          <p role="status" className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            {done}
          </p>
        )
      )}
    </Card>
  );
}

function DevicesCard() {
  const { t } = useTranslation();
  const format = useFormat();
  const devices = useQuery({
    queryKey: notificationKeys.devices,
    queryFn: ({ signal }) => apiGet('/push/subscriptions', DevicesSchema, { signal }),
  });
  return (
    <Card title={t('notifications.devices.title')}>
      {devices.data === undefined ? (
        <Loading error={devices.isError} />
      ) : devices.data.items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('notifications.devices.none')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
          {devices.data.items.map((d) => (
            <li key={d.subscription_id} className="flex flex-wrap justify-between gap-x-3 py-1.5">
              <span>
                <span className="font-medium">{d.label || d.service || '—'}</span>{' '}
                <span className={d.active ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500'}>
                  {d.active ? t('notifications.devices.active') : t('notifications.devices.inactive')}
                </span>
              </span>
              <span className="text-slate-500">
                {t('notifications.devices.lastSuccess', {
                  at: d.last_success_at
                    ? format.dateTime(d.last_success_at)
                    : t('notifications.devices.never'),
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function PreferencesCard() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const prefs = useQuery({
    queryKey: notificationKeys.preferences,
    queryFn: ({ signal }) => apiGet('/notifications/preferences', PreferencesSchema, { signal }),
  });
  const save = useMutation({
    mutationFn: (disabled: string[]) => apiPut('/notifications/preferences', { disabled }, PreferencesSchema),
    onSuccess: (data) => {
      queryClient.setQueryData(notificationKeys.preferences, data);
    },
  });
  return (
    <Card title={t('notifications.prefs.title')}>
      {prefs.data === undefined ? (
        <Loading error={prefs.isError} />
      ) : (
        <>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="sr-only">{t('notifications.prefs.title')}</legend>
            {prefs.data.types.map((type) => {
              const off = prefs.data.disabled;
              return (
                <label key={type} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!off.includes(type)}
                    disabled={save.isPending}
                    onChange={(event) => {
                      save.mutate(event.target.checked ? off.filter((d) => d !== type) : [...off, type]);
                    }}
                  />
                  {translateCode(i18n, 'notificationType', type)}
                </label>
              );
            })}
          </fieldset>
          <p className="mt-2 text-xs text-slate-500">{t('notifications.prefs.note')}</p>
          {save.isError && (
            <p role="alert" className="mt-1 text-sm text-red-700 dark:text-red-400">
              {t('notifications.push.failed')}
            </p>
          )}
        </>
      )}
    </Card>
  );
}

// --- notification centre ------------------------------------------------------------------------------------

function Entry({ item, onRead }: { item: NotificationItem; onRead: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const view = describe(item);
  const unread = item.read_at === null;
  const read = () => {
    if (unread) onRead(item.notification_id);
  };
  return (
    <li className={`py-2 ${unread ? '' : 'opacity-75'}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className={`text-sm ${unread ? 'font-semibold' : ''} ${SEVERITY[item.severity] ?? ''}`}>
          {unread && <span className="sr-only">{t('notifications.centre.unreadMark')} </span>}
          {translateCode(i18n, 'notificationType', item.type)}
        </span>
        <span className="text-xs text-slate-500">{format.dateTime(item.created_at)}</span>
      </div>
      <Text text={view.text} />
      <div className="mt-1 flex gap-3 text-sm">
        {view.link !== null && (
          <Link to={view.link} className="underline" onClick={read}>
            {t('notifications.centre.open')}
          </Link>
        )}
        {unread && (
          <button type="button" className="underline" onClick={read}>
            {t('notifications.centre.markRead')}
          </button>
        )}
      </div>
    </li>
  );
}

function CentreCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const list = useInfiniteQuery({
    queryKey: notificationKeys.list(unreadOnly),
    queryFn: ({ pageParam, signal }) => {
      const query = new URLSearchParams({ limit: String(PAGE) });
      if (unreadOnly) query.set('unread', 'true');
      if (pageParam) query.set('cursor', pageParam);
      return apiGet(`/notifications?${query.toString()}`, NotificationListSchema, { signal });
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEY });
  const readOne = useMutation({
    mutationFn: (id: string) => apiPostEmpty(`/notifications/${encodeURIComponent(id)}/read`),
    onSettled: refresh,
  });
  const readAll = useMutation({
    mutationFn: () => apiPost('/notifications/read-all', {}, ReadAllSchema),
    onSettled: refresh,
  });
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const tab = (only: boolean, label: string) => (
    <button
      type="button"
      aria-pressed={unreadOnly === only}
      className={`rounded px-2 py-0.5 text-sm ${unreadOnly === only ? 'bg-slate-200 font-medium dark:bg-slate-700' : ''}`}
      onClick={() => {
        setUnreadOnly(only);
      }}
    >
      {label}
    </button>
  );
  return (
    <Card
      title={t('notifications.centre.title')}
      action={
        <button
          type="button"
          className="text-sm underline disabled:opacity-50"
          disabled={readAll.isPending || items.every((n) => n.read_at !== null)}
          onClick={() => {
            readAll.mutate();
          }}
        >
          {t('notifications.centre.markAllRead')}
        </button>
      }
    >
      <div className="mb-2 flex gap-1">
        {tab(false, t('notifications.centre.all'))}
        {tab(true, t('notifications.centre.unread'))}
      </div>
      {list.data === undefined ? (
        <Loading error={list.isError} />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">
          {unreadOnly ? t('notifications.centre.noneUnread') : t('notifications.centre.none')}
        </p>
      ) : (
        <>
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {items.map((item) => (
              <Entry
                key={item.notification_id}
                item={item}
                onRead={(id) => {
                  readOne.mutate(id);
                }}
              />
            ))}
          </ul>
          {list.hasNextPage && (
            <button
              type="button"
              className={`${BUTTON} mt-2`}
              disabled={list.isFetchingNextPage}
              onClick={() => {
                void list.fetchNextPage();
              }}
            >
              {t('notifications.centre.more')}
            </button>
          )}
        </>
      )}
    </Card>
  );
}

/**
 * PLAN §A15 Notifications (TAA-912): the centre, push on this device, devices and per-type preferences; the
 * opportunity alert settings of §A28 (TAA-918).
 */
export function NotificationsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  useLiveEvents('notifications', () => {
    void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: notificationKeys.devices });
  });
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">{t('nav.notifications')}</h1>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <CentreCard />
          <AlertSettingsCard />
        </div>
        <div className="flex flex-col gap-4">
          <PushCard />
          <PreferencesCard />
          <DevicesCard />
        </div>
      </div>
    </section>
  );
}
