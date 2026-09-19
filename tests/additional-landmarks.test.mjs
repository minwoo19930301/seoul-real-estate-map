import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const read = file => JSON.parse(readFileSync(new URL(`../${file}`, import.meta.url)));
const canonical = value => JSON.stringify(sort(value));
function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, sort(value[k])]));
  return value;
}
const sha = value => createHash('sha256').update(value).digest('hex');
const manifest = read('public/models/manifest.json');
const matches = read('public/models/footprint-matches.json');
test('all 255 previously published models retain exact metadata, geometry and footprint membership', () => {
  const baseline = read('tests/fixtures/preserved-255-landmarks.json');
  assert.equal(baseline.length, 255);
  for (const original of baseline) {
    const asset = manifest.assets.find(a => a.id === original.id);
    assert.ok(asset, original.id);
    assert.equal(sha(canonical(asset)), original.recordSha256, original.id + ' metadata');
    assert.equal(sha(readFileSync(new URL(`../public/models/${asset.model}`, import.meta.url))), original.glbSha256, original.id + ' geometry');
    assert.deepEqual(matches[original.id], original.footprints, original.id + ' replacements');
  }
});
test('300 additional sites cover all districts with unique physical footprint ownership', () => {
  const added = read('docs/landmark-candidates-expansion-matched.json');
  const baseline = read('tests/fixtures/preserved-255-landmarks.json');
  const oldIds = new Set(baseline.map(x => x.id));
  assert.equal(added.length, 300);
  assert.equal(new Set(added.map(x => x.id)).size, 300);
  assert.equal(manifest.assets.length, 555);
  const counts = new Map();
  for (const candidate of added) {
    assert.ok(!oldIds.has(candidate.id));
    counts.set(candidate.district, (counts.get(candidate.district) ?? 0) + 1);
    const asset = manifest.assets.find(x => x.id === candidate.id);
    assert.equal(asset.nameKo, candidate.nameKo);
    assert.equal(asset.district, candidate.district);
    assert.deepEqual(matches[candidate.id], candidate.buildingIds);
    assert.ok(asset.drawCalls <= 3);
    assert.ok(candidate.sourceUrls.length && candidate.sourceUrls.every(x => /^https:\/\//.test(x)));
  }
  assert.equal(counts.size, 25);
  assert.ok([...counts.values()].every(n => n === 12));
  const owners = new Map();
  for (const [id, footprints] of Object.entries(matches)) {
    for (const footprint of footprints) {
      assert.ok(!owners.has(footprint), `${footprint} belongs to ${owners.get(footprint)} and ${id}`);
      owners.set(footprint, id);
    }
  }
});
