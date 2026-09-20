import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const references = JSON.parse(readFileSync('public/models/reference-manifest.json', 'utf8'));
const bespoke = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const maplePlace = references.places.find((p: any) => p.name === '메이플자이');
const mapleUpgrades = ['maple-xi-208', 'maple-xi-209', 'maple-xi-210', 'maple-xi-211', 'maple-xi-212', 'maple-xi-213'];
const mapleBuildings = references.assets.filter((a: any) => /^maple-xi-\d+$/.test(a.id))
  .map((a: any) => mapleUpgrades.includes(a.id) ? `bespoke-${a.id}` : a.id).sort();

test('latest authored landmarks and Maple Xi replace generic shapes on the map', async ({ page }) => {
  test.setTimeout(300_000);
  const errors: string[] = [], failures: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400 && response.url().includes('/models/')) failures.push(response.url()); });
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels && (window as any).__SEOUL_MAP__.getState().terrainReady);
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((input: HTMLInputElement) => { input.value = '1'; input.dispatchEvent(new Event('input')); });
  await page.locator('#place-search').fill('메이플자이');
  await expect(page.locator('#search-results')).toContainText('메이플자이');
  await page.locator('#place-search').press('Enter');
  await expect.poll(() => page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return { center: map.getCenter().toArray(), zoom: map.getZoom() };
  })).toEqual({ center: maplePlace.center, zoom: maplePlace.zoom });
  await expect(page.locator('#place-subtitle')).toHaveText(maplePlace.subtitle);
  await page.locator('#place-search').fill('');
  mkdirSync('tests/screenshots', { recursive: true });
  const samples = ['bespoke-seoul-city-hall-new', 'reference-flight-amorepacific-hq', 'reference-flight-ddp', 'bespoke-tower-palace-g', 'bespoke-maple-xi-210'];
  const results: any[] = [];
  for (const id of samples) {
    const asset = [...bespoke.assets, ...references.assets].find((a: any) => a.id === id);
    const isMaple = /^(?:bespoke-)?maple-xi-/.test(id);
    const center = isMaple ? maplePlace.center : [asset.coordinate.lon, asset.coordinate.lat];
    await page.evaluate(({ center, zoom }) => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom, pitch: 52, bearing: 25 }), { center, zoom: isMaple ? 16.4 : 17.4 });
    await page.waitForFunction(id => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0);
    }, id, { timeout: 60_000 });
    await page.waitForLoadState('networkidle');
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    expect(state.error).toBeNull();
    expect(state.models.filter((m: any) => m.error)).toEqual([]);
    expect(state.models.filter((m: any) => m.loaded).length).toBeLessThanOrEqual(48);
    expect(state.models.filter((m: any) => m.active).length).toBeLessThanOrEqual(32);
    for (const old of asset.supersedes) expect(state.models.find((m: any) => m.id === old)?.active ?? false).toBe(false);
    for (const fid of asset.footprintIds) expect(state.activeFootprintIds).toContain(fid);
    const activeMaple = state.models.filter((m: any) => /^(?:bespoke-)?maple-xi-/.test(m.id) && m.active);
    if (isMaple) {
      const buildings = activeMaple.filter((m: any) => /^(?:bespoke-)?maple-xi-\d+$/.test(m.id)).map((m: any) => m.id).sort();
      expect(buildings).toHaveLength(29);
      expect(buildings).toEqual(mapleBuildings);
      for (const old of mapleUpgrades) expect(state.models.find((m: any) => m.id === old)?.active).toBe(false);
    }
    await page.screenshot({ path: `tests/screenshots/reference-${isMaple ? 'maple-xi' : id.replace('reference-flight-', '')}.png` });
    results.push({ id, model: state.models.find((m: any) => m.id === id), activeMaple: activeMaple.map((m: any) => m.id), active: state.models.filter((m: any) => m.active).length, drawCalls: state.lastDrawCalls });
  }
  const bridge = bespoke.assets.find((a: any) => a.id === 'bespoke-maple-xi-210');
  await page.evaluate((a: any) => (window as any).__SEOUL_MAP__.map.jumpTo({center:[a.coordinate.lon,a.coordinate.lat],zoom:17.8,pitch:60,bearing:205}), bridge);
  await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.cityModels.getState().loading);
  await page.waitForLoadState('networkidle');
  await page.screenshot({path:'tests/screenshots/reference-maple-skybridge.png'});
  await expect(page.locator('.landmark-pin').filter({hasText:'메이플자이'})).toHaveCount(1);
  await expect(page.locator('.landmark-pin').filter({hasText:'잠원녹원한신'})).toHaveCount(0);
  await expect(page.locator('.landmark-pin').filter({hasText:'잠원한신4지구'})).toHaveCount(0);
  await page.locator('#toggle-city-models').uncheck();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
  await page.locator('#toggle-city-models').check();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.cityModels.getState().models.some((m: any) => m.id === 'bespoke-maple-xi-210' && m.active));
  expect(errors).toEqual([]); expect(failures).toEqual([]);
  writeFileSync('docs/reference-browser-check.json', JSON.stringify({ sourceRevision: references.sourceRevision, results, pageErrors: errors, modelFailures: failures }, null, 2) + '\n');
});
