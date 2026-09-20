import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const read = path => JSON.parse(readFileSync(new URL('../'+path, import.meta.url)));
const manifest = read('public/models/manifest.json');
const matches = read('public/models/footprint-matches.json');
const candidates = read('docs/residential-model-candidates.json');
const audit = read('docs/RESIDENTIAL_SELECTION_AUDIT.json');
const proof = read('docs/RESIDENTIAL_MODEL_PROVENANCE.json');
const assets = new Map(manifest.assets.map(a => [a.id, a]));
function sorted(v) { if(Array.isArray(v)) return v.map(sorted); if(v && typeof v==='object') return Object.fromEntries(Object.keys(v).sort().map(k => [k,sorted(v[k])])); return v; }
const hash = v => createHash('sha256').update(v).digest('hex');

test('hosted build checksums include every active model and current ownership metadata', () => {
  const deployed = read('public/data/deployment-assets.json').files;
  for (const a of assets.values()) {
    assert.equal(deployed['public/models/'+a.model], a.sha256, a.id+' deployment checksum');
  }
  for (const name of ['manifest.json', 'footprint-matches.json']) {
    const path = 'public/models/'+name;
    assert.equal(deployed[path], hash(readFileSync(new URL('../'+path, import.meta.url))), path);
  }
});

test('every previously published model record, hash and footprint list is preserved exactly', () => {
  const baseline = read('tests/fixtures/preserved-3088-landmarks.json');
  assert.equal(baseline.length, 3088);
  for(const b of baseline) {
    const a=assets.get(b.id); assert.ok(a,b.id);
    assert.equal(hash(JSON.stringify(sorted(a))), b.recordSha256, b.id+' metadata');
    assert.equal(a.sha256,b.glbSha256,b.id+' GLB hash');
    assert.deepEqual(matches[b.id],b.footprints,b.id+' footprint ownership');
  }
});

test('all selected residential source buildings are published once, with no district quota or household cutoff', () => {
  assert.equal(candidates.length,10519);
  assert.equal(audit.newModels,candidates.length);
  assert.equal(manifest.assets.length,3088+candidates.length);
  assert.equal(assets.size,manifest.assets.length);
  assert.equal(new Set(candidates.map(c=>c.id)).size,candidates.length);
  assert.equal(proof.newModels,candidates.length);
  assert.equal(hash(readFileSync(new URL('../docs/residential-model-candidates.json',import.meta.url))),proof.sourceCandidateSha256);
  const owners=new Map();
  for(const [id,bids] of Object.entries(matches)) for(const bid of bids) {
    assert.ok(!owners.has(bid),`${bid} already owned by ${owners.get(bid)}`); owners.set(bid,id);
  }
  const byKind={},districts=new Set();
  for(const c of candidates) {
    const a=assets.get(c.id);assert.ok(a,c.id);
    byKind[c.kind]=(byKind[c.kind]??0)+1;districts.add(c.district);
    assert.equal(a.category,'residential-'+c.kind);
    assert.equal(a.nameKo,c.nameKo); assert.equal(a.district,c.district);
    assert.equal(a.buildingCount,1);
    assert.equal(a.minZoom,16.5);
    assert.deepEqual(matches[c.id],c.buildingIds);
    assert.ok(c.buildingIds.includes(c.buildingId));
    assert.ok(c.sourceUrls.length>0 && c.sourceUrls.every(u=>/^https:\/\//.test(u)));
    assert.ok(a.drawCalls<=3 && a.dimensions.every(n=>Number.isFinite(n)&&n>0));
    if(c.complex) {
      assert.equal(a.apartmentCode,c.complex.code);
      assert.equal(a.householdCount,c.complex.householdCount);
      assert.match(a.householdCountScope,/whole official complex/);
      if(c.complex.sourceHouseholdCount===0) assert.equal(a.householdCount,null);
    } else assert.equal(a.householdCount,undefined);
  }
  assert.equal(districts.size,25);
  assert.deepEqual(byKind,audit.categories);
  assert.equal(audit.counts.identifiedSourceBuildings,audit.counts.alreadyModeledFootprints+candidates.length+audit.rejected.length);
});

test('height provenance covers every new model and explicit parts, and estimates are disclosed', () => {
  assert.equal(proof.assets.length,candidates.length);
  const ids=new Set();let reported=0,estimated=0,partModels=0;
  for(const r of proof.assets) {
    assert.ok(!ids.has(r.id));ids.add(r.id);
    const a=assets.get(r.id);assert.ok(a);
    assert.ok(r.parts.length>0);
    const exposed=r.parts.filter(p=>p.hasExposedGeometry);
    assert.ok(exposed.length>0 && exposed.some(p=>p.baseM===0));
    const max=Math.max(...exposed.map(p=>p.topM));
    assert.ok(Math.abs(max-a.dimensions[1])<.01,r.id+' source height envelope');
    assert.ok(exposed.every(p=>p.topM>p.baseM && p.heightBasis));
    if(a.heightEstimated) estimated++;else reported++;
    if(r.parts.length>1)partModels++;
  }
  assert.ok(reported>0 && estimated>0 && partModels>0);
  assert.equal(proof.newBytes,candidates.reduce((s,c)=>s+assets.get(c.id).bytes,0));
  assert.equal(proof.newTriangles,candidates.reduce((s,c)=>s+assets.get(c.id).triangles,0));
});
