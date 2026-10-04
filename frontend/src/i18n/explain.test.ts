import explanationsPy from '../../../app/advisory/explanations.py?raw';

import { createI18n } from '@/i18n';
import { explain, MONEY_PARAMS } from '@/i18n/explain';
import { resources } from '@/i18n/resources';
import { pyExplanationPlaceholders, pyMoneyParams } from '@/test/python';

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = ''): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}

function placeholders(text: string): Set<string> {
  return new Set([...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1] ?? ''));
}

describe('explain', () => {
  const params = { min_lot_risk: 12.5, budget: 5, required_equity: 2500, currency: 'USD' };

  it('renders Thai with locale-formatted money parameters', () => {
    expect(explain(createI18n('th'), 'g2.min_lot_risk', params)).toBe(
      'ล็อตขั้นต่ำเสี่ยง 12.50 USD เกินงบความเสี่ยง 5.00 USD ต้องมีเงินทุน (equity) อย่างน้อย 2,500.00 USD',
    );
  });

  it('renders English', () => {
    expect(explain(createI18n('en'), 'g2.min_lot_risk', params)).toBe(
      'The minimum lot risks 12.50 USD vs your budget of 5.00 USD; needs equity ≥ 2,500.00 USD',
    );
  });

  it('formats non-money numbers without padding', () => {
    expect(explain(createI18n('en'), 'g6.few_candles', { candles: 120, required: 1000 })).toBe(
      'Only 120 of 1,000 candles are available',
    );
  });

  it('renders an unknown key as itself', () => {
    expect(explain(createI18n('th'), 'g9.unknown')).toBe('g9.unknown');
  });
});

describe('explanation catalogs match app/advisory/explanations.py', () => {
  const backend = pyExplanationPlaceholders(explanationsPy);

  it('finds the backend keys', () => {
    expect(backend.size).toBeGreaterThan(20);
  });

  it.each(['th', 'en'] as const)('%s has exactly the backend keys and placeholders', (language) => {
    const catalog = flatten(resources[language].explain);
    expect([...catalog.keys()].sort()).toEqual([...backend.keys()].sort());
    for (const [key, names] of backend) {
      expect({ key, names: [...placeholders(catalog.get(key) ?? '')].sort() }).toEqual({
        key,
        names: [...names].sort(),
      });
    }
  });

  it('formats the same money parameters as the backend', () => {
    expect([...MONEY_PARAMS].sort()).toEqual(pyMoneyParams(explanationsPy).sort());
  });
});
