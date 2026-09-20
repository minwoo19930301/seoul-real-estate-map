import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { applyGenericCorrections } from '../src/generic-corrections.ts';
const read=p=>fs.readFileSync(new URL('../'+p,import.meta.url));
const json=p=>JSON.parse(read(p));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const base=json('public/models/manifest.json'),matches=json('public/models/footprint-matches.json');
const corrections=json('public/models/generic-corrections.json');
const effective=applyGenericCorrections(base.assets,matches,corrections);
function triangles(asset) {
 const bytes=read('public/models/'+asset.model),length=bytes.readUInt32LE(12);
 assert.equal(hash(bytes),asset.sha256);assert.equal(bytes.length,asset.bytes);
 const g=JSON.parse(bytes.subarray(20,20+length)),binary=bytes.subarray(28+length);
 assert.equal(g.nodes.length,1);assert.deepEqual(Object.keys(g.nodes[0]).sort(),['mesh','name']);
 const widths={SCALAR:1,VEC3:3,VEC4:4},sizes={5121:1,5123:2,5125:4,5126:4};
 const accessor=i=>{const a=g.accessors[i],v=g.bufferViews[a.bufferView];assert.equal(v.byteStride,undefined);return{...a,offset:(v.byteOffset??0)+(a.byteOffset??0),stride:widths[a.type]*sizes[a.componentType]};};
 const out=[],bounds=[[Infinity,Infinity,Infinity],[-Infinity,-Infinity,-Infinity]];
 for(const p of g.meshes[0].primitives){
  const indices=accessor(p.indices);assert.equal(indices.count%3,0);
  for(let i=0;i<indices.count;i+=3){const vertices=[];
   for(let k=0;k<3;k++){
    const offset=indices.offset+(i+k)*indices.stride,id=indices.componentType===5123?binary.readUInt16LE(offset):binary.readUInt32LE(offset),attributes=[];
    for(const [name,index]of Object.entries(p.attributes)){
     const a=accessor(index),b=binary.subarray(a.offset+id*a.stride,a.offset+(id+1)*a.stride);attributes.push(name+':'+b.toString('hex'));
     if(name==='POSITION')for(let axis=0;axis<3;axis++){const n=b.readFloatLE(axis*4);assert.ok(Number.isFinite(n));bounds[0][axis]=Math.min(bounds[0][axis],n);bounds[1][axis]=Math.max(bounds[1][axis],n);}
    }vertices.push(attributes.sort().join('|'));
   }out.push(JSON.stringify(g.materials[p.material])+':'+vertices.join('/'));
  }
 }
 assert.equal(out.length,asset.triangles);assert.deepEqual(bounds,[asset.bounds.min,asset.bounds.max]);return out.sort();
}

for(const site of [
 {key:'onebailey',id:'apt-a10023043',count:19,parts:[14,1,1,1,1,1],triangles:[15922,897,769,496,969,786],components:6321,convex:619,outsideMax:9.53},
 {key:'onepentas',id:'apt-a10022556',count:7,parts:[4,1,1,1],triangles:[2953,685,592,580],components:1620,convex:24,outsideMax:2.04},
]){
 const source=base.assets.find(a=>a.id===site.id);
 const correction=corrections.corrections.find(c=>c.sourceId===source.id);
 const proof=json(`docs/model-audit/${site.key}-generic-split.json`);
 test(`${site.key} retains all source triangles, attributes, materials and anchor exactly once`,()=>{
  assert.ok(correction);assert.equal(correction.sourceSha256,source.sha256);
  assert.deepEqual(triangles(source),correction.assets.flatMap(triangles).sort());
  assert.deepEqual(correction.assets.map(a=>a.triangles),site.triangles);
  assert.equal(proof.crossGroupComponents,0);assert.equal(proof.vertexConnectedComponents,site.components);
  assert.equal(proof.trianglesAssignedWithinUniqueSourceConvexHull,site.convex);
  assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM>.15);
  assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM<site.outsideMax);
  assert.match(proof.ownershipMethod,/uniquely covering union/);
  for(const a of correction.assets){assert.deepEqual(a.coordinate,source.coordinate);assert.equal(a.yawDegFromEast,source.yawDegFromEast);}
 });
 test(`${site.key} independently replaceable parts retain the whole source footprint partition`,()=>{
  assert.equal(matches[source.id].length,site.count);
  assert.deepEqual(correction.assets.map(a=>a.footprintIds.length),site.parts);
  const partition=correction.assets.flatMap(a=>a.footprintIds);
  assert.equal(new Set(partition).size,partition.length);
  assert.deepEqual(new Set(partition),new Set(matches[source.id]));
  assert.deepEqual(new Set(proof.sourceFootprints.map(f=>f.id)),new Set(partition));
  const deployment=json('public/data/deployment-assets.json').files;
  for(const a of correction.assets){
   assert.equal(a.householdCount,undefined,'A split mesh is not the whole household total');
   assert.equal(a.residentialCompletionCredit,false);
   assert.deepEqual(effective.assets.find(e=>e.id===a.id),a);
   assert.deepEqual(proof.groupFootprints[a.id],a.footprintIds);
   assert.equal(deployment['public/models/'+a.model],a.sha256);
  }
 });
}
test('One Pentas excludes Prestige 126 without deleting that neighboring tower',()=>{
 const neighbor=effective.assets.find(a=>a.id==='fallback-prestige-126');
 assert.equal(neighbor.apartmentCode,undefined);
 assert.equal(neighbor.buildingCount,1);
 assert.deepEqual(neighbor.footprintIds,['b21842a2-9832-4a21-bcc5-1c571f309556']);
 for(const a of corrections.corrections.find(c=>c.sourceId==='apt-a10022556').assets.filter(a=>a.id!==neighbor.id)){
  assert.ok(!a.footprintIds.includes(neighbor.footprintIds[0]));
 }
});
