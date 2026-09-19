import { test, expect } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const assets = JSON.parse(readFileSync('public/models/manifest.json', 'utf8')).assets;
const samples = [
  assets.find((a: any) => a.id === 'gyeongbokgung'),
  assets.find((a: any) => a.nameKo === '국회의사당'),
  assets.find((a: any) => a.nameKo === '독립문'),
  assets.find((a: any) => a.nameKo === '올림픽체조경기장'),
  assets.find((a: any) => a.nameKo.includes('헬리오')),
  assets.find((a: any) => a.nameKo.includes('경희궁자이2')),
];
test('imported palace and district models render at their actual map locations', async ({ page }) => {
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.cityModels && (window as any).__SEOUL_MAP__.getState().terrainReady);
  await page.locator('#mode-25d').click();
  const results: any[] = [];
  mkdirSync('tests/screenshots', { recursive: true });
  for (const asset of samples) {
    expect(asset).toBeTruthy();
    await page.evaluate((a: any) => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [a.coordinate.lon, a.coordinate.lat], zoom: Math.max(a.dimensions[0], a.dimensions[2]) > 550 ? 15.3 : 16.3, pitch: 58, bearing: -20 }), asset);
    await page.waitForFunction(id => (window as any).__SEOUL_MAP__.cityModels.getState().models.some((m: any) => m.id === id && m.active && m.drawCount > 0), asset.id, { timeout: 35_000 });
    await page.waitForLoadState('networkidle');
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    expect(state.models.length).toBe(255);
    expect(state.models.filter((m: any) => m.loaded).length).toBeLessThanOrEqual(48);
    expect(state.models.filter((m: any) => m.active).length).toBeLessThanOrEqual(32);
    expect(state.models.filter((m: any) => m.error)).toEqual([]);
    const model = state.models.find((m: any) => m.id === asset.id);
    expect(model.height_m).toBe(asset.dimensions[1]);
    expect(model.ground_m).not.toBeNull();
    results.push({ id: asset.id, name: asset.nameKo, ...model, resident: state.models.filter((m: any) => m.loaded).length });
    await page.screenshot({ path: `tests/screenshots/expanded-${asset.id}.png` });
  }
  await page.locator('#toggle-city-models').uncheck();
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState().activeFootprintIds.length)).toBe(0);
  expect(errors).toEqual([]);
  writeFileSync('docs/landmark-browser-check.json', JSON.stringify({ results, pageErrors: errors, cacheLimit: 48, visibleLimit: 32 }, null, 2));
});
