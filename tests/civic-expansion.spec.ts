import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const assets = JSON.parse(readFileSync('public/models/manifest.json', 'utf8')).assets;
const transit = JSON.parse(readFileSync('public/transit.json', 'utf8')).features;
const additions = JSON.parse(readFileSync('docs/apartment-100-candidates.json', 'utf8'));
const apartment = additions.find((a: any) => a.householdCount >= 100 && a.householdCount < 400);
test('City Hall, heritage, corporate offices and 100+ apartments render alongside official bus and bike points', async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.waitForFunction(() => { const a = (window as any).__SEOUL_MAP__; return a?.cityModels && a.getState().terrainReady && a.map.getLayer('transit-bike-points'); });
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((input: HTMLInputElement) => { input.value = '1'; input.dispatchEvent(new Event('input')); });
  const results = [];
  mkdirSync('tests/screenshots', { recursive: true });
  for (const name of ['서울특별시청', '서울도서관', '숭례문', '흥인지문', '아모레퍼시픽 본사', apartment.nameKo]) {
    const asset = assets.find((a: any) => a.nameKo === name);
    expect(asset).toBeTruthy();
    await page.evaluate((a: any) => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [a.coordinate.lon, a.coordinate.lat], zoom: a.category === 'company-office' ? 17 : 18, pitch: 58, bearing: 25 }), asset);
    await page.waitForFunction(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.some((m: any) => m.id === id && m.active && m.drawCount > 0), asset.id, { timeout: 35_000 });
    await page.waitForLoadState('networkidle');
    const s = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    expect(s.models.length).toBeGreaterThanOrEqual(assets.length);
    expect(s.models.filter((m: any) => m.loaded).length).toBeLessThanOrEqual(48);
    expect(s.models.filter((m: any) => m.active).length).toBeLessThanOrEqual(32);
    expect(s.models.filter((m: any) => m.error)).toEqual([]);
    await page.screenshot({ path: `tests/screenshots/civic-${asset.id}.png` });
    results.push({ name, id: asset.id, householdCount: asset.householdCount, model: s.models.find((m: any) => m.id === asset.id) });
    if (asset.category === 'company-office') {
      await page.locator('#toggle-company-models').uncheck();
      await expect.poll(() => page.evaluate(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.find((m: any) => m.id === id).active, asset.id)).toBe(false);
      await page.locator('#toggle-company-models').check();
    }
    if (asset.category === 'city-hall') {
      await page.locator('#toggle-cultural-models').uncheck();
      await expect.poll(() => page.evaluate(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.find((m: any) => m.id === id).active, asset.id)).toBe(false);
      await page.locator('#toggle-cultural-models').check();
    }
  }
  const bike = transit.filter((f: any) => f.properties.kind === 'bike_station').sort((a: any,b: any) => Math.hypot(a.geometry.coordinates[0]-126.978,a.geometry.coordinates[1]-37.566)-Math.hypot(b.geometry.coordinates[0]-126.978,b.geometry.coordinates[1]-37.566))[0];
  await page.evaluate((coordinate: any) => (window as any).__SEOUL_MAP__.map.jumpTo({ center: coordinate, zoom: 17, pitch: 0, bearing: 0 }), bike.geometry.coordinates);
  await page.waitForFunction(() => { const m = (window as any).__SEOUL_MAP__.map; return m.queryRenderedFeatures({ layers: ['transit-bike-points'] }).length > 0 && m.queryRenderedFeatures({ layers: ['transit-bus-points'] }).length > 0; });
  await page.waitForLoadState('networkidle');
  const p = await page.evaluate((coordinate: any) => { const m = (window as any).__SEOUL_MAP__.map, p = m.project(coordinate), r = m.getCanvas().getBoundingClientRect(); return { x: p.x + r.left, y: p.y + r.top }; }, bike.geometry.coordinates);
  const selectionBefore = await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().selectedCoordinate);
  await page.mouse.click(p.x, p.y);
  await expect(page.locator('.maplibregl-popup-content')).toContainText(bike.properties.nameKo);
  await expect(page.locator('.maplibregl-popup-content')).toContainText('실시간 대여 가능 대수는 제공하지 않습니다');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().selectedCoordinate)).toEqual(selectionBefore);
  await page.screenshot({ path: 'tests/screenshots/civic-official-transit.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.maplibregl-popup-close-button').click();
  await expect(page.locator('#mobile-panel')).toHaveAttribute('aria-expanded', 'false');
  await page.evaluate((coordinate: any) => (window as any).__SEOUL_MAP__.map.jumpTo({ center: coordinate, zoom: 17, pitch: 0, bearing: 0 }), bike.geometry.coordinates);
  await page.waitForLoadState('networkidle');
  const mobilePoint = await page.evaluate((coordinate: any) => { const m = (window as any).__SEOUL_MAP__.map, p = m.project(coordinate), r = m.getCanvas().getBoundingClientRect(); return { x: p.x + r.left, y: p.y + r.top }; }, bike.geometry.coordinates);
  await page.mouse.click(mobilePoint.x, mobilePoint.y);
  await expect(page.locator('.maplibregl-popup-content')).toContainText(bike.properties.nameKo);
  await expect(page.locator('#mobile-panel')).toHaveAttribute('aria-expanded', 'false');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().selectedCoordinate)).toEqual(selectionBefore);
  await page.screenshot({ path: 'tests/screenshots/civic-transit-mobile.png' });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.locator('#toggle-bus-stops').uncheck();
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getLayoutProperty('transit-bike-points','visibility'))).toBe('visible');
  await page.locator('#toggle-bike-stations').uncheck();
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getLayoutProperty('transit-bike-labels','visibility'))).toBe('none');
  expect(errors).toEqual([]);
  writeFileSync('docs/civic-expansion-browser-check.json',JSON.stringify({ results, sampledBike: bike, pageErrors: errors, independentToggles: true, sourcePopupVerified: true, transitClickDoesNotInspectTerrain: true, mobilePopupKeepsPanelClosed: true, boundedCache: true },null,2)+'\n');
});
