import { NAMESPACES, resources } from '@/i18n/resources';

type Tree = { [key: string]: string | Tree };

function leaves(tree: Tree, prefix = ''): [string, string][] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === 'string' ? [[path, value] as [string, string]] : leaves(value, path);
  });
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1] ?? '').sort();
}

describe.each(NAMESPACES)('namespace %s', (ns) => {
  const th = new Map(leaves(resources.th[ns]));
  const en = new Map(leaves(resources.en[ns]));

  it('has the same keys in Thai and English', () => {
    expect([...th.keys()].sort()).toEqual([...en.keys()].sort());
  });

  it('has no empty texts and the same placeholders in both languages', () => {
    for (const [key, text] of th) {
      expect(text.trim(), key).not.toBe('');
      expect(placeholders(text), key).toEqual(placeholders(en.get(key) ?? ''));
    }
  });
});

describe('UI texts', () => {
  // PLAN: no profitability claims anywhere in the product.
  const forbidden = [
    /guarantee[sd]?\s+(?:profit|return)/i,
    /risk[- ]free/i,
    /รับประกันกำไร/,
    /ไม่มีความเสี่ยง/,
  ];

  it.each(['th', 'en'] as const)('%s contains no profitability claims', (language) => {
    for (const ns of NAMESPACES) {
      for (const [key, text] of leaves(resources[language][ns])) {
        for (const pattern of forbidden) expect(pattern.test(text), `${ns}:${key}`).toBe(false);
      }
    }
  });
});
