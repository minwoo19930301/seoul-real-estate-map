import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const base = read('public/models/manifest.json').assets;
const sources = read('docs/model-audit/acro-riverview-source-identity.json').towers;
const byId = new Map<string, any>([...base, ...corrections.flatMap((c: any) => c.assets), ...authored].map((a: any) => [a.id, a]));
const numbers = Array.from({length:5}, (_,i)=>101+i);
const scenarios = [
 {name:'normal',fail:[] as number[],raw:[] as number[]},
 {name:'representative-fallback',fail:[101],raw:[] as number[]},
 {name:'two-archive-mixed-fallbacks',fail:[102,104],raw:[] as number[]},
 {name:'104-raw-restoration',fail:[104],raw:[104]},
 {name:'all5-fallbacks',fail:numbers,raw:[] as number[]},
];

for (const scenario of scenarios) {
  test(`Acro Riverview distinct towers: ${scenario.name}`, async ({ page }) => {
    test.setTimeout(180_000);
    const family = numbers.map(number => {
      const source = sources.find((s: any) => s.number === number);
      const asset = byId.get(`bespoke-acro-riverview-${number}`);
      expect(asset, `${number} published`).toBeTruthy();
      expect(asset.footprintIds).toEqual([source.sourceId]);
      expect(asset.supersedes).toHaveLength(1);
      const fallback = byId.get(asset.supersedes[0]);
      expect(fallback.footprintIds).toEqual([source.sourceId]);
      return { number, source, asset, fallback };
    });
    const residual = byId.get('apt-a10026227');
    expect(residual.footprintIds).toHaveLength(2);
    expect(residual.footprintIds.some((id: string) => sources.some((s: any) => s.sourceId === id))).toBe(false);
    expect(byId.get('apt-a13790723').nameKo).toBe('신반포5차');
    const failedIds = family.flatMap(b => scenario.fail.includes(b.number)
      ? [b.asset.id, ...(scenario.raw.includes(b.number) ? [b.fallback.id] : [])] : []);
    for (const id of failedIds) {
      await page.route(`**/models/${byId.get(id).model}`, route => route.fulfill({ status: 404, body: 'intentional Acro Riverview model failure' }));
    }
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(center => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom: 16.25, pitch: 50, bearing: 170 }), [127.00695,37.5145]);
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
    expect(state.models.find((m: any)=>m.id==='apt-a13790723')?.active ?? false).toBe(false);
    expect(errors).toEqual([]);
    const directory = 'tests/screenshots/acro-riverview5'; mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${scenario.name}.png` });
    writeFileSync(`${directory}/${scenario.name}.json`, JSON.stringify({ wanted, failedIds, owned, raw, errors, state }, null, 2) + '\n');
  });
}
