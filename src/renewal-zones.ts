import type { GeoJSONSource, Map as MapInstance } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
import { queryBounds } from './view-window.ts';

type ZoneData = FeatureCollection & { metadata?: { available?: boolean; truncated?: boolean; count?: number } };
const empty = (): ZoneData => ({ type: 'FeatureCollection', features: [] });
const input = (id: string) => document.getElementById(id) as HTMLInputElement;

export const renewalZoneControls = `
    <label class="layer-row"><span class="legend-renewal"></span><span>재건축·재개발 구역 <small>서울도시공간포털</small></span><input id="toggle-renewal-zones" type="checkbox" aria-label="재건축·재개발 구역 표시"/></label>
    <p id="renewal-status" class="muted" role="status" hidden></p>`;

/** Renewal-zone polygons from the local apartment-sources database, shown from zoom 12. */
export class RenewalZones {
  private controller?: AbortController;
  private timer?: ReturnType<typeof setTimeout>;
  private key = '';

  constructor(private map: MapInstance) {}

  init() {
    this.map.addSource('renewal-zones', { type: 'geojson', data: empty() });
    this.map.addLayer({ id: 'renewal-zones-fill', type: 'fill', source: 'renewal-zones', layout: { visibility: 'none' },
      paint: { 'fill-color': ['match', ['get', 'kind'], 'district', '#c2410c', '#7c3aed'], 'fill-opacity': 0.12 } });
    this.map.addLayer({ id: 'renewal-zones-line', type: 'line', source: 'renewal-zones', layout: { visibility: 'none' },
      paint: { 'line-color': ['match', ['get', 'kind'], 'district', '#c2410c', '#7c3aed'], 'line-width': 1.4, 'line-dasharray': [2, 1] } });
    this.map.addLayer({ id: 'renewal-zones-label', type: 'symbol', source: 'renewal-zones', minzoom: 14.5,
      layout: { visibility: 'none', 'text-field': ['get', 'name'], 'text-size': 11, 'symbol-placement': 'point', 'text-max-width': 10 },
      paint: { 'text-color': '#5b21b6', 'text-halo-color': '#ffffff', 'text-halo-width': 1.2 } });
    input('toggle-renewal-zones').addEventListener('change', () => { this.key = ''; this.apply(); this.schedule(); });
  }

  schedule() { clearTimeout(this.timer); this.timer = setTimeout(() => void this.load(), 250); }

  private apply() {
    const on = input('toggle-renewal-zones').checked;
    for (const id of ['renewal-zones-fill', 'renewal-zones-line', 'renewal-zones-label'])
      if (this.map.getLayer(id)) this.map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    document.getElementById('renewal-status')!.hidden = !on;
  }

  private async load() {
    const status = document.getElementById('renewal-status')!;
    if (!input('toggle-renewal-zones').checked) return;
    if (this.map.getZoom() < 12) { (this.map.getSource('renewal-zones') as GeoJSONSource).setData(empty()); this.key = ''; status.textContent = '확대하면 재건축·재개발 구역이 보입니다.'; return; }
    const bbox = queryBounds(this.map).map(v => v.toFixed(5)).join(',');
    if (bbox === this.key) return;
    this.key = bbox; this.controller?.abort(); const controller = this.controller = new AbortController();
    try {
      const response = await fetch(`/api/renewal-zones?bbox=${bbox}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: ZoneData = await response.json();
      if (controller.signal.aborted) return;
      (this.map.getSource('renewal-zones') as GeoJSONSource).setData(data);
      status.textContent = data.metadata?.available === false ? '아파트 공개 자료 DB가 아직 준비되지 않았습니다.'
        : `구역 ${data.features.length}개${data.metadata?.truncated ? ' · 일부만 표시, 확대하면 더 보입니다.' : ''} · 보라 사업장 구역, 주황 정비구역`;
    } catch (error) {
      if ((error as Error).name !== 'AbortError') { this.key = ''; status.textContent = '재건축·재개발 구역을 불러오지 못했습니다.'; }
    }
  }
}
