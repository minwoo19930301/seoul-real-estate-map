import type { Map as MapInstance } from 'maplibre-gl';

type QueryMap = Pick<MapInstance, 'getBounds' | 'getCenter' | 'getZoom' | 'getPitch'>;
type Bounds = [west: number, south: number, east: number, north: number];
const METRES_PER_DEGREE = Math.PI * 6371008.8 / 180;
const CLOSE_VIEW_RADIUS_METRES = 300;
const FLIGHT_VIEW_RADIUS_METRES = 800;
const FLIGHT_GRID_METRES = 100;
const SEOUL_LONGITUDE_SCALE = Math.cos(37.566 * Math.PI / 180);
type FlightFocus = Readonly<{ lon: number; lat: number }>;
const flightFocus = new WeakMap<object, FlightFocus>();

/** Aircraft position, independent of the forward-looking camera target. */
export function setFlightQueryFocus(map: object, focus: FlightFocus | null): void {
  if (!focus || !Number.isFinite(focus.lon) || !Number.isFinite(focus.lat)
    || Math.abs(focus.lon) > 180 || Math.abs(focus.lat) > 90) {
    flightFocus.delete(map);
    return;
  }
  // A fixed Seoul metric grid avoids latitude changes shifting the east grid.
  const latStep = FLIGHT_GRID_METRES / METRES_PER_DEGREE;
  const lonStep = latStep / SEOUL_LONGITUDE_SCALE;
  flightFocus.set(map, Object.freeze({
    lon: 127 + Math.round((focus.lon - 127) / lonStep) * lonStep,
    lat: 37.5 + Math.round((focus.lat - 37.5) / latStep) * latStep,
  }));
}

export function getFlightQueryFocus(map: object): FlightFocus | undefined {
  return flightFocus.get(map);
}

function localBounds(lon: number, lat: number, radius: number): Bounds {
  const latitudeDelta = radius / METRES_PER_DEGREE;
  const longitudeDelta = latitudeDelta / Math.max(0.01, Math.cos(lat * Math.PI / 180));
  return [lon - longitudeDelta, lat - latitudeDelta, lon + longitudeDelta, lat + latitudeDelta];
}

export function isCloseView(map: Pick<QueryMap, 'getZoom' | 'getPitch'>): boolean {
  return map.getZoom() >= 19 && map.getPitch() >= 75;
}

/**
 * Close street views query their local surroundings, not the distant horizon.
 * This bounds data requests only; it does not clip or simplify source geometry.
 * The fixed local cap is centred on the public camera target in this Seoul map.
 */
export function queryBounds(map: QueryMap): Bounds {
  const flight = flightFocus.get(map);
  if (flight) return localBounds(flight.lon, flight.lat, FLIGHT_VIEW_RADIUS_METRES);
  const b = map.getBounds();
  const visible: Bounds = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  if (!isCloseView(map)) return visible;
  const center = map.getCenter();
  // Tall buildings outside the tiny ground-plane extent can still fill the
  // screen at eye level. Include the surrounding block, within this fixed cap.
  return localBounds(center.lng, center.lat, CLOSE_VIEW_RADIUS_METRES);
}
