import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const base = read('public/models/manifest.json').assets;
const sources = read('docs/model-audit/banpo-xi-source-identity.json').towers;
const byId = new Map<string, any>([...base, ...corrections.flatMap((c: any) => c.assets), ...authored].map((a: any) => [a.id, a]));
const numbers = [101, 102, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114];
const east = Array.from({length:15}, (_,i)=>115+i);
const south = Array.from({length:15}, (_,i)=>130+i);
const scenarios = [
  { name: 'normal', numbers, center: [127.0117, 37.5068], fail: [] as number[], raw: [] as number[] },
  { name: 'representative-and-split-fallbacks', numbers, center: [127.0117, 37.5068], fail: [101, 105, 112], raw: [] as number[] },
  { name: 'split105-raw-restoration', numbers, center: [127.0117, 37.5068], fail: [105], raw: [105] },
  { name: 'all13-fallbacks', numbers, center: [127.0117, 37.5068], fail: numbers, raw: [] as number[] },
  { name:'east15-normal', numbers:east, center:[127.0147,37.5074], fail:[] as number[], raw:[] as number[] },
  { name:'east15-mixed-fallbacks', numbers:east, center:[127.0147,37.5074], fail:[116,120,123], raw:[] as number[] },
  { name:'east15-116-and120-raw', numbers:east, center:[127.0147,37.5074], fail:[116,120], raw:[116,120] },
  { name:'south15-normal', numbers:south, center:[127.0163,37.5053], fail:[] as number[], raw:[] as number[] },
  { name:'south15-mixed-fallbacks', numbers:south, center:[127.0163,37.5053], fail:[130,139,142], raw:[] as number[] },
  { name:'south15-130-and142-raw', numbers:south, center:[127.0163,37.5053], fail:[130,142], raw:[130,142] },
];

for (const scenario of scenarios) {
  test(`Banpo Xi distinct towers: ${scenario.name}`, async ({ page }) => {
    test.setTimeout(180_000);
    const family = scenario.numbers.map(number => {
      const source = sources.find((s: any) => s.number === number);
      const asset = byId.get(`bespoke-banpo-xi-${number}`);
      expect(asset, `${number} published`).toBeTruthy();
      expect(asset.footprintIds).toEqual([source.sourceId]);
      expect(asset.supersedes).toHaveLength(1);
      const fallback = byId.get(asset.supersedes[0]);
      expect(fallback.footprintIds).toEqual([source.sourceId]);
      return { number, source, asset, fallback };
    });
    const residual = byId.get('apt-a13704104');
    expect(residual.footprintIds).toHaveLength(16);
    expect(residual.footprintIds.some((id: string) => sources.some((s: any) => s.sourceId === id))).toBe(false);
    expect(byId.get('apt-a10020044').nameKo).toContain('116');
    expect(byId.get('apt-a10020044').apartmentCode).toBeUndefined();
    expect(byId.has('bespoke-banpo-xi-103')).toBe(false);
    const failedIds = family.flatMap(b => scenario.fail.includes(b.number)
      ? [b.asset.id, ...(scenario.raw.includes(b.number) ? [b.fallback.id] : [])] : []);
    for (const id of failedIds) {
      await page.route(`**/models/${byId.get(id).model}`, route => route.fulfill({ status: 404, body: 'intentional Banpo Xi model failure' }));
    }
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(center => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom: 16.65, pitch: 55, bearing: 170 }), scenario.center);
    const desired = family.map(b => ({ ...b,
      wanted: scenario.raw.includes(b.number) ? null : scenario.fail.includes(b.number) ? b.fallback.id : b.asset.id }));
    const wanted = desired.map(b => b.wanted).filter(Boolean).concat(residual.id);
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds }, { timeout: 130_000 });
    const owned = desired.filter(b => b.wanted).map(b => b.source.sourceId).concat(residual.footprintIds);
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
    expect(errors).toEqual([]);
    const directory = 'tests/screenshots/banpo-xi13'; mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${scenario.name}.png` });
    writeFileSync(`${directory}/${scenario.name}.json`, JSON.stringify({ wanted, failedIds, owned, raw, errors, state }, null, 2) + '\n');
  });
}
