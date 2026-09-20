#!/usr/bin/env node
// Export a pinned, trusted Seoul Flight revision into an unpublished staging folder.
// Source models often compress horizontal scale; this script does not claim to fix it.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const options = {
  repo: path.resolve(root, '../../2026-09-05/new-chat/work/repos/seoul-flight-game'),
  ref: 'origin/main',
  out: path.join(root, 'data/model-source/flight-current'),
  adaptation: '',
};
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i].replace(/^--/, '');
  if (!(key in options) || !process.argv[i + 1]) throw Error('Unknown/missing option ' + key);
  options[key] = process.argv[i + 1];
}
const out = path.resolve(options.out);
if (fs.existsSync(out)) throw Error('Refusing to overwrite existing staging directory: ' + out);
const git = (...args) => execFileSync('git', ['-C', options.repo, ...args], { maxBuffer: 64 * 1024 * 1024 });
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const revision = git('rev-parse', '--verify', options.ref + '^{commit}').toString().trim();
const checkout = fs.mkdtempSync(path.join(os.tmpdir(), 'seoul-flight-export-'));
const archive = git('archive', revision, 'landmarks', 'vendor', 'scripts/landmark-registry.mjs', 'assets/landmarks');
execFileSync('tar', ['-xf', '-', '-C', checkout], { input: archive });
fs.writeFileSync(path.join(checkout, 'package.json'), '{"type":"module"}\n');
let adapter, placementAudit, pristineReport;
const originalSources = new Map();
if (options.adaptation) {
  placementAudit = JSON.parse(fs.readFileSync(options.adaptation));
  if (placementAudit.sourceRevision !== revision) throw Error('Adaptation source revision mismatch');
  const pristineBytes = fs.readFileSync(path.join(path.dirname(options.adaptation), 'report.json'));
  if (sha(pristineBytes) !== placementAudit.exportReportSha256) throw Error('Pristine export report hash mismatch');
  pristineReport = JSON.parse(pristineBytes);
  adapter = await import('./adapt_flight_landmarks.mjs');
  for (const asset of placementAudit.assets) {
    const filename = path.join(checkout, asset.sourceFile);
    const source = fs.readFileSync(filename, 'utf8');
    if (sha(source) !== asset.sourceFileSha256) throw Error('Adaptation source file mismatch: ' + asset.id);
    originalSources.set(asset.id, source);
    fs.writeFileSync(filename, adapter.instrumentSource(asset.id, source));
  }
}

// Only Blob ArrayBuffer reading is needed: input modules prohibit images/textures.
globalThis.FileReader ??= class {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then(result => {
      this.result = result;
      this.onloadend?.({ target: this });
    }, error => { this.error = error; this.onerror?.(error); });
  }
};

function inspect(group) {
  group.updateMatrixWorld(true);
  const bounds = new THREE.Box3();
  const materials = new Set();
  const point = new THREE.Vector3();
  let meshes = 0, triangles = 0, nonFinite = 0, nonUnitNormals = 0;
  group.traverse(object => {
    if (!object.isMesh) return;
    meshes++;
    const geo = object.geometry;
    const positions = geo.attributes.position, normals = geo.attributes.normal;
    triangles += (geo.index?.count ?? positions.count) / 3;
    for (let i = 0; i < positions.count; i++) {
      point.fromBufferAttribute(positions, i).applyMatrix4(object.matrixWorld);
      if (![point.x, point.y, point.z].every(Number.isFinite)) nonFinite++;
      else bounds.expandByPoint(point);
      if (normals) {
        const length = Math.hypot(normals.getX(i), normals.getY(i), normals.getZ(i));
        if (!Number.isFinite(length) || Math.abs(length - 1) > .002) nonUnitNormals++;
      }
    }
    for (const mat of Array.isArray(object.material) ? object.material : [object.material]) {
      for (const value of Object.values(mat)) if (value?.isTexture) throw Error('Unexpected texture');
      materials.add(mat);
    }
  });
  if (!meshes || nonFinite || !Number.isFinite(triangles)) throw Error('Empty/nonfinite model');
  return { meshes, triangles, materialCount: materials.size, nonUnitNormals,
    bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() },
    dimensions: bounds.getSize(new THREE.Vector3()).toArray() };
}

function flatten(group, offset) {
  group.updateMatrixWorld(true);
  const result = new THREE.Group();
  const repairs = { removedDegenerateTriangles: 0, repairedZeroNormals: 0 };
  group.traverse(object => {
    if (!object.isMesh) return;
    const transformed = (object.geometry.index ? object.geometry.toNonIndexed() : object.geometry.clone()).applyMatrix4(object.matrixWorld);
    transformed.translate(-offset[0], -offset[1], -offset[2]);
    const positions = [], normals = [];
    const p = transformed.attributes.position, n = transformed.attributes.normal;
    for (let i = 0; i < p.count; i += 3) {
      const vertices = [0, 1, 2].map(j => new THREE.Vector3().fromBufferAttribute(p, i + j));
      const face = vertices[1].clone().sub(vertices[0]).cross(vertices[2].clone().sub(vertices[0]));
      if (face.lengthSq() < 1e-16) { repairs.removedDegenerateTriangles++; continue; }
      face.normalize();
      for (let j = 0; j < 3; j++) {
        const normal = new THREE.Vector3().fromBufferAttribute(n, i + j);
        if (normal.lengthSq() < 1e-12) { normal.copy(face); repairs.repairedZeroNormals++; }
        else normal.normalize();
        positions.push(...vertices[j]); normals.push(...normal);
      }
    }
    transformed.dispose();
    if (!positions.length) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
    const mesh = new THREE.Mesh(geometry, object.material);
    mesh.name = object.name;
    result.add(mesh);
  });
  return { group: result, repairs };
}

function inspectGlb(bytes, gltf) {
  if (bytes.readUInt32LE(0) !== 0x46546c67 || bytes.readUInt32LE(8) !== bytes.length) throw Error('Invalid GLB header');
  const binaryStart = 28 + bytes.readUInt32LE(12);
  const read = (accessorIndex, index) => {
    const accessor = gltf.accessors[accessorIndex], view = gltf.bufferViews[accessor.bufferView];
    if (accessor.componentType !== 5126 || accessor.type !== 'VEC3') throw Error('Unexpected geometry encoding');
    const at = binaryStart + (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0) + index * (view.byteStride ?? 12);
    return new THREE.Vector3(bytes.readFloatLE(at), bytes.readFloatLE(at + 4), bytes.readFloatLE(at + 8));
  };
  let vertices = 0, badNormals = 0, degenerateTriangles = 0;
  const bounds = new THREE.Box3();
  for (const mesh of gltf.meshes) for (const primitive of mesh.primitives) {
    if (primitive.indices !== undefined) throw Error('Unexpected indexed output; verifier expects flattened geometry');
    const count = gltf.accessors[primitive.attributes.POSITION].count;
    vertices += count;
    for (let i = 0; i < count; i++) {
      const position = read(primitive.attributes.POSITION, i);
      const normal = read(primitive.attributes.NORMAL, i);
      if (![...position, ...normal].every(Number.isFinite)) throw Error('Nonfinite GLB geometry');
      bounds.expandByPoint(position);
      if (Math.abs(normal.length() - 1) > .002) badNormals++;
    }
    for (let i = 0; i < count; i += 3) {
      const a = read(primitive.attributes.POSITION, i);
      const b = read(primitive.attributes.POSITION, i + 1);
      const c = read(primitive.attributes.POSITION, i + 2);
      if (b.sub(a).cross(c.sub(a)).lengthSq() < 1e-16) degenerateTriangles++;
    }
  }
  if (badNormals || Math.abs(bounds.min.y) > .001) throw Error('Invalid exported normals/ground');
  return { finitePositions: true, unitNormals: true, vertices, triangles: vertices / 3,
    degenerateTriangles, bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() } };
}

const { extraLandmarks } = await import(pathToFileURL(path.join(checkout, 'landmarks/index.mjs')));
const { mergeGroupByMaterial } = await import(pathToFileURL(path.join(checkout, 'landmarks/_helpers.mjs')));
const { LANDMARKS } = await import(pathToFileURL(path.join(checkout, 'scripts/landmark-registry.mjs')));
const registry = new Map(LANDMARKS.map(row => [row.id, row]));
const stage = out + '.tmp-' + process.pid;
fs.mkdirSync(stage, { recursive: true });
const report = {
  version: 1, sourceRepository: 'https://github.com/minwoo19930301/seoul-flight-game', sourceRevision: revision,
  sourceArchiveSha256: sha(archive), helperSha256: sha(fs.readFileSync(path.join(checkout, 'landmarks/_helpers.mjs'))),
  exporterVersion: THREE.REVISION, publishReady: false,
  notice: 'Source-authored illustrative landmark geometry. Horizontal scale, geographic fit and source-photo provenance require review before publication. No generic fallback.',
  assets: [], failures: [], preservedGlbComparisons: [],
};
if (placementAudit) {
  report.adaptation = { placementAuditSha256: sha(fs.readFileSync(options.adaptation)),
    pristineExportReportSha256: placementAudit.exportReportSha256,
    adapterScriptSha256: sha(fs.readFileSync(path.join(root, 'scripts/adapt_flight_landmarks.mjs'))),
    notice: 'Source-author scale estimates applied before material merge; no claim of independent survey or final geographic fit.' };
}
const seen = new Set();
for (const module of extraLandmarks) {
  try {
    if (!/^[a-z0-9-]+$/.test(module.id) || seen.has(module.id)) throw Error('Unsafe/duplicate ID');
    seen.add(module.id);
    const filename = 'landmarks/' + module.id + '.mjs';
    const instrumentedSource = fs.readFileSync(path.join(checkout, filename), 'utf8');
    const source = originalSources.get(module.id) ?? instrumentedSource;
    const original = module.create();
    const sourceStats = inspect(original);
    const pristine = pristineReport?.assets.find(asset => asset.id === module.id);
    const adaptationRecipe = adapter?.adaptGeometry(module.id, original, placementAudit.assets.find(asset => asset.id === module.id));
    const adaptedSourceStats = adaptationRecipe ? inspect(original) : sourceStats;
    const merged = mergeGroupByMaterial(original);
    const { min, max } = adaptedSourceStats.bounds;
    const offset = [(min[0] + max[0]) / 2, min[1], (min[2] + max[2]) / 2];
    const { group: normalized, repairs } = flatten(merged, offset);
    const stats = inspect(normalized);
    const bytes = Buffer.from(await new GLTFExporter().parseAsync(normalized, { binary: true, onlyVisible: false }));
    const jsonLength = bytes.readUInt32LE(12);
    const gltf = JSON.parse(bytes.subarray(20, 20 + jsonLength));
    if (gltf.images?.length || gltf.textures?.length || gltf.buffers.some(b => b.uri)) throw Error('External/texture resources');
    const byteValidation = inspectGlb(bytes, gltf);
    let adaptationIntegrity;
    if (pristine) {
      const pristineBytes = fs.readFileSync(path.join(path.dirname(options.adaptation), pristine.model));
      if (sha(pristineBytes) !== pristine.sha256) throw Error('Pristine GLB hash mismatch');
      const pristineJson = JSON.parse(pristineBytes.subarray(20, 20 + pristineBytes.readUInt32LE(12)));
      const materialsSha256 = sha(JSON.stringify(gltf.materials));
      const pristineMaterialsSha256 = sha(JSON.stringify(pristineJson.materials));
      const removesDecoration = module.id === 'tower-palace' && adaptationRecipe.namedFootprintPlacement
        && adaptationRecipe.removedDecorativeTriangles > 0;
      const retainedMaterialMap = gltf.materials.map((material, index) => {
        const materialSha256 = sha(JSON.stringify(material));
        const pristineIndex = pristineJson.materials.findIndex(value => sha(JSON.stringify(value)) === materialSha256);
        if (pristineIndex < 0) throw Error('Adaptation changed an original PBR material');
        return { adaptedIndex: index, pristineIndex, sha256: materialSha256 };
      });
      if (!removesDecoration && materialsSha256 !== pristineMaterialsSha256) throw Error('Adaptation changed source materials');
      const removedTriangles = removesDecoration ? adaptationRecipe.removedDecorativeTriangles : 0;
      if (stats.triangles + removedTriangles !== pristine.exportedStats.triangles) throw Error('Unaccounted source triangle change');
      adaptationIntegrity = { preservedPbrMaterials: true, preservedTriangleCount: !removesDecoration,
        preservationMode: removesDecoration ? 'complete-seven-towers-with-documented-site-removal' : 'complete-source-model',
        removedTriangles, retainedMaterialMap, materialsSha256, pristineMaterialsSha256,
        ...(removesDecoration ? { pristineMaterialDefinitions: pristineJson.materials } : {}) };
    }
    const entry = registry.get(module.id);
    const model = module.id + '.glb';
    fs.writeFileSync(path.join(stage, model), bytes);
    const comments = source.split('\n').flatMap((text, index) => /^\s*\/\//.test(text) ? [{ line: index + 1, text: text.replace(/^\s*\/\/\s?/, '') }] : []);
    report.assets.push({
      id: module.id, nameKo: module.name, nameEn: module.nameEn, district: module.district,
      model, bytes: bytes.length, sha256: sha(bytes), sourceFile: filename, sourceFileSha256: sha(source),
      sourceUrl: report.sourceRepository + '/blob/' + revision + '/' + filename,
      moduleCoordinate: { lon: module.lon, lat: module.lat },
      flightRuntimeCoordinate: { lon: entry?.lon ?? module.lon, lat: entry?.lat ?? module.lat },
      declaredHeightM: module.height, registryHeightM: entry?.height, detail: module.detail,
      declaredColliderRadiusM: module.colliderRadius, registryColliderRadiusM: entry?.colliderRadius,
      sourceStats, exportedStats: stats,
      ...(adaptationRecipe ? {
        pristineSource: { sourceFileSha256: sha(source), glbSha256: pristine.sha256,
          sourceStats: pristine.sourceStats, exportOffsetFromSource: pristine.exportOffsetFromSource },
        instrumentedSourceSha256: sha(instrumentedSource), adaptationRecipe, adaptedSourceStats,
        adaptationIntegrity,
        originalCenterOffsetM: pristine.exportOffsetFromSource,
        originalCenterOffsetScaledM: adaptationRecipe.kind === 'component-width-and-centre-spacing' ? null : pristine.exportOffsetFromSource.map((v, i) => v * adaptationRecipe.appliedScaleXYZ[i]),
        adaptedCenterOffsetM: offset, exportOffsetFromAdaptedSource: offset,
        sourceGroundOffsetM: offset[1],
        sourceGroundContract: 'Place centred GLB at independently verified source origin plus adaptedCenterOffsetM.xz; terrainY + sourceGroundOffsetM restores authored nominal y=0 grade. Coordinates are not verified by export.',
        geometryReady: true, footprintFitVerified: false,
      } : {}),
      exportedGlb: { meshes: gltf.meshes.length, primitives: gltf.meshes.reduce((n, m) => n + m.primitives.length, 0), materials: gltf.materials.length, images: gltf.images?.length ?? 0 },
      byteValidation,
      geometryRepairs: repairs,
      axisContract: '+X east, +Y up, +Z south; source geographic accuracy unverified',
      rootTransform: 'identity', exportedScale: [1, 1, 1], yawDegFromEast: 0,
      sourceOrigin: 'module origin placed at flightRuntimeCoordinate and one terrain sample',
      exportOffsetFromSource: offset,
      offsetContract: 'exportedVertex = ' + (adaptationRecipe ? 'adaptedSourceWorldVertex' : 'sourceWorldVertex') + ' - exportOffsetFromSource; source ground y=0 becomes exported y=-offset[1]. Horizontal placement must account for offset.',
      sourceAuthorScaleNotes: comments.filter(c => /compress|scale|footprint|1:1|real/.test(c.text)),
      sourceAuthorDescription: comments.slice(0, 18),
      referenceUrls: [...new Set(source.match(/https?:\/\/[^\s"'<>]+/g) ?? [])],
      publishReady: false,
    });
    console.log(module.id + ': ' + stats.triangles + ' triangles, ' + stats.materialCount + ' materials, ' + bytes.length + ' bytes');
    const geometries = new Set();
    for (const group of [original, merged, normalized]) group.traverse(o => { if (o.isMesh) geometries.add(o.geometry); });
    for (const geometry of geometries) geometry.dispose();
  } catch (error) {
    report.failures.push({ id: module.id, error: String(error.stack ?? error) });
    console.error('FAILED ' + module.id + ': ' + error.message);
  }
}
const originalManifest = JSON.parse(fs.readFileSync(path.join(checkout, 'assets/landmarks/manifest.json')));
for (const asset of originalManifest.assets) {
  const flightBytes = fs.readFileSync(path.join(checkout, 'assets/landmarks', asset.model));
  const existing = path.join(root, 'public/models', asset.model);
  report.preservedGlbComparisons.push({ id: asset.id, flightSha256: sha(flightBytes), elevationSha256: fs.existsSync(existing) ? sha(fs.readFileSync(existing)) : null, sameBytes: fs.existsSync(existing) && flightBytes.equals(fs.readFileSync(existing)) });
}
report.total = { modules: extraLandmarks.length, exported: report.assets.length, failed: report.failures.length,
  triangles: report.assets.reduce((n, a) => n + a.exportedStats.triangles, 0),
  bytes: report.assets.reduce((n, a) => n + a.bytes, 0) };
fs.writeFileSync(path.join(stage, 'report.json'), JSON.stringify(report, null, 2) + '\n');
fs.renameSync(stage, out);
console.log(JSON.stringify(report.total));
console.log('Report: ' + path.join(out, 'report.json'));
if (report.failures.length) process.exitCode = 1;
