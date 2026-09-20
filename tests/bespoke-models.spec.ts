import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json','utf8'));
async function setup(page: any) {
  await page.goto('/'); await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels);
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e: HTMLInputElement) => {e.value='1';e.dispatchEvent(new Event('input'));});
}
async function move(page: any, center: number[], zoom: number, bearing = 25) {
  await page.evaluate(({center,zoom,bearing}: any) => (window as any).__SEOUL_MAP__.map.jumpTo({center,zoom,pitch:55,bearing}),{center,zoom,bearing});
}
async function snapshot(page: any) {
  return page.evaluate(() => {
    const api=(window as any).__SEOUL_MAP__,state=api.cityModels.getState();
    const sources=api.map.querySourceFeatures('building-data').map((f: any)=>f.properties);
    return {models:state.models.filter((m:any)=>m.active||m.error),footprints:state.activeFootprintIds,
      sources:[...new Set(sources.map((p:any)=>String(p.id)))],
      sourceStates:sources.filter((p:any)=>p.id==='a78efc86-7dae-4e63-8e4b-d672a7eff741').map((p:any)=>({id:p.id,heightStatus:p.height_status,extrude:p.extrude})),
      solidParents:[...new Set(api.map.queryRenderedFeatures(undefined,{layers:['building-solids']}).map((f:any)=>String(f.properties.parent_id)))],
      solids:[...new Set(api.map.queryRenderedFeatures(undefined,{layers:['building-solids']}).map((f:any)=>String(f.properties.id)))],
      resident:state.models.filter((m:any)=>m.loaded).length,loading:state.loading};
  });
}

test('eight individually rebuilt sites replace only their owned geometry and retain neighbouring buildings', async ({page}) => {
  test.setTimeout(300_000);await setup(page);mkdirSync('tests/screenshots',{recursive:true});const results=[];
  for(const sample of [
    {site:'terminal',center:[127.0062,37.5054],zoom:16.8,ids:['bespoke-seoul-express-terminal'],source:['c313b964-022c-4f5a-9599-d69d0155d010'],old:[]},
    {site:'skyl65',center:[127.04515,37.5788],zoom:16.5,ids:['bespoke-skyl65-a','bespoke-skyl65-b','bespoke-skyl65-c','bespoke-skyl65-d'],source:['2b68ae2e-2c06-48b5-885e-149a84aea147','64b81053-77b5-474e-9511-4613763e9659','9da9e8a3-a799-43a6-9aed-552bc7577042','de59be43-3b37-45f7-bc6c-894a5680db1f'],old:['reference-flight-cheongnyangni-skyl65','apt-a10023083']},
    {site:'hyperion',center:[126.87497,37.52697],zoom:16.5,ids:['bespoke-hyperion-a','bespoke-hyperion-b','bespoke-hyperion-c','bespoke-hyperion-parking-podium','bespoke-hyperion-department-store'],source:['d17a295c-c15f-459a-99f0-78bd56c3155b','070fa936-533e-4489-8ed1-2b391e7cd6b4','7b59ea22-2e4d-41cb-a79b-c2893081c113','c7f66902-54ea-4bac-ae09-73a57bdf98b7'],old:['reference-flight-hyperion','apt-a15805114','survey-upis-32702773']},
    {site:'seoul284',center:[126.97158,37.555877],zoom:17.5,ids:['bespoke-culture-station-seoul284'],source:['d8469ff5-7c6b-4514-8e0d-da239407bbda','36356163-6139-3732-A335-333337356337'],old:['reference-flight-seoul-station']},
    {site:'maple',center:[127.01307870765513,37.51157245048949],zoom:16.4,ids:[203,204,207,208,209,210,211,212,214,215].map(n=>'bespoke-maple-xi-'+n).concat('bespoke-maple-xi-213-corrected'),source:[],old:[203,204,207,208,209,210,211,212,213,214,215].map(n=>'maple-xi-'+n).concat('bespoke-maple-xi-213')},
    {site:'tower-palace',center:[127.05402372516996,37.48850111478948],zoom:16.2,ids:['a','b','c','d','e','f','g'].map(n=>'bespoke-tower-palace-'+n),source:['9197849d-bf83-4832-9abe-0e78bd90981c','995d5ddd-41d8-44aa-89d0-78b5b8207de6','2d2c76d4-7f8d-48f7-895a-eb2cd30da173','acdd801b-57dc-4384-b867-3cef5d194fa9','0aa4cf05-c633-4f2b-83c5-604b8629272d','c6873a11-88e5-4129-bc93-19bc68cd7bd5','0279553d-08e7-48de-bd31-6016d2b5445c'],old:['reference-flight-tower-palace','apt-a13585402','apt-a13585403']},
    {site:'city-hall',center:[126.9782,37.56658],zoom:17.2,ids:['bespoke-seoul-city-hall-new','bespoke-seoul-city-hall-library'],source:['93725b2d-b39e-490f-bc2e-77536fc0d0c4','c1e08f26-ebe0-4a95-827d-c617ca8b3d5f','bb10e1bc-1807-41fc-87c5-3bdac2090c9c'],old:['reference-flight-seoul-city-hall','civic-93725b2d-b39e-490f-bc2e-77536fc0d0c4','landmark-c1e08f26-ebe0-4a95-827d-c617ca8b3d5f']},
    {site:'banpo-jamsu',center:[126.996466,37.514546],zoom:15.4,ids:['bespoke-banpo-jamsu'],source:[],old:['bridge-way-1085504592','bridge-way-1091571021']},
  ]) {
    await move(page,sample.center,sample.zoom,sample.site==='seoul284'?-90:25);
    await page.waitForFunction(ids => {const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&ids.every(id=>s.models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0));},sample.ids,{timeout:60_000});
    await page.waitForLoadState('networkidle');const s=await snapshot(page);
    for(const id of sample.old)expect(s.models.filter((m:any)=>m.active).map((m:any)=>m.id)).not.toContain(id);
    for(const id of sample.source){expect(s.sources).toContain(id);expect(s.footprints).toContain(id);expect(s.solids).not.toContain(id);}
    expect(s.resident).toBeLessThanOrEqual(48);
    expect(s.models.filter((m:any)=>m.active).length).toBeLessThanOrEqual(32);
    expect(s.models.filter((m:any)=>m.error)).toEqual([]);
    if(sample.site==='skyl65')for(const id of ['ccde143f-4ead-46da-97b5-873021cf0e49','604860f1-8f91-4420-8769-69f9d09b059f']) {
      expect(s.sources).toContain(id);expect(s.footprints).not.toContain(id);expect(s.solids).toContain(id);
    }
    if(sample.site==='hyperion') {
      const id='c7f66902-54ea-4bac-ae09-73a57bdf98b7';
      const department=manifest.assets.find((a:any)=>a.id==='bespoke-hyperion-department-store');
      expect(department.footprintIds).toContain(id);expect(department.supersedes).toContain('survey-upis-32702773');
      expect(s.footprints).toContain(id);expect([...s.solids,...s.solidParents]).not.toContain(id);
    }
    if(sample.site==='maple') {
      const towers=s.models.filter((m:any)=>m.active&&/^(?:bespoke-)?maple-xi-\d+(?:-corrected)?$/.test(m.id));
      expect(towers).toHaveLength(29);
      expect(towers.filter((m:any)=>m.id.startsWith('bespoke-'))).toHaveLength(11);
      expect(towers.filter((m:any)=>m.id.startsWith('maple-'))).toHaveLength(18);
    }
    if(sample.site==='seoul284') {const id='a78efc86-7dae-4e63-8e4b-d672a7eff741';expect(s.sources).toContain(id);expect(s.footprints).not.toContain(id);expect(s.sourceStates.every((p:any)=>p.heightStatus==='missing'&&p.extrude===false)).toBe(true);}
    if(sample.site==='terminal')expect(s.models.some((m:any)=>m.id==='reference-flight-central-city'&&m.active)).toBe(true);
    await page.screenshot({path:`tests/screenshots/bespoke-${sample.site}.png`});results.push({site:sample.site,...s,solids:s.solids.filter(id=>sample.source.includes(id as string)),sources:sample.source});
  }
  writeFileSync('docs/model-audit/browser-check.json',JSON.stringify(results,null,2)+'\n');
});

test('one failed SKY tower retains the entire older reference without mixed versions',async({page})=>{
  test.setTimeout(120_000);const a=manifest.assets.find((a:any)=>a.id==='bespoke-skyl65-c');
  await page.route(`**/models/${a.model}`,route=>route.fulfill({status:404,body:'intentional fallback fixture'}));
  await setup(page);await move(page,[127.04515,37.5788],16.5);
  await page.waitForFunction(()=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&s.models.some((m:any)=>m.id==='reference-flight-cheongnyangni-skyl65'&&m.active)&&s.models.some((m:any)=>m.id==='bespoke-skyl65-c'&&m.error);},undefined,{timeout:60_000});
  const s=await snapshot(page);expect(s.models.filter((m:any)=>m.active&&m.id.startsWith('bespoke-skyl65'))).toEqual([]);
  await page.screenshot({path:'tests/screenshots/bespoke-partial-failure.png'});
});

for (const fixture of [
  {site:'tower-palace',failed:'bespoke-tower-palace-g',prefix:'bespoke-tower-palace-',old:'reference-flight-tower-palace',center:[127.05402372516996,37.48850111478948],zoom:16.2},
  {site:'city-hall',failed:'bespoke-seoul-city-hall-library',prefix:'bespoke-seoul-city-hall-',old:'reference-flight-seoul-city-hall',center:[126.9782,37.56658],zoom:17.2},
]) test(`${fixture.site} partial HTTP404 retains its entire original compound`,async({page})=>{
  test.setTimeout(120_000);
  const asset=manifest.assets.find((a:any)=>a.id===fixture.failed);
  await page.route(`**/models/${asset.model}`,route=>route.fulfill({status:404,body:'intentional split-compound fallback fixture'}));
  await setup(page);await move(page,fixture.center,fixture.zoom);
  await page.waitForFunction(({old,failed})=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&s.models.some((m:any)=>m.id===old&&m.active&&m.drawCount>0)&&s.models.some((m:any)=>m.id===failed&&m.error);},fixture,{timeout:60_000});
  const s=await snapshot(page);
  expect(s.models.filter((m:any)=>m.active&&m.id.startsWith(fixture.prefix))).toEqual([]);
  await page.screenshot({path:`tests/screenshots/bespoke-${fixture.site}-partial-failure.png`});
});
