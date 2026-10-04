import { Outlet } from 'react-router';

import { EngineProvider } from '@/engine/EngineProvider';
import type { EventSourceFactory } from '@/live/stream';
import { LiveProvider } from '@/live/LiveProvider';

import { EngineBar } from './EngineBar';
import { ModeBanner } from './ModeBanner';
import { BottomNav, SideNav } from './Navigation';
import { OfflineBanner } from './OfflineBanner';

/** The signed-in frame (PLAN §A15): banners, navigation, engine bar and the live stream around every page. */
export function AppShell({ createEventSource }: { createEventSource?: EventSourceFactory }) {
  return (
    <EngineProvider>
      <LiveProvider {...(createEventSource ? { createEventSource } : {})}>
        <ModeBanner />
        <OfflineBanner />
        <div className="mx-auto flex max-w-7xl">
          <SideNav />
          <main className="min-w-0 flex-1 px-4 pt-4 pb-24 md:pb-8">
            <EngineBar />
            <Outlet />
          </main>
        </div>
        <BottomNav />
      </LiveProvider>
    </EngineProvider>
  );
}
