import { test, expect, type Page } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/manifest.json', 'utf8'));
const references = JSON.parse(readFileSync('public/models/reference-manifest.json', 'utf8'));
const assets = [...references.assets, ...manifest.assets];
const originals = ['sixtythree', 'lotte', 'nseoul', 'coex', 'gyeongbokgung'];
// Observed source identities, independent of the publisher's supersedes/coverage list.
const cases = [
  { id: 'reference-flight-dcube-city', sourceIds: ['85db7664-8f97-4739-a0b9-e6d36c2be470'] },
  { id: 'reference-flight-dongnimmun', sourceIds: ['820d282e-dcb9-4186-baff-425cb01fbe58'] },
  { id: 'reference-flight-cheongwadae', sourceIds: ['c4dcbadb-1db4-4f64-a89d-541529a582f4'], requireRenderedChildren: true },
  { id: 'reference-flight-jongno-tower', sourceIds: ['34656333-6530-3064-B662-313932333736', '30663634-3164-3230-B130-396264656463'] },
  { id: 'reference-flight-gfc', sourceIds: ['8c853160-e816-4fa5-9bc8-37d2a4902c39'] },
  { id: 'reference-flight-myeongdong-cathedral', sourceIds: ['2723fab9-38dc-4308-830a-748355caca48'] },
  { id: 'reference-flight-samsung-town', sourceIds: ['11ce39b4-914d-469e-b321-645439192b79', '1e2fbefc-05ec-4d57-9c2a-0698e4fea262', 'acb69099-3808-4569-9eeb-acabb692f3bf'] },
  { id: 'reference-flight-cheongnyangni-skyl65', sourceIds: ['2b68ae2e-2c06-48b5-885e-149a84aea147', '64b81053-77b5-474e-9511-4613763e9659', '9da9e8a3-a799-43a6-9aed-552bc7577042'], genericIds: ['apt-a10023083'] },
  { id: 'reference-flight-hyperion', sourceIds: ['d17a295c-c15f-459a-99f0-78bd56c3155b'], genericIds: ['apt-a15805114', 'survey-upis-32702773'] },
  { id: 'coex', sourceIds: ['61626436-3139-3031-B836-373735653536'] },
  { id: 'lotte', sourceIds: ['63646261-6332-3535-A430-633337356430'] },
];

async function setup(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e: HTMLInputElement) => { e.value = '1'; e.dispatchEvent(new Event('input')); });
}
async function move(page: Page, asset: any, waitForActive = true) {
  await page.evaluate((a: any) => (window as any).__SEOUL_MAP__.map.jumpTo({
    center: [a.coordinate.lon, a.coordinate.lat], zoom: a.dimensions[1] > 400 ? 15.9 : a.dimensions[1] > 180 ? 16.7 : 17.1, pitch: 52, bearing: 25,
  }), asset);
  if (waitForActive) {
    await page.waitForFunction(id => { const s = (window as any).__SEOUL_MAP__.cityModels.getState(); return !s.loading && s.models.some((m: any) => m.id === id && m.active && m.drawCount > 0); }, asset.id, { timeout: 60_000 });
    await page.waitForLoadState('networkidle');
  }
}
async function snapshot(page: Page) {
  return page.evaluate((originals: string[]) => {
    const api = (window as any).__SEOUL_MAP__, city = api.cityModels, state = city.getState();
    const entries = city.entries as any[];
    const owners = entries.filter(e => e.active && (e.asset.quality === 'reference' || originals.includes(e.asset.id)));
    const footprints = (e: any): string[] => [...new Set([...(e.asset.footprintIds ?? []), ...(city.matches[e.asset.id] ?? [])])];
    const protectedIds = new Set(owners.flatMap(footprints));
    const genericCollisions = entries.filter(e => e.active && e.asset.quality !== 'reference' && !originals.includes(e.asset.id))
      .map(e => ({ id: e.asset.id, name: e.asset.nameKo, sharedFootprints: footprints(e).filter(fid => protectedIds.has(fid)) })).filter(e => e.sharedFootprints.length);
    const sources = [...new Map(api.map.querySourceFeatures('building-data').map((f: any) => [String(f.properties.id), f.properties])).values()] as any[];
    const rendered = [...new Set(api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).map((f: any) => String(f.properties.id)))] as string[];
    return { active: state.models.filter((m: any) => m.active).map((m: any) => m.id), activeFootprintIds: state.activeFootprintIds, genericCollisions,
      sourceProperties: sources, renderedSolidIds: rendered, solidFilter: api.map.getFilter('building-solids'),
      models: state.models.filter((m: any) => m.active || m.error), loading: state.loading, error: state.error };
  }, originals);
}

function evidence(s: any, ids: string[]) {
  return { ...s, sourceCount: s.sourceProperties.length, renderedSolidCount: s.renderedSolidIds.length,
    sourceProperties: s.sourceProperties.filter((p: any) => ids.includes(p.id) || ids.includes(p.parent_id)),
    renderedSolidIds: s.renderedSolidIds.filter((id: string) => ids.includes(id)) };
}

 test('authored landmarks suppress independently identified source parts and generic GLBs', async ({ page }) => {
  test.setTimeout(300_000); mkdirSync('tests/screenshots', { recursive: true });
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await setup(page); const results: any[] = [];
  for (const sample of cases) {
    const asset = assets.find((a: any) => a.id === sample.id); await move(page, asset);
    const s = await snapshot(page);
    for (const fid of sample.sourceIds) {
      expect.soft(s.sourceProperties.some(p => p.id === fid), `${sample.id}: fixture source ${fid} is loaded`).toBe(true);
      expect.soft(s.renderedSolidIds, `${sample.id}: old source ${fid} must not draw`).not.toContain(fid);
      const source = s.sourceProperties.find(p => p.id === fid);
      expect.soft(s.activeFootprintIds.includes(fid) || (!!source?.parent_id && s.activeFootprintIds.includes(source.parent_id)), `${sample.id}: source is owned directly or through its parent`).toBe(true);
    }
    if (sample.requireRenderedChildren) {
      const children = s.sourceProperties.filter(p => sample.sourceIds.includes(p.parent_id) && p.height_status === 'reported' && p.extrude !== false);
      expect.soft(children.length, `${sample.id}: independently linked extrudable child geometry is loaded`).toBeGreaterThan(0);
      for (const child of children) expect.soft(s.renderedSolidIds, `${sample.id}: owned child ${child.id} must not draw`).not.toContain(child.id);
    }
    for (const id of sample.genericIds ?? []) expect.soft(s.active, `${sample.id}: overlapping generic ${id}`).not.toContain(id);
    expect.soft(s.genericCollisions, `${sample.id}: all active generic models sharing a protected source`).toEqual([]);
    await page.screenshot({ path: `tests/screenshots/overlap-after-${sample.id.replace('reference-flight-', '')}.png` });
    results.push({ id: sample.id, expectedSourceIds: sample.sourceIds, ...evidence(s, sample.sourceIds) });
    if (sample.id === 'reference-flight-jongno-tower') {
      await page.locator('#toggle-city-models').uncheck();
      await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
      await expect.poll(async () => { const off = await snapshot(page); return sample.sourceIds.every(id => off.renderedSolidIds.includes(id)); }).toBe(true);
      const off = await snapshot(page); results.push({ id: 'jongno-disabled-restores-source', ...evidence(off, sample.sourceIds) });
      await page.locator('#toggle-city-models').check(); await move(page, asset);
    }
  }
  expect.soft(errors).toEqual([]);
  writeFileSync('docs/landmark-overlap-browser-check.json', JSON.stringify({ results, pageErrors: errors }, null, 2) + '\n');
});

test('reference ownership preserves unrelated buildings inside large illustration bounds', async ({ page }) => {
  test.setTimeout(120_000); await setup(page); const results: any[] = [];
  for (const sample of [
    { id: 'reference-flight-amorepacific-hq', neighbor: 'e33a76b0-dca2-453b-bb0e-94adab1680c4', label: 'LS용산타워' },
    { id: 'reference-flight-garden-five', neighbor: 'ff6bff59-b677-475e-ad56-f54e43db2a5a', label: '파크하비오 102동' },
  ]) {
    const asset = assets.find((a: any) => a.id === sample.id); await move(page, asset); const s = await snapshot(page);
    const represented = await page.evaluate(({fid, subject}: {fid: string; subject: string}) => { const api = (window as any).__SEOUL_MAP__, city = api.cityModels;
      const source = api.map.querySourceFeatures('building-data').find((f: any) => f.properties.id === fid);
      const raw = api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).some((f: any) => f.properties.id === fid || f.properties.parent_id === fid);
      const generic = city.entries.some((e: any) => e.active && e.asset.quality !== 'reference' && [...(e.asset.footprintIds ?? []), ...(city.matches[e.asset.id] ?? [])].includes(fid));
      const wrongOwners = city.entries.filter((e: any) => e.active && e.asset.id === subject && (e.asset.footprintIds ?? []).includes(fid)).map((e: any) => e.asset.id);
      const correctReference = city.entries.some((e: any) => e.active && e.asset.id === 'reference-flight-park-habio' && (e.asset.footprintIds ?? []).includes(fid));
      return { sourceLoaded: !!source, raw, generic, correctReference, wrongOwners };
    }, {fid: sample.neighbor, subject: sample.id});
    expect.soft(represented.sourceLoaded, `${sample.label} source exists`).toBe(true);
    expect.soft(represented.raw || represented.generic || represented.correctReference, `${sample.label} remains represented`).toBe(true);
    expect.soft(represented.wrongOwners, `${sample.label} must not be claimed by an unrelated reference`).toEqual([]);
    await page.screenshot({ path: `tests/screenshots/overlap-after-${sample.id.replace('reference-flight-', '')}-neighbors.png` });
    results.push({ ...sample, represented, ...evidence(s, [sample.neighbor]) });
  }
  writeFileSync('docs/landmark-overlap-neighbors-check.json', JSON.stringify(results, null, 2) + '\n');
});

test('pending or HTTP404 reference keeps its original solid visible', async ({ page }) => {
  test.setTimeout(120_000); const asset = assets.find((a: any) => a.id === 'reference-flight-gfc');
  const fid = '8c853160-e816-4fa5-9bc8-37d2a4902c39'; let release!: () => void; let requested = false;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(`**/models/${asset.model}`, async route => { requested = true; await gate; await route.fulfill({ status: 404, body: 'intentional overlap regression fixture' }); });
  try {
    await setup(page); await move(page, asset, false); await expect.poll(() => requested).toBe(true);
    await expect.poll(async () => (await snapshot(page)).renderedSolidIds.includes(fid), { timeout: 30_000 }).toBe(true);
    const pending = await snapshot(page); expect(pending.activeFootprintIds).not.toContain(fid); expect(pending.active).not.toContain(asset.id);
    release();
    await page.waitForFunction(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.some((m: any) => m.id === id && m.error?.includes('404')), asset.id);
    await expect.poll(async () => (await snapshot(page)).renderedSolidIds.includes(fid)).toBe(true);
    const failed = await snapshot(page); expect(failed.activeFootprintIds).not.toContain(fid); expect(failed.active).not.toContain(asset.id);
    await page.screenshot({ path: 'tests/screenshots/overlap-reference-404-fallback.png' });
    writeFileSync('docs/landmark-overlap-fallback-check.json', JSON.stringify({ pending: evidence(pending, [fid]), failed: evidence(failed, [fid]) }, null, 2) + '\n');
  } finally { release(); }
});
