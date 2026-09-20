import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { iterateModelAssets } from './model_catalog_assets.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const folder = path.join(root, 'public/models');
const manifest = JSON.parse(await fs.readFile(path.join(folder, 'manifest.json'), 'utf8'));
const matches = JSON.parse(await fs.readFile(path.join(folder, 'footprint-matches.json'), 'utf8'));
const legacyRows = [], loader = new GLTFLoader();
const createTotals = () => ({ assetCount: 0, totalBytes: 0, totalTriangles: 0, totalVertices: 0,
  totalDrawCalls: 0, maxAssetBytes: 0, footprintCount: 0, modelsWithoutOvertureFootprints: 0 });
const totals = createTotals(), categories = new Map(), tiles = new Map();
const modelProof = crypto.createHash('sha256');
let catalogIndex;

function accumulate(target, row, footprintIds) {
  target.assetCount++; target.totalBytes += row.bytes; target.totalTriangles += row.triangles;
  target.totalVertices += row.vertices; target.totalDrawCalls += row.drawCalls;
  target.maxAssetBytes = Math.max(target.maxAssetBytes, row.bytes);
  target.footprintCount += footprintIds.length;
  if (!footprintIds.length) target.modelsWithoutOvertureFootprints++;
}

for await (const { asset, footprintIds, tileId } of iterateModelAssets(folder, manifest, matches, {
  onIndex: index => { catalogIndex = index; },
  onTile: tile => { tiles.set(tile.id, { ...tile, ...createTotals(), proof: crypto.createHash('sha256') }); },
})) {
  const bytes = await fs.readFile(path.join(folder, asset.model));
  const actualSha = crypto.createHash('sha256').update(bytes).digest('hex');
  assert.equal(actualSha, asset.sha256, `${asset.id}: SHA256`);
  assert.equal(bytes.length, asset.bytes, `${asset.id}: byte count`);
  assert.ok(bytes.length >= 28, `${asset.id}: truncated GLB`);
  assert.equal(bytes.readUInt32LE(0), 0x46546c67, `${asset.id}: GLB magic`);
  assert.equal(bytes.readUInt32LE(4), 2, `${asset.id}: GLB version`);
  assert.equal(bytes.readUInt32LE(8), bytes.length, `${asset.id}: GLB declared length`);
  const jsonLength = bytes.readUInt32LE(12);
  assert.equal(bytes.readUInt32LE(16), 0x4e4f534a, `${asset.id}: JSON chunk type`);
  assert.ok(jsonLength > 0 && jsonLength % 4 === 0 && 20 + jsonLength <= bytes.length, `${asset.id}: JSON chunk bounds`);
  const document = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString('utf8').trim());
  assert.ok(!(document.buffers ?? []).some(buffer => buffer.uri), `${asset.id}: external buffer`);
  assert.ok(!(document.images ?? []).some(image => image.uri), `${asset.id}: external image`);
  const gltf = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const dimensions = box.getSize(new THREE.Vector3()).toArray();
  assert.ok(Math.abs(box.min.y) < .01, `${asset.id}: floor origin`);
  assert.ok(dimensions.every((value, i) => Number.isFinite(value) && Math.abs(value - asset.dimensions[i]) < .01), `${asset.id}: metre dimensions`);
  let triangles = 0, drawCalls = 0, vertices = 0;
  gltf.scene.traverse(node => {
    if (!node.isMesh) return;
    const geometry = node.geometry, positions = geometry.attributes.position, normals = geometry.attributes.normal;
    assert.ok(positions && normals && positions.count === normals.count, `${asset.id}: position/normal attributes`);
    const elementCount = geometry.index?.count ?? positions.count;
    assert.equal(elementCount % 3, 0, `${asset.id}: incomplete triangle`);
    drawCalls += Array.isArray(node.material) ? node.material.length : 1;
    triangles += elementCount / 3; vertices += positions.count;
    for (let i = 0; i < positions.count; i++) {
      assert.ok(Number.isFinite(positions.getX(i)) && Number.isFinite(positions.getY(i)) && Number.isFinite(positions.getZ(i)), `${asset.id}: finite positions`);
      const length = Math.hypot(normals.getX(i), normals.getY(i), normals.getZ(i));
      assert.ok(Math.abs(length - 1) < .01, `${asset.id}: unit normal`);
    }
    if (geometry.index) for (let i = 0; i < geometry.index.count; i++) {
      const index = geometry.index.getX(i);
      assert.ok(Number.isSafeInteger(index) && index >= 0 && index < positions.count, `${asset.id}: index range`);
    }
    geometry.dispose();
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) material.dispose();
  });
  assert.equal(triangles, asset.triangles, `${asset.id}: triangle count`);
  if (asset.drawCalls !== undefined) assert.equal(drawCalls, asset.drawCalls, `${asset.id}: draw calls`);
  const row = { id: asset.id, bytes: bytes.length, triangles, drawCalls, vertices,
    bounds: { min: box.min.toArray(), max: box.max.toArray() }, sha256: actualSha };
  const proofLine = JSON.stringify([asset.id, asset.model, actualSha, bytes.length, triangles, dimensions, footprintIds]) + '\n';
  modelProof.update(proofLine); accumulate(totals, row, footprintIds);
  if (tileId === null) legacyRows.push(row);
  else {
    const tile = tiles.get(tileId);
    accumulate(tile, row, footprintIds); tile.proof.update(proofLine);
    const category = asset.category ?? 'unclassified';
    if (!categories.has(category)) categories.set(category, createTotals());
    accumulate(categories.get(category), row, footprintIds);
  }
  if (totals.assetCount % 5000 === 0) console.log(`Validated ${totals.assetCount} individual GLBs`);
}

const result = {
  validator: `Three.js GLTFLoader; all ${totals.assetCount} binary files parsed`, ...totals,
  modelProofSha256: modelProof.digest('hex'),
  proofEncoding: 'SHA256 of UTF-8 JSON lines [id,model,actualGlbSha256,bytes,triangles,actualDimensions,footprintIds] in manifest/index/tile order',
  checks: ['SHA256', 'byteCount', 'GLBHeader', 'float32metreBounds', 'floorOrigin', 'finitePositions', 'unitNormals',
    'indicesInRange', 'triangleCount', 'drawCalls', 'uniqueModelIdentity', 'exclusiveFootprintOwnership',
    'legacyFootprintMembership', 'officialSurveySourceIdentity', 'catalogTileSHA256AndCounts', 'noExternalResources'],
  detailedAssetCount: legacyRows.length,
  assets: legacyRows,
  ...(catalogIndex ? { catalog: {
    ...catalogIndex,
    detailScope: 'Every catalog GLB validated individually; results aggregated by tile/category. Legacy records remain detailed in assets.',
    categories: Object.fromEntries([...categories].sort(([a], [b]) => a.localeCompare(b))),
    tiles: [...tiles.values()].map(({ proof, ...tile }) => ({ ...tile, modelProofSha256: proof.digest('hex') })),
  } } : {}),
};
const output = path.join(root, 'docs/LANDMARK_ASSET_VALIDATION.json');
const temporary = output + '.tmp';
await fs.writeFile(temporary, JSON.stringify(result, null, 2) + '\n');
await fs.rename(temporary, output);
console.log(JSON.stringify({ ...result, assets: undefined,
  ...(result.catalog ? { catalog: { ...result.catalog, tiles: undefined } } : {}) }, null, 2));
