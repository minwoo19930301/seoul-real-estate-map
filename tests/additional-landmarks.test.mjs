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
  assert.equal(manifest.assets.length, 1550);
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

test('all 555 earlier model records, files and replacement lists remain unchanged', () => {
  const baseline = read('tests/fixtures/preserved-555-landmarks.json');
  assert.equal(baseline.length, 555);
  for (const original of baseline) {
    const asset = manifest.assets.find(a => a.id === original.id);
    assert.ok(asset, original.id);
    assert.equal(sha(canonical(asset)), original.recordSha256, original.id + ' metadata');
    assert.equal(sha(readFileSync(new URL(`../public/models/${asset.model}`, import.meta.url))), original.glbSha256, original.id + ' geometry');
    assert.deepEqual(matches[original.id], original.footprints, original.id + ' replacements');
  }
});

test('400-household priority batch accounts for verified counts, unknown counts and district shortfalls', () => {
  const added = read('docs/apartment-400-matched.json');
  const audit = read('docs/apartment-400-selection-audit.json');
  const oldIds = new Set(read('tests/fixtures/preserved-555-landmarks.json').map(a => a.id));
  assert.equal(added.length, 605);
  assert.equal(manifest.assets.length, 1550);
  assert.equal(new Set(added.map(a => a.id)).size, added.length);
  const counts = new Map();
  for (const candidate of added) {
    assert.ok(!oldIds.has(candidate.id));
    const asset = manifest.assets.find(a => a.id === candidate.id);
    assert.equal(asset.nameKo, candidate.nameKo);
    assert.equal(asset.householdCount, candidate.householdCount);
    assert.deepEqual(matches[candidate.id], candidate.buildingIds);
    assert.ok(candidate.buildingIds.length > 0);
    assert.ok(asset.drawCalls <= 3);
    if (candidate.householdCount == null) assert.equal(candidate.householdCountStatus, 'unverified; not counted as 400+');
    counts.set(candidate.district, (counts.get(candidate.district) ?? 0) + 1);
  }
  assert.equal(counts.size, 25);
  assert.ok([...counts.values()].every(n => n <= 25));
  assert.deepEqual(Object.fromEntries([...counts].sort()), audit.finalCounts);
  assert.equal(added.filter(a => a.householdCount >= 400).length, 445);
  assert.equal(audit.atLeast400, 445);
  assert.equal(audit.below400, 127);
  assert.equal(audit.unknownHouseholds, 33);
  assert.deepEqual(audit.shortfalls, { '강북구': 6, '금천구': 1, '종로구': 13 });
});

test('infrastructure expansion preserves every original 1160 model record and footprint assignment', () => {
  const original = read('tests/fixtures/preserved-1160-landmarks.json');
  assert.equal(original.length, 1160);
  for (const baseline of original) {
    const asset = manifest.assets.find(a => a.id === baseline.id);
    assert.equal(sha(canonical(asset)), baseline.recordSha256, baseline.id);
    assert.equal(asset.sha256, baseline.glbSha256, baseline.id);
    assert.deepEqual(matches[baseline.id], baseline.footprints, baseline.id);
  }
  const facilities = read('docs/public-facility-candidates.json');
  assert.equal(facilities.length, 364);
  for (const c of facilities) {
    const a = manifest.assets.find(a => a.id === c.id);
    assert.equal(a.nameKo, c.nameKo);
    assert.equal(a.category, c.kind);
    assert.deepEqual(a.footprintIds, c.buildingIds);
    assert.ok(a.drawCalls <= 3);
  }
  const bridges = manifest.assets.filter(a => a.category === 'bridge');
  assert.equal(bridges.length, 26);
  for (const a of bridges) {
    assert.ok(a.geoBounds.length === 4 && a.geoBounds.every(Number.isFinite));
    assert.deepEqual(matches[a.id], []);
    assert.equal(a.heightEstimated, true);
  }
});
