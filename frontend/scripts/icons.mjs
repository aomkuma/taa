/**
 * Renders the PWA's PNG icons from public/icon.svg with the installed Google Chrome (Playwright, no browser
 * download): `node scripts/icons.mjs`. Run it after changing the SVG and commit the PNGs.
 *
 * - icon-192.png, icon-512.png: the SVG as is (rounded tile, transparent corners), purpose "any"
 * - maskable-512.png: the drawing inside the 80% safe zone on a full-bleed background, purpose "maskable"
 * - apple-touch-icon.png (180): full-bleed and opaque, as iOS rounds the corners itself
 */
import { readFile, writeFile } from 'node:fs/promises';

import { chromium } from '@playwright/test';

const BACKGROUND = '#0f172a';
const svg = await readFile(new URL('../public/icon.svg', import.meta.url), 'utf8');
const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;

const ICONS = [
  { file: 'icon-192.png', size: 192, scale: 1, fill: false },
  { file: 'icon-512.png', size: 512, scale: 1, fill: false },
  { file: 'maskable-512.png', size: 512, scale: 0.8, fill: true },
  { file: 'apple-touch-icon.png', size: 180, scale: 1, fill: true },
];

const browser = await chromium.launch({ channel: 'chrome' });
try {
  for (const { file, size, scale, fill } of ICONS) {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    const inner = Math.round(size * scale);
    const offset = Math.round((size - inner) / 2);
    await page.setContent(
      `<html><body style="margin:0;background:${fill ? BACKGROUND : 'transparent'}">` +
        `<img src="${dataUrl}" width="${inner}" height="${inner}" style="position:absolute;left:${offset}px;top:${offset}px">` +
        '</body></html>',
    );
    const png = await page.screenshot({ omitBackground: !fill });
    await writeFile(new URL(`../public/icons/${file}`, import.meta.url), png);
    await page.close();
    console.log(`public/icons/${file}`);
  }
} finally {
  await browser.close();
}
