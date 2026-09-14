import { test, expect, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';

// The former autonomous mobility suite now covers static first-person scale
// references. /api/mobility is retained only for explicit camera-path entry.
async function state(page: Page) {
  return page.evaluate(() => (window as any).__SEOUL_MAP__.scaleReferences.getState());
}
async function ready(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
}
async function enterFirstPerson(page: Page) {
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__, s = app.scaleReferences.getState();
    return app.streetView.getState().active && s.active && s.drawnPeople + s.drawnCars > 0;
  });
}
async function settle(page: Page) {
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return app.map.loaded() && !app.map.isMoving() && !app.getState().greeneryPending;
  });
  // Account for already queued terrain/label/tree work before measuring idle.
  let previous = '', unchanged = Date.now();
  await expect.poll(async () => {
    const next = await page.evaluate(() => {
      const app = (window as any).__SEOUL_MAP__;
      return `${app.scaleReferences.getState().frames}:${app.cityModels.getState().frameCount}`;
    });
    if (next !== previous) { previous = next; unchanged = Date.now(); }
    return Date.now() - unchanged;
  }, { timeout: 15_000, intervals: [200] }).toBeGreaterThan(700);
}

test('ordinary and extreme map zooms never start people, cars or path requests outside first person', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/mobility?')) requests.push(request.url()); });
  await ready(page);
  await expect(page.locator('#quick-mobility, #mobility-badge, #mobility-status, .mobility-canvas')).toHaveCount(0);
  expect(await page.evaluate(() => 'mobility' in (window as any).__SEOUL_MAP__)).toBe(false);
  await expect(page.getByLabel('1인칭 크기 비교 모형 표시', { exact: true })).toBeChecked();
  for (const [zoom, pitch] of [[17, 52], [20.49, 52], [21, 82], [24, 85]]) {
    await page.evaluate(({ zoom, pitch }) => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [127.03911815, 37.561191125], zoom, pitch }), { zoom, pitch });
    await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.map.isMoving());
    const before = await state(page);
    await page.waitForTimeout(350); // Beyond the removed animation fetch debounce.
    const after = await state(page);
    expect(after.active).toBe(false);
    expect(after.people + after.cars + after.drawnPeople + after.drawnCars).toBe(0);
    expect(after.placements).toEqual([]);
    expect(after.samples).toEqual([]);
    expect(after.frames).toBe(before.frames);
  }
  expect(requests).toEqual([]);
});

test('first-person references use fixed world coordinates and physical dimensions without an idle animation loop', async ({ page }) => {
  const errors: string[] = [], requests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.url().includes('/api/mobility?')) requests.push(request.url()); });
  await ready(page);
  await enterFirstPerson(page);
  await settle(page);
  const before = await page.evaluate(() => {
    const app = (window as any).__SEOUL_MAP__;
    return { references: app.scaleReferences.getState(), mapFrames: app.cityModels.getState().frameCount };
  });
  const requestCount = requests.length;
  expect(requestCount).toBe(1); // The explicit StreetView entry only.
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => {
    const app = (window as any).__SEOUL_MAP__, references = app.scaleReferences.getState();
    return { references, mapFrames: app.cityModels.getState().frameCount,
      groundErrors: references.samples.map((sample: any) => {
        const point = app.map.project(sample.coordinate.slice(0, 2));
        return Math.hypot(point.x - sample.x, point.y - sample.y);
      }) };
  });
  expect(after.references.frames).toBe(before.references.frames);
  expect(after.mapFrames).toBe(before.mapFrames);
  expect(after.references.placements).toEqual(before.references.placements);
  expect(after.references.samples).toEqual(before.references.samples);
  expect(requests.length).toBe(requestCount);
  expect(after.references.people).toBe(after.references.drawnPeople);
  expect(after.references.cars).toBe(after.references.drawnCars);
  expect(after.references.people).toBeLessThanOrEqual(1);
  expect(after.references.cars).toBeLessThanOrEqual(1);
  expect(after.references.samples.length).toBeGreaterThan(0);
  expect(Math.max(...after.groundErrors)).toBeLessThan(.05);
  for (const item of [...after.references.placements, ...after.references.samples]) {
    expect(item.routeId).toMatch(/^osm:way:\d+:(pedestrian|car):/);
    expect(item.coordinate).toHaveLength(3);
    expect(item.coordinate.every(Number.isFinite)).toBe(true);
    expect(item.dimensions_m).toEqual(item.kind === 'pedestrian'
      ? { height: 1.7, width: .5, length: .3 }
      : { height: 1.5, width: 1.8, length: 4.3 });
  }
  const painted = await page.locator('.scale-reference-canvas').evaluate((canvas: HTMLCanvasElement) => {
    const rgba = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, canvas.height).data;
    let painted = 0;
    for (let i = 3; i < rgba.length; i += 4) if (rgba[i]) painted++;
    return painted;
  });
  expect(painted).toBeGreaterThan(100);
  await page.screenshot({ path: 'tests/screenshots/first-person-static.png' });
  expect(errors).toEqual([]);
  writeFileSync('tests/screenshots/scale-references-verification.json', JSON.stringify({ before, after, requests, errors }, null, 2));
});

test('fixed references survive manual steps and toggles but disappear on leaving first person', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/mobility?')) requests.push(request.url()); });
  await ready(page);
  await enterFirstPerson(page);
  const placements = (await state(page)).placements;
  const requestCount = requests.length;
  await page.getByRole('button', { name: '길을 따라 3m 앞으로', exact: true }).click();
  await page.getByRole('button', { name: '왼쪽으로 보기', exact: true }).click();
  expect((await state(page)).placements).toEqual(placements);
  const toggle = page.getByLabel('1인칭 크기 비교 모형 표시', { exact: true });
  await toggle.uncheck();
  const hidden = await state(page);
  expect(hidden.enabled).toBe(false);
  expect(hidden.people + hidden.cars + hidden.samples.length).toBe(0);
  expect(hidden.placements).toEqual(placements);
  await toggle.check();
  expect((await state(page)).enabled).toBe(true);
  expect((await state(page)).placements).toEqual(placements);
  expect(requests.length).toBe(requestCount);
  await page.getByRole('button', { name: '지도 시점', exact: true }).click();
  await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.scaleReferences.getState().active);
  expect((await state(page)).placements).toEqual([]);
  expect((await state(page)).samples).toEqual([]);
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ zoom: 24, pitch: 85 }));
  await page.waitForTimeout(350);
  expect((await state(page)).active).toBe(false);
  expect((await state(page)).people + (await state(page)).cars).toBe(0);
  expect(requests.length).toBe(requestCount);
});

test('a failed first-person entry leaves no references or autonomous retry', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/mobility?**', route => { requests++; return route.fulfill({ status: 503, json: { error: 'Test unavailable' } }); });
  await ready(page);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await expect(page.locator('#eye-status')).toContainText('불러오지 못했습니다');
  const failed = await state(page);
  expect(failed.active).toBe(false);
  expect(failed.placements).toEqual([]);
  expect(failed.samples).toEqual([]);
  await page.waitForTimeout(500);
  expect((await state(page)).frames).toBe(failed.frames);
  expect(requests).toBe(1);
  await expect(page.locator('#map canvas.maplibregl-canvas')).toBeVisible();
});
