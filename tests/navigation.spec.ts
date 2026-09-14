import { test, expect, type Page } from '@playwright/test';

async function ready(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return app?.getState().terrainReady && app.map.getLayer('building-solids') && !app.map.isMoving();
  });
}

test('city overview cancels a pending submitted place search', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let started = 0;
  let completed = 0;
  await page.route('**/api/places?**', async route => {
    started++;
    await gate;
    try {
      await route.fulfill({ json: { results: [{
        id: 'qa-late-station', name: '지연 검색 시험역', subtitle: '회귀 검증용 응답',
        kind: 'station', center: [127.06, 37.51], zoom: 16,
      }] } });
    } catch (error) {
      // A correct cancellation can close the intercepted request before release.
      if (!route.request().failure()) throw error;
    } finally { completed++; }
  });
  await ready(page);
  await page.locator('#place-search').fill('지연 검색 시험역');
  await page.locator('#place-search').press('Enter');
  await expect.poll(() => started).toBeGreaterThan(0);
  await page.getByRole('button', { name: '서울 전체', exact: true }).click();
  await expect(page.locator('#place-title')).toHaveText('서울 전체');
  await expect(page.locator('#search-results')).toBeEmpty();
  const overview = await page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return { center: map.getCenter().toArray(), zoom: map.getZoom() };
  });
  release();
  await expect.poll(() => completed).toBe(started);
  // Let the released response and the following map frame settle.
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.locator('#place-title')).toHaveText('서울 전체');
  await expect(page.locator('#search-results')).toBeEmpty();
  const after = await page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    return { center: map.getCenter().toArray(), zoom: map.getZoom() };
  });
  expect(after.zoom).toBeCloseTo(overview.zoom, 5);
  expect(after.center[0]).toBeCloseTo(overview.center[0], 5);
  expect(after.center[1]).toBeCloseTo(overview.center[1], 5);
});

test('quick building toggle hides solids, footprints and names without a second building basemap', async ({ page }) => {
  await ready(page);
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['building-solids'] }).length > 10);
  await page.locator('#quick-buildings').click();
  await expect(page.locator('#quick-buildings')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByLabel('건물 표시', { exact: true })).not.toBeChecked();
  await expect(page.getByLabel('건물 이름 표시', { exact: true })).toBeDisabled();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['building-solids', 'building-footprints', 'building-outlines', 'building-labels'] }).length === 0);
  const hidden = await page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    const ids = ['building-solids', 'building-footprints', 'building-outlines', 'building-labels'];
    return {
      visibility: ids.map(id => map.getLayoutProperty(id, 'visibility')),
      rendered: map.queryRenderedFeatures({ layers: ids }).length,
      basemapType: map.getStyle().sources.osm.type,
      backgroundBuildings: map.getStyle().layers.filter((layer: any) => layer.source === 'osm' && layer['source-layer'] === 'building').length,
    };
  });
  expect(hidden.visibility).toEqual(['none', 'none', 'none', 'none']);
  expect(hidden.rendered).toBe(0);
  expect(hidden.basemapType).toBe('vector');
  expect(hidden.backgroundBuildings).toBe(0);
  await page.locator('#quick-buildings').click();
  await expect(page.getByLabel('건물 표시', { exact: true })).toBeChecked();
  await expect(page.getByLabel('건물 이름 표시', { exact: true })).toBeEnabled();
  await expect(page.getByLabel('건물 이름 표시', { exact: true })).toBeChecked();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['building-solids'] }).length > 10);
});

test('mobile quick controls remain unobscured and independent from map settings', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await ready(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const controls = await page.evaluate(() => {
    const selectors = ['#quick-buildings', '#quick-roads', '#quick-walkways', '#quick-landmarks', '#mode-eye'];
    return selectors.map(selector => {
      const element = document.querySelector(selector)!;
      const rect = element.getBoundingClientRect();
      const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
      return { selector, inside: rect.x >= 0 && rect.right <= innerWidth && rect.y >= 0 && rect.bottom <= innerHeight, unobscured: !!hit && element.contains(hit) };
    });
  });
  for (const control of controls) {
    expect(control.inside, `${control.selector} stays inside the screen`).toBe(true);
    expect(control.unobscured, `${control.selector} is not covered by navigation or captions`).toBe(true);
  }
  await page.locator('#quick-landmarks').click();
  await expect(page.locator('#quick-landmarks')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('.landmark-pin')).toHaveCount(0);
  await page.getByRole('button', { name: '지도 설정', exact: true }).click();
  await expect(page.getByLabel('장소 핀 표시', { exact: true })).not.toBeChecked();
  await page.getByLabel('장소 핀 표시', { exact: true }).check();
  await expect(page.locator('#quick-landmarks')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('#close-panel').click();
  await expect(page.locator('#sidebar')).not.toHaveClass(/open/);
  await expect(page.locator('#quick-landmarks')).toBeVisible();
});
