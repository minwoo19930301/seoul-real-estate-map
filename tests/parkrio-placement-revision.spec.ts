import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const assets=JSON.parse(readFileSync('public/models/bespoke-manifest.json','utf8')).assets;
test('Parkrio four revised placements draw once with old copies hidden',async({page})=>{
 test.setTimeout(180_000);
 const rows=assets.filter((a:any)=>a.sourceRecord.siteId==='jamsil-parkrio-placement-v2');expect(rows).toHaveLength(4);
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
 if(await page.locator('#mode-25d').getAttribute('aria-pressed')!=='true')await page.locator('#mode-25d').click();
 const b=rows.map((a:any)=>a.geoBounds);
 await page.evaluate(b=>(window as any).__SEOUL_MAP__.map.fitBounds([[Math.min(...b.map((v:number[])=>v[0])),Math.min(...b.map((v:number[])=>v[1]))],[Math.max(...b.map((v:number[])=>v[2])),Math.max(...b.map((v:number[])=>v[3]))]],{padding:150,maxZoom:18,pitch:35,bearing:0,duration:0}),b);
 await page.waitForFunction(rows=>{
  const api=(window as any).__SEOUL_MAP__,state=api.cityModels.getState();
  return rows.every((a:any)=>state.models.some((m:any)=>m.id===a.id && m.active && m.drawCount>0) && !state.models.some((m:any)=>a.supersedes.includes(m.id)&&m.active));
 },rows,{timeout:130_000});
 const state=await page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.getState());
 expect(errors).toEqual([]);mkdirSync('tests/screenshots/shared-apartment-instances',{recursive:true});
 await page.screenshot({path:'tests/screenshots/shared-apartment-instances/parkrio-placement-v2.png'});
 writeFileSync('tests/screenshots/shared-apartment-instances/parkrio-placement-v2.json',JSON.stringify({rows:rows.map((a:any)=>({id:a.id,revision:a.sourceRecord.placementRevision})),active:state.models.filter((m:any)=>m.active).map((m:any)=>m.id),errors},null,2)+'\n');
});
