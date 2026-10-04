import { DEFAULT_LANGUAGE, isLanguage, loadLanguage, saveLanguage } from '@/i18n/languages';

describe('languages', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('defaults to Thai', () => {
    expect(DEFAULT_LANGUAGE).toBe('th');
    expect(loadLanguage()).toBe('th');
  });

  it('round-trips a saved language', () => {
    saveLanguage('en');
    expect(loadLanguage()).toBe('en');
  });

  it('ignores an unsupported stored value', () => {
    window.localStorage.setItem('taa.language', 'fr');
    expect(loadLanguage()).toBe('th');
  });

  it('falls back to the default when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() => {
      saveLanguage('en');
    }).not.toThrow();
    expect(loadLanguage()).toBe('th');
  });

  it('recognizes only supported languages', () => {
    expect(isLanguage('th')).toBe(true);
    expect(isLanguage('en')).toBe(true);
    expect(isLanguage('TH')).toBe(false);
    expect(isLanguage(null)).toBe(false);
  });
});
