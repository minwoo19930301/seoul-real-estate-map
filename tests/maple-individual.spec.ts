import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const manifest=JSON.parse(readFileSync('public/models/bespoke-manifest.json','utf8'));
const numbers=[...Array.from({length:14},(_,i)=>101+i),...Array.from({length:15},(_,i)=>201+i)];
for(const scenario of [
  ...[208,209,212].flatMap(number=>[
    {number,failed:[`bespoke-maple-xi-${number}-corrected`],wanted:`bespoke-maple-xi-${number}`},
    {number,failed:[`bespoke-maple-xi-${number}-corrected`,`bespoke-maple-xi-${number}`],wanted:`maple-xi-${number}`},
  ]),
  ...[205,206].flatMap(number=>[{number,failed:[],wanted:`bespoke-maple-xi-${number}`},{number,failed:[`bespoke-maple-xi-${number}`],wanted:`maple-xi-${number}`}]),
  {number:203,failed:[],wanted:'bespoke-maple-xi-203'},
  {number:203,failed:['bespoke-maple-xi-203'],wanted:'maple-xi-203'},
  {number:214,failed:[],wanted:'bespoke-maple-xi-214'},
  {number:214,failed:['bespoke-maple-xi-214'],wanted:'maple-xi-214'},
  {number:215,failed:[],wanted:'bespoke-maple-xi-215'},
  {number:215,failed:['bespoke-maple-xi-215'],wanted:'maple-xi-215'},
  {number:204,failed:[],wanted:'bespoke-maple-xi-204'},
  {number:204,failed:['bespoke-maple-xi-204'],wanted:'maple-xi-204'},
  {number:207,failed:[],wanted:'bespoke-maple-xi-207'},
  {number:207,failed:['bespoke-maple-xi-207'],wanted:'maple-xi-207'},
  {number:213,failed:[],wanted:'bespoke-maple-xi-213-corrected'},
  {number:213,failed:['bespoke-maple-xi-213-corrected'],wanted:'bespoke-maple-xi-213'},
  {number:213,failed:['bespoke-maple-xi-213-corrected','bespoke-maple-xi-213'],wanted:'maple-xi-213'},
]) test(`Maple${scenario.number} ${scenario.failed.length} failed generations preserve all29 towers`,async({page})=>{
  test.setTimeout(120_000);
  for(const id of scenario.failed){const a=manifest.assets.find((a:any)=>a.id===id);await page.route(`**/models/${a.model}`,r=>r.fulfill({status:404,body:'intentional missing generation'}));}
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.waitForFunction(()=>(window as any).__SEOUL_MAP__?.cityModels);
  await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e:HTMLInputElement)=>{e.value='1';e.dispatchEvent(new Event('input'));});
  await page.evaluate(()=>(window as any).__SEOUL_MAP__.map.jumpTo({center:[127.01307870765513,37.51157245048949],zoom:16.4,pitch:52,bearing:25}));
  const wanted=scenario.wanted;
  await page.waitForFunction(wanted=>{const s=(window as any).__SEOUL_MAP__.cityModels.getState();return !s.loading&&s.models.some((m:any)=>m.id===wanted&&m.active&&m.drawCount>0);},wanted,{timeout:90_000});
  const s=await page.evaluate(()=>(window as any).__SEOUL_MAP__.cityModels.getState());
  const towers=s.models.filter((m:any)=>m.active&&/^(?:bespoke-)?maple-xi-\d+(?:-corrected)?$/.test(m.id));
  expect(towers).toHaveLength(29);
  for(const n of numbers)expect(towers.filter((m:any)=>new RegExp(`maple-xi-${n}(?:-corrected)?$`).test(m.id)),`exactly one visible${n}`).toHaveLength(1);
  expect(towers.some((m:any)=>m.id===wanted)).toBe(true);
  for(const n of [208,209,210,211,212])if(n!==scenario.number)expect(towers.some((m:any)=>m.id===`bespoke-maple-xi-${n}${[208,209,212].includes(n)?'-corrected':''}`)).toBe(true);
  for(const id of scenario.failed)expect(s.models.find((m:any)=>m.id===id)?.error).toBeTruthy();
  expect(s.models.filter((m:any)=>m.error&&!scenario.failed.includes(m.id))).toEqual([]);
  expect(s.models.filter((m:any)=>m.active).length).toBeLessThanOrEqual(32);
  expect(errors).toEqual([]);
  const dir='tests/screenshots/maple-individual';mkdirSync(dir,{recursive:true});
  await page.screenshot({path:`${dir}/${scenario.number}-${scenario.failed.length}-failures.png`});
  writeFileSync(`${dir}/${scenario.number}-${scenario.failed.length}-failures.json`,JSON.stringify({active:s.models.filter((m:any)=>m.active),pageErrors:errors},null,2)+'\n');
});
