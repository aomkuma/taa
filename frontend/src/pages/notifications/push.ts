/**
 * Web Push on this device (PLAN §A14 "Web Push", R17): support, subscribe and unsubscribe.
 *
 * iOS delivers push only to a PWA added to the Home Screen (16.4+), and every browser asks for permission
 * only from a user gesture, so `enablePush` calls `Notification.requestPermission()` before anything else.
 */

export type PushSupport = 'supported' | 'ios-install' | 'unsupported';

export class PushSetupError extends Error {
  constructor(readonly reason: 'denied' | 'no-worker') {
    super(reason);
    this.name = 'PushSetupError';
  }
}

interface NavigatorEnv {
  userAgent: string;
  maxTouchPoints: number;
}

export function isIos(nav: NavigatorEnv): boolean {
  // iPadOS 13+ reports itself as a Mac: tell it apart by its touch screen
  return (
    /iPad|iPhone|iPod/.test(nav.userAgent) || (/Macintosh/.test(nav.userAgent) && nav.maxTouchPoints > 1)
  );
}

export function pushSupport(): PushSupport {
  const nav: Navigator & { standalone?: boolean } = navigator;
  const standalone =
    (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
    nav.standalone === true;
  if (isIos(nav) && !standalone) return 'ios-install';
  if (!('serviceWorker' in nav) || !('PushManager' in window) || !('Notification' in window))
    return 'unsupported';
  return 'supported';
}

/** The VAPID public key (base64url) as the bytes `PushManager.subscribe` wants. */
export function applicationServerKey(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url + '='.repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

const BROWSERS: readonly [RegExp, string][] = [
  [/Edg\//, 'Edge'],
  [/SamsungBrowser/, 'Samsung Internet'],
  [/Firefox\//, 'Firefox'],
  [/Chrome\//, 'Chrome'],
  [/Safari\//, 'Safari'],
];
const SYSTEMS: readonly [RegExp, string][] = [
  [/Windows/, 'Windows'],
  [/Android/, 'Android'],
  [/iPhone|iPad|iPod/, 'iOS'],
  [/Mac OS X|Macintosh/, 'macOS'],
  [/Linux/, 'Linux'],
];

/** A short device name for the devices list, e.g. "Edge · Windows". */
export function deviceLabel(userAgent: string): string {
  const browser = BROWSERS.find(([re]) => re.test(userAgent))?.[1] ?? 'Browser';
  const system = SYSTEMS.find(([re]) => re.test(userAgent))?.[1];
  return system ? `${browser} · ${system}` : browser;
}

async function pushManager(): Promise<PushManager | null> {
  // getRegistration, not `ready`: `ready` never settles where no worker is registered (the dev server)
  const reg = await navigator.serviceWorker.getRegistration();
  return reg?.pushManager ?? null;
}

/** This browser's current subscription endpoint, or null. */
export async function currentEndpoint(): Promise<string | null> {
  const manager = await pushManager();
  const sub = manager ? await manager.getSubscription() : null;
  return sub?.endpoint ?? null;
}

export interface SubscriptionBody {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  label: string;
}

/** Ask for permission (call it first inside the click handler), then subscribe this browser. */
export async function enablePush(publicKey: string): Promise<SubscriptionBody> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new PushSetupError('denied');
  const manager = await pushManager();
  if (!manager) throw new PushSetupError('no-worker');
  const sub = await manager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: applicationServerKey(publicKey),
  });
  const keys = sub.toJSON().keys ?? {};
  return {
    endpoint: sub.endpoint,
    keys: { p256dh: keys.p256dh ?? '', auth: keys.auth ?? '' },
    label: deviceLabel(navigator.userAgent),
  };
}

/** Unsubscribe this browser; returns the endpoint the server should forget (null if there was none). */
export async function disablePush(): Promise<string | null> {
  const manager = await pushManager();
  const sub = manager ? await manager.getSubscription() : null;
  if (!sub) return null;
  await sub.unsubscribe();
  return sub.endpoint;
}
