import test from 'node:test';
import assert from 'node:assert/strict';
import { Buildings } from '../src/buildings.ts';

const settle = () => new Promise(resolve => setImmediate(resolve));
function harness(t, initialZoom = 17, initialPitch = 58) {
  const original = Object.fromEntries(['document', 'fetch', 'setTimeout', 'clearTimeout'].map(key => [key, globalThis[key]]));
  t.after(() => { for (const [key, value] of Object.entries(original)) if (value === undefined) delete globalThis[key]; else globalThis[key] = value; });
  const nodes = new Map(), layers = new Map(), sources = new Map(), timers = new Map();
  const calls = { paint: [], layout: [], filter: [], data: [] };
  let zoom = initialZoom, pitch = initialPitch, timerId = 0;
  globalThis.document = { querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, { checked: selector !== '#apartments-only', textContent: '', addEventListener() {} });
    return nodes.get(selector);
  } };
  globalThis.setTimeout = fn => { const id = ++timerId; timers.set(id, fn); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  const input = { type: 'FeatureCollection', metadata: { available: true, truncated: false }, features: [
    { type: 'Feature', id: 'unknown', geometry: { type: 'Polygon', coordinates: [[[127, 37.55], [127.001, 37.55], [127.001, 37.551], [127, 37.55]]] }, properties: { id: 'unknown', kind: 'building', name: null, height_status: 'missing', height_m: null, min_height_m: null, extrude: false, is_apartment: false } },
    { type: 'Feature', id: 'known', geometry: { type: 'Polygon', coordinates: [[[127.002, 37.55], [127.003, 37.55], [127.003, 37.551], [127.002, 37.55]]] }, properties: { id: 'known', kind: 'building', name: '원본 이름', height_status: 'reported', height_m: 21.5, min_height_m: 0, extrude: true, is_apartment: true } },
  ] };
  globalThis.fetch = async url => new Response(JSON.stringify(url.endsWith('/meta') ? { available: true, total_count: 2, reported_count: 1 } : input));
  const map = {
    addSource: (id, definition) => sources.set(id, { data: definition.data, setData(data) { this.data = data; calls.data.push(data); } }),
    getSource: id => sources.get(id),
    addLayer: layer => layers.set(layer.id, structuredClone(layer)),
    setPaintProperty(id, key, value) { layers.get(id).paint[key] = value; calls.paint.push([id, key, value]); },
    setLayoutProperty(id, key, value) { (layers.get(id).layout ??= {})[key] = value; calls.layout.push([id, key, value]); },
    setFilter(id, value) { layers.get(id).filter = value; calls.filter.push([id, value]); },
    getZoom: () => zoom, getPitch: () => pitch, getCenter: () => ({ lng: 127, lat: 37.55 }),
    getBounds: () => ({ getWest: () => 126.99, getSouth: () => 37.54, getEast: () => 127.01, getNorth: () => 37.56 }),
  };
  const buildings = new Buildings(map, () => {});
  buildings.setMode(true); buildings.init();
  return { buildings, nodes, layers, sources, calls, timers, setView: (z, p) => { zoom = z; pitch = p; },
    visible: id => layers.get(id).layout.visibility, paint: () => layers.get('building-footprints').paint };
}

test('moveend scheduling removes close-view boundaries while preserving missing footprints and original heights', async t => {
  const h = harness(t); await settle();
  const raw = h.buildings.getData(), before = structuredClone(raw);
  const solidPaint = structuredClone(h.layers.get('building-solids').paint);
  const footprintFilter = structuredClone(h.layers.get('building-footprints').filter);
  const dataCalls = h.calls.data.length;
  assert.equal(h.paint()['fill-opacity'], 0.42); assert.equal(h.visible('building-outlines'), 'visible');
  h.setView(22, 82); h.buildings.schedule();
  assert.equal(h.visible('building-outlines'), 'none');
  assert.equal(h.visible('building-footprints'), 'visible'); assert.equal(h.visible('building-solids'), 'visible');
  assert.equal(h.paint()['fill-opacity'], 0.10); assert.equal(h.paint()['fill-antialias'], false);
  assert.deepEqual(h.layers.get('building-footprints').filter, footprintFilter);
  assert.deepEqual(h.layers.get('building-solids').paint, solidPaint);
  assert.equal(h.buildings.getData(), raw); assert.deepEqual(raw, before);
  assert.equal(h.calls.data.length, dataCalls, 'A view-style transition must not resend geometry');
  assert.equal(h.sources.get('building-data').data.features[0].geometry, raw.features[0].geometry);
});

test('unchanged close views do not repeat paint/layout/filter mutations and leaving restores normal style', async t => {
  const h = harness(t); await settle();
  h.setView(19, 75); h.buildings.schedule();
  const counts = [h.calls.paint.length, h.calls.layout.length, h.calls.filter.length];
  for (let i = 0; i < 20; i++) { h.buildings.schedule(); h.buildings.setLabelsVisible(true); }
  assert.deepEqual([h.calls.paint.length, h.calls.layout.length, h.calls.filter.length], counts);
  assert.equal(h.timers.size, 1, 'Move scheduling retains only its latest data timer');
  h.setView(22, 74.99); h.buildings.schedule();
  assert.equal(h.visible('building-outlines'), 'visible');
  assert.equal(h.paint()['fill-opacity'], 0.42); assert.equal(h.paint()['fill-antialias'], true);
  assert.equal(h.calls.paint.length, counts[0] + 2);
  assert.equal(h.nodes.get('#toggle-buildings').checked, true);
  h.setView(18.99, 85); h.buildings.schedule();
  assert.equal(h.calls.paint.length, counts[0] + 2);
});

test('initial close view and hidden-building preference remain correct across zoom transitions', async t => {
  const h = harness(t, 22, 82); await settle();
  assert.equal(h.paint()['fill-opacity'], 0.10); assert.equal(h.paint()['fill-antialias'], false);
  assert.equal(h.visible('building-outlines'), 'none');
  h.buildings.setLabelsVisible(false);
  h.buildings.setVisible(false);
  h.setView(17, 58); h.buildings.schedule();
  for (const id of ['building-footprints', 'building-outlines', 'building-solids', 'building-labels']) assert.equal(h.visible(id), 'none');
  assert.equal(h.paint()['fill-opacity'], 0.42); assert.equal(h.paint()['fill-antialias'], true);
  assert.equal(h.nodes.get('#toggle-buildings').checked, false);
  assert.equal(h.nodes.get('#toggle-building-labels').checked, false);
  h.buildings.setVisible(true); await settle();
  assert.equal(h.visible('building-outlines'), 'visible');
  assert.equal(h.visible('building-labels'), 'none');
  assert.equal(h.buildings.getData().features[0].properties.height_m, null);
  assert.equal(h.buildings.getData().features[1].properties.height_m, 21.5);
});
