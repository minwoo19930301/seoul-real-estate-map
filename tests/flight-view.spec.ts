import { test, expect, type Page } from '@playwright/test';

async function ready(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return app?.flightView && app.getState().terrainReady && !app.map.isMoving();
  });
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [127.03911815, 37.561191125], zoom: 18, pitch: 58, bearing: 15 }));
  await page.waitForFunction(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return map.isSourceLoaded('local-terrain') && map.queryTerrainElevation(map.getCenter()) !== null;
  });
}
async function state(page: Page) {
  return page.evaluate(() => {
    const app = (window as any).__SEOUL_MAP__, map = app.map;
    return { flight: app.flightView.getState(), eye: app.streetView.getState().active, is25d: app.getState().is25d,
      center: map.getCenter().toArray(), zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing(), roll: map.getRoll(),
      scale: map.getTerrain()?.exaggeration ?? null, maxPitch: map.getMaxPitch(), clamped: map.getCenterClampedToGround(),
      handlers: ['dragPan', 'dragRotate', 'scrollZoom', 'boxZoom', 'doubleClickZoom', 'keyboard', 'touchZoomRotate', 'touchPitch'].map(key => map[key].isEnabled()) };
  });
}
async function enter(page: Page) {
  await page.locator('#mode-flight').click();
  await page.waitForFunction(() => {
    const flight = (window as any).__SEOUL_MAP__.flightView.getState();
    return flight.active && flight.terrainReady;
  });
  await expect(page.locator('#mode-flight')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#flight-controls')).toBeVisible();
}
const travelled = (a: any, b: any) => Math.hypot((b.lon - a.lon) * 111195 * Math.cos(a.lat * Math.PI / 180), (b.lat - a.lat) * 111195);

test('flight moves over real terrain, banks, pauses and restores camera, scale and handlers', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  // A previously disabled handler must remain disabled after flight as well.
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.scrollZoom.disable());
  const before = await state(page);
  expect(before.scale).toBe(4);
  await enter(page);
  const start = await state(page);
  expect(start.scale).toBe(1); expect(start.handlers.every((enabled: boolean) => !enabled)).toBe(true);
  expect(start.flight.clearanceM).toBeGreaterThan(0);
  for (const id of ['altitude', 'clearance', 'speed', 'heading']) await expect(page.locator(`#flight-${id}`)).toContainText(/\d/);
  await expect.poll(async () => travelled(start.flight.position, (await state(page)).flight.position)).toBeGreaterThan(5);
  await page.keyboard.down('KeyD');
  try { await expect.poll(async () => Math.abs((await state(page)).flight.rollDeg)).toBeGreaterThan(2); }
  finally { await page.keyboard.up('KeyD'); }
  // Start-button focus must not turn Space into a second mode-toggle click.
  await page.keyboard.press('Space');
  await expect.poll(async () => (await state(page)).flight.paused).toBe(true);
  const paused = (await state(page)).flight;
  await page.waitForTimeout(650);
  expect((await state(page)).flight.position).toEqual(paused.position);
  expect((await state(page)).flight.altitudeM).toBe(paused.altitudeM);
  await page.locator('#flight-recover').click();
  const recovered = (await state(page)).flight;
  expect(recovered.rollDeg).toBe(0); expect(recovered.pitchDeg).toBe(0);
  await page.locator('#flight-pause').click();
  await expect.poll(async () => (await state(page)).flight.paused).toBe(false);
  await page.locator('#flight-exit').click();
  const restored = await state(page);
  expect(restored.flight.active).toBe(false); expect(restored.scale).toBe(before.scale);
  expect(restored.handlers).toEqual(before.handlers); expect(restored.clamped).toBe(before.clamped);
  expect(restored.maxPitch).toBe(before.maxPitch);
  for (const key of ['zoom', 'pitch', 'bearing', 'roll'] as const) expect(restored[key]).toBeCloseTo(before[key], 3);
  expect(restored.center[0]).toBeCloseTo(before.center[0], 5); expect(restored.center[1]).toBeCloseTo(before.center[1], 5);
  await expect(page.locator('#flight-controls')).toBeHidden();
  await expect(page.locator('#mode-flight')).toHaveAttribute('aria-pressed', 'false');
  expect(errors).toEqual([]);
});

test('flight toggles and Escape restore 2D, and switching to eye view releases flight controls', async ({ page }) => {
  await ready(page);
  await page.locator('#mode-2d').click();
  const before = await state(page);
  await enter(page);
  await page.locator('#mode-flight').click();
  expect((await state(page)).is25d).toBe(false); expect((await state(page)).scale).toBeNull();
  await enter(page);
  await page.keyboard.press('Escape');
  const restored = await state(page);
  expect(restored.flight.active).toBe(false); expect(restored.scale).toBeNull();
  expect(restored.handlers).toEqual(before.handlers);
  await expect(page.locator('#mode-2d')).toHaveAttribute('aria-pressed', 'true');
  await enter(page);
  await page.locator('#mode-eye').click();
  await expect.poll(async () => (await state(page)).eye).toBe(true);
  expect((await state(page)).flight.active).toBe(false);
  await expect(page.locator('#flight-controls')).toBeHidden();
  await page.locator('#mode-2d').click();
  expect((await state(page)).eye).toBe(false); expect((await state(page)).scale).toBeNull();
});

test('flight suppresses map inspection and keeps twelve seconds of moving API traffic bounded', async ({ page }) => {
  test.setTimeout(60_000);
  const api: string[] = [], errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page); await enter(page);
  const inspection = await page.locator('#inspection').innerHTML();
  const selected = await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().selectedCoordinate);
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) api.push(request.url()); });
  await page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map, lngLat = map.getCenter(), point = map.project(lngLat);
    map.fire('mousemove', { lngLat, point, originalEvent: new MouseEvent('mousemove') });
    map.fire('click', { lngLat, point, originalEvent: new MouseEvent('click') });
  });
  const start = (await state(page)).flight.position;
  await page.waitForTimeout(12_000);
  expect(travelled(start, (await state(page)).flight.position)).toBeGreaterThan(15);
  expect(api.filter(url => url.includes('/api/elevation?'))).toEqual([]);
  expect(await page.locator('#inspection').innerHTML()).toBe(inspection);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().selectedCoordinate)).toEqual(selected);
  // Enough for several independent spatial layers, but not a request per animation frame.
  expect(api.length, `API requests during 12s of flight: ${api.length}`).toBeLessThan(120);
  expect(errors).toEqual([]);
  await page.screenshot({ path: test.info().outputPath('flight-desktop.png') });
});

test('360px flight HUD and held controls remain visible without overlap or page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await ready(page); await enter(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const selector of ['#mode-flight', '#flight-pause', '#flight-exit', '#flight-recover', ...['pitchUp', 'pitchDown', 'bankLeft', 'bankRight', 'boost', 'brake'].map(name => `[data-flight-control="${name}"]`)]) {
    await expect(page.locator(selector)).toBeVisible();
    expect(await page.locator(selector).evaluate(element => {
      const box = element.getBoundingClientRect(), hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight && !!hit && element.contains(hit);
    }), `${selector} is inside the screen and receives pointer input`).toBe(true);
  }
  const right = page.locator('[data-flight-control="bankRight"]');
  const box = (await right.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down();
  try { await expect.poll(async () => Math.abs((await state(page)).flight.rollDeg)).toBeGreaterThan(2); }
  finally { await page.mouse.up(); }
  await page.locator('#flight-pause').click();
  expect((await state(page)).flight.paused).toBe(true);
  await page.screenshot({ path: test.info().outputPath('flight-mobile.png') });
  await page.locator('#flight-exit').click();
  expect((await state(page)).flight.active).toBe(false);
});
