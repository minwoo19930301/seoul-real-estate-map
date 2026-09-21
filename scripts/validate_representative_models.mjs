import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { representativeManifest } from '../src/reference-models.ts';

const read = path => JSON.parse(fs.readFileSync(path));
const hashes = new Map();
const hash = path => {
  if (!hashes.has(path)) hashes.set(path, crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex'));
  return hashes.get(path);
};
const bespoke = read('public/models/bespoke-manifest.json').assets;
const references = read('public/models/reference-manifest.json').assets;
const generic = read('public/models/manifest.json').assets;
const manifest = representativeManifest(read('public/models/representative-manifest.json'),
  [...generic, ...references, ...bespoke], [...references, ...bespoke]);
const deployment = read('public/data/deployment-assets.json').files;
assert.equal(hash('public/models/representative-manifest.json'), deployment['public/models/representative-manifest.json']);
let bytes = 0;
for (const asset of manifest.assets) {
  const path = 'public/models/' + asset.model;
  assert.equal(hash(path), asset.sha256, asset.id + ' runtime hash');
  assert.equal(deployment[path], asset.sha256, asset.id + ' deployment hash');
  assert.equal(hash(asset.sourceRecord.blendSource), asset.sourceRecord.blendSha256);
  const raw = fs.readFileSync(path);
  bytes += raw.length;
  const { scene } = await new GLTFLoader().parseAsync(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength), '');
  const box = new THREE.Box3().setFromObject(scene);
  assert.ok(Math.abs(box.min.y) < .01, asset.id + ' ground datum');
  box.getSize(new THREE.Vector3()).toArray().forEach((v, i) =>
    assert.ok(Math.abs(v - asset.dimensions[i]) < .01, asset.id + ' dimensions'));
  const sx = 111319.49079327358 * Math.cos(asset.coordinate.lat * Math.PI / 180);
  const sy = 111319.49079327358;
  [asset.coordinate.lon + box.min.x/sx, asset.coordinate.lat - box.max.z/sy,
    asset.coordinate.lon + box.max.x/sx, asset.coordinate.lat - box.min.z/sy]
    .forEach((v, i) => assert.ok(Math.abs(v-asset.geoBounds[i]) < 1e-8, asset.id + ' geographic bounds'));
  let primitives = 0;
  scene.traverse(object => {
    if (!object.isMesh) return;
    primitives++;
    assert.ok(object.matrixWorld.equals(new THREE.Matrix4()), asset.id + ' baked transform');
    for (const coordinate of object.geometry.attributes.position.array) assert.ok(Number.isFinite(coordinate));
    object.geometry.dispose();
    for (const material of [object.material].flat()) material.dispose();
  });
  assert.ok(primitives > 0 && primitives <= 8, asset.id + ' draw primitive budget');
}
console.log(JSON.stringify({ assets: manifest.assets.length,
  sourceFootprints: manifest.assets.flatMap(asset => asset.footprintIds).length, bytes, checks: 'passed' }));
