import { test, expect, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const samples = [
  { site: 'mokdong-hyperion-2', prefix: 'bespoke-mokdong-hyperion-2-', numbers: ['201','202','203','204'], center: [126.87035,37.52417], old: 'apt-a15805111' },
  { site: 'mokdong-trapalace', prefix: 'bespoke-mokdong-trapalace-', numbers: ['western-a','western-b','eastern-a','eastern-b','podium'], center: [126.87095,37.526], old: 'apt-a15870101' },
  { site: 'lotte-castle-empire', prefix: 'bespoke-lotte-castle-empire-', numbers: ['101','102','common'], center: [126.92637,37.52027], old: 'apt-a15088614' },
  { site: 'mecenatpolis', prefix: 'bespoke-mecenatpolis-', numbers: ['101','102','103','residential-podium'], center: [126.9139379,37.5513225], old: 'apt-a12174601' },
  { site: 'lotte-castle-ivy', prefix: 'bespoke-lotte-castle-ivy-', numbers: ['101','102','connector'], center: [126.9317762,37.52018955], old: 'apt-a15088915' },
  { site: 'gratte-ciel', prefix: 'bespoke-gratte-ciel-', numbers: ['101','102','103','104'], center: [127.043016,37.577328], old: 'apt-a10023188' },
  { site: 'trimage', prefix: 'bespoke-trimage-', numbers: ['101','102','103','104'], center: [127.044915,37.538834], old: 'apt-a10026988' },
  { site: 'raemian-caelitus', prefix: 'bespoke-raemian-caelitus-', numbers: ['101','102','103'], center: [126.98002,37.51733], old: 'apt-a10027908' },
];
const directory = 'tests/screenshots/apartments-400';

async function setup(page: Page, center: number[]) {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels);
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e: HTMLInputElement) => { e.value='1';e.dispatchEvent(new Event('input')); });
  await page.evaluate(center => (window as any).__SEOUL_MAP__.map.jumpTo({ center, zoom:16.5, pitch:52, bearing:20 }), center);
}
async function state(page: Page) {
  return page.evaluate(() => {
    const api=(window as any).__SEOUL_MAP__, city=api.cityModels, s=city.getState();
    return { ...s, renderedSolids:[...new Set(api.map.queryRenderedFeatures(undefined,{layers:['building-solids']}).map((f:any)=>f.properties.id))] };
  });
}

for (const sample of samples) {
  test(`${sample.site}: every named tower draws without its old compound`, async ({page}) => {
    test.setTimeout(120_000); mkdirSync(directory,{recursive:true});
    const errors:string[]=[]; page.on('pageerror',e=>errors.push(e.message));
    const ids=sample.numbers.map(n=>sample.prefix+n);
    for(const id of ids) expect(manifest.assets.some((a:any)=>a.id===id),`published ${id}`).toBe(true);
    await setup(page,sample.center);
    await page.waitForFunction(ids=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&ids.every(id=>s.models.some((m:any)=>m.id===id&&m.active&&m.drawCount>0));},ids,{timeout:90_000});
    const s=await state(page);
    expect(s.models.find((m:any)=>m.id===sample.old)?.active??false).toBe(false);
    expect(s.models.filter((m:any)=>m.error)).toEqual([]);
    for(const id of ids) for(const fid of manifest.assets.find((a:any)=>a.id===id).footprintIds) {
      expect(s.activeFootprintIds).toContain(fid);
      expect(s.renderedSolids).not.toContain(fid);
    }
    if(sample.site==='mokdong-trapalace') expect(s.models.find((m:any)=>m.id==='bespoke-mokdong-hyperion-2-203')?.active).toBe(true);
    if(sample.site==='mokdong-hyperion-2') expect(s.models.find((m:any)=>m.id==='fallback-hyperion-ii-officetels')?.active).toBe(true);
    if(sample.site==='lotte-castle-empire') {
      expect(s.models.find((m:any)=>m.id==='fallback-miseong-a')?.active).toBe(true);
      expect(s.activeFootprintIds).toContain('2dd7515f-ae2d-4bec-a511-5398d365e039');
    }
    if(sample.site==='mecenatpolis') {
      expect(s.activeFootprintIds).not.toContain('b028f776-57de-460a-ad6f-4f0919b2d0e7');
      expect(s.renderedSolids).toContain('b028f776-57de-460a-ad6f-4f0919b2d0e7');
      expect(s.models.find((m:any)=>m.id==='survey-upis-32688666')?.active).toBe(true);
    }
    if(sample.site==='raemian-caelitus') {
      expect(s.models.find((m:any)=>m.id==='apt-a14003002')?.active).toBe(true);
      expect(s.models.find((m:any)=>m.id==='fallback-caelitus-101')?.active??false).toBe(false);
    }
    expect(s.models.filter((m:any)=>m.active).length).toBeLessThanOrEqual(32);
    expect(errors).toEqual([]);
    await page.screenshot({path:`${directory}/${sample.site}.png`});
    writeFileSync(`${directory}/${sample.site}.json`,JSON.stringify({ids,active:s.models.filter((m:any)=>m.active),owned:s.activeFootprintIds,pageErrors:errors},null,2)+'\n');
  });

  test(`${sample.site}: one missing replacement retains the complete fallback`, async ({page}) => {
    test.setTimeout(120_000); mkdirSync(directory,{recursive:true});
    const ids=sample.numbers.map(n=>sample.prefix+n);
    const failed=sample.site==='raemian-caelitus'?sample.prefix+'102':ids[0];
    const a=manifest.assets.find((a:any)=>a.id===failed);
    expect(a).toBeTruthy();
    await page.route(`**/models/${a.model}`,r=>r.fulfill({status:404,body:'intentional missing asset'}));
    await setup(page,sample.center);
    await page.waitForFunction(({failed,old})=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&s.models.some((m:any)=>m.id===failed&&m.error)&&s.models.some((m:any)=>m.id===old&&m.active);},{failed,old:sample.old},{timeout:90_000});
    const s=await state(page);
    const peers=sample.site==='raemian-caelitus'?['102','103'].map(n=>sample.prefix+n):ids;
    for(const id of peers) expect(s.models.find((m:any)=>m.id===id)?.active??false).toBe(false);
    if(sample.site==='mokdong-hyperion-2') expect(s.models.find((m:any)=>m.id==='fallback-hyperion-ii-officetels')?.active).toBe(true);
    if(sample.site==='lotte-castle-empire') expect(s.models.find((m:any)=>m.id==='fallback-miseong-a')?.active).toBe(true);
    if(sample.site==='raemian-caelitus') expect(s.models.find((m:any)=>m.id==='apt-a14003002')?.active).toBe(true);
    await page.screenshot({path:`${directory}/${sample.site}-fallback.png`});
    writeFileSync(`${directory}/${sample.site}-fallback.json`,JSON.stringify({failed,old:sample.old,active:s.models.filter((m:any)=>m.active),errors:s.models.filter((m:any)=>m.error)},null,2)+'\n');
  });
}

for(const missing of [false,true])test(`galleria-palace: ${missing?'one absent tower restores only its source solid':'three towers and lower wings draw'}`,async({page})=>{
  test.setTimeout(120_000);mkdirSync(directory,{recursive:true});
  const ids=['a','b','c','common'].map(n=>'bespoke-galleria-palace-'+n),failed=ids[0];
  const a=manifest.assets.find((m:any)=>m.id===failed),errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  if(missing)await page.route(`**/models/${a.model}`,r=>r.fulfill({status:404,body:'intentional missing A tower'}));
  await setup(page,[127.0939498,37.5111075]);
  await page.waitForFunction(({ids,missing})=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&ids.every((id:string,i:number)=>s.models.some((m:any)=>m.id===id&&(missing&&i===0?!!m.error:m.active&&m.drawCount>0)));},{ids,missing},{timeout:90_000});
  const s=await state(page);
  for(const id of ids.slice(0,3)){
    const fid=manifest.assets.find((m:any)=>m.id===id).footprintIds[0];
    if(missing&&id===failed){expect(s.activeFootprintIds).not.toContain(fid);expect(s.renderedSolids).toContain(fid);}
    else {expect(s.activeFootprintIds).toContain(fid);expect(s.renderedSolids).not.toContain(fid);}
  }
  for(const parent of ['17b59b77-985e-4929-b581-d2748f5007c1','6a3cd638-944e-4a9f-8bb6-7a704303b642'])expect(s.activeFootprintIds).not.toContain(parent);
  expect(s.models.filter((m:any)=>m.error).map((m:any)=>m.id)).toEqual(missing?[failed]:[]);expect(errors).toEqual([]);
  const name=`galleria-palace${missing?'-fallback':''}`;
  await page.screenshot({path:`${directory}/${name}.png`});
  writeFileSync(`${directory}/${name}.json`,JSON.stringify({ids,missing:missing?failed:null,active:s.models.filter((m:any)=>m.active),owned:s.activeFootprintIds,renderedSolids:s.renderedSolids,pageErrors:errors},null,2)+'\n');
});
