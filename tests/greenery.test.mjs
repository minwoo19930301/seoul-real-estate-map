import test from 'node:test';
import assert from 'node:assert/strict';
import { buildDecorativeTrees } from '../src/greenery.ts';

const metresLon = 111320 * Math.cos(37.56 * Math.PI / 180);
const lonlat = ([x, y]) => [126.97 + x / metresLon, 37.56 + y / 111132];
const metres = ([lon, lat]) => [(lon - 126.97) * metresLon, (lat - 37.56) * 111132];
const ring = (x1, y1, x2, y2) => [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]].map(lonlat);
const collection = features => ({ type: 'FeatureCollection', features });
const polygon = (rings, properties = {}) => ({ type: 'Feature', geometry: { type: 'Polygon', coordinates: rings }, properties });
const defaults = () => ({
  greenery: collection([polygon([ring(-350, -350, 350, 350)], { class: 'wood' })]),
  buildings: collection([]), roads: collection([]),
  bounds: [...lonlat([-400, -400]), ...lonlat([400, 400])], exclusionsReady: true,
});

test('only source woodland produces decoration, and incomplete exclusions fail closed', () => {
  const input = defaults();
  assert.ok(buildDecorativeTrees(input).length > 20);
  assert.deepEqual(buildDecorativeTrees({ ...input, exclusionsReady: false }), []);
  for (const metadata of [{ available: false }, { truncated: true }, { hidden_at_zoom: true }, { walkways_hidden_at_zoom: true }]) {
    assert.deepEqual(buildDecorativeTrees({ ...input, roads: { ...input.roads, metadata } }), []);
  }
  input.greenery.features[0].properties = { class: 'grass', subclass: 'park' };
  assert.deepEqual(buildDecorativeTrees(input), []);
});

test('crowns avoid forest boundaries, interior holes, buildings and road buffers', () => {
  const input = defaults();
  input.greenery.features[0].geometry.coordinates.push(ring(-50, -50, 50, 50));
  input.buildings = collection([polygon([ring(100, -350, 160, 350)])]);
  input.roads = collection([{
    type: 'Feature', properties: { highway: 'primary' },
    geometry: { type: 'LineString', coordinates: [lonlat([-150, -500]), lonlat([-150, 500])] },
  }]);
  const trees = buildDecorativeTrees(input);
  assert.ok(trees.length > 20);
  for (const tree of trees) {
    const [x, y] = metres(tree.coordinate), radius = tree.crown_radius_m;
    assert.ok(Math.abs(x) < 350 - radius - 1 && Math.abs(y) < 350 - radius - 1);
    assert.ok(Math.hypot(Math.max(0, Math.abs(x) - 50), Math.max(0, Math.abs(y) - 50)) > radius + 1);
    assert.ok(x < 100 - radius - 2 || x > 160 + radius + 2);
    assert.ok(Math.abs(x + 150) > 18 + radius);
  }
});

test('placements are deterministic, deduplicate overlapping tiles, and retain source data', () => {
  const input = defaults();
  const before = structuredClone(input);
  const expected = buildDecorativeTrees(input);
  assert.deepEqual(buildDecorativeTrees(input), expected);
  assert.deepEqual(input, before);
  input.greenery.features.push(structuredClone(input.greenery.features[0]));
  assert.deepEqual(buildDecorativeTrees(input), expected);
  assert.equal(new Set(expected.map(tree => tree.id)).size, expected.length);
  assert.ok(expected.every(tree => tree.decorative && tree.height_m >= 5 && tree.height_m < 9));
});

test('tree limits and malformed exclusion geometry never create uncontrolled decoration', () => {
  const input = defaults();
  assert.equal(buildDecorativeTrees({ ...input, maxCount: 8 }).length, 8);
  assert.deepEqual(buildDecorativeTrees({ ...input, maxCount: 0 }), []);
  assert.ok(buildDecorativeTrees({ ...input, maxCount: 100000 }).length <= 240);
  input.buildings.features.push(polygon([[[NaN, 37.56], [126.97, 37.56]]]));
  assert.deepEqual(buildDecorativeTrees(input), []);
});

test('query boundaries reserve space for exclusion geometry just outside the box', () => {
  const input = defaults();
  input.greenery.features[0].geometry.coordinates = [ring(-1000, -1000, 1000, 1000)];
  const trees = buildDecorativeTrees(input);
  assert.ok(trees.length > 20);
  for (const tree of trees) {
    const [x, y] = metres(tree.coordinate);
    assert.ok(Math.abs(x) <= 400 - 32 && Math.abs(y) <= 400 - 32);
  }
  input.bounds = [...lonlat([-20, -20]), ...lonlat([20, 20])];
  assert.deepEqual(buildDecorativeTrees(input), []);
});
