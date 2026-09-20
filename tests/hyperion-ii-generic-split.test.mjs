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
const source=base.assets.find(a=>a.id==='apt-a15805111');
const correction=corrections.corrections.find(c=>c.sourceId===source.id);
const proof=json('docs/model-audit/hyperion-ii-generic-split.json');
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
test('Hyperion II partition preserves every original triangle and attribute exactly once',()=>{
 assert.ok(correction);assert.equal(correction.sourceSha256,source.sha256);
 assert.deepEqual(triangles(source),correction.assets.flatMap(triangles).sort());
 assert.deepEqual(correction.assets.map(a=>a.triangles),[2806,1771]);
 assert.equal(proof.crossGroupComponents,0);assert.equal(proof.vertexConnectedComponents,1831);
 assert.ok(proof.maximumVertexDistanceOutsideSourceFootprintM<.15);
 for(const a of correction.assets){assert.deepEqual(a.coordinate,source.coordinate);assert.equal(a.yawDegFromEast,source.yawDegFromEast);}
});
test('Hyperion II apartments own four towers and preserve both non-apartment officetels',()=>{
 const apartments=effective.assets.find(a=>a.id===source.id),offices=effective.assets.find(a=>a.id==='fallback-hyperion-ii-officetels');
 const ids=['e75bec98-4829-45f0-ac3e-a2b73a4d8999','13e9a720-1daf-4c3d-89a0-5d3d53b70139'];
 assert.deepEqual(offices.footprintIds,ids);assert.equal(offices.buildingCount,2);
 assert.equal(offices.householdCount,undefined);assert.equal(offices.apartmentCode,undefined);
 assert.equal(offices.category,'officetel');assert.equal(offices.residentialCompletionCredit,false);
 assert.equal(apartments.buildingCount,4);assert.equal(apartments.householdCount,576);
 for(const id of ids)assert.ok(!apartments.footprintIds.includes(id));
 assert.deepEqual(new Set([...apartments.footprintIds,...offices.footprintIds]),new Set(matches[source.id]));
 assert.equal(matches[source.id].length,6);assert.equal(source.model,'apt-a15805111.glb');
 const deployment=json('public/data/deployment-assets.json').files;
 for(const a of correction.assets)assert.equal(deployment['public/models/'+a.model],a.sha256);
});
