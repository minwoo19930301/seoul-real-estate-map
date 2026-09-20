import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const manifest=JSON.parse(readFileSync('public/models/bespoke-manifest.json','utf8'));
for(const site of [
  {id:'maple',query:'메이플자이',count:2,modelIds:['bespoke-maple-xi-207','bespoke-maple-xi-213-corrected'],failedId:'bespoke-maple-xi-213-corrected'},
  {id:'lotte-castle-ivy',query:'여의도 롯데캐슬아이비',count:3},
  {id:'gratte-ciel',query:'청량리역 한양수자인 그라시엘',count:4},
  {id:'trimage',query:'서울숲 트리마제',count:4},
  {id:'raemian-caelitus',query:'래미안 첼리투스',count:3},
]) for(const missing of [false,true]) test(`Public UI ${site.id} ${missing?'missing asset':'normal'}`,async({page})=>{
  test.setTimeout(120_000);
  const models=manifest.assets.filter((a:any)=>site.modelIds ? site.modelIds.includes(a.id) : a.id.startsWith(`bespoke-${site.id}-`));
  const failed=models.find((a:any)=>site.failedId ? a.id===site.failedId : a.id.endsWith(site.id==='raemian-caelitus'?'102':'101'));
  const statuses:Record<string,number>={},errors:string[]=[];
  page.on('response',r=>{if(r.url().includes('/models/'))statuses[new URL(r.url()).pathname]=r.status();});
  page.on('pageerror',e=>errors.push(e.message));
  if(missing)await page.route(`**/models/${failed.model}`,r=>r.fulfill({status:404,body:'intentional missing asset'}));
  await page.goto('/');
  await expect(page.locator('#mode-25d')).toBeEnabled({timeout:30_000});
  if(await page.locator('#mode-25d').getAttribute('aria-pressed')!=='true')await page.locator('#mode-25d').click();
  await page.locator('#exaggeration').evaluate((e:HTMLInputElement)=>{e.value='1';e.dispatchEvent(new Event('input'));});
  await page.locator('#place-search').fill(site.query);
  await page.locator('#place-search').press('Enter');
  await expect(page.locator('#place-title')).toContainText(site.query,{timeout:30_000});
  await expect.poll(()=>models.filter((a:any)=>statuses['/models/'+a.model]===(missing&&a.id===failed.id?404:200)).length,{timeout:60_000}).toBe(site.count);
  for(const close of await page.locator('.maplibregl-popup-close-button').all())await close.click();
  await page.waitForTimeout(2500);
  expect(errors).toEqual([]);
  const dir='tests/screenshots/apartments-public';mkdirSync(dir,{recursive:true});
  const key=`${site.id}-${missing?'fallback':'normal'}`;
  await page.screenshot({path:`${dir}/${key}.png`});
  writeFileSync(`${dir}/${key}.json`,JSON.stringify({url:page.url(),site:site.id,missing:missing?failed.id:null,resourceStatus:statuses,pageErrors:errors,scope:'Production UI and asset responses; model ownership/fallback draw state tested separately in local development build.'},null,2)+'\n');
});
