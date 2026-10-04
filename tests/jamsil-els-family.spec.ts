import { test, expect, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const authored = read('public/models/bespoke-manifest.json').assets;
const base = read('public/models/manifest.json').assets;
const corrections = read('public/models/generic-corrections.json').corrections;
const identity = read('docs/model-audit/jamsil-els-source-identity.json');
const bindingDocument = read('docs/model-audit/jamsil-els-fallback-bindings.json');
const bindings = bindingDocument.bindings;
const matches = read('public/models/footprint-matches.json');
const byId = new Map<string, any>([...base, ...corrections.flatMap((c: any) => c.assets), ...authored].map((a: any) => [a.id, a]));
const numbers = Array.from({length: 72}, (_, i) => 101 + i);
const directory = 'tests/screenshots/jamsil-els72';

function family() {
  return numbers.map(number => {
    const source = identity.towers.find((s: any) => s.number === number);
    const asset = byId.get(`bespoke-jamsil-els-${number}`);
    expect(asset, `${number} published`).toBeTruthy();
    const binding = bindings.find((b: any) => b.number === number);
    const fallback = byId.get(binding.fallbackAssetId);
    expect(asset.footprintIds).toEqual([source.sourceId]);
    expect(asset.supersedes).toEqual([fallback.id]);
    expect(fallback.footprintIds ?? matches[fallback.id]).toEqual([source.sourceId]);
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
  test(`Els all72 visible across camera traversal: ${failAll ? 'fallbacks' : 'authored'}`, async ({page}) => {
    test.setTimeout(600_000);
    const rows = family();
    if (failAll) for (const b of rows) await page.route(`**/models/${b.asset.model}`, route => route.fulfill({status: 404, body: 'intentional Els authored failure'}));
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
  {name: 'representative120-fallback', fail: [120], raw: [] as number[]},
  {name: 'mixed120-121-122-138-139-fallbacks', fail: [120, 121, 122, 138, 139], raw: [] as number[]},
  {name: '120-121-122-raw-restoration', fail: [120, 121, 122], raw: [120, 121, 122]},
]) {
  test(`Els independent failure: ${scenario.name}`, async ({page}) => {
    test.setTimeout(360_000);
    const rows = family(), targets = rows.filter(r => scenario.fail.includes(r.number));
    for (const b of targets) for (const asset of [b.asset, ...(scenario.raw.includes(b.number) ? [b.fallback] : [])]) {
      await page.route(`**/models/${asset.model}`, route => route.fulfill({status: 404, body: 'intentional independent Els failure'}));
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
test('Els shared138/139 boundary restores138 without hiding139',async({page})=>{
 test.setTimeout(180_000);
 const rows=family(),target=rows.find(r=>r.number===138)!,neighbor=rows.find(r=>r.number===139)!;
 for(const a of [target.asset,target.fallback])await page.route(`**/models/${a.model}`,route=>route.fulfill({status:404,body:'intentional shared-wall138failure'}));
 const errors=await boot(page);await focus(page,target.asset.coordinate);await awaitModel(page,neighbor.asset.id);
 await page.waitForFunction(({target,neighbor})=>{
  const api=(window as any).__SEOUL_MAP__,s=api.cityModels.getState();
  const rendered=api.map.queryRenderedFeatures(undefined,{layers:['building-solids']});
  const has=(id:string)=>rendered.some((f:any)=>f.properties.id===id||f.properties.parent_id===id);
  return s.models.find((m:any)=>m.id===target.asset.id)?.error&&s.models.find((m:any)=>m.id===target.fallback.id)?.error
   &&!s.activeFootprintIds.includes(target.source.sourceId)&&s.activeFootprintIds.includes(neighbor.source.sourceId)
   &&has(target.source.sourceId)&&!has(neighbor.source.sourceId);
 },{target,neighbor},{timeout:130_000});
 expect(errors).toEqual([]);await snapshot(page,'shared138-raw-139-authored',{raw:138,authored:139,errors});
});
test('Els preserves both nonresidential residual footprints',async({page})=>{
 test.setTimeout(180_000);const residual=byId.get('apt-a13822004');
 expect(new Set(residual.footprintIds)).toEqual(new Set(bindingDocument.preservedResidualSourceIds));
 const errors=await boot(page);await focus(page,residual.coordinate);await awaitModel(page,residual.id);
 const state=await page.evaluate(()=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return{activeFootprintIds:s.activeFootprintIds}});
 for(const id of bindingDocument.preservedResidualSourceIds)expect(state.activeFootprintIds).toContain(id);
 expect(errors).toEqual([]);await snapshot(page,'residual-buildings',{residualSourceIds:bindingDocument.preservedResidualSourceIds,...state,errors});
});
