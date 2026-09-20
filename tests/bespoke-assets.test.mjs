import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { referenceManifest } from '../src/reference-models.ts';
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const legacy=[...json('public/models/manifest.json').assets,...json('public/models/reference-manifest.json').assets];
const manifest=referenceManifest(json('public/models/bespoke-manifest.json'),legacy);
const evidence=json('docs/model-audit/published-bespoke.json');
const cache=new Map();
async function scene(id) {
  if(cache.has(id))return cache.get(id);
  const a=manifest.assets.find(a=>a.id===id);assert.ok(a,id+' published');
  const b=fs.readFileSync('public/models/'+a.model);
  const g=await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
  cache.set(id,g.scene);return g.scene;
}
function meshes(s,pattern) {const r=[];s.traverse(o=>{if(o.isMesh&&pattern.test(o.name))r.push(o);});return r;}
function bounds(objects) {const b=new THREE.Box3();for(const o of objects)b.union(new THREE.Box3().setFromObject(o));return b;}

test('reviewed Blender exports retain geographic anchors, source evidence, editable scenes and valid geometry',async()=>{
  const deployment=json('public/data/deployment-assets.json').files;
  assert.equal(sha('public/models/bespoke-manifest.json'),deployment['public/models/bespoke-manifest.json']);
  for(const a of manifest.assets){
    assert.equal(sha('public/models/'+a.model),a.sha256);assert.equal(deployment['public/models/'+a.model],a.sha256);
    const record=a.sourceRecord;assert.equal(sha(record.blendSource),record.blendSha256);
    const e=evidence.sites[record.siteId];assert.equal(e.review.status,'visually-reviewed');assert.ok(e.review.comparisons.length&&e.sources.length);
    for(const p of e.review.renders)assert.ok(fs.statSync(p).size>1000);
    for(const p of e.mcpEvidence){assert.equal(sha(p.path),p.sha256);assert.ok(json(p.path).some(call=>call.tool==='execute_blender_code'&&!call.isError&&call.content.some(c=>c.text?.includes('Code executed successfully'))));}
    const s=await scene(a.id),b=bounds(meshes(s,/.*/));
    assert.ok(Math.abs(b.min.y)<.01,a.id+' ground datum');
    b.getSize(new THREE.Vector3()).toArray().forEach((n,i)=>assert.ok(Math.abs(n-a.dimensions[i])<.001,a.id+' manifest dimensions'));
    const sx=111319.49079327358*Math.cos(a.coordinate.lat*Math.PI/180),sy=111319.49079327358;
    [a.coordinate.lon+b.min.x/sx,a.coordinate.lat-b.max.z/sy,a.coordinate.lon+b.max.x/sx,a.coordinate.lat-b.min.z/sy].forEach((v,i)=>assert.ok(Math.abs(v-a.geoBounds[i])<1e-8,a.id+' anchored geographic bounds'));
    for(const m of meshes(s,/.*/)){
      assert.ok(m.matrixWorld.equals(new THREE.Matrix4()),a.id+' baked transform');
      const p=m.geometry.attributes.position,n=m.geometry.attributes.normal;assert.equal(p.count,n.count);
      for(let i=0;i<p.count;i++){assert.ok([p.getX(i),p.getY(i),p.getZ(i)].every(Number.isFinite));assert.ok(Math.abs(Math.hypot(n.getX(i),n.getY(i),n.getZ(i))-1)<.01);}
    }
  }
});

test('the terminal low wing is not a51m extrusion of the complete L footprint',async()=>{
 const s=await scene('bespoke-seoul-express-terminal');
 const low=meshes(s,/Yeongdong|Low_wing|Annex/i);assert.ok(low.length,'separate low wing geometry exists');
 const b=bounds(low);assert.ok(b.max.y<14,'annex including its glazed entrance canopy stays below14m');
 assert.ok(bounds(meshes(s,/Low_Yeongdong.*Grey_flat_roof/)).max.y<10,'long wing roof stays below10m');
 assert.equal(manifest.assets.find(a=>a.id==='bespoke-seoul-express-terminal').footprintIds.length,1,'Honam and separate annex are not claimed');
});

test('SKY official floors and ownership differ per tower without absorbing the business tower',async()=>{
 for(const [letter,floors,height] of [['a',64,196],['b',65,199],['c',63,193],['d',65,199]]){
  const a=manifest.assets.find(a=>a.id==='bespoke-skyl65-'+letter);assert.equal(a.sourceRecord.buildingFacts.floors,floors);assert.equal(a.dimensions[1],height);
  assert.equal(a.footprintIds.length,1);assert.ok(!a.footprintIds.includes('ccde143f-4ead-46da-97b5-873021cf0e49'));
  const s=await scene(a.id);assert.ok(meshes(s,/crown/).length);assert.ok(meshes(s,/six-wing/).length);
 }
});

test('Jamsu navigation crest remains below Banpo and above its own level approaches',async()=>{
 const s=await scene('bespoke-banpo-jamsu'),low=meshes(s,/Jamsu_18m_low_deck/),high=meshes(s,/Banpo_entire_OSM_deck/);
 assert.equal(low.length,1);assert.equal(high.length,1);const b=bounds(low),h=bounds(high);
 assert.ok(b.max.y-b.min.y>5,'lower roadway has an actual raised section');assert.ok(b.max.y<h.max.y-5,'stacked upper roadway remains independent');
 assert.ok(meshes(s,/twin_leg_haunched/).length);assert.ok(meshes(s,/four_longitudinal/).length);
});

test('historic station preserves a long north-south plan and only owns its historic structures',async()=>{
 const a=manifest.assets.find(a=>a.id==='bespoke-culture-station-seoul284');
 assert.ok(a.dimensions[2]>130&&a.dimensions[0]<35,'long axis is north-south, not the old short east-west scene');
 assert.deepEqual(new Set(a.footprintIds),new Set(['d8469ff5-7c6b-4514-8e0d-da239407bbda','36356163-6139-3732-A335-333337356337']));
 const s=await scene(a.id);assert.ok(meshes(s,/Copper_Dome/).length);assert.ok(meshes(s,/Arched_Entrance/).length);
});

test('Hyperion tower facts retain the documented conflicting height interpretation and podium owns no neighbour',()=>{
 for(const [letter,floors,height] of [['a',69,256],['b',59,216],['c',54,201.2]]){
  const a=manifest.assets.find(a=>a.id==='bespoke-hyperion-'+letter);assert.equal(a.sourceRecord.buildingFacts.floors,floors);assert.ok(Math.abs(a.dimensions[1]-height)<.01);assert.equal(a.footprintIds.length,1);
 }
 assert.deepEqual(manifest.assets.find(a=>a.id==='bespoke-hyperion-parking-podium').footprintIds,[]);
 assert.match(evidence.sites.hyperion.review.limits,/239.3/);
});

test('Hyperion department store owns its low source footprint instead of the erroneous 210m survey tower',async()=>{
 const a=manifest.assets.find(a=>a.id==='bespoke-hyperion-department-store');
 assert.deepEqual(a.footprintIds,['c7f66902-54ea-4bac-ae09-73a57bdf98b7']);
 assert.ok(a.supersedes.includes('survey-upis-32702773'));
 assert.ok(a.dimensions[1]>30&&a.dimensions[1]<40);
 const s=await scene(a.id);assert.ok(meshes(s,/arch|pediment/i).length);
});

test('Maple ClubCloud replacement keeps separate tower anchors and a single connecting bridge',async()=>{
 const a=manifest.assets.find(a=>a.id==='bespoke-maple-xi-210'),b=manifest.assets.find(a=>a.id==='bespoke-maple-xi-211');
 for(const x of [a,b]){
  const old=legacy.find(v=>v.id===x.id.replace('bespoke-',''));
  assert.deepEqual(x.coordinate,old.coordinate);assert.deepEqual(x.supersedes,[old.id]);
 }
 assert.ok(meshes(await scene(a.id),/skybridge_continuous_glazing/).length);
 assert.equal(meshes(await scene(b.id),/skybridge/).length,0);
 assert.ok(meshes(await scene(b.id),/e4_source_mapped_window_sizes/).length);
});
