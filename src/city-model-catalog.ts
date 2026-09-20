import type { CityModelAsset } from './city-models.ts';

export type CatalogView = { zoom: number; lon: number; lat: number; west: number; south: number; east: number; north: number };
type Tile = { id: string; path: string; bounds: [number, number, number, number]; count: number; sha256: string };
type Index = { version: 1; minZoom: number; assetCount: number; tiles: Tile[] };
export type CatalogTile = { id: string; assets: CityModelAsset[] };
const pathPattern = /^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.json$/;
const hashPattern = /^[a-f0-9]{64}$/;
const maxTiles = 32;

function validBounds(value: unknown): value is Tile['bounds'] {
  return Array.isArray(value) && value.length === 4 && value.every(Number.isFinite)
    && value[0] >= -180 && value[2] <= 180 && value[1] >= -90 && value[3] <= 90
    && value[0] < value[2] && value[1] < value[3];
}
function parseIndex(value: Index, path: string): Index {
  const directory = path.slice(0, path.lastIndexOf('/') + 1);
  if (value?.version !== 1 || !Number.isFinite(value.minZoom) || value.minZoom < 16.5 || value.minZoom > 24
    || !Number.isSafeInteger(value.assetCount) || value.assetCount < 0 || value.assetCount > 1000000
    || !Array.isArray(value.tiles) || value.tiles.length > 20000) throw new Error('Invalid model catalog index');
  const ids = new Set<string>();
  let count = 0;
  for (const tile of value.tiles) {
    if (!tile || !/^16-\d+-\d+$/.test(tile.id) || ids.has(tile.id)
      || !pathPattern.test(tile.path) || tile.path !== `${directory}tiles/${tile.id}.json`
      || !validBounds(tile.bounds) || !Number.isSafeInteger(tile.count) || tile.count < 1 || tile.count > 4096
      || !hashPattern.test(tile.sha256)) throw new Error('Invalid model catalog tile');
    ids.add(tile.id); count += tile.count;
  }
  if (count !== value.assetCount) throw new Error('Model catalog count mismatch');
  return value;
}

/** Bounded metadata cache; GLB scenes and their individual terrain placement stay in CityModels. */
export class CityModelCatalog {
  private index?: Index;
  private cache = new Map<string, CatalogTile>();
  private owners = new Map<string, string>();
  private failed = new Set<string>();
  private wanted = new Set<string>();
  private request?: { view: CatalogView; enabled: boolean; key: string };
  private pinned: (id: string) => boolean = () => false;
  private controller?: AbortController;
  private cycle?: Promise<void>;
  private revision = 0;
  private disposed = false;
  error: string | null = null;
  private path: string;
  private reservedIds: Set<string>;
  private changed: (tiles: CatalogTile[]) => void;

  constructor(path: string, reservedIds: Set<string>, changed: (tiles: CatalogTile[]) => void) {
    if (!pathPattern.test(path)) throw new Error('Invalid model catalog path');
    this.path = path; this.reservedIds = reservedIds; this.changed = changed;
  }
  get assetCount() { return this.index?.assetCount ?? 0; }
  get tileCount() { return this.cache.size; }

  update(view: CatalogView, enabled: boolean, pinned: (id: string) => boolean): Promise<void> {
    if (this.disposed) return Promise.resolve();
    this.pinned = pinned;
    enabled = enabled && view.zoom >= 16.5;
    const key = enabled ? [view.zoom, view.lon, view.lat, view.west, view.south, view.east, view.north].join(':') : 'off';
    if (this.request?.key !== key) {
      this.request = { view, enabled, key }; this.revision++;
      this.controller?.abort(); this.error = null;
    }
    if (!enabled) return this.cycle ?? Promise.resolve();
    if (!this.cycle) {
      this.cycle = this.run().finally(() => { this.cycle = undefined; });
    }
    return this.cycle;
  }
  private select(view: CatalogView) {
    if (!this.index || view.zoom < this.index.minZoom) return [];
    const dx = (view.east - view.west) * .2, dy = (view.north - view.south) * .2;
    const scale = Math.cos(view.lat * Math.PI / 180);
    const distance = (tile: Tile) => {
      const [w, s, e, n] = tile.bounds;
      return ((Math.max(w, Math.min(e, view.lon)) - view.lon) * scale) ** 2
        + (Math.max(s, Math.min(n, view.lat)) - view.lat) ** 2;
    };
    return this.index.tiles.filter(t => t.bounds[2] >= view.west - dx && t.bounds[0] <= view.east + dx
      && t.bounds[3] >= view.south - dy && t.bounds[1] <= view.north + dy)
      .sort((a, b) => distance(a) - distance(b) || a.id.localeCompare(b.id)).slice(0, 16);
  }
  private async json(path: string, signal: AbortSignal, sha?: string) {
    const response = await fetch(`/models/${path}`, { signal });
    if (!response.ok) throw new Error(`Model catalog HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > 8 * 1024 * 1024) throw new Error('Model catalog response too large');
    if (sha) {
      const actual = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
      if (actual !== sha) throw new Error('Model catalog checksum mismatch');
    }
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  private assets(value: { version: number; assets: CityModelAsset[] }, tile: Tile) {
    if (value?.version !== 1 || !Array.isArray(value.assets) || value.assets.length !== tile.count) throw new Error('Invalid model catalog assets');
    const ids = new Set<string>();
    for (const asset of value.assets) {
      if (!asset || typeof asset.id !== 'string' || !/^[a-z0-9_-]+$/.test(asset.id) || ids.has(asset.id)
        || this.reservedIds.has(asset.id) || this.owners.has(asset.id) && this.owners.get(asset.id) !== tile.id
        || typeof asset.nameKo !== 'string' || !/^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.glb$/.test(asset.model)
        || !hashPattern.test(asset.sha256) || !Number.isFinite(asset.yawDegFromEast)
        || !Array.isArray(asset.dimensions) || asset.dimensions.length !== 3 || !asset.dimensions.every(n => Number.isFinite(n) && n > 0)
        || !asset.coordinate || !Number.isFinite(asset.coordinate.lon) || !Number.isFinite(asset.coordinate.lat)
        || asset.coordinate.lon < tile.bounds[0] || asset.coordinate.lon > tile.bounds[2]
        || asset.coordinate.lat < tile.bounds[1] || asset.coordinate.lat > tile.bounds[3]
        || asset.geoBounds !== undefined && !validBounds(asset.geoBounds)
        || asset.minZoom !== undefined && (!Number.isFinite(asset.minZoom) || asset.minZoom < this.index!.minZoom)
        || !Array.isArray(asset.footprintIds)
        || asset.footprintIds.some(id => typeof id !== 'string' || !id.length || id.length > 200)) throw new Error('Invalid or duplicate catalog model');
      ids.add(asset.id);
    }
    return value.assets.map(asset => ({ ...asset, minZoom: asset.minZoom ?? this.index!.minZoom }));
  }
  private publish(tile: Tile, assets: CityModelAsset[]) {
    if (this.cache.size >= maxTiles) {
      const victim = [...this.cache.keys()].find(id => !this.wanted.has(id) && !this.pinned(id));
      if (!victim) return;
      this.cache.delete(victim);
    }
    assets.forEach(asset => this.owners.set(asset.id, tile.id));
    this.cache.set(tile.id, { id: tile.id, assets });
    this.changed([...this.cache.values()]);
  }
  private async run() {
    let revision: number;
    do {
      revision = this.revision;
      const request = this.request!;
      if (!request.enabled || this.disposed) break;
      const controller = this.controller = new AbortController();
      try {
        if (!this.index) {
          const index = parseIndex(await this.json(this.path, controller.signal), this.path);
          if (this.disposed || revision !== this.revision) continue;
          this.index = index;
        }
        const selected = this.select(request.view);
        this.wanted = new Set(selected.map(tile => tile.id));
        this.failed = new Set([...this.failed].filter(id => this.wanted.has(id)));
        for (const tile of selected) {
          const cached = this.cache.get(tile.id);
          if (cached) { this.cache.delete(tile.id); this.cache.set(tile.id, cached); }
        }
        const queue = selected.filter(tile => !this.cache.has(tile.id) && !this.failed.has(tile.id));
        const worker = async () => {
          while (queue.length && revision === this.revision && !this.disposed) {
            const tile = queue.shift()!;
            try {
              const value = await this.json(tile.path, controller.signal, tile.sha256);
              if (this.disposed || revision !== this.revision) continue;
              this.publish(tile, this.assets(value, tile));
            } catch (error) {
              if (this.disposed || revision !== this.revision) continue;
              this.failed.add(tile.id); this.error = error instanceof Error ? error.message : String(error);
            }
          }
        };
        await Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));
      } catch (error) {
        if (!this.disposed && revision === this.revision) this.error = error instanceof Error ? error.message : String(error);
      }
    } while (!this.disposed && revision !== this.revision);
  }
  dispose() { this.disposed = true; this.revision++; this.controller?.abort(); this.cache.clear(); this.owners.clear(); }
}
