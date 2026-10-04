import enumsPy from '../../../../app/core/enums.py?raw';

import { pyStrEnumValues } from '@/test/python';

import { TRADING_MODES } from './modes';
import { BOTTOM_BAR_SIZE, bottomBarItems, href, NAV_IDS, NAV_ITEMS, visibleItems } from './nav';

describe('navigation model', () => {
  it('lists every page once', () => {
    expect(NAV_ITEMS.map((item) => item.id)).toEqual([...NAV_IDS]);
    expect(NAV_ITEMS.filter((item) => href(item) === '/').map((item) => item.id)).toEqual(['dashboard']);
  });

  it('hides pages with own-engine data on the market feed', () => {
    const feed = visibleItems(false).map((item) => item.id);
    expect(feed).toContain('opportunities');
    expect(feed).not.toContain('positions');
    expect(visibleItems(true)).toHaveLength(NAV_ITEMS.length);
  });

  it('fills the bottom bar from the visible pages', () => {
    expect(bottomBarItems(true).map((item) => item.id)).toEqual([
      'dashboard',
      'opportunities',
      'positions',
      'notifications',
    ]);
    expect(bottomBarItems(false).map((item) => item.id)).toEqual([
      'dashboard',
      'opportunities',
      'notifications',
      'ranking',
    ]);
    expect(bottomBarItems(false)).toHaveLength(BOTTOM_BAR_SIZE);
  });
});

describe('trading modes', () => {
  it('match TradingMode in app/core/enums.py', () => {
    expect([...TRADING_MODES].sort()).toEqual(pyStrEnumValues(enumsPy, 'TradingMode').sort());
  });
});
