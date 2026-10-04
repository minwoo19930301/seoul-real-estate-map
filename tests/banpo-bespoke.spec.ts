import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const bespoke = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8')).assets;
const corrections = JSON.parse(readFileSync('public/models/generic-corrections.json', 'utf8')).corrections;
const compoundId = 'apt-a10022556';
const neighborId = 'fallback-prestige-126';
const numbers = ['101', '102', '103', '104', '105', '106'];
for (const missing of [null, '105', '101']) test(`OnePentas six towers: ${missing ? `missing ${missing}` : 'normal'}`, async ({ page }) => {
  test.setTimeout(150_000);
  const assets = numbers.map(n => bespoke.find((a: any) => a.id === `bespoke-raemian-onepentas-${n}`));
  for (const asset of assets) expect(asset).toBeTruthy();
  const failed = missing ? assets[numbers.indexOf(missing)] : null;
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  if (failed) await page.route(`**/models/${failed.model}`, r => r.fulfill({ status: 404, body: 'intentional missing tower' }));
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
  if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e: HTMLInputElement) => { e.value = '1'; e.dispatchEvent(new Event('input')); });
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9937, 37.5041], zoom: 16.8, pitch: 55, bearing: 5 }));
  const failedGroup = failed ? assets.filter((a: any) => a.supersedes.includes(failed.supersedes[0])).map((a: any) => a.id) : [];
  await page.waitForFunction(({ ids, failedId, failedGroup, compoundId, neighborId, fallback }) => {
    const state = (window as any).__SEOUL_MAP__.cityModels.getState();
    const drawn = (id: string) => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0);
    return !state.loading && drawn(neighborId) && (!fallback || drawn(fallback))
      && ids.every((id: string) => failedGroup.includes(id) ? !drawn(id) : drawn(id))
      && (!failedId || state.models.some((m: any) => m.id === failedId && m.error));
  }, { ids: assets.map((a: any) => a.id), failedId: failed?.id, failedGroup, compoundId, neighborId, fallback: failed?.supersedes[0] }, { timeout: 100_000 });
  const state = await page.evaluate(() => {
    const api = (window as any).__SEOUL_MAP__;
    return { ...api.cityModels.getState(), renderedSolids: [...new Set(api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).map((f: any) => f.properties.id))] };
  });
  for (const asset of assets) {
    const replacedByFallback = failedGroup.includes(asset.id);
    expect(state.models.find((m: any) => m.id === asset.id)?.active ?? false).toBe(!replacedByFallback);
    expect(state.models.find((m: any) => m.id === asset.supersedes[0])?.active ?? false).toBe(replacedByFallback);
    for (const fid of asset.footprintIds) {
      expect(state.activeFootprintIds).toContain(fid);
      expect(state.renderedSolids).not.toContain(fid);
    }
  }
  const neighbor = corrections.find((c: any) => c.sourceId === compoundId).assets.find((a: any) => a.id === neighborId);
  expect(state.models.find((m: any) => m.id === neighborId)?.active).toBe(true);
  for (const fid of neighbor.footprintIds) expect(state.activeFootprintIds).toContain(fid);
  expect(state.models.filter((m: any) => m.error).map((m: any) => m.id)).toEqual(failed ? [failed.id] : []);
  expect(errors).toEqual([]);
  const directory = 'tests/screenshots/banpo-bespoke'; mkdirSync(directory, { recursive: true });
  const key = `onepentas-six-${missing ? `missing-${missing}` : 'normal'}`;
  await page.screenshot({ path: `${directory}/${key}.png` });
  writeFileSync(`${directory}/${key}.json`, JSON.stringify({ missing, failedGroup, active: state.models.filter((m: any) => m.active), owned: state.activeFootprintIds, errors: state.models.filter((m: any) => m.error), pageErrors: errors }, null, 2) + '\n');
});
