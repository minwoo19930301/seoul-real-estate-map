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
const source=base.assets.find(a=>a.id==='apt-a10026207');
const correction=corrections.corrections.find(c=>c.sourceId===source.id);
const proof=json('docs/model-audit/seoulforest-riverview-xi-generic-split.json');
const bindings=json('docs/model-audit/seoulforest-riverview-xi-fallback-bindings.json').bindings;
const effective=applyGenericCorrections(base.assets,matches,corrections);
function triangles(asset, onTriangle) {
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
   }const signature=JSON.stringify(g.materials[p.material])+':'+vertices.join('/'); onTriangle?.({material:p.material,index:i/3,signature});out.push(signature);
  }
 }
 assert.equal(out.length,asset.triangles);assert.deepEqual(bounds,[asset.bounds.min,asset.bounds.max]);return out.sort();
}
test('Seoul Forest Riverview Xi seven partitions conserve all 8017 original triangle emissions exactly once',()=>{
 assert.equal(source.sha256,'2a69f3a385c791e290f0fce9a7b093aefb8015e3b8240d3c080dd0b5f422ab63');
 assert.equal(proof.sourceAuthoringReplay.byteExact,true);
 assert.equal(proof.sourceAuthoringReplay.sha256,source.sha256);
 const ordered=new Map();
 triangles(source,({material,index,signature})=>{
  if(!ordered.has(material))ordered.set(material,[]);
  assert.equal(ordered.get(material).length,index);ordered.get(material).push(signature);
 });
 const ranges=proof.sourceAuthoringReplay.triangleRangesBySource;
 assert.equal(ranges.length,7);
 const bySource=new Map(ranges.map(r=>[r.sourceId,[]]));
 for(const [material,signatures]of ordered){
  const coverage=new Uint8Array(signatures.length);
  for(const row of ranges){
   const [start,end]=row.triangleRangesByMaterial[material];
   assert.ok(Number.isInteger(start)&&start>=0&&start<=end&&end<=signatures.length);
   bySource.get(row.sourceId).push(...signatures.slice(start,end));
   for(let i=start;i<end;i++)coverage[i]++;
  }
  assert.ok(coverage.every(n=>n===1));
 }
 assert.equal(correction.assets.length,7);
 assert.equal(correction.assets.reduce((n,a)=>n+a.triangles,0),8017);
 for(const part of correction.assets){
  assert.equal(part.footprintIds.length,1);
  assert.deepEqual(triangles(part),bySource.get(part.footprintIds[0]).sort(),part.id);
  for(const key of ['coordinate','yawDegFromEast','heightDatum','modelingEstimates']) assert.deepEqual(part[key],source[key]);
  assert.equal(part.apartmentCode,undefined);assert.equal(part.householdCount,undefined);
  assert.equal(part.residentialCompletionCredit,false);
 }
 assert.equal(proof.crossGroupComponents,0);
 assert.equal(proof.trianglesAssignedWithinUniqueSourceConvexHull,10);
 assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM>1.496&&proof.maximumVertexDistanceOutsideSourceFootprintM<1.498,'Inherited roofplant approximation is documented and retained');
});
test('Seoul Forest Riverview Xi bindings retain seven independent source owners without a hidden compound',()=>{
 const identity=json('docs/model-audit/seoulforest-riverview-xi-source-identity.json');
 assert.deepEqual(bindings.map(b=>b.number),[101,102,103,104,105,106,107]);
 assert.equal(new Set(bindings.map(b=>b.sourceFootprintId)).size,7);
 assert.equal(identity.towers.reduce((sum,t)=>sum+Number(t.register.households),0),1034);
 assert.equal(effective.assets.some(a=>a.id===source.id),false);
 for(const b of bindings){
  const original=identity.towers.find(t=>t.number===b.number);
  assert.equal(b.sourceFootprintId,original.sourceId);
  assert.equal(b.fallbackAssetId,`fallback-seoulforest-riverview-xi-${b.number}`);
  const part=effective.assets.find(a=>a.id===b.fallbackAssetId);assert.ok(part);
  assert.deepEqual(part.footprintIds,[b.sourceFootprintId]);assert.deepEqual(b.supersedes,[part.id]);
  assert.equal(b.fallbackSha256,part.sha256);assert.equal(b.fallbackModel,part.model);
  assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(b.sourceFootprintId)).length,1);
 }
 assert.deepEqual(new Set(correction.assets.flatMap(a=>a.footprintIds)),new Set(matches[source.id]));
});
test('Seoul Forest Riverview Xi split preserves all sixteen pre-existing correction records and their files',()=>{
 const ids=proof.preservedPriorCorrectionIds;
 assert.equal(ids.length,16);
 const prior=corrections.corrections.filter(c=>ids.includes(c.sourceId));
 assert.deepEqual(prior.map(c=>c.sourceId),ids);
 const sort=value=>Array.isArray(value)?value.map(sort):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,sort(value[k])])):value;
 assert.equal(hash(JSON.stringify(sort(prior))),'545505596fd2539ae24a8caec559a27a8ef67220168609fde4602e3a54e8b143');
 for(const c of prior)for(const a of c.assets)assert.equal(hash(read('public/models/'+a.model)),a.sha256);
});
