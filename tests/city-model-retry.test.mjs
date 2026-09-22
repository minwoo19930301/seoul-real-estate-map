import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { CityModels } from '../src/city-models.ts';

// A real tiny GLB exercises the runtime fetch/hash/parse path, not a mocked pool.
const bin = Buffer.from(new Float32Array([0,0,0, 1,0,0, 0,2,1]).buffer);
const document = { asset:{version:'2.0'}, scene:0, scenes:[{nodes:[0]}], nodes:[{mesh:0}],
  meshes:[{primitives:[{attributes:{POSITION:0}}]}], buffers:[{byteLength:bin.length}],
  bufferViews:[{buffer:0,byteLength:bin.length}],
  accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[0,0,0],max:[1,2,1]}] };
const text = JSON.stringify(document), json = Buffer.from(text.padEnd(Math.ceil(text.length / 4) * 4, ' '));
const bytes = Buffer.alloc(12 + 8 + json.length + 8 + bin.length);
bytes.writeUInt32LE(0x46546c67,0); bytes.writeUInt32LE(2,4); bytes.writeUInt32LE(bytes.length,8);
bytes.writeUInt32LE(json.length,12); bytes.writeUInt32LE(0x4e4f534a,16); json.copy(bytes,20);
bytes.writeUInt32LE(bin.length,20+json.length); bytes.writeUInt32LE(0x004e4942,24+json.length); bin.copy(bytes,28+json.length);
const sha256 = createHash('sha256').update(bytes).digest('hex');
const response = () => new Response(bytes);
const args = { defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements}, shaderData:{variantName:'mercator'} };
function harness(t) {
  let now = 0;
  t.mock.method(performance, 'now', () => now);
  t.mock.timers.enable({apis:['setTimeout']});
  const map = { getZoom:()=>18, getCenter:()=>({lng:127,lat:37.5}),
    getBounds:()=>({getWest:()=>126.99,getEast:()=>127.01,getSouth:()=>37.49,getNorth:()=>37.51}),
    getTerrain:()=>({source:'local-terrain'}),getSource:()=>({}),isSourceLoaded:()=>true,
    queryTerrainElevation:()=>0,triggerRepaint(){},off(){},getLayer:()=>null };
  const models = new CityModels(map);
  const asset = {id:'representative',nameKo:'대표',model:'test.glb',sha256,dimensions:[1,2,1],
    coordinate:{lon:127,lat:37.5},yawDegFromEast:0,quality:'reference',footprintIds:['footprint'],supersedes:['fallback']};
  const entry = {asset,error:null,ground:null,draws:0,active:false};
  const fallback = {asset:{...asset,id:'fallback',quality:undefined,supersedes:[]},scene:new THREE.Scene(),error:null,ground:null,draws:0,active:false};
  models.entries=[entry,fallback]; models.legacyEntries=models.entries; models.is25d=true;
  models.renderer={resetState(){},render(){},dispose(){},info:{render:{calls:1}}};
  t.after(()=>models.destroy());
  return {models,entry,fallback,async tick(ms){now+=ms;t.mock.timers.tick(ms);await models.loadNearby();}};
}

test('CityModels retries transient fetch after backoff; fallback owns the place until successful draw', async t => {
  const h=harness(t); let calls=0,finish;
  t.mock.method(globalThis,'fetch',async()=>{calls++;if(calls===1)throw new TypeError('network disconnected');return new Promise(r=>{finish=r;});});
  await h.models.loadNearby(); assert.equal(calls,1); assert.ok(h.entry.error);
  h.models.render(args); assert.equal(h.fallback.active,true); assert.deepEqual(h.models.getState().activeFootprintIds,[]);
  await h.tick(999); assert.equal(calls,1);
  const pending=h.tick(1); await Promise.resolve(); await Promise.resolve();
  h.models.render(args); assert.equal(h.fallback.active,true); assert.equal(h.entry.active,false);
  // Let the real parser complete; the replacement must suppress fallback only when drawn.
  while(!finish)await Promise.resolve(); finish(response()); await pending;
  assert.equal(calls,2); assert.equal(h.entry.error,null); assert.ok(h.entry.scene);
  h.models.render(args); assert.equal(h.entry.active,true); assert.equal(h.fallback.active,false);
  assert.deepEqual(h.models.getState().activeFootprintIds,['footprint']);
});

test('CityModels network retry budget is two retries with increasing backoff', async t => {
  const h=harness(t);let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;return new Response('',{status:503});});
  await h.models.loadNearby();await h.tick(1000);assert.equal(calls,2);
  await h.tick(1999);assert.equal(calls,2);await h.tick(1);assert.equal(calls,3);
  await h.tick(60000);h.models.render(args);assert.equal(calls,3);assert.equal(h.fallback.active,true);
});

for (const kind of ['checksum','dimensions','manifest','parse','404']) test(`CityModels never retries permanent ${kind} failure`,async t=>{
  const h=harness(t);let calls=0;
  if(kind==='checksum')h.entry.asset.sha256='0'.repeat(64);
  if(kind==='dimensions')h.entry.asset.dimensions=[1,3,1];
  if(kind==='manifest')h.entry.asset.model='../invalid.glb';
  const invalid=Buffer.from('invalid glb');
  if(kind==='parse')h.entry.asset.sha256=createHash('sha256').update(invalid).digest('hex');
  t.mock.method(globalThis,'fetch',async()=>{calls++;return kind==='404'?new Response('',{status:404}):kind==='parse'?new Response(invalid):response();});
  await h.models.loadNearby();assert.ok(h.entry.error);const first=calls;
  await h.tick(60000);h.models.render(args);assert.equal(calls,first);assert.equal(h.entry.retryAt,undefined);assert.equal(h.fallback.active,true);
});

test('destroy cancels scheduled CityModels retry and later frames cannot restart it',async t=>{
  const h=harness(t);let calls=0;
  t.mock.method(globalThis,'fetch',async()=>{calls++;throw new TypeError('offline');});
  await h.models.loadNearby();assert.equal(calls,1);h.models.destroy();
  await h.tick(60000);h.models.render(args);assert.equal(calls,1);assert.equal(h.models.modelRetryTimer,undefined);
});
