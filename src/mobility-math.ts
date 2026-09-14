/** Real route geometry and raw DEM metres for manual walking and fixed references. */
export type RouteCoordinate = [number, number, number];
export type MobilityRoute = {
  id: string;
  kind: 'pedestrian' | 'car';
  category: 'roadway' | 'walkway' | 'steps';
  coordinates: RouteCoordinate[];
  oneway: boolean;
};
export type Direction = 1 | -1;
type Segment = { start: number; length: number; rise: number; slopeDegrees: number };
export type PreparedRoute = {
  source: MobilityRoute;
  direction: Direction;
  coordinates: RouteCoordinate[];
  segments: Segment[];
  length: number;
  maxSlopeDegrees: number;
};
export type RouteSample = {
  coordinate: RouteCoordinate;
  slopeDegrees: number;
};
const RAD = Math.PI / 180;
const EARTH_RADIUS = 6371008.8;

export function horizontalDistance(a: RouteCoordinate, b: RouteCoordinate): number {
  const dLat = (b[1] - a[1]) * RAD, dLon = (b[0] - a[0]) * RAD;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** atan rise/run returns degrees, not a percent gradient. No vertical zero-length segments. */
export function slopeDegrees(rise: number, horizontal: number): number {
  return horizontal > 0 && Number.isFinite(rise) && Number.isFinite(horizontal) ? Math.atan2(rise, horizontal) / RAD : 0;
}

export function canReverse(route: MobilityRoute): boolean {
  return route.kind === 'pedestrian' || !route.oneway;
}

export function prepareRoute(source: MobilityRoute, direction: Direction = 1): PreparedRoute | null {
  if (direction === -1 && !canReverse(source)) return null;
  if (!Array.isArray(source.coordinates) || source.coordinates.length < 2) return null;
  const coordinates: RouteCoordinate[] = [];
  for (const point of source.coordinates) {
    if (!Array.isArray(point) || point.length !== 3 || !point.every(Number.isFinite) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 85) return null;
    // Duplicate XY cannot establish a grade. Keep the first sample, do not invent a vertical route.
    if (!coordinates.length || horizontalDistance(coordinates[coordinates.length - 1], point) >= 0.05) coordinates.push([...point]);
  }
  if (coordinates.length < 2) return null;
  if (direction === -1) coordinates.reverse();
  let length = 0, maxSlopeDegrees = 0;
  const segments: Segment[] = [];
  for (let i = 1; i < coordinates.length; i++) {
    const run = horizontalDistance(coordinates[i - 1], coordinates[i]);
    const rise = coordinates[i][2] - coordinates[i - 1][2];
    const slope = slopeDegrees(rise, run);
    segments.push({ start: length, length: run, rise, slopeDegrees: slope });
    maxSlopeDegrees = Math.max(maxSlopeDegrees, slope);
    length += run;
  }
  return { source, direction, coordinates, segments, length, maxSlopeDegrees };
}

export function sampleRoute(route: PreparedRoute, distance: number): RouteSample {
  const at = Math.max(0, Math.min(route.length, Number.isFinite(distance) ? distance : 0));
  let lo = 0, hi = route.segments.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi + 1) / 2);
    if (route.segments[mid].start <= at) lo = mid; else hi = mid - 1;
  }
  const segment = route.segments[lo], t = Math.min(1, (at - segment.start) / segment.length);
  const a = route.coordinates[lo], b = route.coordinates[lo + 1];
  return {
    coordinate: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
    slopeDegrees: segment.slopeDegrees,
  };
}

/** Public terrain ray picking must return the same ground position, within small mesh tolerance. */
export function terrainPointVisible(coordinate: RouteCoordinate, hit: { lng: number; lat: number } | null | undefined, toleranceM = 0.75): boolean {
  return !!hit && Number.isFinite(hit.lng) && Number.isFinite(hit.lat) && horizontalDistance(coordinate, [hit.lng, hit.lat, 0]) <= toleranceM;
}

/** MapLibre's public custom-layer Mercator matrix uses column-major clip coordinates. */
export function projectMercator(matrix: ArrayLike<number>, coordinate: { x: number; y: number; z: number }, width: number, height: number): { x: number; y: number } | null {
  const { x, y, z } = coordinate;
  const w = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
  if (!Number.isFinite(w) || w <= 0) return null;
  const depth = (matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]) / w;
  if (!Number.isFinite(depth) || depth < -1 || depth > 1) return null;
  const sx = ((matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]) / w + 1) * width / 2;
  const sy = (1 - (matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]) / w) * height / 2;
  return Number.isFinite(sx) && Number.isFinite(sy) ? { x: sx, y: sy } : null;
}
