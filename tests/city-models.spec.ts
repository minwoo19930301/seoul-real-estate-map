import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const assets = JSON.parse(readFileSync('public/models/manifest.json', 'utf8')).assets;

test('four original Blender models render, stay at 1x height, restore solids and remain idle', async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  const requests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.url().endsWith('.glb')) requests.push(request.url()); });
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels && (window as any).__SEOUL_MAP__.getState().terrainReady);
  await page.locator('#mode-25d').click();
  const results: any[] = [];
  for (const asset of assets) {
    const zoom = asset.id === 'lotte' ? 15.0 : asset.id === 'nseoul' ? 15.6 : 16.0;
    const matchesViewport = (url: string, route: string) => {
      const query = new URL(url);
      // Building contents and the detailed-road tier are identical above z14;
      // controllers normalize this API parameter to reuse complete responses.
      if (query.pathname !== route || Number(query.searchParams.get('zoom')) !== 14) return false;
      const [west, south, east, north] = (query.searchParams.get('bbox') ?? '').split(',').map(Number);
      return west < asset.coordinate.lon && asset.coordinate.lon < east && south < asset.coordinate.lat && asset.coordinate.lat < north;
    };
    const nextRoads = page.waitForResponse(response => matchesViewport(response.url(), '/api/roads') && response.ok());
    const nextBuildings = page.waitForResponse(response => matchesViewport(response.url(), '/api/buildings') && response.ok());
    await page.evaluate((a: any) => {
      const map = (window as any).__SEOUL_MAP__.map;
      map.jumpTo({ center: [a.coordinate.lon, a.coordinate.lat], zoom: a.id === 'lotte' ? 15.0 : a.id === 'nseoul' ? 15.6 : 16.0, pitch: 58, bearing: -20 });
    }, asset);
    await Promise.all([nextRoads, nextBuildings]);
    await page.waitForFunction(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.some((m: any) => m.id === id && m.active && m.drawCount > 0), asset.id);
    await page.waitForFunction(() => {
      const api = (window as any).__SEOUL_MAP__;
      return api.map.loaded() && !api.map.isMoving() && api.roads.getData().features.length > 0
        && !document.querySelector('#building-status')?.textContent?.includes('불러오는');
    });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    const model = state.models.find((m: any) => m.id === asset.id);
    expect(model.height_m).toBe(asset.dimensions[1]);
    expect(model.ground_m).not.toBeNull();
    expect(state.lastDrawCalls).toBeGreaterThan(0);
    expect(state.activeFootprintIds.length).toBeGreaterThan(0);
    await page.screenshot({ path: `tests/screenshots/city-model-${asset.id}.png` });
    results.push({ id: asset.id, ...model, draw_calls: state.lastDrawCalls });
  }
  const before = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().models.find((m: any) => m.id === 'coex'));
  await page.locator('#exaggeration').evaluate((input: HTMLInputElement) => { input.value = '1'; input.dispatchEvent(new Event('input')); });
  await page.waitForFunction(old => {
    const model = (window as any).__SEOUL_MAP__.cityModels.getState().models.find((m: any) => m.id === 'coex');
    return model.active && model.ground_m !== old;
  }, before.ground_m);
  const after = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().models.find((m: any) => m.id === 'coex'));
  expect(after.height_m).toBe(before.height_m);
  expect(Math.abs(after.ground_m * 4 - before.ground_m)).toBeLessThan(1);
  await page.locator('#toggle-city-models').uncheck();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
  await page.locator('#toggle-city-models').check();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length > 0);
  await page.locator('#mode-2d').click();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
  await page.locator('#mode-25d').click();
  await page.waitForFunction(() => {
    const api = (window as any).__SEOUL_MAP__;
    return api.cityModels.getState().activeFootprintIds.length > 0 && api.map.loaded() && !api.map.isMoving();
  });
  // Tile completion can precede the debounced tree worker and symbol fade.
  // Measure inactivity after all network/worker work has actually settled.
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.getState().greeneryPending);
  let settlingFrame = -1, unchangedSince = Date.now();
  await expect.poll(async () => {
    const frame = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().frameCount);
    if (frame !== settlingFrame) { settlingFrame = frame; unchangedSince = Date.now(); }
    return Date.now() - unchangedSince;
  }, { timeout: 15_000, intervals: [250] }).toBeGreaterThan(700);
  const frameStart = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().frameCount);
  await page.waitForTimeout(1000);
  const frameEnd = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().frameCount);
  expect(frameEnd - frameStart).toBeLessThanOrEqual(3);
  expect(new Set(requests).size).toBe(4);
  expect(requests.length).toBe(4);
  expect(errors).toEqual([]);
  mkdirSync('tests/screenshots', { recursive: true });
  writeFileSync('tests/screenshots/city-model-render-proof.json', JSON.stringify({ results, before, after, idle_frames_in_one_second: frameEnd - frameStart, glb_requests: requests, page_errors: errors }, null, 2));
});
