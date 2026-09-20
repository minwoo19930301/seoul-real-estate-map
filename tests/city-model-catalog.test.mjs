import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { CityModelCatalog } from '../src/city-model-catalog.ts';
import { CityModels } from '../src/city-models.ts';

const indexPath = 'residential-survey/index.json';
const sha = value => createHash('sha256').update(value).digest('hex');
const asset = (id, lon = 127, lat = 37.5) => ({ id, nameKo: id, model: `${id}.glb`, dimensions: [10, 12, 10],
  coordinate: { lon, lat }, yawDegFromEast: 0, sha256: 'a'.repeat(64), minZoom: 16.5,
  referenceUrl: 'https://example.com/source', footprintIds: [`source-${id}`], category: 'residential-villa' });
function fixture(count = 40, perTile = 1) {
  const bodies = new Map();
  const tiles = Array.from({ length: count }, (_, i) => {
    const lon = 126 + i * .01;
    const id = `16-${20000+i}-25000`, path = `residential-survey/tiles/${id}.json`;
    const body = JSON.stringify({ version: 1, assets: Array.from({ length: perTile }, (_, j) => asset(`tile-${i}-model-${j}`, lon + .002 + j * .0000001)) });
    bodies.set(path, body);
    return { id, path, bounds: [lon, 37.499, lon+.004, 37.501], count: perTile, sha256: sha(body) };
  });
  return { index: { version: 1, minZoom: 16.5, assetCount: count * perTile, tiles }, bodies };
}
const view = (i = 0, zoom = 17) => ({ zoom, lon: 126+i*.01+.002, lat: 37.5,
  west: 126+i*.01+.001, east: 126+i*.01+.003, south: 37.4995, north: 37.5005 });
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function mockFetch(data, handler) {
  const requests = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    requests.push(url);
    if (handler) {
      const response = await handler(url, options);
      if (response) return response;
    }
    const path = url.replace('/models/', '');
    const body = path === indexPath ? JSON.stringify(data.index) : data.bodies.get(path);
    return new Response(body ?? '', { status: body === undefined ? 404 : 200 });
  };
  return { requests, restore: () => { globalThis.fetch = original; } };
}

test('100000-model index fetches only nearby shards, respects 16 tile / 4 request limits and reuses metadata', async () => {
  const data = fixture(1000, 100);
  let active = 0, maximum = 0;
  const fetch = mockFetch(data, async url => {
    if (url.endsWith('index.json')) return;
    active++; maximum = Math.max(maximum, active); await delay(2); active--;
  });
  let tiles = [];
  const catalog = new CityModelCatalog(indexPath, new Set(), value => { tiles = value; });
  try {
    await catalog.update(view(0, 16), true, () => false);
    await catalog.update(view(), false, () => false);
    assert.equal(fetch.requests.length, 0);
    const wide = { ...view(), east: 136, west: 126, lon: 126.002 };
    await catalog.update(wide, true, () => false);
    assert.equal(catalog.assetCount, 100000);
    assert.equal(fetch.requests.length, 17, 'one index and only 16 of 1000 tiles');
    assert.equal(tiles.length, 16); assert.equal(tiles.flatMap(t => t.assets).length, 1600);
    assert.ok(maximum <= 4); assert.ok(maximum > 1);
    await catalog.update(wide, true, () => false);
    assert.equal(fetch.requests.length, 17);
    assert.equal(catalog.error, null);
  } finally { catalog.dispose(); fetch.restore(); }
});

test('32-tile metadata LRU evicts cold tiles, preserves protected tiles and refetches evicted metadata', async () => {
  const data = fixture(40), fetch = mockFetch(data);
  let tiles = [];
  const catalog = new CityModelCatalog(indexPath, new Set(), value => { tiles = value; });
  try {
    const pinned = id => id === data.index.tiles[0].id;
    for (let i = 0; i < 40; i++) {
      await catalog.update(view(i), true, pinned);
      assert.ok(catalog.tileCount <= 32);
    }
    assert.equal(tiles.length, 32);
    assert.ok(tiles.some(t => t.id === data.index.tiles[0].id));
    assert.ok(!tiles.some(t => t.id === data.index.tiles[1].id));
    const before = fetch.requests.length;
    await catalog.update(view(1), true, pinned);
    assert.equal(fetch.requests.length, before+1);
    assert.ok(tiles.some(t => t.id === data.index.tiles[1].id));
  } finally { catalog.dispose(); fetch.restore(); }
});

test('navigation, zoom-out, disable and dispose discard late tile responses even when fetch ignores abort', async () => {
  for (const action of ['pan', 'zoom-out', 'disable', 'dispose']) {
    const data = fixture(2);
    let release, started;
    const waiting = new Promise(resolve => { started = resolve; });
    const fetch = mockFetch(data, async url => {
      if (url.endsWith('/16-20000-25000.json')) { started(); await new Promise(resolve => { release = resolve; }); }
    });
    let tiles = [];
    const catalog = new CityModelCatalog(indexPath, new Set(), value => { tiles = value; });
    try {
      const first = catalog.update(view(), true, () => false); await waiting;
      let next;
      if (action === 'pan') next = catalog.update(view(1), true, () => false);
      if (action === 'zoom-out') next = catalog.update(view(0, 15), true, () => false);
      if (action === 'disable') next = catalog.update(view(), false, () => false);
      if (action === 'dispose') catalog.dispose();
      release(); await first; await next;
      assert.deepEqual(tiles.map(t => t.id), action === 'pan' ? [data.index.tiles[1].id] : []);
      assert.equal(catalog.error, null);
    } finally { catalog.dispose(); fetch.restore(); }
  }
});

test('bad paths and invalid index counts fail before any untrusted shard request', async () => {
  for (const path of ['../index.json', '/index.json', 'https://evil.test/index.json', 'a/%2e%2e/index.json', 'a/index.json?x=1']) {
    assert.throws(() => new CityModelCatalog(path, new Set(), () => {}), /path/);
  }
  for (const mutate of [
    index => { index.tiles[0].path = '../steal.json'; },
    index => { index.tiles[0].path = 'other/tiles/16-20000-25000.json'; },
    index => { index.assetCount++; },
    index => { index.tiles.push(index.tiles[0]); index.assetCount++; },
    index => { index.tiles[0].bounds = [NaN, 0, 1, 1]; },
  ]) {
    const data = fixture(1); mutate(data.index); const fetch = mockFetch(data);
    const catalog = new CityModelCatalog(indexPath, new Set(), () => assert.fail('bad index published assets'));
    try {
      await catalog.update(view(), true, () => false);
      assert.equal(fetch.requests.length, 1); assert.ok(catalog.error);
    } finally { catalog.dispose(); fetch.restore(); }
  }
});

test('failed fetch, checksum mismatch, invalid models and duplicate IDs never publish partial tiles', async () => {
  const cases = ['http', 'sha', 'legacy-id', 'duplicate-id', 'model-path', 'coordinates', 'footprints'];
  for (const failure of cases) {
    const data = fixture(1, 2), tile = data.index.tiles[0];
    const body = JSON.parse(data.bodies.get(tile.path));
    if (failure === 'legacy-id') body.assets[0].id = 'legacy';
    if (failure === 'duplicate-id') body.assets[1].id = body.assets[0].id;
    if (failure === 'model-path') body.assets[0].model = '../secret.glb';
    if (failure === 'coordinates') body.assets[0].coordinate.lon = 180;
    if (failure === 'footprints') body.assets[0].footprintIds = [null];
    data.bodies.set(tile.path, JSON.stringify(body));
    tile.sha256 = failure === 'sha' ? '0'.repeat(64) : sha(data.bodies.get(tile.path));
    const fetch = mockFetch(data, url => failure === 'http' && url.endsWith(tile.path) ? new Response('', { status: 503 }) : undefined);
    const catalog = new CityModelCatalog(indexPath, new Set(['legacy']), () => assert.fail('bad tile admitted'));
    try {
      await catalog.update(view(), true, () => false);
      assert.equal(catalog.tileCount, 0); assert.ok(catalog.error, failure);
      const count = fetch.requests.length;
      await catalog.update(view(), true, () => false);
      assert.equal(fetch.requests.length, count, 'failed tiles do not create retry loops');
    } finally { catalog.dispose(); fetch.restore(); }
  }
});

test('namespaced GLB paths are accepted while traversal, absolute URLs and query paths are rejected', async () => {
  for (const model of ['residential-survey/glb/16-20000-25000/survey-upis-42.glb',
    'residential-survey/../secret.glb', '/secret.glb', 'https://evil.test/a.glb', 'a.glb?token=1', 'a.glb#part', 'a/%2e%2e/b.glb']) {
    const data = fixture(1), tile = data.index.tiles[0];
    const body = JSON.parse(data.bodies.get(tile.path)); body.assets[0].model = model;
    data.bodies.set(tile.path, JSON.stringify(body)); tile.sha256 = sha(data.bodies.get(tile.path));
    const fetch = mockFetch(data); let assets = [];
    const catalog = new CityModelCatalog(indexPath, new Set(), tiles => { assets = tiles.flatMap(t => t.assets); });
    try {
      await catalog.update(view(), true, () => false);
      assert.equal(assets.length, model.includes('survey-upis-42') ? 1 : 0, model);
    } finally { catalog.dispose(); fetch.restore(); }
  }
});

test('official building without an Overture counterpart can have empty footprint matches', async () => {
  const data = fixture(1), tile = data.index.tiles[0];
  const body = JSON.parse(data.bodies.get(tile.path)); body.assets[0].footprintIds = [];
  data.bodies.set(tile.path, JSON.stringify(body)); tile.sha256 = sha(data.bodies.get(tile.path));
  const fetch = mockFetch(data); let h;
  try {
    h = await modelsHarness(data);
    h.models.setMode(true); await h.models.loadNearby(); h.models.render(h.args);
    const state = h.models.getState();
    assert.equal(state.models.length, 2);
    assert.equal(state.models.find(m => m.id === 'tile-0-model-0').active, true);
    assert.deepEqual(state.activeFootprintIds, []);
    assert.equal(state.error, null);
  } finally { h?.models.destroy(); fetch.restore(); }
});

test('duplicate model identity in another tile is rejected even after its first tile was evicted', async () => {
  const data = fixture(34), last = data.index.tiles[33];
  const body = JSON.parse(data.bodies.get(last.path)); body.assets[0].id = 'tile-0-model-0';
  data.bodies.set(last.path, JSON.stringify(body)); last.sha256 = sha(data.bodies.get(last.path));
  const fetch = mockFetch(data);
  const catalog = new CityModelCatalog(indexPath, new Set(), () => {});
  try {
    for (let i = 0; i < 34; i++) await catalog.update(view(i), true, () => false);
    assert.match(catalog.error, /duplicate/);
    assert.equal(catalog.tileCount, 32);
  } finally { catalog.dispose(); fetch.restore(); }
});

async function modelsHarness(data) {
  let current = view(), ready = true;
  const queries = [], footprints = [];
  const map = {
    getZoom: () => current.zoom, getCenter: () => ({ lng: current.lon, lat: current.lat }),
    getBounds: () => ({ getWest: () => current.west, getEast: () => current.east, getSouth: () => current.south, getNorth: () => current.north }),
    getTerrain: () => ({}), getSource: () => ({}), isSourceLoaded: () => ready,
    queryTerrainElevation: coordinate => { queries.push(coordinate); return coordinate[0]*100; },
    triggerRepaint() {}, on() {}, off() {}, addLayer() {}, getLayer: () => null,
  };
  const legacy = asset('legacy', 125, 37.5);
  const models = new CityModels(map, { assets: [legacy], catalogIndex: indexPath, onActiveFootprints: ids => footprints.push(ids) });
  await models.init();
  models.renderer = { resetState() {}, render() {}, dispose() {}, info: { render: { calls: 3 } } };
  models.loadEntry = async entry => {
    entry.scene = new THREE.Scene(); entry.pending = undefined; models.trackEntry(entry);
  };
  const args = { defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } };
  return { models, args, queries, footprints, legacy,
    setView: next => { current = next; }, setReady: value => { ready = value; } };
}

test('CityModels integrates lazy tiles while preserving legacy identity, per-building terrain and footprint precedence', async () => {
  const data = fixture(2, 40), fetch = mockFetch(data);
  let h;
  try {
    h = await modelsHarness(data);
    assert.equal(fetch.requests.length, 0, 'initial 2D view does not load the catalog');
    const original = h.models.entries[0];
    h.models.setFootprintMatches({ legacy: ['old-source'], 'tile-0-model-0': ['wrong-global-match'] });
    h.models.setMode(true); await h.models.loadNearby(); h.models.render(h.args);
    let state = h.models.getState();
    assert.equal(state.catalogTotal, 81); assert.equal(state.models.length, 41);
    assert.equal(state.models.filter(m => m.loaded).length, 32); assert.equal(state.models.filter(m => m.active).length, 32);
    assert.equal(h.queries.length, 32);
    assert.equal(new Set(h.queries.map(p => p[0])).size, 32, 'every building queries its own ground');
    assert.ok(state.activeFootprintIds.includes('source-tile-0-model-0'));
    assert.ok(!state.activeFootprintIds.includes('wrong-global-match'));
    h.setView(view(1)); await h.models.loadNearby(); h.models.render(h.args);
    state = h.models.getState();
    assert.equal(state.models.filter(m => m.loaded).length, 48);
    assert.equal(h.models.entries[0], original); assert.equal(original.asset, h.legacy);
    assert.ok(state.activeFootprintIds.every(id => id.startsWith('source-tile-1-')));
    h.setReady(false); h.models.render(h.args); assert.deepEqual(h.models.getState().activeFootprintIds, []);
    h.setReady(true); h.models.setVisible(false); assert.deepEqual(h.models.getState().activeFootprintIds, []);
    h.setView(view(0, 15)); h.models.setVisible(true); await h.models.loadNearby(); h.models.render(h.args);
    assert.deepEqual(h.models.getState().activeFootprintIds, []);
  } finally { h?.models.destroy(); fetch.restore(); }
});

test('optional index failure keeps original entries and original footprint replacement working', async () => {
  const data = fixture(1), fetch = mockFetch(data, url => url.endsWith('index.json') ? new Response('', { status: 500 }) : undefined);
  let h;
  try {
    h = await modelsHarness(data);
    h.models.entries[0].asset.coordinate.lon = 126.002;
    h.models.setFootprintMatches({ legacy: ['old-source'] });
    h.models.setMode(true); await h.models.loadNearby(); h.models.render(h.args);
    const state = h.models.getState();
    assert.equal(state.models.length, 1); assert.ok(state.error);
    assert.deepEqual(state.activeFootprintIds, ['old-source']);
  } finally { h?.models.destroy(); fetch.restore(); }
});

test('CityModels metadata eviction disposes cold GLBs while retaining legacy and pending tile entries', async () => {
  const data = fixture(36), fetch = mockFetch(data);
  let h;
  try {
    h = await modelsHarness(data);
    h.models.setMode(true); await h.models.loadNearby(); h.models.render(h.args);
    const pinned = h.models.entries.find(e => e.catalogTile);
    pinned.pending = new Promise(() => {}); h.models.trackEntry(pinned);
    let disposed = 0;
    for (let i = 1; i < 36; i++) {
      h.setView(view(i)); await h.models.loadNearby(); h.models.render(h.args);
      const entry = h.models.entries.find(e => e.asset.id === `tile-${i}-model-0`);
      const geometry = new THREE.BoxGeometry(1, 1, 1);
      geometry.addEventListener('dispose', () => { disposed++; });
      entry.scene.add(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial()));
      assert.ok(h.models.catalog.tileCount <= 32);
      assert.ok(h.models.entries.length <= 33);
      assert.ok(h.models.entries.includes(pinned), 'in-flight model metadata is pinned');
      assert.equal(h.models.entries[0].asset, h.legacy);
    }
    assert.ok(disposed > 0, 'metadata eviction also releases the evicted GLB geometry');
    assert.ok(!h.models.entries.some(e => e.asset.id === 'tile-1-model-0'));
    pinned.pending = undefined; h.models.trackEntry(pinned);
  } finally { h?.models.destroy(); fetch.restore(); }
});

test('CityModels cancels incoming metadata on disable and restores loading only after re-enable', async () => {
  const data = fixture(1), tile = data.index.tiles[0];
  let started, release;
  const waiting = new Promise(resolve => { started = resolve; });
  let delayed = true;
  const fetch = mockFetch(data, async url => {
    if (delayed && url.endsWith(tile.path)) { started(); await new Promise(resolve => { release = resolve; }); delayed = false; }
  });
  let h;
  try {
    h = await modelsHarness(data);
    h.models.setMode(true); const pending = h.models.loadNearby(); await waiting;
    h.models.setVisible(false); release(); await pending;
    assert.equal(h.models.getState().models.length, 1);
    assert.deepEqual(h.models.getState().activeFootprintIds, []);
    h.models.setVisible(true); await h.models.loadNearby(); h.models.render(h.args);
    assert.equal(h.models.getState().models.length, 2);
    assert.deepEqual(h.models.getState().activeFootprintIds, ['source-tile-0-model-0']);
  } finally { h?.models.destroy(); fetch.restore(); }
});
