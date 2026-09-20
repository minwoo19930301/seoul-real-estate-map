// Adapted from minwoo19930301/seoul-flight-game, commit 792696011ee53921020ccbbf5f39105081da06bc.
// Arcade flight in ground metres; this is not an aerodynamic or collision simulator.
export const RAD = Math.PI / 180;
export const METRES_PER_DEGREE = 6371008.8 * RAD;
export const SEOUL_FLIGHT_BOUNDS: FlightBounds = [126.72, 37.39, 127.25, 37.76];
export type FlightBounds = [west: number, south: number, east: number, north: number];
export type FlightControl = 'pitchUp' | 'pitchDown' | 'bankLeft' | 'bankRight' | 'yawLeft' | 'yawRight' | 'boost' | 'brake' | 'level';
export type FlightInputState = Record<FlightControl, boolean>;
export type FlightBody = { lon: number; lat: number; altitudeM: number; yaw: number; pitch: number; roll: number; speedMps: number };
export type TerrainSampler = (lon: number, lat: number) => number | null;

export const controlByCode: Record<string, FlightControl> = {
  KeyW: 'pitchUp', ArrowUp: 'pitchUp', KeyS: 'pitchDown', ArrowDown: 'pitchDown',
  KeyA: 'bankLeft', ArrowLeft: 'bankLeft', KeyD: 'bankRight', ArrowRight: 'bankRight',
  KeyQ: 'yawLeft', KeyE: 'yawRight', ShiftLeft: 'boost', ShiftRight: 'boost',
  ControlLeft: 'brake', ControlRight: 'brake', KeyL: 'level',
};

export class FlightInputs {
  private sources = new Map<FlightControl, Set<string>>();
  readonly state: FlightInputState = { pitchUp: false, pitchDown: false, bankLeft: false, bankRight: false, yawLeft: false, yawRight: false, boost: false, brake: false, level: false };
  set(control: FlightControl, source: string, active: boolean) {
    if (!(control in this.state)) return;
    let sources = this.sources.get(control);
    if (!sources) { sources = new Set(); this.sources.set(control, sources); }
    if (active) sources.add(source); else sources.delete(source);
    this.state[control] = sources.size > 0;
  }
  clear() { this.sources.clear(); for (const control of Object.keys(this.state) as FlightControl[]) this.state[control] = false; }
}

export const clamp = (x: number, min: number, max: number) => Math.max(min, Math.min(max, x));
export const damp = (a: number, b: number, rate: number, dt: number) => b + (a - b) * Math.exp(-rate * dt);
export const compassHeading = (yaw: number) => ((-yaw / RAD) % 360 + 360) % 360;

export function updateAttitude(body: Pick<FlightBody, 'yaw' | 'pitch' | 'roll'>, input: FlightInputState, dt: number, mouseRoll = 0, pointerLocked = false) {
  const pitch = Number(input.pitchUp) - Number(input.pitchDown);
  const bank = Number(input.bankRight) - Number(input.bankLeft);
  const yaw = Number(input.yawRight) - Number(input.yawLeft);
  body.pitch += pitch * .82 * dt;
  body.yaw -= (bank * .62 + yaw * .86) * dt;
  if (input.level) body.pitch = damp(body.pitch, 0, 3.4, dt);
  else if (!pointerLocked && !pitch) body.pitch = damp(body.pitch, 0, 1.3, dt);
  body.roll = damp(body.roll, input.level ? 0 : clamp(-mouseRoll * 1.8 - bank * .34 - yaw * .18, -.72, .72), input.level ? 4.2 : 3.2, dt);
  body.pitch = clamp(body.pitch, -.48, .58);
}

export function moveMetres(lon: number, lat: number, eastM: number, northM: number) {
  const nextLat = lat + northM / METRES_PER_DEGREE;
  return { lon: lon + eastM / (METRES_PER_DEGREE * Math.cos((lat + nextLat) / 2 * RAD)), lat: nextLat };
}

export function forwardVector(body: Pick<FlightBody, 'yaw' | 'pitch'>) {
  return { east: -Math.sin(body.yaw) * Math.cos(body.pitch), north: Math.cos(body.yaw) * Math.cos(body.pitch), up: Math.sin(body.pitch) };
}

export function flightTarget(body: FlightBody, distanceM = 300) {
  const forward = forwardVector(body);
  return { ...moveMetres(body.lon, body.lat, forward.east * distanceM, forward.north * distanceM), altitudeM: body.altitudeM + forward.up * distanceM };
}

/** Unknown DEM freezes translation; boundary correction precedes the final terrain sample. */
export function stepFlight(body: FlightBody, input: FlightInputState, elapsedSeconds: number, terrain: TerrainSampler, bounds: FlightBounds = SEOUL_FLIGHT_BOUNDS, mouseRoll = 0, pointerLocked = false) {
  const dt = Number.isFinite(elapsedSeconds) ? clamp(elapsedSeconds, 0, .05) : 0;
  updateAttitude(body, input, dt, mouseRoll, pointerLocked);
  body.speedMps = damp(body.speedMps, input.brake ? 40 : input.boost ? 116 : 74, 2.1, dt);
  const forward = forwardVector(body);
  const proposed = moveMetres(body.lon, body.lat, forward.east * body.speedMps * dt, forward.north * body.speedMps * dt);
  const lon = clamp(proposed.lon, bounds[0], bounds[2]), lat = clamp(proposed.lat, bounds[1], bounds[3]);
  const bounded = lon !== proposed.lon || lat !== proposed.lat;
  if (bounded) {
    const east = ((bounds[0] + bounds[2]) / 2 - lon) * Math.cos(lat * RAD);
    const north = (bounds[1] + bounds[3]) / 2 - lat;
    const targetYaw = -Math.atan2(east, north);
    const turn = Math.atan2(Math.sin(targetYaw - body.yaw), Math.cos(targetYaw - body.yaw));
    body.yaw += turn * Math.min(1, dt * 1.8);
  }
  const ground = terrain(lon, lat);
  if (ground === null || !Number.isFinite(ground)) return { terrainReady: false, clearanceM: null, bounded };
  body.lon = lon; body.lat = lat;
  body.altitudeM += forward.up * body.speedMps * dt;
  const floor = Math.max(0, ground) + 18;
  if (body.altitudeM < floor) {
    body.altitudeM = floor; body.pitch = Math.max(body.pitch, .05); body.roll = damp(body.roll, 0, 5.4, dt);
  }
  const ceiling = Math.max(1600, floor);
  if (body.altitudeM > ceiling) { body.altitudeM = ceiling; body.pitch = Math.min(body.pitch, 0); }
  return { terrainReady: true, clearanceM: body.altitudeM - ground, bounded };
}
