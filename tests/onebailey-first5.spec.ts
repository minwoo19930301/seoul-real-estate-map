import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8'));
const numbers = [101, 102, 121, 122, 123];
const remaining = corrections.corrections.find((c: any) => c.sourceId === 'apt-a10023043').assets.find((a: any) => a.id === 'apt-a10023043');

for (const missing of [null, 101, 123]) {
  test(`OneBailey first five: ${missing ? `bridge owner ${missing} unavailable` : 'all models draw'}`, async ({ page }) => {
    test.setTimeout(180_000);
    const assets = numbers.map(n => manifest.assets.find((a: any) => a.id === `bespoke-raemian-onebailey-${n}`));
    assets.forEach((a: any) => expect(a).toBeTruthy());
    const failed = assets.find((a: any) => a.id === `bespoke-raemian-onebailey-${missing}`);
    if (failed) await page.route(`**/models/${failed.model}`, route => route.fulfill({ status: 404, body: 'intentional bridge-owner failure' }));
    const pageErrors: string[] = [];
    page.on('pageerror', e => pageErrors.push(e.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9974, 37.50818], zoom: 16.65, pitch: 55, bearing: 208 }));
    const wanted = assets.map((a: any) => a === failed ? a.supersedes[0] : a.id);
    wanted.push(remaining.id);
    await page.waitForFunction(({ wanted, failedId }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && (!failedId || state.models.some((m: any) => m.id === failedId && m.error));
    }, { wanted, failedId: failed?.id }, { timeout: 130_000 });
    await page.waitForFunction((ownedIds: string[]) => {
      const map = (window as any).__SEOUL_MAP__.map;
      const rendered = map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      return ownedIds.every(id => !rendered.some((f: any) => f.properties.id === id || f.properties.parent_id === id));
    }, assets.flatMap((a: any) => a.footprintIds), { timeout: 15_000 });
    const state = await page.evaluate(() => {
      const api = (window as any).__SEOUL_MAP__;
      return { ...api.cityModels.getState(), renderedSolids: [...new Set(api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).map((f: any) => f.properties.id))] };
    });
    for (const asset of assets) {
      expect(state.models.find((m: any) => m.id === asset.id)?.active ?? false).toBe(asset !== failed);
      expect(state.models.find((m: any) => m.id === asset.supersedes[0])?.active ?? false).toBe(asset === failed);
      for (const id of asset.footprintIds) {
        expect(state.activeFootprintIds).toContain(id);
        expect(state.renderedSolids).not.toContain(id);
      }
    }
    for (const id of remaining.footprintIds) expect(state.activeFootprintIds).toContain(id);
    expect(remaining.footprintIds).toHaveLength(14);
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id)).toEqual(failed ? [failed.id] : []);
    expect(pageErrors).toEqual([]);
    const directory = 'tests/screenshots/onebailey-first5'; mkdirSync(directory, { recursive: true });
    const key = missing ? `missing-${missing}` : 'normal';
    await page.screenshot({ path: `${directory}/${key}.png` });
    writeFileSync(`${directory}/${key}.json`, JSON.stringify({ wanted, active: state.models.filter((m: any) => m.active), owned: state.activeFootprintIds, pageErrors }, null, 2) + '\n');
  });
}
