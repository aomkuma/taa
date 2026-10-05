import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation } from 'react-router';

import { useAuthState } from '@/auth/hooks';
import { useEngine } from '@/engine/context';

import { ADMIN_ROLES, bottomBarItems, href, NAV_GROUPS, type NavId, type NavItem, visibleItems } from './nav';

/** Whether the signed-in user may see the user administration. */
function useIsAdmin(): boolean {
  const { data } = useAuthState();
  return data?.status === 'signed_in' && ADMIN_ROLES.includes(data.session.user.role);
}

const ICON_PATHS: Partial<Record<NavId | 'more', string>> = {
  dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  opportunities: 'M13 3 5 14h6l-1 7 8-11h-6z',
  positions: 'M4 7h16v12H4zM9 7V5h6v2M4 12h16',
  notifications: 'M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20h4',
  ranking: 'M5 20V10M12 20V4M19 20v-7',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
};

function NavIcon({ id }: { id: NavId | 'more' }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={id === 'more' ? 3 : 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={ICON_PATHS[id] ?? ICON_PATHS.dashboard} />
    </svg>
  );
}

const LINK = 'block rounded px-3 py-2 text-sm';
const LINK_ACTIVE = `${LINK} bg-slate-900 font-semibold text-white dark:bg-slate-100 dark:text-slate-900`;
const LINK_IDLE = `${LINK} text-slate-700 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800`;

function GroupedLinks({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const { t } = useTranslation();
  return (
    <>
      {NAV_GROUPS.map((group) => {
        const inGroup = items.filter((navItem) => navItem.group === group);
        if (inGroup.length === 0) return null;
        return (
          <div key={group} className="mb-3">
            <p className="px-3 pb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
              {t(`nav.group.${group}`)}
            </p>
            <ul>
              {inGroup.map((navItem) => (
                <li key={navItem.id}>
                  <NavLink
                    to={href(navItem)}
                    end={navItem.path === ''}
                    className={({ isActive }) => (isActive ? LINK_ACTIVE : LINK_IDLE)}
                    {...(onNavigate ? { onClick: onNavigate } : {})}
                  >
                    {t(`nav.${navItem.id}`)}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </>
  );
}

/** Sidebar on tablets and desktops. */
export function SideNav() {
  const { t } = useTranslation();
  const { own } = useEngine();
  const admin = useIsAdmin();
  return (
    <nav aria-label={t('nav.main')} className="hidden w-56 shrink-0 px-2 py-4 md:block">
      <GroupedLinks items={visibleItems(own, admin)} />
    </nav>
  );
}

/** Bottom bar on phones: the main pages plus a "More" sheet with every page. */
export function BottomNav() {
  const { t } = useTranslation();
  const { own } = useEngine();
  const admin = useIsAdmin();
  const location = useLocation();
  // The sheet belongs to the page it was opened on, so any navigation (a link, the back button) closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === location.pathname;
  const setOpen = (value: boolean) => {
    setOpenOn(value ? location.pathname : null);
  };
  const titleId = useId();
  const closeButton = useRef<HTMLButtonElement>(null);
  const moreButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const opener = moreButton.current;
    closeButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenOn(null);
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      opener?.focus();
    };
  }, [open]);

  const tab = 'flex flex-1 flex-col items-center gap-0.5 py-2 text-xs';
  return (
    <>
      <nav
        aria-label={t('nav.quick')}
        className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden dark:border-slate-800 dark:bg-slate-950"
      >
        <ul className="flex">
          {bottomBarItems(own).map((navItem) => (
            <li key={navItem.id} className="flex flex-1">
              <NavLink
                to={href(navItem)}
                end={navItem.path === ''}
                className={({ isActive }) =>
                  `${tab} ${isActive ? 'font-semibold text-slate-900 dark:text-white' : 'text-slate-500 dark:text-slate-400'}`
                }
              >
                <NavIcon id={navItem.id} />
                {t(`nav.${navItem.id}`)}
              </NavLink>
            </li>
          ))}
          <li className="flex flex-1">
            <button
              ref={moreButton}
              type="button"
              aria-expanded={open}
              aria-haspopup="dialog"
              onClick={() => {
                setOpen(true);
              }}
              className={`${tab} text-slate-500 dark:text-slate-400`}
            >
              <NavIcon id="more" />
              {t('nav.more')}
            </button>
          </li>
        </ul>
      </nav>
      {open && (
        <div className="fixed inset-0 z-30 md:hidden">
          <button
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            className="absolute inset-0 h-full w-full bg-slate-900/50"
            onClick={() => {
              setOpen(false);
            }}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto rounded-t-xl bg-white p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] dark:bg-slate-900"
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 id={titleId} className="text-base font-semibold">
                {t('nav.allPages')}
              </h2>
              <button
                ref={closeButton}
                type="button"
                onClick={() => {
                  setOpen(false);
                }}
                className="rounded px-2 py-1 text-sm underline"
              >
                {t('nav.close')}
              </button>
            </div>
            <GroupedLinks
              items={visibleItems(own, admin)}
              onNavigate={() => {
                setOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </>
  );
}
