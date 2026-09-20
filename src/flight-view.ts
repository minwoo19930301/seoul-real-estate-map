import { LngLat } from 'maplibre-gl';
import type { Map as MapInstance } from 'maplibre-gl';
import { FlightInputs, RAD, SEOUL_FLIGHT_BOUNDS, clamp, compassHeading, controlByCode, damp, flightTarget, stepFlight } from './flight-model.ts';
import type { FlightBody, FlightBounds, FlightControl } from './flight-model.ts';
export type { FlightControl } from './flight-model.ts';

export type FlightState = {
  active: boolean; paused: boolean; loading: boolean; terrainReady: boolean; message: string;
  position: { lon: number; lat: number }; altitudeM: number; clearanceM: number | null;
  speedMps: number; speedKmh: number; headingDeg: number; pitchDeg: number; rollDeg: number;
};
export type FlightViewOptions = {
  bounds?: FlightBounds;
  onChange?: (state: FlightState) => void;
  onPosition?: (position: { lon: number; lat: number; altitudeM: number }) => void;
  onExitRequest?: () => void;
};
type Handler = { isEnabled(): boolean; enable(): void; disable(): void };
type SavedCamera = {
  center: [number, number]; zoom: number; pitch: number; bearing: number; roll: number; elevation: number;
  clamped: boolean; maxPitch: number; handlers: [Handler, boolean][];
};

export class FlightView {
  private map: MapInstance;
  private options: FlightViewOptions;
  private body: FlightBody = { lon: 127, lat: 37.56, altitudeM: 200, yaw: 0, pitch: -.1, roll: 0, speedMps: 68 };
  private inputs = new FlightInputs();
  private saved?: SavedCamera;
  private active = false;
  private paused = false;
  private terrainReady = false;
  private prepared = false;
  private clearanceM: number | null = null;
  private message = '';
  private frame = 0;
  private lastTime = 0;
  private nextFrameAt = 0;
  private lastEmit = -Infinity;
  private lastPosition = -Infinity;
  private mouseRoll = 0;
  private pointerLocked = false;
  private disposed = false;

  constructor(map: MapInstance, options: FlightViewOptions = {}) {
    this.map = map; this.options = options;
    window.addEventListener('keydown', this.keyDown);
    window.addEventListener('keyup', this.keyUp);
    window.addEventListener('blur', this.onBlur);
    window.addEventListener('pagehide', this.onBlur);
    document.addEventListener('visibilitychange', this.onVisibility);
    document.addEventListener('pointerlockchange', this.onPointerLock);
    document.addEventListener('mousemove', this.onMouseMove);
    map.on('resize', this.onResize);
    map.on('remove', this.onRemove);
    map.getCanvas().addEventListener('webglcontextlost', this.onBlur);
  }

  getState(): FlightState {
    return { active: this.active, paused: this.paused, loading: this.active && !this.terrainReady, terrainReady: this.terrainReady, message: this.message,
      position: { lon: this.body.lon, lat: this.body.lat }, altitudeM: this.body.altitudeM, clearanceM: this.clearanceM,
      speedMps: this.body.speedMps, speedKmh: this.body.speedMps * 3.6, headingDeg: compassHeading(this.body.yaw), pitchDeg: this.body.pitch / RAD, rollDeg: this.body.roll / RAD };
  }

  start(): boolean {
    if (this.disposed) return false;
    if (this.active) return true;
    if (!this.map.getTerrain()) { this.message = '지형을 켠 뒤 비행을 시작해 주세요.'; this.emit(true); return false; }
    this.map.stop();
    const handlers: Handler[] = [this.map.dragPan, this.map.dragRotate, this.map.scrollZoom, this.map.boxZoom, this.map.doubleClickZoom, this.map.keyboard, this.map.touchZoomRotate, this.map.touchPitch];
    this.saved = { center: this.map.getCenter().toArray(), zoom: this.map.getZoom(), pitch: this.map.getPitch(), bearing: this.map.getBearing(), roll: this.map.getRoll(), elevation: this.map.getCenterElevation(), clamped: this.map.getCenterClampedToGround(), maxPitch: this.map.getMaxPitch(), handlers: handlers.map(h => [h, h.isEnabled()]) };
    for (const [handler] of this.saved.handlers) handler.disable();
    const bounds = this.options.bounds ?? SEOUL_FLIGHT_BOUNDS;
    const center = this.map.getCenter();
    this.body = { lon: clamp(center.lng, bounds[0], bounds[2]), lat: clamp(center.lat, bounds[1], bounds[3]), altitudeM: 200, yaw: -this.map.getBearing() * RAD, pitch: -.1, roll: 0, speedMps: 68 };
    this.active = true; this.paused = false; this.terrainReady = false; this.prepared = false; this.clearanceM = null;
    this.inputs.clear(); this.mouseRoll = 0; this.lastPosition = -Infinity;
    this.map.setMaxPitch(Math.max(125, this.saved.maxPitch));
    this.map.setCenterClampedToGround(false);
    this.message = '지형을 준비하는 중…';
    this.prepareTerrain();
    this.map.getCanvas().focus?.({ preventScroll: true });
    this.lastTime = performance.now(); this.nextFrameAt = this.lastTime; this.emit(true); this.schedule();
    return true;
  }

  exit() {
    if (!this.active) return;
    this.active = false; this.paused = false; this.terrainReady = false; this.inputs.clear();
    cancelAnimationFrame(this.frame); this.frame = 0; this.unlockPointer();
    const saved = this.saved; this.saved = undefined;
    if (saved) {
      this.map.stop(); this.map.setCenterClampedToGround(false);
      this.map.jumpTo({ center: saved.center, zoom: saved.zoom, pitch: saved.pitch, bearing: saved.bearing, roll: saved.roll, elevation: saved.elevation }, { flightView: true });
      this.map.setMaxPitch(saved.maxPitch); this.map.setCenterClampedToGround(saved.clamped);
      for (const [handler, enabled] of saved.handlers) if (enabled) handler.enable(); else handler.disable();
    }
    this.message = ''; this.emit(true);
  }

  pause() {
    this.inputs.clear(); this.mouseRoll = 0;
    if (!this.active || this.paused) return;
    this.paused = true; cancelAnimationFrame(this.frame); this.frame = 0; this.unlockPointer();
    this.message = '일시정지'; this.emit(true);
  }
  resume() {
    if (!this.active || !this.paused || document.hidden) return;
    this.paused = false; this.lastTime = performance.now(); this.nextFrameAt = this.lastTime; this.message = ''; this.emit(true); this.schedule();
  }
  togglePause() { if (this.paused) this.resume(); else this.pause(); }
  setControl(control: FlightControl, pressed: boolean, source = 'ui') { this.inputs.set(control, source, pressed && this.active && !this.paused); }

  recover() {
    if (!this.active) return;
    this.inputs.clear(); this.mouseRoll = 0;
    const ground = this.sampleTerrain(this.body.lon, this.body.lat);
    if (ground !== null) this.body.altitudeM = Math.min(1600, Math.max(this.body.altitudeM, Math.max(0, ground) + 150));
    this.body.pitch = 0; this.body.roll = 0; this.body.speedMps = 68;
    if (this.terrainReady) this.updateCamera();
    this.emit(true);
  }

  requestPointerLock() {
    if (!this.active || this.paused || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    try { const pending = this.map.getCanvas().requestPointerLock(); if (pending) void pending.catch(() => {}); } catch { /* Keyboard controls remain available. */ }
  }

  private sampleTerrain(lon: number, lat: number): number | null {
    const ground = this.map.queryTerrainElevation([lon, lat]);
    return ground !== null && Number.isFinite(ground) ? ground : null;
  }
  private prepareTerrain() {
    const terrain = this.map.getTerrain();
    if (!terrain || !this.map.isSourceLoaded(terrain.source)) return;
    const ground = this.sampleTerrain(this.body.lon, this.body.lat);
    if (ground === null) return;
    this.body.altitudeM = Math.max(0, ground) + 150; this.clearanceM = this.body.altitudeM - ground;
    this.prepared = true; this.terrainReady = true; this.message = ''; this.updateCamera(); this.emit(true);
  }
  private schedule() { if (this.active && !this.paused && !this.frame) this.frame = requestAnimationFrame(this.tick); }
  private tick = (now: number) => {
    this.frame = 0;
    if (!this.active || this.paused) return;
    if (now < this.nextFrameAt) { this.schedule(); return; }
    this.nextFrameAt = Math.max(now, this.nextFrameAt + 20);
    const dt = clamp((now - this.lastTime) / 1000, 0, .05); this.lastTime = now;
    if (!this.prepared) this.prepareTerrain();
    else {
      const terrain = this.map.getTerrain();
      const loaded = !!terrain && this.map.isSourceLoaded(terrain.source);
      const result = stepFlight(this.body, this.inputs.state, dt, (lon, lat) => loaded ? this.sampleTerrain(lon, lat) : null, this.options.bounds, this.mouseRoll, this.pointerLocked);
      this.terrainReady = result.terrainReady;
      this.clearanceM = result.clearanceM;
      this.mouseRoll = damp(this.mouseRoll, 0, 4.8, dt);
      this.message = !result.terrainReady ? '지형을 기다리는 중…' : result.bounded ? '서울 비행 구역 안으로 선회합니다.' : '';
      if (this.terrainReady) this.updateCamera();
    }
    if (this.terrainReady && now - this.lastPosition >= 250) {
      this.lastPosition = now; this.options.onPosition?.({ lon: this.body.lon, lat: this.body.lat, altitudeM: this.body.altitudeM });
    }
    this.emit(); this.schedule();
  };
  private updateCamera() {
    const target = flightTarget(this.body);
    const camera = this.map.calculateCameraOptionsFromTo(new LngLat(this.body.lon, this.body.lat), this.body.altitudeM, new LngLat(target.lon, target.lat), target.altitudeM);
    this.map.jumpTo({ ...camera, roll: this.body.roll / RAD }, { flightView: true });
  }
  private emit(force = false) {
    const now = performance.now();
    if (!force && now - this.lastEmit < 100) return;
    this.lastEmit = now; this.options.onChange?.(this.getState());
  }
  private unlockPointer() { this.pointerLocked = false; if (document.pointerLockElement === this.map.getCanvas()) document.exitPointerLock(); }
  private keyDown = (event: KeyboardEvent) => {
    if (!this.active || event.isComposing || event.metaKey || event.altKey) return;
    if (event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return;
    if (event.target instanceof Element && event.target.closest('button, a, [role="button"]') && ['Space', 'Enter'].includes(event.code)) return;
    if (['Escape', 'Space', 'KeyP', 'KeyR'].includes(event.code)) {
      event.preventDefault(); if (event.repeat) return;
      if (event.code === 'Escape') { if (this.options.onExitRequest) this.options.onExitRequest(); else this.exit(); }
      else if (event.code === 'KeyR') this.recover(); else this.togglePause();
      return;
    }
    const control = controlByCode[event.code];
    if (control) { event.preventDefault(); this.setControl(control, true, event.code); }
  };
  private keyUp = (event: KeyboardEvent) => { const control = controlByCode[event.code]; if (control) this.inputs.set(control, event.code, false); };
  private onBlur = () => this.pause();
  private onVisibility = () => { if (document.hidden) this.pause(); };
  private onPointerLock = () => {
    const wasLocked = this.pointerLocked; this.pointerLocked = document.pointerLockElement === this.map.getCanvas();
    if (wasLocked && !this.pointerLocked) this.pause();
  };
  private onMouseMove = (event: MouseEvent) => {
    if (!this.active || this.paused || !this.pointerLocked) return;
    this.body.yaw -= event.movementX * .0022;
    this.body.pitch = clamp(this.body.pitch - event.movementY * .0016, -.48, .58);
    this.mouseRoll = clamp(event.movementX * .0026, -.45, .45);
  };
  private onResize = () => { if (this.active && this.terrainReady) this.updateCamera(); };
  private onRemove = () => this.dispose(false);
  dispose(restoreCamera = true) {
    if (this.disposed) return;
    if (restoreCamera) this.exit();
    this.active = false; this.disposed = true; cancelAnimationFrame(this.frame); this.frame = 0; this.inputs.clear(); this.unlockPointer();
    window.removeEventListener('keydown', this.keyDown); window.removeEventListener('keyup', this.keyUp);
    window.removeEventListener('blur', this.onBlur); window.removeEventListener('pagehide', this.onBlur);
    document.removeEventListener('visibilitychange', this.onVisibility); document.removeEventListener('pointerlockchange', this.onPointerLock); document.removeEventListener('mousemove', this.onMouseMove);
    this.map.off('resize', this.onResize); this.map.off('remove', this.onRemove); this.map.getCanvas().removeEventListener('webglcontextlost', this.onBlur);
  }
}
