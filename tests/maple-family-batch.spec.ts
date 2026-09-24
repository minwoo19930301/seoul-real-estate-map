import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const allNumbers = [...Array.from({ length: 14 }, (_, i) => 101 + i), ...Array.from({ length: 15 }, (_, i) => 201 + i)];
const newNumbers = [...Array.from({ length: 14 }, (_, i) => 101 + i), 201, 202];
const currentId = (n: number) => `bespoke-maple-xi-${n}${[208, 209, 212, 213].includes(n) ? '-corrected' : ''}`;

for (const failNewBatch of [false, true]) {
  test(`Maple all 29 towers: ${failNewBatch ? 'sixteen family models unavailable' : 'all current models draw'}`, async ({ page }) => {
    test.setTimeout(180_000);
    const candidates = newNumbers.map(n => manifest.assets.find((a: any) => a.id === currentId(n)));
    for (const asset of candidates) expect(asset).toBeTruthy();
    const failedIds = failNewBatch ? candidates.map((a: any) => a.id) : [];
    if (failNewBatch) for (const asset of candidates) {
      await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional family-batch failure' }));
    }
    const pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady && (window as any).__SEOUL_MAP__?.cityModels);
    if (await page.locator('#mode-25d').getAttribute('aria-pressed') !== 'true') await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((element: HTMLInputElement) => {
      element.value = '1'; element.dispatchEvent(new Event('input'));
    });
    await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [127.01307870765513, 37.51157245048949], zoom: 16.4, pitch: 52, bearing: 25 }));
    const wanted = allNumbers.map(n => failNewBatch && newNumbers.includes(n) ? `maple-xi-${n}` : currentId(n));
    await page.waitForFunction(({ wanted, failedIds }) => {
      const state = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !state.loading
        && wanted.every(id => state.models.some((m: any) => m.id === id && m.active && m.drawCount > 0))
        && failedIds.every(id => state.models.some((m: any) => m.id === id && m.error));
    }, { wanted, failedIds }, { timeout: 130_000 });
    const state = await page.evaluate(() => (window as any).__SEOUL_MAP__.cityModels.getState());
    const towers = state.models.filter((m: any) => m.active && /^(?:bespoke-)?maple-xi-\d+(?:-corrected)?$/.test(m.id));
    expect(towers.map((m: any) => m.id).sort()).toEqual(wanted.sort());
    for (const number of allNumbers) expect(towers.filter((m: any) => new RegExp(`maple-xi-${number}(?:-corrected)?$`).test(m.id))).toHaveLength(1);
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id).sort()).toEqual(failedIds.sort());
    expect(state.models.filter((m: any) => m.active).length).toBeLessThanOrEqual(32);
    expect(pageErrors).toEqual([]);
    const directory = 'tests/screenshots/maple-family'; mkdirSync(directory, { recursive: true });
    const key = failNewBatch ? 'sixteen-failures' : 'all-29-normal';
    await page.screenshot({ path: `${directory}/${key}.png` });
    writeFileSync(`${directory}/${key}.json`, JSON.stringify({ wanted, failedIds, active: towers, pageErrors }, null, 2) + '\n');
  });
}
