import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const candidates=JSON.parse(readFileSync('docs/residential-model-candidates.json','utf8'));
const assets=JSON.parse(readFileSync('public/models/manifest.json','utf8')).assets;
const samples=[
 candidates.find((c:any)=>c.kind==='villa' && c.sourceName && c.floors>=3 && c.floors<=5),
 candidates.find((c:any)=>c.kind==='villa' && c.sourceClass==='terrace' && !c.sourceName),
 candidates.find((c:any)=>c.kind==='apartment' && c.complex?.householdCount>0 && c.complex.householdCount<=100),
 candidates.find((c:any)=>c.kind==='mixed-use' && c.sourceName?.includes('주상복합')),
 candidates.find((c:any)=>c.kind==='officetel' && c.sourceName?.includes('르메이에르')),
 candidates.find((c:any)=>c.hasParts && c.heightM>0),
];
test('new residential types, small official complexes and source building parts render at actual source locations',async({page})=>{
 test.setTimeout(180_000);const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await page.waitForFunction(()=>{const a=(window as any).__SEOUL_MAP__;return a?.cityModels && a.getState().terrainReady;});
 await page.locator('#mode-25d').click();
 await page.locator('#exaggeration').evaluate((input:HTMLInputElement)=>{input.value='1';input.dispatchEvent(new Event('input'));});
 mkdirSync('tests/screenshots',{recursive:true});const results=[];
 for(let i=0;i<samples.length;i++){
  const c=samples[i];expect(c).toBeTruthy();const asset=assets.find((a:any)=>a.id===c.id);
  await page.evaluate((a:any)=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[a.coordinate.lon,a.coordinate.lat],zoom:Math.max(16.6,Math.min(19,20.4-Math.log2(a.dimensions[1]/12))),pitch:58,bearing:25}),asset);
  await page.waitForFunction(id=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading && s.models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0);},asset.id,{timeout:35_000});
  await page.waitForLoadState('networkidle');
  const state=await page.evaluate(id=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return {total:s.models.length,loaded:s.models.filter((m:any)=>m.loaded).length,active:s.models.filter((m:any)=>m.active).length,errors:s.models.filter((m:any)=>m.error),model:s.models.find((m:any)=>m.id===id),footprints:s.activeFootprintIds};},asset.id);
  expect(state.total).toBeGreaterThanOrEqual(13607);expect(state.loaded).toBeLessThanOrEqual(48);expect(state.active).toBeLessThanOrEqual(32);expect(state.errors).toEqual([]);
  expect(state.model.height_m).toBe(asset.dimensions[1]);expect(state.model.ground_m).not.toBeNull();
  for(const bid of c.buildingIds)expect(state.footprints).toContain(bid);
  await page.screenshot({path:`tests/screenshots/residential-${i}-${c.kind}.png`});
  results.push({id:c.id,name:c.nameKo,kind:c.kind,householdCount:c.complex?.householdCount,hasParts:c.hasParts,model:state.model,loaded:state.loaded,active:state.active});
 }
 const last=samples.at(-1);
 await page.locator('#toggle-city-models').uncheck();
 await expect.poll(()=>page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
 await page.locator('#toggle-city-models').check();
 await page.waitForFunction(id=>(window as any).__SEOUL_MAP__.cityModels.getState().models.some((m:any)=>m.id===id&&m.active),last.id);
 expect(errors).toEqual([]);
 writeFileSync('docs/residential-browser-check.json',JSON.stringify({models:assets.length,results,boundedCache:true,hideRestoresSourceFootprints:true,pageErrors:errors},null,2)+'\n');
});
