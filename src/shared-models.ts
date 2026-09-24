import * as THREE from 'three';

export interface ModelInstance {
  sourceAssetId: string;
  sourceDimensions: [number, number, number];
  matrix: number[];
  hiddenNodes: string[];
}

export function validModelInstance(value: ModelInstance | undefined): boolean {
  if (value === undefined) return true;
  if (!value || !/^[a-z0-9_-]+$/.test(value.sourceAssetId)
    || !Array.isArray(value.sourceDimensions) || value.sourceDimensions.length !== 3
    || !value.sourceDimensions.every(n => Number.isFinite(n) && n > 0)
    || !Array.isArray(value.matrix) || value.matrix.length !== 16
    || !value.matrix.every(n => Number.isFinite(n) && Math.abs(n) < 1e6)
    || !Array.isArray(value.hiddenNodes) || value.hiddenNodes.length > 20
    || value.hiddenNodes.some(n => typeof n !== 'string' || !n || n.length > 200)
    || new Set(value.hiddenNodes).size !== value.hiddenNodes.length) return false;
  const m = value.matrix;
  return [1, 3, 4, 6, 7, 9, 11, 13].every(i => m[i] === 0)
    && m[15] === 1 && m[5] > 0 && m[0] * m[10] - m[8] * m[2] > 1e-8;
}

export function applyModelInstance(model: THREE.Object3D, instance?: ModelInstance) {
  if (!instance) return;
  if (!validModelInstance(instance)) throw Error('Invalid representative model transform');
  for (const name of instance.hiddenNodes) {
    const node = model.getObjectByName(name);
    if (!node || !(node as THREE.Mesh).isMesh) throw Error('Representative label mesh is missing: ' + name);
    node.visible = false;
  }
  model.matrixAutoUpdate = false;
  model.matrix.fromArray(instance.matrix);
  model.updateMatrixWorld(true);
}

export function disposeModel(model: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>();
  model.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    geometries.add(mesh.geometry);
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) materials.add(material);
  });
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
}

type Shared = { promise: Promise<THREE.Object3D>; model?: THREE.Object3D; references: number };

export class SharedModelPool {
  private entries = new Map<string, Shared>();
  private closed = false;

  async acquire(key: string, load: () => Promise<THREE.Object3D>) {
    if (this.closed) throw Error('Model pool is closed');
    let entry = this.entries.get(key);
    if (!entry) {
      entry = { references: 0, promise: Promise.resolve().then(load) };
      const created = entry;
      entry.promise = entry.promise.then(model => { created.model = model; return model; });
      this.entries.set(key, entry);
    }
    const shared = entry;
    shared.references++;
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      if (--shared.references === 0) {
        if (this.entries.get(key) === shared) this.entries.delete(key);
        if (shared.model) disposeModel(shared.model);
      }
    };
    try {
      const template = await shared.promise;
      if (this.closed) throw Error('Model pool is closed');
      return { model: template.clone(true), release };
    } catch (error) { release(); throw error; }
  }

  dispose() { this.closed = true; }
}
