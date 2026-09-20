import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = name => fs.readFile(path.join(root, name));
const json = async name => JSON.parse(await read(name));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const hashPattern = /^[a-f0-9]{64}$/;
const sum = values => values.reduce((total, value) => total + value, 0);

function inspectGlb(bytes, id) {
  assert.ok(bytes.length >= 28, `${id}: truncated GLB`);
  assert.equal(bytes.readUInt32LE(0), 0x46546c67, `${id}: GLB magic`);
  assert.equal(bytes.readUInt32LE(4), 2, `${id}: GLB version`);
  assert.equal(bytes.readUInt32LE(8), bytes.length, `${id}: GLB length`);
  const jsonLength = bytes.readUInt32LE(12);
  assert.equal(bytes.readUInt32LE(16), 0x4e4f534a, `${id}: JSON chunk`);
  assert.ok(jsonLength > 0 && jsonLength % 4 === 0 && 28 + jsonLength <= bytes.length);
  const gltf = JSON.parse(bytes.subarray(20, 20 + jsonLength));
  const binaryStart = 28 + jsonLength, binaryLength = bytes.readUInt32LE(20 + jsonLength);
  assert.equal(bytes.readUInt32LE(24 + jsonLength), 0x004e4942, `${id}: binary chunk`);
  assert.equal(binaryStart + binaryLength, bytes.length, `${id}: complete binary chunk`);
  assert.ok(gltf.buffers.length === 1 && !gltf.buffers[0].uri);
  assert.ok(!gltf.images?.length && !gltf.textures?.length, `${id}: standalone geometric materials`);
  // The two exporters bake all transforms. Reject an unhandled transform rather
  // than comparing local accessor bounds to world-space manifest dimensions.
  for (const node of gltf.nodes) for (const key of ['matrix', 'translation', 'rotation', 'scale']) {
    assert.equal(node[key], undefined, `${id}: unexpected node ${key}`);
  }
  const sizes = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 };
  const readers = { 5121: 'readUInt8', 5123: 'readUInt16LE', 5125: 'readUInt32LE', 5126: 'readFloatLE' };
  const channels = { SCALAR: 1, VEC3: 3, VEC4: 4 };
  const accessor = index => {
    const a = gltf.accessors[index], view = gltf.bufferViews[a.bufferView];
    assert.ok(a && view && !a.sparse && view.buffer === 0, `${id}: accessor storage`);
    const size = sizes[a.componentType], width = channels[a.type];
    assert.ok(size && width && Number.isSafeInteger(a.count) && a.count > 0);
    const stride = view.byteStride ?? size * width;
    const relative = a.byteOffset ?? 0, offset = (view.byteOffset ?? 0) + relative;
    assert.ok(stride >= size * width && relative + (a.count - 1) * stride + size * width <= view.byteLength);
    assert.ok(offset + (a.count - 1) * stride + size * width <= binaryLength);
    const divisor = a.normalized ? ({ 5121: 255, 5123: 65535 }[a.componentType] ?? 1) : 1;
    return { ...a, width, value: (i, c = 0) => bytes[readers[a.componentType]](binaryStart + offset + i * stride + c * size) / divisor };
  };
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  let triangles = 0, vertices = 0, primitives = 0;
  const colours = new Set(), bridgeVertices = [];
  for (const mesh of gltf.meshes) for (const primitive of mesh.primitives) {
    primitives++;
    assert.equal(primitive.mode ?? 4, 4, `${id}: triangle primitive`);
    const p = accessor(primitive.attributes.POSITION), n = accessor(primitive.attributes.NORMAL);
    assert.equal(p.type, 'VEC3'); assert.equal(n.type, 'VEC3'); assert.equal(p.count, n.count);
    const c = primitive.attributes.COLOR_0 === undefined ? null : accessor(primitive.attributes.COLOR_0);
    if (c) assert.equal(c.count, p.count);
    const indices = primitive.indices === undefined ? null : accessor(primitive.indices);
    const elements = indices?.count ?? p.count;
    assert.equal(elements % 3, 0, `${id}: complete triangles`);
    triangles += elements / 3; vertices += p.count;
    for (let i = 0; i < p.count; i++) {
      const xyz = [p.value(i, 0), p.value(i, 1), p.value(i, 2)];
      for (let axis = 0; axis < 3; axis++) {
        assert.ok(Number.isFinite(xyz[axis]), `${id}: finite position`);
        min[axis] = Math.min(min[axis], xyz[axis]); max[axis] = Math.max(max[axis], xyz[axis]);
      }
      const length = Math.hypot(n.value(i, 0), n.value(i, 1), n.value(i, 2));
      assert.ok(Number.isFinite(length) && Math.abs(length - 1) < .01, `${id}: unit normal`);
      const rgb = c ? [c.value(i, 0), c.value(i, 1), c.value(i, 2)] : null;
      if (rgb) {
        assert.ok(rgb.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
        colours.add(rgb.map(value => Math.round(value * 255)).join(','));
      }
      if (id === 'maple-xi-210') bridgeVertices.push({ xyz, rgb });
    }
    if (indices) for (let i = 0; i < indices.count; i++) {
      const value = indices.value(i);
      assert.ok(Number.isSafeInteger(value) && value >= 0 && value < p.count, `${id}: index bounds`);
    }
  }
  assert.ok(Math.abs(min[1]) < .01, `${id}: local floor zero`);
  assert.ok(triangles >= 300 && primitives > 0 && vertices > 0, `${id}: authored geometry rather than a box`);
  return { gltf, min, max, dimensions: max.map((value, i) => value - min[i]), triangles, primitives,
    materials: gltf.materials.length, vertices, colourCount: colours.size, bridgeVertices };
}

let inspection;
function inspectPublished() {
  return inspection ??= (async () => {
    const [manifest, integration, flight, maple] = await Promise.all([
      json('public/models/reference-manifest.json'), json('docs/REFERENCE_MODEL_INTEGRATION.json'),
      json('docs/FLIGHT_ADAPTED_EXPORT.json'), json('docs/MAPLE_XI_MODEL_RECIPE.json'),
    ]);
    const evidence = new Map(integration.assets.map(asset => [asset.id, asset]));
    const results = new Map();
    for (const asset of manifest.assets) {
      assert.match(asset.model, /^(?:reference-flight|maple-xi)\/[a-z0-9-]+\.glb$/);
      const bytes = await read('public/models/' + asset.model);
      assert.equal(sha(bytes), asset.sha256, `${asset.id}: published SHA`);
      const actual = inspectGlb(bytes, asset.id), proof = evidence.get(asset.id);
      assert.ok(proof, `${asset.id}: integration evidence`);
      assert.equal(bytes.length, proof.bytes, `${asset.id}: bytes`);
      assert.equal(actual.triangles, proof.triangles, `${asset.id}: triangle count`);
      assert.equal(actual.materials, proof.materials, `${asset.id}: materials`);
      assert.ok(actual.dimensions.every((value, i) => Number.isFinite(value) && value > 0 && Math.abs(value - asset.dimensions[i]) < .01), `${asset.id}: physical dimensions`);
      results.set(asset.id, { asset, proof, actual, bytes: bytes.length });
    }
    return { manifest, integration, flight, maple, results };
  })();
}

test('all 125 published reference GLBs match hashes, bounds, normals and geometry evidence', async () => {
  const { manifest, integration, results } = await inspectPublished();
  assert.equal(manifest.assets.length, 125); assert.equal(results.size, 125);
  assert.equal(integration.models, 125); assert.equal(integration.flightModels, 94); assert.equal(integration.mapleModels, 31);
  assert.equal(integration.preservedCatalogModels, 113123); assert.equal(integration.sourceCatalogUnchanged, true);
  assert.equal(sum([...results.values()].map(row => row.bytes)), integration.bytes);
  assert.equal(sum([...results.values()].map(row => row.actual.triangles)), integration.triangles);
});

test('94 Flight assets preserve source PBR materials and detail through 38 explicit scale adaptations', async () => {
  const { manifest, flight, results } = await inspectPublished();
  assert.equal(flight.assets.length, 94); assert.equal(flight.failures.length, 0);
  assert.equal(manifest.sourceRevision, flight.sourceRevision);
  assert.equal(new Set(flight.assets.map(asset => asset.id)).size, 94);
  assert.equal(flight.assets.filter(asset => asset.adaptationRecipe.changed).length, 38);
  assert.equal(flight.assets.filter(asset => !asset.adaptationRecipe.changed).length, 56);
  for (const source of flight.assets) {
    const { asset, actual } = results.get('reference-flight-' + source.id);
    assert.equal(asset.sha256, source.sha256, `${source.id}: adapted GLB copied intact`);
    assert.equal(asset.sourceRecord.sourceFileSha256, source.sourceFileSha256);
    assert.match(source.sourceFileSha256, hashPattern); assert.match(source.pristineSource.glbSha256, hashPattern);
    const materialHash = sha(JSON.stringify(actual.gltf.materials));
    assert.equal(materialHash, source.adaptationIntegrity.materialsSha256);
    assert.equal(actual.triangles, source.exportedStats.triangles);
    if (['tower-palace', 'garden-five'].includes(source.id)) {
      const integrity = source.adaptationIntegrity, recipe = source.adaptationRecipe;
      const tower = source.id === 'tower-palace';
      assert.equal(integrity.preservationMode, tower ? 'complete-seven-towers-with-documented-site-removal' : 'complete-four-life-halls-with-documented-unverified-site-removal');
      assert.equal(sha(JSON.stringify(integrity.pristineMaterialDefinitions)), integrity.pristineMaterialsSha256);
      assert.equal(integrity.retainedMaterialMap.length, actual.gltf.materials.length);
      for (const entry of integrity.retainedMaterialMap) {
        assert.deepEqual(actual.gltf.materials[entry.adaptedIndex], integrity.pristineMaterialDefinitions[entry.pristineIndex]);
        assert.equal(sha(JSON.stringify(actual.gltf.materials[entry.adaptedIndex])), entry.sha256);
      }
      assert.equal(recipe.removedDecorativeMeshes, tower ? 105 : 43);
      assert.equal(recipe.removedDecorativeTriangles, tower ? 5804 : 1484);
      assert.equal(integrity.removedTriangles, recipe.removedDecorativeTriangles);
      assert.equal(actual.triangles + integrity.removedTriangles, source.pristineSource.sourceStats.triangles);
      const components = recipe.componentRecipe.components;
      assert.deepEqual(components.map(component => component.name).sort(), tower ? ['A', 'B', 'C', 'D', 'E', 'F', 'G'] : ['패션관', '영관', '리빙관', '테크노관'].sort());
      assert.equal(sum(components.map(component => component.sourceComponentGeometry.triangles)), actual.triangles);
      assert.equal(new Set(components.map(component => component.footprintId)).size, tower ? 7 : 4);
      assert.equal(recipe.componentRecipe.landscapeObjects, 0);
      assert.ok(recipe.removalReason.includes('pristine GLB stays unchanged'));
      if (!tower) {
        assert.ok(asset.dimensions[0] < 250 && asset.dimensions[2] < 250, 'Life halls no longer span neighbouring apartment blocks');
        assert.ok(recipe.omittedSourceComponents.includes('unverified fifth Tool/Works bar'));
        for (const component of components) assert.ok(component.widthScale > .9 && component.widthScale < 1.6);
      }
    } else {
      assert.equal(materialHash, source.adaptationIntegrity.pristineMaterialsSha256, `${source.id}: original PBR colours preserved`);
      assert.equal(source.adaptationIntegrity.preservedTriangleCount, true);
    }
    assert.ok(Math.abs(asset.groundOffsetM - source.sourceGroundOffsetM) < 1e-6);
    assert.equal(source.footprintFitVerified, false, `${source.id}: export does not imply surveyed fit`);
    if (!source.adaptationRecipe.changed) assert.equal(source.sha256, source.pristineSource.glbSha256);
  }
  for (const [id, count] of [['tower-palace', 7], ['garden-five', 4], ['parc1-ifc', 12], ['samsung-town', 5], ['walkerhill', 9]]) {
    const source = flight.assets.find(asset => asset.id === id);
    assert.equal(source.adaptationRecipe.kind, 'component-width-and-centre-spacing');
    assert.equal(source.adaptationRecipe.componentRecipe.components.length, count);
  }
});

test('Maple Xi has 29 individually traced housing models, two ancillary models and a geometric 210–211 skybridge', async () => {
  const { maple, results } = await inspectPublished();
  const expectedHousing = [...Array.from({ length: 14 }, (_, i) => 101 + i), ...Array.from({ length: 15 }, (_, i) => 201 + i)];
  assert.equal(maple.residentialBuildingCount, 29); assert.equal(maple.ancillaryBuildingCount, 2);
  assert.equal(maple.assets.length, 31);
  assert.deepEqual(maple.assets.filter(asset => Number.isInteger(asset.recipe.dong)).map(asset => asset.recipe.dong).sort((a, b) => a - b), expectedHousing);
  assert.deepEqual(maple.assets.filter(asset => asset.recipe.residential === false).map(asset => asset.id).sort(), ['maple-xi-kindergarten', 'maple-xi-maple-road']);
  assert.equal(maple.imagesRedistributed, false);
  assert.ok(maple.sources.some(source => source.url.startsWith('https://www.xi.co.kr/') && source.kind.includes('photo')));
  for (const source of maple.assets) {
    const { asset, actual } = results.get(source.id);
    assert.equal(asset.sha256, source.sha256); assert.equal(actual.triangles, source.triangles);
    assert.equal(actual.colourCount >= 5, true, `${source.id}: geometric facade colours retained`);
    if (source.recipe.dong) {
      assert.ok(actual.triangles >= 5000, `${source.id}: individually detailed housing`);
      assert.ok(source.recipe.groundFootprintPixelTrace.length >= 4);
      assert.equal(source.heightEstimated, true);
      assert.equal(source.recipe.floorCountVerified, [210, 211].includes(source.recipe.dong));
    }
  }
  assert.equal(maple.skybridgeAttachedTo, 'maple-xi-210');
  const source = maple.assets.find(asset => asset.id === maple.skybridgeAttachedTo);
  assert.ok(source.recipe.features.some(feature => /skybridge.*210.*211/i.test(feature)));
  assert.equal(source.recipe.floorCountVerified, true); assert.equal(source.recipe.floorsEstimate, 29);
  const vertices = results.get(source.id).actual.bridgeVertices;
  const roof = source.recipe.mainRoofHeightEstimateM;
  const middle = vertices.filter(({ xyz }) => xyz[1] >= 10 && xyz[1] <= roof * .75);
  const high = vertices.filter(({ xyz }) => xyz[1] >= roof - 4.6 && xyz[1] <= roof + .3);
  const extent = (rows, axis) => rows.reduce((range, { xyz }) => [Math.min(range[0], xyz[axis]), Math.max(range[1], xyz[axis])], [Infinity, -Infinity]);
  const bodyX = extent(middle, 0), bridgeX = extent(high, 0);
  assert.ok(bridgeX[1] - bridgeX[0] > (bodyX[1] - bodyX[0]) * 1.5, '29F bridge extends well beyond the actual middle-storey tower width');
  assert.ok(high.some(({ xyz, rgb }) => (xyz[0] < bodyX[0] - 3 || xyz[0] > bodyX[1] + 3)
    && rgb && rgb[2] > rgb[0] + .08 && rgb[1] > rgb[0] + .05), 'outboard skybridge has actual blue-green glazing vertices');
  assert.equal(maple.assets.find(asset => asset.id === 'maple-xi-maple-road').recipe.distinguishedFromSkybridge, true);
});

test('reference replacement targets never replace each other and footprint claims have one owner', async () => {
  const { manifest, results } = await inspectPublished();
  const referenceIds = new Set(manifest.assets.map(asset => asset.id));
  const footprints = new Map(), replacements = new Map();
  const preservedOriginals = new Set(['sixtythree', 'lotte', 'nseoul', 'coex', 'gyeongbokgung']);
  for (const asset of manifest.assets) {
    assert.ok(Array.isArray(asset.footprintIds) && Array.isArray(asset.supersedes));
    assert.equal(new Set(asset.footprintIds).size, asset.footprintIds.length);
    assert.equal(new Set(asset.supersedes).size, asset.supersedes.length);
    assert.deepEqual(asset.supersedes, results.get(asset.id).proof.supersedes);
    for (const id of asset.footprintIds) {
      assert.ok(typeof id === 'string' && id.length > 0);
      assert.ok(!footprints.has(id), `${id}: footprint claimed by ${footprints.get(id)} and ${asset.id}`);
      footprints.set(id, asset.id);
    }
    for (const id of asset.supersedes) {
      assert.ok(!referenceIds.has(id) && !preservedOriginals.has(id), `${asset.id}: protected/reference replacement ${id}`);
      assert.ok(!replacements.has(id), `${id}: generic model has two replacements`);
      replacements.set(id, asset.id);
    }
  }
  assert.ok(footprints.size > 0 && replacements.size > 0, 'geometric replacement evidence is present');
});

test('Seoul City Hall explicitly replaces the six source-linked Seoul Library parts', async () => {
  const { results } = await inspectPublished();
  const { asset, proof } = results.get('reference-flight-seoul-city-hall');
  const parent = '93725b2d-b39e-490f-bc2e-77536fc0d0c4';
  const children = [
    '65353666-6637-3832-B737-653535376535', '61663761-3634-3437-B130-396663306134',
    '66386562-6237-3130-B832-613137653632', '64653532-3632-3162-A430-656635303463',
    '39366536-6530-3761-A336-633966663466', '34396137-6165-3238-B830-313064633537',
  ];
  assert.ok(asset.footprintIds.includes(parent));
  assert.ok(asset.supersedes.includes('civic-' + parent));
  assert.equal(asset.placementReview.explicitBuildingPartParentId, parent);
  for (const child of children) {
    assert.ok(asset.footprintIds.includes(child), `${child}: original solid is suppressed with the authored library`);
    const identity = proof.explicitIdentityMatches.find(match => match.id === child);
    assert.equal(identity?.parentId, parent, `${child}: source parent relation recorded`);
    assert.match(identity.basis, /not a measured footprint fit/);
  }
});

test('reviewed building identities and their source descendants survive partial geometric coverage', async () => {
  const { results } = await inspectPublished();
  const placements = await json('scripts/reference_placements.json');
  for (const [key, placement] of Object.entries(placements)) {
    const result = results.get('reference-flight-' + key);
    if (!result) continue;
    const { asset, proof } = result;
    for (const id of placement.explicitFootprintIds ?? []) {
      assert.ok(asset.footprintIds.includes(id), `${key}: reviewed same-building identity ${id}`);
      assert.ok(proof.explicitIdentityMatches.some(match => match.id === id));
    }
    for (const name of placement.reviewedSourceBuildingNames ?? []) {
      assert.ok(proof.explicitIdentityMatches.some(match => match.name === name), `${key}: reviewed source name ${name}`);
    }
    for (const id of placement.excludedFootprintIds ?? []) {
      assert.ok(!asset.footprintIds.includes(id), `${key}: unrelated neighbour stays visible`);
    }
    for (const match of proof.descendantIdentityMatches ?? []) {
      assert.ok(asset.footprintIds.includes(match.id));
      assert.ok(asset.footprintIds.includes(match.parentId), `${key}: descendant has a claimed source parent`);
    }
    assert.equal(proof.descendantOwnershipConflicts?.length ?? 0, 0, `${key}: no ambiguous descendant owners`);
  }
  for (const [key, id] of [
    ['gfc', '8c853160-e816-4fa5-9bc8-37d2a4902c39'],
    ['technomart', '16db731d-41af-45e1-9faa-c7c2febc6584'],
    ['central-city', 'bf07fa32-2bb1-45f4-95d9-eb4d863f0c34'],
    ['myeongdong-cathedral', '2723fab9-38dc-4308-830a-748355caca48'],
    ['national-assembly', '34656637-6534-3134-B038-306162663631'],
    ['dcube-city', '85db7664-8f97-4739-a0b9-e6d36c2be470'],
    ['dongnimmun', '820d282e-dcb9-4186-baff-425cb01fbe58'],
    ['cheongwadae', 'c4dcbadb-1db4-4f64-a89d-541529a582f4'],
    ['cheongwadae', '36633834-3566-3232-B535-373635303565'],
  ]) assert.ok(results.get('reference-flight-' + key).asset.footprintIds.includes(id), `${key}: formerly occluding source solid is replaced`);
  for (const key of ['dcube-city', 'dongnimmun', 'cheongwadae']) {
    const sources = results.get('reference-flight-' + key).asset.placementReview.identitySources;
    assert.ok(sources.some(source => source.url.startsWith('https://api.openstreetmap.org/api/0.6/')));
    assert.ok(sources.every(source => source.supports.length > 20), `${key}: reviewed source supports the stated identity`);
  }
  const garden = results.get('reference-flight-garden-five').asset;
  assert.ok(!garden.footprintIds.includes('ff6bff59-b677-475e-ad56-f54e43db2a5a'));
  assert.ok(!garden.supersedes.includes('apt-a10027346'), 'Garden Five does not replace Park Habio');
  const acro = results.get('reference-flight-acro-seoul-forest').asset;
  assert.ok(!acro.footprintIds.includes('c982c559-cf35-4b97-8296-4d6fcf9674af'), 'D Tower lies outside the authored Acro model');
  const gold = results.get('reference-flight-lotte-castle-goldpark');
  assert.deepEqual(gold.asset.placementReview.reviewedSourceBuildingNames.slice().sort(), ['301동', '302동', '303동', '304동', '305동', '306동']);
  assert.equal(gold.asset.placementReview.coordinateSourceFootprintIds.length, 6);
  assert.ok(Math.abs(gold.asset.coordinate.lon - 126.89730848375991) < 1e-8);
  assert.ok(Math.abs(gold.asset.coordinate.lat - 37.45994546325999) < 1e-8);
  assert.ok(!gold.asset.footprintIds.includes('bc9e12f5-3148-4e0f-8cd4-020854c8edc2'), 'phase 1 tower 107 is not part of phase 3');
});

test('the original five landmarks retain their matches and gain only source-linked descendants', async () => {
  const { manifest, integration } = await inspectPublished();
  const originals = await json('public/models/footprint-matches.json');
  const expanded = manifest.preservedLandmarkFootprints;
  assert.deepEqual(Object.keys(expanded).sort(), ['sixtythree', 'lotte', 'nseoul', 'coex', 'gyeongbokgung'].sort());
  for (const [id, ids] of Object.entries(expanded)) {
    assert.equal(new Set(ids).size, ids.length);
    for (const sourceId of originals[id]) assert.ok(ids.includes(sourceId), `${id}: original match retained`);
    assert.deepEqual(ids, integration.preservedLandmarkFootprints.models[id].footprintIds);
  }
  assert.ok(expanded.nseoul.includes('37616532-6231-3236-B565-353535326361'));
  assert.ok(expanded.gyeongbokgung.includes('66653035-3832-3836-A634-643863373039'));
});
