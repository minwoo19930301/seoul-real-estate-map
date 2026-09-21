import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { applyGenericCorrections } from '../src/generic-corrections.ts';
import { CityModels } from '../src/city-models.ts';
import { iterateModelAssets } from '../scripts/model_catalog_assets.mjs';
import { fileURLToPath } from 'node:url';
const read = p => fs.readFileSync(new URL('../'+p, import.meta.url));
const json = p => JSON.parse(read(p));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const base = json('public/models/manifest.json'), matches=json('public/models/footprint-matches.json');
const correction=json('public/models/generic-corrections.json');
const source=base.assets.find(a=>a.id==='apt-a14003002');
const effective=applyGenericCorrections(base.assets,matches,correction);
const parts=correction.corrections.find(c=>c.sourceId===source.id).assets;
const addedPartitions=correction.corrections.reduce((count,c)=>count+c.assets.length-1,0);
const fp='805bb192-2c3d-473f-b645-1eca99731876';
const proof=json('docs/model-audit/caelitus-generic-split.json');
function polygonDistance(point, polygon) {
  const ring=polygon.coordinates[0];let inside=false,distance=Infinity;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++) {
    const a=ring[j],b=ring[i],dx=b[0]-a[0],dy=b[1]-a[1];
    if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
    const t=Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
    distance=Math.min(distance,Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy));
  }
  return inside?0:distance;
}
function geometry(asset) {
  const bytes=read('public/models/'+asset.model),len=bytes.readUInt32LE(12),g=JSON.parse(bytes.subarray(20,20+len)),bin=bytes.subarray(28+len);
  assert.equal(hash(bytes),asset.sha256); assert.equal(bytes.length,asset.bytes);
  const width={SCALAR:1,VEC3:3,VEC4:4},size={5121:1,5123:2,5125:4,5126:4};
  function accessor(i) { const a=g.accessors[i],v=g.bufferViews[a.bufferView]; assert.equal(v.byteStride,undefined);return {a,start:(v.byteOffset??0)+(a.byteOffset??0),stride:width[a.type]*size[a.componentType]}; }
  const triangles=[],positions=[],ownershipCounts={};
  for(const p of g.meshes[0].primitives) {
    const idx=accessor(p.indices),n=g.accessors[p.indices].count;assert.equal(n%3,0);
    for(let i=0;i<n;i+=3) {
      const vertices=[],trianglePositions=[];
      for(let k=0;k<3;k++) {
        const off=idx.start+(i+k)*idx.stride,id=idx.a.componentType===5123?bin.readUInt16LE(off):bin.readUInt32LE(off),attrs=[];
        for(const [key,index] of Object.entries(p.attributes)) {
          const a=accessor(index),b=bin.subarray(a.start+id*a.stride,a.start+(id+1)*a.stride);attrs.push(key+':'+b.toString('hex'));
          if(key==='POSITION'){const position=[0,4,8].map(o=>b.readFloatLE(o));positions.push(position);trianglePositions.push([position[0],position[2]]);}
          if(key==='NORMAL') { const norm=Math.hypot(...[0,4,8].map(o=>b.readFloatLE(o)));assert.ok(Number.isFinite(norm)&&Math.abs(norm-1)<1e-5); }
        }
        vertices.push(attrs.sort().join('|'));
      }
      const owners=proof.sourceFootprints.filter(source=>trianglePositions.every(p=>polygonDistance(p,source.localFootprint)<.05));
      assert.equal(owners.length,1,'triangle must lie on exactly one retained source footprint');
      assert.ok(asset.footprintIds.includes(owners[0].id));
      ownershipCounts[owners[0].id]=(ownershipCounts[owners[0].id]??0)+1;
      triangles.push(JSON.stringify(g.materials[p.material])+':'+vertices.join('/'));
    }
  }
  assert.equal(triangles.length,asset.triangles);
  for(let axis=0;axis<3;axis++) {
    const min=positions.reduce((m,p)=>Math.min(m,p[axis]),Infinity),max=positions.reduce((m,p)=>Math.max(m,p[axis]),-Infinity);
    assert.equal(min,asset.bounds.min[axis]);assert.equal(max,asset.bounds.max[axis]);assert.ok(Math.abs(max-min-asset.dimensions[axis])<1e-5);
  }
  for(const [id,count] of Object.entries(ownershipCounts))assert.equal(count,proof.triangleCountsByFootprint[id]);
  return triangles;
}
test('partition preserves every original triangle, material and attribute exactly once without changing world anchor',()=>{
  const original=geometry(source),split=parts.flatMap(geometry);
  assert.deepEqual(split.sort(),original.sort());
  assert.equal(original.length,1996);assert.deepEqual(parts.map(a=>a.triangles),[1520,476]);
  for(const a of parts) {assert.deepEqual(a.coordinate,source.coordinate);assert.equal(a.yawDegFromEast,source.yawDegFromEast);assert.equal(a.bounds.min[1],0);}
  assert.equal(proof.crossBuildingComponents,0);assert.equal(proof.vertexConnectedComponents,942);
  assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM<.05);
});
test('effective catalog replaces only the bad compound and exactly partitions its seven footprint owners',()=>{
  assert.equal(effective.assets.length,base.assets.length+addedPartitions);
  const correctedIds=new Set(correction.corrections.map(c=>c.sourceId));
  for(const a of base.assets.filter(a=>!correctedIds.has(a.id))) assert.equal(effective.assets.find(b=>b.id===a.id),a);
  assert.deepEqual(effective.matches['fallback-caelitus-101'],[fp]);
  assert.equal(effective.matches[source.id].length,6);assert.ok(!effective.matches[source.id].includes(fp));
  assert.equal(matches[source.id].length,7);assert.equal(source.model,'apt-a14003002.glb');
  const claimed=Object.entries(effective.matches).filter(([,ids])=>ids.includes(fp));assert.deepEqual(claimed.map(([id])=>id),['fallback-caelitus-101']);
  const deployment=json('public/data/deployment-assets.json');
  for(const path of ['public/models/generic-corrections.json',...parts.map(a=>'public/models/'+a.model)])assert.equal(deployment.files[path],hash(read(path)));
});
test('invalid source hashes, overlap, omitted neighbors, unsafe paths and reference takeover are rejected without mutations',()=>{
  const before=JSON.stringify({base,matches});
  for(const corrupt of [d=>d.corrections.find(c=>c.sourceId===source.id).sourceSha256='0'.repeat(64),d=>d.corrections.find(c=>c.sourceId===source.id).assets[0].footprintIds.push(fp),d=>d.corrections.find(c=>c.sourceId===source.id).assets[0].footprintIds.pop(),d=>d.corrections.find(c=>c.sourceId===source.id).assets[1].model='../bad.glb',d=>d.corrections.find(c=>c.sourceId===source.id).assets[1].quality='reference']) {
    const d=structuredClone(correction);corrupt(d);assert.throws(()=>applyGenericCorrections(base.assets,matches,d));
  }
  assert.equal(JSON.stringify({base,matches}),before);
});
function completePartition() {
  const document={version:1,corrections:[structuredClone(correction.corrections.find(c=>c.sourceId===source.id))]};
  const residual=document.corrections[0].assets.find(a=>a.id===source.id);
  residual.id='fallback-caelitus-retained-neighbors';
  residual.model='generic-corrections/fallback-caelitus-retained-neighbors.glb';
  return document;
}
test('complete valid partition removes the original effective asset and ownership only after exact coverage',()=>{
  const document=completePartition(),before=structuredClone({base,matches,document});
  const result=applyGenericCorrections(base.assets,matches,document);
  assert.equal(result.assets.some(a=>a.id===source.id),false);
  assert.equal(Object.hasOwn(result.matches,source.id),false);
  assert.equal(result.assets.length,base.assets.length+document.corrections[0].assets.length-1);
  for(const part of document.corrections[0].assets){
    assert.equal(result.assets.find(a=>a.id===part.id),part);
    assert.deepEqual(result.matches[part.id],part.footprintIds);
  }
  for(const id of matches[source.id])assert.equal(Object.values(result.matches).filter(ids=>ids.includes(id)).length,1);
  assert.deepEqual({base,matches,document},before,'Archived catalog, matches and correction inputs remain untouched');
});
test('complete partition with missing or duplicate ownership fails closed without removing source inputs',()=>{
  for(const corrupt of [
    c=>c.assets[0].footprintIds.pop(),
    c=>c.assets[0].footprintIds.push(c.assets[1].footprintIds[0]),
    c=>c.assets[0].footprintIds.splice(0,1,c.assets[1].footprintIds[0]),
    c=>c.assets[1].id=c.assets[0].id,
  ]){
    const document=completePartition();corrupt(document.corrections[0]);
    const before=structuredClone({base,matches,document});
    assert.throws(()=>applyGenericCorrections(base.assets,matches,document),/exactly partition original ownership/);
    assert.deepEqual({base,matches,document},before);
    assert.equal(base.assets.find(a=>a.id===source.id),source);
    assert.equal(matches[source.id].length,7);
  }
});
const frame={defaultProjectionData:{mainMatrix:new THREE.Matrix4().elements},shaderData:{variantName:'mercator'}};
function harness(state,neighborFailed=false) {
  const replacement={...parts[1],id:'bespoke-raemian-caelitus-101',quality:'reference',supersedes:['fallback-caelitus-101']};
  const assets=[...parts,replacement],entries=assets.map(asset=>({asset,scene:new THREE.Scene(),error:null,ground:null,draws:0,active:false}));
  const upgrade=entries[2];
  if(state==='pending'){upgrade.scene=undefined;upgrade.pending=Promise.resolve();}
  if(state==='404'){upgrade.scene=undefined;upgrade.error='HTTP 404';}
  if(state==='culled')upgrade.scene.userData.calls=0;
  if(neighborFailed){entries[0].scene=undefined;entries[0].error='HTTP 404';}
  const map={getZoom:()=>18,getCenter:()=>({lng:source.coordinate.lon,lat:source.coordinate.lat}),getBounds:()=>({getWest:()=>126.97,getEast:()=>126.99,getSouth:()=>37.50,getNorth:()=>37.53}),getTerrain:()=>({}),getSource:()=>({}),isSourceLoaded:()=>true,queryTerrainElevation:()=>40,triggerRepaint(){},off(){},getLayer:()=>null};
  const models=new CityModels(map);models.entries=entries;models.is25d=true;
  models.renderer={info:{render:{calls:0}},resetState(){},dispose(){},render(scene){this.info.render.calls=scene.userData.calls??1;}};
  models.setFootprintMatches(effective.matches);models.render(frame);return {models,entries};
}
test('ready, pending, 404 and culled bespoke101 never suppress the six-neighbor GLB or double-draw101',()=>{
  for(const state of ['ready','pending','404','culled']) {
    const h=harness(state);assert.equal(h.entries[0].active,true,state);
    assert.equal(h.entries[1].active,state!=='ready',state);assert.equal(h.entries[2].active,state==='ready',state);
    assert.deepEqual(new Set(h.models.getState().activeFootprintIds),new Set(matches[source.id]),state);h.models.destroy();
  }
});
test('failed six-neighbor GLB restores those source solids while101 stays independently visible',()=>{
  const h=harness('ready',true);assert.equal(h.entries[0].active,false);assert.equal(h.entries[2].active,true);
  assert.deepEqual(h.models.getState().activeFootprintIds,[fp]);h.models.destroy();
});

test('off-center split101 remains eligible when its footprint is visible but preserved terrain anchor is outside the view',()=>{
  const h=harness('404'),a=parts[1],b=a.geoBounds;
  assert.ok(source.coordinate.lon<b[0]);
  const view={zoom:20,lon:(b[0]+b[2])/2,lat:(b[1]+b[3])/2,west:b[0],south:b[1],east:b[2],north:b[3]};
  assert.equal(h.models.inView(a,view),true);h.models.destroy();
});

test('effective legacy plus lazy catalog retains all113123 sources and adds the split records with unique ownership',async()=>{
  let count=0,found=0;
  for await(const {asset,footprintIds} of iterateModelAssets(fileURLToPath(new URL('../public/models',import.meta.url)),{...base,assets:effective.assets},effective.matches)) {
    count++;
    if(asset.id==='fallback-caelitus-101'){found++;assert.deepEqual(footprintIds,[fp]);}
  }
  assert.equal(count,113123+addedPartitions);assert.equal(found,1);
});
