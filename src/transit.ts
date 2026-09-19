import { Popup, type Map as MapInstance, type FilterSpecification } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
export type TransitKind = 'rail_station' | 'bus_stop' | 'bike_station';
export type TransitRecord = { nameKo: string; kind: TransitKind; sourceUrl: string; locationMethod: string; ref?: string; sourceDate?: string; district?: string };
export type TransitData = FeatureCollection<Point, TransitRecord> & { metadata?: { attribution?: string } };
const kinds: { kind: TransitKind; point: string; label: string; prefix: string; color: string; minZoom: number; labelZoom: number }[] = [
  { kind: 'rail_station', point: 'transit-rail-points', label: 'transit-labels', prefix: '역', color: '#265c81', minZoom: 11, labelZoom: 13 },
  { kind: 'bus_stop', point: 'transit-bus-points', label: 'transit-bus-labels', prefix: '버스', color: '#b26e27', minZoom: 14, labelZoom: 16 },
  { kind: 'bike_station', point: 'transit-bike-points', label: 'transit-bike-labels', prefix: '따릉이', color: '#27864b', minZoom: 14, labelZoom: 16 },
];
export class TransitLayer {
  private ready = false;
  private visibility = [true, true, true];
  private map: MapInstance;
  private popup?: Popup;
  constructor(map: MapInstance) { this.map = map; }
  async init() {
    if (this.ready) return;
    const response = await fetch('/transit.json');
    if (!response.ok) throw new Error(`Transit data HTTP ${response.status}`);
    const fc = await response.json() as TransitData;
    if (fc.type !== 'FeatureCollection' || !Array.isArray(fc.features) || new Set(fc.features.map(f => f.id)).size !== fc.features.length || fc.features.some(f => f.id == null || f.geometry?.type !== 'Point' || f.geometry.coordinates.length !== 2 || !f.geometry.coordinates.every(Number.isFinite) || Math.abs(f.geometry.coordinates[0]) > 180 || Math.abs(f.geometry.coordinates[1]) > 90 || !kinds.some(k => k.kind === f.properties?.kind) || !f.properties.nameKo)) throw new Error('Invalid transit GeoJSON');
    this.map.addSource('transit-data', { type: 'geojson', data: fc, attribution: fc.metadata?.attribution ?? '역·정류장·따릉이 위치: 서울특별시, © OpenStreetMap contributors' });
    for (const item of kinds) {
      const filter: FilterSpecification = ['==', ['get', 'kind'], item.kind];
      this.map.addLayer({ id: item.point, type: 'circle', source: 'transit-data', minzoom: item.minZoom, filter, paint: { 'circle-color': item.color, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2.5, 15, 4, 18, 5.5], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.3 } });
      this.map.addLayer({ id: item.label, type: 'symbol', source: 'transit-data', minzoom: item.labelZoom, filter, layout: { 'text-field': ['concat', `${item.prefix} · `, ['get', 'nameKo']], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1], 'text-anchor': 'top', 'text-allow-overlap': false, 'text-max-width': 14 }, paint: { 'text-color': item.color, 'text-halo-color': '#fff', 'text-halo-width': 1.5 } });
      this.map.on('click', item.point, event => {
        const feature = event.features?.[0];
        if (!feature || feature.geometry.type !== 'Point') return;
        const p = feature.properties;
        const content = document.createElement('div');
        const title = document.createElement('strong'); title.textContent = `${item.prefix} · ${p.nameKo}`; content.append(title);
        const detail = document.createElement('p'); detail.textContent = `${p.ref ? `번호 ${p.ref} · ` : ''}${p.sourceDate ? `${p.sourceDate} 기준 위치` : '원본 자료의 위치'}`; content.append(detail);
        if (item.kind === 'bike_station') { const note = document.createElement('p'); note.textContent = '실시간 대여 가능 대수는 제공하지 않습니다.'; content.append(note); }
        if (typeof p.sourceUrl === 'string' && /^https?:\/\//.test(p.sourceUrl)) { const link = document.createElement('a'); link.href = p.sourceUrl; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = '위치 자료 출처'; content.append(link); }
        this.popup?.remove(); this.popup = new Popup({ maxWidth: '280px' }).setLngLat(feature.geometry.coordinates as [number, number]).setDOMContent(content).addTo(this.map);
      });
    }
    this.ready = true; this.applyVisibility();
  }
  setVisible(visible: boolean) { this.setKinds(visible, visible, visible); }
  setKinds(rail: boolean, bus: boolean, bike = this.visibility[2]) {
    const next = [rail, bus, bike];
    if (next.every((value, i) => value === this.visibility[i])) return;
    this.visibility = next; this.popup?.remove(); this.applyVisibility();
  }
  private applyVisibility() {
    if (!this.ready) return;
    for (const [i, item] of kinds.entries()) for (const id of [item.point, item.label]) this.map.setLayoutProperty(id, 'visibility', this.visibility[i] ? 'visible' : 'none');
  }
}
