import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync('public/models/bespoke-manifest.json', 'utf8'));
const fixtures = [
  { site: 'lg-art-center-seoul', id: 'bespoke-lg-art-center-seoul-discovery-lab', source: '2623bbf0-348f-4cec-94c6-dc8ca4977552', old: 'landmark-2623bbf0-348f-4cec-94c6-dc8ca4977552', center: [126.82940115000001, 37.56553850254776], zoom: 17.2, bearing: 25, neighbour: 'reference-flight-lg-science-park' },
  { site: 'jungmyeongjeon', id: 'bespoke-jungmyeongjeon', source: '4c53ad91-93b0-4472-b7a4-0086e45cbdd2', old: 'civic-4c53ad91-93b0-4472-b7a4-0086e45cbdd2', center: [126.9725588920004, 37.56673044964224], zoom: 18.65, bearing: 0 },
  { site: 'mmca-deoksugung', id: 'bespoke-mmca-deoksugung', source: 'a1d78a03-a0b3-4ef2-ab28-b3a5021cfbcc', old: 'civic-a1d78a03-a0b3-4ef2-ab28-b3a5021cfbcc', center: [126.97376445000575, 37.56588615088699], zoom: 17.7, bearing: -90, neighbour: 'reference-flight-deoksugung' },
];
const eastSeokjojeon = '5a79ee99-0908-4cf3-812f-16dee899ab41';

for (const fixture of fixtures) for (const fail of [false, true]) {
  test(`${fixture.site} ${fail ? 'HTTP404 restores its original model' : 'draws its individual reconstruction'} without absorbing neighbours`, async ({ page }) => {
    test.setTimeout(120_000);
    const asset = manifest.assets.find((a: any) => a.id === fixture.id);
    expect(asset).toBeTruthy();
    expect(asset.footprintIds).toEqual([fixture.source]);
    expect(asset.supersedes).toEqual([fixture.old]);
    if (fail) await page.route(`**/models/${asset.model}`, route => route.fulfill({ status: 404, body: 'intentional cultural model fallback fixture' }));
    await page.goto('/');
    await page.waitForFunction(() => (window as any).__SEOUL_MAP__?.getState().terrainReady);
    await page.locator('#mode-25d').click();
    await page.locator('#exaggeration').evaluate((e: HTMLInputElement) => { e.value = '1'; e.dispatchEvent(new Event('input')); });
    await page.evaluate(f => (window as any).__SEOUL_MAP__.map.jumpTo({ center: f.center, zoom: f.zoom, pitch: 55, bearing: f.bearing }), fixture);
    await page.waitForFunction(({ fixture, fail }) => {
      const s = (window as any).__SEOUL_MAP__.cityModels.getState();
      return !s.loading && s.models.some((m: any) => m.id === (fail ? fixture.old : fixture.id) && m.active && m.drawCount > 0)
        && (!fail || s.models.some((m: any) => m.id === fixture.id && m.error));
    }, { fixture, fail }, { timeout: 60_000 });
    await page.waitForLoadState('networkidle');
    const state = await page.evaluate(() => {
      const api = (window as any).__SEOUL_MAP__, s = api.cityModels.getState();
      const sources = api.map.querySourceFeatures('building-data').map((f: any) => f.properties);
      return { models: s.models.filter((m: any) => m.active || m.error), owned: s.activeFootprintIds,
        sources: [...new Set(sources.map((p: any) => String(p.id)))],
        eastParts: [...new Set(sources.filter((p: any) => p.parent_id === '5a79ee99-0908-4cf3-812f-16dee899ab41').map((p: any) => String(p.id)))],
        solids: [...new Set(api.map.queryRenderedFeatures(undefined, { layers: ['building-solids'] }).map((f: any) => String(f.properties.id)))],
        resident: s.models.filter((m: any) => m.loaded).length };
    });
    const active = state.models.filter((m: any) => m.active).map((m: any) => m.id);
    expect(active).not.toContain(fail ? fixture.id : fixture.old);
    expect(state.sources).toContain(fixture.source);
    expect(state.owned).toContain(fixture.source);
    expect(state.solids).not.toContain(fixture.source);
    if (fixture.neighbour) expect(active).toContain(fixture.neighbour);
    if (fixture.site === 'mmca-deoksugung') {
      expect(state.sources).toContain(eastSeokjojeon);
      expect(state.eastParts.length).toBeGreaterThan(10);
      for (const id of [eastSeokjojeon, ...state.eastParts]) expect(state.owned).not.toContain(id);
      expect(state.solids).toContain('36343235-3439-3065-A161-383533376161');
    }
    expect(state.resident).toBeLessThanOrEqual(48);
    expect(active.length).toBeLessThanOrEqual(32);
    expect(state.models.filter((m: any) => m.error).map((m: any) => m.id)).toEqual(fail ? [fixture.id] : []);
    mkdirSync('tests/screenshots', { recursive: true });
    const name = `cultural-${fixture.site}${fail ? '-fallback' : ''}`;
    await page.screenshot({ path: `tests/screenshots/${name}.png` });
    writeFileSync(`tests/screenshots/${name}.json`, JSON.stringify(state, null, 2) + '\n');
  });
}
