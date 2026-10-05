import { expect, test } from '@playwright/test';

import { fakeApi } from './api';

test.describe('PWA smoke', () => {
  test('serves an installable app: manifest with maskable icons, Apple icon, a service worker', async ({
    page,
  }) => {
    await fakeApi(page, { signedIn: false });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute('href');
    expect(manifestHref).toBeTruthy();
    const manifest = (await (await page.request.get(manifestHref ?? '')).json()) as {
      icons: { src: string; purpose?: string }[];
      display: string;
    };
    expect(manifest.display).toBe('standalone');
    expect(manifest.icons.some((i) => i.purpose === 'maskable')).toBe(true);
    for (const icon of manifest.icons) {
      expect((await page.request.get(`/${icon.src}`)).ok(), icon.src).toBe(true);
    }
    const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute('href');
    expect((await page.request.get(apple ?? '')).ok()).toBe(true);
    const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
    expect(scope).toMatch(/\/$/);
  });

  test('a signed-out visitor gets the login page, in Thai', async ({ page }) => {
    await fakeApi(page, { signedIn: false });
    await page.goto('/positions');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('html')).toHaveAttribute('lang', 'th');
    await expect(page.getByRole('button', { name: /เข้าสู่ระบบ/ })).toBeVisible();
  });

  test('the owner opens the dashboard and moves between pages without errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await fakeApi(page, { signedIn: true });
    await page.goto('/');
    const nav = page.getByRole('navigation', { name: 'เมนูหลัก' });
    await expect(nav).toBeVisible();
    for (const name of ['จัดอันดับสัญลักษณ์', 'บุคลิกการเทรด', 'ตั้งค่า']) {
      await nav.getByRole('link', { name }).click();
      await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
    }
    expect(errors).toEqual([]);
  });
});
