import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const samples=JSON.parse(readFileSync('docs/residential-survey-browser-samples.json','utf8'));

test('official survey housing renders individually with bounded regional metadata and source restoration',async({page})=>{
 test.setTimeout(300_000);
 const errors:string[]=[], failedResponses:{url:string,status:number}[]=[], tileRequests=new Set<string>();
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400)failedResponses.push({url:r.url(),status:r.status()});});
 page.on('request',r=>{if(/\/models\/residential-survey\/tiles\//.test(r.url()))tileRequests.add(r.url());});
 await page.goto('/');
 await page.waitForFunction(()=>{const a=(window as any).__SEOUL_MAP__;return a?.cityModels && a.getState().terrainReady;});
 await page.locator('#mode-25d').click();
 await page.locator('#exaggeration').evaluate((input:HTMLInputElement)=>{input.value='1';input.dispatchEvent(new Event('input'));});
 mkdirSync('tests/screenshots',{recursive:true});const results:any[]=[];
 for(const sample of samples){
  const asset=sample.asset;
  await page.evaluate((a:any)=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[a.coordinate.lon,a.coordinate.lat],zoom:17.8,pitch:48,bearing:25}),asset);
  await page.waitForFunction(id=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading && s.models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0);},asset.id,{timeout:45_000});
  await page.waitForLoadState('networkidle');
  const state=await page.evaluate((a:any)=>{
   const api=(window as any).__SEOUL_MAP__, city=api.cityModels,s=city.getState();
   return {metadataModels:s.models.length,catalogTotal:s.catalogTotal,metadataTiles:city.catalog.tileCount,loaded:s.models.filter((m:any)=>m.loaded).length,active:s.models.filter((m:any)=>m.active).length,errors:s.models.filter((m:any)=>m.error),error:s.error,model:s.models.find((m:any)=>m.id===a.id),footprints:s.activeFootprintIds,terrainAtAnchor:api.map.queryTerrainElevation([a.coordinate.lon,a.coordinate.lat])};
  },asset);
  expect(state.catalogTotal).toBe(113123);expect(state.metadataModels).toBeLessThan(113123);
  expect(state.metadataTiles).toBeLessThanOrEqual(32);expect(state.loaded).toBeLessThanOrEqual(48);expect(state.active).toBeLessThanOrEqual(32);
  expect(state.errors).toEqual([]);expect(state.error).toBeNull();
  expect(state.model.height_m).toBe(asset.dimensions[1]);expect(state.model.ground_m).not.toBeNull();
  expect(state.model.ground_m).toBeCloseTo(state.terrainAtAnchor,3);
  for(const id of asset.footprintIds)expect(state.footprints).toContain(id);
  if(sample.case==='villa-no-overture')expect(asset.footprintIds).toHaveLength(0);
  if(sample.case==='villa-matched')expect(asset.footprintIds.length).toBeGreaterThan(0);
  if(sample.case==='small-apartment'){expect(Number(asset.sourceRecord.register.households)).toBeGreaterThan(0);expect(Number(asset.sourceRecord.register.households)).toBeLessThanOrEqual(100);}
  await page.screenshot({path:`tests/screenshots/survey-${sample.case}.png`});
  results.push({case:sample.case,id:sample.id,name:sample.name,district:sample.district,kind:sample.kind,households:asset.sourceRecord.register?.households,...state});
 }
 const stress:any[]=[];
 for(const sample of [samples[1],samples[3],samples[4],samples[0]]){
  await page.evaluate((a:any)=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[a.coordinate.lon,a.coordinate.lat],zoom:16.6,pitch:58,bearing:25}),sample.asset);
  await page.waitForFunction(()=>!(window as any).__SEOUL_MAP__.cityModels.getState().loading,{},{timeout:45_000});
  await page.waitForLoadState('networkidle');
  const state=await page.evaluate(()=>{const c=(window as any).__SEOUL_MAP__.cityModels,s=c.getState();return {metadataTiles:c.catalog.tileCount,metadataModels:s.models.length,loaded:s.models.filter((m:any)=>m.loaded).length,active:s.models.filter((m:any)=>m.active).length,error:s.error};});
  expect(state.metadataTiles).toBeLessThanOrEqual(32);expect(state.loaded).toBeLessThanOrEqual(48);expect(state.active).toBeLessThanOrEqual(32);expect(state.error).toBeNull();stress.push(state);
 }
 expect(tileRequests.size).toBeGreaterThan(32);expect(tileRequests.size).toBeLessThan(1660);
 const matched=samples.find((s:any)=>s.case==='villa-matched').asset;
 await page.evaluate((a:any)=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[a.coordinate.lon,a.coordinate.lat],zoom:19,pitch:58,bearing:25}),matched);
 await page.waitForFunction(id=>(window as any).__SEOUL_MAP__.cityModels.getState().models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0),matched.id,{timeout:45_000});
 const solidFilterBefore=await page.evaluate(()=>(window as any).__SEOUL_MAP__.map.getFilter('building-solids'));
 for(const id of matched.footprintIds)expect(JSON.stringify(solidFilterBefore)).toContain(id);
 await page.locator('#toggle-city-models').uncheck();
 await expect.poll(()=>page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
 await expect.poll(()=>page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.getState().models.filter((m:any)=>m.active).length)).toBe(0);
 const solidFilterDisabled=await page.evaluate(()=>(window as any).__SEOUL_MAP__.map.getFilter('building-solids'));
 for(const id of matched.footprintIds)expect(JSON.stringify(solidFilterDisabled)).not.toContain(id);
 await page.locator('#toggle-city-models').check();
 await page.waitForFunction((a:any)=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return s.models.some((m:any)=>m.id===a.id&&m.active)&&a.footprintIds.every((id:string)=>s.activeFootprintIds.includes(id));},matched,{timeout:45_000});
 expect(errors).toEqual([]);expect(failedResponses).toEqual([]);
 writeFileSync('docs/residential-survey-browser-check.json',JSON.stringify({catalogModels:113123,newSurveyModels:99516,results,stress,metadataTileRequests:tileRequests.size,metadataCacheLimit:32,glbCacheLimit:48,activeLimit:32,individualTerrainAnchors:true,hideRestoresSourceFootprints:true,solidFilterBefore,solidFilterDisabled,pageErrors:errors,failedResponses},null,2)+'\n');
});
