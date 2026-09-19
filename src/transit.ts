import type { Map as MapInstance, LayerSpecification } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
export type TransitRecord = { nameKo: string; kind: 'rail_station' | 'bus_stop'; sourceUrl: string; locationMethod: string; ref?: string };
export type TransitData = FeatureCollection<Point, TransitRecord>;
const ids = ['transit-rail-points', 'transit-bus-points', 'transit-labels'];
export class TransitLayer {
  private ready = false; private rail = true; private bus = true;
  private map: MapInstance;
  constructor(map: MapInstance) { this.map = map; }
  async init() {
    if (this.ready) return;
    const response = await fetch('/transit.json');
    if (!response.ok) throw new Error(`Transit data HTTP ${response.status}`);
    const fc = await response.json() as TransitData;
    if (fc.type !== 'FeatureCollection' || !Array.isArray(fc.features) || new Set(fc.features.map(f => f.id)).size !== fc.features.length || fc.features.some(f => f.geometry?.type !== 'Point' || !f.geometry.coordinates.every(Number.isFinite) || !['rail_station', 'bus_stop'].includes(f.properties?.kind))) throw new Error('Invalid transit GeoJSON');
    this.map.addSource('transit-data', { type: 'geojson', data: fc, attribution: '정류장·역 위치: © OpenStreetMap contributors' });
    const defs: LayerSpecification[] = [
      { id: ids[0], type: 'circle', source: 'transit-data', minzoom: 11, filter: ['==', ['get', 'kind'], 'rail_station'], paint: { 'circle-color': '#265c81', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 3, 15, 5, 18, 6], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } },
      { id: ids[1], type: 'circle', source: 'transit-data', minzoom: 14, filter: ['==', ['get', 'kind'], 'bus_stop'], paint: { 'circle-color': '#b26e27', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 3, 18, 5], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } },
      { id: ids[2], type: 'symbol', source: 'transit-data', minzoom: 13, layout: { 'text-field': ['concat', ['case', ['==', ['get', 'kind'], 'bus_stop'], '버스 · ', '역 · '], ['get', 'nameKo']], 'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 13, 10, 17, 12], 'text-offset': [0, 1], 'text-anchor': 'top', 'text-allow-overlap': false }, paint: { 'text-color': '#243842', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } },
    ];
    for (const layer of defs) this.map.addLayer(layer);
    this.ready = true; this.setKinds(this.rail, this.bus, true);
  }
  setVisible(visible: boolean) { this.setKinds(visible, visible); }
  setKinds(rail: boolean, bus: boolean, force = false) {
    if (!force && this.rail === rail && this.bus === bus) return;
    this.rail = rail; this.bus = bus;
    if (!this.ready) return;
    this.map.setLayoutProperty(ids[0], 'visibility', rail ? 'visible' : 'none');
    this.map.setLayoutProperty(ids[1], 'visibility', bus ? 'visible' : 'none');
    this.map.setFilter(ids[2], ['in', ['get', 'kind'], ['literal', [...(rail ? ['rail_station'] : []), ...(bus ? ['bus_stop'] : [])]]]);
  }
}
