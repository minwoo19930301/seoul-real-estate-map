import type { Map as MapInstance, GeoJSONSource, MapGeoJSONFeature } from 'maplibre-gl';
import type { FeatureCollection, Feature } from 'geojson';
import { isCloseView, queryBounds } from './view-window.ts';

type BuildingData = FeatureCollection & { metadata?: { truncated?: boolean; hidden_at_zoom?: boolean; count?: number; returned?: number; available?: boolean } };
type ViewBounds = [number, number, number, number];
const BUILDING_LABEL_MIN_ZOOM = 16;
const empty = (): BuildingData => ({ type: 'FeatureCollection', features: [] });
const EMPTY_DATA = empty();
const covers = (outer: ViewBounds, inner: ViewBounds) => outer[0] <= inner[0] && outer[1] <= inner[1] && outer[2] >= inner[2] && outer[3] >= inner[3];
const escape = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const number = (value: unknown, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '미등록';
const recordedName = (value: unknown) => typeof value === 'string' ? value.trim() : '';

function classification(p: Record<string, any>, original: Record<string, any>) {
  if (p.is_apartment) return p.classification_source === 'parent' ? '아파트 (상위 건물 분류)' : '아파트 (원본 분류)';
  const labels: Record<string, string> = { residential: '주거', mixed_use: '복합용도' };
  const values = [p.class || original.class, p.subtype || original.subtype, original.A9]
    .filter((value): value is string => typeof value === 'string' && !!value.trim());
  const unique = [...new Set(values.map(value => labels[value] ?? value))];
  return unique.length ? `${unique.join(' · ')} (원본 분류)` : '용도 미등록';
}

export const buildingControls = `
  <section class="buildings-section">
    <div class="section-heading"><h2>건물 · 아파트</h2><span class="small-label">원본 외곽선</span></div>
    <label class="layer-row"><span class="legend-building"></span><span>건물 표시 <small>원본 높이로 입체 표시</small></span><input id="toggle-buildings" type="checkbox" checked aria-label="건물 표시"/></label>
    <label class="layer-row"><span class="legend-building"></span><span>건물 이름 <small>확대하면 등록 이름 표시</small></span><input id="toggle-building-labels" type="checkbox" checked aria-label="건물 이름 표시"/></label>
    <label class="layer-row"><span class="legend-apartment"></span><span>아파트만 보기</span><input id="apartments-only" type="checkbox" aria-label="아파트만 보기"/></label>
    <p id="building-status" class="muted" role="status">건물 자료 연결 중…</p>
    <p id="building-label-status" class="muted">확대하면 원본에 등록된 건물 이름을 표시합니다.</p>
    <p id="building-quality-note" class="muted">현재 높이: OSM 기여 기록 · 건축물대장 미연결</p>
    <p class="building-key"><i class="legend-building"></i>높이 기록 있음 <i class="legend-unknown"></i>높이 미등록</p>
    <p class="muted">높이가 없는 건물은 외곽선만 표시합니다. 아파트 분류는 원본 태그 기준입니다.</p>
    <details class="building-source"><summary>수록 범위와 높이 출처</summary><p id="building-coverage" class="muted">자료 확인 중…</p><p id="building-source-note" class="muted">OSM 높이 기록은 실측 검증 전 값입니다. 외곽선은 OSM 또는 영상 추출 자료이며, 현장 측량 도면과 차이가 날 수 있습니다.</p><a id="building-source-link" href="https://docs.overturemaps.org/guides/buildings/" target="_blank" rel="noreferrer">Overture Maps 건물 자료 ↗</a></details>
  </section>`;

export class Buildings {
  private data: BuildingData = empty();
  private controller?: AbortController;
  private timer?: ReturnType<typeof setTimeout>;
  private requestId = 0;
  private detailId = 0;
  private selected: string | number | null = null;
  private is25d = false;
  private ready = false;
  private latestError = false;
  private available = true;
  private official = false;
  private receivedData = false;
  private modelFootprints: string[] = [];
  private cachedKey = '';
  private cachedData?: BuildingData;
  private cachedBounds?: ViewBounds;
  private cachedCloseView = false;
  private cachedAt = 0;
  private loadingKey = '';
  private renderedData?: BuildingData;
  private rawFeatures = new Map<string, Feature>();
  private layouts = new Map<string, string>();
  private filters = new Map<string, string>();
  private presentationCloseView = false;
  private countedData?: BuildingData;
  private counts = { all: 0, known: 0, named: 0, apartments: 0, apartmentKnown: 0, apartmentNamed: 0 };

  private map: MapInstance;
  private onSelect: (coordinate: [number, number]) => void;
  constructor(map: MapInstance, onSelect: (coordinate: [number, number]) => void) {
    this.map = map; this.onSelect = onSelect;
    document.querySelector('#toggle-buildings')!.addEventListener('change', () => this.setVisible(this.enabled()));
    document.querySelector('#toggle-building-labels')!.addEventListener('change', () => this.setLabelsVisible(this.labelsEnabled()));
    document.querySelector('#apartments-only')!.addEventListener('change', () => { this.visibility(); this.status(); });
  }

  init() {
    this.map.addSource('building-data', { type: 'geojson', data: empty(), tolerance: 0, attribution: '건물: © Overture Maps · © OpenStreetMap 기여자 · Qian Shi et al. (CC BY 4.0)', promoteId: 'id' });
    const color: any = ['case', ['boolean', ['feature-state', 'selected'], false], '#126c95', ['boolean', ['get', 'is_apartment'], false], '#c5ae86', '#b0c3c8'];
    this.map.addLayer({ id: 'building-footprints', type: 'fill', source: 'building-data', paint: { 'fill-color': ['case', ['boolean', ['feature-state', 'selected'], false], '#126c95', ['==', ['get', 'height_status'], 'missing'], '#d6dcdf', color], 'fill-opacity': 0.42 } });
    this.map.addLayer({ id: 'building-outlines', type: 'line', source: 'building-data', paint: { 'line-color': ['case', ['==', ['get', 'height_status'], 'reported'], '#68818a', '#87949b'], 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 0.45, 18, 1.1], 'line-opacity': 0.7 } });
    this.map.addLayer({ id: 'building-solids', type: 'fill-extrusion', source: 'building-data', filter: ['==', ['get', 'height_status'], 'reported'], paint: { 'fill-extrusion-color': color, 'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 0], 'fill-extrusion-base': ['coalesce', ['get', 'min_height_m'], 0], 'fill-extrusion-opacity': ['interpolate', ['linear'], ['zoom'], 19, 0.92, 20.5, 1], 'fill-extrusion-vertical-gradient': true } });
    this.map.addLayer({
      id: 'building-labels', type: 'symbol', source: 'building-data', minzoom: BUILDING_LABEL_MIN_ZOOM,
      layout: {
        'text-field': ['get', '_building_label'], 'text-font': ['Noto Sans Regular'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 16, 11, 18, 13],
        'text-max-width': 10, 'text-padding': 5, 'text-offset': [0, -0.5],
        'text-anchor': 'bottom', 'text-pitch-alignment': 'viewport', 'text-rotation-alignment': 'viewport',
        'text-allow-overlap': false, 'text-ignore-placement': false,
        'symbol-sort-key': ['case', ['boolean', ['get', 'is_apartment'], false], 0, 1],
      },
      paint: { 'text-color': '#314d58', 'text-halo-color': '#ffffff', 'text-halo-width': 1.8 },
    });
    this.ready = true;
    this.visibility();
    void this.load();
    void fetch('/api/buildings/meta').then(response => { if (!response.ok) throw new Error('metadata'); return response.json(); }).then(meta => {
      this.available = meta.available !== false;
      this.official = meta.source_kind === 'official_gis_buildings';
      const count = meta.by_kind?.building?.count ?? meta.total_count;
      const reported = meta.by_kind?.building?.reported ?? meta.reported_count;
      const parts = meta.by_kind?.building_part?.count ?? 0;
      document.querySelector('#building-coverage')!.textContent = this.available ? `서울 · 건물 ${number(count, 0)}동 · 높이 기록 ${number(reported, 0)}동${parts ? ` · 부분 도형 ${number(parts, 0)}개` : ''}. 지형을 강조해도 건물의 기록 높이는 변하지 않습니다.` : '이 컴퓨터에 건물 DB가 아직 없습니다. README의 자료 준비 명령을 실행해 주세요.';
      if (this.official) {
        document.querySelector('#building-quality-note')!.textContent = '현재 높이: 국토부 건축물대장 기록 · 현장 실측 검증 전';
        document.querySelector('#building-source-note')!.textContent = '국토부 GIS건물통합정보의 도형과 건축물대장 기록입니다. 기록 기준일 이후의 현장 변화와 대장 오류는 별도 확인이 필요합니다.';
        const link = document.querySelector('#building-source-link') as HTMLAnchorElement;
        link.href = 'https://www.data.go.kr/data/15083092/fileData.do'; link.textContent = '국토부 GIS건물통합정보 ↗';
        const source = this.map.getSource('building-data');
        if (source) source.attribution = '건물: 국토교통부 GIS건물통합정보 · 건축물대장';
      }
      this.status();
    }).catch(() => { document.querySelector('#building-coverage')!.textContent = '건물 자료의 수록 범위를 확인하지 못했습니다.'; });
  }

  getData() { return this.data; }
  /** Label preference is retained while buildings are hidden. */
  getVisibility() { return { buildings: this.enabled(), labels: this.labelsEnabled() }; }
  setVisible(visible: boolean) {
    (document.querySelector('#toggle-buildings') as HTMLInputElement).checked = visible;
    this.visibility();
    void this.load();
  }
  setLabelsVisible(visible: boolean) {
    (document.querySelector('#toggle-building-labels') as HTMLInputElement).checked = visible;
    this.visibility();
  }
  setMode(is25d: boolean) { if (this.is25d !== is25d) { this.is25d = is25d; this.visibility(); } }
  /** Only successfully rendered models replace these exact source solids. */
  setModelFootprints(ids: string[]) {
    const next = [...new Set(ids)].sort();
    if (next.length === this.modelFootprints.length && next.every((id, index) => id === this.modelFootprints[index])) return;
    this.modelFootprints = next;
    this.visibility();
  }
  schedule() { this.visibility(); clearTimeout(this.timer); if (this.map.getZoom() < 14) void this.load(); else this.timer = setTimeout(() => void this.load(), 200); }
  private enabled() { return (document.querySelector('#toggle-buildings') as HTMLInputElement).checked; }
  private labelsEnabled() { return (document.querySelector('#toggle-building-labels') as HTMLInputElement).checked; }
  private onlyApartments() { return (document.querySelector('#apartments-only') as HTMLInputElement).checked; }
  private layout(id: string, visible: boolean) {
    const value = visible ? 'visible' : 'none';
    if (this.layouts.get(id) === value) return;
    this.layouts.set(id, value); this.map.setLayoutProperty(id, 'visibility', value);
  }
  private filter(id: string, value: any) {
    const signature = JSON.stringify(value);
    if (this.filters.get(id) === signature) return;
    this.filters.set(id, signature); this.map.setFilter(id, value);
  }
  private visibility() {
    if (!this.ready) return;
    const closeView = isCloseView(this.map);
    if (this.presentationCloseView !== closeView) {
      this.presentationCloseView = closeView;
      // Keep unregistered-height buildings visible as faint ground areas in a
      // street view, without their outline or implicit antialiased border.
      this.map.setPaintProperty('building-footprints', 'fill-opacity', closeView ? 0.10 : 0.42);
      this.map.setPaintProperty('building-footprints', 'fill-antialias', !closeView);
    }
    const filter: any = this.onlyApartments() ? ['==', ['get', 'is_apartment'], true] : ['literal', true];
    for (const id of ['building-footprints', 'building-outlines', 'building-solids']) {
      this.layout(id, this.enabled() && (id !== 'building-solids' || this.is25d) && (id !== 'building-outlines' || !closeView));
      this.filter(id, id === 'building-solids' ? ['all', filter, ['==', ['get', 'height_status'], 'reported'], ['!=', ['get', 'extrude'], false],
        ['!', ['in', ['get', 'id'], ['literal', this.modelFootprints]]],
        ['!', ['in', ['coalesce', ['get', 'parent_id'], ''], ['literal', this.modelFootprints]]]] : filter);
    }
    this.layout('building-labels', this.enabled() && this.labelsEnabled());
    this.filter('building-labels', ['all', filter, ['==', ['get', 'kind'], 'building'], ['!=', ['coalesce', ['get', '_building_label'], ''], '']]);
    (document.querySelector('#toggle-building-labels') as HTMLInputElement).disabled = !this.enabled();
    this.status();
  }

  private renderData() {
    if (this.renderedData === this.data) return;
    this.renderedData = this.data;
    this.rawFeatures.clear();
    // Worker tiling needs only paint/filter fields. Full source coordinates and
    // inspector properties stay in data/rawFeatures, outside the render payload.
    const displayData: FeatureCollection = { type: 'FeatureCollection', features: this.data.features.map(feature => {
      const p = feature.properties ?? {};
      this.rawFeatures.set(String(p.id ?? feature.id), feature);
      return { type: 'Feature', id: feature.id, geometry: feature.geometry, properties: {
        id: p.id ?? feature.id, parent_id: p.parent_id, height_status: p.height_status, height_m: p.height_m, min_height_m: p.min_height_m,
        is_apartment: p.is_apartment, extrude: p.extrude, kind: p.kind, _building_label: recordedName(p.name),
      } };
    }) };
    (this.map.getSource('building-data') as GeoJSONSource).setData(displayData);
  }

  private status() {
    const node = document.querySelector('#building-status')!;
    const labelNode = document.querySelector('#building-label-status')!;
    if (this.countedData !== this.data) {
      this.countedData = this.data;
      this.counts = { all: 0, known: 0, named: 0, apartments: 0, apartmentKnown: 0, apartmentNamed: 0 };
      for (const feature of this.data.features) {
        const p = feature.properties ?? {}, known = p.height_status === 'reported', named = p.kind === 'building' && !!recordedName(p.name);
        this.counts.all++; this.counts.known += Number(known); this.counts.named += Number(named);
        if (p.is_apartment) { this.counts.apartments++; this.counts.apartmentKnown += Number(known); this.counts.apartmentNamed += Number(named); }
      }
    }
    const named = this.onlyApartments() ? this.counts.apartmentNamed : this.counts.named;
    labelNode.textContent = !this.enabled() ? '건물 이름도 함께 숨겼습니다.'
      : !this.labelsEnabled() ? '건물 이름 표시를 껐습니다.'
        : !this.available || this.latestError ? '건물 자료가 준비되면 등록된 이름을 표시합니다.'
        : this.map.getZoom() < BUILDING_LABEL_MIN_ZOOM ? '더 확대하면 등록된 건물 이름이 보입니다.'
          : !this.receivedData ? '이 영역의 등록 이름을 확인하는 중…'
          : named ? `등록 이름 ${named.toLocaleString()}개 · 서로 겹치지 않는 이름만 표시합니다.`
            : '이 영역의 받은 자료에는 표시할 건물 이름이 없습니다.';
    if (!this.enabled()) { node.textContent = '건물 표시를 껐습니다.'; return; }
    if (this.latestError) { node.textContent = '건물 자료를 불러오지 못했습니다. 지도 이동 또는 표시를 다시 켜면 재시도합니다.'; return; }
    if (!this.available) { node.textContent = '로컬 건물 DB가 아직 준비되지 않았습니다.'; return; }
    if (this.map.getZoom() < 14) { node.textContent = '건물을 보려면 동네 수준으로 확대해 주세요.'; return; }
    if (!this.receivedData) { node.textContent = '이 영역의 건물 조회 중…'; return; }
    const count = this.onlyApartments() ? this.counts.apartments : this.counts.all;
    const known = this.onlyApartments() ? this.counts.apartmentKnown : this.counts.known;
    node.textContent = `불러온 영역 ${count.toLocaleString()}개 · 높이 기록 ${known.toLocaleString()}개${this.data.metadata?.truncated ? ' · 표시량 제한: 더 확대하세요.' : ''}`;
  }

  private async load() {
    if (!this.ready) return;
    if (!this.enabled() || this.map.getZoom() < 14) {
      this.controller?.abort(); this.loadingKey = ''; ++this.requestId;
      this.data = EMPTY_DATA; this.renderData(); this.latestError = false; this.receivedData = false; this.status(); return;
    }
    const b = queryBounds(this.map);
    const closeView = isCloseView(this.map);
    // Building API contents are identical at every zoom >=14; camera zoom only
    // affects rendering. Reuse a broader query only when it was fully returned.
    const bounds: ViewBounds = [Math.floor(b[0] * 1e6) / 1e6, Math.floor(b[1] * 1e6) / 1e6, Math.ceil(b[2] * 1e6) / 1e6, Math.ceil(b[3] * 1e6) / 1e6];
    const params = new URLSearchParams({ bbox: bounds.join(','), zoom: '14' });
    const key = params.toString();
    if (this.cachedData && this.cachedCloseView === closeView && Date.now() - this.cachedAt < 60_000 && (key === this.cachedKey || this.cachedBounds && this.cachedData.metadata?.available === true && this.cachedData.metadata.truncated === false && covers(this.cachedBounds, bounds))) {
      this.controller?.abort(); this.loadingKey = ''; ++this.requestId;
      const changed = this.data !== this.cachedData;
      this.data = this.cachedData; this.receivedData = true; this.latestError = false;
      this.available = this.data.metadata?.available !== false;
      if (changed) this.renderData();
      this.status(); return;
    }
    if (this.loadingKey === key && this.controller && !this.controller.signal.aborted) return;
    this.controller?.abort();
    const id = ++this.requestId;
    this.controller = new AbortController(); this.loadingKey = key; this.receivedData = false;
    document.querySelector('#building-status')!.textContent = '이 영역의 건물 조회 중…';
    this.status();
    try {
      const response = await fetch(`/api/buildings?${params}`, { signal: this.controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (id !== this.requestId) return;
      if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new Error('Invalid building data');
      this.data = data; this.latestError = false; this.receivedData = true;
      if (data.metadata?.available !== false) { this.cachedKey = key; this.cachedData = data; this.cachedBounds = bounds; this.cachedCloseView = closeView; this.cachedAt = Date.now(); }
      this.available = data.metadata?.available !== false;
      this.renderData();
      this.status();
    } catch (error) {
      if (id !== this.requestId || (error instanceof DOMException && error.name === 'AbortError')) return;
      this.data = EMPTY_DATA; this.latestError = true;
      this.renderData();
      this.status();
    } finally { if (id === this.requestId) this.loadingKey = ''; }
  }

  clearSelection() {
    ++this.detailId;
    if (this.selected !== null) this.map.setFeatureState({ source: 'building-data', id: this.selected }, { selected: false });
    this.selected = null;
  }

  click(point: { x: number; y: number }, coordinate: [number, number]) {
    if (!this.ready || !this.enabled()) return false;
    const hits = this.map.queryRenderedFeatures([point.x, point.y], { layers: ['building-labels', 'building-solids', 'building-footprints'] });
    if (!hits.length) return false;
    void this.inspect(hits[0], coordinate);
    return true;
  }

  async inspect(feature: MapGeoJSONFeature | Feature, coordinate: [number, number]) {
    const raw = this.rawFeatures.get(String(feature.properties?.id ?? feature.id));
    if (raw) feature = raw;
    else if (feature.properties && '_building_label' in feature.properties) return this.inspectById(String(feature.properties.id), coordinate);
    this.clearSelection();
    const id = ++this.detailId;
    this.selected = feature.properties!.id;
    this.map.setFeatureState({ source: 'building-data', id: this.selected! }, { selected: true });
    this.onSelect(coordinate);
    document.querySelector('#inspect-kind')!.textContent = '선택한 건물';
    this.showDetail(feature.properties!);
    document.querySelector('.inspect-section')!.scrollIntoView({ block: 'start', behavior: 'auto' });
    try {
      const response = await fetch(`/api/buildings/${encodeURIComponent(String(this.selected))}`);
      if (!response.ok) throw new Error('detail');
      const detail = await response.json();
      if (id !== this.detailId) return;
      this.showDetail(detail.properties ?? detail, detail.source_properties ?? {}, false);
    } catch {
      if (id === this.detailId) document.querySelector('#building-detail-note')!.textContent = '추가 상세 조회에 실패했습니다. 화면에 받은 원본 속성을 표시합니다.';
    }
  }

  /** Search results carry an original ID, not a partial building record. */
  async inspectById(buildingId: string, coordinate: [number, number]) {
    this.clearSelection();
    const id = ++this.detailId;
    this.selected = buildingId;
    this.map.setFeatureState({ source: 'building-data', id: buildingId }, { selected: true });
    this.onSelect(coordinate);
    document.querySelector('#inspect-kind')!.textContent = '선택한 건물';
    (document.querySelector('#save-form') as HTMLElement).hidden = true;
    const identifier = `<p class="building-id"><span class="building-id-label">원본 도형 ID</span><code>${escape(buildingId)}</code></p>`;
    document.querySelector('#inspection')!.innerHTML = `<p class="muted" role="status">건물 기록을 불러오는 중…</p>${identifier}`;
    document.querySelector('.inspect-section')!.scrollIntoView({ block: 'start', behavior: 'auto' });
    try {
      const response = await fetch(`/api/buildings/${encodeURIComponent(buildingId)}`);
      if (!response.ok) throw new Error('detail');
      const detail = await response.json();
      if (id !== this.detailId) return;
      const properties = detail.properties ?? detail;
      if (!properties || String(properties.id) !== buildingId) throw new Error('building ID mismatch');
      this.showDetail(properties, detail.source_properties ?? {});
    } catch {
      if (id !== this.detailId) return;
      document.querySelector('#inspection')!.innerHTML = `<p class="no-data" role="alert">건물 기록을 불러오지 못했습니다. 검색 결과를 다시 선택해 주세요.</p>${identifier}`;
      (document.querySelector('#save-form') as HTMLElement).hidden = true;
    }
  }

  private showDetail(p: Record<string, any>, original: Record<string, any> = {}, prefillBookmark = true) {
    const name = recordedName(p.name);
    const title = name || (p.is_apartment ? '이름 미등록 아파트' : '이름 미등록 건물');
    document.querySelector('#inspection')!.innerHTML = `
      <h3 class="building-title">${escape(title)}</h3>
      ${!name ? '<p class="muted building-name-note">이 원본 자료에는 건물 이름이 기록되어 있지 않습니다. 실제 건물에 이름이 없다는 뜻은 아닙니다.</p>' : ''}
      <div class="elevation-value building-height">${p.height_m == null ? '—' : number(p.height_m)}<span>m</span></div>
      <p class="reading-label">${p.height_review_required ? '검토가 필요한 원본 높이' : p.min_height_m ? '원본 높이 값' : '지면 위 건물 높이'} · ${p.height_m == null ? '미등록' : this.official ? '건축물대장 기록' : '원본 기록 / 미검증'}</p>
      <dl class="building-facts"><div><dt>외곽선 면적</dt><dd>${number(p.footprint_area_m2)} m²</dd></div><div><dt>지상 층수</dt><dd>${number(p.num_floors, 0)}${p.num_floors == null ? '' : '층'}</dd></div><div><dt>분류</dt><dd>${escape(classification(p, original))}</dd></div><div><dt>외곽선 출처</dt><dd>${escape(p.geometry_source || 'Overture Maps')}</dd></div><div><dt>높이 출처</dt><dd>${escape(p.height_source || '미등록')}</dd></div></dl>
      <p class="muted">외곽선 면적은 지도 도형의 수평 면적입니다. 대지면적·연면적·전용면적과 다릅니다.</p>
      ${p.kind === 'building_part' ? '<p class="muted">건물의 한 부분입니다. 같은 건물의 부분별 높이가 다를 수 있습니다.</p>' : ''}
      ${p.extrusion_reason === 'elevated_height_semantics_unverified' ? '<p class="muted">이 상부 구조물은 높이 기준을 확인할 때까지 외곽선으로 표시합니다.</p>' : ''}
      ${p.height_review_required ? '<p class="no-data">높이 기록이 1,000m 이상으로 검토가 필요합니다. 원본 숫자는 보존하고 입체 표시에서 제외했습니다.</p>' : ''}
      ${p.has_parts ? '<p class="muted">입체는 별도의 부분 도형으로 표시합니다. 높이가 없는 부분은 외곽선으로 남습니다.</p>' : ''}
      <details class="building-id"${!name ? ' open' : ''}><summary>원본 도형 식별자</summary><span class="building-id-label">${p.kind === 'building_part' ? '이 부분 도형 ID' : '이 건물 도형 ID'}</span><code>${escape(p.id)}</code>${p.parent_id ? `<span class="building-id-label">상위 건물 ID</span><code>${escape(p.parent_id)}</code>` : ''}<p class="muted">${this.official ? '국토부 원본 건물 식별자입니다.' : 'Overture 원본 ID입니다.'} 건물 이름이나 아파트 단지 코드와는 다르며, 공식 단지 정보 연결은 별도 확인이 필요합니다.</p></details>
      <p id="building-detail-note" class="muted"></p>`;
    if (prefillBookmark) (document.querySelector('#bookmark-name') as HTMLInputElement).value = title;
    (document.querySelector('#save-form') as HTMLElement).hidden = false;
  }
}
