import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8'));
const numbers = [100, 109];

for (const missing of [[], [100], [109], [100, 109]]) {
  test(`Acro first two: ${missing.length ? `missing ${missing.join(',')}` : 'normal'}`, async ({ page }) => {
    test.setTimeout(150_000);
    const assets = numbers.map(n => manifest.assets.find((a: any) => a.id === `bespoke-acro-riverpark-${n}`));
    const retained = corrections.corrections.find((c: any) => c.sourceId === 'apt-a10027205').assets.find((a: any) => a.id === 'apt-a10027205');
    const failed = assets.filter((a: any) => missing.some(n => a.id === `bespoke-acro-riverpark-${n}`));
    for (const asset of failed) await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional Acro failure' }));
    const pageErrors: string[] = []; page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9937, 37.5057], zoom: 16.45, pitch: 55, bearing: 30 }));
    const wanted = [...assets.map((a: any) => failed.includes(a) ? a.supersedes[0] : a.id), retained.id];
    await page.waitForFunction(({ wanted, failed }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failed.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failed: failed.map((a: any) => a.id) }, { timeout: 120_000 });
    const owned = assets.flatMap((a: any) => a.footprintIds);
    await page.waitForFunction(ids => {
      const features = (window as any).__SEOUL_MAP__.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      return ids.every(id => !features.some((f: any) => f.properties.id === id || f.properties.parent_id === id));
    }, owned, { timeout: 15_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    for (const asset of assets) {
      expect(state.models.find((m: any) => m.id === asset.id)?.active ?? false).toBe(!failed.includes(asset));
      expect(state.models.find((m: any) => m.id === asset.supersedes[0])?.active ?? false).toBe(failed.includes(asset));
    }
    expect(retained.footprintIds).toHaveLength(15);
    for (const id of [...owned, ...retained.footprintIds]) expect(state.activeFootprintIds).toContain(id);
    for (const id of ['8be35ba6-cad9-427a-b6c9-21b83caf3501', 'ce2823b4-6bb2-4b4a-b1f6-21f035384ce1']) {
      expect(retained.footprintIds).toContain(id);
      expect(owned).not.toContain(id);
    }
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id).sort()).toEqual(failed.map((a: any) => a.id).sort());
    expect(pageErrors).toEqual([]);
    const directory = 'tests/screenshots/acro-first2'; mkdirSync(directory, { recursive: true });
    const key = missing.length ? `missing-${missing.join('-')}` : 'normal';
    await page.screenshot({ path: `${directory}/${key}.png` });
    writeFileSync(`${directory}/${key}.json`, JSON.stringify({ wanted, active: state.models.filter((m: any) => m.active), owned: state.activeFootprintIds, pageErrors }, null, 2) + '\n');
  });
}
