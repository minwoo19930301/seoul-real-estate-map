import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { CityModels } from '../src/city-models.ts';

const asset = (id, extra = {}) => ({ id, nameKo: id, model: `${id}.glb`, quality: 'reference',
  coordinate: { lon: 127, lat: 37.5 }, dimensions: [10, 30, 10], yawDegFromEast: 0,
  footprintIds: [`fp-${id}`], supersedes: [], ...extra });
const entry = a => ({ asset: a, scene: new THREE.Scene(), error: null, ground: null, draws: 0, active: false });
const frame = { defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } };
function harness(entries) {
  const map = { getZoom: () => 18, getCenter: () => ({ lng: 127, lat: 37.5 }),
    getBounds: () => ({ getWest: () => 126.98, getEast: () => 127.02, getSouth: () => 37.48, getNorth: () => 37.52 }),
    getTerrain: () => ({}), getSource: () => ({}), isSourceLoaded: () => true,
    queryTerrainElevation: () => 40, triggerRepaint() {}, off() {}, getLayer: () => null };
  const models = new CityModels(map); models.entries = entries; models.is25d = true;
  models.renderer = { info: { render: { calls: 0 } }, resetState() {}, dispose() {},
    render(scene) { this.info.render.calls = scene.userData.calls ?? 1; } };
  return models;
}
const upgradedMaple = [208, 209, 210, 211, 212, 213];
function maple() {
  const old = Array.from({ length: 29 }, (_, i) => entry(asset(`maple-${201+i}`, {
    coordinate: { lon: 127 + i * .0001, lat: 37.5 },
  })));
  const auxiliary = ['kindergarten', 'road'].map(id => entry(asset(id)));
  const upgrades = upgradedMaple.map(n => entry(asset(`bespoke-maple-xi-${n}`, {
    supersedes: [`maple-${n}`], footprintIds: [`fp-maple-${n}`], coordinate: { lon: 127.001, lat: 37.5 },
  })));
  const models = harness([...old, ...auxiliary, ...upgrades]);
  return { models, old, auxiliary, upgrades };
}

test('31-piece Maple site draws all 29 towers and two auxiliaries without charging six hidden references to primary budget', () => {
  const h = maple();
  assert.equal(h.models.nearbyEntries().length, 31);
  assert.equal(h.models.nearbyCandidates().length, 37);
  h.models.render(frame);
  const active = h.models.getState().models.filter(m => m.active).map(m => m.id);
  assert.equal(active.length, 31);
  for (let n = 201; n <= 229; n++) assert.ok(active.includes(upgradedMaple.includes(n) ? `bespoke-maple-xi-${n}` : `maple-${n}`));
  assert.ok(h.auxiliary.every(e => e.active));
  assert.ok(h.old.filter(e => upgradedMaple.some(n => e.asset.id === `maple-${n}`)).every(e => !e.active));
  h.models.destroy();
});

test('dense site uses the retained same-tower reference for pending, failed, or camera-culled upgrade', () => {
  for (const mode of ['pending', 'failed', 'culled']) {
    const h = maple(), upgrade = h.upgrades.find(e => e.asset.id === 'bespoke-maple-xi-210'), old = h.old.find(e => e.asset.id === 'maple-210');
    if (mode === 'pending') { upgrade.scene = undefined; upgrade.pending = Promise.resolve(); }
    if (mode === 'failed') { upgrade.scene = undefined; upgrade.error = 'HTTP 404'; }
    if (mode === 'culled') upgrade.scene.userData.calls = 0;
    h.models.render(frame);
    assert.equal(old.active, true, mode);
    assert.equal(upgrade.active, false, mode);
    assert.ok(h.upgrades.filter(e => e !== upgrade).every(e => e.active), mode);
    assert.equal(h.models.getState().models.filter(m => m.active).length, 31, mode);
    assert.ok(h.old.filter(e => !upgradedMaple.some(n => e.asset.id === `maple-${n}`)).every(e => e.active), mode);
    h.models.destroy();
  }
});

test('replacement closure cannot protect more than 48 resident scenes or draw more than 32 models', () => {
  const primaries = Array.from({ length: 32 }, (_, i) => entry(asset(`new-${i}`, { supersedes: [`old-${i}`] })));
  const old = Array.from({ length: 32 }, (_, i) => entry(asset(`old-${i}`, { supersedes: [`generic-${i}`] })));
  const generic = Array.from({ length: 32 }, (_, i) => entry(asset(`generic-${i}`, { quality: undefined })));
  const models = harness([...generic, ...old, ...primaries]);
  assert.equal(models.nearbyEntries().length, 32);
  assert.equal(models.nearbyCandidates().length, 48);
  models.trimCache();
  assert.equal(models.entries.filter(e => e.scene).length, 48);
  models.render(frame);
  assert.equal(models.entries.filter(e => e.active).length, 32);
  assert.ok(primaries.every(e => e.active));
  assert.ok([...old, ...generic].every(e => !e.active));
  models.destroy();
});

test('a partial split-compound failure keeps one compound and never draws a ready peer through it', () => {
  const compound = entry(asset('old-compound'));
  const a = entry(asset('split-a', { supersedes: ['old-compound'] }));
  const b = entry(asset('split-b', { supersedes: ['old-compound'] })); b.scene = undefined; b.error = '404';
  const neighbours = Array.from({ length: 28 }, (_, i) => entry(asset(`neighbour-${i}`)));
  const models = harness([compound, ...neighbours, a, b]);
  models.render(frame);
  assert.equal(compound.active, true); assert.equal(a.active, false); assert.equal(b.active, false);
  assert.ok(neighbours.every(e => e.active));
  assert.equal(models.entries.filter(e => e.active).length, 29);
  models.destroy();
});

test('the five preserved landmarks retain selection priority over a dense generic neighbourhood', () => {
  const ids = ['sixtythree', 'lotte', 'nseoul', 'coex', 'gyeongbokgung'];
  const originals = ids.map(id => entry(asset(id, { quality: undefined })));
  const generic = Array.from({ length: 50 }, (_, i) => entry(asset(`generic-${i}`, { quality: undefined })));
  const models = harness([...generic, ...originals]);
  models.trimCache(); models.render(frame);
  assert.ok(originals.every(e => e.active));
  assert.equal(models.entries.filter(e => e.active).length, 32);
  assert.equal(models.entries.filter(e => e.scene).length, 48);
  models.destroy();
});

test('a pending multi-building replacement cannot turn its many fallback models into more than 32 active draws', () => {
  const generic = Array.from({ length: 20 }, (_, i) => entry(asset(`generic-${i}`, { quality: undefined })));
  const replacement = entry(asset('replacement', { supersedes: generic.map(e => e.asset.id) })); replacement.scene = undefined;
  const neighbours = Array.from({ length: 31 }, (_, i) => entry(asset(`neighbour-${i}`)));
  const models = harness([replacement, ...neighbours, ...generic]);
  assert.equal(models.nearbyEntries().length, 32);
  assert.equal(models.nearbyCandidates().length, 48);
  models.render(frame);
  assert.ok(neighbours.every(e => e.active));
  assert.equal(generic.filter(e => e.active).length, 1);
  assert.equal(models.entries.filter(e => e.active).length, 32);
  models.destroy();
});

test('loading the 31 primary models plus six retained references keeps four-worker scheduling and a bounded resident cache', async () => {
  const h = maple(), requested = []; let inflight = 0, peak = 0;
  for (const e of h.models.entries) e.scene = undefined;
  h.models.loadEntry = async e => {
    requested.push(e.asset.id); peak = Math.max(peak, ++inflight);
    await new Promise(resolve => setTimeout(resolve, 2));
    e.scene = new THREE.Scene(); e.pending = undefined; inflight--; h.models.trackEntry(e);
  };
  await h.models.loadNearby();
  assert.equal(requested.length, 37); assert.equal(new Set(requested).size, 37);
  assert.equal(peak, 4);
  assert.ok(h.models.entries.filter(e => e.scene).length <= 48);
  h.models.render(frame);
  assert.equal(h.models.entries.filter(e => e.active).length, 31);
  h.models.destroy();
});
