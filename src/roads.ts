import type { Map as MapInstance, GeoJSONSource, LayerSpecification } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
import { isCloseView, queryBounds } from './view-window.ts';

export type RoadVisibility = { roadways: boolean; walkways: boolean; steps: boolean };
export type RoadData = FeatureCollection & { metadata?: { available?: boolean; count?: number; truncated?: boolean; hidden_at_zoom?: boolean; walkways_hidden_at_zoom?: boolean; counts?: Record<string, number> } };
type ViewBounds = [number, number, number, number];
const empty = (): RoadData => ({ type: 'FeatureCollection', features: [] });
const EMPTY_DATA = empty();
const layers = { roadways: ['roadway-lines'], walkways: ['walkway-lines', 'walkway-crossings'], steps: ['walkway-steps'] };
const covers = (outer: ViewBounds, inner: ViewBounds) => outer[0] <= inner[0] && outer[1] <= inner[1] && outer[2] >= inner[2] && outer[3] >= inner[3];

/** Original OSM lines. The caller owns controls and moveend scheduling. */
export class Roads {
  private data: RoadData = empty();
  private enabled: RoadVisibility = { roadways: true, walkways: true, steps: true };
  private controller?: AbortController;
  private timer?: ReturnType<typeof setTimeout>;
  private requestId = 0;
  private ready = false;
  private disposed = false;
  private lastError = false;
  private cachedKey = '';
  private cachedData?: RoadData;
  private cachedBounds?: ViewBounds;
  private cachedCloseView = false;
  private cachedBand = 0;
  private cachedAt = 0;
  private loadingKey = '';
  private renderedData?: RoadData;
  private layouts = new Map<string, string>();
  private lastStatus = '';

  private map: MapInstance;
  private onStatus: (text: string) => void;
  constructor(map: MapInstance, onStatus: (text: string) => void = () => {}) { this.map = map; this.onStatus = onStatus; }

  async init() {
    if (this.ready || this.disposed) return;
    this.map.addSource('road-data', { type: 'geojson', data: empty(), tolerance: 0, attribution: '도로·보행로: © OpenStreetMap contributors', promoteId: 'id' });
    const definitions: LayerSpecification[] = [
      // These are centreline symbols, not surveyed road-surface polygons.
      // MapLibre widths are pixels and dash lengths multiply those widths:
      // keep both bounded instead of converting assumed metres to huge strokes.
      { id: 'roadway-lines', type: 'line', source: 'road-data', minzoom: 11, filter: ['==', ['get', 'category'], 'roadway'], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#e1e5e8', 'line-opacity': 0.94, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1, 14, 3, 17, 7, 18, 9, 20, 10, 22, 11, 24, 12] } },
      { id: 'walkway-lines', type: 'line', source: 'road-data', minzoom: 14, filter: ['all', ['==', ['get', 'category'], 'walkway'], ['!=', ['get', 'subtype'], 'crossing']], layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['case', ['==', ['get', 'restricted'], true], '#c8d1d1', '#b8cfcb'], 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 1, 15, 1.3, 18, 2, 20, 2.5, 24, 3], 'line-dasharray': [2, 1.8], 'line-opacity': 0.65 } },
      { id: 'walkway-crossings', type: 'line', source: 'road-data', minzoom: 14, filter: ['==', ['get', 'subtype'], 'crossing'], layout: { 'line-cap': 'butt', 'line-join': 'round' }, paint: { 'line-color': '#adc7c4', 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 1.2, 15, 1.6, 18, 2.4, 20, 3, 24, 3.5], 'line-dasharray': [0.45, 1.1], 'line-opacity': 0.7 } },
      { id: 'walkway-steps', type: 'line', source: 'road-data', minzoom: 14, filter: ['==', ['get', 'category'], 'steps'], layout: { 'line-cap': 'butt', 'line-join': 'round' }, paint: { 'line-color': '#c9bca4', 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 1.2, 15, 1.6, 18, 2.3, 20, 3, 24, 3.5], 'line-dasharray': [0.35, 1.25], 'line-opacity': 0.72 } },
    ];
    const before = this.map.getLayer('contours') ? 'contours' : undefined;
    for (const layer of definitions) this.map.addLayer(layer, before);
    this.ready = true;
    this.visibility();
    await this.load();
  }

  getData() { return this.data; }
  setVisibility(value: RoadVisibility) {
    const changed = Object.keys(this.enabled).some(key => this.enabled[key as keyof RoadVisibility] !== value[key as keyof RoadVisibility]);
    if (!changed && !this.lastError) return;
    const wasEnabled = Object.values(this.enabled).some(Boolean);
    this.enabled = { ...value };
    this.visibility();
    if (wasEnabled !== Object.values(this.enabled).some(Boolean) || this.lastError) void this.load();
  }
  schedule() {
    clearTimeout(this.timer);
    if (this.map.getZoom() < 11) void this.load();
    else this.timer = setTimeout(() => void this.load(), 200);
  }
  private visibility() {
    if (!this.ready || this.disposed) return;
    for (const [key, ids] of Object.entries(layers)) for (const id of ids) {
      const value = this.enabled[key as keyof RoadVisibility] ? 'visible' : 'none';
      if (this.layouts.get(id) !== value) { this.layouts.set(id, value); this.map.setLayoutProperty(id, 'visibility', value); }
    }
    this.status();
  }
  private report(text: string) {
    if (text === this.lastStatus) return;
    this.lastStatus = text; this.onStatus(text);
  }
  private status() {
    if (!Object.values(this.enabled).some(Boolean)) { this.report('도로·보행로 표시 꺼짐'); return; }
    if (this.lastError) { this.report('도로 자료를 불러오지 못했습니다. 지도를 움직여 다시 시도할 수 있습니다.'); return; }
    if (this.data.metadata?.available === false) { this.report('이 컴퓨터에 도로 자료가 없습니다.'); return; }
    if (this.map.getZoom() < 11) { this.report('지도를 확대하면 도로가 표시됩니다.'); return; }
    const counts = this.data.metadata?.counts ?? {};
    const parts = [this.enabled.roadways ? `차도 ${(counts.roadway ?? 0).toLocaleString()}개` : '', this.enabled.walkways ? `보행로 ${(counts.walkway ?? 0).toLocaleString()}개` : '', this.enabled.steps ? `계단 ${(counts.steps ?? 0).toLocaleString()}개` : ''].filter(Boolean);
    this.report(`불러온 영역 · ${parts.join(' · ')}${this.data.metadata?.truncated ? ' · 표시 한도에 도달했습니다. 확대하면 더 보입니다.' : this.map.getZoom() < 14 ? ' · 보행로는 더 확대하면 표시됩니다.' : ''}`);
  }
  private async load() {
    if (!this.ready || this.disposed) return;
    if (this.map.getZoom() < 11 || !Object.values(this.enabled).some(Boolean)) {
      this.controller?.abort(); this.loadingKey = ''; ++this.requestId;
      this.data = EMPTY_DATA; this.lastError = false; this.update(); return;
    }
    const bounds = queryBounds(this.map);
    const closeView = isCloseView(this.map);
    const view: ViewBounds = [Math.floor(bounds[0] * 1e6) / 1e6, Math.floor(bounds[1] * 1e6) / 1e6, Math.ceil(bounds[2] * 1e6) / 1e6, Math.ceil(bounds[3] * 1e6) / 1e6];
    // Source min_zoom classes are 11 (major), 13 (local), and 14 (paths).
    const band = this.map.getZoom() >= 14 ? 14 : this.map.getZoom() >= 13 ? 13 : 11;
    const url = `/api/roads?bbox=${encodeURIComponent(view.join(','))}&zoom=${band}`;
    if (this.cachedData && this.cachedCloseView === closeView && Date.now() - this.cachedAt < 60_000 && this.cachedBand === band && (url === this.cachedKey || this.cachedBounds && this.cachedData.metadata?.available === true && this.cachedData.metadata.truncated === false && covers(this.cachedBounds, view))) {
      this.controller?.abort(); this.loadingKey = ''; ++this.requestId;
      const changed = this.data !== this.cachedData;
      this.data = this.cachedData; this.lastError = false;
      if (changed) this.update(); else this.status();
      return;
    }
    if (this.loadingKey === url && this.controller && !this.controller.signal.aborted) return;
    this.controller?.abort();
    const request = ++this.requestId;
    this.controller = new AbortController(); this.loadingKey = url;
    try {
      const response = await fetch(url, { signal: this.controller.signal });
      if (!response.ok) throw new Error(`Road API ${response.status}`);
      const data = await response.json() as RoadData;
      if (request !== this.requestId || this.disposed) return;
      if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new Error('Invalid road data');
      this.data = data; this.lastError = false; this.update();
      if (data.metadata?.available !== false) { this.cachedKey = url; this.cachedData = data; this.cachedBounds = view; this.cachedBand = band; this.cachedCloseView = closeView; this.cachedAt = Date.now(); }
    } catch (error) {
      if (request !== this.requestId || this.disposed || (error instanceof Error && error.name === 'AbortError')) return;
      this.data = EMPTY_DATA; this.lastError = true; this.update();
    } finally { if (request === this.requestId) this.loadingKey = ''; }
  }
  private update() {
    if (this.renderedData !== this.data) {
      this.renderedData = this.data;
      const display: FeatureCollection = { type: 'FeatureCollection', features: this.data.features.map(feature => {
        const p = feature.properties ?? {};
        return { type: 'Feature', id: feature.id, geometry: feature.geometry, properties: { id: p.id ?? feature.id, category: p.category, subtype: p.subtype, restricted: p.restricted } };
      }) };
      (this.map.getSource('road-data') as GeoJSONSource | undefined)?.setData(display);
    }
    this.status();
  }
  destroy() {
    this.disposed = true; this.requestId++; this.controller?.abort(); clearTimeout(this.timer);
    for (const ids of Object.values(layers)) for (const id of ids) if (this.map.getLayer(id)) this.map.removeLayer(id);
    if (this.map.getSource('road-data')) this.map.removeSource('road-data');
  }
}
