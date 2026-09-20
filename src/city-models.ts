import { MercatorCoordinate } from 'maplibre-gl';
import type { Map as MapInstance, CustomLayerInterface, CustomRenderMethodInput } from 'maplibre-gl';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { CityModelCatalog } from './city-model-catalog.ts';
import type { CatalogTile } from './city-model-catalog.ts';

export interface CityModelAsset {
  id: string; nameKo: string; model: string; dimensions: [number, number, number];
  coordinate: { lon: number; lat: number }; yawDegFromEast: number;
  heightDatum: string; sha256: string; referenceUrl: string; minZoom?: number; district?: string; category?: string; geoBounds?: [number, number, number, number];
  footprintIds?: string[];
}
export interface DecorativeTree { coordinate: [number, number]; height_m: number; crown_radius_m: number }
export interface CityModelState {
  message: string;
  enabled: boolean; is25d: boolean; loading: boolean; contextLost: boolean;
  models: { id: string; name: string; loaded: boolean; active: boolean; error: string | null; height_m: number; ground_m: number | null; drawCount: number }[];
  activeFootprintIds: string[]; trees: { count: number; activeCount: number; enabled: boolean; decorative: true };
  frameCount: number; lastDrawCalls: number; error: string | null;
  catalogTotal?: number;
}
type Options = { assets?: CityModelAsset[]; catalogIndex?: string; onState?: (state: CityModelState) => void; onActiveFootprints?: (ids: string[]) => void };
type Entry = { asset: CityModelAsset; catalogTile?: string; scene?: THREE.Scene; error: string | null; ground: number | null; draws: number; active: boolean; pending?: Promise<void>; lastUsed?: number };
type View = { zoom: number; lon: number; lat: number; west: number; east: number; south: number; north: number };

/** GLB metres: +X east, +Y up, +Z south at yaw=0. Ground is already exaggerated. */
export function modelMercatorMatrix(coordinate: [number, number], groundM: number) {
  const origin = MercatorCoordinate.fromLngLat(coordinate, groundM);
  const scale = origin.meterInMercatorCoordinateUnits();
  return new THREE.Matrix4().makeTranslation(origin.x, origin.y, origin.z)
    .scale(new THREE.Vector3(scale, -scale, scale))
    .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2));
}

function disposeScene(scene: THREE.Object3D) {
  scene.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry.dispose();
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) material.dispose();
  });
}

function illuminate(scene: THREE.Scene) {
  scene.add(new THREE.HemisphereLight(0xe9f4ff, 0x797768, 2.1));
  const key = new THREE.DirectionalLight(0xfff1df, 2.4);
  key.position.set(-120, 250, -80); scene.add(key);
  const fill = new THREE.DirectionalLight(0xc9ddec, 0.8);
  fill.position.set(100, 100, 180); scene.add(fill);
}

export class CityModels {
  readonly layerId = 'city-landmark-models';
  private enabled = true;
  private publicVisible = true;
  private bridgesVisible = true;
  private culturalVisible = true;
  private officesVisible = true;
  private treesEnabled = false;
  private is25d = false;
  private loading = false;
  private disposed = false;
  private contextLost = false;
  private error: string | null = null;
  private entries: Entry[] = [];
  private legacyEntries: Entry[] = [];
  private catalog?: CityModelCatalog;
  private indexedEntries?: Entry[];
  private indexedLength = -1;
  private catalogRevision = 0;
  private entryOrder = new Map<Entry, number>();
  private trackedEntries = new Set<Entry>();
  private nearbyCache?: { key: string; entries: Entry[] };
  private loadCycle?: Promise<void>;
  private loadAgain = false;
  private useCounter = 0;
  private readonly maxNearby = 32;
  private readonly maxResident = 48;
  private matches: Record<string, string[]> = {};
  private renderer?: THREE.WebGLRenderer;
  private camera = new THREE.Camera();
  private frameCount = 0;
  private drawCalls = 0;
  private lastState = '';
  private lastFootprints = '';
  private initPromise?: Promise<void>;
  private trees: DecorativeTree[] = [];
  private treeScene?: THREE.Scene;
  private trunks?: THREE.InstancedMesh;
  private crowns?: THREE.InstancedMesh;
  private treeOrigin: [number, number] = [126.978, 37.566];
  private activeTrees = 0;
  private treesDirty = true;
  private treesSignature = '';
  private abort = new AbortController();
  private onViewChanged = () => { void this.loadNearby(); this.updateTerrain(); };
  private onTerrainData = (event: { sourceId?: string; sourceDataType?: string }) => { if (event.sourceId === 'local-terrain' && event.sourceDataType === 'content') this.updateTerrain(); };
  private onLost = () => { this.contextLost = true; this.clearActiveEntries(); this.activeTrees = 0; this.emit(); };
  private onRestored = () => { this.contextLost = false; this.updateTerrain(); };

  private map: MapInstance;
  private options: Options;
  constructor(map: MapInstance, options: Options = {}) { this.map = map; this.options = options; }

  init() {
    if (!this.initPromise) this.initPromise = this.initialize();
    return this.initPromise;
  }
  private async initialize() {
    this.loading = true; this.emit();
    try {
      let manifest: { assets: CityModelAsset[]; catalogIndex?: string };
      if (this.options.assets) manifest = { assets: this.options.assets, catalogIndex: this.options.catalogIndex };
      else {
        const response = await fetch('/models/manifest.json', { signal: this.abort.signal });
        if (!response.ok) throw new Error('랜드마크 목록을 불러오지 못했습니다.');
        manifest = await response.json() as { assets: CityModelAsset[]; catalogIndex?: string };
      }
      if (!Array.isArray(manifest.assets) || manifest.assets.length > 25000) throw new Error('잘못된 모델 목록입니다.');
      if (new Set(manifest.assets.map(a => a.id)).size !== manifest.assets.length || manifest.assets.some(a => !a.coordinate || !Number.isFinite(a.coordinate.lon) || !Number.isFinite(a.coordinate.lat) || Math.abs(a.coordinate.lon) > 180 || Math.abs(a.coordinate.lat) > 90)) throw new Error('잘못된 모델 위치입니다.');
      this.entries = manifest.assets.map(asset => ({ asset, error: null, ground: null, draws: 0, active: false }));
      this.legacyEntries = this.entries;
      if (manifest.catalogIndex !== undefined) {
        // A broken optional catalog must not prevent the preserved models loading.
        try { this.catalog = new CityModelCatalog(manifest.catalogIndex, new Set(manifest.assets.map(a => a.id)), tiles => this.replaceCatalogTiles(tiles)); }
        catch (error) { this.error = error instanceof Error ? error.message : String(error); }
      }
      const layer: CustomLayerInterface = {
        id: this.layerId, type: 'custom', renderingMode: '3d',
        onAdd: (_map, gl) => {
          this.renderer = new THREE.WebGLRenderer({ canvas: this.map.getCanvas(), context: gl, antialias: true });
          this.renderer.autoClear = false;
          this.renderer.outputColorSpace = THREE.SRGBColorSpace;
          this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
          this.renderer.toneMappingExposure = 1.1;
        },
        render: (_gl, args) => this.render(args),
        onRemove: () => this.disposeResources(),
      };
      if (this.disposed) return;
      this.map.addLayer(layer);
      this.map.on('sourcedata', this.onTerrainData);
      this.map.on('webglcontextlost', this.onLost);
      this.map.on('webglcontextrestored', this.onRestored);
      this.map.on('moveend', this.onViewChanged);
      await this.loadNearby();
    } catch (error) {
      if (!this.disposed) this.error = error instanceof Error ? error.message : String(error);
    } finally { this.loading = false; if (!this.disposed) { this.emit(); this.map.triggerRepaint(); } }
  }
  private replaceCatalogTiles(tiles: CatalogTile[]) {
    if (this.disposed) return;
    const current = new Map(this.entries.filter(e => e.catalogTile).map(e => [e.asset.id, e]));
    const added = tiles.flatMap(tile => tile.assets.map(asset => {
      const existing = current.get(asset.id);
      current.delete(asset.id);
      return existing ?? { asset, catalogTile: tile.id, error: null, ground: null, draws: 0, active: false };
    }));
    for (const entry of current.values()) if (entry.scene) disposeScene(entry.scene);
    this.entries = [...this.legacyEntries, ...added];
    this.syncCatalog(); this.emit(); this.map.triggerRepaint();
  }
  private updateCatalog() {
    if (!this.catalog) return Promise.resolve();
    const view = this.viewSnapshot();
    for (const entry of this.trackedEntries) if (entry.active && !this.inView(entry.asset, view)) entry.active = false;
    return this.catalog.update(view, !this.disposed && this.enabled && this.is25d,
      id => [...this.trackedEntries].some(entry => entry.catalogTile === id && (entry.active || !!entry.pending)));
  }
  private footprints(entry: Entry) {
    return entry.catalogTile ? entry.asset.footprintIds ?? [] : this.matches[entry.asset.id] ?? [];
  }
  private syncCatalog() {
    if (this.indexedEntries === this.entries && this.indexedLength === this.entries.length) return;
    this.indexedEntries = this.entries; this.indexedLength = this.entries.length;
    this.catalogRevision++; this.nearbyCache = undefined;
    this.entryOrder.clear(); this.trackedEntries.clear();
    this.entries.forEach((entry, index) => {
      this.entryOrder.set(entry, index);
      if (entry.scene || entry.error || entry.pending || entry.active) this.trackedEntries.add(entry);
    });
  }
  private trackEntry(entry: Entry) {
    this.syncCatalog();
    if (!this.entryOrder.has(entry)) return;
    if (entry.scene || entry.error || entry.pending || entry.active) this.trackedEntries.add(entry);
    else this.trackedEntries.delete(entry);
  }
  private clearActiveEntries() {
    this.syncCatalog();
    for (const entry of this.trackedEntries) entry.active = false;
  }
  private viewSnapshot(): View {
    const bounds = this.map.getBounds();
    const { lng: lon, lat } = this.map.getCenter();
    return { zoom: this.map.getZoom(), lon, lat, west: bounds.getWest(), east: bounds.getEast(), south: bounds.getSouth(), north: bounds.getNorth() };
  }
  private inView(asset: CityModelAsset, view: View) {
    if (asset.category === 'bridge' && !this.bridgesVisible || ['k12-school', 'district-public-office'].includes(asset.category ?? '') && !this.publicVisible) return false;
    if (['city-hall', 'cultural-site'].includes(asset.category ?? '') && !this.culturalVisible || asset.category === 'company-office' && !this.officesVisible) return false;
    if (view.zoom < (asset.minZoom ?? 13)) return false;
    const dx = (view.east - view.west) * 0.2;
    const dy = (view.north - view.south) * 0.2;
    if (asset.geoBounds) return asset.geoBounds[2] >= view.west - dx && asset.geoBounds[0] <= view.east + dx && asset.geoBounds[3] >= view.south - dy && asset.geoBounds[1] <= view.north + dy;
    return asset.coordinate.lon >= view.west - dx && asset.coordinate.lon <= view.east + dx
      && asset.coordinate.lat >= view.south - dy && asset.coordinate.lat <= view.north + dy;
  }
  private nearbyEntries() {
    this.syncCatalog();
    const view = this.viewSnapshot();
    const key = [view.zoom, view.lon, view.lat, view.west, view.east, view.south, view.north,
      this.publicVisible, this.bridgesVisible, this.culturalVisible, this.officesVisible].join(':');
    if (this.nearbyCache?.key === key) return this.nearbyCache.entries;
    const scale = Math.cos(view.lat * Math.PI / 180);
    const distance = (entry: Entry) => ((entry.asset.coordinate.lon - view.lon) * scale) ** 2 + (entry.asset.coordinate.lat - view.lat) ** 2;
    const entries = this.entries.filter(entry => this.inView(entry.asset, view))
      .sort((a, b) => distance(a) - distance(b) || a.asset.id.localeCompare(b.asset.id))
      .slice(0, this.maxNearby);
    this.nearbyCache = { key, entries };
    return entries;
  }
  private trimCache() {
    const protectedEntries = new Set(this.nearbyEntries());
    const resident = [...this.trackedEntries].filter(entry => !!entry.scene);
    let excess = resident.length - this.maxResident;
    for (const entry of resident.sort((a, b) => (a.lastUsed ?? 0) - (b.lastUsed ?? 0))) {
      if (excess <= 0) break;
      if (protectedEntries.has(entry) || entry.pending) continue;
      disposeScene(entry.scene!); entry.scene = undefined; entry.active = false; entry.ground = null; excess--;
      this.trackEntry(entry);
    }
  }
  private loadNearby(): Promise<void> {
    void this.updateCatalog();
    if (this.disposed || !this.enabled || !this.is25d) return Promise.resolve();
    if (this.loadCycle) { this.loadAgain = true; return this.loadCycle; }
    this.loadCycle = Promise.resolve().then(async () => {
      do {
        this.loadAgain = false;
        await this.updateCatalog();
        if (this.disposed || !this.enabled || !this.is25d) break;
        const nearby = this.nearbyEntries();
        for (const entry of nearby) entry.lastUsed = ++this.useCounter;
        const queue = nearby.filter(entry => !entry.scene && !entry.error);
        const worker = async () => {
          while (queue.length) {
            const entry = queue.shift()!;
            if (this.disposed || !this.enabled || !this.is25d || !this.nearbyEntries().includes(entry)) continue;
            entry.pending = Promise.resolve().then(() => this.loadEntry(entry));
            this.trackEntry(entry);
            await entry.pending;
            this.trimCache();
          }
        };
        await Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));
        this.trimCache();
      } while (this.loadAgain && !this.disposed && this.enabled && this.is25d);
    }).finally(() => { this.loadCycle = undefined; if (!this.disposed) this.emit(); });
    return this.loadCycle;
  }
  private async loadEntry(entry: Entry) {
        try {
          const asset = entry.asset;
          if (!/^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.glb$/.test(asset.model) || !asset.dimensions.every(n => Number.isFinite(n) && n > 0)) throw new Error('Invalid model manifest');
          const response = await fetch(`/models/${asset.model}`, { signal: this.abort.signal });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const bytes = await response.arrayBuffer();
          const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
          if (digest !== asset.sha256) throw new Error('원본 모델 체크섬 불일치');
          const { scene: model } = await new GLTFLoader().parseAsync(bytes, '/models/');
          if (this.disposed) { disposeScene(model); return; }
          const box = new THREE.Box3().setFromObject(model);
          const size = box.getSize(new THREE.Vector3()).toArray();
          if (Math.abs(box.min.y) > 0.01 || size.some((v, i) => Math.abs(v - asset.dimensions[i]) > 0.01)) {
            disposeScene(model); throw new Error('모델 바닥 또는 미터 치수 불일치');
          }
          model.rotation.y = THREE.MathUtils.degToRad(asset.yawDegFromEast);
          entry.scene = new THREE.Scene(); illuminate(entry.scene); entry.scene.add(model);
        } catch (error) {
          if (!this.disposed) entry.error = error instanceof Error ? error.message : String(error);
        }
        entry.pending = undefined;
        this.trackEntry(entry);
        if (!this.disposed) { this.emit(); this.map.triggerRepaint(); }
  }

  setFootprintMatches(matches: Record<string, string[]>) {
    this.matches = Object.fromEntries(Object.entries(matches).map(([id, ids]) => [id, [...new Set(ids)]])); this.emit();
  }
  setCategories(publicFacilities: boolean, bridges: boolean, cultural = this.culturalVisible, offices = this.officesVisible) {
    if (this.publicVisible === publicFacilities && this.bridgesVisible === bridges && this.culturalVisible === cultural && this.officesVisible === offices) return;
    this.publicVisible = publicFacilities; this.bridgesVisible = bridges; this.culturalVisible = cultural; this.officesVisible = offices; void this.loadNearby(); this.updateTerrain();
  }
  setMode(is25d: boolean) { this.is25d = is25d; void this.loadNearby(); this.updateTerrain(); }
  setVisible(visible: boolean) { this.enabled = visible; void this.loadNearby(); this.updateTerrain(); }
  setTreesVisible(visible: boolean) { this.treesEnabled = visible; this.updateTerrain(); }
  updateTerrain() {
    if (this.disposed) return;
    this.treesDirty = true;
    if (!this.enabled || !this.is25d) this.clearActiveEntries();
    if (!this.treesEnabled || !this.is25d) this.activeTrees = 0;
    this.emit(); this.map.triggerRepaint();
  }
  setTrees(trees: DecorativeTree[]) {
    const selected = trees.filter(t => t.coordinate.every(Number.isFinite) && t.height_m > 0 && t.height_m <= 40 && t.crown_radius_m > 0 && t.crown_radius_m <= 15).slice(0, 800);
    const signature = JSON.stringify(selected);
    if (signature === this.treesSignature) return;
    this.treesSignature = signature; this.trees = selected;
    if (!this.trees.length) {
      if (this.trunks) this.trunks.count = 0;
      if (this.crowns) this.crowns.count = 0;
      this.activeTrees = 0; this.updateTerrain(); return;
    }
    if (!this.treeScene) {
      this.treeScene = new THREE.Scene(); illuminate(this.treeScene);
      this.trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.15, 0.22, 1, 5), new THREE.MeshLambertMaterial({ color: '#71563c' }), 800);
      this.crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshLambertMaterial({ color: '#70915a' }), 800);
      this.trunks.frustumCulled = false; this.crowns.frustumCulled = false;
      this.treeScene.add(this.trunks, this.crowns);
    }
    if (this.trees.length) this.treeOrigin = [...this.trees[0].coordinate];
    this.updateTerrain();
  }
  private terrainReady() {
    return !!this.map.getTerrain() && !!this.map.getSource('local-terrain') && this.map.isSourceLoaded('local-terrain');
  }
  private render(args: CustomRenderMethodInput) {
    if (this.disposed || this.contextLost || !this.renderer || !this.is25d) return;
    this.drawCalls = 0;
    const supported = args.shaderData.variantName === 'mercator';
    const ready = supported && this.terrainReady();
    const visible = this.nearbyEntries();
    this.clearActiveEntries();
    for (const entry of visible) {
      if (!this.enabled || !entry.scene || entry.error || !ready) continue;
      const coordinate: [number, number] = [entry.asset.coordinate.lon, entry.asset.coordinate.lat];
      const ground = this.map.queryTerrainElevation(coordinate);
      if (ground === null || !Number.isFinite(ground)) continue;
      entry.ground = ground;
      try {
        this.camera.projectionMatrix.fromArray(args.defaultProjectionData.mainMatrix).multiply(modelMercatorMatrix(coordinate, ground));
        this.renderer.resetState(); this.renderer.render(entry.scene, this.camera);
        const calls = this.renderer.info.render.calls;
        this.drawCalls += calls;
        // Being inside a padded geographic bbox does not guarantee that any
        // mesh survives the Three.js camera frustum (especially at high pitch).
        entry.active = calls > 0;
        if (entry.active) entry.draws++;
      } catch (error) { entry.error = error instanceof Error ? error.message : String(error); }
      this.trackEntry(entry);
    }
    this.activeTrees = 0;
    if (this.treesEnabled && ready && this.treeScene && this.trunks && this.crowns && this.trees.length) {
      if (this.treesDirty) this.placeTrees();
      this.camera.projectionMatrix.fromArray(args.defaultProjectionData.mainMatrix).multiply(modelMercatorMatrix(this.treeOrigin, 0));
      this.renderer.resetState(); this.renderer.render(this.treeScene, this.camera);
      this.drawCalls += this.renderer.info.render.calls;
      this.activeTrees = this.trunks.count;
    }
    this.renderer.resetState(); this.frameCount++; this.emit();
    // Static scene: map movement / DEM sourcedata / controls request frames.
    // Do not create a permanent animation loop on an otherwise idle map.
  }
  private placeTrees() {
    if (!this.trunks || !this.crowns) return;
    const origin = MercatorCoordinate.fromLngLat(this.treeOrigin);
    const scale = origin.meterInMercatorCoordinateUnits();
    const object = new THREE.Object3D();
    let count = 0;
    for (const tree of this.trees) {
      const ground = this.map.queryTerrainElevation(tree.coordinate);
      if (ground === null || !Number.isFinite(ground)) continue;
      const p = MercatorCoordinate.fromLngLat(tree.coordinate);
      const x = (p.x - origin.x) / scale, z = (p.y - origin.y) / scale;
      const trunkHeight = tree.height_m * 0.6;
      object.position.set(x, ground + trunkHeight / 2, z); object.scale.set(1, trunkHeight, 1); object.updateMatrix();
      this.trunks.setMatrixAt(count, object.matrix);
      object.position.y = ground + tree.height_m * 0.68;
      object.scale.set(tree.crown_radius_m, tree.height_m * 0.32, tree.crown_radius_m); object.updateMatrix();
      this.crowns.setMatrixAt(count, object.matrix); count++;
    }
    this.trunks.count = count; this.crowns.count = count;
    this.trunks.instanceMatrix.needsUpdate = true; this.crowns.instanceMatrix.needsUpdate = true;
    this.treesDirty = false;
  }
  getState(): CityModelState {
    this.syncCatalog();
    const pending = this.loading || !!this.loadCycle || this.entries.some(e => !!e.pending);
    const active = this.entries.filter(e => e.active).length;
    const errors = this.entries.filter(e => e.error).length;
    const error = this.error ?? this.catalog?.error ?? null;
    const message = error ?? (this.contextLost ? '그래픽 연결을 복구하는 중입니다.' : !this.is25d ? '주요 건물 모델은 2.5D에서 표시합니다.' : !this.enabled ? '주요 건물 모델 표시 꺼짐' : pending ? '화면 근처의 주요 건물 모델을 불러오는 중…' : errors ? `모델 ${errors}개를 불러오지 못했습니다. 원본 건물 표시를 유지합니다.` : active ? `주요 건물 모델 ${active}개 · 모형 높이 1배 · 외관은 참고 재현` : '주요 건물 위치로 확대하면 모델이 표시됩니다.');
    return { message, enabled: this.enabled, is25d: this.is25d, loading: pending, contextLost: this.contextLost,
      models: this.entries.map(e => ({ id: e.asset.id, name: e.asset.nameKo, loaded: !!e.scene, active: e.active,
        error: e.error, height_m: e.asset.dimensions[1], ground_m: e.ground, drawCount: e.draws })),
      activeFootprintIds: [...new Set(this.entries.filter(e => e.active).flatMap(e => this.footprints(e)))],
      trees: { count: this.trees.length, activeCount: this.activeTrees, enabled: this.treesEnabled, decorative: true },
      frameCount: this.frameCount, lastDrawCalls: this.drawCalls, error,
      ...(this.catalog ? { catalogTotal: this.legacyEntries.length + this.catalog.assetCount } : {}) };
  }
  private emit() {
    this.syncCatalog();
    // Only resident/error/pending/active entries change between frames. Keep the
    // complete catalog available through getState(), but build it for callbacks
    // only when this compact state changes (not for draw/frame counters).
    const tracked = [...this.trackedEntries].sort((a, b) => this.entryOrder.get(a)! - this.entryOrder.get(b)!);
    const activeFootprints = [...new Set(tracked.filter(entry => entry.active).flatMap(entry => this.footprints(entry)))];
    const footprints = JSON.stringify(activeFootprints);
    if (footprints !== this.lastFootprints) { this.lastFootprints = footprints; this.options.onActiveFootprints?.(activeFootprints); }
    const signature = JSON.stringify([this.catalogRevision, this.enabled, this.is25d, this.loading, !!this.loadCycle,
      this.contextLost, this.error, this.catalog?.error, this.catalog?.assetCount, this.trees.length, this.activeTrees, this.treesEnabled, footprints,
      tracked.map(entry => [entry.asset.id, entry.asset.nameKo, entry.asset.dimensions[1], !!entry.scene, entry.error,
        entry.ground, entry.active, !!entry.pending])]);
    if (signature !== this.lastState) { this.lastState = signature; this.options.onState?.(this.getState()); }
  }
  private disposeResources() {
    if (this.disposed) return;
    this.disposed = true; this.catalog?.dispose(); this.abort.abort();
    this.map.off('sourcedata', this.onTerrainData); this.map.off('webglcontextlost', this.onLost); this.map.off('webglcontextrestored', this.onRestored);
    this.map.off('moveend', this.onViewChanged);
    this.syncCatalog();
    for (const entry of this.trackedEntries) { if (entry.scene) disposeScene(entry.scene); entry.active = false; }
    if (this.treeScene) disposeScene(this.treeScene);
    this.renderer?.dispose(); this.activeTrees = 0; this.emit();
  }
  destroy() { if (this.map.getLayer(this.layerId)) this.map.removeLayer(this.layerId); else this.disposeResources(); }
}
