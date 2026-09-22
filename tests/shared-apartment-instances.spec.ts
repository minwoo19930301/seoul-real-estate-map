import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const read = (p: string) => JSON.parse(readFileSync(p, 'utf8'));
const assets = read('public/models/bespoke-manifest.json').assets;
const families = [
  {site: 'godeok-raemian-hillstate-completion', assetSite: 'godeok-raemian-hillstate', number: 123, count: 18, label: null},
  {site: 'mapo-raemian-prugio-completion', assetSite: 'mapo-raemian-prugio', number: 101, count: 10, label: null},
  {site: 'gaepo-raemian-forest-completion', assetSite: 'gaepo-raemian-forest', number: 128, count: 3, label: null},
  {site: 'raemian-blesstige-completion', assetSite: 'raemian-blesstige', number: 201, count: 2, label: null},
  {site: 'dh-honor-hills-completion', assetSite: 'dh-honor-hills', number: 314, count: 2, label: null},
  {site: 'godeok-arteon-completion', assetSite: 'godeok-arteon', number: 301, count: 16, label: null},
  {site: 'godeok-central-ipark-completion', assetSite: 'godeok-central-ipark', number: 504, count: 1, label: null},
  {site: 'raemian-la-classy-completion', assetSite: 'raemian-la-classy', number: 103, count: 2, label: null},
  {site: 'songpa-helio-city', number: 503, count: 33, label: '416_verified_number_mesh'},
  {site: 'jamsil-parkrio', number: 208, count: 59, label: 'building-number-label'},
  {site: 'jamsil-trizium', number: 305, count: 44, label: 'building-number-label'},
  {site: 'daechi-eunma', number: 12, count: 27, label: 'building-number-label'},
  {site: 'godeok-gracium', number: 102, count: 21, label: null},
  {site: 'raemian-la-classy', number: 101, count: 4, label: null},
  {site: 'godeok-arteon', number: 321, count: 24, label: null},
  {site: 'godeok-raemian-hillstate', number: 102, count: 27, label: null},
  {site: 'godeok-central-ipark', number: 501, count: 17, label: null},
  {site: 'geumho-park-hills', number: 104, count: 15, label: null},
  {site: 'raemian-oksu-riverzen', number: 102, count: 14, label: null},
  {site: 'dmc-parkview-xi', number: 302, count: 5, label: null},
  {site: 'seocho-grand-xi', number: 108, count: 8, label: null},
  {site: 'gaepo-raemian-forest', number: 101, count: 26, label: null},
  {site: 'raemian-blesstige', number: 202, count: 20, label: null},
  {site: 'dh-honor-hills', number: 301, count: 20, label: null},
  {site: 'mapo-raemian-prugio', number: 403, count: 33, label: null},
  {site: 'dmc-parkview-xi-completion', assetSite: 'dmc-parkview-xi', number: 105, count: 22, label: null},
  {site: 'banpo-xi-final', assetSite: 'banpo-xi', number: 103, count: 1, label: null},
  {site: 'mapo-grang-xi', number: 101, count: 14, label: null},
  {site: 'dmc-parkview-xi-extension', assetSite: 'dmc-parkview-xi', number: 103, count: 33, label: null},
];
for (const family of families) for (const failure of ['none', 'shared-model', 'shared-and-fallback']) {
  test(`${family.site} shared copies: ${failure}`, async ({page}) => {
    test.setTimeout(240_000);
    const siblings = assets.filter((a: any) => a.sourceRecord.siteId === `${family.site}-shared`);
    expect(siblings.length).toBe(family.count);
    const target = siblings.find((a: any) => a.id === `bespoke-${family.assetSite ?? family.site}-${family.number}`);
    const binding = read(`docs/model-audit/${family.site}-fallback-bindings.json`).bindings.find((b: any) => b.number === family.number);
    const errors: string[] = [], requests: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if (r.url().endsWith(`/models/${target.model}`)) requests.push(r.url());});
    if (failure !== 'none') await page.route(`**/models/${target.model}`, r => r.fulfill({status:404, body:'intentional shared-model failure'}));
    if (failure === 'shared-and-fallback') await page.route(`**/models/${binding.fallbackModel}`, r => r.fulfill({status:404, body:'intentional one fallback failure'}));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((el: HTMLInputElement) => {el.value='1';el.dispatchEvent(new Event('input'));});
    await page.evaluate(coordinate => (window as any).__SEOUL_MAP__.map.jumpTo({center:[coordinate.lon,coordinate.lat],zoom:17.5,pitch:50,bearing:165}),target.coordinate);
    await page.waitForFunction(({target,binding,failure}) => {
      const api = (window as any).__SEOUL_MAP__, state = api.cityModels.getState();
      const model = state.models.find((m: any) => m.id === target.id), fallback = state.models.find((m: any) => m.id === binding.fallbackAssetId);
      const layer = failure === 'shared-and-fallback' && target.sourceRecord.buildingFacts.sourceHeightM === null ? 'building-footprints' : 'building-solids';
      const raw = api.map.queryRenderedFeatures(undefined,{layers:[layer]}).some((f: any)=>f.properties.id===binding.sourceFootprintId || f.properties.parent_id===binding.sourceFootprintId);
      if (failure === 'none') return model?.active && model.drawCount>0 && !raw && state.activeFootprintIds.includes(binding.sourceFootprintId);
      if (failure === 'shared-model') return model?.error && !model.active && fallback?.active && !raw && state.activeFootprintIds.includes(binding.sourceFootprintId);
      return model?.error && !model.active && fallback?.error && !fallback.active && raw && !state.activeFootprintIds.includes(binding.sourceFootprintId);
    },{target,binding,failure},{timeout:150_000});
    const proof = await page.evaluate(({site,label}) => {
      const api = (window as any).__SEOUL_MAP__, entries = api.cityModels.entries.filter((e: any)=>e.scene && e.asset.sourceRecord?.siteId===`${site}-shared`);
      return entries.map((e: any)=>{
        let geometry: string|undefined, material: string|undefined, labelVisible: boolean|undefined, sourceGeometry: string|undefined, sourceMaterial: string|undefined;
        const source=api.cityModels.entries.find((source: any)=>source.asset.id===e.asset.modelInstance?.sourceAssetId);
        source?.scene?.traverse((o: any)=>{if(o.isMesh && sourceGeometry===undefined){sourceGeometry=o.geometry.uuid;sourceMaterial=o.material.uuid;}});
        e.scene.traverse((o: any)=>{
          if (o.name===label) labelVisible=o.visible;
          if (o.isMesh && o.name!==label && geometry===undefined) {geometry=o.geometry.uuid;material=o.material.uuid;}
        });
        return {id:e.asset.id,geometry,material,sourceGeometry,sourceMaterial,labelVisible,coordinate:e.asset.coordinate,active:e.active};
      });
    },family);
    if (failure === 'none') {
      expect(proof.length).toBeGreaterThanOrEqual(Math.min(2,family.count));
      if(family.count===1){expect(proof[0].sourceGeometry).toBeDefined();expect(proof[0].geometry).toBe(proof[0].sourceGeometry);expect(proof[0].material).toBe(proof[0].sourceMaterial);}
      expect(new Set(proof.map((p: any)=>p.geometry)).size).toBe(1);
      expect(new Set(proof.map((p: any)=>p.material)).size).toBe(1);
      expect(proof.every((p: any)=>p.labelVisible===(family.label ? false : undefined))).toBe(true);
      expect(requests.length).toBe(1);
    }
    expect(errors).toEqual([]);
    const dir='tests/screenshots/shared-apartment-instances';mkdirSync(dir,{recursive:true});
    await page.screenshot({path:`${dir}/${family.site}-${failure}.png`});
    writeFileSync(`${dir}/${family.site}-${failure}.json`,JSON.stringify({family,failure,rawFallbackPrimitive:target.sourceRecord.buildingFacts.sourceHeightM===null?'original 2D footprint; height missing':'original height-reported solid',proof,requests,errors},null,2)+'\n');
  });
}
