import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { SharedModelPool, applyModelInstance, validModelInstance } from '../src/shared-models.ts';
import { referenceManifest } from '../src/reference-models.ts';

function template() {
  const model = new THREE.Group();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 30, 20), new THREE.MeshStandardMaterial());
  mesh.geometry.translate(0, 15, 0); mesh.name = 'representative-number'; model.add(mesh);
  return model;
}
const instance = (matrix = new THREE.Matrix4().makeScale(2, 3, 4).elements) => ({
  sourceAssetId: 'representative', sourceDimensions: [10, 30, 20], matrix, hiddenNodes: ['representative-number'],
});

test('concurrent buildings fetch/parse once and share geometry without sharing transforms or labels', async () => {
  const source = template(), pool = new SharedModelPool(); let loads = 0, disposed = 0;
  source.children[0].geometry.addEventListener('dispose', () => disposed++);
  const load = async () => { loads++; return source; };
  const [a, b] = await Promise.all([pool.acquire('url:hash', load), pool.acquire('url:hash', load)]);
  assert.equal(loads, 1); assert.notEqual(a.model, b.model);
  assert.equal(a.model.children[0].geometry, b.model.children[0].geometry);
  assert.equal(a.model.children[0].material, b.model.children[0].material);
  applyModelInstance(a.model, instance());
  assert.equal(a.model.children[0].visible, false); assert.equal(b.model.children[0].visible, true);
  assert.equal(source.children[0].visible, true);
  assert.deepEqual(new THREE.Box3().setFromObject(a.model, true).getSize(new THREE.Vector3()).toArray(), [20, 90, 80]);
  assert.deepEqual(new THREE.Box3().setFromObject(b.model, true).getSize(new THREE.Vector3()).toArray(), [10, 30, 20]);
  a.release(); a.release(); assert.equal(disposed, 0);
  b.release(); assert.equal(disposed, 1); pool.dispose(); assert.equal(disposed, 1);
});

test('failed shared requests can retry without retaining a broken promise', async () => {
  const pool = new SharedModelPool(); let calls = 0;
  const load = async () => { calls++; if (calls === 1) throw Error('network'); return template(); };
  const failed = await Promise.allSettled([pool.acquire('a', load), pool.acquire('a', load)]);
  assert.equal(calls, 1); assert.ok(failed.every(r => r.status === 'rejected'));
  const good = await pool.acquire('a', load); assert.equal(calls, 2); good.release(); pool.dispose();
});

test('disposing during a pending load releases its geometry when it arrives', async () => {
  const pool = new SharedModelPool(), model = template(); let resolve, disposed = 0;
  model.children[0].geometry.addEventListener('dispose', () => disposed++);
  const pending = pool.acquire('a', () => new Promise(r => { resolve = r; }));
  await Promise.resolve(); pool.dispose(); resolve(model);
  await assert.rejects(pending, /closed/); assert.equal(disposed, 1);
  await assert.rejects(pool.acquire('new', async () => template()), /closed/);
});

test('clone transforms reject tilt, perspective, reflection, zero height and nonfinite values', () => {
  assert.equal(validModelInstance(instance()), true);
  for (const [index, value] of [[1,.1],[7,.1],[13,1],[15,2],[5,0],[0,-2],[10,Infinity]]) {
    const bad = instance(); bad.matrix[index] = value;
    assert.equal(validModelInstance(bad), false, `${index}:${value}`);
  }
  const missing = instance(); missing.hiddenNodes = ['missing'];
  assert.throws(() => applyModelInstance(template(), missing), /missing/);
});

test('manifest instances must link the same file, checksum and dimensions as their representative', () => {
  const source = {id:'representative', nameKo:'대표', model:'rep.glb', quality:'reference', sha256:'a'.repeat(64),
    coordinate:{lon:127,lat:37.5}, dimensions:[10,30,20], yawDegFromEast:0, footprintIds:['source'],supersedes:[]};
  const clone = {...source,id:'clone',nameKo:'복제', dimensions:[20,90,80],footprintIds:['clone'],modelInstance:instance()};
  const manifest = assets => ({version:1,assets,places:[]});
  assert.equal(referenceManifest(manifest([source,clone]),[]).assets.length,2);
  for (const change of [{model:'other.glb'},{sha256:'b'.repeat(64)},{yawDegFromEast:10},
    {modelInstance:{...instance(),sourceAssetId:'absent'}},
    {modelInstance:{...instance(),sourceDimensions:[10,31,20]}}]) {
    assert.throws(() => referenceManifest(manifest([source,{...clone,...change}]),[]),/대표 원본/);
  }
});
