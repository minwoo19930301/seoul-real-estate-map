import { Marker, Popup, type Map as MapInstance } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
import type { Place } from './places';
import { queryBounds } from './view-window.ts';
import { renewalZoneControls } from './renewal-zones.ts';

type ApartmentRecord = { household_count?: number | null; official_complex_code?: string | null; household_count_source?: string; source_updated_at?: string; coordinate_source_url?: string };
export type SearchPlace = Place & ApartmentRecord & { id?: string; kind?: string; source_url?: string; building_id?: string | null };
type PinProperties = ApartmentRecord & { id: string; name: string; kind: string; priority?: number; subtitle?: string; source_url?: string };
type PinData = FeatureCollection<Point, PinProperties> & { metadata?: { available?: boolean; truncated?: boolean } };
const kinds: Record<string, { label: string; glyph: string }> = {
  station: { label: '철도·지하철역', glyph: '역' }, bridge: { label: '대교·다리', glyph: '교' },
  junction: { label: '교차로', glyph: '＋' }, residential: { label: '아파트·주거지', glyph: '집' },
};
const input = (id: string) => document.getElementById(id) as HTMLInputElement;
const empty = (): PinData => ({ type: 'FeatureCollection', features: [] });
export const landmarkControls = `
  <section class="landmarks-section">
    <div class="section-heading"><h2>주요 장소</h2><span class="small-label">이름이 있는 기준점</span></div>
    <label class="layer-row"><span class="pin-key"></span><span>장소 핀</span><input id="toggle-landmarks" type="checkbox" checked aria-label="장소 핀 표시"/></label>
    <div class="pin-filters">${Object.entries(kinds).map(([kind, item]) => `<label class="pin-filter ${kind}"><input id="pin-${kind}" type="checkbox" checked/><span>${item.label}</span></label>`).join('')}</div>
    <label class="layer-row"><span>아파트 핀은 400세대 이상</span><input id="pin-large-apartments" type="checkbox" checked aria-label="400세대 이상 아파트 핀만 표시"/></label>
    <p id="apartment-coverage" class="muted"></p>${renewalZoneControls}
    <p id="landmark-status" class="muted" role="status">주요 장소를 불러오는 중…</p>
    <p class="muted">가까운 이름은 겹치지 않게 표시합니다. 단지 핀은 단지 위치이며 개별 동의 높이를 뜻하지 않습니다.</p>
    <p id="landmark-source-date" class="muted"></p>
  </section>`;

export class Landmarks {
  private data: PinData = empty();
  private markers: Marker[] = [];
  private controller?: AbortController;
  private requestId = 0;
  private timer?: ReturnType<typeof setTimeout>;
  private popup?: Popup;
  private initialized = false;
  private cachedKey = '';
  private cachedData?: PinData;
  private renderKey = '';
  private dataRevision = 0;
  private measure?: CanvasRenderingContext2D | null;

  constructor(private map: MapInstance, private onSelect: (place: SearchPlace) => void) {}

  init() {
    this.initialized = true;
    for (const id of ['toggle-landmarks', 'pin-large-apartments', ...Object.keys(kinds).map(kind => `pin-${kind}`)]) {
      input(id).addEventListener('change', () => {
        this.controller?.abort(); ++this.requestId;
        this.clear(); this.popup?.remove(); this.schedule();
      });
    }
    this.map.on('pitchend', () => this.render());
    this.map.on('rotateend', () => this.render());
    this.map.on('resize', () => this.render());
    void this.load();
  }

  schedule() { clearTimeout(this.timer); this.timer = setTimeout(() => void this.load(), 180); }
  getData() { return this.data; }
  private clear() { this.renderKey = ''; this.markers.splice(0).forEach(marker => marker.remove()); }

  async load() {
    if (!this.initialized) return;
    this.controller?.abort(); const id = ++this.requestId;
    const status = document.getElementById('landmark-status')!;
    const selected = Object.keys(kinds).filter(kind => input(`pin-${kind}`).checked);
    if (!input('toggle-landmarks').checked || !selected.length) {
      this.data = empty(); this.clear(); status.textContent = '장소 핀을 숨겼습니다.'; return;
    }
    this.controller = new AbortController();
    const params = new URLSearchParams({ bbox: queryBounds(this.map).join(','), zoom: this.map.getZoom().toFixed(2), kinds: selected.join(',') });
    if (input('pin-large-apartments').checked) params.set('min_households', '400');
    const key = params.toString();
    if (key === this.cachedKey && this.cachedData) { this.data = this.cachedData; this.render(); return; }
    try {
      const response = await fetch(`/api/landmarks?${params}`, { signal: this.controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: PinData = await response.json();
      if (id !== this.requestId) return;
      this.cachedKey = key; this.cachedData = data;
      this.data = data; this.dataRevision++; this.render();
    } catch (error) {
      if (id !== this.requestId || error instanceof DOMException && error.name === 'AbortError') return;
      this.data = empty(); this.clear(); status.textContent = '장소 자료를 불러오지 못했습니다. 검색을 다시 시도해 주세요.';
    }
  }

  private render() {
    if (!this.initialized || !input('toggle-landmarks').checked) return;
    const canvas = this.map.getCanvas();
    const obstacles = Array.from(document.querySelectorAll<HTMLElement>('.map-tools, .terrain-badge, .map-legend, .mobility-badge, .map-notice, .maplibregl-ctrl-top-right')).filter(element => !element.hidden && element.getClientRects().length);
    const obstacleKey = obstacles.map(element => { const rect = element.getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height].join(','); }).join('|');
    const key = [this.dataRevision, this.map.getCenter().toArray().join(','), this.map.getZoom(), this.map.getPitch(), this.map.getBearing(), this.map.getTerrain()?.exaggeration ?? 0, canvas.clientWidth, canvas.clientHeight, obstacleKey,
      ...Object.keys(kinds).map(kind => input(`pin-${kind}`).checked)].join(':');
    if (this.renderKey === key) return;
    this.clear();
    this.renderKey = key;
    type Rect = { left: number; right: number; top: number; bottom: number };
    const occupied: Rect[] = [];
    const origin = canvas.getBoundingClientRect();
    for (const element of obstacles) {
      const rect = element.getBoundingClientRect();
      occupied.push({ left: rect.left - origin.left - 6, right: rect.right - origin.left + 6, top: rect.top - origin.top - 6, bottom: rect.bottom - origin.top + 6 });
    }
    const measure = this.measure ??= document.createElement('canvas').getContext('2d')!;
    measure.font = '650 11px "Apple SD Gothic Neo", "Noto Sans KR", sans-serif';
    const center = this.map.getCenter();
    const distance = (point: number[]) => (point[0] - center.lng) ** 2 + (point[1] - center.lat) ** 2;
    const features = [...this.data.features].filter(f => kinds[f.properties.kind] && input(`pin-${f.properties.kind}`).checked)
      .sort((a, b) => (b.properties.priority ?? 0) - (a.properties.priority ?? 0) || distance(a.geometry.coordinates) - distance(b.geometry.coordinates));
    const maxPins = canvas.clientWidth < 600 ? 14 : 30;
    for (const feature of features) {
      const coordinate = feature.geometry.coordinates as [number, number];
      const p = this.map.project(coordinate);
      const props = feature.properties, kind = kinds[props.kind];
      if (!Number.isFinite(p.x + p.y) || p.x < 25 || p.y < 60 || p.x > canvas.clientWidth - 25 || p.y > canvas.clientHeight - 70) continue;
      const labelWidth = Math.min(150, Math.ceil(measure.measureText(props.name).width) + 16);
      const leftLabel = p.x + 19 + labelWidth > canvas.clientWidth - 10;
      const rect: Rect = { left: leftLabel ? p.x - 19 - labelWidth : p.x - 17, right: leftLabel ? p.x + 17 : p.x + 19 + labelWidth, top: p.y - 43, bottom: p.y + 5 };
      if (rect.left < 8 || occupied.some(q => rect.left - 8 < q.right && rect.right + 8 > q.left && rect.top < q.bottom && rect.bottom > q.top)) continue;
      const button = document.createElement('button');
      button.type = 'button'; button.className = `landmark-pin ${props.kind}${leftLabel ? ' label-left' : ''}`;
      button.setAttribute('aria-label', `${props.name} ${kind.label} 위치`);
      button.title = `${props.name} · ${kind.label}${props.household_count ? ` · ${props.household_count.toLocaleString()}세대` : ''}`;
      button.innerHTML = `<span class="pin-head" aria-hidden="true">${kind.glyph}</span><span class="pin-name"></span>`;
      button.querySelector('.pin-name')!.textContent = props.name;
      button.addEventListener('click', event => {
        event.stopPropagation();
        this.select({ ...props, center: coordinate, zoom: 16,
          subtitle: props.subtitle || kind.label, source_url: props.source_url });
      });
      // Markers follow the terrain while their text remains upright in 2.5D.
      this.markers.push(new Marker({ element: button, anchor: 'bottom', pitchAlignment: 'viewport', rotationAlignment: 'viewport' }).setLngLat(coordinate).addTo(this.map));
      occupied.push(rect);
      if (this.markers.length >= maxPins) break;
    }
    document.getElementById('landmark-status')!.textContent = this.data.metadata?.available === false
      ? '장소 자료가 아직 준비되지 않았습니다.'
      : `현재 화면 핀 ${this.markers.length}개${features.length > this.markers.length || this.data.metadata?.truncated ? ' · 확대하면 더 보입니다.' : ''}`;
  }

  private async loadDetails(code: string, target: HTMLElement) {
    try {
      const response = await fetch(`/api/apartments/${encodeURIComponent(code)}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const d = await response.json();
      target.textContent = '';
      if (d.available === false) { target.textContent = '아파트 공개 자료 DB가 아직 준비되지 않았습니다.'; return; }
      const line = (text: string) => { const p = document.createElement('p'); p.textContent = text; target.append(p); };
      const b = d.kapt_basic;
      if (b) {
        line(['K-apt', b.동수 && `${b.동수}개 동`, b.최고층수 && `최고 ${b.최고층수}층`, b.사용승인일 && `사용승인 ${b.사용승인일}`, b.분양형태].filter(Boolean).join(' · '));
        const extras = [b.난방방식, b.복도유형, b.총주차대수 && `주차 ${Number(b.총주차대수).toLocaleString()}대`, b.시공사 && `시공 ${b.시공사}`].filter(Boolean);
        if (extras.length) line(extras.join(' · '));
      }
      for (const r of d.reb ?? []) line(`한국부동산원 ${r.dong_count ?? '?'}개 동 · 최고 지상 ${r.max_ground_floors ?? '?'}층${r.match_status === 'pnu_exact_multiple' ? ' (같은 필지 단지 여러 개)' : ''}`);
      const fee = d.management_fee;
      if (fee) line(`관리비 부과 합계 ${fee.month.slice(0, 4)}.${fee.month.slice(4)} · ${Math.round(fee.total_won / 10000).toLocaleString()}만원 (단지 전체)`);
      const pc = d.parcel;
      if (pc?.available) {
        const s = pc.sales;
        if (s?.count_apartment_uncancelled) {
          const r = s.recent[0];
          line(`실거래 ${s.count_apartment_uncancelled.toLocaleString()}건 · 최근 ${r.contract_date.slice(0, 4)}.${r.contract_date.slice(4, 6)} ${Math.round(r.area_m2)}㎡ ${r.floor}층 ${(r.price_manwon / 10000).toFixed(1)}억`);
        }
        if (pc.rents_2025?.count) line(`2025 전월세 ${pc.rents_2025.count.toLocaleString()}건 (전세 ${pc.rents_2025.jeonse.toLocaleString()} · 월세 ${pc.rents_2025.wolse.toLocaleString()})`);
        const price = pc.official_price_2025?.[0];
        if (price?.median_won) line(`2025 공시가격 중앙값 ${(price.median_won / 1e8).toFixed(1)}억 · ${price.unit_count.toLocaleString()}호`);
        const reg = pc.registers?.[0];
        if (reg) line(['건축물대장', reg.households && `${Number(reg.households).toLocaleString()}세대`, reg.floor_area_ratio && `용적률 ${reg.floor_area_ratio}%`, reg.parking && `주차 ${Number(reg.parking).toLocaleString()}대`].filter(Boolean).join(' · '));
        if (pc.permit_dongs?.count) line(`주택인허가 기록 동 ${pc.permit_dongs.count}개 · 최고 ${pc.permit_dongs.max_ground_floors ?? '?'}층${pc.permit_dongs.max_height_m ? ` · 기록 높이 최대 ${pc.permit_dongs.max_height_m}m` : ''}${pc.permit_dongs.suspect_height_count ? ` · 이상 높이 기록 ${pc.permit_dongs.suspect_height_count}개 제외` : ''} (재건축 계획 포함 가능)`);
      }
      const al = d.address_links;
      if (al?.available) {
        const labels: Record<string, string> = { sh_housing_management_oa_12027: 'SH 관리', sh_rental_complex_detail: 'SH 임대', lh_apartment_complexes: 'LH 아파트', lh_rental_complexes_built: 'LH 건설임대', lh_rental_complexes_purchased: 'LH 매입임대' };
        const renewalTables = ['cleanup_seoul_project_list', 'seoul_redevelopment_stats_oa_22856'];
        const lists = (al.lists ?? []) as { source_table: string; source_label: string; source_count: string }[];
        const parking = lists.find(x => x.source_table.endsWith('_parking'));
        const rental = lists.filter(x => labels[x.source_table]);
        const renewal = lists.filter(x => renewalTables.includes(x.source_table));
        const district = lists.filter(x => !labels[x.source_table] && !x.source_table.endsWith('_parking') && !renewalTables.includes(x.source_table));
        if (renewal.length) line(`정비사업 ${renewal.map(x => `${x.source_label} (${x.source_count})`).slice(0, 2).join(' · ')}`);
        if (rental.length) line(rental.map(x => `${labels[x.source_table]} ${x.source_label}${x.source_count && !isNaN(Number(x.source_count)) ? ` ${Number(x.source_count).toLocaleString()}세대` : ''}`).join(' · '));
        if (district.length) line(`자치구 공동주택 현황 ${district.length}건 · ${district[0].source_label}`);
        if (parking) line(`자치구 주차면수 ${Number(parking.source_count).toLocaleString()}면`);
        if (al.building_db_dongs?.count) line(`도로명주소 건물DB 공동주택 건물 ${al.building_db_dongs.count}개`);
        const energyText = (al.energy ?? []).map((e: { kind: string; month: string; amount_sum: number }) => `${e.kind === 'electric' ? '전기' : '가스'} ${Math.round(e.amount_sum).toLocaleString()}`).join(' · ');
        if (energyText) line(`건물에너지 ${al.energy[0].month.slice(0, 4)}.${al.energy[0].month.slice(4)} ${energyText} (원본 단위 미표기)`);
      }
      if (!b && !(d.reb ?? []).length && !fee && !pc?.sales?.count_apartment_uncancelled && !pc?.official_price_2025?.length) line('같은 단지코드·필지번호로 연결된 추가 공개 자료가 없습니다.');
      else line('층수는 층 수이며 높이가 아닙니다. 거래·공시가격은 같은 필지번호로 연결했습니다.');
    } catch { target.textContent = '공개 자료를 불러오지 못했습니다.'; }
  }

  select(place: SearchPlace) {
    this.popup?.remove();
    const content = document.createElement('div'); content.className = 'place-popup';
    const category = document.createElement('small'); category.textContent = kinds[place.kind ?? '']?.label || '검색한 장소';
    const title = document.createElement('h3'); title.textContent = place.name;
    const description = document.createElement('p'); description.textContent = place.subtitle;
    content.append(category, title, description);
    if (place.kind === 'residential') {
      if (typeof place.household_count === 'number' && place.official_complex_code) {
        const count = document.createElement('p'); count.className = 'apartment-households';
        count.textContent = `${place.household_count.toLocaleString()}세대 · 서울시 전체 세대수 기록`;
        const code = document.createElement('small'); code.textContent = `단지 코드 ${place.official_complex_code}`;
        content.append(count, code);
      }
      const note = document.createElement('p'); note.className = 'muted'; note.textContent = '단지 위치를 표시합니다. 개별 동의 높이는 건물을 선택해 확인하세요.'; content.append(note);
      if (place.official_complex_code) {
        const extra = document.createElement('div'); extra.className = 'apartment-details muted'; extra.textContent = '공개 자료를 불러오는 중…';
        content.append(extra); void this.loadDetails(place.official_complex_code, extra);
      }
    }
    if (place.coordinate_source_url && place.coordinate_source_url !== place.source_url && /^https?:\/\//.test(place.coordinate_source_url)) {
      const locationLink = document.createElement('a'); locationLink.href = place.coordinate_source_url; locationLink.target = '_blank'; locationLink.rel = 'noreferrer'; locationLink.textContent = '보완한 위치 출처 ↗'; content.append(locationLink);
    }
    if (place.source_url && /^https?:\/\//.test(place.source_url)) {
      const link = document.createElement('a'); link.href = place.source_url; link.target = '_blank'; link.rel = 'noreferrer'; link.textContent = place.official_complex_code ? '단지·세대수 원본 자료 ↗' : '이름·위치 출처 ↗'; content.append(link);
    }
    this.popup = new Popup({ closeOnClick: true, maxWidth: '260px', offset: 36 }).setLngLat(place.center).setDOMContent(content).addTo(this.map);
    this.onSelect(place);
  }
}
