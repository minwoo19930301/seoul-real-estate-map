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
const source=base.assets.find(a=>a.id==='apt-a13704104');
const correction=corrections.corrections.find(c=>c.sourceId===source.id);
const proof=json('docs/model-audit/banpo-xi-generic-split.json');
const bindingDocument=json('docs/model-audit/banpo-xi-fallback-bindings.json');
const bindings=bindingDocument.bindings;
const effective=applyGenericCorrections(base.assets,matches,corrections);
const priorIds=['apt-a14003002','apt-a15088614','apt-a15805111','apt-a10022556','apt-a10023043','apt-a13780006','apt-a10027205','apt-a13776509','apt-a13776508','apt-a13780001'];
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
test('all 22,551 archived triangles retain exact indexed source emissions, attributes, materials and multiplicity',()=>{
 assert.equal(source.sha256,'e4066ceee7746e353fe7f88ef794a892ee541cef1dad9bc583c4bb32a50b5e6a');
 assert.equal(proof.sourceAuthoringReplay.byteExact,true);
 assert.equal(proof.sourceAuthoringReplay.sha256,source.sha256);
 const ranges=proof.sourceAuthoringReplay.triangleRangesBySource;
 assert.equal(hash(JSON.stringify(ranges)),'f37aca9acce3800079d27d0d094f41fb24c5e8ac469c26fd5a0cdda212c07b41');
 assert.equal(ranges.length,45);
 const ordered=new Map();
 triangles(source,({material,index,signature})=>{
  if(!ordered.has(material))ordered.set(material,[]);
  assert.equal(ordered.get(material).length,index);ordered.get(material).push(signature);
 });
 const bySource=new Map(ranges.map(r=>[r.sourceId,[]]));
 for(const [material,signatures]of ordered){
  const coverage=new Uint8Array(signatures.length);
  for(const row of ranges){
   const [start,end]=row.triangleRangesByMaterial[material];
   assert.ok(Number.isInteger(start)&&start>=0&&start<=end&&end<=signatures.length);
   bySource.get(row.sourceId).push(...signatures.slice(start,end));
   for(let i=start;i<end;i++)coverage[i]++;
  }
  assert.ok(coverage.every(n=>n===1),'Indexed multiplicity is preserved even when positions coincide');
 }
 assert.equal(correction.assets.length,30);
 assert.equal(correction.assets.reduce((n,a)=>n+a.triangles,0),22551);
 for(const part of correction.assets){
  assert.deepEqual(triangles(part),part.footprintIds.flatMap(id=>bySource.get(id)).sort(),part.id);
  assert.deepEqual(part.coordinate,source.coordinate);assert.equal(part.yawDegFromEast,source.yawDegFromEast);
  assert.equal(part.heightDatum,source.heightDatum);assert.deepEqual(part.modelingEstimates,source.modelingEstimates);
  assert.equal(part.apartmentCode,undefined);assert.equal(part.householdCount,undefined);
  assert.equal(part.residentialCompletionCredit,false);
 }
});
test('shared boundaries retain proven authoring identities with zero source area overlap',()=>{
 assert.equal(proof.sharedBoundaryAmbiguityCount,2088);
 assert.equal(proof.sharedBoundaryAmbiguities.length,2088);
 assert.equal(proof.vertexConnectedComponents,6437);
 assert.equal(proof.crossGroupComponents,5,'Shared original vertices are retained, not deleted or reassigned');
 assert.equal(proof.trianglesAssignedWithinUniqueSourceConvexHull,86);
 assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM<.901);
 assert.match(proof.ownershipMethod,/no nearest-footprint attribution/);
 const indices=new Set(),sources=new Set();
 for(const entry of proof.sharedBoundaryAmbiguities){
  const key=`${entry.material}:${entry.triangleIndex}`;assert.ok(!indices.has(key));indices.add(key);
  const row=proof.sourceAuthoringReplay.triangleRangesBySource.find(r=>r.sourceId===entry.emissionSourceId);
  const [start,end]=row.triangleRangesByMaterial[entry.material];
  assert.ok(entry.triangleIndex>=start&&entry.triangleIndex<end,'Boundary ownership is an exact original emission');
  assert.equal(entry.positiveAreaOverlapM2,0);
  assert.ok(entry.otherSourceIds.length>0);
  assert.ok(entry.otherSourceIds.every(id=>id!==entry.emissionSourceId&&proof.sourceFootprints.some(f=>f.id===id)));
  for(const id of [entry.emissionSourceId,...entry.otherSourceIds]){
   sources.add(id);const distance=entry.maximumVertexDistanceToSourceBoundaryM[id];assert.ok(distance>=0&&distance<.049);
  }
 }
 assert.equal(sources.size,20);
});
test('44 unique numbered tower bindings replace only their own sources and preserve all 16 residual sources',()=>{
 assert.deepEqual(bindings.map(b=>b.number),Array.from({length:44},(_,i)=>i+101));
 assert.equal(hash(JSON.stringify(bindings.map(b=>[b.number,b.sourceFootprintId]))),'d487291c15bdbef0d8b5fd7a693903ad67e227251eb8c3db0f1f1f3f00592f3c');
 assert.equal(new Set(bindings.map(b=>b.fallbackAssetId)).size,44);
 assert.equal(new Set(bindings.map(b=>b.sourceFootprintId)).size,44);
 for(const b of bindings){
  const a=effective.assets.find(a=>a.id===b.fallbackAssetId);assert.ok(a);
  assert.deepEqual(a.footprintIds,[b.sourceFootprintId]);assert.deepEqual(effective.matches[a.id],a.footprintIds);
  assert.deepEqual(b.supersedes,[a.id]);assert.equal(b.fallbackModel,a.model);assert.equal(b.fallbackSha256,a.sha256);
  assert.equal(hash(read('public/models/'+a.model)),a.sha256);
  assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(b.sourceFootprintId)).length,1);
 }
 const residual=effective.assets.find(a=>a.id===source.id);
 const towerIds=new Set(bindings.map(b=>b.sourceFootprintId));
 const expected=matches[source.id].filter(id=>!towerIds.has(id));
 assert.equal(expected.length,16);assert.deepEqual(residual.footprintIds,expected);
 assert.deepEqual(bindingDocument.residual.sourceFootprintIds,expected);
 assert.equal(residual.triangles,2956);assert.equal(residual.buildingCount,16);
 assert.equal(residual.apartmentCode,undefined);assert.equal(residual.householdCount,undefined);
 assert.equal(residual.residentialCompletionCredit,false);
 const partition=correction.assets.flatMap(a=>a.footprintIds);
 assert.equal(new Set(partition).size,45);assert.deepEqual(new Set(partition),new Set(matches[source.id]));
 for(const id of expected)assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(id)).length,1);
});
test('14 residential singletons, including unresolved 103, preserve every field and GLB byte',()=>{
 const unchanged=bindings.filter(b=>b.fallbackAssetId.startsWith('residential-'));
 assert.equal(unchanged.length,14);
 for(const binding of unchanged){
  const original=base.assets.find(a=>a.id===binding.fallbackAssetId);
  assert.deepEqual(effective.assets.find(a=>a.id===original.id),original);
  assert.equal(hash(read('public/models/'+original.model)),original.sha256);
 }
 const tower103=bindings.find(b=>b.number===103);
 assert.equal(tower103.fallbackAssetId,'residential-4afb2bb8-e9bd-4692-b310-cec4d7ccc560');
 assert.equal(tower103.fallbackSha256,'7f310923774b387c42cb44d4a1284a8848cfe97b48bf899a4df47f144baff389');
 assert.ok(bindingDocument.limits.some(s=>s.includes('57.7m / 27F')));
});
test('116 changes only incorrect identity metadata while preserving rendering and source replay',()=>{
 const original=base.assets.find(a=>a.id==='apt-a10020044');
 const item=corrections.corrections.find(c=>c.sourceId===original.id),part=item.assets[0];
 assert.equal(item.kind,'metadata-only');assert.equal(item.assets.length,1);
 assert.equal(original.nameKo,'오티에르반포');assert.equal(part.nameKo,'반포자이 116동 (기존 추정 모형)');
 assert.equal(part.apartmentCode,undefined);assert.equal(part.householdCount,undefined);
 const changed=new Set(['name','nameKo','householdCount','apartmentCode','sourceIdentity']);
 const rendering=a=>Object.fromEntries(Object.entries(a).filter(([k])=>!changed.has(k)));
 assert.deepEqual(rendering(part),rendering(original));
 assert.equal(part.model,'apt-a10020044.glb');assert.equal(part.sha256,'1ff87eec0916a91fe001a5a0df80543916bcaf44fec41b2d28e4b36e0dcbea73');
 assert.equal(hash(read('public/models/'+part.model)),part.sha256);
 const identity=json('docs/model-audit/banpo-xi-116-identity.json');
 assert.equal(identity.sourceAuthoringReplay.byteExact,true);assert.equal(identity.sourceAuthoringReplay.sha256,part.sha256);
 assert.equal(identity.sourceAuthoringReplay.triangleRangesBySource.length,1);
 assert.equal(identity.sourceIdentity.geometryChanged,false);
});
test('all 10 historical correction records and GLBs remain exact, and catalog shards add no tower owner',()=>{
 const prior=corrections.corrections.filter(c=>priorIds.includes(c.sourceId));
 assert.deepEqual(prior.map(c=>c.sourceId),priorIds);
 assert.equal(hash(JSON.stringify(prior)),'5ba808b75e43fb417752c5126867fc9017acbfa80ed2bd492feb3d0929cb3a68');
 for(const c of prior)for(const a of c.assets)assert.equal(hash(read('public/models/'+a.model)),a.sha256);
 assert.deepEqual(corrections.corrections.map(c=>c.sourceId),[...priorIds,'apt-a13704104','apt-a10020044']);
 const audit=bindingDocument.catalogOwnershipAudit;
 assert.equal(audit.checkedTiles.length,3);assert.equal(audit.additionalOwners,0);
 assert.equal(hash(read('public/models/'+audit.catalogIndex)),audit.catalogIndexSha256);
 const towerIds=new Set(bindings.map(b=>b.sourceFootprintId));
 for(const tile of audit.checkedTiles){
  const bytes=read('public/models/'+tile.path);assert.equal(hash(bytes),tile.sha256);
  const assets=JSON.parse(bytes).assets;assert.equal(assets.length,tile.assetCount);
  assert.ok(assets.every(a=>(a.footprintIds??[]).every(fid=>!towerIds.has(fid))));
 }
});
