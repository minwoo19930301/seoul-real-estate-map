import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const bespoke = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8')).assets;
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8')).corrections;
const representative = bespoke.find((a: any) => a.id === 'bespoke-raemian-prestige-126');
const fallback = corrections.flatMap((c: any) => c.assets).find((a: any) => a.id === 'fallback-prestige-126');
const pentas = Array.from({ length: 6 }, (_, i) => `bespoke-raemian-onepentas-${101 + i}`);

for (const failure of ['none', 'model', 'model-and-fallback']) {
  test(`Prestige126 and One Pentas remain independent: ${failure}`, async ({ page }) => {
    test.setTimeout(180_000);
    expect(representative).toBeTruthy();
    expect(representative.footprintIds).toEqual(['b21842a2-9832-4a21-bcc5-1c571f309556']);
    expect(representative.supersedes).toEqual([fallback.id]);
    expect(fallback.footprintIds).toEqual(representative.footprintIds);
    const failed = failure === 'none' ? [] : failure === 'model' ? [representative] : [representative, fallback];
    for (const asset of failed) {
      await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional Prestige126 failure' }));
    }
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9943, 37.5035], zoom: 16.9, pitch: 50, bearing: 25 }));
    const expected126 = failure === 'none' ? representative.id : failure === 'model' ? fallback.id : null;
    const wanted = expected126 ? [...pentas, expected126] : pentas;
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds: failed.map((a: any) => a.id) }, { timeout: 130_000 });
    const footprint = representative.footprintIds[0];
    await page.waitForFunction(({ footprint, rawExpected }) => {
      const map = (window as any).__SEOUL_MAP__.map;
      const visible = map.queryRenderedFeatures(undefined, { layers: ['building-solids'] })
        .some((f: any) => f.properties.id === footprint || f.properties.parent_id === footprint);
      return visible === rawExpected;
    }, { footprint, rawExpected: expected126 === null }, { timeout: 15_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    for (const asset of [representative, fallback]) {
      expect(state.models.find((m: any) => m.id === asset.id)?.active ?? false).toBe(asset.id === expected126);
    }
    expect(state.activeFootprintIds.includes(footprint)).toBe(expected126 !== null);
    for (const id of pentas) {
      for (const sourceId of bespoke.find((a: any) => a.id === id).footprintIds) expect(state.activeFootprintIds).toContain(sourceId);
    }
    expect(errors).toEqual([]);
    const directory = 'tests/screenshots/prestige126';
    mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${failure}.png` });
    writeFileSync(`${directory}/${failure}.json`, JSON.stringify({ wanted, failedIds: failed.map((a: any) => a.id), errors, state }, null, 2) + '\n');
  });
}
