import { MercatorCoordinate } from 'maplibre-gl';
import type { Map as MapInstance, CustomLayerInterface, CustomRenderMethodInput } from 'maplibre-gl';
import { horizontalDistance, projectMercator, terrainPointVisible } from './mobility-math.ts';
import type { MobilityRoute, RouteCoordinate } from './mobility-math.ts';

export type ScaleReferenceScene = { routes: MobilityRoute[]; coordinate: RouteCoordinate; bearing: number };
type Dimensions = { height: number; width: number; length: number };
type Point = { x: number; y: number };
type Placement = { id: string; routeId: string; kind: 'pedestrian' | 'car'; coordinate: RouteCoordinate; dimensions_m: Dimensions; bearing: number };
type Sample = Omit<Placement, 'bearing'> & { x: number; y: number; pixelHeight: number; ground_m: number };
export type ScaleReferenceState = {
  enabled: boolean; active: boolean; reason: 'inactive' | 'disabled' | 'loading' | 'empty' | 'visible' | 'error';
  people: number; cars: number; drawnPeople: number; drawnCars: number; frames: number;
  samples: Sample[]; placements: Omit<Placement, 'bearing'>[];
};
const LAYER = 'scale-reference-projection';
const RAD = Math.PI / 180;
const HUMAN = { height: 1.7, width: 0.5, length: 0.3 };
const CAR = { height: 1.5, width: 1.8, length: 4.3 };

/** Static size references on real paths. No fetching, timer, RAF, or map repaint requests. */
export class ScaleReferences {
  private map: MapInstance;
  private onState: (state: ScaleReferenceState) => void;
  private canvas?: HTMLCanvasElement;
  private context?: CanvasRenderingContext2D;
  private matrix?: number[];
  private width = 0;
  private height = 0;
  private initialized = false;
  private disposed = false;
  private enabled = true;
  private scene?: ScaleReferenceScene;
  private selected = false;
  private placements: Placement[] = [];
  private lastState = '';
  private state: ScaleReferenceState = { enabled: true, active: false, reason: 'inactive', people: 0, cars: 0, drawnPeople: 0, drawnCars: 0, frames: 0, samples: [], placements: [] };

  constructor(map: MapInstance, options: { onState?: (state: ScaleReferenceState) => void } = {}) {
    this.map = map; this.onState = options.onState ?? (() => {});
  }

  init() {
    if (this.initialized || this.disposed) return;
    this.initialized = true;
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'scale-reference-canvas';
    this.canvas.setAttribute('aria-hidden', 'true');
    Object.assign(this.canvas.style, { position: 'absolute', top: '0', left: '0', pointerEvents: 'none', zIndex: '2', display: 'none' });
    this.context = this.canvas.getContext('2d', { alpha: true }) ?? undefined;
    this.map.getCanvasContainer().appendChild(this.canvas);
    this.map.on('style.load', this.styleLoaded);
    this.map.on('render', this.render);
    this.map.on('resize', this.resize);
    this.map.on('remove', this.removed);
    document.addEventListener('visibilitychange', this.visibilityChanged);
    this.resize();
    if (this.map.isStyleLoaded()) this.styleLoaded();
    this.emit();
  }

  /** Call once when entering first person; clear on exit. Camera steps do not move placements. */
  setScene(scene: ScaleReferenceScene | null) {
    if (this.disposed) return;
    this.scene = scene && Number.isFinite(scene.bearing) && scene.coordinate.length === 3 && scene.coordinate.every(Number.isFinite)
      ? { ...scene, coordinate: [...scene.coordinate], routes: scene.routes.slice(0, 60) } : undefined;
    this.placements = []; this.selected = false;
    // Entry just positioned the camera. Wait for that camera's natural render
    // before combining its terrain projection with the custom-layer matrix.
    // Using the previous frame here can incorrectly reject nearby references.
    if (this.scene) this.matrix = undefined;
    this.clear();
    this.state.placements = [];
    this.render();
  }

  setEnabled(enabled: boolean) {
    if (this.enabled === enabled || this.disposed) return;
    this.enabled = enabled; this.state.enabled = enabled;
    this.render();
  }

  getState(): ScaleReferenceState {
    return { ...this.state, samples: this.state.samples.map(sample => ({ ...sample, coordinate: [...sample.coordinate], dimensions_m: { ...sample.dimensions_m } })),
      placements: this.placements.map(({ bearing: _bearing, ...placement }) => ({ ...placement, coordinate: [...placement.coordinate], dimensions_m: { ...placement.dimensions_m } })) };
  }

  private styleLoaded = () => {
    this.matrix = undefined;
    if (this.disposed || this.map.getLayer(LAYER)) return;
    const layer: CustomLayerInterface = { id: LAYER, type: 'custom', renderingMode: '3d', render: (_gl, args) => this.capture(args) };
    this.map.addLayer(layer);
  };

  private capture(args: CustomRenderMethodInput) {
    this.matrix = args.shaderData.variantName === 'mercator' ? Array.from(args.defaultProjectionData.mainMatrix) : undefined;
  }

  private resize = () => {
    if (!this.canvas || !this.context) return;
    const canvas = this.map.getCanvas();
    this.width = canvas.clientWidth; this.height = canvas.clientHeight;
    const dpr = Math.max(1, Math.min(1.25, window.devicePixelRatio || 1));
    this.canvas.width = Math.round(this.width * dpr); this.canvas.height = Math.round(this.height * dpr);
    this.canvas.style.width = `${this.width}px`; this.canvas.style.height = `${this.height}px`;
    this.context.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  private visibilityChanged = () => { this.render(); };
  private removed = () => { this.destroy(); };

  private ground(coordinate: RouteCoordinate): number | null {
    const height = this.map.getTerrain() ? this.map.queryTerrainElevation([coordinate[0], coordinate[1]]) : 0;
    return height !== null && Number.isFinite(height) ? height : null;
  }

  private project(coordinate: RouteCoordinate): Point | null {
    const point = this.map.project([coordinate[0], coordinate[1]]);
    return Number.isFinite(point.x) && Number.isFinite(point.y) ? { x: point.x, y: point.y } : null;
  }

  private elevated(coordinate: RouteCoordinate, height: number): Point | null {
    const ground = this.ground(coordinate);
    return this.matrix && ground !== null ? projectMercator(this.matrix, MercatorCoordinate.fromLngLat([coordinate[0], coordinate[1]], ground + height), this.width, this.height) : null;
  }

  private visible(coordinate: RouteCoordinate, point: Point) {
    if (point.x < 0 || point.x > this.width || point.y < 0 || point.y > this.height) return false;
    if (!terrainPointVisible(coordinate, this.map.unproject([point.x, point.y]))) return false;
    // Conservative surface/ordinary-building occlusion, not a shared GL depth buffer.
    return !this.map.getLayer('building-solids') || this.map.queryRenderedFeatures([point.x, point.y], { layers: ['building-solids'] }).length === 0;
  }

  private choosePlacements() {
    const scene = this.scene!;
    const metresLat = 111195.08, metresLon = metresLat * Math.cos(scene.coordinate[1] * RAD);
    const sin = Math.sin(scene.bearing * RAD), cos = Math.cos(scene.bearing * RAD);
    const candidates: { placement: Placement; score: number }[] = [];
    for (const route of scene.routes) {
      if (!Array.isArray(route.coordinates) || route.coordinates.length < 2 || route.coordinates.length > 5000) continue;
      if (route.kind === 'car' ? route.category !== 'roadway' : route.kind !== 'pedestrian' || !['walkway', 'steps'].includes(route.category)) continue;
      for (let i = 1; i < route.coordinates.length; i++) {
        const a = route.coordinates[i - 1], b = route.coordinates[i];
        if (!a || !b || !a.every(Number.isFinite) || !b.every(Number.isFinite)) continue;
        const ax = (a[0] - scene.coordinate[0]) * metresLon, ay = (a[1] - scene.coordinate[1]) * metresLat;
        const dx = (b[0] - a[0]) * metresLon, dy = (b[1] - a[1]) * metresLat;
        const lengthSquared = dx * dx + dy * dy;
        if (lengthSquared < 0.01) continue;
        for (const target of route.kind === 'car' ? [23] : [16, 29]) {
          const tx = sin * target, ty = cos * target;
          const t = Math.max(0, Math.min(1, ((tx - ax) * dx + (ty - ay) * dy) / lengthSquared));
          const x = ax + dx * t, y = ay + dy * t;
          const forward = x * sin + y * cos, lateral = x * cos - y * sin;
          if (forward < 12 || forward > 35 || Math.abs(lateral) > 20 || Math.hypot(x, y) > 40) continue;
          const coordinate: RouteCoordinate = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
          candidates.push({ score: (forward - target) ** 2 + lateral ** 2 * 2,
            placement: { id: `${route.id}:scale:${i}:${target}`, routeId: route.id, kind: route.kind, coordinate,
              dimensions_m: route.kind === 'car' ? { ...CAR } : { ...HUMAN }, bearing: Math.atan2(dx, dy) / RAD } });
        }
      }
    }
    candidates.sort((a, b) => a.score - b.score);
    let people = 0, cars = 0, checked = 0;
    for (const { placement } of candidates) {
      if (placement.kind === 'car' ? cars >= 1 : people >= 1) continue;
      if (this.placements.some(prior => horizontalDistance(prior.coordinate, placement.coordinate) < 6)) continue;
      if (++checked > 36) break;
      const ground = this.ground(placement.coordinate), point = this.project(placement.coordinate), top = this.elevated(placement.coordinate, placement.dimensions_m.height);
      if (ground === null || !point || !top || !this.visible(placement.coordinate, point)) continue;
      const pixels = Math.hypot(top.x - point.x, top.y - point.y);
      if (pixels < 3 || pixels > this.height * 0.35) continue;
      this.placements.push(placement);
      if (placement.kind === 'car') cars++; else people++;
      if (people === 1 && cars === 1) break;
    }
    this.selected = true;
  }

  private render = () => {
    if (!this.initialized || this.disposed) return;
    this.clear();
    if (!this.enabled || !this.scene || document.hidden) {
      this.state.active = false; this.state.reason = !this.enabled ? 'disabled' : 'inactive'; this.emit(); return;
    }
    this.state.active = true;
    const terrain = this.map.getTerrain();
    if (!this.matrix || !this.width || !this.height || terrain && !this.map.isSourceLoaded(terrain.source)) { this.state.reason = 'loading'; this.emit(); return; }
    if (!this.context) { this.state.reason = 'error'; this.emit(); return; }
    if (!this.selected) this.choosePlacements();
    const drawn: { placement: Placement; foot: Point; top: Point; ground: number; pixels: number }[] = [];
    for (const placement of this.placements) {
      const foot = this.project(placement.coordinate), top = this.elevated(placement.coordinate, placement.dimensions_m.height), ground = this.ground(placement.coordinate);
      if (!foot || !top || ground === null || !this.visible(placement.coordinate, foot)) continue;
      const pixels = Math.hypot(top.x - foot.x, top.y - foot.y);
      // Close references disappear completely; they are never resized or made ghost-like.
      if (pixels < 3 || pixels > this.height * 0.35) continue;
      drawn.push({ placement, foot, top, ground, pixels });
    }
    drawn.sort((a, b) => a.foot.y - b.foot.y);
    for (const { placement, foot, top, ground, pixels } of drawn) {
      if (placement.kind === 'car' ? !this.drawCar(placement) : !this.drawPerson(foot, top, pixels)) continue;
      const { bearing: _bearing, ...properties } = placement;
      this.state.samples.push({ ...properties, coordinate: [...properties.coordinate], dimensions_m: { ...properties.dimensions_m }, x: foot.x, y: foot.y, pixelHeight: pixels, ground_m: ground });
      if (placement.kind === 'car') this.state.cars++; else this.state.people++;
    }
    this.state.drawnPeople = this.state.people; this.state.drawnCars = this.state.cars;
    this.state.reason = this.state.samples.length ? 'visible' : 'empty';
    this.state.frames++;
    if (this.canvas) this.canvas.style.display = this.state.samples.length ? 'block' : 'none';
    this.emit();
  };

  private drawPerson(foot: Point, top: Point, pixels: number) {
    const ctx = this.context!;
    ctx.save(); ctx.translate(foot.x, foot.y); ctx.rotate(Math.atan2(top.x - foot.x, foot.y - top.y)); ctx.scale(pixels / HUMAN.height, pixels / HUMAN.height);
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#465762';
    ctx.fillRect(-0.145, -0.85, 0.12, 0.81); ctx.fillRect(0.025, -0.85, 0.12, 0.81);
    ctx.fillStyle = '#303f47'; ctx.fillRect(-0.17, -0.07, 0.15, 0.07); ctx.fillRect(0.02, -0.07, 0.15, 0.07);
    ctx.fillStyle = '#71868d';
    ctx.beginPath(); ctx.moveTo(-0.20, -1.44); ctx.lineTo(0.20, -1.44); ctx.lineTo(0.15, -0.8); ctx.lineTo(-0.15, -0.8); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#c8aa8d';
    ctx.beginPath(); ctx.arc(0, -1.59, 0.11, 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(-0.25, -1.34, 0.085, 0.58); ctx.fillRect(0.165, -1.34, 0.085, 0.58);
    ctx.fillStyle = '#514c48'; ctx.beginPath(); ctx.arc(0, -1.61, 0.095, Math.PI, Math.PI * 2); ctx.fill();
    ctx.restore(); return true;
  }

  private drawCar(placement: Placement) {
    const ctx = this.context!, sin = Math.sin(placement.bearing * RAD), cos = Math.cos(placement.bearing * RAD);
    const metresLat = 111195.08, metresLon = metresLat * Math.cos(placement.coordinate[1] * RAD);
    const corner = (along: number, side: number, height: number) => {
      const coordinate: RouteCoordinate = [placement.coordinate[0] + (sin * along + cos * side) / metresLon, placement.coordinate[1] + (cos * along - sin * side) / metresLat, 0];
      return this.elevated(coordinate, height);
    };
    const ring = (length: number, width: number, height: number) => [[-length / 2, -width / 2], [length / 2, -width / 2], [length / 2, width / 2], [-length / 2, width / 2]].map(([along, side]) => corner(along, side, height));
    const base = ring(CAR.length, CAR.width, 0.18), belt = ring(CAR.length, CAR.width, 0.82), roof = ring(2.3, 1.5, CAR.height);
    if ([...base, ...belt, ...roof].some(point => !point || Math.abs(point.x) > this.width * 2 || Math.abs(point.y) > this.height * 2)) return false;
    const polygon = (points: (Point | null)[], colour: string) => {
      ctx.fillStyle = colour; ctx.beginPath(); ctx.moveTo(points[0]!.x, points[0]!.y);
      for (const point of points.slice(1)) ctx.lineTo(point!.x, point!.y);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    };
    ctx.save(); ctx.globalAlpha = 1; ctx.lineWidth = 0.6; ctx.strokeStyle = '#6c7c82';
    const sides = [0, 1, 2, 3].sort((a, b) => (base[a]!.y + base[(a + 1) % 4]!.y) - (base[b]!.y + base[(b + 1) % 4]!.y));
    for (const i of sides) { const next = (i + 1) % 4; polygon([base[i], base[next], belt[next], belt[i]], '#abbcc2'); }
    polygon(belt, '#c5d1d5');
    for (const i of sides) { const next = (i + 1) % 4; polygon([belt[i], belt[next], roof[next], roof[i]], '#829aa5'); }
    polygon(roof, '#c5d1d5');
    ctx.restore(); return true;
  }

  private clear() {
    this.context?.clearRect(0, 0, this.width, this.height);
    if (this.canvas) this.canvas.style.display = 'none';
    Object.assign(this.state, { people: 0, cars: 0, drawnPeople: 0, drawnCars: 0, samples: [] });
  }

  private emit() {
    const signature = JSON.stringify([this.state.enabled, this.state.active, this.state.reason, this.state.people, this.state.cars, this.placements.map(placement => placement.id)]);
    if (signature === this.lastState) return;
    this.lastState = signature; this.onState(this.getState());
  }

  destroy() {
    if (this.disposed) return;
    this.disposed = true; this.scene = undefined; this.placements = []; this.clear();
    this.state.active = false; this.state.reason = 'inactive'; this.emit();
    this.map.off('style.load', this.styleLoaded); this.map.off('render', this.render); this.map.off('resize', this.resize); this.map.off('remove', this.removed);
    document.removeEventListener('visibilitychange', this.visibilityChanged);
    if (this.map.getLayer(LAYER)) this.map.removeLayer(LAYER);
    this.canvas?.remove(); this.canvas = undefined; this.context = undefined; this.matrix = undefined;
  }
}
