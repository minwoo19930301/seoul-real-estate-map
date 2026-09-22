import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { applyGenericCorrections } from '../src/generic-corrections.ts';
const read=p=>fs.readFileSync(new URL('../'+p,import.meta.url));
const json=p=>JSON.parse(read(p));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const base=json('public/models/manifest.json'),matches=json('public/models/footprint-matches.json');
const corrections=json('public/models/generic-corrections.json');
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
for (const batch of [
 {name:'godeok-laclassy', bindings:52, residuals:65, prior:27, triangles:93135},
 {name:'godeok-central-hillstate', bindings:46, residuals:4, prior:33, triangles:32489},
 {name:'geumho-oksu-dmc', bindings:37, residuals:6, prior:35, triangles:33787},
 {name:'seocho-gaepo-blesstige-honor', bindings:78, residuals:17, prior:38, triangles:61407},
 {name:'dmc-extension', bindings:33, residuals:25, prior:42, triangles:18080},
 {name:'mapo-two', bindings:49, residuals:8, prior:46, triangles:61489},
 {name:'dmc-completion', bindings:22, residuals:47, prior:48, triangles:24214},
]) {
const audit=json(`docs/model-audit/${batch.name}-generic-split.json`);
const frozen=json(`docs/model-audit/${batch.name}-fallback-inputs.json`);
for (const input of frozen.compounds) test(`${input.assetId} source-emission partition conserves every archived attribute and owner`,()=>{
 const source=[...base.assets,...corrections.corrections.flatMap(c=>c.assets)].find(a=>a.id===input.assetId&&a.sha256===input.sha256),proof=audit.sources.find(p=>p.sourceId===input.assetId);
 const correction=corrections.corrections.find(c=>c.sourceId===input.assetId&&c.sourceSha256===input.sha256);
 assert.equal(source.sha256,input.sha256);assert.equal(proof.sourceAuthoringReplay.byteExact,true);
 assert.equal(proof.sourceAuthoringReplay.sha256,input.sha256);
 const ordered=new Map();triangles(source,({material,index,signature})=>{if(!ordered.has(material))ordered.set(material,[]);assert.equal(ordered.get(material).length,index);ordered.get(material).push(signature)});
 const ranges=proof.sourceAuthoringReplay.triangleRangesBySource;
 assert.deepEqual(new Set(ranges.map(r=>r.sourceId)),new Set(input.footprintIds));
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
 assert.match(proof.ownershipMethod,/byte-exact|byte.exact|Byte-exact/);
});
test(`${batch.name} bindings retain ${batch.bindings} buildings and ${batch.residuals} unmatched neighbors`,()=>{
 let count=0;const allSelected=new Set();
 for(const item of frozen.identities){
  assert.equal(hash(read(item.path)),item.sha256);
  const identity=json(item.path),bindings=json(`docs/model-audit/${item.site}-fallback-bindings.json`).bindings;
  assert.equal(bindings.length,item.count);
  for(const b of bindings){
   const row=identity.towers.find(t=>t.number===b.number),asset=effective.assets.find(a=>a.id===b.fallbackAssetId);
   assert.equal(b.sourceFootprintId,row.sourceId);assert.deepEqual(asset.footprintIds,[row.sourceId]);assert.equal(asset.sha256,b.fallbackSha256);
   assert.deepEqual(b.supersedes,[asset.id]);assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(row.sourceId)).length,1);
   assert.equal(allSelected.has(row.sourceId),false);allSelected.add(row.sourceId);count++;
  }
 }
 assert.equal(count,batch.bindings);assert.equal(audit.preservedResidualSourceIds.length,batch.residuals);
 for(const fid of audit.preservedResidualSourceIds){assert.equal(allSelected.has(fid),false);assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(fid)).length,1);}
 assert.equal(audit.sourceTriangles,batch.triangles);
});
test(`${batch.name} retains all ${batch.prior} earlier corrections and their files`,()=>{
 const ids=audit.preservedPriorCorrectionIds;assert.equal(ids.length,batch.prior);
 const prior=corrections.corrections.slice(0,batch.prior);assert.deepEqual(prior.map(c=>c.sourceId),ids);
 // Preserve the publisher's numeric JSON representation (Python0.0 must not become JS0).
 const canonical=execFileSync('python3',['-c',"import sys,json,hashlib; a=json.load(open(sys.argv[1])); c=json.load(open('public/models/generic-corrections.json')); p=c['corrections'][:len(a['preservedPriorCorrectionIds'])]; print(hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())",`docs/model-audit/${batch.name}-generic-split.json`],{encoding:'utf8'}).trim();
 assert.equal(canonical,audit.preservedPriorCorrectionsCanonicalSha256);
 for(const c of prior)for(const a of c.assets)assert.equal(hash(read('public/models/'+a.model)),a.sha256);
});

}
