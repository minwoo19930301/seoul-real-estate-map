import * as maplibregl from 'maplibre-gl';
import type { GeoJSONSource, Map as MapInstance } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type { FeatureCollection } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import { places, searchPlaces, type Place } from './places';
import { Buildings, buildingControls } from './buildings';
import { Landmarks, landmarkControls, type SearchPlace } from './landmarks';
import { Roads } from './roads';
import { RenewalZones } from './renewal-zones';
import { ScaleReferences } from './scale-references';
import { StreetView } from './street-view';
import { isCloseView, queryBounds } from './view-window';
import { basemapSource, basemapLayers, basemapIds, basemapRoadIds } from './basemap';
import type { CityModels } from './city-models';
import { GREENERY_DECORATION_NOTICE, type DecorativeTree, type GreeneryInput } from './greenery';

type Bookmark = { id: string; name: string; lon: number; lat: number };
type ElevationResult = {
  query: [number, number];
  nearest: { id: string; coordinate: [number, number]; height_m: number; distance_m: number } | null;
  method: string;
};
type MapData = FeatureCollection & { metadata?: { contours?: number; spots?: number; contour_interval_m?: number; simplified_m?: number; truncated?: boolean; spots_sampled?: boolean; points_hidden_at_zoom?: boolean } };
type TerrainMetadata = { tiles: string[]; coverage_tiles?: string[]; source_hull_url?: string; bounds: [number, number, number, number]; minzoom: number; maxzoom: number; encoding: 'mapbox' | 'terrarium'; tileSize: number; method?: string };

const icons = {
  contour: '<svg viewBox="0 0 38 38" fill="none" aria-hidden="true"><path d="M2 30C3 18 8 7 21 8s16 14 15 23M8 30c1-12 6-17 14-16s10 7 9 16M14 29c1-6 3-10 9-9s4 7 3 10" stroke="currentColor" stroke-width="1.8"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>',
};
const empty = (): FeatureCollection => ({ type: 'FeatureCollection', features: [] });
const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector<T>(selector)!;
const escape = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
maplibregl.setWorkerUrl(workerUrl);

$('#app').innerHTML = `
  <header class="topbar">
    <div class="identity"><span class="brandmark">${icons.contour}</span><h1>서울 높낮이</h1></div>
    <div class="top-actions"><div class="mode-switch" role="group" aria-label="지도 보기 모드"><button id="mode-2d" class="active" aria-pressed="true">2D 지도</button><button id="mode-25d" aria-pressed="false" disabled>2.5D 지형</button><button id="mode-eye" aria-pressed="false" disabled>사람 1인칭</button></div><button id="mobile-panel" class="mobile-only" aria-expanded="false" aria-controls="sidebar">지도 설정</button></div>
  </header>
  <div class="workspace">
    <aside id="sidebar" class="sidebar" aria-label="지도 탐색 및 높이 조회">
      <div class="sidebar-heading"><span>EXPLORE SEOUL</span><button id="close-panel" class="icon-button mobile-only" aria-label="지도 설정 닫기">${icons.close}</button></div>
      <section class="search-section">
        <label class="field-label" for="place-search">동네 · 역 · 아파트 찾기</label>
        <form id="search-form"><div class="search-input">${icons.search}<input id="place-search" type="search" autocomplete="off" placeholder="동네, 역, 아파트·건물 이름" aria-controls="search-results"/><button type="submit" aria-label="장소 찾기">찾기</button></div></form>
        <div id="search-results" class="search-results" aria-live="polite"></div>
        <p id="search-help" class="muted search-help">이름이 등록된 장소 검색 · 위도, 경도 입력도 가능</p>
      </section>
      <section id="terrain-settings" class="terrain-settings" hidden>
        <div class="section-heading"><h2>언덕 높이 강조</h2><span class="estimate-tag">화면 배율</span></div>
        <label class="slider-label" for="exaggeration">지형 높이 <output id="exaggeration-value">4×</output></label><input id="exaggeration" type="range" min="1" max="8" step="0.5" value="4"/>
        <div class="scale-presets" role="group" aria-label="지형 강조 빠른 선택"><button data-scale="1">1×</button><button data-scale="4" class="selected">4× 기본</button><button data-scale="6">6×</button><button data-scale="8">8×</button></div>
        <label class="slider-label" for="pitch">기울기 <output id="pitch-value">58°</output></label><input id="pitch" type="range" min="20" max="85" value="58"/>
        <p class="muted">지형만 강조합니다. 건물 높이와 고도 숫자는 원본 값입니다.</p>
      </section>
      ${landmarkControls}
      <section class="roads-section">
        <div class="section-heading"><h2>차도와 보행로</h2><span class="small-label">종류별 표시</span></div>
        <label class="layer-row"><span class="legend-road"></span><span>차도</span><input id="toggle-roads" type="checkbox" checked aria-label="차도 표시"/></label>
        <label class="layer-row"><span class="legend-walkway"></span><span>보도·보행로</span><input id="toggle-walkways" type="checkbox" checked aria-label="보도·보행로 표시"/></label>
        <label class="layer-row"><span class="legend-steps"></span><span>계단</span><input id="toggle-steps" type="checkbox" checked aria-label="계단 표시"/></label>
        <p id="road-status" class="muted" role="status">도로 자료를 불러오는 중…</p>
        <details class="road-source"><summary>도로 자료 안내</summary><p class="muted">별도 선으로 등록된 보도·보행로를 구분합니다. 선이 없는 곳도 실제 인도가 있을 수 있습니다.</p><p id="road-source-date" class="muted"></p></details>
      </section>
      ${buildingControls}
      <section class="first-person-section">
        <div class="section-heading"><h2>거리 크기 가늠하기</h2><button id="show-uphill" class="text-button">사람 1인칭 예시</button></div>
        <p class="muted">눈높이 약 1.7m에서 길을 따라 3m씩 이동합니다.</p>
        <label class="layer-row"><span>1인칭에서 크기 비교 모형</span><input id="toggle-scale-references" type="checkbox" checked aria-label="1인칭 크기 비교 모형 표시"/></label>
        <p id="scale-reference-status" class="muted" role="status">사람 1인칭 모드에서만 표시합니다.</p>
        <details class="source-details"><summary>눈높이와 모형 크기</summary><p>사람 키 1.7m, 승용차 길이 4.3m·너비 1.8m·높이 1.5m를 기준으로 고정된 비교 모형을 놓습니다. 실제 사람이나 주차된 차량의 위치를 나타내지는 않습니다.</p><p>이 모드의 지형 배율은 1×입니다. 지면은 등고선·표고점에서 보간했으므로 계단·옹벽·교량 같은 세부 높이와는 차이가 있을 수 있습니다.</p></details>
      </section>
      <section class="city-models-section">
        <div class="section-heading"><h2>주요 빌딩 · 나무</h2><span class="small-label">2.5D</span></div>
        <label class="layer-row"><span>주요 빌딩 모형</span><input id="toggle-city-models" type="checkbox" checked aria-label="주요 빌딩 모형 표시"/></label>
        <p id="city-model-status" class="muted" role="status">빌딩 모형 준비 중…</p>
        <label class="layer-row"><span>숲에 나무 표현</span><input id="toggle-trees" type="checkbox" checked aria-label="숲 나무 표시"/></label>
        <p id="tree-status" class="muted" role="status"></p>
        <details class="source-details"><summary>모형의 치수와 표현</summary><p>롯데월드타워·63빌딩·N서울타워·트레이드타워는 공개 높이와 지도 외곽선을 참고해 만든 Blender 모형입니다. 창문·재질·세부 외형은 재구성했습니다.</p><p>${GREENERY_DECORATION_NOTICE}</p></details>
      </section>
      <section class="layers-section">
        <div class="section-heading"><h2>지도에 표시</h2><button id="show-seoul" class="text-button">서울 전체</button></div>
        <label class="layer-row"><span class="legend-line"></span><span>등고선 <small>원본 높이</small></span><input id="toggle-contours" type="checkbox" checked aria-label="등고선 표시"/></label>
        <div class="interval-row"><label for="interval">선의 높이 간격</label><select id="interval"><option value="5">5 m</option><option value="10">10 m</option><option value="25">25 m</option></select></div>
        <label class="layer-row"><span class="legend-dot"></span><span>표고점 <small>지점별 높이</small></span><input id="toggle-spots" type="checkbox" checked aria-label="표고점 표시"/></label>
        <label class="layer-row"><span class="legend-hill"></span><span>지형 음영 <small>보간한 지형</small></span><input id="toggle-shade" type="checkbox" checked aria-label="지형 음영 표시"/></label>
        <label class="layer-row"><span class="legend-base"></span><span>강·공원·녹지</span><input id="toggle-base" type="checkbox" checked aria-label="배경지도 표시"/></label>
        <div class="interval-row"><label for="render-quality">화면 선명도</label><select id="render-quality"><option value="1">가볍게</option><option value="1.25" selected>균형</option><option value="2">선명하게</option></select></div>
        <p id="close-layer-note" class="muted" hidden>거리 시점에서는 등고선·표고점·건물 테두리를 잠시 숨깁니다.</p><p id="density-note" class="muted">확대하면 더 촘촘한 등고선이 보입니다.</p><p id="coverage-note" class="muted" hidden><span class="coverage-swatch"></span>회색: 보간 지형을 뒷받침할 자료가 부족한 곳</p>
      </section>
      <section class="inspect-section">
        <div class="section-heading"><h2>높이 읽기</h2><span id="inspect-kind" class="small-label">원본 데이터</span></div>
        <div id="inspection" aria-live="polite"><div class="empty-inspection"><span class="crosshair-glyph">+</span><p>지도에서 한 지점을 눌러보세요.</p><small>가까운 표고점의 높이와 거리를 보여줍니다.</small></div></div>
        <form id="save-form" hidden><input id="bookmark-name" aria-label="저장할 위치 이름" maxlength="80" placeholder="이 위치의 이름"/><button type="submit">위치 저장</button></form>
        <p id="save-status" class="muted" aria-live="polite"></p>
      </section>
      <section class="bookmarks-section"><div class="section-heading"><h2>저장한 위치</h2><span id="bookmark-count" class="small-label">0</span></div><div id="bookmarks"><p class="muted">저장한 위치는 이 컴퓨터에 남습니다.</p></div></section>
      <details class="source-details"><summary>자료 출처와 읽는 방법</summary><p>서울특별시 · 국토지리정보원<br/>2023년 기준 수치지형도 / 첨부 갱신 2025.03</p><p>원본 등고선은 5m 간격입니다. 간격은 측량 오차를 뜻하지 않습니다. 평지·자료 공백을 선의 개수만으로 판단하지 마세요.</p><p>표고점의 수직 기준과 실제 지면 오차는 추가 확인이 필요합니다. 최근 공사·옹벽·교량 상판은 다를 수 있습니다.</p><a href="https://data.seoul.go.kr/dataList/OA-22241/F/1/datasetView.do" target="_blank" rel="noreferrer">서울시 원본 자료 보기 ↗</a><p>공공누리 제1유형 · 출처 표시<br/>배경지도: OpenFreeMap · OpenMapTiles · © OpenStreetMap 기여자</p><p>등고선·DB·2.5D 지형은 로컬 파일입니다. 강·공원·도로 배경과 지도 글꼴은 인터넷을 사용합니다. 장소 핀과 상세 보행로는 로컬 자료입니다.</p><p>아파트 단지·전체 세대수: 서울특별시 공동주택통합정보마당 · 공공누리 제1유형</p><a href="https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do" target="_blank" rel="noreferrer">공식 공동주택 자료 ↗</a></details>
    </aside>
    <main class="map-wrap">
      <div id="map" aria-label="서울 등고선 지도"></div>
      <div class="map-tools" role="group" aria-label="지도 표시 빠른 선택"><button id="quick-buildings" aria-pressed="true">건물</button><button id="quick-roads" aria-pressed="true">차도</button><button id="quick-walkways" aria-pressed="true">보행로</button><button id="quick-landmarks" aria-pressed="true">장소 핀</button></div>
      <div id="eye-controls" class="eye-controls" hidden><span id="eye-status" role="status"></span><small id="eye-scale-note" hidden>고정 모형 · 사람 키 1.7m · 차 길이 4.3m</small><div><button id="eye-back" aria-label="길을 따라 3m 뒤로">뒤로</button><button id="eye-forward" aria-label="길을 따라 3m 앞으로">앞으로 3m</button><button id="eye-left" aria-label="왼쪽으로 보기">↶</button><button id="eye-right" aria-label="오른쪽으로 보기">↷</button><button id="eye-exit">지도 시점</button></div></div>
      <div class="sr-only" role="status" aria-live="polite"><span id="place-title"></span><span id="place-subtitle"></span></div>
      <div id="terrain-badge" class="terrain-badge" hidden>지형 <span id="terrain-badge-scale">4×</span></div>
      <div class="map-legend" aria-label="지도 범례"><span><i class="legend-line"></i>5 m 등고선</span><span><i class="legend-line major"></i>25 m 기준선</span><span><i class="legend-dot"></i>표고점</span></div>
      <div id="map-notice" class="map-notice" role="status">로컬 높이 데이터를 불러오는 중…</div>
      <div class="map-bottom"><span id="coordinate-readout">중심 37.50100° N · 126.94800° E</span><span id="data-status" role="status">DB 연결 중</span></div>
    </main>
  </div>`;

// Move the existing nodes, preserving IDs used by metadata updates and controls.
// Selected-place details and live layer status stay next to their controls.
const dataInformation = document.createElement('details');
dataInformation.id = 'data-information';
dataInformation.className = 'source-details data-information';
dataInformation.innerHTML = '<summary>자료 정보</summary>';
const informationGroups: [string, string][] = [
  ['장소 검색', '#search-help'],
  ['지형', '.terrain-settings > p, #density-note, #coverage-note'],
  ['장소 · 아파트', '.landmarks-section > p:not([role="status"])'],
  ['도로', '.road-source'],
  ['건물', '.buildings-section > p.muted:not([role="status"]), .building-source'],
  ['빌딩 · 나무 모형', '.city-models-section > .source-details'],
  ['사람 1인칭 · 크기 비교', '.first-person-section > .source-details'],
  ['출처 · 이용 안내', '#sidebar > .source-details'],
];
for (const [title, selector] of informationGroups) {
  const section = document.createElement('section');
  const heading = document.createElement('h3');
  heading.textContent = title;
  section.append(heading);
  for (const node of document.querySelectorAll(selector)) {
    if (node instanceof HTMLDetailsElement) {
      section.append(...Array.from(node.children).filter(child => child.tagName !== 'SUMMARY'));
      node.remove();
    } else section.append(node);
  }
  if (section.childElementCount > 1) dataInformation.append(section);
}
$('#sidebar').append(dataInformation);
document.querySelectorAll('.landmarks-section > .section-heading .small-label, .roads-section > .section-heading .small-label, .buildings-section > .section-heading .small-label').forEach(node => node.remove());

let map: MapInstance;
let buildings: Buildings;
let landmarks: Landmarks;
let renewalZones: RenewalZones | undefined;
let roads: Roads;
let scaleReferences: ScaleReferences;
let streetView: StreetView;
let previousStreetScale = 4;
let previousStreetMode = true;
let cityModels: CityModels;
let modelPlaces: SearchPlace[] = [];
let greeneryTimer: ReturnType<typeof setTimeout>;
let greeneryController: AbortController | undefined;
let greeneryKey = '';
let greeneryRevision = 0;
const exclusionCache = new Map<string, { buildings: FeatureCollection; roads: FeatureCollection }>();
const exclusionRequests = new Map<string, Promise<{ buildings: FeatureCollection; roads: FeatureCollection }>>();
const treeCache = new Map<string, DecorativeTree[]>();
let treeWorker: Worker | undefined;
let treeJob = 0;
const treeJobs = new Map<number, (trees: DecorativeTree[]) => void>();
let searchController: AbortController | null = null;
let searchTimer: ReturnType<typeof setTimeout>;
let searchRequest = 0;
let mapLoaded = false;
let terrainReady = false;
let is25d = false;
let targetPitch = 58;
let modeChosen = false;
let selectedCoordinate: [number, number] | null = null;
let lastData: MapData = empty();
let featureController: AbortController | null = null;
let elevationController: AbortController | null = null;
let loadTimer: ReturnType<typeof setTimeout>;
let lastFeatureRequest = 0;
let lastFeatureKey = '';
let elevationRequest = 0;
let basemapWarning = false;
let currentPlace = places[2];
const marks: maplibregl.Marker[] = [];

function notice(message: string, error = false) {
  const node = $('#map-notice');
  node.textContent = message;
  node.classList.toggle('error', error);
  node.hidden = !message;
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function source(id: string) { return map.getSource(id) as GeoJSONSource; }
function setLayerVisible(id: string, visible: boolean) {
  if (!map.getLayer(id)) return;
  const next = visible ? 'visible' : 'none';
  if ((map.getLayoutProperty(id, 'visibility') ?? 'visible') !== next) map.setLayoutProperty(id, 'visibility', next);
}

async function loadContextMetadata() {
  const results = await Promise.allSettled([
    request<{ available: boolean; total_count: number; official_apartments?: { official_complex_count_ge400: number; mapped_complex_count_ge400: number; source_date: string }; sources?: { kind: string; osm_timestamp?: string }[] }>('/api/places/meta'),
    request<{ source_osm_timestamp?: string }>('/api/roads/meta'),
  ]);
  const [placeResult, roadResult] = results;
  if (placeResult.status === 'fulfilled' && placeResult.value.available) {
    $('#search-help').textContent = `${placeResult.value.total_count.toLocaleString()}개 등록 이름 검색 · 서울 좌표 이동`;
    const timestamp = placeResult.value.sources?.find(source => source.kind === 'osm_overpass')?.osm_timestamp;
    if (timestamp) $('#landmark-source-date').textContent = `장소 핀: OpenStreetMap · ${timestamp.slice(0, 10)} 기준`;
    const apartments = placeResult.value.official_apartments;
    if (apartments) $('#apartment-coverage').textContent = `400세대 이상 아파트·주상복합 ${apartments.official_complex_count_ge400.toLocaleString()}개 등록 · ${apartments.mapped_complex_count_ge400.toLocaleString()}개 위치 연결 · 서울시 ${apartments.source_date}. 세대수는 관리 단지 코드별 기록입니다.`;
  }
  if (roadResult.status === 'fulfilled' && roadResult.value.source_osm_timestamp) $('#road-source-date').textContent = `OpenStreetMap · ${roadResult.value.source_osm_timestamp.slice(0, 10)} 기준`;
}

function applyVisibility() {
  if (!mapLoaded) return;
  const contours = $('#toggle-contours') as HTMLInputElement;
  const spots = $('#toggle-spots') as HTMLInputElement;
  const close = isCloseView(map);
  for (const id of ['contours', 'contour-labels']) setLayerVisible(id, contours.checked && !close);
  for (const id of ['spots', 'spot-labels']) setLayerVisible(id, spots.checked && !close);
  setLayerVisible('selection-link-line', !close);
  setLayerVisible('hillshade', ($('#toggle-shade') as HTMLInputElement).checked && !close);
  const showCoverage = is25d || ($('#toggle-shade') as HTMLInputElement).checked;
  setLayerVisible('terrain-coverage', showCoverage);
  $('#coverage-note').hidden = !map.getLayer('terrain-coverage') || !showCoverage;
  const base = ($('#toggle-base') as HTMLInputElement).checked;
  const localStreetsReady = close && (roads?.getData().features.length ?? 0) > 0;
  for (const id of basemapIds) setLayerVisible(id, basemapRoadIds.includes(id) ? ($('#toggle-roads') as HTMLInputElement).checked && !localStreetsReady : base);
  cityModels?.setTreesVisible(base && ($('#toggle-trees') as HTMLInputElement).checked);
  $('.map-legend').classList.toggle('no-contours', !contours.checked);
  $('.map-legend').hidden = close;
  $('#close-layer-note').hidden = !close;
}

function updateModelVisibility() {
  const enabled = ($('#toggle-buildings') as HTMLInputElement).checked;
  const apartmentsOnly = ($('#apartments-only') as HTMLInputElement).checked;
  cityModels?.setVisible(enabled && !apartmentsOnly && ($('#toggle-city-models') as HTMLInputElement).checked);
  ($('#toggle-city-models') as HTMLInputElement).disabled = !enabled || apartmentsOnly;
}

function scheduleGreenery() { clearTimeout(greeneryTimer); greeneryTimer = setTimeout(() => void loadGreenery(), 300); }

function generateTrees(input: GreeneryInput): Promise<DecorativeTree[]> {
  if (!treeWorker) {
    treeWorker = new Worker(new URL('./greenery.worker.ts', import.meta.url), { type: 'module' });
    treeWorker.onmessage = ({ data }) => { treeJobs.get(data.id)?.(data.trees); treeJobs.delete(data.id); };
    treeWorker.onerror = () => { for (const resolve of treeJobs.values()) resolve([]); treeJobs.clear(); treeWorker?.terminate(); treeWorker = undefined; };
  }
  const id = ++treeJob;
  return new Promise(resolve => { treeJobs.set(id, resolve); treeWorker!.postMessage({ id, input }); });
}

function loadExclusions(bbox: string) {
  const cached = exclusionCache.get(bbox);
  if (cached) return Promise.resolve(cached);
  const pending = exclusionRequests.get(bbox);
  if (pending) return pending;
  const promise = request<{ buildings: FeatureCollection; roads: FeatureCollection }>(`/api/greenery?bbox=${bbox}`).then(data => {
    exclusionCache.set(bbox, data);
    if (exclusionCache.size > 3) exclusionCache.delete(exclusionCache.keys().next().value!);
    return data;
  }).finally(() => exclusionRequests.delete(bbox));
  exclusionRequests.set(bbox, promise);
  return promise;
}

async function loadGreenery() {
  if (!mapLoaded || !cityModels || map.isMoving()) return;
  if (!is25d || map.getZoom() < 14.8 || !($('#toggle-trees') as HTMLInputElement).checked || !($('#toggle-base') as HTMLInputElement).checked) {
    greeneryController?.abort(); greeneryKey = ''; cityModels.setTrees([]);
    $('#tree-status').textContent = !is25d ? '나무 모형은 2.5D에서 보입니다.' : '숲은 녹색으로 표시하며, 확대하면 나무 모형이 보입니다.';
    return;
  }
  const greenery: FeatureCollection = { type: 'FeatureCollection', features: map.querySourceFeatures('osm', { sourceLayer: 'landcover', filter: ['==', ['get', 'class'], 'wood'] }).map(feature => ({ type: 'Feature', properties: { class: feature.properties.class }, geometry: feature.geometry })) };
  const c = map.getCenter();
  const lon = Math.round(c.lng / .0025) * .0025, lat = Math.round(c.lat / .002) * .002;
  // Independent exclusion queries keep trees off buildings and paths even when
  // their display switches are off. Only this small, fully returned area is used.
  const bounds: [number, number, number, number] = [lon - .009, lat - .0072, lon + .009, lat + .0072];
  const bbox = bounds.map(n => n.toFixed(6)).join(',');
  const key = `${bbox}:${greeneryRevision}:${greenery.features.length}`;
  if (greeneryKey === key) return;
  greeneryKey = key; greeneryController?.abort();
  const cached = treeCache.get(key);
  if (cached) { cityModels.setTrees(cached); $('#tree-status').textContent = cached.length ? `숲 안의 장식 나무 ${cached.length}그루 · 개별 나무 실측 자료 아님` : '숲 영역은 녹색으로 표시합니다.'; return; }
  if (!greenery.features.length) { cityModels.setTrees([]); $('#tree-status').textContent = '이 화면에서 불러온 숲 영역이 없습니다.'; return; }
  const controller = new AbortController(); greeneryController = controller;
  try {
    const data = await loadExclusions(bbox);
    if (controller.signal.aborted || key !== greeneryKey) return;
    const trees = await generateTrees({ greenery, buildings: data.buildings, roads: data.roads, bounds, exclusionsReady: true });
    if (controller.signal.aborted || key !== greeneryKey) return;
    treeCache.set(key, trees);
    if (treeCache.size > 6) treeCache.delete(treeCache.keys().next().value!);
    cityModels.setTrees(trees);
    $('#tree-status').textContent = trees.length ? `숲 안의 장식 나무 ${trees.length}그루 · 개별 나무 실측 자료 아님` : '숲 영역은 녹색으로 표시합니다.';
  } catch (error) {
    if (controller.signal.aborted) return;
    greeneryKey = ''; $('#tree-status').textContent = '나무 배치 영역을 확인하지 못했습니다. 녹지 면은 계속 표시합니다.';
  }
}

async function loadCityModels() {
  const { CityModels } = await import('./city-models');
  cityModels = new CityModels(map, {
    onState: state => { $('#city-model-status').textContent = state.message; },
    onActiveFootprints: ids => buildings.setModelFootprints(ids),
  });
  const manifest = await request<{ assets: { id: string; nameKo: string; coordinate: { lon: number; lat: number }; dimensions: number[]; referenceUrl: string }[] }>('/models/manifest.json');
  modelPlaces = manifest.assets.map(asset => ({ id: `model:${asset.id}`, name: asset.nameKo, subtitle: `주요 빌딩 모형 · 공개 높이 ${asset.dimensions[1]} m`, center: [asset.coordinate.lon, asset.coordinate.lat], zoom: asset.dimensions[1] > 400 ? 15.3 : 16, kind: 'building', source_url: asset.referenceUrl }));
  const matches = await request<Record<string, string[]>>('/models/footprint-matches.json');
  cityModels.setFootprintMatches(matches);
  await cityModels.init();
  cityModels.setMode(is25d); updateModelVisibility(); applyVisibility(); scheduleGreenery();
}

function loadFeaturesSoon() { clearTimeout(loadTimer); loadTimer = setTimeout(loadFeatures, 170); }

async function loadFeatures() {
  if (!mapLoaded) return;
  featureController?.abort();
  featureController = new AbortController();
  const requestId = ++lastFeatureRequest;
  const bbox = queryBounds(map);
  const interval = $('#interval') as HTMLSelectElement;
  const params = new URLSearchParams({ bbox: bbox.map(v => v.toFixed(6)).join(','), zoom: Math.min(22, map.getZoom()).toFixed(2), interval: interval.value, points: ($('#toggle-spots') as HTMLInputElement).checked ? '1' : '0' });
  if (params.toString() === lastFeatureKey) return;
  $('#data-status').textContent = '영역 조회 중…';
  try {
    const data = await request<MapData>(`/api/features?${params}`, { signal: featureController.signal });
    if (requestId !== lastFeatureRequest) return;
    lastData = data;
    lastFeatureKey = params.toString();
    source('elevation-data').setData(data);
    const countContours = data.metadata?.contours ?? data.features.filter(f => f.properties?.kind === 'contour').length;
    const countSpots = data.metadata?.spots ?? data.features.filter(f => f.properties?.kind === 'spot').length;
    const actualInterval = data.metadata?.contour_interval_m ?? Number(interval.value);
    $('#data-status').textContent = `등고선 ${countContours.toLocaleString()} · 표고점 ${countSpots.toLocaleString()}`;
    $('#density-note').textContent = `현재 ${actualInterval}m 간격 표시${map.getZoom() < 13 ? ' · 확대하면 5m 선과 표고점이 보입니다.' : ' · 굵은 선은 25m 배수입니다.'}${data.metadata?.spots_sampled ? ' 표고점은 겹치지 않도록 일부 표시합니다.' : ''}${data.metadata?.simplified_m ? ' 선 모양은 확대 수준에 맞춰 단순화합니다.' : ''}`;
    $('.map-legend span:first-child').innerHTML = `<i class="legend-line"></i>${actualInterval} m 등고선`;
    if (data.metadata?.truncated) notice('표시량을 제한했습니다. 확대하면 더 자세한 자료가 보입니다.');
    else if (!data.features.length) notice('이 화면 범위에 표시할 원본 자료가 없습니다.');
    else if (basemapWarning && ($('#toggle-base') as HTMLInputElement).checked) notice('도로 배경 연결이 원활하지 않습니다. 로컬 높이 자료는 계속 볼 수 있습니다.');
    else notice('');
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return;
    if (requestId !== lastFeatureRequest) return;
    $('#data-status').textContent = 'DB 조회 실패';
    lastFeatureKey = '';
    source('elevation-data').setData(empty());
    notice('높이 자료를 불러오지 못했습니다. 로컬 API 서버 연결을 확인해 주세요.', true);
  }
}

async function loadTerrain() {
  try {
    const metadata = await request<TerrainMetadata>('/data/terrain.json');
    map.addSource('local-terrain', {
      type: 'raster-dem',
      tiles: metadata.tiles.map(tile => new URL(tile, location.origin).href.replaceAll('%7B', '{').replaceAll('%7D', '}')),
      bounds: metadata.bounds, minzoom: metadata.minzoom, maxzoom: metadata.maxzoom,
      tileSize: metadata.tileSize, encoding: metadata.encoding,
      attribution: '지형: 서울시 원본 등고선·표고점으로 보간',
    });
    map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'local-terrain', paint: { 'hillshade-exaggeration': 0.48, 'hillshade-shadow-color': '#47535b', 'hillshade-highlight-color': '#ffffff', 'hillshade-accent-color': '#a5acae' } }, 'contours');
    if (metadata.coverage_tiles) {
      map.addSource('terrain-coverage', { type: 'raster', tiles: metadata.coverage_tiles.map(tile => new URL(tile, location.origin).href.replaceAll('%7B', '{').replaceAll('%7D', '}')), bounds: metadata.bounds, minzoom: metadata.minzoom, maxzoom: metadata.maxzoom, tileSize: metadata.tileSize });
      map.addLayer({ id: 'terrain-coverage', type: 'raster', source: 'terrain-coverage', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.8, 'raster-fade-duration': 0 } }, 'contours');
      $('#coverage-note').hidden = false;
    }
    terrainReady = true;
    ($('#mode-25d') as HTMLButtonElement).disabled = false;
    ($('#mode-eye') as HTMLButtonElement).disabled = false;
    if (!modeChosen) changeMode(true);
    else applyVisibility();
  } catch {
    ($('#mode-25d') as HTMLButtonElement).title = '로컬 지형 파일이 준비되지 않았습니다.';
    ($('#toggle-shade') as HTMLInputElement).disabled = true;
    notice('등고선은 준비됐습니다. 2.5D 지형 파일은 아직 준비되지 않았습니다.');
  }
}

function changeMode(next: boolean) {
  if (!mapLoaded || (next && !terrainReady)) return;
  const view = { center: map.getCenter().toArray() as [number, number], zoom: map.getZoom() };
  streetView?.exit(false);
  map.setCenterClampedToGround(true);
  is25d = next;
  const exaggeration = Number(($('#exaggeration') as HTMLInputElement).value);
  map.setTerrain(next ? { source: 'local-terrain', exaggeration } : null);
  map.easeTo({ ...view, pitch: next ? targetPitch : 0, bearing: next ? -24 : 0, duration: reduceMotion ? 0 : 650 });
  for (const [id, active] of [['#mode-2d', !next], ['#mode-25d', next]] as const) {
    $(id).classList.toggle('active', active); $(id).setAttribute('aria-pressed', String(active));
  }
  $('#terrain-settings').hidden = !next;
  $('#terrain-badge').hidden = !next;
  buildings?.setMode(next);
  cityModels?.setMode(next);
  scheduleGreenery();
  applyVisibility();
}

function moveTo(place: SearchPlace) {
  streetView?.exit(false);
  currentPlace = place;
  $('#place-title').textContent = place.name;
  $('#place-subtitle').textContent = place.subtitle;
  clearTimeout(searchTimer); searchController?.abort(); ++searchRequest;
  $('#search-results').replaceChildren();
  // A following mode switch must not interrupt navigation halfway to a named place.
  map.jumpTo({ center: place.center, zoom: place.zoom, pitch: is25d ? targetPitch : 0 });
  if (place.id) landmarks?.select(place);
  if (place.building_id) void buildings.inspectById(place.building_id, place.center);
  if (window.innerWidth <= 760) setPanel(Boolean(place.building_id));
}

async function updateSearch(submit = false) {
  clearTimeout(searchTimer); searchController?.abort(); const id = ++searchRequest;
  const value = ($('#place-search') as HTMLInputElement).value;
  const container = $('#search-results'); container.replaceChildren();
  if (!value.trim()) return;
  searchController = new AbortController();
  const normalized = value.trim().replace(/\s+/g, '').toLowerCase();
  const local = [...modelPlaces.filter(place => place.name.replace(/\s+/g, '').toLowerCase().includes(normalized)), ...searchPlaces(value)];
  let remote: SearchPlace[] = [], failed = false;
  container.innerHTML = '<p>장소를 찾는 중…</p>';
  try {
    const data = await request<{ results: SearchPlace[] }>(`/api/places?${new URLSearchParams({ q: value, limit: '12' })}`, { signal: searchController.signal });
    remote = data.results;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return;
    failed = true;
  }
  if (id !== searchRequest) return;
  const seen = new Set<string>();
  const results = [...local, ...remote].filter(place => {
    const key = `${place.name}:${place.center.map(v => v.toFixed(3)).join(',')}`;
    if (seen.has(key)) return false; seen.add(key); return true;
  }).slice(0, 12);
  if (submit && results.length) { moveTo(results[0]); return; }
  container.replaceChildren();
  if (!results.length) {
    container.innerHTML = failed ? '<p>장소 검색 서버에 연결하지 못했습니다. 위도, 경도를 입력하면 이동할 수 있습니다.</p>' : '<p>등록된 이름에서 찾지 못했습니다. 이름 일부나 가까운 역·동네 이름으로 찾아보세요.</p>';
    return;
  }
  for (const place of results) {
    const button = document.createElement('button');
    button.type = 'button'; button.innerHTML = `<strong>${escape(place.name)}</strong><small>${escape(place.subtitle)}</small>`;
    button.addEventListener('click', () => moveTo(place)); container.append(button);
  }
  if (failed) { const note = document.createElement('p'); note.textContent = '검색 서버 연결이 없어 입력한 좌표로 이동합니다.'; container.append(note); }
}

function clearMarkers() { for (const marker of marks.splice(0)) marker.remove(); }
function mark(coordinate: [number, number], className: string) {
  const element = document.createElement('div'); element.className = className;
  marks.push(new maplibregl.Marker({ element }).setLngLat(coordinate).addTo(map));
}

async function inspect(coordinate: [number, number], featureHeight?: number, kind?: string) {
  buildings?.clearSelection();
  elevationController?.abort(); elevationController = new AbortController();
  const id = ++elevationRequest;
  selectedCoordinate = coordinate;
  clearMarkers(); mark(coordinate, 'query-marker');
  source('selection-link').setData(empty());
  $('#save-form').hidden = true;
  $('#save-status').textContent = '';
  $('#inspection').innerHTML = '<p class="muted">가까운 표고점을 확인하는 중…</p>';
  const exactContour = kind === 'contour' && Number.isFinite(featureHeight);
  try {
    const result = await request<ElevationResult>(`/api/elevation?lon=${coordinate[0]}&lat=${coordinate[1]}`, { signal: elevationController.signal });
    if (id !== elevationRequest) return;
    const nearest = result.nearest;
    $('#inspect-kind').textContent = exactContour ? '선택한 등고선' : '가까운 원본 표고점';
    const coordinateText = `${coordinate[1].toFixed(5)}, ${coordinate[0].toFixed(5)}`;
    let markup = '';
    if (exactContour) markup += `<div class="elevation-value">${featureHeight!.toFixed(0)}<span>m</span></div><p class="reading-label">선택한 원본 등고선의 높이</p>`;
    if (nearest) {
      if (!exactContour) markup += `<div class="elevation-value">${nearest.height_m.toFixed(2)}<span>m</span></div><p class="reading-label">가까운 표고점에 기록된 높이</p>`;
      else markup += `<p class="nearby-reading">주변 표고점 <strong>${nearest.height_m.toFixed(2)} m</strong></p>`;
      markup += `<p class="distance-reading">선택 위치에서 <strong>${nearest.distance_m.toFixed(0)}m</strong> 떨어진 점입니다.</p><p class="muted">${exactContour ? '원본 선과 점의 높이를 함께 표시합니다.' : '선택한 위치 자체의 높이를 뜻하지 않습니다.'}</p>`;
      mark(nearest.coordinate, 'source-marker');
      source('selection-link').setData({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [coordinate, nearest.coordinate] } }] });
    } else markup += '<p class="no-data">1km 이내에서 표고점을 찾지 못했습니다.</p><p class="muted">자료가 없는 위치의 높이는 표시하지 않습니다.</p>';
    markup += `<p class="selected-coordinate">선택 좌표 ${coordinateText}</p>`;
    $('#inspection').innerHTML = markup;
    ($('#bookmark-name') as HTMLInputElement).value = `${currentPlace.name}에서 선택한 위치`;
    $('#save-form').hidden = false;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return;
    if (id !== elevationRequest) return;
    $('#inspection').innerHTML = '<p class="no-data">표고점 조회에 실패했습니다. 다시 선택해 주세요.</p>';
  }
}

async function loadBookmarks() {
  try {
    const { bookmarks } = await request<{ bookmarks: Bookmark[] }>('/api/bookmarks');
    $('#bookmark-count').textContent = String(bookmarks.length);
    $('#bookmarks').replaceChildren();
    if (!bookmarks.length) $('#bookmarks').innerHTML = '<p class="muted">저장한 위치는 이 컴퓨터에 남습니다.</p>';
    for (const bookmark of bookmarks) {
      const row = document.createElement('div'); row.className = 'bookmark-row';
      const go = document.createElement('button'); go.className = 'bookmark-go'; go.textContent = bookmark.name;
      go.addEventListener('click', () => { moveTo({ name: bookmark.name, subtitle: '이 컴퓨터에 저장한 위치', center: [bookmark.lon, bookmark.lat], zoom: 15 }); void inspect([bookmark.lon, bookmark.lat]); });
      const remove = document.createElement('button'); remove.className = 'bookmark-remove'; remove.setAttribute('aria-label', `${bookmark.name} 삭제`); remove.innerHTML = icons.close;
      remove.addEventListener('click', async () => {
        try { await request(`/api/bookmarks/${bookmark.id}`, { method: 'DELETE' }); await loadBookmarks(); }
        catch { $('#save-status').textContent = '삭제에 실패했습니다.'; }
      });
      row.append(go, remove); $('#bookmarks').append(row);
    }
  } catch { $('#bookmarks').innerHTML = '<p class="muted">저장 목록에 연결하지 못했습니다.</p>'; }
}

function setPanel(open: boolean) {
  $('#sidebar').classList.toggle('open', open);
  $('#mobile-panel').setAttribute('aria-expanded', String(open));
}

$('#search-form').addEventListener('submit', event => { event.preventDefault(); updateSearch(true); });
$('#place-search').addEventListener('input', () => { clearTimeout(searchTimer); searchController?.abort(); ++searchRequest; searchTimer = setTimeout(() => void updateSearch(), 180); });
$('#show-seoul').addEventListener('click', () => {
  streetView?.exit(false);
  clearTimeout(searchTimer); searchController?.abort(); ++searchRequest;
  $('#search-results').replaceChildren();
  $('#place-title').textContent = '서울 전체'; $('#place-subtitle').textContent = '원본 자료가 포함된 서울의 지형';
  map.fitBounds([[126.77, 37.425], [127.195, 37.707]], { padding: 65, duration: 0, pitch: is25d ? 35 : 0 });
  if (window.innerWidth <= 760) setPanel(false);
});
$('#mode-2d').addEventListener('click', () => { modeChosen = true; changeMode(false); });
$('#mode-25d').addEventListener('click', () => { modeChosen = true; changeMode(true); });
$('#mode-eye').addEventListener('click', () => { modeChosen = true; void streetView.enter(); });
$('#interval').addEventListener('change', loadFeaturesSoon);
for (const [quick, control] of [['quick-buildings', 'toggle-buildings'], ['quick-roads', 'toggle-roads'], ['quick-walkways', 'toggle-walkways'], ['quick-landmarks', 'toggle-landmarks']]) {
  const checkbox = $(`#${control}`) as HTMLInputElement;
  $(`#${quick}`).addEventListener('click', () => { checkbox.checked = !checkbox.checked; checkbox.dispatchEvent(new Event('change')); });
  checkbox.addEventListener('change', () => $(`#${quick}`).setAttribute('aria-pressed', String(checkbox.checked)));
}
for (const id of ['toggle-roads', 'toggle-walkways', 'toggle-steps']) $(`#${id}`).addEventListener('change', () => {
  roads?.setVisibility({ roadways: ($('#toggle-roads') as HTMLInputElement).checked, walkways: ($('#toggle-walkways') as HTMLInputElement).checked, steps: ($('#toggle-steps') as HTMLInputElement).checked });
  applyVisibility();
});
for (const id of ['toggle-contours', 'toggle-spots', 'toggle-shade', 'toggle-base']) $(`#${id}`).addEventListener('change', () => { applyVisibility(); if (id === 'toggle-spots') loadFeaturesSoon(); if (id === 'toggle-base' && !($('#toggle-base') as HTMLInputElement).checked) notice(''); });
for (const id of ['toggle-city-models', 'toggle-buildings', 'apartments-only']) $(`#${id}`).addEventListener('change', updateModelVisibility);
for (const id of ['toggle-trees', 'toggle-base']) $(`#${id}`).addEventListener('change', () => { applyVisibility(); scheduleGreenery(); });
$('#render-quality').addEventListener('change', () => {
  const value = Number(($('#render-quality') as HTMLSelectElement).value);
  map.setPixelRatio(Math.min(window.devicePixelRatio || 1, value));
});
$('#toggle-scale-references').addEventListener('change', () => scaleReferences?.setEnabled(($('#toggle-scale-references') as HTMLInputElement).checked));
$('#show-uphill').addEventListener('click', () => {
  void streetView.enter([127.03911815, 37.561191125], 350.39);
  if (window.innerWidth <= 760) setPanel(false);
});
$('#eye-forward').addEventListener('click', () => streetView.step(1));
$('#eye-back').addEventListener('click', () => streetView.step(-1));
$('#eye-left').addEventListener('click', () => streetView.turn(-1));
$('#eye-right').addEventListener('click', () => streetView.turn(1));
$('#eye-exit').addEventListener('click', () => streetView.exit(true));
$('#exaggeration').addEventListener('input', () => {
  const value = Number(($('#exaggeration') as HTMLInputElement).value);
  $('#exaggeration-value').textContent = `${value}×`; $('#terrain-badge-scale').textContent = `${value}×`;
  document.querySelectorAll<HTMLButtonElement>('[data-scale]').forEach(button => button.classList.toggle('selected', Number(button.dataset.scale) === value));
  if (is25d) map.setTerrain({ source: 'local-terrain', exaggeration: value });
  loadFeaturesSoon(); buildings?.schedule(); roads?.schedule(); landmarks?.schedule();
  cityModels?.updateTerrain(); scheduleGreenery();
});
document.querySelectorAll<HTMLButtonElement>('[data-scale]').forEach(button => button.addEventListener('click', () => { ($('#exaggeration') as HTMLInputElement).value = button.dataset.scale!; $('#exaggeration').dispatchEvent(new Event('input')); }));
$('#pitch').addEventListener('input', () => {
  const value = Number(($('#pitch') as HTMLInputElement).value); $('#pitch-value').textContent = `${value}°`;
  targetPitch = value;
  if (is25d) map.setPitch(value);
});
$('#mobile-panel').addEventListener('click', () => setPanel(!$('#sidebar').classList.contains('open')));
$('#close-panel').addEventListener('click', () => setPanel(false));
document.addEventListener('keydown', event => { if (event.key === 'Escape') { setPanel(false); clearTimeout(searchTimer); searchController?.abort(); ++searchRequest; $('#search-results').replaceChildren(); } });
$('#save-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!selectedCoordinate) return;
  const button = $('#save-form button') as HTMLButtonElement; button.disabled = true;
  const name = ($('#bookmark-name') as HTMLInputElement).value.trim();
  try {
    if (!name) { $('#save-status').textContent = '위치 이름을 입력해 주세요.'; return; }
    await request('/api/bookmarks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, lon: selectedCoordinate[0], lat: selectedCoordinate[1] }) });
    $('#save-status').textContent = '이 컴퓨터에 저장했습니다.'; await loadBookmarks();
  } catch { $('#save-status').textContent = '저장에 실패했습니다. 다시 시도해 주세요.'; }
  finally { button.disabled = false; }
});

try {
  map = new maplibregl.Map({
    container: 'map', center: currentPlace.center, zoom: currentPlace.zoom, minZoom: 10.2, maxZoom: 24,
    maxBounds: [[126.70, 37.37], [127.27, 37.78]], maxPitch: 85,
    attributionControl: false, hash: false,
    pixelRatio: Math.min(window.devicePixelRatio || 1, 1.25),
    style: {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        osm: basemapSource,
        'elevation-data': { type: 'geojson', data: empty(), tolerance: 0.15, attribution: '서울특별시·국토지리정보원 / 공공누리 제1유형' },
        'selection-link': { type: 'geojson', data: empty() },
      },
      layers: [
        { id: 'background', type: 'background', paint: { 'background-color': '#f0f2ed' } },
        ...basemapLayers,
        { id: 'contours', type: 'line', source: 'elevation-data', filter: ['==', ['get', 'kind'], 'contour'], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': ['case', ['boolean', ['get', 'major'], false], '#94502c', '#bb815e'], 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.55, 14, ['case', ['boolean', ['get', 'major'], false], 1.6, 0.85], 18, ['case', ['boolean', ['get', 'major'], false], 2.3, 1.3]], 'line-opacity': 0.86 } },
        { id: 'contour-labels', type: 'symbol', source: 'elevation-data', filter: ['==', ['get', 'kind'], 'contour'], minzoom: 12,
          layout: { 'symbol-placement': 'line', 'symbol-spacing': 200, 'text-field': ['concat', ['to-string', ['get', 'height_m']], ' m'], 'text-font': ['Noto Sans Regular'], 'text-size': 11 },
          paint: { 'text-color': '#824525', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 } },
        { id: 'spots', type: 'circle', source: 'elevation-data', filter: ['==', ['get', 'kind'], 'spot'], minzoom: 12, paint: { 'circle-color': '#236c87', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 1.6, 16, 3.2], 'circle-opacity': 0.8, 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 0.65 } },
        { id: 'spot-labels', type: 'symbol', source: 'elevation-data', filter: ['==', ['get', 'kind'], 'spot'], minzoom: 15.5, layout: { 'text-field': ['concat', ['to-string', ['get', 'height_m']], ' m'], 'text-font': ['Noto Sans Regular'], 'text-size': 10, 'text-anchor': 'bottom-left', 'text-offset': [0.45, -0.35] }, paint: { 'text-color': '#20596f', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 } },
        { id: 'selection-link-line', type: 'line', source: 'selection-link', paint: { 'line-color': '#086996', 'line-width': 2, 'line-dasharray': [2, 2] } },
      ],
    },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left');
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
  buildings = new Buildings(map, coordinate => {
    elevationController?.abort(); ++elevationRequest;
    selectedCoordinate = coordinate;
    clearMarkers();
    source('selection-link').setData(empty());
    $('#save-status').textContent = '';
    if (window.innerWidth <= 760) setPanel(true);
  });
  landmarks = new Landmarks(map, place => {
    clearTimeout(searchTimer); searchController?.abort(); ++searchRequest;
    $('#search-results').replaceChildren();
    $('#place-title').textContent = place.name; $('#place-subtitle').textContent = place.subtitle;
  });
  roads = new Roads(map, text => { $('#road-status').textContent = text; applyVisibility(); });
  scaleReferences = new ScaleReferences(map, { onState: state => {
    $('#eye-scale-note').hidden = !state.active || !state.enabled || !(state.drawnPeople || state.drawnCars);
    $('#scale-reference-status').textContent = !state.enabled ? '크기 비교 모형 꺼짐'
      : !state.active ? '사람 1인칭 모드에서만 표시합니다.'
      : state.people || state.cars ? '고정 모형 · 사람 1.7m · 승용차 길이 4.3m'
      : '현재 보이는 길에는 비교 모형을 놓을 자리가 없습니다.';
  } });
  scaleReferences.init();
  streetView = new StreetView(map, {
    onScene: scene => scaleReferences.setScene(scene),
    onMode: (active, preserveView = false) => {
      if (active) { previousStreetScale = Number(($('#exaggeration') as HTMLInputElement).value); previousStreetMode = is25d; }
      if (!preserveView) is25d = active ? true : previousStreetMode;
      const scale = preserveView ? Number(($('#exaggeration') as HTMLInputElement).value) : active ? 1 : previousStreetScale;
      ($('#exaggeration') as HTMLInputElement).value = String(scale);
      ($('#exaggeration') as HTMLInputElement).disabled = active;
      ($('#pitch') as HTMLInputElement).disabled = active;
      document.querySelectorAll<HTMLButtonElement>('[data-scale]').forEach(button => { button.disabled = active; button.classList.toggle('selected', Number(button.dataset.scale) === scale); });
      $('#exaggeration-value').textContent = `${scale}×`; $('#terrain-badge-scale').textContent = `${scale}×`;
      // Detaching the eye camera for a zoom must only update the controls.
      // Even setTerrain with the same options resets MapLibre's camera altitude.
      if (!preserveView) map.setTerrain(is25d ? { source: 'local-terrain', exaggeration: scale } : null);
      $('#terrain-settings').hidden = !is25d; $('#terrain-badge').hidden = !is25d;
      for (const [id, selected] of [['#mode-eye', active], ['#mode-25d', !active && is25d], ['#mode-2d', !active && !is25d]] as const) {
        $(id).classList.toggle('active', selected); $(id).setAttribute('aria-pressed', String(selected));
      }
      buildings.setMode(is25d); cityModels?.setMode(is25d);
      applyVisibility(); scheduleGreenery();
    },
    onState: state => {
      $('#eye-controls').hidden = !state.active && !state.loading && !state.message;
      $('#eye-status').textContent = state.message;
      ($('#eye-forward') as HTMLButtonElement).disabled = !state.active || !state.canForward;
      ($('#eye-back') as HTMLButtonElement).disabled = !state.active || !state.canBack;
      for (const id of ['eye-left', 'eye-right']) ($(`#${id}`) as HTMLButtonElement).disabled = !state.active;
      for (const id of ['eye-forward', 'eye-back', 'eye-left', 'eye-right']) $(`#${id}`).hidden = !state.active && !state.loading;
    },
  });

  // Local data must start even when the optional online basemap has pending tiles.
  map.once('style.load', () => { mapLoaded = true; buildings.init(); landmarks.init();
  renewalZones = new RenewalZones(map); renewalZones.init(); void roads.init(); void loadFeatures(); void loadTerrain(); void loadBookmarks(); void loadContextMetadata(); void loadCityModels().catch(error => { $('#city-model-status').textContent = '주요 빌딩 모형을 불러오지 못했습니다.'; console.error(error); }); });
  map.on('sourcedata', event => { if (event.sourceId === 'osm' && event.sourceDataType === 'content') { greeneryRevision++; scheduleGreenery(); } });
  map.on('idle', scheduleGreenery);
  map.on('moveend', () => { const center = map.getCenter(); $('#coordinate-readout').textContent = `중심 ${center.lat.toFixed(5)}° N · ${center.lng.toFixed(5)}° E`; applyVisibility(); loadFeaturesSoon(); buildings.schedule(); landmarks.schedule(); renewalZones?.schedule(); roads.schedule(); cityModels?.updateTerrain(); scheduleGreenery(); });
  let lastCoordinatePaint = 0;
  map.on('mousemove', event => {
    const now = performance.now();
    if (map.isMoving() || now - lastCoordinatePaint < 100) return;
    lastCoordinatePaint = now;
    $('#coordinate-readout').textContent = `커서 ${event.lngLat.lat.toFixed(5)}° N · ${event.lngLat.lng.toFixed(5)}° E`;
  });
  map.on('pitch', () => { if (is25d) { const value = Math.round(map.getPitch()); ($('#pitch') as HTMLInputElement).value = String(value); $('#pitch-value').textContent = `${value}°`; } });
  map.on('pitchend', () => { if (is25d) targetPitch = Math.round(map.getPitch()); });
  map.on('click', event => {
    if (buildings.click(event.point, [event.lngLat.lng, event.lngLat.lat])) return;
    const layers = [...(($('#toggle-spots') as HTMLInputElement).checked ? ['spots'] : []), ...(($('#toggle-contours') as HTMLInputElement).checked ? ['contours'] : [])];
    const features = layers.length ? map.queryRenderedFeatures([[event.point.x - 5, event.point.y - 5], [event.point.x + 5, event.point.y + 5]], { layers }) : [];
    const feature = features.find(f => f.properties.kind === 'spot') ?? features[0];
    void inspect([event.lngLat.lng, event.lngLat.lat], feature?.properties.height_m, feature?.properties.kind);
    if (window.innerWidth <= 760) setPanel(true);
  });
  map.on('error', event => {
    const sourceId = (event as typeof event & { sourceId?: string }).sourceId;
    if (sourceId === 'osm') { basemapWarning = true; notice('온라인 배경 연결이 원활하지 않습니다. 로컬 지형·건물·장소 자료는 계속 볼 수 있습니다.'); }
    else if (sourceId === 'local-terrain') notice('지형 타일을 불러오지 못했습니다. 2D 원본 등고선으로 확인할 수 있습니다.', true);
    else console.error('Map rendering error', event.error);
  });
  if (import.meta.env.DEV) Object.assign(window, { __SEOUL_MAP__: { map, buildings, landmarks, roads, scaleReferences, streetView, get cityModels() { return cityModels; }, getData: () => lastData, inspect, getState: () => ({ mapLoaded, terrainReady, is25d, selectedCoordinate, greeneryPending: exclusionRequests.size > 0 || treeJobs.size > 0 }) } });
} catch (error) {
  notice('이 브라우저에서 지도를 시작하지 못했습니다. WebGL을 지원하는 브라우저로 열어 주세요.', true);
  console.error(error);
}
