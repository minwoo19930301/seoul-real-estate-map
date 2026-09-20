import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const bespoke=JSON.parse(readFileSync('public/models/bespoke-manifest.json','utf8')).assets;
const corrections=JSON.parse(readFileSync('public/models/generic-corrections.json','utf8')).corrections;
const samples=[
 {site:'onepentas',prefix:'bespoke-raemian-onepentas-',numbers:['105','106'],center:[126.9937,37.5041],compound:'apt-a10022556',neighbor:'fallback-prestige-126'},
];
for(const site of samples)for(const missing of [false,true])test(`${site.site}: ${missing?'one failed tower restores only its own fallback':'reviewed towers preserve unfinished neighbors'}`,async({page})=>{
 test.setTimeout(150_000);
 const assets=site.numbers.map(n=>bespoke.find((a:any)=>a.id===site.prefix+n));
 for(const a of assets)expect(a).toBeTruthy();
 const failed=assets[0],errors:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 if(missing)await page.route(`**/models/${failed.model}`,r=>r.fulfill({status:404,body:'intentional missing apartment tower'}));
 await page.goto('/');
 await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.getState().terrainReady);
 await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.cityModels);
 if(await page.locator('#mode-25d').getAttribute('aria-pressed')!=='true')await page.locator('#mode-25d').click();
 await page.locator('#exaggeration').evaluate((e:HTMLInputElement)=>{e.value='1';e.dispatchEvent(new Event('input'));});
 await page.evaluate(center=>(window as any).__SEOUL_MAP__.map.jumpTo({center,zoom:16.8,pitch:55,bearing:5}),site.center);
 await page.waitForFunction(({ids,failed,missing,compound,neighbor})=>{
  const s=(window as any).__SEOUL_MAP__.cityModels.getState(),draws=(id:string)=>s.models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0);
  return !s.loading&&draws(compound)&&(!neighbor||draws(neighbor))&&ids.every((id:string)=>missing&&id===failed?s.models.some((m:any)=>m.id===id&&m.error):draws(id));
 },{ids:assets.map((a:any)=>a.id),failed:failed.id,missing,compound:site.compound,neighbor:site.neighbor},{timeout:100_000});
 const state=await page.evaluate(()=>{
  const api=(window as any).__SEOUL_MAP__;
  return {...api.cityModels.getState(),renderedSolids:[...new Set(api.map.queryRenderedFeatures(undefined,{layers:['building-solids']}).map((f:any)=>f.properties.id))]};
 });
 for(const a of assets){
  const fallback=a.supersedes[0],isFailed=missing&&a.id===failed.id;
  expect(state.models.find((m:any)=>m.id===a.id)?.active??false).toBe(!isFailed);
  expect(state.models.find((m:any)=>m.id===fallback)?.active??false).toBe(isFailed);
  for(const fid of a.footprintIds){expect(state.activeFootprintIds).toContain(fid);expect(state.renderedSolids).not.toContain(fid);}
 }
 const retained=corrections.find((c:any)=>c.sourceId===site.compound).assets.filter((a:any)=>a.id===site.compound||a.id===site.neighbor);
 for(const a of retained){
  expect(state.models.find((m:any)=>m.id===a.id)?.active).toBe(true);
  for(const fid of a.footprintIds)expect(state.activeFootprintIds).toContain(fid);
 }
 expect(state.models.filter((m:any)=>m.error).map((m:any)=>m.id)).toEqual(missing?[failed.id]:[]);
 expect(errors).toEqual([]);
 const directory='tests/screenshots/banpo-bespoke';mkdirSync(directory,{recursive:true});
 const key=site.site+'-'+(missing?'fallback':'normal');
 await page.screenshot({path:`${directory}/${key}.png`});
 writeFileSync(`${directory}/${key}.json`,JSON.stringify({site:site.site,missing:missing?failed.id:null,active:state.models.filter((m:any)=>m.active),owned:state.activeFootprintIds,renderedSolids:state.renderedSolids,errors:state.models.filter((m:any)=>m.error),pageErrors:errors},null,2)+'\n');
});
