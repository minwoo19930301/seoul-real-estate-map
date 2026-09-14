#!/usr/bin/env node
/**
 * Run from the project root: node scripts/measure-map-data.mjs
 * Requires the prepared local SQLite DBs, .venv, dependencies, and a Node
 * version supporting TypeScript stripping (the same as the Node tests).
 * Reads local APIs directly. No server, browser, network or large fixture files.
 */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Buildings } from '../src/buildings.ts';
import { Roads } from '../src/roads.ts';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outputPath = join(root, 'docs/MAP_RENDER_MEASUREMENTS.json');
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const jsonBytes = value => Buffer.byteLength(JSON.stringify(value));
const sourceFiles = [
  'scripts/measure-map-data.mjs', 'src/buildings.ts', 'src/roads.ts',
  'server/buildings.py', 'server/roads.py',
];

// SQLite API connections use mode=ro. Samples remain in the child process and
// this process's memory; the artifact stores counts, hashes and measurements.
const python = String.raw`
import hashlib, json, platform
from pathlib import Path
from server.buildings import BuildingsAPI
from server.roads import RoadsAPI

def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}

paths = [Path('data/buildings.sqlite'), Path('data/roads.sqlite')]
databases = [fingerprint(path) for path in paths]
buildings, roads = BuildingsAPI(paths[0]), RoadsAPI(paths[1])
samples = []
for area, lon, lat in [('sangdo', 126.948, 37.501), ('namsan', 126.99, 37.551), ('seoul_forest', 127.041, 37.544)]:
    bounds = [lon - .009, lat - .0072, lon + .009, lat + .0072]
    bbox = ','.join(str(value) for value in bounds)
    samples.append({'area': area, 'bounds': bounds, 'query_zoom': 16,
                    'buildings': buildings.features(bbox, '16'),
                    'roads': roads.features(bbox, '16')})
print(json.dumps({'python': platform.python_version(), 'databases': databases, 'samples': samples}, ensure_ascii=False, separators=(',', ':')))
`;
const query = JSON.parse(execFileSync(join(root, '.venv/bin/python'), ['-c', python], {
  cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
}));

const previousDocument = globalThis.document;
globalThis.document = { querySelector: () => ({ addEventListener() {} }) };
const results = [];
try {
  for (const sample of query.samples) {
    const { area, bounds, query_zoom, buildings: rawBuildings, roads: rawRoads } = sample;
    for (const data of [rawBuildings, rawRoads]) {
      assert.equal(data.type, 'FeatureCollection');
      assert.notEqual(data.metadata?.available, false, `${area}: source unavailable`);
      assert.ok(data.features.length > 0, `${area}: expected a populated local sample`);
    }
    const rendered = new Map();
    const map = {
      getSource: id => ({ setData: value => rendered.set(id, value) }),
      getZoom: () => query_zoom,
    };
    const buildings = new Buildings(map, () => {});
    buildings.data = rawBuildings;
    buildings.renderData();
    const roads = new Roads(map);
    roads.data = rawRoads;
    roads.update();

    // Before the render-property reduction, buildings submitted full properties
    // plus a normalized label; roads submitted the full API collection.
    const oldBuildings = {
      ...rawBuildings,
      features: rawBuildings.features.map(feature => ({
        ...feature,
        properties: { ...feature.properties, _building_label: String(feature.properties?.name ?? '').trim() },
      })),
    };
    const measure = (raw, before, after, controller) => {
      assert.ok(after, 'The real controller must call GeoJSONSource.setData');
      assert.equal(after.features.length, raw.features.length);
      const sameGeometry = after.features.every((feature, i) => feature.geometry === raw.features[i].geometry);
      const rawRetained = controller.getData() === raw;
      assert.equal(sameGeometry, true, 'Every original geometry reference must survive');
      assert.equal(rawRetained, true, 'The controller must retain full raw inspection data');
      const beforeBytes = jsonBytes(before), afterBytes = jsonBytes(after);
      return {
        features: raw.features.length,
        source_truncated: raw.metadata?.truncated === true,
        before_bytes: beforeBytes, after_bytes: afterBytes,
        reduction_percent: +(100 * (1 - afterBytes / beforeBytes)).toFixed(2),
        same_geometry_references: sameGeometry,
        full_raw_collection_retained: rawRetained,
      };
    };
    results.push({
      area, bounds, query_zoom,
      sample_sha256: sha256(JSON.stringify({ buildings: rawBuildings, roads: rawRoads, bounds })),
      buildings: measure(rawBuildings, oldBuildings, rendered.get('building-data'), buildings),
      roads: measure(rawRoads, rawRoads, rendered.get('road-data'), roads),
    });
  }
} finally {
  if (previousDocument === undefined) delete globalThis.document;
  else globalThis.document = previousDocument;
}

const result = {
  schema_version: 1,
  measured_at: new Date().toISOString(),
  reproduction: 'node scripts/measure-map-data.mjs',
  runtime: { node: process.version, python: query.python },
  metric: 'UTF-8 JSON bytes submitted to GeoJSONSource.setData; not HTTP bytes, heap use, GPU cost, timing or browser FPS',
  method: 'Fresh read-only local Python API queries; real Buildings.renderData and Roads.update output captured without a map, server or network',
  baseline: 'Full building API collection with normalized _building_label added; full road API collection',
  sample_hash_format: 'SHA-256 of UTF-8 JSON.stringify({buildings: rawBuildings, roads: rawRoads, bounds}); property and feature order retained',
  source_databases: query.databases,
  source_files: sourceFiles.map(path => ({ path, sha256: sha256(readFileSync(join(root, path))) })),
  results,
};
writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`);
console.log(`Wrote docs/MAP_RENDER_MEASUREMENTS.json\n${JSON.stringify(results, null, 2)}`);
