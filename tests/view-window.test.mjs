import test from 'node:test';
import assert from 'node:assert/strict';
import { queryBounds, isCloseView } from '../src/view-window.ts';

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
