import type { Map as MapInstance, LayerSpecification } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
const ids = ['avenue-surface', 'avenue-centre', 'avenue-names'];
export class Avenues {
  private ready = false;
  private visible = true;
  private map: MapInstance;
  constructor(map: MapInstance) { this.map = map; }
  async init() {
    const load = async (url: string) => {
      const r = await fetch(url); if (!r.ok) throw new Error('대로 자료를 불러오지 못했습니다.');
      const data = await r.json() as FeatureCollection;
      if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new Error('잘못된 도로 자료');
      return data;
    };
    const [surfaces, lines] = await Promise.all([load('/avenue-surfaces.geojson'), load('/avenue-centerlines.geojson')]);
    this.map.addSource('avenue-surfaces', { type: 'geojson', data: surfaces, attribution: '도로 중심선: © OpenStreetMap contributors · 폭 일부 추정' });
    this.map.addSource('avenue-lines', { type: 'geojson', data: lines });
    const layers: LayerSpecification[] = [
      { id: ids[0], type: 'fill', source: 'avenue-surfaces', minzoom: 12, paint: { 'fill-color': '#373d42', 'fill-opacity': .94 } },
      { id: ids[1], type: 'line', source: 'avenue-lines', minzoom: 16, layout: { 'line-cap': 'butt' }, paint: { 'line-color': ['case', ['get', 'oneway'], '#f0eee4', '#edcc62'], 'line-width': ['interpolate', ['linear'], ['zoom'], 16, .5, 19, 1.2], 'line-dasharray': [5, 5], 'line-opacity': .7 } },
      { id: ids[2], type: 'symbol', source: 'avenue-lines', minzoom: 14, layout: { 'symbol-placement': 'line', 'symbol-spacing': 450, 'text-field': ['get', 'name'], 'text-size': 11, 'text-font': ['Noto Sans Regular'], 'text-allow-overlap': false }, paint: { 'text-color': '#fafaf5', 'text-halo-color': '#343b40', 'text-halo-width': 1.3 } },
    ];
    const before = this.map.getLayer('contours') ? 'contours' : undefined;
    for (const layer of layers) this.map.addLayer(layer, before);
    this.ready = true; this.setVisible(this.visible, true);
  }
  setVisible(visible: boolean, force = false) {
    if (visible === this.visible && !force) return;
    this.visible = visible;
    if (this.ready) for (const id of ids) this.map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  }
}
