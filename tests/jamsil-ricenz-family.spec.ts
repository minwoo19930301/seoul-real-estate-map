import { test, expect, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { applyGenericCorrections } from '../src/generic-corrections.ts';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const base = read('public/models/manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const identity = read('docs/model-audit/jamsil-ricenz-source-identity.json');
const bindings = read('docs/model-audit/jamsil-ricenz-fallback-bindings.json').bindings;
const effective = applyGenericCorrections(base, read('public/models/footprint-matches.json'), {version:1,corrections});
const byId = new Map<string, any>([...effective.assets, ...authored].map((a: any) => [a.id, a]));
const numbers = Array.from({length: 65}, (_, i) => 201 + i).filter(n => ![263, 265].includes(n));
const directory = 'tests/screenshots/jamsil-ricenz63';

function family() {
  return numbers.map(number => {
    const source = identity.towers.find((s: any) => s.number === number);
    const asset = byId.get(`bespoke-jamsil-ricenz-${number}`);
    expect(asset, `${number} published`).toBeTruthy();
    const binding = bindings.find((b: any) => b.number === number);
    const fallback = byId.get(binding.fallbackAssetId);
    expect(asset.footprintIds).toEqual([source.sourceId]);
    expect(asset.supersedes).toEqual([fallback.id]);
    expect(fallback.footprintIds).toEqual([source.sourceId]);
    return {number, source, asset, fallback};
  });
}
async function boot(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
  if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => { el.value = '1'; el.dispatchEvent(new Event('input')); });
  return errors;
}
async function focus(page: Page, coordinate: {lon: number; lat: number}) {
  await page.evaluate(c => (window as any).__SEOUL_MAP__.map.jumpTo({center: [c.lon, c.lat], zoom: 17, pitch: 50, bearing: 165}), coordinate);
}
async function awaitModel(page: Page, id: string) {
  await page.waitForFunction(id => {
    const s = (window as any).__SEOUL_MAP__.cityModels.getState();
    return !s.loading && s.models.some((m: any) => m.id === id && m.active && m.drawCount > 0);
  }, id, {timeout: 130_000});
}
async function snapshot(page: Page, name: string, proof: unknown) {
  mkdirSync(directory, {recursive: true});
  await page.screenshot({path: `${directory}/${name}.png`});
  writeFileSync(`${directory}/${name}.json`, JSON.stringify(proof, null, 2) + '\n');
}
for (const failAll of [false, true]) {
  test(`Ricenz all63 visible across camera traversal: ${failAll ? 'fallbacks' : 'authored'}`, async ({page}) => {
    test.setTimeout(600_000);
    const rows = family();
    if (failAll) for (const b of rows) await page.route(`**/models/${b.asset.model}`, route => route.fulfill({status: 404, body: 'intentional Ricenz authored failure'}));
    const errors = await boot(page), seen = new Set<string>(), visits: any[] = [];
    const wanted = rows.map(b => (failAll ? b.fallback : b.asset).id);
    for (const b of rows) {
      const id = (failAll ? b.fallback : b.asset).id;
      if (seen.has(id)) continue;
      await focus(page, b.asset.coordinate);
      await awaitModel(page, id);
      // MapLibre applies its updated footprint filter on the next rendered frame.
      await page.waitForFunction(bindings => {
        const api = (window as any).__SEOUL_MAP__, s = api.cityModels.getState();
        const rendered = api.map.queryRenderedFeatures(undefined, {layers: ['building-solids']});
        return !s.loading && bindings.every(({id, sourceId}) => {
          const m = s.models.find((m: any) => m.id === id);
          return !m?.active || !rendered.some((f: any) => f.properties.id === sourceId || f.properties.parent_id === sourceId);
        });
      }, rows.map(r => ({id: (failAll ? r.fallback : r.asset).id, sourceId: r.source.sourceId})), {timeout: 15_000});
      const state = await page.evaluate(wanted => {
        const api = (window as any).__SEOUL_MAP__, s = api.cityModels.getState();
        const active = s.models.filter((m: any) => wanted.includes(m.id) && m.active && m.drawCount > 0);
        const raw = api.map.queryRenderedFeatures(undefined, {layers: ['building-solids']}).map((f: any) => f.properties.id);
        return {active: active.map((m: any) => m.id), footprints: s.activeFootprintIds, raw};
      }, wanted);
      for (const aid of state.active) {
        seen.add(aid);
        const row = rows.find(r => (failAll ? r.fallback : r.asset).id === aid)!;
        expect(state.footprints).toContain(row.source.sourceId);
        expect(state.raw).not.toContain(row.source.sourceId);
      }
      visits.push({centerTower: b.number, active: state.active});
      if (visits.length <= 3) await snapshot(page, `${failAll ? 'fallbacks' : 'normal'}-view${visits.length}`, {visits, errors});
    }
    expect([...seen].sort()).toEqual([...wanted].sort());
    expect(errors).toEqual([]);
    await snapshot(page, `${failAll ? 'fallbacks' : 'normal'}-complete`, {seen: [...seen], visits, errors});
  });
}
for (const scenario of [
  {name: 'representative218-fallback', fail: [218], raw: [] as number[]},
  {name: 'mixed201-218-241-fallbacks', fail: [201, 218, 241], raw: [] as number[]},
  {name: '218-raw-restoration', fail: [218], raw: [218]},
]) {
  test(`Ricenz independent failure: ${scenario.name}`, async ({page}) => {
    test.setTimeout(360_000);
    const rows = family(), targets = rows.filter(r => scenario.fail.includes(r.number));
    for (const b of targets) for (const asset of [b.asset, ...(scenario.raw.includes(b.number) ? [b.fallback] : [])]) {
      await page.route(`**/models/${asset.model}`, route => route.fulfill({status: 404, body: 'intentional independent Ricenz failure'}));
    }
    const errors = await boot(page), checks: any[] = [];
    for (const b of targets) {
      await focus(page, b.asset.coordinate);
      if (!scenario.raw.includes(b.number)) await awaitModel(page, b.fallback.id);
      await page.waitForFunction(({asset, fallback, sourceId, raw}) => {
        const api = (window as any).__SEOUL_MAP__, s = api.cityModels.getState();
        const a = s.models.find((m: any) => m.id === asset), f = s.models.find((m: any) => m.id === fallback);
        const rendered = api.map.queryRenderedFeatures(undefined, {layers: ['building-solids']}).some((v: any) => v.properties.id === sourceId || v.properties.parent_id === sourceId);
        return a?.error && !a.active && (raw ? f?.error && !f.active && rendered && !s.activeFootprintIds.includes(sourceId) : f?.active && !rendered && s.activeFootprintIds.includes(sourceId));
      }, {asset: b.asset.id, fallback: b.fallback.id, sourceId: b.source.sourceId, raw: scenario.raw.includes(b.number)}, {timeout: 130_000});
      checks.push({number: b.number, sourceId: b.source.sourceId, restoredTo: scenario.raw.includes(b.number) ? 'raw-map' : b.fallback.id});
    }
    expect(errors).toEqual([]);
    await snapshot(page, scenario.name, {checks, errors});
  });
}
test('Ricenz withheld263/265 remain visible in the preserved residual', async ({page}) => {
  test.setTimeout(180_000);
  const errors = await boot(page), checks: any[] = [];
  const residuals = identity.excludedTowers.map((excluded: any) => effective.assets.find(a => a.footprintIds?.includes(excluded.sourceId)));
  for (const excluded of identity.excludedTowers) {
    expect(residuals.some((a: any) => a.footprintIds.includes(excluded.sourceId))).toBe(true);
    expect(authored.some((a: any) => a.id === `bespoke-jamsil-ricenz-${excluded.number}`)).toBe(false);
  }
  const bounds = residuals.map((a: any) => a.geoBounds);
  await page.evaluate(bounds => (window as any).__SEOUL_MAP__.map.fitBounds([
    [Math.min(...bounds.map((b: number[])=>b[0])),Math.min(...bounds.map((b: number[])=>b[1]))],
    [Math.max(...bounds.map((b: number[])=>b[2])),Math.max(...bounds.map((b: number[])=>b[3]))],
  ],{padding:100,maxZoom:18,pitch:35,bearing:0,duration:0}),bounds);
  for (const residual of residuals) await awaitModel(page, residual.id);
  const state = await page.evaluate(ids => {
    const s = (window as any).__SEOUL_MAP__.cityModels.getState();
    return {activeFootprintIds: s.activeFootprintIds, residuals: s.models.filter((m: any) => ids.includes(m.id)).map((m: any) => ({id:m.id,active:m.active,drawCount:m.drawCount}))};
  }, residuals.map((a: any)=>a.id));
  for (const excluded of identity.excludedTowers) expect(state.activeFootprintIds).toContain(excluded.sourceId);
  expect(errors).toEqual([]);
  checks.push({withheld: identity.excludedTowers.map((e: any) => e.number), ...state});
  await snapshot(page, 'withheld263-265', {checks, errors});
});
