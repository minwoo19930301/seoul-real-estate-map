import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const base = read('public/models/manifest.json').assets;
const sources = read('docs/model-audit/shinbanpo-xi-source-identity.json').towers;
const byId = new Map<string, any>([...base, ...corrections.flatMap((c: any) => c.assets), ...authored].map((a: any) => [a.id, a]));
const numbers = Array.from({length: 7}, (_, i) => 101 + i);
const scenarios = [
  {name: 'normal', fail: [] as number[], raw: [] as number[]},
  {name: 'representative-fallback', fail: [101], raw: [] as number[]},
  {name: 'mixed-independent-fallbacks', fail: [102, 105], raw: [] as number[]},
  {name: '106-raw-restoration', fail: [106], raw: [106]},
  {name: 'all7-fallbacks', fail: numbers, raw: [] as number[]},
];
const neighbors = ['public-9b75f8f8-36fd-447e-82f2-445bab864146', 'apt-a13790721',
  'apt-a13703027', 'apt-a13779431', 'apt-a13790910', 'residential-40d8003b-2122-4429-b9c8-df133a85ed4d'];

for (const scenario of scenarios) {
  test(`Shinbanpo Xi distinct towers: ${scenario.name}`, async ({ page }) => {
    test.setTimeout(180_000);
    const family = numbers.map(number => {
      const source = sources.find((s: any) => s.number === number);
      const asset = byId.get(`bespoke-shinbanpo-xi-${number}`);
      expect(asset, `${number} published`).toBeTruthy();
      expect(asset.footprintIds).toEqual([source.sourceId]);
      expect(asset.supersedes).toHaveLength(1);
      const fallback = byId.get(asset.supersedes[0]);
      expect(fallback.footprintIds).toEqual([source.sourceId]);
      return { number, source, asset, fallback };
    });
    const familyFootprints = family.map(b => b.source.sourceId);
    for (const id of neighbors) expect(byId.get(id).footprintIds.some((fid: string) => familyFootprints.includes(fid))).toBe(false);
    const failedIds = family.flatMap(b => scenario.fail.includes(b.number)
      ? [b.asset.id, ...(scenario.raw.includes(b.number) ? [b.fallback.id] : [])] : []);
    for (const id of failedIds) {
      await page.route(`**/models/${byId.get(id).model}`, route => route.fulfill({ status: 404, body: 'intentional Shinbanpo Xi model failure' }));
    }
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(center => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom: 16.65, pitch: 55, bearing: 30 }), [127.00845, 37.51025]);
    const desired = family.map(b => ({ ...b,
      wanted: scenario.raw.includes(b.number) ? null : scenario.fail.includes(b.number) ? b.fallback.id : b.asset.id }));
    const wanted = desired.map(b => b.wanted).filter(Boolean);
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds }, { timeout: 130_000 });
    const owned = desired.filter(b => b.wanted).map(b => b.source.sourceId);
    const raw = desired.filter(b => !b.wanted).map(b => b.source.sourceId);
    await page.waitForFunction(({ owned, raw }) => {
      const rendered = (window as any).__SEOUL_MAP__.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      const contains = (id: string) => rendered.some((f: any) => f.properties.id === id || f.properties.parent_id === id);
      return owned.every(id => !contains(id)) && raw.every(contains);
    }, { owned, raw }, { timeout: 15_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    for (const b of desired) {
      expect(state.models.find((m: any) => m.id === b.asset.id)?.active ?? false).toBe(b.wanted === b.asset.id);
      expect(state.models.find((m: any) => m.id === b.fallback.id)?.active ?? false).toBe(b.wanted === b.fallback.id);
    }
    for (const id of owned) expect(state.activeFootprintIds).toContain(id);
    for (const id of raw) expect(state.activeFootprintIds).not.toContain(id);
    expect(state.models.find((m: any) => m.id === 'apt-a10026004')?.active ?? false).toBe(false);
    const neighborFootprints = neighbors.map(id => ({id, footprints: byId.get(id).footprintIds}));
    await page.waitForFunction(groups => {
      const app = (window as any).__SEOUL_MAP__;
      const state = app.cityModels.getState();
      const raw = app.map.queryRenderedFeatures(undefined, {layers: ['building-solids', 'building-footprints', 'building-outlines']});
      return groups.every(({id, footprints}: any) => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0)
        || raw.some((f: any) => footprints.includes(f.properties.id) || footprints.includes(f.properties.parent_id)));
    }, neighborFootprints, {timeout: 15_000});
    expect(errors).toEqual([]);
    const directory = 'tests/screenshots/shinbanpo-xi7'; mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${scenario.name}.png` });
    writeFileSync(`${directory}/${scenario.name}.json`, JSON.stringify({ wanted, failedIds, owned, raw, errors, state }, null, 2) + '\n');
  });
}
