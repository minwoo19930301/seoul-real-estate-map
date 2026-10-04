import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8'));
const numbers = Array.from({ length: 23 }, (_, i) => 101 + i);
const fallbacks = corrections.corrections.flatMap((c: any) => c.assets).filter((a: any) => a.id.startsWith('fallback-onebailey-'));
const scenarios = [[], [101], [123], [110], [114], [113, 114, 115, 116], Array.from({ length: 12 }, (_, i) => 109 + i)]
  .map(missing => ({ missing, missingFallbacks: [] as number[] }));
scenarios.push({ missing: [115], missingFallbacks: [115] });

for (const { missing, missingFallbacks } of scenarios) {
  test(`OneBailey all23 towers: ${missing.length ? `models ${missing.join(',')}${missingFallbacks.length ? ` and fallbacks ${missingFallbacks.join(',')}` : ''} unavailable` : 'all models draw'}`, async ({ page }) => {
    test.setTimeout(180_000);
    const assets = numbers.map(n => manifest.assets.find((a: any) => a.id === `bespoke-raemian-onebailey-${n}`));
    assets.forEach((a: any, i: number) => {
      expect(a).toBeTruthy();
      expect(a.supersedes).toEqual([`fallback-onebailey-${numbers[i]}`]);
      expect(fallbacks.find((f: any) => f.id === a.supersedes[0])?.footprintIds).toEqual(a.footprintIds);
    });
    const failed = assets.filter((a: any) => missing.some(n => a.id === `bespoke-raemian-onebailey-${n}`));
    const failedFallbacks = fallbacks.filter((a: any) => missingFallbacks.some(n => a.id === `fallback-onebailey-${n}`));
    const failedFallbackIds = new Set(failedFallbacks.map((a: any) => a.id));
    const failedEntries = [...failed, ...failedFallbacks];
    for (const asset of failedEntries) await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional individual family failure' }));
    const pageErrors: string[] = [];
    page.on('pageerror', e => pageErrors.push(e.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9981, 37.5068], zoom: 16.25, pitch: 55, bearing: 208 }));
    const wanted = assets.flatMap((a: any) => failed.includes(a) ? a.supersedes.filter((id: string) => !failedFallbackIds.has(id)) : [a.id]);
    const rawFailures = failed.filter((a: any) => a.supersedes.every((id: string) => failedFallbackIds.has(id))).flatMap((a: any) => a.footprintIds);
    const owned = assets.flatMap((a: any) => a.footprintIds).filter((id: string) => !rawFailures.includes(id));
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds: failedEntries.map((a: any) => a.id) }, { timeout: 130_000 });
    await page.waitForFunction((ownedIds: string[]) => {
      const map = (window as any).__SEOUL_MAP__.map;
      const rendered = map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      return ownedIds.every(id => !rendered.some((f: any) => f.properties.id === id || f.properties.parent_id === id));
    }, owned, { timeout: 15_000 });
    await page.waitForFunction((rawIds: string[]) => {
      const features = (window as any).__SEOUL_MAP__.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] });
      return rawIds.every(id => features.some((f: any) => f.properties.id === id || f.properties.parent_id === id));
    }, rawFailures, { timeout: 15_000 });
    const state = await page.evaluate(() => {
      const api = (window as any).__SEOUL_MAP__;
      return { ...api.cityModels.getState(), renderedSolids: [...new Set(api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).flatMap((f: any) => [f.properties.id, f.properties.parent_id].filter(Boolean)))] };
    });
    for (const asset of assets) {
      expect(state.models.find((m: any) => m.id === asset.id)?.active ?? false).toBe(!failed.includes(asset));
      expect(state.models.find((m: any) => m.id === asset.supersedes[0])?.active ?? false).toBe(failed.includes(asset) && !failedFallbackIds.has(asset.supersedes[0]));
      for (const id of asset.footprintIds) {
        if (rawFailures.includes(id)) {
          expect(state.activeFootprintIds).not.toContain(id);
          expect(state.renderedSolids).toContain(id);
        } else {
          expect(state.activeFootprintIds).toContain(id);
          expect(state.renderedSolids).not.toContain(id);
        }
      }
    }
    expect(fallbacks).toHaveLength(23);
    expect(fallbacks.some((a: any) => a.id === 'apt-a10023043')).toBe(false);
    expect(state.models.find((m: any) => m.id === 'apt-a10023043')?.active ?? false).toBe(false);
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id).sort()).toEqual(failedEntries.map((a: any) => a.id).sort());
    expect(pageErrors).toEqual([]);
    const directory = 'tests/screenshots/onebailey-all23'; mkdirSync(directory, { recursive: true });
    const key = missing.length ? `missing-${missing.join('-')}${missingFallbacks.length ? `-and-fallback-${missingFallbacks.join('-')}` : ''}` : 'normal';
    await page.screenshot({ path: `${directory}/${key}.png` });
    writeFileSync(`${directory}/${key}.json`, JSON.stringify({ wanted, failedIds: failedEntries.map((a: any) => a.id), rawFailures, renderedSolids: state.renderedSolids, active: state.models.filter((m: any) => m.active), owned: state.activeFootprintIds, pageErrors }, null, 2) + '\n');
  });
}
