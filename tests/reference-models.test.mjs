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
  assert.throws(() => referenceManifest({ version: 1, assets: [asset('ref-a', { supersedes: ['ref-b'] }), asset('ref-b')], places: [place] }, preserved));
});

test('reference entries carry visible footprint replacement metadata', () => {
  const value = referenceManifest({ version: 1, assets: [asset('ref-a', { footprintIds: ['solid-1', 'solid-2'], supersedes: ['generic-1'] })], places: [place] }, preserved);
  assert.deepEqual(value.assets[0].footprintIds, ['solid-1', 'solid-2']);
  assert.deepEqual(value.assets[0].supersedes, ['generic-1']);
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
