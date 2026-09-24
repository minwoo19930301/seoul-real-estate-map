import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8'));
const numbers = Array.from({ length: 15 }, (_, i) => 100 + i);
const latestId = (n: number) => `bespoke-acro-riverpark-${n}${[100, 109].includes(n) ? '-corrected' : ''}`;
const correction = corrections.corrections.find((c: any) => c.sourceId === 'apt-a10027205');
const allAssets = [...manifest.assets, ...correction.assets];
const byId = new Map<string, any>(allAssets.map((a: any) => [a.id, a]));
const retained = byId.get('apt-a10027205');
const connector = 'ce2823b4-6bb2-4b4a-b1f6-21f035384ce1';
const neighbor = '8be35ba6-cad9-427a-b6c9-21b83caf3501';
const scenarios = [
  { name: 'normal', failedIds: [] },
  { name: 'corrected100-unavailable', failedIds: [latestId(100)] },
  { name: 'both109-generations-unavailable', failedIds: [latestId(109), 'bespoke-acro-riverpark-109'] },
  { name: 'low105-unavailable', failedIds: [latestId(105)] },
  { name: '110-with-connector-unavailable', failedIds: [latestId(110)] },
  { name: '110-and-fallback-unavailable', failedIds: [latestId(110), 'fallback-acro-riverpark-110'] },
  { name: 'all15-latest-unavailable', failedIds: numbers.map(latestId) },
];

for (const { name, failedIds } of scenarios) {
  test(`Acro all15 towers: ${name}`, async ({ page }) => {
    test.setTimeout(180_000);
    const assets = numbers.map(n => byId.get(latestId(n)));
    const failed = new Set(failedIds);
    const failedEntries = failedIds.map(id => byId.get(id));
    const desired = new Map<number, string | null>();
    const chains = new Map<number, string[]>();
    for (let i = 0; i < assets.length; i++) {
      const asset = assets[i]; const number = numbers[i];
      expect(asset, `${number} present`).toBeTruthy();
      expect(asset.footprintIds).toEqual(byId.get(`fallback-acro-riverpark-${number}`).footprintIds);
      const chain: string[] = []; let entry = asset;
      while (entry) {
        expect(chain).not.toContain(entry.id);
        chain.push(entry.id);
        entry = entry.supersedes?.length ? byId.get(entry.supersedes[0]) : null;
      }
      chains.set(number, chain);
      desired.set(number, chain.find(id => !failed.has(id)) ?? null);
    }
    expect(retained.footprintIds).toEqual([neighbor]);
    expect(assets.find((a: any) => a.id === latestId(110)).footprintIds).toContain(connector);
    const sourceIds = assets.flatMap((a: any) => a.footprintIds);
    expect(sourceIds).toHaveLength(16);
    expect(new Set(sourceIds).size).toBe(16);
    expect(sourceIds).not.toContain(neighbor);
    for (const asset of failedEntries) {
      expect(asset).toBeTruthy();
      await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional Acro generation failure' }));
    }
    const pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9937, 37.5057], zoom: 16.45, pitch: 55, bearing: 30 }));
    const wanted = [...desired.values()].filter((id): id is string => id !== null).concat(retained.id);
    const rawFailures = assets.filter((_: any, i: number) => desired.get(numbers[i]) === null).flatMap((a: any) => a.footprintIds);
    const owned = sourceIds.filter((id: string) => !rawFailures.includes(id)).concat(neighbor);
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds }, { timeout: 130_000 });
    await page.waitForFunction(({ owned, rawFailures }) => {
      const map = (window as any).__SEOUL_MAP__.map;
      const features = map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      // 110's child metre heights are absent in the raw dataset; those source
      // features correctly fall back to footprints, not invented extrusions.
      const raw = map.queryRenderedFeatures(undefined, { layers: ['building-solids', 'building-footprints'] });
      return owned.every(id => !features.some((f: any) => f.properties.id === id || f.properties.parent_id === id))
        && rawFailures.every(id => raw.some((f: any) => f.properties.id === id || f.properties.parent_id === id));
    }, { owned, rawFailures }, { timeout: 15_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    for (const [number, chain] of chains) {
      for (const id of chain) expect(state.models.find((m: any) => m.id === id)?.active ?? false, id).toBe(id === desired.get(number));
    }
    for (const id of owned) expect(state.activeFootprintIds).toContain(id);
    for (const id of rawFailures) expect(state.activeFootprintIds).not.toContain(id);
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id).sort()).toEqual([...failedIds].sort());
    expect(pageErrors).toEqual([]);
    const directory = 'tests/screenshots/acro-all15'; mkdirSync(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${name}.png` });
    writeFileSync(`${directory}/${name}.json`, JSON.stringify({ wanted, failedIds, rawFailures, active: state.models.filter((m: any) => m.active), owned: state.activeFootprintIds, pageErrors }, null, 2) + '\n');
  });
}
