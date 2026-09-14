import { test, expect } from '@playwright/test';

test('major complex, station and named building searches open actual source records', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.locator('#place-search').fill('헬리오시티');
  await page.locator('#place-search').press('Enter');
  await expect(page.locator('#place-title')).toHaveText('헬리오시티아파트');
  await expect(page.locator('.place-popup')).toContainText('개별 동의 높이');
  await expect(page.locator('.place-popup a')).toHaveAttribute('href', 'https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do');
  await expect.poll(() => page.locator('.landmark-pin').count()).toBeGreaterThan(0);
  await page.waitForFunction(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return !map.isMoving() && map.loaded() && map.queryRenderedFeatures({ layers: ['building-footprints', 'building-solids'] }).length > 20;
  });
  await expect(page.locator('#pitch-value')).toHaveText('58°');
  await page.screenshot({ path: 'tests/screenshots/helio-landmarks.png' });
  await page.locator('#place-search').fill('강남역');
  await page.locator('#place-search').press('Enter');
  await expect(page.locator('#place-title')).toHaveText('강남');
  await expect(page.locator('.place-popup')).toContainText('철도·지하철역');
  await page.locator('#place-search').fill('헬리오시티 경로당');
  await page.locator('#place-search').press('Enter');
  await expect(page.locator('#inspection .building-title')).toHaveText('헬리오시티 경로당');
  const results = await (await request.get('/api/places?q=헬리오시티%20경로당')).json();
  const original = await (await request.get(`/api/buildings/${results.results[0].building_id}`)).json();
  await expect(page.locator('.building-facts')).toContainText(`${original.properties.footprint_area_m2.toLocaleString('ko-KR', { maximumFractionDigits: 1 })} m²`);
  expect(errors).toEqual([]);
});

test('roadways and mapped walkways render and can be hidden independently', async ({ page }) => {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.roads.getData().features.length > 100);
  await page.locator('#quick-buildings').click();
  await page.locator('#quick-landmarks').click();
  await page.getByRole('button', { name: '2D 지도', exact: true }).click();
  await page.waitForFunction(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return map.getPitch() === 0 && map.queryRenderedFeatures({ layers: ['walkway-lines', 'walkway-crossings'] }).length > 5;
  });
  await page.locator('#quick-roads').click();
  const roadLayers = ['base-roads', 'base-roads-case', 'base-road-names', 'roadway-lines'];
  await expect.poll(() => page.evaluate(ids => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ids }).length, roadLayers)).toBe(0);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['walkway-lines', 'walkway-crossings'] }).length)).toBeGreaterThan(5);
  await page.locator('#quick-walkways').click();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['walkway-lines', 'walkway-crossings'] }).length)).toBe(0);
  await page.locator('#quick-roads').click();
  await page.locator('#quick-walkways').click();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['roadway-lines', 'walkway-lines'] }).length)).toBeGreaterThan(20);
  await page.screenshot({ path: 'tests/screenshots/road-walkway-layers.png' });
});
