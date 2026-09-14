import { test, expect, type Page } from '@playwright/test';

async function ready(page: Page) {
  await page.goto('/');
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return app?.getState().terrainReady && app.map.queryRenderedFeatures({ layers: ['contours'] }).length > 10;
  });
  await expect(page.locator('#data-status')).toContainText('등고선');
}

test('official vectors render, exact nearest point is identified, and bookmarks survive reload', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  await page.getByRole('button', { name: '2D 지도', exact: true }).click();
  await page.waitForFunction(() => !(window as any).__SEOUL_MAP__.map.isMoving());
  await page.getByLabel('건물 표시', { exact: true }).uncheck();
  await page.getByLabel('장소 핀 표시', { exact: true }).uncheck();
  const coordinate: [number, number] = [126.948, 37.501];
  const expected = await (await request.get(`/api/elevation?lon=${coordinate[0]}&lat=${coordinate[1]}`)).json();
  await page.getByLabel('등고선 표시', { exact: true }).uncheck();
  const point = await page.evaluate(coordinate => {
    const point = (window as any).__SEOUL_MAP__.map.project(coordinate);
    return { x: point.x, y: point.y };
  }, coordinate);
  await page.locator('#map').click({ position: point });
  await expect(page.locator('#inspection .elevation-value')).toHaveText(`${expected.nearest.height_m.toFixed(2)}m`);
  await expect(page.locator('#inspection')).toContainText('선택한 위치 자체의 높이를 뜻하지 않습니다.');
  await page.getByLabel('등고선 표시', { exact: true }).check();
  const name = `QA-${Date.now()}`;
  await page.getByLabel('저장할 위치 이름').fill(name);
  let bookmarkId: string | undefined;
  try {
    await page.getByRole('button', { name: '위치 저장', exact: true }).click();
    await expect(page.locator('#save-status')).toHaveText('이 컴퓨터에 저장했습니다.');
    const bookmarks = await (await request.get('/api/bookmarks')).json();
    bookmarkId = bookmarks.bookmarks.find((b: any) => b.name === name)?.id;
    expect(bookmarkId).toBeTruthy();
    await ready(page);
    await expect(page.getByRole('button', { name, exact: true })).toBeVisible();
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.locator('#place-title')).toHaveText(name);
    await expect(page.locator('#inspection')).toContainText('가까운 표고점');
  } finally {
    if (bookmarkId) await request.delete(`/api/bookmarks/${bookmarkId}`);
  }
  expect(errors).toEqual([]);
});

test('2.5D uses local terrain and exaggeration never changes the source height reading', async ({ page }) => {
  const failures: string[] = [];
  page.on('response', response => { if (response.url().includes('/data/terrain/') && response.status() >= 400) failures.push(response.url()); });
  await ready(page);
  await page.getByLabel('건물 표시', { exact: true }).uncheck();
  await page.getByLabel('장소 핀 표시', { exact: true }).uncheck();
  await page.getByLabel('등고선 표시', { exact: true }).uncheck();
  await page.locator('#map').click({ position: { x: 500, y: 450 } });
  await expect(page.locator('#inspection .elevation-value')).toBeVisible();
  const height = await page.locator('#inspection .elevation-value').innerText();
  await page.getByLabel('등고선 표시', { exact: true }).check();
  await page.getByRole('button', { name: '2.5D 지형', exact: true }).click();
  await expect(page.locator('#terrain-settings')).toBeVisible();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.getPitch() > 50);
  await page.waitForFunction(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    const h = map.queryTerrainElevation([126.948, 37.501]);
    return typeof h === 'number' && h > 10 && h < 1500;
  });
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getTerrain()?.source)).toBe('local-terrain');
  await page.locator('#exaggeration').fill('2');
  await expect(page.locator('#terrain-badge-scale')).toHaveText('2×');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getTerrain()?.exaggeration)).toBe(2);
  await expect(page.locator('#inspection .elevation-value')).toHaveText(height);
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return !app.map.isMoving() && app.map.loaded() && !document.querySelector('#data-status')?.textContent?.includes('조회 중');
  });
  await page.screenshot({ path: 'tests/screenshots/desktop-25d.png' });
  await page.getByRole('button', { name: '2D 지도', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.getPitch() === 0);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getTerrain())).toBeNull();
  await page.screenshot({ path: 'tests/screenshots/desktop-2d.png' });
  expect(failures).toEqual([]);
});

test('default terrain is 4x while building heights and footprints retain original dimensions', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await ready(page);
  await expect(page.getByRole('button', { name: '2.5D 지형', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#exaggeration')).toHaveValue('4');
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return !app.map.isMoving() && app.map.queryRenderedFeatures({ layers: ['building-solids'] }).length > 20;
  });
  await page.getByLabel('장소 핀 표시', { exact: true }).uncheck();
  const hit = await page.evaluate(() => {
    const map = (window as any).__SEOUL_MAP__.map;
    const canvas = map.getCanvas();
    for (let y = 230; y < canvas.clientHeight - 150; y += 14) {
      for (let x = 140; x < canvas.clientWidth - 80; x += 14) {
        const feature = map.queryRenderedFeatures([x, y], { layers: ['building-solids'] }).find((f: any) => f.properties.is_apartment && f.properties.height_m > 15);
        if (feature) return { x, y, id: feature.properties.id };
      }
    }
    return null;
  });
  expect(hit).not.toBeNull();
  const response = await request.get(`/api/buildings/${hit!.id}`);
  expect(response.ok()).toBe(true);
  const data = await response.json();
  const expected = data.properties ?? data;
  await page.locator('#map').click({ position: { x: hit!.x, y: hit!.y } });
  await expect(page.locator('#inspect-kind')).toHaveText('선택한 건물');
  await expect(page.locator('.building-height')).toHaveText(`${expected.height_m.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}m`);
  await expect(page.locator('.building-facts')).toContainText(`${expected.footprint_area_m2.toLocaleString('ko-KR', { maximumFractionDigits: 1 })} m²`);
  const height = await page.locator('.building-height').innerText();
  await page.locator('#exaggeration').fill('3');
  await expect(page.locator('.building-height')).toHaveText(height);
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getPaintProperty('building-solids', 'fill-extrusion-height'))).toEqual(['coalesce', ['get', 'height_m'], 0]);
  await page.locator('#exaggeration').fill('2');
  await page.getByLabel('아파트만 보기', { exact: true }).check();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.queryRenderedFeatures({ layers: ['building-solids'] }).every((f: any) => f.properties.is_apartment));
  await page.getByLabel('아파트만 보기', { exact: true }).uncheck();
  await page.screenshot({ path: 'tests/screenshots/buildings-25d.png' });
  expect(errors).toEqual([]);
});

test('missing building heights stay absent and overview unloads building geometry', async ({ page, request }) => {
  await ready(page);
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.buildings.getData().features.length > 100);
  const missing = await page.evaluate(() => (window as any).__SEOUL_MAP__.buildings.getData().features.find((f: any) => f.properties.height_m === null));
  expect(missing).toBeTruthy();
  await page.evaluate(feature => (window as any).__SEOUL_MAP__.buildings.inspect(feature, [126.948, 37.501]), missing);
  await expect(page.locator('.building-height')).toHaveText('—m');
  await expect(page.locator('.reading-label')).toContainText('미등록');
  const detail = await (await request.get(`/api/buildings/${missing.properties.id}`)).json();
  expect((detail.properties ?? detail).height_m).toBeNull();
  await page.getByRole('button', { name: '서울 전체', exact: true }).click();
  await expect(page.locator('#building-status')).toContainText('확대');
  await expect.poll(() => page.evaluate(() => (window as any).__SEOUL_MAP__.buildings.getData().features.length)).toBe(0);
});

test('flat neighborhoods, contour interval, search and city overview work', async ({ page }) => {
  await ready(page);
  await page.getByPlaceholder('동네, 역, 아파트·건물 이름').fill('성수동');
  await page.getByRole('button', { name: '장소 찾기', exact: true }).click();
  await expect(page.locator('#place-title')).toHaveText('성수동');
  await page.waitForFunction(() => {
    const a = (window as any).__SEOUL_MAP__;
    return !a.map.isMoving() && a.getData().features.some((f: any) => f.properties.kind === 'contour' && f.properties.height_m === 5);
  });
  await page.getByLabel('선의 높이 간격').selectOption('10');
  await expect(page.locator('#density-note')).toContainText('현재 10m');
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.getData().features.filter((f: any) => f.properties.kind === 'contour').every((f: any) => f.properties.height_m % 10 === 0))).toBe(true);
  await page.getByPlaceholder('동네, 역, 아파트·건물 이름').fill('대치동');
  await page.getByRole('button', { name: '장소 찾기', exact: true }).click();
  await expect(page.locator('#place-title')).toHaveText('대치동');
  await page.getByPlaceholder('동네, 역, 아파트·건물 이름').fill('해방촌');
  await page.getByRole('button', { name: '장소 찾기', exact: true }).click();
  await expect(page.locator('#place-title')).toHaveText('해방촌');
  await page.getByRole('button', { name: '서울 전체', exact: true }).click();
  await expect(page.locator('#place-title')).toHaveText('서울 전체');
  await expect(page.locator('#density-note')).toContainText('확대하면');
  await expect(page.locator('#data-status')).not.toContainText('실패');
});

test('local vectors and 2.5D remain usable when external basemap and fonts are unavailable', async ({ page }) => {
  await page.route('https://**/*', route => route.abort());
  await ready(page);
  await page.getByLabel('배경지도 표시', { exact: true }).uncheck();
  await page.getByRole('button', { name: '2.5D 지형', exact: true }).click();
  await page.waitForFunction(() => (window as any).__SEOUL_MAP__.map.getTerrain()?.source === 'local-terrain');
  await expect(page.locator('#data-status')).toContainText('등고선');
});

test('mobile controls fit and the map stays accessible behind the panel', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '지도 설정', exact: true }).click();
  await expect(page.locator('#sidebar')).toHaveClass(/open/);
  await page.getByPlaceholder('동네, 역, 아파트·건물 이름').fill('성수동');
  await page.getByRole('button', { name: '장소 찾기', exact: true }).click();
  await expect(page.locator('#sidebar')).not.toHaveClass(/open/);
  await expect(page.locator('#place-title')).toHaveText('성수동');
  await page.getByRole('button', { name: '2.5D 지형', exact: true }).click();
  await expect(page.locator('#terrain-badge')).toBeVisible();
  await page.waitForFunction(() => {
    const app = (window as any).__SEOUL_MAP__;
    return !app.map.isMoving() && app.map.loaded() && !document.querySelector('#data-status')?.textContent?.includes('조회 중');
  });
  expect(await page.evaluate(() => (window as any).__SEOUL_MAP__.map.getCenter().lng)).toBeCloseTo(127.049, 3);
  await page.screenshot({ path: 'tests/screenshots/mobile-25d.png' });
});
