/**
 * The PWA service worker (vite-plugin-pwa `injectManifest`; PLAN §A15, TAA-912).
 *
 * - Caching rules (TAA-914): the built app shell (JS, CSS, HTML, icons, fonts) is precached and replaced as a
 *   whole on each release; navigations get the precached `index.html`, except `/api/`. Nothing else is
 *   cached: API responses (account data, issued secrets) always go to the network.
 * - Updates: a new version waits until the page sends SKIP_WAITING (the "new version" banner).
 * - Web Push: shows the worker's message (app/worker/push.py), sets the app icon badge where supported
 *   (R25), and a click focuses an open TAA window on the message's in-app link, or opens one.
 */
/// <reference lib="webworker" />
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

import { parsePushMessage, safePath } from '../app/pushMessage';

declare const self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(new NavigationRoute(createHandlerBoundToURL('index.html'), { denylist: [/^\/api\//] }));

self.addEventListener('message', (event) => {
  const data: unknown = event.data;
  if (typeof data === 'object' && data !== null && (data as { type?: unknown }).type === 'SKIP_WAITING') {
    void self.skipWaiting();
  }
});

function readPush(event: PushEvent): unknown {
  try {
    return event.data?.json();
  } catch {
    return null; // not JSON: nothing we sent
  }
}

self.addEventListener('push', (event) => {
  const message = parsePushMessage(readPush(event));
  if (!message) return;
  event.waitUntil(
    (async () => {
      if (message.badge !== null && 'setAppBadge' in navigator) {
        await navigator.setAppBadge(message.badge).catch(() => undefined);
      }
      // `renotify` is not in TypeScript's NotificationOptions yet; browsers that know it use it
      const options: NotificationOptions & { renotify?: boolean } = {
        body: message.body,
        icon: '/icons/icon-192.png',
        data: { url: message.url },
        silent: message.silent,
        ...(message.tag ? { tag: message.tag, renotify: message.renotify } : {}),
      };
      await self.registration.showNotification(message.title, options);
    })(),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const data: unknown = event.notification.data;
  const path = safePath(typeof data === 'object' && data !== null ? (data as { url?: unknown }).url : null);
  const target = new URL(path, self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const open = windows.find((w) => new URL(w.url).origin === self.location.origin);
      if (open) {
        const focused = await open.focus();
        try {
          await focused.navigate(target);
          return;
        } catch {
          // an uncontrolled window cannot be navigated from here: open a new one instead
        }
      }
      await self.clients.openWindow(target);
    })(),
  );
});
