#!/usr/bin/env node
// Undo documented game-scale compression. These are source-author estimates,
// not independently surveyed building dimensions or authoritative coordinates.
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';

const here = path.dirname(fileURLToPath(import.meta.url));
// Named retained OSM polygons, read from buildings.sqlite on 2026-09-20.
// These are source-footprint centroids, not independently surveyed coordinates.
const towerPalaceOrigin = [127.0548, 37.488];
const towerPalaceTargets = [
  ['A', [-37, -3], '9197849d-bf83-4832-9abe-0e78bd90981c', [127.05522435000002, 37.48881715], 'c47d2a5dd3084e189a47f0bff794329e9616d1a25492e2cbc415023a8323e92c'],
  ['B', [-8, 8], '995d5ddd-41d8-44aa-89d0-78b5b8207de6', [127.05479001805989, 37.48826845366382], 'b50fb8694e50c271d4808a2d4b5467fa3aa26fcf2f5537e0fbab8f72051b1382'],
  ['C', [20, -1], '2d2c76d4-7f8d-48f7-895a-eb2cd30da173', [127.05434670000001, 37.487735199999996], 'a719a2bdc3cf1261286b651ffe12049f5568790d941d13b982f2b516f427a00a'],
  ['D', [-28, -33], 'acdd801b-57dc-4384-b867-3cef5d194fa9', [127.05349534999999, 37.48805215], '47011ea783c534a09b317a550bb89acdf042ae36deeb022b5fd10faf107b3094'],
  ['E', [2, -40], '0aa4cf05-c633-4f2b-83c5-604b8629272d', [127.0540146331005, 37.489470684534695], '33c36219ac17a09481cf8af39c4048a2f5f5ed939b3b17e414de5c965cee92f4'],
  ['F', [28, -30], 'c6873a11-88e5-4129-bc93-19bc68cd7bd5', [127.05496656226549, 37.489885778640605], '19797209224f0f4c6bbdf59235552832fc4534336094d170723cdc89cf9805af'],
  ['G', [-25, 36], '0279553d-08e7-48de-bd31-6016d2b5445c', [127.05284687789084, 37.4870854797417], '23343bfa429560710d7cf1c79c240040fb491188f486f63d9396adf06dea1c62'],
].map(([name, sourceCentre, footprintId, coordinate, geometrySha256]) => ({ name, sourceCentre, footprintId, coordinate, geometrySha256 }));
const captureHelper = `
function __captureFlightParts(g, start, component) {
  for (const object of g.children.slice(start)) {
    if (!object.userData.flightComponent) object.userData.flightComponent = component;
  }
}
`;

function replaceOnce(source, marker, replacement) {
  if (source.split(marker).length !== 2) throw Error('Expected one source marker: ' + marker);
  return source.replace(marker, replacement);
}

function capture(source, key, start, end, centre, parent = 'g') {
  const variable = '__flight_' + key.replace(/-/g, '_');
  source = replaceOnce(source, start, `const ${variable} = ${parent}.children.length;\n    ${start}`);
  return replaceOnce(source, end, `__captureFlightParts(${parent}, ${variable}, ${JSON.stringify({ id: key, centre })});\n    ${end}`);
}

/** Instrument only temporary archived source, without changing source dimensions. */
export function instrumentSource(id, source) {
  if (id === 'tower-palace') {
    const marker = 'const g = subgroup(parent, { x, z, ry });';
    if (source.split(marker).length !== 4) throw Error('Tower Palace component structure changed');
    return source.replaceAll(marker, marker + "\n  g.userData.flightComponent = { id: 'tower-' + x + '-' + z, centre: [x, z] };");
  }
  if (id === 'samsung-town') {
    const sections = [
      ['samsung-c', 'const C = { x: 14, z: 16 };', '// ── A동:', [14, 16]],
      ['samsung-a', 'const A = { x: 14, z: -20 };', '// ── B동:', [14, -20]],
      ['samsung-b', 'const B = { x: -26, z: -4 };', '// ── Podium 1:', [-26, -4]],
      ['samsung-podium-ac', 'const p1 = { x0: 2, x1: 30, z0: -13, z1: 6 };', '// ── Podium 2:', [16, -3.5]],
      ['samsung-podium-b', 'const p2 = { x0: -35, x1: -17, z0: -28, z1: -16 };', '// ── Community plaza:', [-26, -22]],
    ];
    for (const [key, start, end, centre] of sections) source = capture(source, key, start, end, centre);
    return source + captureHelper;
  }
  if (id === 'parc1-ifc') {
    const sections = [
      ['ifc-three', '// Three IFC -', '// One IFC -', [-24, -21]],
      ['ifc-one', '// One IFC -', '// Two IFC -', [-46, 2]],
      ['ifc-two', '// Two IFC -', '// Conrad Seoul -', [-22, 23]],
      ['conrad', '// Conrad Seoul -', '// IFC Mall pavilions:', [-42.5, 21.5]],
      ['ifc-mall', '// IFC Mall pavilions:', '// ── Parc1 (', [-26, 2.5]],
      ['parc1-one', '// Tower 1 -', '// Tower 2 -', [4, -10]],
      ['parc1-two', '// Tower 2 -', '// The Hyundai Seoul -', [33, -2]],
      ['hyundai-seoul', '// The Hyundai Seoul -', '// Fairmont Ambassador Seoul -', [16, 23.5]],
      ['fairmont', '// Fairmont Ambassador Seoul -', '// ── LG Twin Towers (', [44.5, 18.5]],
      ['lg-twins', '// ── LG Twin Towers (', '// ── Trees ─', [29, -33]],
    ];
    for (const [key, start, end, centre] of sections) source = capture(source, key, start, end, centre);
    // Preserve each LG tower's own width while expanding their two centre positions.
    source = replaceOnce(source, '[22, 36].forEach((x) => {', '[22, 36].forEach((x) => {\n        const __lgStart = g.children.length;');
    const end = 'box(g, { w: 6, h: 1.6, d: 7, x, y: 136.5, z, mat: M.steelDark });';
    source = replaceOnce(source, end, end + "\n        __captureFlightParts(g, __lgStart, { id: 'lg-' + x, centre: [x, z] });");
    return source + captureHelper;
  }
  if (id === 'walkerhill') {
    const sections = [
      ['grand-hotel', '// ── 본관 Grand Walkerhill:', '// ── 비스타 워커힐 (', [-3, 0]],
      ['vista-hotel', '// ── 비스타 워커힐 (', '// Low glass bridge linking', [14, -36]],
      ['douglas-house', '// ── 더글라스 하우스:', '// Villas (1963)', [-16, -38]],
      ['pizza-hill', '// ── 피자힐 (', '// ── 리버파크 outdoor pool', [-46, 12]],
      ['river-pool', '// ── 리버파크 outdoor pool', '// ── 애스톤 하우스:', [14, 22]],
      ['aston-house', '// ── 애스톤 하우스:', '// ── 워커힐로:', [-14, 24]],
    ];
    for (const [key, start, end, centre] of sections) source = capture(source, key, start, end, centre, 'site');
    const start = '[[-36, -27], [-31, -33], [-25, -38]].forEach(([x, z], i) => {';
    source = replaceOnce(source, start, start + '\n      const __villaStart = site.children.length;');
    const end = 'if (i === 1) box(site, { w: 2, h: 2, d: 2, x: x + 1.5, y: T_UP + 5.9, z: z - 1.5, mat: M.concrete });';
    source = replaceOnce(source, end, end + "\n      __captureFlightParts(site, __villaStart, { id: 'villa-' + i, centre: [x, z] });");
    return source + captureHelper;
  }
  return source;
}

function scaleObject(object, x, y, z) {
  object.applyMatrix4(new THREE.Matrix4().makeScale(x, y, z));
}

function meshCounts(group) {
  let meshes = 0, triangles = 0;
  group.traverse(object => {
    if (object.isMesh) {
      meshes++;
      triangles += (object.geometry.index?.count ?? object.geometry.attributes.position.count) / 3;
    }
  });
  return { meshes, triangles };
}

function adaptComponents(group, { width, spacing, expected, targets = null, removeDecoration = false }) {
  const parts = new Map();
  let landscapeObjects = 0, removedDecorativeMeshes = 0, removedDecorativeTriangles = 0;
  const containers = [];
  group.traverse(object => {
    if (object.children.some(child => child.userData.flightComponent)) containers.push(object);
  });
  for (const container of containers) for (const child of [...container.children]) {
    const component = child.userData.flightComponent;
    if (component) {
      const [x, z] = component.centre;
      const target = targets?.find(row => row.sourceCentre[0] === x && row.sourceCentre[1] === z);
      if (targets && !target) throw Error('Missing named footprint target for ' + component.id);
      let targetX = x * spacing, targetZ = z * spacing;
      if (target) {
        const east = (target.coordinate[0] - towerPalaceOrigin[0]) * 111319.49079327358 * Math.cos(towerPalaceOrigin[1] * Math.PI / 180);
        const south = -(target.coordinate[1] - towerPalaceOrigin[1]) * 111319.49079327358;
        const local = new THREE.Vector3(east, 0, south).applyMatrix4(container.matrixWorld.clone().invert());
        targetX = local.x; targetZ = local.z;
      }
      // Source coordinates may be stored in geometry (flat components) or in
      // a subgroup translation (Tower Palace). T(c*s) S(w) T(-c) handles both.
      const transform = new THREE.Matrix4().makeTranslation(targetX, 0, targetZ)
        .multiply(new THREE.Matrix4().makeScale(width, 1, width))
        .multiply(new THREE.Matrix4().makeTranslation(-x, 0, -z));
      child.applyMatrix4(transform);
      const record = parts.get(component.id) ?? { id: component.id, sourceCentre: [x, z], adaptedCentre: [targetX, targetZ], widthScale: width, objects: 0,
        ...(target ? { name: target.name, footprintId: target.footprintId, coordinate: target.coordinate,
          geometrySha256: target.geometrySha256, sourceComponentGeometry: meshCounts(child),
          placementBasis: 'Retained named OSM footprint centroid; author tower width/roof retained with prior 2x width correction.' } : {}) };
      record.objects++;
      parts.set(component.id, record);
    } else {
      if (removeDecoration) {
        const counts = meshCounts(child);
        removedDecorativeMeshes += counts.meshes; removedDecorativeTriangles += counts.triangles;
        container.remove(child);
        continue;
      }
      // Shared site surfaces follow centre spacing, keeping the translated towers
      // on the shared site. This is explicitly an estimated landscape adaptation.
      scaleObject(child, spacing, 1, spacing);
      landscapeObjects++;
    }
  }
  if (parts.size !== expected) throw Error('Unexpected component count: ' + parts.size + ', expected ' + expected);
  return { components: [...parts.values()], landscapeObjects, landscapePlanScale: removeDecoration ? null : spacing,
    removedDecorativeMeshes, removedDecorativeTriangles,
    landscapeBasis: removeDecoration ? 'Unmatched shared decoration removed; original remains in pristine export.' : 'Estimated expansion of shared unassigned podium/plaza/landscape to follow source-author centre spacing; not surveyed.' };
}

/** Mutates a newly-created group before material merging and ground normalization. */
export function adaptGeometry(id, group, audit) {
  if (!audit || audit.id !== id) throw Error('Missing placement audit for ' + id);
  const recipe = {
    kind: 'original-source-proportions', changed: false, scaleVerified: false,
    evidenceAuthority: 'Source author comments only; actual footprint/coordinate fitting remains separate.',
    sourcePlanarFraction: audit.sourcePlanarFraction,
    sourceVerticalFraction: audit.sourceVerticalFraction,
    sourceCentreSpacingFraction: audit.sourceCentreSpacingFraction,
    sourceFileSha256: audit.sourceFileSha256,
    appliedScaleXYZ: [1, 1, 1], unresolved: [],
  };
  const complex = {
    'tower-palace': { width: 2, spacing: 1 / .35, expected: 7, targets: towerPalaceTargets, removeDecoration: true },
    'parc1-ifc': { width: 1, spacing: 1 / .35, expected: 12 },
    'samsung-town': { width: 1, spacing: 2, expected: 5 },
    'walkerhill': { width: 1, spacing: 1 / .45, expected: 9 },
  }[id];
  if (complex) {
    recipe.kind = 'component-width-and-centre-spacing';
    recipe.changed = true;
    recipe.componentRecipe = adaptComponents(group, complex);
    if (complex.targets) {
      recipe.namedFootprintPlacement = { sourceOrigin: towerPalaceOrigin, provider: 'Retained OpenStreetMap building polygons',
        independentlySurveyed: false, footprintIds: towerPalaceTargets.map(row => row.footprintId),
        centreSpacingRule: 'Actual named footprint centroids replace the former 1/0.35 game-spacing estimate.' };
      recipe.removedDecorativeMeshes = recipe.componentRecipe.removedDecorativeMeshes;
      recipe.removedDecorativeTriangles = recipe.componentRecipe.removedDecorativeTriangles;
      recipe.removalReason = 'Shared game-only plaza, podiums and landscape do not follow the actual seven-building block and would cover real roads/neighbours. All seven complete tower subgroups, including their own lower details, facades and roofs, are retained; pristine GLB stays unchanged.';
    }
    recipe.unresolved.push(complex.targets ? 'Building centres follow named retained footprints. Roof/width/height and rotation remain authored estimates; footprint outline matching is not asserted.' : 'Shared site/podium fitting and absolute georeferencing require independent footprint checks.');
    if (complex.width === 1) recipe.unresolved.push('Individual building footprint sizes have no explicit inverse-scale ratio; original widths retained.');
  } else {
    let planar = audit.sourcePlanarFraction;
    const vertical = audit.sourceVerticalFraction;
    let sx = 1, sz = 1, sy = 1;
    if (typeof planar === 'number') sx = sz = 1 / planar;
    else if (Array.isArray(planar)) [sx, sz] = planar.map(value => 1 / value);
    if (typeof vertical === 'number') sy = 1 / vertical;
    else if (Array.isArray(vertical)) {
      sy = 1 / ((vertical[0] + vertical[1]) / 2);
      recipe.unresolved.push('Vertical author range uses its midpoint as an explicit modeling estimate, not an exact measurement.');
    }
    if (planar == null && audit.sourceCentreSpacingFraction != null) {
      // Without stable component boundaries, global width enlargement would
      // falsely turn a centre-spacing claim into a building-dimension claim.
      recipe.unresolved.push('Centre-spacing ratio exists but source components are not individually isolated; original horizontal layout retained.');
    }
    if (planar == null && audit.sourceCentreSpacingFraction == null) recipe.unresolved.push('No numeric plan scale available; original source proportions retained.');
    if (vertical == null) recipe.unresolved.push('Vertical scale unspecified; original source height retained.');
    if (audit.planarClaimScope === 'building-footprints' || audit.planarClaimScope === 'site-spacing') {
      recipe.unresolved.push('The stated plan ratio is applied to the whole authored site; relative spacing and landscape are illustrative, not separately measured.');
    }
    scaleObject(group, sx, sy, sz);
    recipe.appliedScaleXYZ = [sx, sy, sz];
    recipe.changed = sx !== 1 || sy !== 1 || sz !== 1;
    recipe.kind = recipe.changed ? 'inverse-author-scale-estimate' : recipe.kind;
  }
  group.updateMatrixWorld(true);
  return recipe;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(here, '..');
  const supplied = process.argv.slice(2);
  const args = [path.join(here, 'export_flight_landmarks.mjs'),
    '--adaptation', path.join(root, 'data/model-source/flight-current/placement-audit.json'),
    '--out', path.join(root, 'data/model-source/flight-adapted'), ...supplied];
  execFileSync(process.execPath, args, { stdio: 'inherit' });
}
