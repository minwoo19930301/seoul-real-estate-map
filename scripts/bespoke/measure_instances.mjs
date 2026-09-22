import fs from 'node:fs';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { applyModelInstance } from '../../src/shared-models.ts';

const [input, output] = process.argv.slice(2);
const batch = JSON.parse(fs.readFileSync(input, 'utf8'));
const bytes = fs.readFileSync(batch.model);
if (crypto.createHash('sha256').update(bytes).digest('hex') !== batch.sha256) throw Error('Source GLB changed');
const { scene } = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
const dimensions = new THREE.Box3().setFromObject(scene, true).getSize(new THREE.Vector3()).toArray();
const result = batch.instances.map(({ id, modelInstance }) => {
  if (dimensions.some((v, i) => Math.abs(v - modelInstance.sourceDimensions[i]) > .001)) throw Error('Source dimensions changed');
  const clone = scene.clone(true);
  applyModelInstance(clone, modelInstance);
  const box = new THREE.Box3().setFromObject(clone, true);
  if (Math.abs(box.min.y) > .01) throw Error('Instance ground is not zero');
  return { id, dimensions: box.getSize(new THREE.Vector3()).toArray(), min: box.min.toArray(), max: box.max.toArray() };
});
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
