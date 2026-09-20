import test from 'node:test';
import assert from 'node:assert/strict';
import { CityModels } from '../src/city-models.ts';
import { queryBounds, isCloseView, setFlightQueryFocus } from '../src/view-window.ts';

const center = { lng: 127, lat: 37.55 };
const metresPerDegree = Math.PI * 6371008.8 / 180;
function map(bounds, zoom = 22, pitch = 85) {
  return { getBounds: () => ({ getWest: () => bounds[0], getSouth: () => bounds[1], getEast: () => bounds[2], getNorth: () => bounds[3] }),
    getCenter: () => center, getZoom: () => zoom, getPitch: () => pitch };
}

test('normal overview, zoomed overhead and pre-threshold views keep the exact original bounds', () => {
  const bounds = [126.321012345, 37.123456789, 127.87654321, 38.1];
  for (const [zoom, pitch] of [[18.99, 85], [19, 74.99], [24, 0], [10, 60]]) {
    const current = map(bounds, zoom, pitch);
    assert.equal(isCloseView(current), false);
    assert.deepEqual(queryBounds(current), bounds);
  }
});

test('street-level horizon requests remain inside a 600 metre local square', () => {
  const current = map([125, 35, 129, 40], 19, 75);
  const [west, south, east, north] = queryBounds(current);
  assert.equal(isCloseView(current), true);
  assert.ok(Math.abs((east - west) * metresPerDegree * Math.cos(center.lat * Math.PI / 180) - 600) < 1e-6);
  assert.ok(Math.abs((north - south) * metresPerDegree - 600) < 1e-6);
  assert.ok(Math.abs((west + east) / 2 - center.lng) < 1e-10);
  assert.ok(Math.abs((south + north) / 2 - center.lat) < 1e-10);
});

test('eye-level requests include nearby tall buildings beyond the small ground-plane extent', () => {
  const small = [126.9999, 37.5499, 127.0001, 37.5501];
  const surrounding = queryBounds(map(small));
  assert.ok(surrounding[0] < small[0] && surrounding[2] > small[2]);
  assert.ok(surrounding[1] < small[1] && surrounding[3] > small[3]);
  const partlyVisible = [126.9999, 37.5499, 130, 40];
  const limited = queryBounds(map(partlyVisible));
  assert.deepEqual(limited, surrounding);
  assert.ok(limited[2] < 127.004 && limited[3] < 37.553);
});

test('transient disjoint or invalid horizon bounds still produce a valid nearby cap', () => {
  for (const bounds of [[130, 40, 131, 41], [NaN, 0, Infinity, 90]]) {
    const result = queryBounds(map(bounds));
    assert.ok(result.every(Number.isFinite));
    assert.ok(result[0] < center.lng && result[2] > center.lng && result[1] < center.lat && result[3] > center.lat);
    assert.ok(result[2] - result[0] < 0.007 && result[3] - result[1] < 0.0055);
  }
});

test('flight queries use a bounded aircraft focus despite remote, invalid or changing camera bounds', () => {
  const current = map([125, 35, 129, 40], 15, 80);
  setFlightQueryFocus(current, { lon: 126.83, lat: 37.56 });
  const result = queryBounds(current);
  const lat = (result[1] + result[3]) / 2;
  assert.ok(Math.abs((result[2] - result[0]) * metresPerDegree * Math.cos(lat * Math.PI / 180) - 1600) < 1e-6);
  assert.ok(Math.abs((result[3] - result[1]) * metresPerDegree - 1600) < 1e-6);
  assert.ok(Math.abs((result[0] + result[2]) / 2 - 126.83) < 0.0006);
  current.getBounds = () => { throw new Error('flight must not query the camera horizon'); };
  current.getCenter = () => { throw new Error('flight must not query the camera target'); };
  assert.deepEqual(queryBounds(current), result);
});

test('flight focus is map-specific, copied, snapped to 100m and removable', () => {
  const bounds = [126, 37, 128, 38], a = map(bounds, 15, 80), b = map(bounds, 15, 80);
  const focus = { lon: 127, lat: 37.5 };
  setFlightQueryFocus(a, focus);
  const first = queryBounds(a);
  focus.lon = 128;
  assert.deepEqual(queryBounds(a), first);
  assert.deepEqual(queryBounds(b), bounds);
  setFlightQueryFocus(a, { lon: 127.0001, lat: 37.5001 });
  assert.deepEqual(queryBounds(a), first);
  setFlightQueryFocus(a, { lon: 127.0012, lat: 37.5 });
  const moved = queryBounds(a);
  assert.ok(Math.abs(((moved[0] + moved[2]) - (first[0] + first[2])) / 2 * metresPerDegree * Math.cos(37.566 * Math.PI / 180) - 100) < 1e-6);
  setFlightQueryFocus(a, null);
  assert.deepEqual(queryBounds(a), bounds);
  a.getZoom = () => 22; a.getPitch = () => 85;
  assert.deepEqual(queryBounds(a), queryBounds(map(bounds)));
  setFlightQueryFocus(a, { lon: NaN, lat: 37.5 });
  assert.ok(queryBounds(a).every(Number.isFinite));
});

test('flight model work coalesces at 1Hz, tracks aircraft rather than target, and cancels on exit/dispose', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let now = 0;
  t.mock.method(performance, 'now', () => now);
  const current = map([120, 30, 135, 45], 16, 80);
  current.off = () => {}; current.getLayer = () => null; current.triggerRepaint = () => {};
  const models = new CityModels(current);
  let loads = 0, terrain = 0;
  models.loadNearby = () => { loads++; return Promise.resolve(); };
  models.updateTerrain = () => { terrain++; };
  setFlightQueryFocus(current, { lon: 126.83, lat: 37.56 });
  models.onViewChanged({ flightView: true });
  const first = models.viewSnapshot();
  assert.ok(Math.abs(first.lon - 126.83) < 0.0006);
  assert.ok(first.east - first.west < 0.02);
  models.entries = [
    { asset: { id: 'aircraft-nearby', coordinate: { lon: 126.83, lat: 37.56 } }, error: null, ground: null, draws: 0, active: false },
    { asset: { id: 'camera-target', coordinate: { lon: center.lng, lat: center.lat } }, error: null, ground: null, draws: 0, active: false },
  ];
  assert.deepEqual(models.nearbyEntries().map(entry => entry.asset.id), ['aircraft-nearby']);
  setFlightQueryFocus(current, { lon: 126.84, lat: 37.56 });
  for (now = 10; now < 1000; now += 10) models.onViewChanged({ flightView: true });
  now = 999;
  assert.equal(models.viewSnapshot(), first);
  assert.equal(loads, 1); assert.equal(terrain, 1);
  now = 1000; t.mock.timers.tick(1000);
  assert.equal(loads, 2); assert.equal(terrain, 2);
  assert.ok(models.viewSnapshot().lon > first.lon);
  now = 1100; models.onViewChanged({ flightView: true });
  setFlightQueryFocus(current, null);
  models.onViewChanged({});
  assert.equal(loads, 3);
  assert.equal(models.viewSnapshot().lon, center.lng);
  now = 3000; t.mock.timers.tick(2000);
  assert.equal(loads, 3, 'exit cancels the pending flight update');
  models.onViewChanged({ flightView: true });
  now = 3100; models.onViewChanged({ flightView: true });
  models.destroy();
  const before = loads;
  now = 5000; t.mock.timers.tick(2000);
  assert.equal(loads, before, 'disposal cancels pending flight work');
});
