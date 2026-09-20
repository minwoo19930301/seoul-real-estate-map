import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

test('reference place search waits for reference manifest before selecting Maple', async ({ page }) => {
  test.setTimeout(90_000);
  const reference = JSON.parse(readFileSync('public/models/reference-manifest.json', 'utf8'));
  const maple = reference.places.find((p: any) => p.id === 'reference:maple-xi') ?? reference.places[0];
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/models/reference-manifest.json', async route => {
    await held;
    await route.continue();
  });
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().mapLoaded);
  const initialCenter = await page.evaluate(() => { const m = (window as any).__SEOUL_MAP__.map.getCenter(); return [m.lng, m.lat]; });
  await page.locator('#place-search').fill(maple.name);
  await page.locator('#place-search').press('Enter');
  await page.waitForTimeout(800);
  expect(await page.locator('#place-title').textContent()).not.toContain(maple.name);
  expect(await page.locator('#place-subtitle').textContent()).not.toContain(maple.name);
  expect(await page.evaluate(() => { const m = (window as any).__SEOUL_MAP__.map.getCenter(); return [m.lng, m.lat]; })).toEqual(initialCenter);
  release();
  await expect.poll(() => page.locator('#place-title').textContent(), { timeout: 30_000 }).toBe(maple.name);
  await expect(page.locator('#place-subtitle')).toHaveText(maple.subtitle);
  await expect.poll(async () => page.evaluate(() => {
    const m = (window as any).__SEOUL_MAP__.map.getCenter();
    return [m.lng, m.lat];
  }), { timeout: 10_000 }).toEqual(maple.center);
});

test('main manifest failure does not leave place submit waiting forever', async ({ page }) => {
  await page.route('**/models/manifest.json', route => route.fulfill({ status: 404, body: 'missing' }));
  await page.goto('/');
  await page.locator('#place-search').fill('서울특별시청');
  await page.locator('#place-search').press('Enter');
  await expect(page.locator('#place-title')).toContainText('서울특별시청', { timeout: 20_000 });
});
