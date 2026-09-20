import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const jsonPath = /^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.json$/;
const modelPath = /^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.glb$/;
const hashPattern = /^[a-f0-9]{64}$/;
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const boundsValid = bounds => Array.isArray(bounds) && bounds.length === 4 && bounds.every(Number.isFinite)
  && bounds[0] >= -180 && bounds[2] <= 180 && bounds[1] >= -90 && bounds[3] <= 90
  && bounds[0] < bounds[2] && bounds[1] < bounds[3];

function validAsset(asset) {
  assert.ok(asset && typeof asset.id === 'string' && /^[a-z0-9_-]+$/.test(asset.id), 'Invalid model ID');
  assert.ok(typeof asset.model === 'string' && modelPath.test(asset.model), `${asset.id}: unsafe GLB path`);
  assert.ok(hashPattern.test(asset.sha256), `${asset.id}: invalid GLB SHA256`);
  assert.ok(Array.isArray(asset.dimensions) && asset.dimensions.length === 3
    && asset.dimensions.every(n => Number.isFinite(n) && n > 0), `${asset.id}: invalid dimensions`);
  assert.ok(asset.coordinate && Number.isFinite(asset.coordinate.lon) && Math.abs(asset.coordinate.lon) <= 180
    && Number.isFinite(asset.coordinate.lat) && Math.abs(asset.coordinate.lat) <= 90, `${asset.id}: invalid coordinates`);
  assert.ok(Number.isFinite(asset.yawDegFromEast), `${asset.id}: invalid heading`);
  if (asset.geoBounds !== undefined) assert.ok(boundsValid(asset.geoBounds), `${asset.id}: invalid geographic bounds`);
}

function officialSurveySource(asset) {
  const source = asset.sourceRecord;
  assert.equal(source?.provider, 'Seoul UPIS public building layer 86', `${asset.id}: missing official geometry provenance`);
  assert.ok(Number.isSafeInteger(source.objectId) && source.objectId > 0, `${asset.id}: invalid official object ID`);
  assert.equal(asset.id, `survey-upis-${source.objectId}`, `${asset.id}: official object ID mismatch`);
  // Empty manager/parcel strings remain explicit missing metadata; objectId is
  // the source geometry identity. An address alone is not a building match.
  assert.equal(typeof source.buildingManagerId, 'string', `${asset.id}: missing manager metadata`);
  assert.equal(typeof source.parcelId, 'string', `${asset.id}: missing parcel metadata`);
}

/** Stream legacy and optional catalog assets, validating every metadata shard. */
export async function* iterateModelAssets(folder, manifest, matches, { onIndex, onTile } = {}) {
  assert.ok(Array.isArray(manifest.assets), 'Missing legacy asset array');
  assert.ok(matches && typeof matches === 'object' && !Array.isArray(matches), 'Invalid footprint matches');
  const ids = new Set(), paths = new Set(), owners = new Map();
  const claim = (id, footprints) => {
    assert.ok(Array.isArray(footprints), `${id}: missing footprint membership`);
    assert.equal(new Set(footprints).size, footprints.length, `${id}: repeated footprint membership`);
    for (const footprint of footprints) {
      assert.ok(typeof footprint === 'string' && footprint.length > 0 && footprint.length <= 200, `${id}: invalid footprint ID`);
      const owner = owners.get(footprint);
      assert.ok(owner === undefined || owner === id, `${id}: footprint ${footprint} already owned by ${owner}`);
      owners.set(footprint, id);
    }
  };
  // Preserve all existing ownership, including legacy records not rendered by
  // this particular manifest. Inline survey metadata cannot take them over.
  for (const [id, footprints] of Object.entries(matches)) claim(id, footprints);
  const admit = asset => {
    validAsset(asset);
    assert.ok(!ids.has(asset.id), `${asset.id}: duplicate model ID`);
    assert.ok(!paths.has(asset.model), `${asset.id}: duplicate GLB path`);
    ids.add(asset.id); paths.add(asset.model);
  };
  for (const asset of manifest.assets) {
    admit(asset);
    const footprintIds = matches[asset.id] ?? asset.footprintIds;
    if (asset.category === 'bridge') assert.deepEqual(footprintIds, [], `${asset.id}: bridge must not replace buildings`);
    else assert.ok(footprintIds?.length, `${asset.id}: empty legacy footprint membership`);
    claim(asset.id, footprintIds);
    yield { asset, footprintIds, tileId: null };
  }
  if (manifest.catalogIndex === undefined) return;
  assert.ok(typeof manifest.catalogIndex === 'string' && jsonPath.test(manifest.catalogIndex), 'Unsafe catalog index path');
  const readJSON = async name => {
    const bytes = await fs.readFile(path.join(folder, name));
    assert.ok(bytes.length <= 8 * 1024 * 1024, `${name}: catalog JSON exceeds 8 MiB`);
    return { bytes, value: JSON.parse(bytes.toString('utf8')) };
  };
  const { bytes: indexBytes, value: index } = await readJSON(manifest.catalogIndex);
  assert.equal(index.version, 1, 'Unsupported catalog index version');
  assert.ok(Number.isFinite(index.minZoom) && index.minZoom >= 16.5 && index.minZoom <= 24, 'Invalid catalog minimum zoom');
  assert.ok(Number.isSafeInteger(index.assetCount) && index.assetCount >= 0 && index.assetCount <= 1000000, 'Invalid catalog count');
  assert.ok(Array.isArray(index.tiles) && index.tiles.length <= 20000, 'Invalid catalog tiles');
  const tileIds = new Set();
  const directory = path.posix.dirname(manifest.catalogIndex);
  let count = 0;
  for (const tile of index.tiles) {
    assert.ok(tile && typeof tile.id === 'string' && /^16-\d+-\d+$/.test(tile.id) && !tileIds.has(tile.id), 'Invalid or duplicate catalog tile');
    tileIds.add(tile.id);
    assert.ok(typeof tile.path === 'string' && jsonPath.test(tile.path), `${tile.id}: unsafe tile path`);
    assert.equal(tile.path, path.posix.join(directory, 'tiles', `${tile.id}.json`), `${tile.id}: tile path mismatch`);
    assert.ok(boundsValid(tile.bounds), `${tile.id}: invalid bounds`);
    assert.ok(Number.isSafeInteger(tile.count) && tile.count > 0 && tile.count <= 4096, `${tile.id}: invalid tile count`);
    assert.ok(hashPattern.test(tile.sha256), `${tile.id}: invalid tile SHA256`);
    count += tile.count;
  }
  assert.equal(count, index.assetCount, 'Catalog declared count mismatch');
  await onIndex?.({ path: manifest.catalogIndex, sha256: digest(indexBytes), bytes: indexBytes.length,
    assetCount: index.assetCount, tileCount: index.tiles.length });
  count = 0;
  for (const tile of index.tiles) {
    const { bytes, value } = await readJSON(tile.path);
    assert.equal(digest(bytes), tile.sha256, `${tile.id}: tile SHA256 mismatch`);
    assert.equal(value.version, 1, `${tile.id}: unsupported tile version`);
    assert.ok(Array.isArray(value.assets), `${tile.id}: missing assets`);
    assert.equal(value.assets.length, tile.count, `${tile.id}: tile asset count mismatch`);
    await onTile?.({ id: tile.id, path: tile.path, sha256: tile.sha256, bytes: bytes.length, count: tile.count });
    for (const asset of value.assets) {
      admit(asset); officialSurveySource(asset);
      const { lon, lat } = asset.coordinate;
      assert.ok(lon >= tile.bounds[0] && lon <= tile.bounds[2] && lat >= tile.bounds[1] && lat <= tile.bounds[3], `${asset.id}: coordinate outside tile bounds`);
      assert.ok(asset.minZoom === undefined || Number.isFinite(asset.minZoom) && asset.minZoom >= index.minZoom, `${asset.id}: invalid catalog minimum zoom`);
      const footprintIds = asset.footprintIds ?? matches[asset.id];
      claim(asset.id, footprintIds);
      count++;
      yield { asset, footprintIds, tileId: tile.id };
    }
  }
  assert.equal(count, index.assetCount, 'Catalog actual count mismatch');
}
