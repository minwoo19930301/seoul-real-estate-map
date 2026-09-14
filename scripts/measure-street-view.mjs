// Run against `npm run dev`; the production app intentionally has no debug hook.
// Measures fixed references and natural map frames, without instrumenting private controllers.
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';

const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const viewport = { width: 1440, height: 960 };
  const page = await browser.newPage({ viewport }), errors = [];
  page.setDefaultTimeout(20_000);
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:4173');
  await page.waitForFunction(() => window.__SEOUL_MAP__?.getState().terrainReady && window.__SEOUL_MAP__.scaleReferences);
  await page.getByRole('button', { name: '사람 1인칭 예시', exact: true }).click();
  await page.waitForFunction(() => {
    const app = window.__SEOUL_MAP__;
    return app.streetView.getState().active && app.scaleReferences.getState().placements.length > 0;
  });
  await page.waitForFunction(() => !window.__SEOUL_MAP__.map.isMoving());
  await page.waitForTimeout(2000);
  await page.evaluate(() => {
    const counter = { frames: 0, onRender: null };
    counter.onRender = () => { counter.frames++; };
    window.__streetMeasurement = counter;
    window.__SEOUL_MAP__.map.on('render', counter.onRender);
  });
  const capture = () => page.evaluate(async () => {
    const { cameraEye } = await import('/src/street-view.ts');
    const app = window.__SEOUL_MAP__;
    return { eyeHeight: cameraEye(app.map).height, street: app.streetView.getState(),
      references: app.scaleReferences.getState(), mapFrames: window.__streetMeasurement.frames };
  });
  const fixed = state => JSON.stringify([...state.references.placements].sort((a, b) => a.id.localeCompare(b.id)));
  const before = await capture();
  const samples = [];
  for (let i = 0; i < 10; i++) {
    await page.waitForTimeout(200);
    samples.push(await capture());
  }
  const idleStable = samples.every(sample => fixed(sample) === fixed(before));
  assert.ok(idleStable, 'Fixed reference coordinates changed while idle');
  const direction = await page.locator('#eye-forward').isEnabled() ? '#eye-forward' : '#eye-back';
  await page.locator(direction).click();
  await page.waitForFunction(() => !window.__SEOUL_MAP__.map.isMoving());
  await page.waitForTimeout(300);
  const afterStep = await capture();
  assert.equal(fixed(afterStep), fixed(before), 'Walking the camera moved the fixed references');
  await page.locator('#eye-exit').click();
  const afterExit = await capture();
  assert.equal(afterExit.references.active, false, 'References remained active outside first-person mode');
  assert.equal(afterExit.references.placements.length, 0, 'References were not cleared on exit');
  await page.evaluate(() => {
    window.__SEOUL_MAP__.map.off('render', window.__streetMeasurement.onRender);
    delete window.__streetMeasurement;
  });
  const last = samples.at(-1);
  const summary = { idleStable, fixedAfterStep: fixed(afterStep) === fixed(before),
    clearedAfterExit: afterExit.references.placements.length === 0,
    idleMapFrames: last.mapFrames - before.mapFrames,
    idleReferenceFrames: last.references.frames - before.references.frames,
    drawnPeople: samples.map(sample => sample.references.drawnPeople),
    drawnCars: samples.map(sample => sample.references.drawnCars),
    eyeHeights: samples.map(sample => sample.eyeHeight) };
  const result = { date: new Date().toISOString(), mode: 'static_first_person_references', viewport,
    idleWindowMs: 2000, summary, before, samples, afterStep, afterExit, errors };
  writeFileSync('docs/FIRST_PERSON_MEASUREMENTS.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ ...summary, errors }, null, 2));
  assert.deepEqual(errors, [], 'Browser errors occurred during measurement');
} finally { await browser.close(); }
