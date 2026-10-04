import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const base = read('public/models/manifest.json').assets;
const bindings = read('docs/model-audit/prestige-fallback-bindings.json').bindings;
const byId = new Map<string, any>([...base, ...corrections.flatMap((c: any) => c.assets), ...authored].map((a: any) => [a.id, a]));
const west = [101, 102, 103, 104, 105, 110, 111, 125, 126, 127, 128];
const east = [106, 107, 108, 109, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124];
const scenarios = [
  { name: 'west-normal', numbers: west, center: [126.99625, 37.5027], fail: [] as number[], raw: [] as number[] },
  { name: 'east-normal', numbers: east, center: [127.00015, 37.5029], fail: [] as number[], raw: [] as number[] },
  { name: 'west-mixed-fallbacks', numbers: west, center: [126.99625, 37.5027], fail: [101, 103, 125, 126], raw: [] as number[] },
  { name: 'west-103-and125-raw', numbers: west, center: [126.99625, 37.5027], fail: [103, 125], raw: [103, 125] },
  { name: 'east-all-fallbacks', numbers: east, center: [127.00015, 37.5029], fail: east, raw: [] as number[] },
];

for (const scenario of scenarios) {
  test(`Prestige28 distinct towers: ${scenario.name}`, async ({ page }) => {
    test.setTimeout(180_000);
    expect(bindings.map((b: any) => b.number)).toEqual(Array.from({ length: 28 }, (_, i) => 101 + i));
    const family = bindings.map((b: any) => {
      const asset = byId.get(`bespoke-raemian-prestige-${b.number}`);
      expect(asset, `${b.number} published`).toBeTruthy();
      expect(asset.footprintIds).toEqual([b.sourceFootprintId]);
      expect(asset.supersedes).toEqual([b.fallbackAssetId]);
      expect(byId.get(b.fallbackAssetId).footprintIds).toEqual([b.sourceFootprintId]);
      return { ...b, asset };
    });
    const selected = family.filter((b: any) => scenario.numbers.includes(b.number));
    const failedIds = selected.flatMap((b: any) => scenario.fail.includes(b.number)
      ? [b.asset.id, ...(scenario.raw.includes(b.number) ? [b.fallbackAssetId] : [])] : []);
    for (const id of failedIds) {
      await page.route(`**/models/${byId.get(id).model}`, route => route.fulfill({ status: 404, body: 'intentional Prestige family failure' }));
    }
    const retained = ['apt-a13776509', ...(scenario.numbers === west ? ['apt-a13776508'] : [])].map(id => byId.get(id));
    expect(byId.get('apt-a13776509').footprintIds).toHaveLength(2);
    expect(byId.get('apt-a13776508').footprintIds).toHaveLength(3);
    expect(byId.get('apt-a13780001').nameKo).toContain('125');
    expect(byId.get('apt-a13780001').apartmentCode).toBeUndefined();
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(center => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom: 16.65, pitch: 55, bearing: 170 }), scenario.center);
    const desired = selected.map((b: any) => ({ ...b,
      wanted: scenario.raw.includes(b.number) ? null : scenario.fail.includes(b.number) ? b.fallbackAssetId : b.asset.id }));
    const wanted = desired.map((b: any) => b.wanted).filter(Boolean).concat(retained.map(a => a.id));
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds }, { timeout: 130_000 });
    const owned = desired.filter((b: any) => b.wanted).map((b: any) => b.sourceFootprintId).concat(retained.flatMap(a => a.footprintIds));
    const raw = desired.filter((b: any) => !b.wanted).map((b: any) => b.sourceFootprintId);
    await page.waitForFunction(({ owned, raw }) => {
      const rendered = (window as any).__SEOUL_MAP__.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      const contains = (id: string) => rendered.some((f: any) => f.properties.id === id || f.properties.parent_id === id);
      return owned.every(id => !contains(id)) && raw.every(contains);
    }, { owned, raw }, { timeout: 15_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    for (const b of desired) {
      expect(state.models.find((m: any) => m.id === b.asset.id)?.active ?? false).toBe(b.wanted === b.asset.id);
      expect(state.models.find((m: any) => m.id === b.fallbackAssetId)?.active ?? false).toBe(b.wanted === b.fallbackAssetId);
    }
    for (const id of owned) expect(state.activeFootprintIds).toContain(id);
    for (const id of raw) expect(state.activeFootprintIds).not.toContain(id);
    expect(errors).toEqual([]);
    const directory = 'tests/screenshots/prestige28'; mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${scenario.name}.png` });
    writeFileSync(`${directory}/${scenario.name}.json`, JSON.stringify({ wanted, failedIds, owned, raw, errors, state }, null, 2) + '\n');
  });
}
