import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { iterateModelAssets } from '../scripts/model_catalog_assets.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const folder = path.join(root, 'public/models');
const read = name => fs.readFile(path.join(root, name));
const json = async name => JSON.parse(await read(name));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const sum = values => values.reduce((total, value) => total + value, 0);
const increment = (counts, key, amount = 1) => { counts[key] = (counts[key] ?? 0) + amount; };
const sorted = object => Object.fromEntries(Object.entries(object).sort(([a], [b]) => a.localeCompare(b)));
const manifestBytes = await read('public/models/manifest.json');
const manifest = JSON.parse(manifestBytes);
const matchesBytes = await read('public/models/footprint-matches.json');
const matches = JSON.parse(matchesBytes);
const baseline = await json('tests/fixtures/preserved-13607-models.json');
const provenance = await json('docs/RESIDENTIAL_SURVEY_PROVENANCE.json');
const audit = await json('docs/RESIDENTIAL_SURVEY_AUDIT.json');

test('residential survey preserves the exact 13607-model manifest and footprint-match bytes', () => {
  assert.equal(baseline.models, 13607);
  assert.equal(manifest.assets.length, baseline.models);
  assert.equal(manifest.catalogIndex, 'residential-survey/index.json');
  // The publisher adds exactly these two root properties; remove only their
  // complete lines so all original metadata/record formatting remains hashed.
  const text = manifestBytes.toString('utf8');
  for (const key of ['catalogIndex', 'residentialSurvey']) {
    assert.equal((text.match(new RegExp(`^  "${key}": .*[,]\\n`, 'gm')) ?? []).length, 1);
  }
  const restored = text.replace(/^  "(?:catalogIndex|residentialSurvey)": .*[,]\n/gm, '');
  assert.equal(sha(restored), baseline.manifestSha256);
  assert.equal(sha(matchesBytes), baseline.matchesSha256);
  assert.equal(provenance.selectionBaselineManifestSha256, baseline.manifestSha256);
  assert.equal(audit.baselineManifestSha256, baseline.manifestSha256);
});

test('all 131618 acquired official records have one audited disposition', () => {
  assert.equal(audit.counts.sourceFeatures, 131618);
  assert.equal(audit.counts.selected, 99516);
  const dispositions = Object.entries(audit.counts).filter(([key]) => key !== 'sourceFeatures');
  assert.ok(dispositions.every(([, count]) => Number.isSafeInteger(count) && count >= 0));
  assert.equal(sum(dispositions.map(([, count]) => count)), 131618);
  assert.equal(sum(Object.values(audit.categories)), 99516);
  assert.equal(sum(Object.values(audit.heightBasis)), 99516);
  assert.equal(Object.keys(audit.districts).length, 25);
  assert.equal(sum(Object.values(audit.districts).flatMap(counts => Object.values(counts))), 99516);
  assert.equal(audit.sourceIdsExactlyAccounted, true);
  assert.equal(provenance.allSourceDispositionsAccounted, true);
  assert.ok(audit.sharedRegisterRecordsNotTransferred > 0, 'ambiguous shared-register cases remain excluded from transfer');
  assert.equal(new Set(audit.sourceBatches.map(batch => batch.path)).size, audit.sourceBatches.length);
  assert.ok(audit.sourceBatches.every(batch => /^[a-f0-9]{64}$/.test(batch.sha256)));
});

let inspection;
function inspectCatalog() {
  // Shared across tests: read each GLB once without loading 100k Three.js scenes
  // or depending on private source databases, local Python, or Git history.
  return inspection ??= (async () => {
    const result = { legacyCount: 0, surveyCount: 0, totalCount: 0, newBytes: 0, newTriangles: 0,
      newFootprintCount: 0, emptyFootprints: 0, registerHeightCount: 0, maxTileBytes: 0, maxTileModels: 0,
      categories: {}, districts: {}, heightBasis: {}, tiles: [], index: null };
    const sourceIds = new Set(), footprintOwners = new Map(), transferredRegisterIds = new Set();
    for await (const { asset, footprintIds, tileId } of iterateModelAssets(folder, manifest, matches, {
      onIndex: index => { result.index = index; },
      onTile: tile => {
        result.tiles.push(tile); result.maxTileBytes = Math.max(result.maxTileBytes, tile.bytes);
        result.maxTileModels = Math.max(result.maxTileModels, tile.count);
      },
    })) {
      result.totalCount++;
      const bytes = await fs.readFile(path.join(folder, asset.model));
      assert.equal(sha(bytes), asset.sha256, `${asset.id}: GLB SHA256`);
      assert.equal(bytes.length, asset.bytes, `${asset.id}: GLB byte count`);
      for (const id of footprintIds) {
        assert.ok(!footprintOwners.has(id), `${id}: duplicate ownership by ${footprintOwners.get(id)} and ${asset.id}`);
        footprintOwners.set(id, asset.id);
      }
      if (tileId === null) { result.legacyCount++; continue; }
      result.surveyCount++; result.newBytes += bytes.length; result.newTriangles += asset.triangles;
      result.newFootprintCount += footprintIds.length;
      if (!footprintIds.length) result.emptyFootprints++;
      const source = asset.sourceRecord;
      assert.ok(!sourceIds.has(source.objectId), `${asset.id}: repeated official source object`);
      sourceIds.add(source.objectId);
      assert.equal(asset.id, `survey-upis-${source.objectId}`);
      assert.equal(asset.model, `residential-survey/glb/${tileId}/${asset.id}.glb`);
      increment(result.categories, asset.category.replace(/^residential-/, ''));
      result.districts[asset.district] ??= {};
      increment(result.districts[asset.district], asset.category.replace(/^residential-/, ''));
      increment(result.heightBasis, source.heightBasis);
      if (source.heightBasis.startsWith('register height corroborated')) {
        const record = source.register;
        assert.ok(record && typeof record.id === 'string' && record.id.length, `${asset.id}: missing height register identity`);
        assert.ok(!transferredRegisterIds.has(record.id), `${asset.id}: register height reused across official buildings (${record.id})`);
        transferredRegisterIds.add(record.id); result.registerHeightCount++;
        assert.equal(Number(record.floors), Number(source.sourceFloors), `${asset.id}: floor corroboration`);
        assert.equal(String(record.approval_year), String(source.sourceApprovalYear).slice(0, 4), `${asset.id}: approval year corroboration`);
        assert.ok(Math.abs(Number(record.height) - asset.dimensions[1]) < .01, `${asset.id}: transferred height envelope`);
      }
    }
    result.uniqueSourceIds = sourceIds.size;
    result.uniqueTransferredRegisterIds = transferredRegisterIds.size;
    return result;
  })();
}

test('streamed catalog verifies all 99516 new and 13607 legacy GLBs with exclusive source ownership', async () => {
  const result = await inspectCatalog();
  assert.equal(result.legacyCount, 13607); assert.equal(result.surveyCount, 99516);
  assert.equal(result.totalCount, 113123); assert.equal(result.uniqueSourceIds, 99516);
  assert.equal(result.index.assetCount, 99516); assert.equal(result.index.tileCount, 1660);
  assert.equal(result.tiles.length, result.index.tileCount);
  assert.equal(sum(result.tiles.map(tile => tile.count)), 99516);
  assert.equal(result.index.sha256, provenance.newCatalogIndexSha256);
  assert.equal(result.newBytes, provenance.newBytes); assert.equal(result.newTriangles, provenance.newTriangles);
  assert.equal(result.newFootprintCount, audit.ownedOvertureFootprints);
  assert.equal(result.maxTileBytes, provenance.maxTileBytes); assert.equal(result.maxTileModels, provenance.maxTileModels);
  assert.equal(result.totalCount, provenance.totalModels); assert.equal(result.surveyCount, provenance.newModels);
  assert.deepEqual(sorted(result.categories), sorted(audit.categories));
  assert.deepEqual(sorted(result.categories), sorted(provenance.categories));
  assert.deepEqual(result.districts, audit.districts);
  assert.deepEqual(sorted(result.heightBasis), sorted(audit.heightBasis));
  assert.ok(result.emptyFootprints > 0, 'official buildings without Overture counterparts are valid');
});

test('register heights are corroborated per building and no register ID is reused for height transfer', async () => {
  const result = await inspectCatalog();
  const expected = sum(Object.entries(audit.heightBasis).filter(([basis]) => basis.startsWith('register height corroborated')).map(([, count]) => count));
  assert.equal(result.registerHeightCount, expected);
  assert.equal(result.uniqueTransferredRegisterIds, expected);
  assert.ok(expected > 0);
});
