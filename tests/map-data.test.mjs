import test from 'node:test';
import assert from 'node:assert/strict';
import { Buildings } from '../src/buildings.ts';
import { Roads } from '../src/roads.ts';
import { createPropertyExpression, latest, validateStyleMin } from '@maplibre/maplibre-gl-style-spec';

const tick = () => new Promise(resolve => setImmediate(resolve));
const building = (id = 'building-1') => ({ type: 'FeatureCollection', metadata: { available: true, truncated: false }, features: [{
  type: 'Feature', id, geometry: { type: 'Polygon', coordinates: [[[126.96, 37.55], [126.961, 37.55], [126.961, 37.551], [126.96, 37.55]]] },
  properties: { id, name: '원본 이름', height_status: 'reported', height_m: 33.5, min_height_m: 0,
    is_apartment: true, extrude: true, kind: 'building', footprint_area_m2: 109.25, num_floors: 10,
    geometry_source: 'Original source', height_source: 'Unverified record', parent_id: 'source-parent',
    source_detail: { retained: true }, classification_source: 'source' },
}] });
const roads = () => ({ type: 'FeatureCollection', metadata: { available: true, truncated: false, counts: { roadway: 1 } }, features: [{
  type: 'Feature', id: 'osm:way:1', geometry: { type: 'LineString', coordinates: [[126.95, 37.54], [126.97, 37.56]] },
  properties: { id: 'osm:way:1', category: 'roadway', subtype: 'road', restricted: false, highway: 'primary', name: '원본 도로', surface: 'asphalt' },
}] });

function harness(t, kind, response = kind === 'building' ? building() : roads()) {
  const previousDocument = globalThis.document, previousFetch = globalThis.fetch;
  t.after(() => { globalThis.document = previousDocument; globalThis.fetch = previousFetch; });
  const nodes = new Map();
  globalThis.document = { querySelector: selector => {
    if (!nodes.has(selector)) nodes.set(selector, { checked: selector !== '#apartments-only', disabled: false,
      textContent: '', innerHTML: '', hidden: true, value: '', addEventListener() {}, scrollIntoView() {} });
    return nodes.get(selector);
  } };
  const calls = { layout: [], filter: [], data: [], fetch: [], status: [] };
  const sources = new Map(), layers = new Map();
  let bounds = [126.95, 37.54, 126.98, 37.57], zoom = 16, pitch = 0, supplied = response;
  const map = {
    addSource: (id, definition) => sources.set(id, { data: definition.data, setData(data) { this.data = data; calls.data.push({ id, data }); } }),
    getSource: id => sources.get(id),
    addLayer: layer => layers.set(layer.id, layer), getLayer: id => layers.get(id),
    setLayoutProperty: (...args) => calls.layout.push(args), setFilter: (...args) => calls.filter.push(args),
    getBounds: () => ({ getWest: () => bounds[0], getSouth: () => bounds[1], getEast: () => bounds[2], getNorth: () => bounds[3] }),
    getZoom: () => zoom, getPitch: () => pitch, getCenter: () => ({ lng: 126.965, lat: 37.555 }), setFeatureState() {}, queryRenderedFeatures: () => [], removeLayer() {}, removeSource() {},
  };
  globalThis.fetch = async url => {
    calls.fetch.push(url);
    if (url.endsWith('/meta')) return new Response(JSON.stringify({ available: true, total_count: 1, reported_count: 1 }));
    if (/\/api\/buildings\/[^?]+$/.test(url)) throw new Error('Detail deliberately unavailable');
    return new Response(JSON.stringify(supplied));
  };
  const controller = kind === 'building' ? new Buildings(map, () => {}) : new Roads(map, text => calls.status.push(text));
  return { controller, map, calls, sources, layers, nodes,
    queries: () => calls.fetch.filter(url => url.includes('?')),
    setView: (value, level = zoom, angle = pitch) => { bounds = value; zoom = level; pitch = angle; }, setResponse: value => { supplied = value; } };
}

test('building render payload is lean while coordinates, raw data and inspection remain original', async t => {
  const h = harness(t, 'building'); h.controller.init(); await tick();
  const original = h.controller.getData().features[0];
  const rendered = h.sources.get('building-data').data.features[0];
  assert.equal(rendered.geometry, original.geometry);
  assert.deepEqual(original.properties.source_detail, { retained: true });
  assert.equal(original.properties.footprint_area_m2, 109.25);
  assert.equal(rendered.properties.footprint_area_m2, undefined);
  assert.equal(rendered.properties.source_detail, undefined);
  assert.equal(rendered.properties._building_label, '원본 이름');
  assert.equal(rendered.properties.parent_id, original.properties.parent_id);
  assert.equal(Object.keys(rendered.properties).length, 9);
  const displayed = [];
  h.controller.showDetail = props => displayed.push(props);
  await h.controller.inspect(rendered, [126.96, 37.55]);
  assert.equal(displayed[0], original.properties);
  assert.equal(displayed[0].height_m, 33.5);
});

test('unchanged building visibility, model IDs and cached data do not repeat map mutations', async t => {
  const h = harness(t, 'building'); h.controller.init(); await tick();
  h.controller.setMode(true); h.controller.setModelFootprints(['B', 'A']);
  const before = [h.calls.layout.length, h.calls.filter.length, h.calls.data.length];
  for (let i = 0; i < 10; i++) {
    h.controller.setMode(true); h.controller.setModelFootprints(['A', 'B', 'A']);
    h.controller.setLabelsVisible(true); h.controller.setVisible(true);
  }
  await tick();
  assert.deepEqual([h.calls.layout.length, h.calls.filter.length, h.calls.data.length], before);
  assert.equal(h.queries().length, 1);
  h.controller.setLabelsVisible(false);
  assert.equal(h.calls.layout.length, before[0] + 1);
  assert.equal(h.calls.filter.length, before[1]);
});

test('complete building view covers zoomed-in data, but outside or truncated views refetch', async t => {
  const h = harness(t, 'building'); h.controller.init(); await tick();
  const original = h.controller.getData();
  h.setView([126.955, 37.545, 126.975, 37.565], 17.2); await h.controller.load();
  assert.equal(h.queries().length, 1); assert.equal(h.controller.getData(), original);
  assert.equal(h.calls.data.length, 1);
  assert.match(h.nodes.get('#building-status').textContent, /불러온 영역/);
  h.setView([126.94, 37.54, 126.98, 37.57]); await h.controller.load();
  assert.equal(h.queries().length, 2);
  const truncated = building(); truncated.metadata.truncated = true; h.setResponse(truncated);
  h.setView([126.94, 37.54, 126.99, 37.58]); await h.controller.load();
  h.setView([126.95, 37.55, 126.98, 37.57]); await h.controller.load();
  assert.equal(h.queries().length, 4);
});

test('unavailable building results are retried and repeated hidden clears are no-ops', async t => {
  const unavailable = building(); unavailable.metadata.available = false;
  const h = harness(t, 'building', unavailable); h.controller.init(); await tick();
  await h.controller.load(); assert.equal(h.queries().length, 2);
  h.controller.setVisible(false); const updates = h.calls.data.length;
  h.controller.setVisible(false); await h.controller.load();
  assert.equal(h.calls.data.length, updates); assert.equal(h.controller.getData().features.length, 0);
});

test('duplicate pending building queries share work and late replies cannot replace a new view', async t => {
  const h = harness(t, 'building'), pending = [];
  globalThis.fetch = async url => {
    if (url.endsWith('/meta')) return new Response('{}');
    h.calls.fetch.push(url);
    return new Promise(resolve => pending.push(data => resolve(new Response(JSON.stringify(data)))));
  };
  h.controller.init(); await h.controller.load(); await h.controller.load();
  assert.equal(pending.length, 1);
  h.setView([126.98, 37.54, 127.01, 37.57]); const newer = h.controller.load();
  assert.equal(pending.length, 2);
  pending[1](building('new')); await newer;
  pending[0](building('old')); await tick();
  assert.equal(h.controller.getData().features[0].id, 'new');
  assert.equal(h.calls.data.length, 1);
});

test('roadways use one pale pass and visibility changes keep original road data', async t => {
  const h = harness(t, 'road'); await h.controller.init();
  assert.equal(h.layers.has('roadway-casing'), false);
  const layer = h.layers.get('roadway-lines');
  const rgb = layer.paint['line-color'].slice(1).match(/../g).map(channel => parseInt(channel, 16));
  assert.ok(rgb.every(channel => channel >= 210), 'road tint must stay pale');
  assert.ok(layer.paint['line-opacity'] > 0.5 && layer.paint['line-opacity'] <= 1);
  const width = createPropertyExpression(layer.paint['line-width'], 'line-width', latest.paint_line['line-width']);
  assert.equal(width.result, 'success');
  assert.equal(width.value.evaluate({ zoom: 17 }), 7);
  assert.ok(width.value.evaluate({ zoom: 18.5 }) < 12);
  const raw = h.controller.getData().features[0], display = h.sources.get('road-data').data.features[0];
  assert.equal(display.geometry, raw.geometry); assert.equal(raw.properties.highway, 'primary');
  assert.equal(display.properties.name, undefined); assert.equal(raw.properties.name, '원본 도로');
  const before = [h.calls.layout.length, h.calls.data.length, h.calls.status.length];
  for (let i = 0; i < 10; i++) h.controller.setVisibility({ roadways: true, walkways: true, steps: true });
  assert.deepEqual([h.calls.layout.length, h.calls.data.length, h.calls.status.length], before);
  h.controller.setVisibility({ roadways: true, walkways: false, steps: true });
  await tick(); assert.equal(h.queries().length, 1); assert.equal(h.calls.data.length, before[1]);
});

test('road symbols remain bounded and continuous through extreme zoom without oversized dashes', async t => {
  const h = harness(t, 'road'); await h.controller.init();
  assert.deepEqual(validateStyleMin({ version: 8, sources: { 'road-data': { type: 'geojson', data: roads() } }, layers: [...h.layers.values()] }), []);
  for (const [id, maxWidth] of [['roadway-lines', 12], ['walkway-lines', 3], ['walkway-crossings', 3.5], ['walkway-steps', 3.5]]) {
    const layer = h.layers.get(id);
    const width = createPropertyExpression(h.layers.get(id).paint['line-width'], 'line-width', latest.paint_line['line-width']);
    assert.equal(width.result, 'success');
    let previous = width.value.evaluate({ zoom: 11 });
    for (let tick = 221; tick <= 500; tick++) {
      const zoom = tick / 20;
      const pixels = width.value.evaluate({ zoom });
      assert.ok(pixels > 0 && pixels <= maxWidth, `${id} z${zoom}: ${pixels}px`);
      assert.ok(pixels >= previous && pixels - previous <= 0.11, `${id}: abrupt zoom step at ${zoom}`);
      previous = pixels;
      const dash = layer.paint['line-dasharray'];
      if (dash) {
        assert.ok(dash.every(length => typeof length === 'number' && length > 0));
        assert.ok(Math.max(...dash) * pixels <= 6.1, `${id}: oversized dash at ${zoom}`);
      }
    }
    assert.equal(layer.layout['line-join'], 'round');
  }
});

test('entering street view replaces a broad cache with a bounded nearby query for buildings and roads', async t => {
  for (const kind of ['building', 'road']) {
    const h = harness(t, kind);
    await h.controller.init(); await tick();
    assert.equal(h.queries().length, 1);
    h.setView([126.5, 37.1, 127.5, 38], 22, 85);
    await h.controller.load();
    assert.equal(h.queries().length, 2, `${kind}: broad complete cache must not bypass close-view cap`);
    const bounds = new URL(h.queries()[1], 'http://test').searchParams.get('bbox').split(',').map(Number);
    assert.ok(bounds[2] - bounds[0] < 0.007 && bounds[3] - bounds[1] < 0.0055);
    await h.controller.load(); assert.equal(h.queries().length, 2);
    h.setView([126.95, 37.54, 126.98, 37.57], 18, 60);
    await h.controller.load(); assert.equal(h.queries().length, 3);
  }
});

test('road cache respects full coverage and source zoom thresholds', async t => {
  const h = harness(t, 'road'); h.setView([126.95, 37.54, 126.98, 37.57], 11.2); await h.controller.init();
  h.setView([126.955, 37.545, 126.975, 37.565], 12.8); await h.controller.load();
  assert.equal(h.queries().length, 1);
  h.setView([126.955, 37.545, 126.975, 37.565], 13); await h.controller.load();
  h.setView([126.955, 37.545, 126.975, 37.565], 14); await h.controller.load();
  assert.deepEqual(h.queries().map(url => new URL(url, 'http://test').searchParams.get('zoom')), ['11', '13', '14']);
  h.setView([126.956, 37.546, 126.974, 37.564], 17); await h.controller.load();
  assert.equal(h.queries().length, 3);
  h.setView([126.94, 37.54, 126.98, 37.57], 17); await h.controller.load();
  assert.equal(h.queries().length, 4);
});

test('truncated road data cannot cover a different view and cache expires', async t => {
  const data = roads(); data.metadata.truncated = true;
  const h = harness(t, 'road', data); await h.controller.init();
  await h.controller.load(); assert.equal(h.queries().length, 1);
  h.setView([126.955, 37.545, 126.975, 37.565]); await h.controller.load();
  assert.equal(h.queries().length, 2);
  h.controller.cachedAt = Date.now() - 61000; await h.controller.load();
  assert.equal(h.queries().length, 3);
});
