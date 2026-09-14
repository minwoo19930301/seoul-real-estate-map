import { LngLat, MercatorCoordinate } from 'maplibre-gl';
import type { Map as MapInstance } from 'maplibre-gl';
import { prepareRoute, sampleRoute } from './mobility-math.ts';
import type { MobilityRoute, PreparedRoute, RouteCoordinate } from './mobility-math.ts';

type Anchor = { route: PreparedRoute; distance: number; offset: number };
export type StreetState = { active: boolean; loading: boolean; message: string; coordinate?: RouteCoordinate; eyeHeight?: number; canForward: boolean; canBack: boolean };
export type StreetScene = { routes: MobilityRoute[]; coordinate: RouteCoordinate; bearing: number };
type StreetViewOptions = {
  onState: (state: StreetState) => void;
  onMode: (active: boolean, preserveView?: boolean) => void;
  onScene?: (scene: StreetScene | null) => void;
};
const RAD = Math.PI / 180;
export const EYE_HEIGHT = 1.7;
export const EYE_PITCH = 82;

/** Snap to a real line; prefer a nearby pedestrian line over a car centreline. */
export function nearestStreet(routes: MobilityRoute[], center: [number, number]): Anchor | null {
  const candidates: Anchor[] = [];
  const sx = 111195 * Math.cos(center[1] * RAD), sy = 111195;
  for (const source of routes) {
    const route = prepareRoute(source);
    if (!route) continue;
    let best: Anchor | undefined;
    route.segments.forEach((segment, i) => {
      const a = route.coordinates[i], b = route.coordinates[i + 1];
      const ax = (a[0] - center[0]) * sx, ay = (a[1] - center[1]) * sy;
      const dx = (b[0] - a[0]) * sx, dy = (b[1] - a[1]) * sy;
      const t = Math.max(0, Math.min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)));
      const offset = Math.hypot(ax + t * dx, ay + t * dy);
      if (!best || offset < best.offset) best = { route, distance: segment.start + t * segment.length, offset };
    });
    if (best && best.offset <= 350) candidates.push(best);
  }
  const pedestrian = candidates.filter(c => c.route.source.kind === 'pedestrian' && c.offset <= 60);
  return (pedestrian.length ? pedestrian : candidates).sort((a, b) => a.offset - b.offset)[0] ?? null;
}

export function routeBearing(route: PreparedRoute, distance: number): number {
  const a = sampleRoute(route, Math.max(0, distance - 0.2)).coordinate;
  const b = sampleRoute(route, Math.min(route.length, distance + 2)).coordinate;
  return Math.atan2((b[0] - a[0]) * Math.cos(a[1] * RAD), b[1] - a[1]) / RAD;
}

/** Public MapLibre camera values, useful for checking the actual eye altitude. */
export function cameraEye(map: MapInstance) {
  const center = MercatorCoordinate.fromLngLat(map.getCenter(), map.getCenterElevation());
  const pitch = map.getPitch() * RAD, bearing = map.getBearing() * RAD;
  const distance = map.getCanvas().clientHeight / (2 * Math.tan(map.getVerticalFieldOfView() * RAD / 2)) / (512 * 2 ** map.getZoom());
  const eye = new MercatorCoordinate(center.x - Math.sin(bearing) * Math.sin(pitch) * distance,
    center.y + Math.cos(bearing) * Math.sin(pitch) * distance, center.z + Math.cos(pitch) * distance);
  const coordinate = eye.toLngLat();
  const altitude = map.getCenterElevation() + Math.cos(pitch) * distance / center.meterInMercatorCoordinateUnits();
  const ground = map.queryTerrainElevation(coordinate);
  return { coordinate: coordinate.toArray(), altitude, ground, height: ground === null ? null : altitude - ground };
}

export class StreetView {
  private anchor?: Anchor;
  private saved?: { center: [number, number]; zoom: number; pitch: number; bearing: number; elevation: number; clamped: boolean };
  private controller?: AbortController;
  private epoch = 0;
  private turnOffset = 0;
  private modeEntered = false;
  private entering = false;
  private anchorGround?: number;
  private state: StreetState = { active: false, loading: false, message: '', canForward: false, canBack: false };
  private map: MapInstance;
  private options: StreetViewOptions;
  constructor(map: MapInstance, options: StreetViewOptions) {
    this.map = map; this.options = options;
    map.on('idle', () => {
      if (!this.state.active || !this.state.coordinate || this.anchorGround === undefined) return;
      const ground = map.queryTerrainElevation(this.state.coordinate.slice(0, 2) as [number, number]);
      // Refine only the ground altitude. Never reapply a stored zoom or position
      // on idle: doing that undoes the user's navigation after the next frame.
      if (ground !== null && Math.abs(ground - this.anchorGround) > .03) {
        const delta = ground - this.anchorGround; this.anchorGround = ground;
        map.setCenterElevation(map.getCenterElevation() + delta, { streetView: true });
        this.state.eyeHeight = cameraEye(map).height ?? undefined; this.emit();
      }
    });
    map.on('movestart', event => {
      if (!(event as typeof event & { streetView?: boolean }).streetView && (this.state.active || this.state.loading)) this.detach();
    });
  }
  getState() { return { ...this.state }; }
  private emit() { this.options.onState(this.getState()); }

  async enter(center = this.map.getCenter().toArray() as [number, number], bearing?: number) {
    this.controller?.abort(); this.controller = new AbortController();
    const epoch = ++this.epoch;
    this.options.onScene?.(null);
    // A new eye-view request owns a fresh return/failure snapshot. Reusing an
    // older session here sends a failed retry back to a place already left.
    if (this.modeEntered) { this.modeEntered = false; this.options.onMode(false, true); }
    this.saved = { center: this.map.getCenter().toArray(), zoom: this.map.getZoom(), pitch: this.map.getPitch(), bearing: this.map.getBearing(), elevation: this.map.getCenterElevation(), clamped: this.map.getCenterClampedToGround() };
    this.state = { active: false, loading: true, message: '주변 길에서 눈높이 시점을 준비하는 중…', canForward: false, canBack: false }; this.emit();
    try {
      const readRoutes = async (dx: number, dy: number) => {
        const bbox = [center[0] - dx, center[1] - dy, center[0] + dx, center[1] + dy];
        const response = await fetch(`/api/mobility?bbox=${bbox.join(',')}`, { signal: this.controller!.signal });
        if (!response.ok) throw new Error('이 위치의 길을 불러오지 못했습니다.');
        return response.json() as Promise<{ routes: MobilityRoute[] }>;
      };
      // Keep nearby paths and size references in the API's bounded route set.
      // A city-wide sampling window can omit the road right beside the viewer.
      let data = await readRoutes(.0015, .0015);
      if (epoch !== this.epoch) return;
      let anchor = nearestStreet(data.routes, center);
      if (!anchor) {
        data = await readRoutes(.004, .003);
        if (epoch !== this.epoch) return;
        anchor = nearestStreet(data.routes, center);
      }
      if (!anchor) throw new Error('주변에 높이를 확인할 수 있는 길이 없습니다. 다른 위치에서 눌러 주세요.');
      this.anchor = anchor;
      this.turnOffset = bearing === undefined ? 0 : bearing - routeBearing(anchor.route, anchor.distance);
      this.options.onMode(true);
      this.modeEntered = true;
      const at = sampleRoute(anchor.route, anchor.distance).coordinate;
      this.map.setCenterClampedToGround(true);
      this.map.jumpTo({ center: [at[0], at[1]], zoom: 19.5, pitch: 30, bearing: bearing ?? routeBearing(anchor.route, anchor.distance) }, { streetView: true });
      await this.waitForTerrain(this.controller.signal);
      if (epoch !== this.epoch) return;
      this.entering = true;
      this.position();
      // The high-pitch camera selects a different set of terrain tiles. Keep
      // controls in loading state until that rendered tile selection is ready.
      await this.waitForTerrain(this.controller.signal, true);
      if (epoch !== this.epoch) return;
      this.entering = false;
      this.position();
      // Fixed references belong to this completed entry, not each subsequent
      // step, turn or DEM refinement. A superseded entry must never publish.
      if (epoch === this.epoch && this.state.active && this.state.coordinate) {
        this.options.onScene?.({ routes: data.routes, coordinate: [...this.state.coordinate], bearing: this.map.getBearing() });
      }
    } catch (error) {
      if (epoch !== this.epoch || this.controller.signal.aborted) return;
      this.exit(true);
      this.state.message = error instanceof Error ? error.message : '눈높이 시점을 준비하지 못했습니다.'; this.emit();
    }
  }

  private waitForTerrain(signal: AbortSignal, requireFrame = false) {
    return new Promise<void>((resolve, reject) => {
      let rendered = !requireFrame;
      const onRender = () => { rendered = true; check(); };
      const finish = (error?: Error) => { clearTimeout(timeout); this.map.off('render', onRender); this.map.off('sourcedata', check); this.map.off('idle', check); signal.removeEventListener('abort', abort); error ? reject(error) : resolve(); };
      const check = () => { if (rendered && this.map.getTerrain() && this.map.isSourceLoaded('local-terrain') && !this.map.isMoving()) finish(); };
      const abort = () => finish(new DOMException('Aborted', 'AbortError'));
      const timeout = setTimeout(() => finish(new Error('지형을 불러오는 데 시간이 걸립니다. 잠시 후 다시 눌러 주세요.')), 12000);
      if (requireFrame) this.map.on('render', onRender);
      this.map.on('sourcedata', check); this.map.on('idle', check); signal.addEventListener('abort', abort, { once: true }); check();
    });
  }

  private position() {
    if (!this.anchor) return;
    const { route, distance } = this.anchor;
    const at = sampleRoute(route, distance).coordinate;
    const from = new LngLat(at[0], at[1]);
    const ground = this.map.queryTerrainElevation(from);
    if (ground === null) {
      if (this.entering || this.state.loading) throw new Error('이 위치의 지면 높이를 확인하지 못했습니다. 다른 길에서 다시 눌러 주세요.');
      this.state.message = '지형을 불러오면 다시 이동할 수 있습니다.'; this.emit(); return;
    }
    const bearing = routeBearing(route, distance) + this.turnOffset;
    const forward = Math.cos(this.turnOffset * RAD) >= 0;
    const eye = MercatorCoordinate.fromLngLat(from, ground + EYE_HEIGHT);
    const d = 12 * eye.meterInMercatorCoordinateUnits(), b = bearing * RAD;
    const target = new MercatorCoordinate(eye.x + Math.sin(b) * d, eye.y - Math.cos(b) * d, eye.z - d / Math.tan(EYE_PITCH * RAD));
    this.map.setCenterClampedToGround(false);
    this.map.jumpTo({ ...this.map.calculateCameraOptionsFromTo(from, ground + EYE_HEIGHT, target.toLngLat(), target.toAltitude()), roll: 0 }, { streetView: true });
    this.anchorGround = ground;
    this.state = { active: !this.entering, loading: this.entering, message: this.entering ? '가까운 지면을 맞추는 중…' : '눈높이 약 1.7m · 지형 1×', coordinate: at, eyeHeight: cameraEye(this.map).height ?? undefined,
      canForward: forward ? distance < route.length - 0.2 : distance > 0.2,
      canBack: forward ? distance > 0.2 : distance < route.length - 0.2 };
    this.emit();
  }

  step(direction: 1 | -1) {
    if (!this.state.active || !this.anchor) return;
    const facing = Math.cos(this.turnOffset * RAD) >= 0 ? 1 : -1;
    this.anchor.distance = Math.max(0, Math.min(this.anchor.route.length, this.anchor.distance + direction * facing * 3)); this.position();
  }
  turn(direction: 1 | -1) { if (this.state.active) { this.turnOffset += direction * 15; this.position(); } }
  refresh() { if (this.state.active) this.position(); }
  private detach() {
    ++this.epoch; this.controller?.abort();
    this.options.onScene?.(null);
    this.anchor = undefined; this.anchorGround = undefined; this.entering = false;
    this.state = { active: false, loading: false, message: this.modeEntered ? '자유 시점 · 현재 지형 배율 유지' : '', canForward: false, canBack: false };
    // Keep the current terrain, camera and clamping policy untouched. A terrain
    // reset here changes the camera distance while a wheel/button zoom is running.
    if (this.modeEntered) this.options.onMode(false, true);
    else this.saved = undefined;
    this.emit();
  }
  exit(restore = true) {
    ++this.epoch; this.controller?.abort();
    this.options.onScene?.(null);
    const saved = this.saved;
    this.saved = undefined; this.anchor = undefined; this.anchorGround = undefined; this.entering = false;
    this.state = { active: false, loading: false, message: '', canForward: false, canBack: false };
    if (restore) this.map.setCenterClampedToGround(saved?.clamped ?? true);
    if (this.modeEntered) this.options.onMode(false, !restore);
    this.modeEntered = false;
    if (restore && saved) this.map.jumpTo(saved);
    this.emit();
  }
}
