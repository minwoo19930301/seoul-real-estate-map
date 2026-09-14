import { test, expect } from '@playwright/test';

test('fixed neighborhood labels are removed and high DPI rendering has a controllable budget', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  try {
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
    await expect(page.locator('.map-caption, .preset-row, .neighborhood-list, [data-place]')).toHaveCount(0);
    const budget = await page.evaluate(() => {
      const map = (window as any).__SEOUL_MAP__.map;
      return { ratio: map.getPixelRatio(), width: map.getCanvas().width, cssWidth: map.getCanvas().clientWidth,
        neighborhoodLayers: map.getStyle().layers.filter((l: any) => l['source-layer'] === 'place').length };
    });
    expect(budget.ratio).toBe(1.25);
    expect(Math.abs(budget.width - budget.cssWidth * 1.25)).toBeLessThanOrEqual(1);
    expect(budget.neighborhoodLayers).toBe(0);
    await page.getByLabel('화면 선명도').selectOption('1');
    expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getPixelRatio())).toBe(1);
    await page.getByLabel('화면 선명도').selectOption('2');
    expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getPixelRatio())).toBe(2);
  } finally { await context.close(); }
});

test('woodland trees are drawn by the worker, reuse exclusion data and stay independent of buildings', async ({ page }) => {
  const exclusionRequests: string[] = [];
  const errors: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/greenery?')) exclusionRequests.push(request.url()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels);
  await page.locator('#place-search').fill('N서울타워');
  await page.locator('#place-search').press('Enter');
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return app.cityModels.getState().trees.activeCount > 0 && app.map.loaded() && !app.map.isMoving();
  });
  await expect(page.locator('#tree-status')).toContainText('실측 자료 아님');
  await page.locator('.maplibregl-popup-close-button').click();
  await page.locator('#quick-buildings').click();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().trees.activeCount)).toBeGreaterThan(0);
  const before = exclusionRequests.length;
  await page.locator('#toggle-trees').uncheck();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().trees.activeCount)).toBe(0);
  await page.locator('#toggle-trees').check();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.cityModels.getState().trees.activeCount > 0);
  expect(exclusionRequests.length).toBe(before);
  expect(new Set(exclusionRequests).size).toBe(exclusionRequests.length);
  await page.locator('#quick-buildings').click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.loaded());
  await page.screenshot({ path: 'tests/screenshots/namsan-greenery.png' });
  expect(errors).toEqual([]);
});
