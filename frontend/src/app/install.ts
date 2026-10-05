/**
 * The browser's install offer (`beforeinstallprompt`, Chromium; TAA-914). main.tsx listens from the start,
 * because the event fires once, early; the settings page offers "Install the app" while it is available.
 * Safari has no such event: on iOS the page explains "Add to Home Screen" instead.
 */
import { useSyncExternalStore } from 'react';

import { isIos } from '@/pages/notifications/push';

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let offer: InstallPromptEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Call once at start-up. */
export function listenForInstall(target: Window = window): void {
  target.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); // no mini-infobar: the app offers it where it explains it
    offer = event as InstallPromptEvent;
    emit();
  });
  target.addEventListener('appinstalled', () => {
    offer = null;
    installed = true;
    emit();
  });
}

/** Shows the browser's install dialog; true when the user accepted. */
export async function promptInstall(): Promise<boolean> {
  const event = offer;
  if (!event) return false;
  offer = null;
  emit();
  await event.prompt();
  return (await event.userChoice).outcome === 'accepted';
}

function standalone(): boolean {
  const nav: Navigator & { standalone?: boolean } = navigator;
  return (
    (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
    nav.standalone === true
  );
}

export type InstallState = 'installed' | 'available' | 'ios' | 'unavailable';

function state(): InstallState {
  if (installed || standalone()) return 'installed';
  if (offer) return 'available';
  return isIos(navigator) ? 'ios' : 'unavailable';
}

export function useInstallState(): InstallState {
  return useSyncExternalStore((listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, state);
}

/** Tests: forget any captured offer. */
export function resetInstall(): void {
  offer = null;
  installed = false;
  emit();
}
