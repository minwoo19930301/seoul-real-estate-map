import test from 'node:test';
import assert from 'node:assert/strict';
import { representativeManifest } from '../src/reference-models.ts';
const asset = { id:'representative-a',model:'representative/site/a.glb',sha256:'a'.repeat(64),quality:'reference',nameKo:'A',dimensions:[10,20,10],coordinate:{lon:127,lat:37.5},yawDegFromEast:0,footprintIds:['a'],supersedes:[],sourceRecord:{method:'representative-photo-informed',completionCredit:false} };
const manifest = assets => ({version:1,assets,places:[]});
test('representative catalog keeps explicit provenance and rejects authored ownership or supersession', () => {
  assert.equal(representativeManifest(manifest([asset]),[],[]).assets.length,1);
  assert.throws(()=>representativeManifest(manifest([asset]),[],[{id:'bespoke',footprintIds:['a']}]));
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
