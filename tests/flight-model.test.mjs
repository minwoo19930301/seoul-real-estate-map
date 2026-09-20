import test from 'node:test';
import assert from 'node:assert/strict';
import { FlightInputs, RAD, METRES_PER_DEGREE, compassHeading, flightTarget, moveMetres, stepFlight, updateAttitude } from '../src/flight-model.ts';
import { FlightView } from '../src/flight-view.ts';

const body = (patch = {}) => ({ lon: 127, lat: 37.55, altitudeM: 250, yaw: 0, pitch: 0, roll: 0, speedMps: 74, ...patch });
const distance = (a, b) => Math.hypot((a.lon - b.lon) * METRES_PER_DEGREE * Math.cos((a.lat + b.lat) / 2 * RAD), (a.lat - b.lat) * METRES_PER_DEGREE);

test('flight headings and real metre travel agree at different latitudes', () => {
  for (const lat of [0, 37.55, 60]) {
    assert.ok(Math.abs(distance({ lon: 127, lat }, moveMetres(127, lat, 300, 400)) - 500) < .01);
  }
  for (const [yaw, heading, axis, direction] of [[0, 0, 'lat', 1], [-Math.PI / 2, 90, 'lon', 1], [-Math.PI, 180, 'lat', -1], [Math.PI / 2, 270, 'lon', -1]]) {
    const b = body({ yaw }), before = { ...b };
    stepFlight(b, new FlightInputs().state, .05, () => 0);
    assert.equal(compassHeading(yaw), heading);
    assert.equal(Math.sign(b[axis] - before[axis]), direction);
    assert.ok(Math.abs(distance(before, b) - 3.7) < .001);
  }
});

test('named banking/rudder directions remain consistent at 20, 60 and 120 Hz', () => {
  for (const [control, direction] of [['bankRight', 1], ['bankLeft', -1], ['yawRight', 1], ['yawLeft', -1]]) {
    const headings = [];
    for (const hz of [20, 60, 120]) {
      const input = new FlightInputs(), b = body(); input.set(control, 'test', true);
      for (let i = 0; i < hz; i++) stepFlight(b, input.state, 1 / hz, () => 0);
      assert.equal(Math.sign(-b.yaw), direction);
      assert.equal(Math.sign(-b.roll), direction);
      assert.equal(Math.sign(b.lon - 127), direction);
      headings.push(b.yaw);
    }
    assert.ok(Math.max(...headings) - Math.min(...headings) < 1e-12);
  }
});

test('climb/dive, level recovery and boost/brake have distinct bounded effects', () => {
  for (const [control, sign] of [['pitchUp', 1], ['pitchDown', -1]]) {
    const b = body({ altitudeM: 500 }), inputs = new FlightInputs(); inputs.set(control, 'test', true);
    for (let i = 0; i < 120; i++) stepFlight(b, inputs.state, 1 / 60, () => 0);
    assert.equal(Math.sign(b.altitudeM - 500), sign); assert.ok(b.pitch >= -.48 && b.pitch <= .58);
    inputs.clear(); inputs.set('level', 'test', true);
    for (let i = 0; i < 240; i++) updateAttitude(b, inputs.state, 1 / 60, 0, true);
    assert.ok(Math.abs(b.pitch) < 1e-5 && Math.abs(b.roll) < 1e-5);
  }
  const distances = [];
  for (const control of ['boost', null, 'brake']) {
    const b = body(), input = new FlightInputs(); if (control) input.set(control, 'test', true);
    for (let i = 0; i < 200; i++) stepFlight(b, input.state, .05, () => 0);
    distances.push(distance(body(), b));
  }
  assert.ok(distances[0] > distances[1] * 1.4 && distances[2] < distances[1] * .65);
});

test('terrain is sampled after region clamp, and floor/ceiling never use stale coordinates', () => {
  const b = body({ lon: 127.000999, yaw: -Math.PI / 2, altitudeM: 50, pitch: -.4 });
  let sample;
  const result = stepFlight(b, new FlightInputs().state, .05, (lon, lat) => { sample = [lon, lat]; return 470; }, [126.99, 37.54, 127.001, 37.56]);
  assert.deepEqual(sample, [b.lon, b.lat]); assert.equal(b.lon, 127.001);
  assert.equal(b.altitudeM, 488); assert.equal(result.clearanceM, 18); assert.ok(result.bounded);
  const high = body({ altitudeM: 1700, pitch: .4 });
  stepFlight(high, new FlightInputs().state, .05, () => 0);
  assert.equal(high.altitudeM, 1600); assert.equal(high.pitch, 0);
});

test('missing or invalid terrain freezes translation, and long frame gaps cannot teleport', () => {
  for (const ground of [null, NaN, Infinity]) {
    const b = body({ pitch: -.3 }), before = { ...b };
    const result = stepFlight(b, new FlightInputs().state, .05, () => ground);
    assert.equal(result.terrainReady, false); assert.equal(result.clearanceM, null);
    assert.deepEqual([b.lon, b.lat, b.altitudeM], [before.lon, before.lat, before.altitudeM]);
  }
  const a = body(), b = body(), input = new FlightInputs(); input.set('bankRight', 'test', true);
  stepFlight(a, input.state, 45, () => 0); stepFlight(b, input.state, .05, () => 0);
  assert.deepEqual(a, b);
});

test('short camera target follows pitch and heading without a distant horizon centre', () => {
  for (const pitch of [-.48, 0, .58]) {
    const b = body({ yaw: -Math.PI / 2, pitch }), target = flightTarget(b);
    assert.ok(target.lon > b.lon); assert.ok(Math.abs(target.lat - b.lat) < 1e-10);
    assert.ok(Math.abs(Math.hypot(distance(b, target), target.altitudeM - b.altitudeM) - 300) < .01);
  }
});

test('independent keyboard and touch sources do not release each other', () => {
  const inputs = new FlightInputs();
  for (const source of ['KeyW', 'ArrowUp', 'finger:3']) inputs.set('pitchUp', source, true);
  inputs.set('pitchUp', 'KeyW', false); inputs.set('pitchUp', 'finger:3', false);
  assert.equal(inputs.state.pitchUp, true);
  inputs.clear(); assert.ok(Object.values(inputs.state).every(x => !x));
});

class Events {
  listeners = new Map();
  addEventListener(type, fn) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn); }
  removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }
  fire(type, detail = {}) { for (const fn of [...this.listeners.get(type) ?? []]) fn({ type, ...detail }); }
}
class FakeElement extends Events {
  constructor(kind = '') { super(); this.kind = kind; }
  closest(selector) { return this.kind && selector.includes(this.kind) ? this : null; }
}
function harness(t) {
  const originals = new Map();
  const replace = (key, value) => { originals.set(key, Object.getOwnPropertyDescriptor(globalThis, key)); Object.defineProperty(globalThis, key, { configurable: true, writable: true, value }); };
  const win = new Events(), doc = new Events(), canvas = new FakeElement(); let now = 0, next = 0;
  const frames = new Map();
  doc.hidden = false; doc.pointerLockElement = null; doc.exitPointerLock = () => { doc.pointerLockElement = null; doc.fire('pointerlockchange'); };
  win.matchMedia = () => ({ matches: true });
  replace('window', win); replace('document', doc); replace('Element', FakeElement); replace('performance', { now: () => now });
  replace('requestAnimationFrame', fn => { frames.set(++next, fn); return next; }); replace('cancelAnimationFrame', id => frames.delete(id));
  const events = new Events();
  const map = {
    loaded: true, terrain: { source: 'local-terrain' }, ground: 40, camera: { center: [127, 37.55], zoom: 17, pitch: 58, bearing: 17, roll: 3, elevation: 40 }, maxPitch: 85, clamped: true, jumps: [],
    on: (name, fn) => events.addEventListener(name, fn), off: (name, fn) => events.removeEventListener(name, fn),
    getCanvas: () => canvas, getTerrain() { return this.terrain; }, isSourceLoaded() { return this.loaded; }, queryTerrainElevation() { return this.ground; },
    getCenter() { return { lng: this.camera.center[0], lat: this.camera.center[1], toArray: () => [...this.camera.center] }; },
    getZoom() { return this.camera.zoom; }, getPitch() { return this.camera.pitch; }, getBearing() { return this.camera.bearing; }, getRoll() { return this.camera.roll; }, getCenterElevation() { return this.camera.elevation; },
    getMaxPitch() { return this.maxPitch; }, setMaxPitch(x) { this.maxPitch = x; }, getCenterClampedToGround() { return this.clamped; }, setCenterClampedToGround(x) { this.clamped = x; }, stop() {},
    calculateCameraOptionsFromTo(from, altitude, to, targetAltitude) { return { center: [to.lng, to.lat], elevation: targetAltitude, pitch: 90, bearing: 17, zoom: 18 }; },
    jumpTo(options, data) { this.camera = { ...this.camera, ...options }; this.jumps.push({ ...options, data }); },
  };
  for (const name of ['dragPan', 'dragRotate', 'scrollZoom', 'boxZoom', 'doubleClickZoom', 'keyboard', 'touchZoomRotate', 'touchPitch']) {
    map[name] = { enabled: name !== 'scrollZoom', isEnabled() { return this.enabled; }, enable() { this.enabled = true; }, disable() { this.enabled = false; } };
  }
  t.after(() => { for (const [key, descriptor] of originals) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; } });
  return { map, win, doc, canvas, frames, step(ms = 20) { now += ms; const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(fn => fn(now)); }, key(code, target = canvas, extra = {}) { let prevented = false; win.fire('keydown', { code, target, preventDefault() { prevented = true; }, ...extra }); return prevented; } };
}

test('controller waits for DEM, throttles callbacks, pauses without drift and restores camera/handlers', t => {
  const h = harness(t), original = structuredClone(h.map.camera); let updates = 0, positions = 0;
  const flight = new FlightView(h.map, { onChange: () => updates++, onPosition: () => positions++ });
  h.map.loaded = false; assert.equal(flight.start(), true); assert.equal(flight.getState().loading, true);
  h.step(1000); assert.equal(h.map.jumps.length, 0);
  h.map.loaded = true; h.step(); assert.equal(flight.getState().altitudeM, 190);
  updates = 0; positions = 0;
  for (let i = 0; i < 120; i++) h.step(1000 / 120);
  assert.ok(updates <= 10); assert.ok(positions <= 4); assert.ok(h.map.jumps.length <= 53);
  assert.ok(h.map.jumps.every(j => j.data.flightView));
  h.key('ShiftLeft'); h.win.fire('blur'); const paused = flight.getState();
  assert.equal(paused.paused, true); assert.equal(h.frames.size, 0); h.step(60000); assert.deepEqual(flight.getState(), paused);
  flight.resume(); h.step(); assert.ok(distance(paused.position, flight.getState().position) < 6);
  flight.exit(); assert.equal(h.frames.size, 0); assert.deepEqual(h.map.camera, original);
  assert.equal(h.map.maxPitch, 85); assert.equal(h.map.clamped, true);
  assert.equal(h.map.dragPan.isEnabled(), true); assert.equal(h.map.scrollZoom.isEnabled(), false);
  flight.dispose(); assert.ok([...h.win.listeners.values()].every(set => set.size === 0));
});

test('form typing is ignored, escape delegates exit and repeated start never adds a second animation loop', t => {
  const h = harness(t); let exits = 0;
  const flight = new FlightView(h.map, { onExitRequest: () => { exits++; flight.exit(); } });
  flight.start(); flight.start(); assert.equal(h.frames.size, 1);
  assert.equal(h.key('KeyW', new FakeElement('input')), false);
  assert.equal(h.key('Space', new FakeElement('button')), false); assert.equal(flight.getState().paused, false);
  h.key('Space'); assert.equal(flight.getState().paused, true); h.key('Space'); assert.equal(flight.getState().paused, false);
  h.key('Escape'); assert.equal(exits, 1); assert.equal(flight.getState().active, false); assert.equal(h.frames.size, 0);
  flight.start(); h.doc.hidden = true; h.doc.fire('visibilitychange'); assert.equal(flight.getState().paused, true);
  flight.resume(); assert.equal(flight.getState().paused, true); flight.dispose();
});
