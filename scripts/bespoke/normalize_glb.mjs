// Bake the exact Blender scene transforms into metres for the map renderer.
// This only changes export encoding, never the authored building geometry.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
const [source, destination] = process.argv.slice(2);
if (!source || !destination) throw Error('Usage: node normalize_glb.mjs source.glb destination.glb');
globalThis.FileReader ??= class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.({ target: this }); }); }
};
const bytes = fs.readFileSync(source);
const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
gltf.scene.updateMatrixWorld(true);
const baked = new THREE.Group(), bounds = new THREE.Box3(), point = new THREE.Vector3();
let triangles = 0;
const components = [];
gltf.scene.traverse(object => {
  if (!object.isMesh) return;
  if (object.isSkinnedMesh || object.isInstancedMesh) throw Error('Architectural export must use ordinary meshes');
  const geometry = object.geometry.clone().applyMatrix4(object.matrixWorld);
  const positions = geometry.getAttribute('position'), normals = geometry.getAttribute('normal');
  if (!normals) throw Error('Missing surface normals: ' + object.name);
  const count = (geometry.index?.count ?? positions.count) / 3;
  if (!Number.isInteger(count)) throw Error('Incomplete triangles: ' + object.name);
  for (let i = 0; i < positions.count; i++) {
    point.fromBufferAttribute(positions, i);
    if (![point.x, point.y, point.z].every(Number.isFinite)) throw Error('Nonfinite geometry: ' + object.name);
    bounds.expandByPoint(point);
    const length = Math.hypot(normals.getX(i), normals.getY(i), normals.getZ(i));
    if (!Number.isFinite(length) || Math.abs(length - 1) > .01) throw Error('Invalid normals: ' + object.name);
  }
  const materials = Array.isArray(object.material) ? object.material : [object.material];
  for (const material of materials) for (const value of Object.values(material)) {
    if (value?.isTexture) throw Error('Review embedded image rights before enabling textured exports');
  }
  const mesh = new THREE.Mesh(geometry, object.material);
  mesh.name = object.name; baked.add(mesh); triangles += count;
  components.push({ name: object.name, triangles: count });
});
if (!components.length || Math.abs(bounds.min.y) > .01) throw Error('Empty scene or ground is not zero: ' + bounds.min.y);
const result = await new GLTFExporter().parseAsync(baked, { binary: true, onlyVisible: true, includeCustomExtensions: false });
fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.writeFileSync(destination, Buffer.from(result));
const output = { sourceSha256: crypto.createHash('sha256').update(bytes).digest('hex'),
  sha256: crypto.createHash('sha256').update(Buffer.from(result)).digest('hex'), bytes: result.byteLength,
  dimensions: bounds.getSize(new THREE.Vector3()).toArray(), min: bounds.min.toArray(), max: bounds.max.toArray(), triangles, components };
fs.writeFileSync(destination + '.json', JSON.stringify(output, null, 2) + '\n');
console.log(JSON.stringify({ output: destination, bytes: output.bytes, triangles, components: components.length, dimensions: output.dimensions }));
