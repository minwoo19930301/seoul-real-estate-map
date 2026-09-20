import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { MercatorCoordinate } from 'maplibre-gl';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { CityModels, modelMercatorMatrix } from '../src/city-models.ts';

const manifest = JSON.parse(readFileSync(new URL('../public/models/manifest.json', import.meta.url)));
const assetBytes = asset => readFileSync(new URL(`../public/models/${asset.model}`, import.meta.url));
for (const asset of manifest.assets) test(`${asset.id}: actual GLB SHA, physical bounds, metre axes and published height envelope`, async () => {
  const bytes = assetBytes(asset);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), asset.sha256);
  const { scene } = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  const box = new THREE.Box3().setFromObject(scene);
  const dimensions = box.getSize(new THREE.Vector3()).toArray();
  dimensions.forEach((n, i) => assert.ok(Math.abs(n - asset.dimensions[i]) < 0.0001));
  assert.ok(Math.abs(box.min.y) < 0.0001);
  const coordinate = [asset.coordinate.lon, asset.coordinate.lat];
  const scale = MercatorCoordinate.fromLngLat(coordinate).meterInMercatorCoordinateUnits();
  for (const exaggeration of [1, 2, 4]) {
    const ground = 57 * exaggeration;
    const matrix = modelMercatorMatrix(coordinate, ground);
    const base = new THREE.Vector3(0, 0, 0).applyMatrix4(matrix);
    const roof = new THREE.Vector3(0, asset.dimensions[1], 0).applyMatrix4(matrix);
    assert.ok(Math.abs((roof.z - base.z) / scale - asset.dimensions[1]) < 1e-7);
    assert.ok(Math.abs(base.z / scale - ground) < 1e-7);
    const east = new THREE.Vector3(1, 0, 0).applyMatrix4(matrix).sub(base);
    const south = new THREE.Vector3(0, 0, 1).applyMatrix4(matrix).sub(base);
    assert.ok(east.x > 0 && south.y > 0);
    const oriented = matrix.clone().multiply(new THREE.Matrix4().makeRotationY(asset.yawDegFromEast * Math.PI / 180));
    const widthAxis = new THREE.Vector3(1, 0, 0).applyMatrix4(oriented).sub(base);
    const heading = Math.atan2(-widthAxis.y, widthAxis.x) * 180 / Math.PI;
    assert.ok(Math.abs(heading - asset.yawDegFromEast) < 0.000001);
  }
});

function harness() {
  const footprints = [], stateEvents = [];
  let ground = 80, ready = true, center = [127.102679, 37.5125537];
  const map = {
    getZoom: () => 16,
    getCenter: () => ({ lng: center[0], lat: center[1] }),
    getBounds: () => ({ getWest: () => center[0] - 0.002, getEast: () => center[0] + 0.002, getSouth: () => center[1] - 0.002, getNorth: () => center[1] + 0.002 }),
    getTerrain: () => ({ source: 'local-terrain', exaggeration: 4 }),
    getSource: () => ({}), isSourceLoaded: () => ready,
    queryTerrainElevation: () => ground, triggerRepaint() {}, off() {}, getLayer: () => null,
  };
  const models = new CityModels(map, { onActiveFootprints: ids => footprints.push(ids), onState: state => stateEvents.push(state) });
  models.entries = manifest.assets.filter(a => ['sixtythree', 'lotte', 'nseoul', 'coex'].includes(a.id)).map(asset => ({ asset, scene: new THREE.Scene(), error: null, ground: null, draws: 0, active: false }));
  models.renderer = { resetState() {}, render() {}, dispose() {}, info: { render: { calls: 3 } } };
  models.setFootprintMatches(Object.fromEntries(manifest.assets.map(asset => [asset.id, [`real-id:${asset.id}`]])));
  const args = { defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } };
  return { models, args, footprints, stateEvents, setGround: value => { ground = value; }, setReady: value => { ready = value; }, setCenter: value => { center = value; } };
}

test('only rendered nearby models replace matching solids; repeat frames do not churn UI; toggles restore originals', () => {
  const h = harness(); h.models.setMode(true); h.models.render(h.args);
  assert.deepEqual(h.models.getState().activeFootprintIds, ['real-id:lotte']);
  const callbacks = h.footprints.length, states = h.stateEvents.length;
  for (let i = 0; i < 10; i++) h.models.render(h.args);
  assert.equal(h.footprints.length, callbacks); assert.equal(h.stateEvents.length, states);
  assert.equal(h.models.getState().models.find(m => m.id === 'sixtythree').drawCount, 0);
  h.models.renderer.info.render.calls = 0;
  h.models.render(h.args);
  assert.deepEqual(h.models.getState().activeFootprintIds, []);
  h.models.renderer.info.render.calls = 3;
  h.models.render(h.args);
  h.models.setVisible(false); assert.deepEqual(h.models.getState().activeFootprintIds, []);
  h.models.setVisible(true); h.models.render(h.args);
  h.models.setMode(false); assert.deepEqual(h.models.getState().activeFootprintIds, []);
  h.models.destroy();
});

test('missing DEM and rendering failure keep generic solids; terrain changes only alter model base', () => {
  const h = harness(); h.models.setMode(true); h.setReady(false); h.models.render(h.args);
  assert.deepEqual(h.models.getState().activeFootprintIds, []);
  h.setReady(true); h.models.render(h.args);
  h.setGround(320); h.models.updateTerrain(); h.models.render(h.args);
  const lotte = h.models.getState().models.find(m => m.id === 'lotte');
  assert.equal(lotte.ground_m, 320); assert.equal(lotte.height_m, 555);
  h.models.renderer.render = () => { throw new Error('GPU failure'); };
  h.models.render(h.args);
  assert.deepEqual(h.models.getState().activeFootprintIds, []);
  assert.equal(h.models.getState().models.find(m => m.id === 'lotte').error, 'GPU failure');
  h.models.destroy();
});

test('nearby GLB is lazy loaded once; far models stay unfetched', async () => {
  const h = harness(); h.models.entries.forEach(e => { e.scene = undefined; });
  const originalFetch = globalThis.fetch, requests = [];
  globalThis.fetch = async url => {
    requests.push(url);
    const asset = manifest.assets.find(a => `/models/${a.model}` === url);
    assert.ok(asset); return new Response(assetBytes(asset));
  };
  try {
    await h.models.loadNearby(); assert.deepEqual(requests, []);
    h.models.setMode(true); await h.models.loadNearby();
    assert.deepEqual(requests, ['/models/lotte.glb']);
    await h.models.loadNearby(); assert.equal(requests.length, 1);
    assert.equal(h.models.getState().models.filter(m => m.loaded).length, 1);
  } finally { globalThis.fetch = originalFetch; h.models.destroy(); }
});

test('trees reuse GPU geometry, survive model toggle, and clear without allocations', () => {
  const h = harness(); const trees = [{ coordinate: [127.1026, 37.5125], height_m: 8, crown_radius_m: 3 }];
  h.models.setTrees(trees); const trunk = h.models.trunks, crown = h.models.crowns;
  h.models.setTrees(structuredClone(trees)); assert.equal(h.models.trunks, trunk);
  h.models.setMode(true); h.models.setTreesVisible(true); h.models.setVisible(false); h.models.render(h.args);
  assert.equal(h.models.getState().trees.activeCount, 1);
  assert.deepEqual(h.models.getState().activeFootprintIds, []);
  h.models.setTrees([]); h.models.setTrees([]);
  assert.equal(h.models.trunks, trunk); assert.equal(h.models.crowns, crown);
  assert.equal(trunk.count, 0); assert.equal(crown.count, 0);
  h.models.setTrees(trees); assert.equal(h.models.trunks, trunk);
  h.models.destroy();
});

test('invalid manifest fails before fetch and exits loading state with originals retained', async () => {
  const h = harness();
  const entry = h.models.entries.find(e => e.asset.id === 'lotte');
  entry.scene = undefined; entry.asset = { ...entry.asset, model: '../unexpected.glb' };
  h.models.setMode(true); await h.models.loadNearby();
  const state = h.models.getState();
  assert.equal(state.loading, false);
  assert.equal(state.models.find(m => m.id === 'lotte').error, 'Invalid model manifest');
  assert.ok(state.message.includes('불러오지 못했습니다'));
  assert.deepEqual(state.activeFootprintIds, []);
  h.models.destroy();
});

test('namespaced GLB path loads the verified per-building mesh without changing its ground placement', async () => {
  const h = harness();
  const entry = h.models.entries.find(e => e.asset.id === 'lotte');
  const originalAsset = entry.asset;
  entry.scene = undefined;
  entry.asset = { ...originalAsset, model: 'residential-survey/glb/16-55909-25393/survey-upis-42.glb' };
  const originalFetch = globalThis.fetch, requests = [];
  globalThis.fetch = async url => { requests.push(url); return new Response(assetBytes(originalAsset)); };
  try {
    h.models.setMode(true); await h.models.loadNearby(); h.models.render(h.args);
    assert.deepEqual(requests, ['/models/residential-survey/glb/16-55909-25393/survey-upis-42.glb']);
    const state = h.models.getState().models.find(m => m.id === 'lotte');
    assert.equal(state.loaded, true); assert.equal(state.active, true);
    assert.equal(state.ground_m, 80); assert.equal(state.height_m, 555);
  } finally { globalThis.fetch = originalFetch; h.models.destroy(); }
});

test('dense district catalog limits concurrent loads and evicts old GPU scenes across navigation', async () => {
  const h = harness();
  const template = manifest.assets.find(a => a.id === 'lotte');
  h.models.entries = Array.from({ length: 20000 }, (_, i) => ({
    asset: { ...template, id: `district-${i}`, coordinate: { lon: 127.102679 + (i >= 40 ? 0.05 : 0), lat: 37.5125537 + (i % 40) * 0.000001 } },
    error: null, ground: null, draws: 0, active: false,
  }));
  const originalFetch = globalThis.fetch;
  let active = 0, maxActive = 0, requests = 0;
  globalThis.fetch = async () => {
    active++; requests++; maxActive = Math.max(maxActive, active);
    await new Promise(resolve => setTimeout(resolve, 3));
    active--; return new Response(assetBytes(template));
  };
  try {
    h.models.setMode(true); await h.models.loadNearby();
    assert.equal(requests, 32); assert.ok(maxActive <= 4);
    h.models.render(h.args);
    assert.equal(h.models.getState().models.filter(m => m.active).length, 32);
    h.setCenter([127.152679, 37.5125537]); await h.models.loadNearby();
    assert.equal(requests, 64);
    assert.equal(h.models.getState().models.filter(m => m.loaded).length, 48);
    assert.ok(h.models.entries.slice(0, 40).some(e => !e.scene));
    h.models.render(h.args);
    assert.ok(h.models.getState().models.filter(m => m.active).every(m => Number(m.id.split('-')[1]) >= 40));
  } finally { globalThis.fetch = originalFetch; h.models.destroy(); }
});

test('moving away cancels queued model work while originals stay visible', async () => {
  const h = harness();
  const template = manifest.assets.find(a => a.id === 'lotte');
  h.models.entries = Array.from({ length: 40 }, (_, i) => ({ asset: { ...template, id: `queued-${i}` }, error: null, ground: null, draws: 0, active: false }));
  const originalFetch = globalThis.fetch;
  let requests = 0;
  globalThis.fetch = async () => {
    requests++;
    h.setCenter([126.8, 37.7]);
    await new Promise(resolve => setTimeout(resolve, 3));
    return new Response(assetBytes(template));
  };
  try {
    h.models.setMode(true); await h.models.loadNearby();
    assert.ok(requests <= 4);
    h.models.render(h.args); assert.deepEqual(h.models.getState().activeFootprintIds, []);
  } finally { globalThis.fetch = originalFetch; h.models.destroy(); }
});

test('20000-entry catalog reuses nearby selection and avoids full QA state construction on repeat frames', () => {
  const h = harness();
  const template = manifest.assets.find(a => a.id === 'lotte');
  h.models.entries = Array.from({ length: 20000 }, (_, i) => ({
    asset: { ...template, id: `cached-${i}`, coordinate: { lon: 127.102679 + (i >= 32 ? .05 : 0), lat: 37.5125537 + (i % 32) * .000001 } },
    scene: i < 32 ? new THREE.Scene() : undefined, error: null, ground: null, draws: 0, active: false,
  }));
  let boundsReads = 0, visibilityChecks = 0, fullStates = 0;
  const bounds = h.models.map.getBounds;
  h.models.map.getBounds = () => { boundsReads++; return bounds(); };
  const inView = h.models.inView.bind(h.models);
  h.models.inView = (...args) => { visibilityChecks++; return inView(...args); };
  const getState = h.models.getState.bind(h.models);
  h.models.getState = () => { fullStates++; return getState(); };
  const first = h.models.nearbyEntries();
  assert.equal(first.length, 32); assert.equal(boundsReads, 1); assert.equal(visibilityChecks, 20000);
  assert.equal(h.models.nearbyEntries(), first);
  assert.equal(boundsReads, 2); assert.equal(visibilityChecks, 20000);
  // Skip asynchronous loading so only the repeated render path is measured.
  h.models.is25d = true; h.models.render(h.args);
  const events = h.stateEvents.length;
  boundsReads = 0; visibilityChecks = 0; fullStates = 0;
  for (let i = 0; i < 50; i++) h.models.render(h.args);
  assert.equal(boundsReads, 50, 'one view snapshot per frame, not one per catalog entry');
  assert.equal(visibilityChecks, 0, 'unchanged view does not filter/sort the catalog again');
  assert.equal(fullStates, 0, 'unchanged frames do not materialize the complete catalog');
  assert.equal(h.stateEvents.length, events);
  const state = h.models.getState();
  assert.equal(state.models.length, 20000, 'explicit QA API still returns every model');
  assert.equal(state.models.filter(m => m.active).length, 32);
  assert.ok(state.models.filter(m => m.active).every(m => m.drawCount === 51));
  h.setGround(321); h.models.render(h.args);
  assert.equal(h.stateEvents.length, events+1, 'changed resident terrain state still emits');
  assert.ok(h.stateEvents.at(-1).models.filter(m => m.active).every(m => m.ground_m === 321));
  h.models.destroy();
});

test('nearby cache invalidates for bounds, zoom, center, categories and replaced catalog references', () => {
  const h = harness();
  const template = manifest.assets.find(a => a.id === 'lotte');
  const entry = (id, category, lon = 127.102679) => ({
    asset: { ...template, id, category, coordinate: { lon, lat: 37.5125537 } },
    error: null, ground: null, draws: 0, active: false,
  });
  h.models.entries = [entry('school', 'k12-school'), entry('bridge', 'bridge'),
    entry('culture', 'cultural-site'), entry('company', 'company-office'), entry('plain', 'apartment-complex'),
    entry('east', 'apartment-complex', 127.109)];
  const ids = () => h.models.nearbyEntries().map(e => e.asset.id).sort();
  assert.deepEqual(ids(), ['bridge', 'company', 'culture', 'plain', 'school']);
  h.models.setCategories(false, false, false, false);
  assert.deepEqual(ids(), ['plain']);
  h.models.setCategories(true, true, true, true);
  assert.equal(ids().length, 5);
  h.models.map.getZoom = () => 10;
  assert.deepEqual(ids(), []);
  h.models.map.getZoom = () => 16;
  h.models.map.getBounds = () => ({ getWest: () => 127.09, getEast: () => 127.12, getSouth: () => 37.50, getNorth: () => 37.53 });
  assert.equal(ids().length, 6, 'bounds-only change expands eligibility');
  h.setCenter([127.109, 37.5125537]);
  assert.equal(h.models.nearbyEntries()[0].asset.id, 'east', 'center-only change updates distance order');
  const old = h.models.nearbyEntries();
  h.models.entries = h.models.entries.map(e => entry('new-'+e.asset.id, e.asset.category, e.asset.coordinate.lon));
  assert.notEqual(h.models.nearbyEntries(), old);
  assert.ok(ids().every(id => id.startsWith('new-')));
  h.models.entries.push(entry('appended', 'apartment-complex'));
  assert.ok(ids().includes('appended'), 'catalog length changes are detected as well');
  h.models.destroy();
});

test('cultural visibility hides the three bespoke facilities and their retained fallbacks together', () => {
  const h = harness();
  const bespoke = JSON.parse(readFileSync(new URL('../public/models/bespoke-manifest.json', import.meta.url))).assets;
  const ids = ['bespoke-jungmyeongjeon', 'bespoke-mmca-deoksugung', 'bespoke-lg-art-center-seoul-discovery-lab'];
  const upgrades = ids.map(id => bespoke.find(asset => asset.id === id));
  const originals = upgrades.flatMap(asset => asset.supersedes.map(id => manifest.assets.find(old => old.id === id)));
  assert.ok([...upgrades, ...originals].every(Boolean), 'actual published upgrade/fallback records exist');
  h.models.entries = [...upgrades, ...originals].map(asset => ({ asset, error: null, ground: null, draws: 0, active: false }));
  h.models.map.getZoom = () => 17;
  h.models.map.getBounds = () => ({ getWest: () => 126.8, getEast: () => 127.1, getSouth: () => 37.5, getNorth: () => 37.6 });
  const selected = () => h.models.nearbyCandidates().map(entry => entry.asset.id).sort();
  const all = [...upgrades, ...originals].map(asset => asset.id).sort();
  assert.deepEqual(selected(), all, 'retained references remain available as fallbacks');
  h.models.setCategories(true, true, false, true);
  assert.deepEqual(selected(), [], 'off hides heritage, cultural and civic-cultural-landmark together');
  h.models.setCategories(true, true, true, true);
  assert.deepEqual(selected(), all, 'on restores both upgrades and fallbacks');
  h.models.destroy();
});

test('catalog admission accepts 20000 models and rejects more than 25000 before adding a layer', async () => {
  const template = manifest.assets.find(a => a.id === 'lotte');
  for (const count of [20000, 25001]) {
    const h = harness(); let layers = 0;
    h.models.map.addLayer = () => { layers++; };
    h.models.map.on = () => {};
    const assets = Array.from({ length: count }, (_, i) => ({ ...template, id: `admitted-${i}` }));
    const models = new CityModels(h.models.map, { assets });
    await models.init();
    assert.equal(layers, count <= 25000 ? 1 : 0);
    assert.equal(models.getState().models.length, count <= 25000 ? count : 0);
    assert.equal(models.getState().error, count <= 25000 ? null : '잘못된 모델 목록입니다.');
    models.destroy(); h.models.destroy();
  }
});

test('pitched bounds do not let distant buildings evict the bridge at the camera target', () => {
  const h = harness();
  const template = manifest.assets.find(a => a.id === 'lotte');
  h.models.map.getBounds = () => ({ getWest: () => 127.08, getEast: () => 127.12, getSouth: () => 37.50, getNorth: () => 37.60 });
  h.models.entries = Array.from({ length: 40 }, (_, i) => ({ asset: { ...template, id: `far-${i}`, coordinate: { lon: 127.10, lat: 37.55 + i * 0.00001 } } }));
  h.models.entries.push({ asset: { ...template, id: 'target-bridge', category: 'bridge', coordinate: { lon: 127.102679, lat: 37.5125537 }, geoBounds: [127.102, 37.51, 127.104, 37.52] } });
  assert.equal(h.models.nearbyEntries()[0].asset.id, 'target-bridge');
  assert.equal(h.models.nearbyEntries().length, 32);
  h.models.destroy();
});

test('elevation originals retain their complete manifest records and all 250 selected sites are modeled', () => {
  const originals = JSON.parse(readFileSync(new URL('./fixtures/preserved-landmarks.json', import.meta.url)));
  for (const original of originals) assert.deepEqual(manifest.assets.find(a => a.id === original.id), original);
  const candidates = ['a', 'b'].flatMap(part => JSON.parse(readFileSync(new URL(`../docs/landmark-candidates-${part}.json`, import.meta.url))));
  assert.equal(candidates.length, 250);
  assert.equal(new Set(candidates.map(a => a.id)).size, 250);
  const counts = new Map();
  const matches = JSON.parse(readFileSync(new URL('../public/models/footprint-matches.json', import.meta.url)));
  for (const candidate of candidates) {
    counts.set(candidate.district, (counts.get(candidate.district) ?? 0) + 1);
    const asset = manifest.assets.find(a => a.id === candidate.id);
    assert.ok(asset, `Missing selected model ${candidate.nameKo}`);
    assert.ok(matches[candidate.id]?.length, `No matched source footprint for ${candidate.nameKo}`);
    assert.ok(candidate.sourceUrls.length && candidate.sourceUrls.every(url => typeof url === 'string' && url.startsWith('https://')));
  }
  assert.equal(counts.size, 25);
  assert.ok([...counts.values()].every(n => n === 10));
  assert.ok(manifest.assets.some(a => a.id === 'gyeongbokgung'));
  const priorIds = [
    ...JSON.parse(readFileSync(new URL('./fixtures/preserved-1550-landmarks.json', import.meta.url))).map(a => a.id),
    ...JSON.parse(readFileSync(new URL('../docs/apartment-100-candidates.json', import.meta.url))).map(a => a.id),
    ...JSON.parse(readFileSync(new URL('../docs/civic-company-candidates.json', import.meta.url))).map(a => a.id),
  ];
  assert.equal(new Set(priorIds).size, 3088, 'the previous completed batch remains the fixed baseline');
  const currentIds = new Set(manifest.assets.map(a => a.id));
  for (const id of priorIds) assert.ok(currentIds.has(id), `Missing baseline model ${id}`);
});
