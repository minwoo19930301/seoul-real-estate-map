import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const read=(name:string)=>JSON.parse(readFileSync(`public/models/${name}`,'utf8'));
test('historical representatives coexist with protected bespoke apartments',async({page})=>{
 test.setTimeout(180000);
 const bespoke=read('bespoke-manifest.json').assets;
 const protectedIds=new Set([...bespoke,...read('reference-manifest.json').assets].flatMap((a:any)=>a.footprintIds??[]));
 const historic=read('representative-manifest.json').assets;
 const retained=historic.find((a:any)=>!a.footprintIds.some((id:string)=>protectedIds.has(id)));
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.cityModels && (window as any).__SEOUL_MAP__?.getState().terrainReady);
 if(await page.locator('#mode-25d').getAttribute('aria-pressed')!=='true')await page.locator('#mode-25d').click();
 for(const asset of [retained,bespoke.find((a:any)=>a.id==='bespoke-lake-palace-107')]){
  await page.evaluate((c:any)=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[c.lon,c.lat],zoom:17.5,pitch:50}),asset.coordinate);
  await page.waitForFunction((id:string)=>(window as any).__SEOUL_MAP__.cityModels.getState().models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0),asset.id,{timeout:90000});
 }
 const ids=await page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.entries.map((e:any)=>e.asset.id));
 expect(ids).toContain(retained.id);
 for(const asset of historic.filter((a:any)=>a.footprintIds.some((id:string)=>protectedIds.has(id))))expect(ids).not.toContain(asset.id);
 expect(errors).toEqual([]);
});
