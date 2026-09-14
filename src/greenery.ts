import type { Feature, FeatureCollection, Position } from 'geojson';

export type DecorativeTree = {
  id: string;
  coordinate: [number, number];
  height_m: number;
  crown_radius_m: number;
  decorative: true;
};
type Data = FeatureCollection & { metadata?: { available?: boolean; truncated?: boolean; hidden_at_zoom?: boolean; walkways_hidden_at_zoom?: boolean } };
export type GreeneryInput = {
  greenery: Data;
  buildings: Data;
  roads: Data;
  bounds: [number, number, number, number];
  /** True only when exclusion geometry covers the same viewport, independently of display toggles. */
  exclusionsReady: boolean;
  maxCount?: number;
};
export const GREENERY_DECORATION_NOTICE = '숲 안의 나무 모형은 장식입니다. 개별 나무의 실제 위치·높이를 나타내지 않습니다.';

type XY = [number, number];
type Box = [number, number, number, number];
type Shape = { rings: XY[][]; box: Box; polygon: boolean; buffer: number };
const ORIGIN: XY = [126.97, 37.56];
// Local planar distances for conservative visual spacing around Seoul only.
const METRES_LON = 111_320 * Math.cos(ORIGIN[1] * Math.PI / 180);
const METRES_LAT = 111_132;
const SPACING = 32;
const MAX_TREES = 240;
// Exclusion queries contain intersecting source geometry only. Keep enough
// margin for a road just outside the queried box plus the full tree crown.
const EXCLUSION_MARGIN = 32;
const point = (p: Position): XY => [(p[0] - ORIGIN[0]) * METRES_LON, (p[1] - ORIGIN[1]) * METRES_LAT];
const coordinate = (p: XY): XY => [ORIGIN[0] + p[0] / METRES_LON, ORIGIN[1] + p[1] / METRES_LAT];
const inBox = (p: XY, b: Box, padding = 0) => p[0] >= b[0] - padding && p[0] <= b[2] + padding && p[1] >= b[1] - padding && p[1] <= b[3] + padding;
const overlap = (a: Box, b: Box, padding = 0) => a[0] <= b[2] + padding && a[2] >= b[0] - padding && a[1] <= b[3] + padding && a[3] >= b[1] - padding;

function hash(x: number, y: number, salt: number) {
  let n = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ salt;
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}

function insideRing(p: XY, ring: XY[]) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

function inside(p: XY, rings: XY[][]) {
  return insideRing(p, rings[0]) && !rings.slice(1).some(ring => insideRing(p, ring));
}

function nearEdges(p: XY, rings: XY[][], distance: number, closed: boolean) {
  for (const ring of rings) {
    const segments = closed ? ring.length : ring.length - 1;
    for (let i = 0; i < segments; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      const dx = b[0] - a[0], dy = b[1] - a[1], length = dx * dx + dy * dy;
      const t = length ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length)) : 0;
      if ((p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2 <= distance ** 2) return true;
    }
  }
  return false;
}

function roadBuffer(feature: Feature) {
  const p = feature.properties ?? {};
  const road = String(p.highway ?? p.class ?? '');
  if (/^(motorway|trunk)/.test(road)) return 25;
  if (/^(primary|secondary)/.test(road)) return 18;
  if (/^tertiary/.test(road)) return 12;
  if (p.category === 'walkway' || p.category === 'steps' || /^(path|footway|pedestrian|cycleway|steps|track)$/.test(road)) return 5;
  return 9;
}

function shapes(features: Feature[], roads = false): Shape[] {
  const result: Shape[] = [];
  for (const feature of features) {
    const g = feature.geometry;
    if (!g) throw new Error('Missing exclusion geometry');
    let groups: Position[][][];
    const polygon = g.type === 'Polygon' || g.type === 'MultiPolygon';
    if (g.type === 'Polygon') groups = [g.coordinates];
    else if (g.type === 'MultiPolygon') groups = g.coordinates;
    else if (roads && g.type === 'LineString') groups = [[g.coordinates]];
    else if (roads && g.type === 'MultiLineString') groups = g.coordinates.map(line => [line]);
    else throw new Error('Unsupported exclusion geometry');
    for (const group of groups) {
      const rings = group.map(ring => ring.map(point));
      if (!rings.length || rings.some(ring => ring.length < (polygon ? 4 : 2) || ring.some(p => !p.every(Number.isFinite)))) throw new Error('Invalid geometry');
      const box: Box = [Infinity, Infinity, -Infinity, -Infinity];
      for (const ring of rings) for (const p of ring) {
        box[0] = Math.min(box[0], p[0]); box[1] = Math.min(box[1], p[1]);
        box[2] = Math.max(box[2], p[0]); box[3] = Math.max(box[3], p[1]);
      }
      result.push({ rings, box, polygon, buffer: roads ? roadBuffer(feature) : 2 });
    }
  }
  return result;
}

function incomplete(data: Data) {
  const m = data.metadata;
  return m?.available === false || m?.truncated || m?.hidden_at_zoom || m?.walkways_hidden_at_zoom;
}

/** Decorative, stable world-grid trees; never treats a park or lawn as a forest. */
export function buildDecorativeTrees(input: GreeneryInput): DecorativeTree[] {
  if (!input.exclusionsReady || incomplete(input.buildings) || incomplete(input.roads) || incomplete(input.greenery)) return [];
  const [west, south, east, north] = input.bounds;
  if (!input.bounds.every(Number.isFinite) || west >= east || south >= north || west < 126.6 || east > 127.4 || south < 37.3 || north > 37.85) return [];
  const limit = Math.min(MAX_TREES, Math.max(0, Math.floor(input.maxCount ?? MAX_TREES)));
  if (!Number.isFinite(limit) || !limit) return [];
  const sw = point([west, south]), ne = point([east, north]);
  const center: XY = [(sw[0] + ne[0]) / 2, (sw[1] + ne[1]) / 2];
  const viewport: Box = [Math.max(sw[0] + EXCLUSION_MARGIN, center[0] - 800), Math.max(sw[1] + EXCLUSION_MARGIN, center[1] - 800), Math.min(ne[0] - EXCLUSION_MARGIN, center[0] + 800), Math.min(ne[1] - EXCLUSION_MARGIN, center[1] + 800)];
  if (viewport[0] >= viewport[2] || viewport[1] >= viewport[3]) return [];
  let woods: Shape[], obstacles: Shape[];
  try {
    woods = shapes(input.greenery.features.filter(feature => {
      const p = feature.properties ?? {};
      return p.class === 'wood' || p.natural === 'wood' || p.landuse === 'forest';
    })).filter(shape => overlap(shape.box, viewport));
    obstacles = [...shapes(input.buildings.features), ...shapes(input.roads.features, true)].filter(shape => overlap(shape.box, viewport, shape.buffer + 5));
  } catch { return []; }
  if (!woods.length) return [];
  const candidates: { cell: XY; position: XY; rank: number }[] = [];
  for (let x = Math.floor(viewport[0] / SPACING); x <= Math.floor(viewport[2] / SPACING); x++) {
    for (let y = Math.floor(viewport[1] / SPACING); y <= Math.floor(viewport[3] / SPACING); y++) {
      const position: XY = [(x + 0.2 + hash(x, y, 17) * 0.6) * SPACING, (y + 0.2 + hash(x, y, 53) * 0.6) * SPACING];
      if (inBox(position, viewport)) candidates.push({ cell: [x, y], position, rank: (position[0] - center[0]) ** 2 + (position[1] - center[1]) ** 2 });
    }
  }
  candidates.sort((a, b) => a.rank - b.rank || a.cell[0] - b.cell[0] || a.cell[1] - b.cell[1]);
  const trees: DecorativeTree[] = [];
  for (const { cell: [x, y], position } of candidates) {
    const radius = 2 + hash(x, y, 101) * 1.4;
    if (!woods.some(shape => inBox(position, shape.box) && inside(position, shape.rings) && !nearEdges(position, shape.rings, radius + 1, true))) continue;
    if (obstacles.some(shape => inBox(position, shape.box, shape.buffer + radius) && (shape.polygon && inside(position, shape.rings) || nearEdges(position, shape.rings, shape.buffer + radius, shape.polygon)))) continue;
    trees.push({ id: `decorative-tree:${x}:${y}`, coordinate: coordinate(position), height_m: 5 + hash(x, y, 211) * 4, crown_radius_m: radius, decorative: true });
    if (trees.length >= limit) break;
  }
  return trees;
}
