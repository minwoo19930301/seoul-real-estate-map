import test from 'node:test';
import assert from 'node:assert/strict';
import { representativeManifest } from '../src/reference-models.ts';
const asset = { id:'representative-a',model:'representative/site/a.glb',sha256:'a'.repeat(64),quality:'reference',nameKo:'A',dimensions:[10,20,10],coordinate:{lon:127,lat:37.5},yawDegFromEast:0,footprintIds:['a'],supersedes:[],sourceRecord:{method:'representative-photo-informed',completionCredit:false} };
const manifest = assets => ({version:1,assets,places:[]});
test('representative catalog preserves authored ownership and rejects invalid provenance or supersession', () => {
  assert.equal(representativeManifest(manifest([asset]),[],[]).assets.length,1);
  assert.equal(representativeManifest(manifest([asset]),[],[{id:'bespoke',footprintIds:['a']}]).assets.length,0);
  assert.throws(()=>representativeManifest(manifest([asset,{...asset,id:'representative-b'}]),[],[]));
  assert.throws(()=>representativeManifest(manifest([{...asset,supersedes:['bespoke']}]),[],[]));
  assert.throws(()=>representativeManifest(manifest([{...asset,sourceRecord:{...asset.sourceRecord,completionCredit:true}}]),[],[]));
});
import { CityModels } from '../src/city-models.ts';
import * as THREE from 'three';
test('representative ownership activates only after drawing and restores generic on failed load', async () => {
  const map = {getZoom:()=>16,getCenter:()=>({lng:127,lat:37.5}),getBounds:()=>({getWest:()=>126.998,getEast:()=>127.002,getSouth:()=>37.498,getNorth:()=>37.502}),getTerrain:()=>({source:'local',exaggeration:1}),getSource:()=>({}),isSourceLoaded:()=>true,queryTerrainElevation:()=>0,triggerRepaint(){},off(){},getLayer:()=>null};
  const models = new CityModels(map);
  const generic = {...asset,id:'generic',quality:undefined,model:'generic.glb',footprintIds:['a','unrelated']};
  models.entries = [{asset:generic,scene:new THREE.Scene(),error:null,ground:null,draws:0,active:false}, {asset,scene:undefined,error:null,ground:null,draws:0,active:false}];
  models.renderer = {resetState(){},render(){},dispose(){},info:{render:{calls:2}}};
  models.setFootprintMatches({generic:['a','unrelated']}); models.setMode(true);
  const args = {defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}};
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async()=>{throw Error('missing representative GLB')};
  try {
    await models.loadNearby(); models.render(args);
    assert.equal(models.entries[0].active,true);
    assert.deepEqual(models.getState().activeFootprintIds,['a','unrelated']);
    models.entries[1].scene = new THREE.Scene(); models.entries[1].error = null; models.entries = [...models.entries];
    models.render(args);
    assert.equal(models.entries[1].active,true);
    assert.equal(models.entries[0].active,false);
    assert.deepEqual(models.getState().activeFootprintIds,['a']);
    models.entries[1].scene = undefined; models.render(args);
    assert.equal(models.entries[0].active,true);
  } finally {globalThis.fetch=originalFetch; models.destroy();}
});

import { readFileSync } from 'node:fs';
test('overlapping compound is omitted as a whole while unrelated representatives and provenance survive', () => {
  const compound = {...asset, footprintIds:['a','unprotected']};
  const unrelated = {...asset,id:'representative-b',footprintIds:['b']};
  const input = manifest([compound,unrelated]);
  const result = representativeManifest(input,[],[{id:'landmark',footprintIds:['a']}]);
  assert.deepEqual(result.assets,[unrelated]);
  assert.deepEqual(result.excludedRepresentatives,[{assetId:compound.id,protectedFootprintIds:['a']}]);
  assert.deepEqual(input.assets,[compound,unrelated]);
  assert.equal(result.assets[0].sourceRecord.completionCredit,false);
  assert.throws(()=>representativeManifest(manifest([{...compound,sourceRecord:{method:'invented'}}]),[],[{id:'landmark',footprintIds:['a']}]),/provenance/);
});
test('historical catalog remains usable alongside all published authored models', () => {
  const read = name => JSON.parse(readFileSync(new URL('../public/models/'+name,import.meta.url),'utf8'));
  const historic = read('representative-manifest.json');
  const bespoke = read('bespoke-manifest.json');
  const references = read('reference-manifest.json');
  const protectedModels = [...references.assets,...bespoke.assets];
  const result = representativeManifest(historic,protectedModels,protectedModels);
  const protectedIds = new Set(protectedModels.flatMap(a=>a.footprintIds??[]));
  const expected = historic.assets.filter(a=>!a.footprintIds.some(id=>protectedIds.has(id)));
  assert.deepEqual(result.assets,expected);
  assert.ok(result.assets.length>0);
  assert.ok(result.excludedRepresentatives.length>0);
  assert.equal(result.assets.length+result.excludedRepresentatives.length,historic.assets.length);
  for(const a of result.assets) assert.equal(a.sourceRecord.completionCredit,false);
});
