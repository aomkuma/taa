import { applyTheme, loadTheme, resolveTheme, saveTheme } from './theme';

function mockSystemDark(dark: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: dark && query.includes('dark'),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe('theme', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('follows the system unless the user chose light or dark', () => {
    mockSystemDark(true);
    expect(resolveTheme('system')).toBe('dark');
    expect(resolveTheme('light')).toBe('light');
    mockSystemDark(false);
    expect(resolveTheme('system')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('sets the dark class and color scheme on <html>', () => {
    applyTheme('dark');
    expect(document.documentElement).toHaveClass('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    applyTheme('light');
    expect(document.documentElement).not.toHaveClass('dark');
  });

  it('remembers the choice and ignores unknown stored values', () => {
    expect(loadTheme()).toBe('system');
    saveTheme('dark');
    expect(loadTheme()).toBe('dark');
    window.localStorage.setItem('taa.theme', 'neon');
    expect(loadTheme()).toBe('system');
  });
});
