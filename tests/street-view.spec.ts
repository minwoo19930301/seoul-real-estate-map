import { test, expect, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';

async function ready(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
}
async function camera(page: Page) {
  return page.evaluate(async () => {
    const app = (window as any).__SEOUL_MAP__, map = app.map;
    const { cameraEye } = await import('/src/street-view.ts' as string);
    return { eye: cameraEye(map), street: app.streetView.getState(), zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing(),
      center: map.getCenter().toArray(), scale: map.getTerrain()?.exaggeration, clamped: map.getCenterClampedToGround() };
  });
}

test('eye view stands on a real path, walks three metres, turns and restores the map view', async ({ page }) => {
  const errors: string[] = [], failures: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 400) failures.push(response.url()); });
  await ready(page);
  const original = await camera(page);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.streetView.getState().active);
  await page.waitForTimeout(1500); // Include the first fine terrain tile selection.
  await expect.poll(async () => Math.abs((await camera(page)).eye.height - 1.7)).toBeLessThan(.05);
  const start = await camera(page);
  expect(start.eye.height).toBeCloseTo(1.7, 1);
  for (let i = 0; i < 4; i++) {
    await page.waitForTimeout(250);
    expect(Math.abs((await camera(page)).eye.height - 1.7)).toBeLessThan(.05);
  }
  expect(start.zoom).toBeGreaterThan(21);
  expect(start.pitch).toBeCloseTo(82, 2);
  expect(start.scale).toBe(1);
  expect(start.clamped).toBe(false);
  await expect(page.locator('#exaggeration')).toBeDisabled();
  await page.getByRole('button', { name: '길을 따라 3m 앞으로', exact: true }).click();
  const forward = await camera(page);
  const a = start.street.coordinate, b = forward.street.coordinate;
  const metres = Math.hypot((b[0] - a[0]) * 111195 * Math.cos(a[1] * Math.PI / 180), (b[1] - a[1]) * 111195);
  expect(metres).toBeGreaterThan(2.8); expect(metres).toBeLessThan(3.01);
  const ahead = (b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180) * Math.sin(start.bearing * Math.PI / 180) + (b[1] - a[1]) * Math.cos(start.bearing * Math.PI / 180);
  expect(ahead).toBeGreaterThan(0); // Forward must follow the view, even on a reversed source line.
  await page.getByRole('button', { name: '왼쪽으로 보기', exact: true }).click();
  const turned = await camera(page);
  expect(((turned.bearing - forward.bearing + 540) % 360) - 180).toBeCloseTo(-15, 2);
  expect(turned.street.coordinate).toEqual(forward.street.coordinate);
  await page.screenshot({ path: 'tests/screenshots/street-eye.png' });
  await page.getByRole('button', { name: '지도 시점', exact: true }).click();
  const restored = await camera(page);
  expect(restored.street.active).toBe(false); expect(restored.scale).toBe(original.scale);
  expect(restored.zoom).toBeCloseTo(original.zoom, 5);
  expect(restored.center[0]).toBeCloseTo(original.center[0], 5);
  expect(restored.center[1]).toBeCloseTo(original.center[1], 5);
  expect(restored.clamped).toBe(true);
  await expect(page.locator('#exaggeration')).toBeEnabled();
  expect(errors).toEqual([]); expect(failures).toEqual([]);
  writeFileSync('tests/screenshots/street-eye-verification.json', JSON.stringify({ start, forward, turned, restored, errors, failures }, null, 2));
});

test('zoom reaches 24 and high pitch stays within bounded local API queries', async ({ page }) => {
  const failures: string[] = [];
  page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 400) failures.push(response.url()); });
  await ready(page);
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [127.03911815, 37.561191125], zoom: 24, pitch: 85 }));
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.map.getZoom())).toBe(24);
  await page.waitForTimeout(2000);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getMaxPitch())).toBe(85);
  const bounds = await page.evaluate(async () => {
    const { queryBounds } = await import('/src/view-window.ts' as string);
    return queryBounds((window as any).__SEOUL_MAP__.map);
  });
  expect(bounds[2] - bounds[0]).toBeLessThan(.007);
  expect(bounds[3] - bounds[1]).toBeLessThan(.0055);
  expect(failures).toEqual([]);
});

test('mobile eye controls fit the screen and eye setup failure preserves the previous 2D mode', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await ready(page);
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [127.03911815, 37.561191125], zoom: 18, pitch: 58 }));
  await page.getByRole('button', { name: '사람 1인칭', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.streetView.getState().active);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  for (const selector of ['h1', '#mode-eye', '#mobile-panel']) {
    expect(await page.locator(selector).evaluate(element => {
      const range = document.createRange(); range.selectNodeContents(element);
      return range.getBoundingClientRect().height;
    })).toBeLessThan(23);
  }
  for (const id of ['mode-eye', 'eye-forward', 'eye-left', 'eye-exit']) {
    expect(await page.locator(`#${id}`).evaluate(element => {
      const b = element.getBoundingClientRect(), hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
      return b.x >= 0 && b.right <= innerWidth && !!hit && element.contains(hit);
    })).toBe(true);
  }
  await page.screenshot({ path: 'tests/screenshots/street-eye-mobile.png' });
  await page.getByRole('button', { name: '2D 지도', exact: true }).click();
  await page.route('**/api/mobility?**', route => route.fulfill({ status: 503, json: {} }));
  await page.getByRole('button', { name: '사람 1인칭', exact: true }).click();
  await expect(page.locator('#eye-status')).toContainText('불러오지 못했습니다');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.getState().is25d)).toBe(false);
  await expect(page.locator('#mode-2d')).toHaveAttribute('aria-pressed', 'true');
  await page.unroute('**/api/mobility?**');
  await page.evaluate(() => { (window as any).__SEOUL_MAP__.map.queryTerrainElevation = () => null; });
  await page.getByRole('button', { name: '사람 1인칭', exact: true }).click();
  await expect(page.locator('#eye-status')).toContainText('지면 높이를 확인하지 못했습니다');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.streetView.getState().loading)).toBe(false);
  await expect(page.locator('#mode-2d')).toHaveAttribute('aria-pressed', 'true');
});
