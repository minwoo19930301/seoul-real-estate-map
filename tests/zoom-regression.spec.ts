import { test, expect, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';

async function eye(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.streetView.getState().active);
  await page.waitForTimeout(1000);
}
async function camera(page: Page) {
  return page.evaluate(() => {
    const app = (window as any).__SEOUL_MAP__, map = app.map;
    return { zoom: map.getZoom(), center: map.getCenter().toArray(), elevation: map.getCenterElevation(), pitch: map.getPitch(), bearing: map.getBearing(), scale: map.getTerrain()?.exaggeration, active: app.streetView.getState().active };
  });
}
async function settle(page: Page) {
  await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.map.isMoving());
  await page.waitForTimeout(700); // Include idle/terrain events that previously undid the navigation.
}

test('native zoom buttons keep the requested zoom and do not restore terrain exaggeration', async ({ page }) => {
  await eye(page);
  const before = await camera(page);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await settle(page);
  const after = await camera(page);
  expect(after.zoom).toBeCloseTo(before.zoom + 1, 4);
  expect(after.scale).toBe(1); expect(after.active).toBe(false);
  const sequence = [before, after];
  for (let i = 0; i < 4; i++) {
    const old = await camera(page);
    await page.getByRole('button', { name: 'Zoom out', exact: true }).click();
    await settle(page);
    const next = await camera(page);
    expect(next.zoom).toBeCloseTo(old.zoom - 1, 4);
    expect(next.scale).toBe(1);
    sequence.push(next);
  }
  expect(sequence.at(-1)!.zoom).toBeLessThan(20.5);
  writeFileSync('tests/screenshots/zoom-button-regression.json', JSON.stringify(sequence, null, 2));
});

test('wheel, drag and camera API navigation are not reset on idle', async ({ page }) => {
  await eye(page);
  const before = await camera(page);
  const box = (await page.locator('#map').boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -160);
  await settle(page);
  const wheel = await camera(page);
  expect(wheel.zoom).toBeGreaterThan(before.zoom + .05);
  expect(wheel.scale).toBe(1); expect(wheel.active).toBe(false);
  await page.waitForTimeout(800);
  expect((await camera(page)).zoom).toBeCloseTo(wheel.zoom, 5);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 90, box.y + box.height / 2 + 20, { steps: 8 }); await page.mouse.up();
  await settle(page);
  const dragged = await camera(page);
  expect(dragged.center).not.toEqual(wheel.center);
  await page.waitForTimeout(800);
  const held = await camera(page);
  expect(held.center[0]).toBeCloseTo(dragged.center[0], 7);
  expect(held.center[1]).toBeCloseTo(dragged.center[1], 7);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.streetView.getState().active);
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.zoomIn({ duration: 0 }));
  const requested = await camera(page);
  await settle(page);
  const settled = await camera(page);
  expect(settled.zoom).toBeCloseTo(requested.zoom, 5);
  expect(settled.scale).toBe(1); expect(settled.active).toBe(false);
  await page.getByRole('button', { name: '지도 시점', exact: true }).click();
  const restored = await camera(page);
  expect(restored.scale).toBe(dragged.scale); // Return to the latest eye-entry snapshot.
  expect(restored.zoom).toBeCloseTo(dragged.zoom, 5);
});

test('mode switches and failed eye retries preserve the latest browsing location', async ({ page }) => {
  await eye(page);
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ center: [126.9209, 37.5604], zoom: 19, pitch: 58 }));
  await settle(page);
  const free = await camera(page);
  await page.route('**/api/mobility?**', route => route.fulfill({ status: 503, json: {} }));
  await page.getByRole('button', { name: '사람 1인칭', exact: true }).click();
  await expect(page.locator('#eye-status')).toContainText('불러오지 못했습니다');
  const failed = await camera(page);
  expect(failed.zoom).toBeCloseTo(free.zoom, 5);
  expect(failed.center[0]).toBeCloseTo(free.center[0], 7);
  expect(failed.center[1]).toBeCloseTo(free.center[1], 7);
  expect(failed.scale).toBe(free.scale);
  await page.unroute('**/api/mobility?**');
  await page.getByRole('button', { name: '2D 지도', exact: true }).click();
  await settle(page);
  const flat = await camera(page);
  expect(flat.zoom).toBeCloseTo(free.zoom, 5);
  expect(flat.center[0]).toBeCloseTo(free.center[0], 7);
  expect(flat.center[1]).toBeCloseTo(free.center[1], 7);
});

test('close views hide analysis lines without changing saved layer choices or source geometry', async ({ page }) => {
  await page.goto('/');
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
  await page.evaluate(async () => { await (window as any).__SEOUL_MAP__.inspect([126.948, 37.501]); });
  const sourceBefore = await page.evaluate(async () => (window as any).__SEOUL_MAP__.map.getSource('selection-link').getData());
  expect(sourceBefore.features.length).toBeGreaterThan(0);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.streetView.getState().active);
  const hidden = ['contours', 'contour-labels', 'spots', 'spot-labels', 'selection-link-line', 'hillshade', 'building-outlines', 'base-roads', 'base-roads-case', 'base-road-names'];
  await expect.poll(() => page.evaluate(ids => ids.map(id => (window as any).__SEOUL_MAP__.map.getLayoutProperty(id, 'visibility')), hidden)).toEqual(hidden.map(() => 'none'));
  await expect(page.getByLabel('등고선 표시', { exact: true })).toBeChecked();
  await expect(page.getByLabel('표고점 표시', { exact: true })).toBeChecked();
  await expect(page.locator('#close-layer-note')).toBeVisible();
  expect(await page.evaluate(async () => (window as any).__SEOUL_MAP__.map.getSource('selection-link').getData())).toEqual(sourceBefore);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getPaintProperty('roadway-lines', 'line-color'))).toBe('#e1e5e8');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'tests/screenshots/pale-street.png' });
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ zoom: 18, pitch: 58 }));
  await settle(page);
  await expect.poll(() => page.evaluate(ids => ids.map(id => (window as any).__SEOUL_MAP__.map.getLayoutProperty(id, 'visibility')), hidden)).toEqual(hidden.map(() => 'visible'));
  await page.getByLabel('등고선 표시', { exact: true }).uncheck();
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ zoom: 21, pitch: 82 }));
  await page.evaluate(() => (window as any).__SEOUL_MAP__.map.jumpTo({ zoom: 18, pitch: 58 }));
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getLayoutProperty('contours', 'visibility'))).toBe('none');
  await page.screenshot({ path: 'tests/screenshots/pale-neighborhood.png' });
});
