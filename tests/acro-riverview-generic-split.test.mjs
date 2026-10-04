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
const audit=json('docs/model-audit/acro-riverview-generic-split.json');
const bindingDocument=json('docs/model-audit/acro-riverview-fallback-bindings.json');
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
for (const [sourceId, sha256, count] of [
 ['apt-a10026227','d42448c000366195e432e731b7b50edc71e17a40cb769e8b01009aa3ea218d8f',5],
 ['apt-a13790723','3b9248d428e4445801616d4527281d1392df1bd080a39b467a7b1a63edfb7bad',2],
]) test(`Riverview ${sourceId} partitions preserve original per-source triangle emissions`,()=>{
 const source=base.assets.find(a=>a.id===sourceId),proof=audit.sources.find(p=>p.sourceId===sourceId);
 const correction=corrections.corrections.find(c=>c.sourceId===sourceId);
 assert.equal(source.sha256,sha256);assert.equal(proof.sourceAuthoringReplay.byteExact,true);
 assert.equal(proof.sourceAuthoringReplay.sha256,sha256);
 const ordered=new Map();triangles(source,({material,index,signature})=>{if(!ordered.has(material))ordered.set(material,[]);assert.equal(ordered.get(material).length,index);ordered.get(material).push(signature)});
 const ranges=proof.sourceAuthoringReplay.triangleRangesBySource;assert.equal(ranges.length,count);
 const bySource=new Map(ranges.map(r=>[r.sourceId,[]]));
 for(const[material,signatures]of ordered){
  const coverage=new Uint8Array(signatures.length);
  for(const row of ranges){const[start,end]=row.triangleRangesByMaterial[material];assert.ok(Number.isInteger(start)&&start>=0&&start<=end&&end<=signatures.length);bySource.get(row.sourceId).push(...signatures.slice(start,end));for(let i=start;i<end;i++)coverage[i]++}
  assert.ok(coverage.every(n=>n===1));
 }
 for(const part of correction.assets){
  assert.deepEqual(triangles(part),part.footprintIds.flatMap(fid=>bySource.get(fid)).sort(),part.id);
  for(const key of ['coordinate','yawDegFromEast','heightDatum','modelingEstimates'])assert.deepEqual(part[key],source[key]);
  assert.equal(part.apartmentCode,undefined);assert.equal(part.householdCount,undefined);assert.equal(part.residentialCompletionCredit,false);
 }
 assert.equal(correction.assets.reduce((n,a)=>n+a.triangles,0),source.triangles);
 assert.equal(proof.crossGroupComponents,0);assert.equal(proof.trianglesAssignedWithinUniqueSourceConvexHull,0);
});
test('Riverview five independent bindings preserve two neighboring buildings and correct misleading archive identity',()=>{
 const identity=json('docs/model-audit/acro-riverview-source-identity.json');
 assert.equal(identity.towers.reduce((n,t)=>n+Number(t.register.households),0),595);
 assert.deepEqual(bindingDocument.bindings.map(b=>b.number),[101,102,103,104,105]);
 for(const b of bindingDocument.bindings){
  const original=identity.towers.find(t=>t.number===b.number),asset=effective.assets.find(a=>a.id===b.fallbackAssetId);
  assert.equal(b.sourceFootprintId,original.sourceId);assert.deepEqual(asset.footprintIds,[original.sourceId]);assert.equal(asset.sha256,b.fallbackSha256);
  assert.deepEqual(b.supersedes,[asset.id]);assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(original.sourceId)).length,1);
 }
 const residual=effective.assets.find(a=>a.id==='apt-a10026227');
 assert.deepEqual(new Set(residual.footprintIds),new Set(['77c66b26-e411-42e1-bac0-339e92925576','28668f28-4296-4b97-898b-b61b7cadf0eb']));
 assert.equal(residual.nameKo,'아크로리버뷰 인접 기존112·113동 (기존 추정 모형)');
 assert.equal(effective.assets.some(a=>a.id==='apt-a13790723'),false);
 assert.equal(base.assets.find(a=>a.id==='apt-a13790723').nameKo,'신반포5차');
 for(const id of residual.footprintIds)assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(id)).length,1);
 assert.equal(audit.sourceTriangles,4004);
});
test('Riverview leaves all thirteen pre-existing correction records and files unchanged',()=>{
 const ids=audit.preservedPriorCorrectionIds;assert.equal(ids.length,13);
 const prior=corrections.corrections.filter(c=>ids.includes(c.sourceId));assert.deepEqual(prior.map(c=>c.sourceId),ids);
 const sort=v=>Array.isArray(v)?v.map(sort):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])])):v;
 assert.equal(hash(JSON.stringify(sort(prior))),'8769b8da87ae2d63c8198176c6f2079480214a9f8dfd1c904e2ab0c4d8095e1e');
 for(const c of prior)for(const a of c.assets)assert.equal(hash(read('public/models/'+a.model)),a.sha256);
});
