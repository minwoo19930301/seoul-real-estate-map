import test from 'node:test';
import assert from 'node:assert/strict';
import {
  horizontalDistance, prepareRoute, projectMercator, sampleRoute, slopeDegrees, terrainPointVisible,
} from '../src/mobility-math.ts';
import { nearestStreet, routeBearing } from '../src/street-view.ts';

const LATITUDE = 37.5;
const metresLatitude = 180 / (Math.PI * 6371008.8);
const metresLongitude = metresLatitude / Math.cos(LATITUDE * Math.PI / 180);
const point = (x, elevation = 0, y = 0) => [127 + x * metresLongitude, LATITUDE + y * metresLatitude, elevation];
const route = (coordinates, fields = {}) => ({ id: 'source-way', kind: 'pedestrian', category: 'walkway', oneway: false, coordinates, ...fields });
const near = (a, b, tolerance = 1e-6) => assert.ok(Math.abs(a - b) <= tolerance, `${a} != ${b}`);

test('route interpolation retains raw negative heights and clamps at source endpoints', () => {
  const input = route([point(0, -5.5), point(100, 10.5)]);
  const prepared = prepareRoute(input);
  near(sampleRoute(prepared, 50).coordinate[0], point(50)[0]);
  near(sampleRoute(prepared, 50).coordinate[2], 2.5);
  assert.deepEqual(sampleRoute(prepared, -100).coordinate, input.coordinates[0]);
  assert.deepEqual(sampleRoute(prepared, 1000).coordinate, input.coordinates[1]);
  near(slopeDegrees(15, 100), 8.530765609948133);
  near(slopeDegrees(Math.tan(Math.PI / 12) * 100, 100), 15);
});

test('reverse sampling preserves source geometry and vehicle direction without mutating input', () => {
  const input = route([point(0, 10), point(10, 15), point(20, 20)]);
  const original = structuredClone(input);
  const backward = prepareRoute(input, -1);
  near(sampleRoute(backward, 5).coordinate[0], point(15)[0]);
  near(sampleRoute(backward, 5).coordinate[2], 17.5);
  assert.ok(sampleRoute(backward, 5).slopeDegrees < 0);
  const car = { ...input, kind: 'car', category: 'roadway', oneway: true };
  assert.equal(prepareRoute(car, -1), null);
  assert.ok(prepareRoute({ ...car, kind: 'pedestrian' }, -1));
  assert.deepEqual(input, original);
});

test('manual traversal follows original bends rather than a shortcut between endpoints', () => {
  const prepared = prepareRoute(route([point(0, 0), point(20, 2), point(20, 4, 20)]));
  const at = prepared.segments[1].start + prepared.segments[1].length / 2;
  const halfway = sampleRoute(prepared, at).coordinate;
  near(halfway[0], point(20)[0]); near(halfway[1], point(0, 0, 10)[1]); near(halfway[2], 3);
  near(prepared.length, 40, 1e-4);
});

test('zero-length and invalid geometry cannot invent a vertical route or infinite grade', () => {
  assert.equal(prepareRoute(route([point(0, 0), point(0, 100)])), null);
  assert.equal(prepareRoute(route([point(0, 0), [127, 37.5, NaN]])), null);
  assert.equal(prepareRoute(route([point(0), [181, 37.5, 0]])), null);
  const cleaned = prepareRoute(route([point(0, 10), point(0, 500), point(10, 10)]));
  assert.equal(cleaned.coordinates.length, 2);
  assert.equal(sampleRoute(cleaned, 5).slopeDegrees, 0);
  near(horizontalDistance(point(0), point(100)), 100);
});

test('first-person snapping prefers a nearby pedestrian line and rejects distant routes', () => {
  const car = route([point(-100), point(100)], { id: 'car', kind: 'car', category: 'roadway' });
  const sidewalk = route([point(-100, 10, 40), point(100, 10, 40)], { id: 'sidewalk' });
  const selected = nearestStreet([car, sidewalk], point(0).slice(0, 2));
  assert.equal(selected.route.source.id, 'sidewalk');
  near(selected.offset, 40, .01);
  near(sampleRoute(selected.route, selected.distance).coordinate[0], point(0)[0]);
  const farSidewalk = route([point(-100, 10, 80), point(100, 10, 80)], { id: 'far' });
  assert.equal(nearestStreet([car, farSidewalk], point(0).slice(0, 2)).route.source.id, 'car');
  assert.equal(nearestStreet([car, sidewalk], point(1000).slice(0, 2)), null);
});

test('street bearings respect source orientation at both endpoints and around bends', () => {
  const east = prepareRoute(route([point(0), point(20)]));
  near(routeBearing(east, 0), 90); near(routeBearing(east, east.length), 90);
  near(routeBearing(prepareRoute(east.source, -1), 5), -90);
  const bent = prepareRoute(route([point(0), point(20), point(20, 0, 20)]));
  near(routeBearing(bent, bent.segments[1].start + 5), 0);
});

test('public column-major projection includes altitude and rejects behind-camera or clipped points', () => {
  const matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1];
  assert.deepEqual(projectMercator(matrix, { x: 0, y: 0, z: 0 }, 100, 100), { x: 50, y: 50 });
  near(projectMercator(matrix, { x: 0, y: 0, z: .4 }, 100, 100).y, 30);
  assert.equal(projectMercator(matrix, { x: 0, y: 0, z: 2 }, 100, 100), null);
  matrix[15] = -1;
  assert.equal(projectMercator(matrix, { x: 0, y: 0, z: 0 }, 100, 100), null);
});

test('terrain visibility rejects foreground occlusion and real dimensions obey perspective', () => {
  const original = point(0, 999);
  assert.equal(terrainPointVisible(original, { lng: original[0], lat: original[1] }), true);
  assert.equal(terrainPointVisible(original, { lng: point(3)[0], lat: original[1] }), false);
  assert.equal(terrainPointVisible(original, { lng: NaN, lat: original[1] }), false);
  // A fixed 1.7 m reference twice as far away has half the projected height.
  const perspective = [1,0,0,0, 0,1,0,1, 0,.1,0,0, 0,0,0,1];
  const height = distance => projectMercator(perspective, { x: 0, y: distance, z: 0 }, 1000, 600).y - projectMercator(perspective, { x: 0, y: distance, z: 1.7 }, 1000, 600).y;
  near(height(1), height(3) * 2);
});
