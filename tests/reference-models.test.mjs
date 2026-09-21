import test from 'node:test';
import assert from 'node:assert/strict';
import { referenceManifest } from '../src/reference-models.ts';
import { CityModels } from '../src/city-models.ts';
import * as THREE from 'three';
import { readFileSync } from 'node:fs';

const asset = (id, extra = {}) => ({ id, model: `${id}.glb`, sha256: 'a'.repeat(64), quality: 'reference', nameKo: id, dimensions: [10, 20, 10], coordinate: { lon: 126.9, lat: 37.5 }, yawDegFromEast: 0, footprintIds: ['fp-' + id], supersedes: [], ...extra });
const place = { id: 'p', name: '테스트', subtitle: '', center: [126.9, 37.5], zoom: 15, source_url: 'https://example.test' };
const preserved = [{ id: 'generic', model: 'generic.glb' }];

test('reference validator accepts valid fixture and rejects duplicate/path/cyclic supersedes', () => {
  const valid = referenceManifest({ version: 1, assets: [asset('ref-a', { supersedes: ['generic'] })], places: [place] }, preserved);
  assert.equal(valid.assets[0].quality, 'reference');
  assert.throws(() => referenceManifest({ version: 1, assets: [asset('bad.id')], places: [place] }, preserved));
  assert.throws(() => referenceManifest({ version: 1, assets: [asset('ref-a'), asset('ref-a')], places: [place] }, preserved));
  assert.throws(() => referenceManifest({ version: 1, assets: [asset('ref-a', { supersedes: ['ref-b'] }), asset('ref-b', { supersedes: ['ref-a'] })], places: [place] }, preserved));
  assert.throws(() => referenceManifest({ version: 1, assets: [asset('ref-a', { supersedes: ['ref-a'] })], places: [place] }, preserved));
});

test('reference validator accepts replacement generations in either catalog order', () => {
  const chain = [asset('ref-a', {supersedes: ['generic']}), asset('ref-b', {supersedes: ['ref-a']}),
    asset('ref-c', {supersedes: ['ref-b', 'ref-a', 'generic']})];
  for (const assets of [chain, [...chain].reverse()]) {
    assert.equal(referenceManifest({version: 1, assets, places: []}, preserved).assets.length, 3);
  }
  chain[0].supersedes.push('ref-c');
  assert.throws(() => referenceManifest({version: 1, assets: chain, places: []}, preserved));
});

test('published catalogs accept the corrected Maple tower without dropping all bespoke models', () => {
  const read = name => JSON.parse(readFileSync(new URL(`../public/models/${name}.json`, import.meta.url)));
  const base = read('manifest');
  const reference = referenceManifest(read('reference-manifest'), base.assets);
  const bespoke = referenceManifest(read('bespoke-manifest'), [...base.assets, ...reference.assets]);
  assert.ok(bespoke.assets.some(asset => asset.id === 'bespoke-maple-xi-213-corrected'));
  assert.ok(bespoke.assets.some(asset => asset.id === 'bespoke-maple-xi-213'));
});

test('reference entries carry visible footprint replacement metadata', () => {
  const value = referenceManifest({ version: 1, assets: [asset('ref-a', { footprintIds: ['solid-1', 'solid-2'], supersedes: ['generic-1'] })], places: [place] }, preserved);
  assert.deepEqual(value.assets[0].footprintIds, ['solid-1', 'solid-2']);
  assert.deepEqual(value.assets[0].supersedes, ['generic-1']);
});

test('preserved landmark descendants extend known assets and reject invalid identities', () => {
  const value = { version: 1, assets: [], places: [], preservedLandmarkFootprints: { generic: ['parent', 'part'] } };
  assert.deepEqual(referenceManifest(value, preserved).preservedLandmarkFootprints.generic, ['parent', 'part']);
  assert.throws(() => referenceManifest({ ...value, preservedLandmarkFootprints: { missing: ['part'] } }, preserved));
  assert.throws(() => referenceManifest({ ...value, preservedLandmarkFootprints: { generic: [''] } }, preserved));
});

function cityHarness() {
  const events=[]; let center=[127.1,37.5], ready=true;
  const map={getZoom:()=>16,getCenter:()=>({lng:center[0],lat:center[1]}),getBounds:()=>({getWest:()=>center[0]-.002,getEast:()=>center[0]+.002,getSouth:()=>center[1]-.002,getNorth:()=>center[1]+.002}),getTerrain:()=>({source:'local',exaggeration:1}),getSource:()=>({}),isSourceLoaded:()=>ready,queryTerrainElevation:()=>80,triggerRepaint(){},off(){},getLayer:()=>null};
  const m=new CityModels(map,{onActiveFootprints:x=>events.push(x)}); const base=JSON.parse(readFileSync(new URL('../public/models/manifest.json',import.meta.url))).assets.find(x=>x.id==='lotte');
  const ref={...base,id:'ref',nameKo:'Reference',quality:'reference',supersedes:['generic'],footprintIds:['fp-ref'],coordinate:{lon:127.1,lat:37.5}};
  const generic={...base,id:'generic',nameKo:'Generic',coordinate:{lon:127.1,lat:37.5}};
  m.entries=[{asset:generic,scene:new THREE.Scene(),error:null,ground:null,draws:0,active:false},{asset:ref,scene:new THREE.Scene(),error:null,ground:null,draws:0,active:false}];
  m.renderer={resetState(){},render(){},dispose(){},info:{render:{calls:2}}}; m.setMode(true); return {m,events,map,setCenter:x=>center=x,setReady:x=>ready=x};
}
test('reference model hides superseded footprint only while reference is active',()=>{const h=cityHarness();h.m.render({defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}});assert.deepEqual(h.m.getState().activeFootprintIds,['fp-ref']);h.m.setVisible(false);assert.deepEqual(h.m.getState().activeFootprintIds,[]);h.m.destroy();});
test('reference load failure restores superseded generic visibility',async()=>{const h=cityHarness(), old=globalThis.fetch;globalThis.fetch=async()=>{throw new Error('load failed')};try{h.m.entries[1].scene=undefined;await h.m.loadNearby();h.m.render({defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}});assert.deepEqual(h.m.getState().activeFootprintIds,[]);assert.equal(h.m.getState().models.find(x=>x.id==='generic').active,true)}finally{globalThis.fetch=old;h.m.destroy()}});
test('reference replacement recovers after toggle and view changes',()=>{const h=cityHarness(),a={defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}};h.m.render(a);h.m.setVisible(false);h.m.setVisible(true);h.setCenter([126.8,37.7]);h.m.render(a);assert.deepEqual(h.m.getState().activeFootprintIds,[]);h.setCenter([127.1,37.5]);h.m.render(a);assert.deepEqual(h.m.getState().activeFootprintIds,['fp-ref']);h.m.destroy()});
test('reference priority remains selected with 32 nearby generic catalog entries',()=>{const h=cityHarness();const g=h.m.entries[0];h.m.entries=[h.m.entries[1],...Array.from({length:32},(_,i)=>({...g,asset:{...g.asset,id:'g'+i,coordinate:{lon:127.1,lat:37.5}}}))];h.m.render({defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}});assert.ok(h.m.getState().models.find(x=>x.id==='ref').active);assert.equal(h.m.getState().activeFootprintIds.includes('fp-ref'),true);h.m.destroy()});

test('a partly overlapping compound GLB yields to the landmark without hiding its unrelated source solids', () => {
  const h = cityHarness(), [generic, reference] = h.m.entries;
  reference.asset.supersedes = [];
  generic.asset.footprintIds = ['fp-ref', 'neighbour'];
  h.m.setFootprintMatches({ generic: ['fp-ref', 'neighbour'] });
  h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
  assert.equal(generic.active, false);
  assert.equal(reference.active, true);
  assert.deepEqual(h.m.getState().activeFootprintIds, ['fp-ref']);
  reference.scene = undefined;
  h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
  assert.equal(generic.active, true, 'the retained compound remains available while the landmark is not drawable');
  h.m.destroy();
});

test('original Flight landmarks win over later generic and lazy catalog copies', () => {
  const h = cityHarness(), [generic, reference] = h.m.entries;
  reference.asset = { ...reference.asset, id: 'lotte', quality: undefined, supersedes: undefined };
  h.m.setFootprintMatches({ lotte: ['tower'], generic: ['tower', 'mall'] });
  generic.catalogTile = 'late-tile'; generic.asset.footprintIds = ['tower', 'mall'];
  h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
  assert.equal(reference.active, true);
  assert.equal(generic.active, false);
  assert.deepEqual(h.m.getState().activeFootprintIds, ['tower']);
  h.m.destroy();
});

test('a landmark culled by the camera does not hide a drawable fallback', () => {
  const h = cityHarness(), [generic, reference] = h.m.entries;
  h.m.renderer.render = scene => { h.m.renderer.info.render.calls = scene === reference.scene ? 0 : 2; };
  h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
  assert.equal(reference.active, false);
  assert.equal(generic.active, true);
  h.m.destroy();
});

test('a failed reference fetch loads the unloaded preserved replacement and restores its footprint', async () => {
  const h = cityHarness(), originalFetch = globalThis.fetch, requested = [];
  h.m.entries.forEach(entry => { entry.scene = undefined; });
  h.m.entries[1].asset = { ...h.m.entries[1].asset, model: 'unavailable.glb' };
  h.m.setFootprintMatches({ generic: ['preserved-solid'] });
  globalThis.fetch = async url => {
    requested.push(url);
    return url.endsWith('/unavailable.glb') ? new Response('', { status: 404 })
      : new Response(readFileSync(new URL('../public/models/lotte.glb', import.meta.url)));
  };
  try {
    await h.m.loadNearby();
    h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
    assert.deepEqual(requested, ['/models/unavailable.glb', '/models/lotte.glb']);
    assert.deepEqual(h.m.getState().activeFootprintIds, ['preserved-solid']);
    assert.equal(h.m.getState().models.find(m => m.id === 'generic').active, true);
  } finally { globalThis.fetch = originalFetch; h.m.destroy(); }
});

test('a failed landmark retains its unloaded generic fallback among more than 32 nearby landmarks', async () => {
  const h = cityHarness(), [generic, reference] = h.m.entries, originalFetch = globalThis.fetch, requested = [];
  generic.scene = undefined;
  generic.asset = { ...generic.asset, coordinate: { lon: 127.13, lat: 37.5 }, geoBounds: [127.0999, 37.4999, 127.1001, 37.5001] };
  reference.scene = undefined; reference.asset = { ...reference.asset, model: 'unavailable.glb' };
  const peers = Array.from({ length: 40 }, (_, i) => ({ ...reference, scene: new THREE.Scene(),
    asset: { ...reference.asset, id: `nearby-${i}`, model: 'lotte.glb', coordinate: { lon: 127.1002 + i * .00002, lat: 37.5 }, supersedes: [`fallback-${i}`], footprintIds: [`peer-${i}`] } }));
  const retainedPeers = peers.map((peer, i) => ({ ...generic, scene: new THREE.Scene(),
    asset: { ...generic.asset, id: `fallback-${i}`, coordinate: peer.asset.coordinate, geoBounds: undefined } }));
  h.m.entries = [generic, reference, ...peers, ...retainedPeers];
  h.m.setFootprintMatches({ generic: ['preserved-solid'] });
  assert.ok(!h.m.nearbyCandidates().includes(generic), 'remote shared anchor initially puts this fallback beyond the resident reserve');
  globalThis.fetch = async url => {
    requested.push(url);
    return url.endsWith('/unavailable.glb') ? new Response('', { status: 404 })
      : new Response(readFileSync(new URL('../public/models/lotte.glb', import.meta.url)));
  };
  try {
    await h.m.loadNearby();
    h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
    assert.deepEqual(requested, ['/models/unavailable.glb', '/models/lotte.glb']);
    assert.equal(reference.error, 'HTTP 404');
    assert.equal(generic.active, true);
    assert.ok(h.m.getState().activeFootprintIds.includes('preserved-solid'));
    assert.equal(h.m.nearbyEntries().length, 32);
    assert.ok(h.m.nearbyCandidates().length <= 48);
    assert.equal(h.m.getState().models.filter(m => m.active).length, 32);
  } finally { globalThis.fetch = originalFetch; h.m.destroy(); }
});

test('a shared compound fallback remains drawable after one sibling fails in a dense landmark view', () => {
  const h = cityHarness(), [generic, reference] = h.m.entries;
  const sibling = { ...reference, asset: { ...reference.asset, id: 'failed-sibling', footprintIds: ['sibling-solid'] }, scene: undefined, error: 'HTTP 404' };
  const peers = Array.from({ length: 40 }, (_, i) => ({ ...reference, scene: new THREE.Scene(),
    asset: { ...reference.asset, id: `peer-${i}`, coordinate: { lon: 127.1002 + i * .00002, lat: 37.5 }, supersedes: [], footprintIds: [`peer-solid-${i}`] } }));
  h.m.entries = [generic, reference, sibling, ...peers];
  h.m.setFootprintMatches({ generic: ['fp-ref', 'sibling-solid'] });
  h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
  assert.equal(reference.active, false, 'ready sibling must not overlap the retained compound');
  assert.equal(generic.active, true);
  assert.ok(h.m.getState().activeFootprintIds.includes('sibling-solid'));
  assert.ok(h.m.nearbyCandidates().length <= 48);
  assert.equal(h.m.getState().models.filter(m => m.active).length, 32);
  h.m.destroy();
});

test('an authored split tower keeps the unmodeled compound remainder selectable in a dense view', async () => {
  const h = cityHarness(), [remainder, reference] = h.m.entries, originalFetch = globalThis.fetch, requested = [];
  remainder.scene = undefined;
  remainder.asset = { ...remainder.asset, genericCorrection: { sourceId: 'generic' },
    coordinate: { lon: 127.13, lat: 37.5 }, geoBounds: [127.0999, 37.4999, 127.1001, 37.5001] };
  reference.asset = { ...reference.asset, supersedes: ['split-fallback'] };
  const split = { ...remainder, scene: new THREE.Scene(), asset: { ...remainder.asset, id: 'split-fallback', coordinate: reference.asset.coordinate } };
  const peers = Array.from({ length: 40 }, (_, i) => ({ ...reference, scene: new THREE.Scene(),
    asset: { ...reference.asset, id: `peer-${i}`, coordinate: { lon: 127.1002 + i * .00002, lat: 37.5 }, supersedes: [], footprintIds: [`peer-solid-${i}`] } }));
  h.m.entries = [remainder, split, reference, ...peers];
  h.m.setFootprintMatches({ generic: ['preserved-neighbor'], 'split-fallback': ['fp-ref'] });
  globalThis.fetch = async url => { requested.push(url); return new Response(readFileSync(new URL('../public/models/lotte.glb', import.meta.url))); };
  try {
    await h.m.loadNearby();
    h.m.render({ defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } });
    assert.deepEqual(requested, ['/models/lotte.glb']);
    assert.equal(reference.active, true);assert.equal(split.active, false);assert.equal(remainder.active, true);
    assert.ok(h.m.getState().activeFootprintIds.includes('preserved-neighbor'));
    assert.equal(remainder.asset.quality, undefined, 'selection priority does not award authored-model status');
    assert.equal(h.m.nearbyEntries().length, 32);assert.ok(h.m.nearbyCandidates().length <= 48);
    assert.equal(h.m.getState().models.filter(m => m.active).length, 32);
  } finally { globalThis.fetch = originalFetch; h.m.destroy(); }
});

test('a rebuilt reference replaces an older authored model only after a successful draw', () => {
  const h = cityHarness(), old = h.m.entries[1];
  const upgrade = { ...old, asset: { ...old.asset, id: 'rebuilt', supersedes: ['ref'], coordinate: { lon: 127.101, lat: 37.5 } }, scene: undefined, active: false };
  h.m.entries.push(upgrade);
  const args = { defaultProjectionData: { mainMatrix: new THREE.Matrix4().elements }, shaderData: { variantName: 'mercator' } };
  h.m.render(args);
  assert.equal(old.active, true, 'previous authored model survives pending rebuild');
  upgrade.scene = new THREE.Scene();
  h.m.render(args);
  assert.equal(upgrade.active, true);
  assert.equal(old.active, false, 'nearer previous reference cannot cover its rebuilt replacement');
  assert.equal(h.m.entries[0].active, false, 'generic source duplicate remains suppressed');
  h.m.renderer.render = scene => { h.m.renderer.info.render.calls = scene === upgrade.scene ? 0 : 2; };
  h.m.render(args);
  assert.equal(upgrade.active, false);
  assert.equal(old.active, true, 'frustum-culled rebuild restores previous reference');
  upgrade.error = '404'; h.m.nearbyCache = undefined;
  h.m.render(args);
  assert.equal(old.active, true, 'failed rebuild restores previous reference');
  h.m.destroy();
});

test('a split tower replacement waits for every visible peer and retains the compound on partial failure', () => {
  const h = cityHarness(), old = h.m.entries[1];
  const tower = suffix => ({ asset: asset('rebuilt-' + suffix, {coordinate: old.asset.coordinate, supersedes: ['ref']}), scene: new THREE.Scene(), error: null, ground: null, draws: 0, active: false });
  const a = tower('a'), b = tower('b'); b.scene = undefined;
  h.m.entries = [...h.m.entries, a, b];
  const frame = {defaultProjectionData: {mainMatrix: new THREE.Matrix4().elements}, shaderData: {variantName: 'mercator'}};
  h.m.render(frame); assert.equal(old.active, true); assert.equal(a.active, false);
  b.error = '404'; h.m.render(frame); assert.equal(old.active, true); assert.equal(a.active, false);
  b.error = null; b.scene = new THREE.Scene(); h.m.nearbyCache = undefined;
  h.m.render(frame); assert.equal(old.active, false); assert.equal(a.active, true); assert.equal(b.active, true);
  h.m.destroy();
});

test('splitting a generic apartment compound also waits for pending or failed sibling towers', () => {
  for (const state of ['pending', '404', 'ready']) {
    const h = cityHarness(), old = h.m.entries[0];
    const tower = suffix => ({ asset: asset('rebuilt-' + suffix, {coordinate: old.asset.coordinate,
      footprintIds: ['tower-' + suffix], supersedes: ['generic']}), scene: new THREE.Scene(),
      error: null, ground: null, draws: 0, active: false });
    const a = tower('a'), b = tower('b');
    if (state !== 'ready') b.scene = undefined;
    if (state === '404') b.error = 'HTTP 404';
    h.m.entries = [old, a, b];
    h.m.setFootprintMatches({generic: ['tower-a', 'tower-b']});
    h.m.render({defaultProjectionData: {mainMatrix: new THREE.Matrix4().elements}, shaderData: {variantName: 'mercator'}});
    assert.equal(old.active, state !== 'ready', state);
    assert.equal(a.active, state === 'ready', state);
    assert.equal(b.active, state === 'ready', state);
    assert.deepEqual(new Set(h.m.getState().activeFootprintIds), new Set(['tower-a', 'tower-b']), state);
    h.m.destroy();
  }
});

test('reference and upgraded tower generations sharing a generic fallback never wait on each other', () => {
  for (const failed of ['none', 'old-reference', 'new-b', 'both-generations']) {
    const h = cityHarness(), [generic, old] = h.m.entries;
    const tower = suffix => ({asset: asset('rebuilt-' + suffix, {coordinate: old.asset.coordinate,
      footprintIds: ['tower-' + suffix], supersedes: ['ref', 'generic']}), scene: new THREE.Scene(),
      error: null, ground: null, draws: 0, active: false});
    const a = tower('a'), b = tower('b');
    if (failed === 'old-reference' || failed === 'both-generations') { old.scene = undefined; old.error = 'HTTP 404'; }
    if (failed === 'new-b' || failed === 'both-generations') { b.scene = undefined; b.error = 'HTTP 404'; }
    h.m.entries = [generic, old, a, b];
    h.m.render({defaultProjectionData: {mainMatrix: new THREE.Matrix4().elements}, shaderData: {variantName: 'mercator'}});
    const newReady = failed === 'none' || failed === 'old-reference';
    assert.equal(a.active, newReady, failed); assert.equal(b.active, newReady, failed);
    assert.equal(old.active, failed === 'new-b', failed);
    assert.equal(generic.active, failed === 'both-generations', failed);
    h.m.destroy();
  }
});
