/**
 * The app's pages (PLAN §A15, §A26–§A32) in navigation order. `own`: the page shows the user's own engine
 * (account, trading or engine data), so it is hidden on the market feed and guarded by `RequireOwnEngine`.
 * Pages not built yet render `PlaceholderPage`; their tickets replace it in `routes.tsx`.
 */

export const NAV_GROUPS = ['overview', 'advisory', 'trading', 'analysis', 'account'] as const;
export type NavGroup = (typeof NAV_GROUPS)[number];

export const NAV_IDS = [
  'dashboard',
  'charts',
  'symbols',
  'ranking',
  'opportunities',
  'accuracy',
  'watchlists',
  'theories',
  'positions',
  'history',
  'decisions',
  'strategies',
  'risk',
  'analytics',
  'backtests',
  'notifications',
  'engines',
  'system',
  'settings',
] as const;
export type NavId = (typeof NAV_IDS)[number];

export interface NavItem {
  id: NavId;
  /** Route path ('' is the index route). */
  path: string;
  group: NavGroup;
  own: boolean;
}

const item = (id: NavId, group: NavGroup, own = false): NavItem => ({
  id,
  path: id === 'dashboard' ? '' : id,
  group,
  own,
});

export const NAV_ITEMS: readonly NavItem[] = [
  item('dashboard', 'overview'),
  item('charts', 'overview', true),
  item('symbols', 'overview', true),
  item('ranking', 'advisory'),
  item('opportunities', 'advisory'),
  item('accuracy', 'advisory'),
  item('watchlists', 'advisory'),
  item('theories', 'advisory'),
  item('positions', 'trading', true),
  item('history', 'trading', true),
  item('decisions', 'trading', true),
  item('strategies', 'trading', true),
  item('risk', 'trading', true),
  item('analytics', 'analysis', true),
  item('backtests', 'analysis', true),
  item('notifications', 'account'),
  item('engines', 'account'),
  item('system', 'account', true),
  item('settings', 'account'),
];

/** The phone's bottom bar: the first `BOTTOM_BAR_SIZE` visible of these, then "More". */
const BOTTOM_BAR_ORDER: readonly NavId[] = [
  'dashboard',
  'opportunities',
  'positions',
  'notifications',
  'ranking',
];
export const BOTTOM_BAR_SIZE = 4;

export function visibleItems(own: boolean): NavItem[] {
  return NAV_ITEMS.filter((navItem) => own || !navItem.own);
}

export function bottomBarItems(own: boolean): NavItem[] {
  const visible = visibleItems(own);
  return BOTTOM_BAR_ORDER.flatMap((id) => visible.filter((navItem) => navItem.id === id)).slice(
    0,
    BOTTOM_BAR_SIZE,
  );
}

export function href(navItem: NavItem): string {
  return `/${navItem.path}`;
}
