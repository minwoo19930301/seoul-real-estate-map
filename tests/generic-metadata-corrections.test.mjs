import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { applyGenericCorrections } from '../src/generic-corrections.ts';

const json = file => JSON.parse(fs.readFileSync(new URL('../' + file, import.meta.url)));
const base = json('public/models/manifest.json');
const matches = json('public/models/footprint-matches.json');
const original = base.assets.find(a => a.id === 'apt-a13780001');
function fixture() {
  const part = structuredClone(original);
  part.name = part.nameKo = '래미안퍼스티지 125동 (기존 추정 모형)';
  delete part.apartmentCode;
  delete part.householdCount;
  part.sourceIdentity = { sourceFootprintId: original.footprintIds[0], geometryChanged: false };
  return { version: 1, corrections: [{ kind: 'metadata-only', sourceId: original.id,
    sourceSha256: original.sha256, sourceFootprintIds: [...matches[original.id]], assets: [part] }] };
}

test('explicit singleton identity correction preserves its rendering and source ownership', () => {
  const document = fixture(), before = structuredClone({ base, matches, document });
  const result = applyGenericCorrections(base.assets, matches, document);
  const changed = result.assets.find(a => a.id === original.id);
  assert.equal(changed.nameKo, '래미안퍼스티지 125동 (기존 추정 모형)');
  assert.equal(changed.apartmentCode, undefined);
  assert.equal(changed.householdCount, undefined);
  assert.equal(changed.model, original.model);
  assert.equal(changed.sha256, original.sha256);
  assert.equal(result.assets.length, base.assets.length);
  assert.deepEqual(result.matches, matches);
  for (const asset of base.assets.filter(a => a.id !== original.id)) assert.equal(result.assets.find(a => a.id === asset.id), asset);
  assert.deepEqual({ base, matches, document }, before);
});

test('metadata-only corrections reject every rendering, geometry, ID and ownership change', () => {
  for (const corrupt of [
    c => c.assets[0].model = 'other.glb',
    c => c.assets[0].sha256 = '0'.repeat(64),
    c => c.assets[0].id = 'renamed-fallback',
    c => c.assets[0].coordinate.lon += .00001,
    c => c.assets[0].yawDegFromEast = 10,
    c => c.assets[0].dimensions[1] += 1,
    c => c.assets[0].bounds.max[1] += 1,
    c => c.assets[0].geoBounds = [126, 37, 127, 38],
    c => c.assets[0].groundOffsetM = 1,
    c => c.assets[0].minZoom = 1,
    c => c.assets[0].quality = 'reference',
    c => c.assets[0].supersedes = ['other'],
    c => c.assets[0].genericCorrection = { sourceId: 'other' },
    c => c.assets[0].category = 'other',
    c => c.assets[0].bytes++,
    c => c.assets[0].triangles++,
    c => c.assets[0].footprintIds[0] = 'other',
    c => c.assets[0].footprintIds.push(c.assets[0].footprintIds[0]),
    c => c.assets[0].futureRenderingProperty = true,
    c => delete c.assets[0].heightDatum,
    c => c.assets.push(structuredClone(c.assets[0])),
    c => c.assets[0].nameKo = '',
  ]) {
    const document = fixture(); corrupt(document.corrections[0]);
    const before = structuredClone({ base, matches, document });
    assert.throws(() => applyGenericCorrections(base.assets, matches, document), /Metadata-only correction/);
    assert.deepEqual({ base, matches, document }, before);
  }
});

test('ordinary singleton partitions, unknown kinds, compounds and repeated identity corrections fail closed', () => {
  for (const corrupt of [
    c => delete c.kind,
    c => c.kind = 'unchecked',
    c => c.sourceSha256 = '0'.repeat(64),
  ]) {
    const document = fixture(); corrupt(document.corrections[0]);
    assert.throws(() => applyGenericCorrections(base.assets, matches, document), /source mismatch/);
  }
  const compound = base.assets.find(a => a.id === 'apt-a13776508');
  const document = { version: 1, corrections: [{ kind: 'metadata-only', sourceId: compound.id,
    sourceSha256: compound.sha256, sourceFootprintIds: matches[compound.id], assets: [structuredClone(compound)] }] };
  assert.throws(() => applyGenericCorrections(base.assets, matches, document), /Metadata-only correction/);
  const duplicate = fixture(); duplicate.corrections.push(structuredClone(duplicate.corrections[0]));
  assert.throws(() => applyGenericCorrections(base.assets, matches, duplicate), /source mismatch/);
});
