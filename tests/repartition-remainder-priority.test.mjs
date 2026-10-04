import test from 'node:test';
import assert from 'node:assert/strict';
import { applyGenericCorrections } from '../src/generic-corrections.ts';
import { CityModels } from '../src/city-models.ts';

const hash = n => String(n).repeat(64);
const base = { id: 'compound', model: 'compound.glb', sha256: hash(1),
  coordinate: { lon: 10, lat: 0 }, yawDegFromEast: 0, dimensions: [10, 20, 10],
  geoBounds: [9, -1, 11, 1], footprintIds: ['a', 'b', 'c', 'd'] };
function part(id, footprints, sourceId, n, searchable) {
  return { ...base, id, model: `generic-corrections/${id}.glb`, sha256: hash(n),
    footprintIds: footprints, searchable, genericCorrection: { sourceId } };
}
function chain(count = 3) {
  const first = { sourceId: 'compound', sourceSha256: hash(1), sourceFootprintIds: ['a','b','c','d'], assets: [
    part('target-a', ['a'], 'compound', 2, false), part('compound', ['b','c','d'], 'compound', 3, true)] };
  const second = { kind: 'repartition', sourceId: 'compound', sourceSha256: hash(3), sourceFootprintIds: ['b','c','d'], assets: [
    part('target-b', ['b'], 'compound', 4, false), part('residual-v2', ['c','d'], 'compound', 5, true)] };
  const third = { kind: 'repartition', sourceId: 'residual-v2', sourceSha256: hash(5), sourceFootprintIds: ['c','d'], assets: [
    part('target-c', ['c'], 'residual-v2', 6, false), part('residual-v3', ['d'], 'residual-v2', 7, true)] };
  return { version: 1, corrections: [first, second, third].slice(0, count) };
}
const view = { zoom: 18, lon: 0, lat: 0, west: -20, east: 20, south: -1, north: 1 };
function harness(effective, extras = 1) {
  const models = new CityModels({});
  const rep = { id: 'rep-a', quality: 'reference', coordinate: { lon: 0, lat: 0 },
    footprintIds: ['a'], supersedes: ['target-a'] };
  const additions = Array.from({length: extras}, (_, i) => ({ id: `other-${i}`, quality: 'reference',
    coordinate: { lon: 1 + i / 100, lat: 0 }, footprintIds: [`other-${i}`], supersedes: [`fallback-${i}`] }));
  const fallbacks = additions.map((a, i) => ({ ...a, id: `fallback-${i}`, quality: undefined, supersedes: [] }));
  models.entries = [...effective.assets, rep, ...additions, ...fallbacks].map(asset => ({ asset, error: null, ground: null, draws: 0, active: false }));
  models.legacyEntries = models.entries;
  models.inView = () => true;
  models.matches = effective.matches;
  return models;
}

test('sequential repartitions retain current ancestry without mutating public records or old targets', () => {
  const doc = chain(), snapshot = structuredClone({base, doc});
  const effective = applyGenericCorrections([base], {compound: base.footprintIds}, doc);
  assert.deepEqual({base, doc}, snapshot);
  assert.ok(!effective.assets.some(a => ['compound','residual-v2'].includes(a.id)));
  assert.deepEqual(effective.assets.find(a => a.id === 'residual-v3').genericCorrection.ancestorSourceIds,
    ['residual-v2','compound']);
  for (const id of ['target-a','target-b','target-c']) {
    const original = doc.corrections.flatMap(c => c.assets).find(a => a.id === id);
    const actual = structuredClone(effective.assets.find(a => a.id === id));
    delete actual.genericCorrection.ancestorSourceIds;
    assert.deepEqual(actual, original);
  }
  assert.equal(effective.assets.find(a => a.id === 'residual-v3').searchable, true);
});

test('same-ID residual and two renamed generations inherit representative selection priority', () => {
  for (const count of [1, 2, 3]) {
    const effective = applyGenericCorrections([base], {compound: base.footprintIds}, chain(count));
    const residualId = count === 1 ? 'compound' : `residual-v${count}`;
    const models = harness(effective);
    models.maxNearby = 2;
    const selected = models.nearbyCandidates(view).map(e => e.asset.id);
    assert.deepEqual([...models.retainedRemainders.get('rep-a')], [residualId]);
    assert.ok(selected.includes(residualId), `${count}: remote residual must inherit nearby representative rank`);
    assert.ok(selected.includes('target-a'), 'direct target remains available if representative fails');
    assert.ok(!selected.includes('other-0'));
  }
});

test('renamed residual remains selected in dense views without exceeding 48 resident slots', () => {
  const effective = applyGenericCorrections([base], {compound: base.footprintIds}, chain());
  const models = harness(effective, 60);
  const selected = models.nearbyCandidates(view).map(e => e.asset.id);
  assert.ok(selected.includes('residual-v3'));
  assert.ok(selected.includes('rep-a'));
  assert.ok(models.entries.some(e => e.asset.id === 'target-a'), 'old target is retained even when fallback budget is full');
  assert.equal(selected.length, 48);
  const failed = models.entries.find(e => e.asset.id === 'rep-a');
  failed.error = 'HTTP404'; models.trackEntry(failed); models.nearbyCache = undefined;
  assert.ok(models.nearbyCandidates(view).some(e => e.asset.id === 'target-a'), 'failed representative promotes its own fallback');
  assert.ok(!selected.includes('compound') && !selected.includes('residual-v2'));
});
