import type { Map as MapInstance } from 'maplibre-gl';

type QueryMap = Pick<MapInstance, 'getBounds' | 'getCenter' | 'getZoom' | 'getPitch'>;
type Bounds = [west: number, south: number, east: number, north: number];
const METRES_PER_DEGREE = Math.PI * 6371008.8 / 180;
const CLOSE_VIEW_RADIUS_METRES = 300;

export function isCloseView(map: Pick<QueryMap, 'getZoom' | 'getPitch'>): boolean {
  return map.getZoom() >= 19 && map.getPitch() >= 75;
}

/**
 * Close street views query their local surroundings, not the distant horizon.
 * This bounds data requests only; it does not clip or simplify source geometry.
 * The fixed local cap is centred on the public camera target in this Seoul map.
 */
export function queryBounds(map: QueryMap): Bounds {
  const b = map.getBounds();
  const visible: Bounds = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  if (!isCloseView(map)) return visible;
  const center = map.getCenter();
  const latitudeDelta = CLOSE_VIEW_RADIUS_METRES / METRES_PER_DEGREE;
  const longitudeDelta = latitudeDelta / Math.max(0.01, Math.cos(center.lat * Math.PI / 180));
  const local: Bounds = [center.lng - longitudeDelta, center.lat - latitudeDelta, center.lng + longitudeDelta, center.lat + latitudeDelta];
  // Tall buildings outside the tiny ground-plane extent can still fill the
  // screen at eye level. Include the surrounding block, within this fixed cap.
  return local;
}
