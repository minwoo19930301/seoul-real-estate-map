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
function polygonDistance(point,ring){
 let inside=false,distance=Infinity;
 for(let i=0,j=ring.length-1;i<ring.length;j=i++){
  const a=ring[j],b=ring[i],dx=b[0]-a[0],dy=b[1]-a[1];
  if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<dx*(point[1]-a[1])/dy+a[0])inside=!inside;
  const t=Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy||1)));
  distance=Math.min(distance,Math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy));
 }
 return inside?0:distance;
}
function convexHull(ring){
 const points=ring.slice(0,-1).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
 const half=points=>{const h=[];for(const p of points){while(h.length>1&&cross(h.at(-2),h.at(-1),p)<=0)h.pop();h.push(p);}return h.slice(0,-1);};
 return [...half(points),...half([...points].reverse())];
}
function triangles(asset,sourceFootprints,partitionAssets) {
 const footprints=sourceFootprints?.map(f=>{
  const geometry=f.localFootprint;
  assert.ok(['Polygon','MultiPolygon'].includes(geometry.type));
  const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
  const rings=polygons.map(p=>{assert.equal(p.length,1,'These archived source footprints have no holes');return p[0];});
  const points=rings.flatMap(r=>r.slice(0,-1));
  return{id:f.id,rings,hull:convexHull([...points,points[0]])};
 });
 const groups=partitionAssets?.map(part=>({id:part.id,footprints:footprints.filter(f=>part.footprintIds.includes(f.id))}));
 const bytes=read('public/models/'+asset.model),length=bytes.readUInt32LE(12);
 assert.equal(hash(bytes),asset.sha256);assert.equal(bytes.length,asset.bytes);
 const g=JSON.parse(bytes.subarray(20,20+length)),binary=bytes.subarray(28+length);
 assert.equal(g.nodes.length,1);assert.deepEqual(Object.keys(g.nodes[0]).sort(),['mesh','name']);
 const widths={SCALAR:1,VEC3:3,VEC4:4},sizes={5121:1,5123:2,5125:4,5126:4};
 const accessor=i=>{const a=g.accessors[i],v=g.bufferViews[a.bufferView];assert.equal(v.byteStride,undefined);return{...a,offset:(v.byteOffset??0)+(a.byteOffset??0),stride:widths[a.type]*sizes[a.componentType]};};
 const out=[],bounds=[[Infinity,Infinity,Infinity],[-Infinity,-Infinity,-Infinity]];
 for(const p of g.meshes[0].primitives){
  const indices=accessor(p.indices);assert.equal(indices.count%3,0);
  for(let i=0;i<indices.count;i+=3){const vertices=[],positions=[];
   for(let k=0;k<3;k++){
    const offset=indices.offset+(i+k)*indices.stride,id=indices.componentType===5123?binary.readUInt16LE(offset):binary.readUInt32LE(offset),attributes=[];
    for(const [name,index]of Object.entries(p.attributes)){
     const a=accessor(index),b=binary.subarray(a.offset+id*a.stride,a.offset+(id+1)*a.stride);attributes.push(name+':'+b.toString('hex'));
     if(name==='POSITION'){positions.push([b.readFloatLE(0),b.readFloatLE(8)]);for(let axis=0;axis<3;axis++){const n=b.readFloatLE(axis*4);assert.ok(Number.isFinite(n));bounds[0][axis]=Math.min(bounds[0][axis],n);bounds[1][axis]=Math.max(bounds[1][axis],n);}}
    }vertices.push(attributes.sort().join('|'));
   }
   if(groups){
    let owners=groups.filter(group=>positions.every(p=>group.footprints.some(f=>f.rings.some(r=>polygonDistance(p,r)<=.15))));
    if(!owners.length)owners=groups.filter(group=>positions.every(p=>group.footprints.some(f=>polygonDistance(p,f.hull)<=.15)));
    assert.equal(owners.length,1,`${asset.id}: each triangle must have one source partition owner`);
    assert.equal(owners[0].id,asset.id,`${asset.id}: geometry must remain with its declared source partition`);
   }
   out.push(JSON.stringify(g.materials[p.material])+':'+vertices.join('/'));
  }
 }
 assert.equal(out.length,asset.triangles);assert.deepEqual(bounds,[asset.bounds.min,asset.bounds.max]);return out.sort();
}

for(const site of [
 {key:'onebailey',id:'apt-a10023043',count:19,parts:Array(19).fill(1),triangles:[897,769,1423,1005,1059,1257,1369,1074,1257,596,1107,951,1323,1307,1005,1189,496,969,786],components:6321,convex:619,outsideMax:9.53},
 {key:'onebailey-113-116',id:'apt-a13780006',count:5,parts:Array(5).fill(1),triangles:[236,992,905,1028,1202],components:1332,convex:79,outsideMax:3.92},
 {key:'onepentas',id:'apt-a10022556',count:7,parts:[4,1,1,1],triangles:[2953,685,592,580],components:1620,convex:24,outsideMax:2.04},
 {key:'acro-riverpark',id:'apt-a10027205',count:17,parts:[15,1,1],triangles:[19314,1787,1052],components:6138,convex:362,outsideMax:4.63},
]){
 const source=base.assets.find(a=>a.id===site.id);
 const correction=corrections.corrections.find(c=>c.sourceId===source.id);
 const proof=json(`docs/model-audit/${site.key}-generic-split.json`);
 test(`${site.key} retains all source triangles, attributes, materials and anchor exactly once`,()=>{
  assert.ok(correction);assert.equal(correction.sourceSha256,source.sha256);
  assert.deepEqual(triangles(source),correction.assets.flatMap(a=>triangles(a,proof.sourceFootprints,correction.assets)).sort());
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
test('One Bailey primary archive yields only its 19 existing footprints, excluding 113–116',()=>{
 const source=base.assets.find(a=>a.id==='apt-a10023043');
 const correction=corrections.corrections.find(c=>c.sourceId===source.id);
 const expectedNumbers=[101,102,103,104,105,106,107,108,109,110,111,112,117,118,119,120,121,122,123];
 assert.deepEqual(correction.assets.map(a=>a.id),expectedNumbers.map(n=>`fallback-onebailey-${n}`));
 assert.equal(correction.assets.reduce((n,a)=>n+a.triangles,0),19839);
 assert.equal(effective.assets.some(a=>a.id===source.id),false);
 assert.equal(Object.hasOwn(effective.matches,source.id),false);
 assert.equal(source.model,'apt-a10023043.glb');
 assert.equal(source.sha256,'b50af817af714ec3027f9fa240a0a17d72fc896987180699ae47a50f9fd393ca');
 assert.equal(hash(read('public/models/'+source.model)),source.sha256);
 const newlySeparated={
  109:'de07b28c-23ae-4269-8ec4-b52eeb69f263',110:'2d201360-9fb2-45a6-aaf1-24b716cb2497',
  111:'a067f8da-623a-49c8-ae6f-630514a4e5e0',112:'2d55f2d2-3aea-4c56-a82f-96e3df9a5630',
  117:'6425f454-ba84-4f09-8035-81972ca60315',118:'79b1392f-7edf-4cc2-9ec4-07c539094e35',
  119:'c36de435-fa03-41d5-8590-0ea943645668',120:'3db90e64-b0eb-4e9a-bfef-41ea3cf11c43',
 };
 for(const [number,id]of Object.entries(newlySeparated))assert.deepEqual(correction.assets.find(a=>a.id===`fallback-onebailey-${number}`).footprintIds,[id]);
 for(const id of matches[source.id])assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(id)).length,1);
 const absentSourceIds=['c4e0e45a-f6c4-4e42-9c78-8411bbc35196','6c880c2b-4050-43e1-9966-d778d6919944','cd7c1e28-21f5-4557-9658-4c70b4f31a9c','88e4562e-a229-441e-abdb-6d071becf986'];
 for(const id of absentSourceIds)assert.ok(!correction.sourceFootprintIds.includes(id));
 for(const a of correction.assets){assert.equal(a.buildingCount,1);assert.equal(a.searchable,false);assert.ok(a.triangles>0);}
});
test('the second archive provides real 113–116 fallbacks while preserving the separate Jamwon Weve neighbor',()=>{
 const source=base.assets.find(a=>a.id==='apt-a13780006');
 const correction=corrections.corrections.find(c=>c.sourceId===source.id);
 assert.equal(source.nameKo,'반포경남','Archived source identity remains untouched');
 assert.equal(source.model,'apt-a13780006.glb');
 assert.equal(source.sha256,'592c23e04732cfb977adb31a28c5c41ca0d59b372f1a17a4f22df1ec35dab34e');
 assert.equal(hash(read('public/models/'+source.model)),source.sha256);
 assert.equal(correction.assets.reduce((n,a)=>n+a.triangles,0),4363);
 const sourceIds={113:'c4e0e45a-f6c4-4e42-9c78-8411bbc35196',114:'6c880c2b-4050-43e1-9966-d778d6919944',115:'cd7c1e28-21f5-4557-9658-4c70b4f31a9c',116:'88e4562e-a229-441e-abdb-6d071becf986'};
 for(const [number,id]of Object.entries(sourceIds)){
  const a=correction.assets.find(a=>a.id===`fallback-onebailey-${number}`);
  assert.deepEqual(a.footprintIds,[id]);assert.equal(a.genericCorrection.sourceId,source.id);assert.equal(a.searchable,false);
 }
 const neighbor=effective.assets.find(a=>a.id===source.id);
 assert.equal(neighbor.nameKo,'잠원위브아파트 (기존 추정 모형)');
 assert.deepEqual(neighbor.footprintIds,['671b8451-4737-4461-b4c4-725117141fb5']);
 assert.equal(neighbor.triangles,236);assert.equal(neighbor.buildingCount,1);assert.equal(neighbor.residentialCompletionCredit,false);
 assert.deepEqual(effective.matches[source.id],neighbor.footprintIds);
 for(const a of correction.assets){assert.equal(a.apartmentCode,undefined);assert.equal(a.householdCount,undefined);}
 const onebailey=effective.assets.filter(a=>a.id.startsWith('fallback-onebailey-'));
 assert.equal(onebailey.length,23);
 assert.deepEqual(onebailey.map(a=>Number(a.id.split('-').at(-1))).sort((a,b)=>a-b),Array.from({length:23},(_,i)=>101+i));
 assert.equal(new Set(onebailey.flatMap(a=>a.footprintIds)).size,23);
 assert.ok(onebailey.every(a=>!a.footprintIds.includes(neighbor.footprintIds[0])));
 for(const id of correction.sourceFootprintIds)assert.equal(Object.values(effective.matches).filter(ids=>ids.includes(id)).length,1);
});
test('the previously published 11 One Bailey singletons retain all metadata and exact GLB bytes',()=>{
 // Frozen before completing the split; metadata includes each immutable GLB digest.
 const existing={
  101:'2ff6b023ae71bca37a95fa5903f13eaa685a427cade4ee034ce2ef28ff2f7ac2',
  102:'688d78333f5f6ddbea798b06ccb3b07a1fe7dc0c5f990613a98bd9d3d0666f84',
  103:'af4c7ac3d86ed33492b3a93a3bf8d7210917ad5480a50282a0a011e69bda3eb3',
  104:'e96c66b21b1f089baa3b2fba3da8651a0cd73438038836db78940fceb23d2efa',
  105:'1ef88f70b6e20286aed3b39c9888603b4711622c1347ff60fbe89002ee07430d',
  106:'bec7c2dc894594fb22e04600e60bd2d42bdf30bd4f4763bbddbbb734da6c0865',
  107:'617720a513ea3275e36dd3bc36d76169fe10718b35a4e9312af71375ab9913a8',
  108:'a058593ee47e66dd6d05a80bea8cbf13f467763082bd4bab4fea089175940a1b',
  121:'0b3acb688d59296f58509a860decc328e3f56b2bb68536fd5dea3fa3a8b09f54',
  122:'a783e1fd17c603888688888fa2cbc268a2e9eca413e48222f7bc39f3368608bd',
  123:'05dedf361c3fbc2b78cddeb952043876d0dc85c45b4c54247f2ffb8cc5f64d63',
 };
 for(const [number,digest]of Object.entries(existing)){
  const a=effective.assets.find(a=>a.id===`fallback-onebailey-${number}`);
  assert.equal(hash(JSON.stringify(a)),digest,`${number} metadata is unchanged`);
  assert.equal(hash(read('public/models/'+a.model)),a.sha256,`${number} GLB is unchanged`);
 }
});
test('One Pentas and neighboring Prestige retain their prior metadata, GLB bytes and audit proof',()=>{
 const correction=corrections.corrections.find(c=>c.sourceId==='apt-a10022556');
 assert.equal(hash(JSON.stringify(correction)),'82e3ae02f8f6794b04e7705aa744c94266af105f7cd57d19a6cb5c1a17150f81');
 for(const a of correction.assets)assert.equal(hash(read('public/models/'+a.model)),a.sha256);
 assert.equal(hash(read('docs/model-audit/onepentas-generic-split.json')),'31dc965a445f85be87e7d6e356952efa4ac91bf1e3900704a0f00d765eefda14');
});
test('One Pentas excludes Prestige 126 without deleting that neighboring tower',()=>{
 const neighbor=effective.assets.find(a=>a.id==='fallback-prestige-126');
 assert.equal(neighbor.apartmentCode,undefined);
 assert.equal(neighbor.buildingCount,1);
 assert.deepEqual(neighbor.footprintIds,['b21842a2-9832-4a21-bcc5-1c571f309556']);
 for(const a of corrections.corrections.find(c=>c.sourceId==='apt-a10022556').assets.filter(a=>a.id!==neighbor.id)){
  assert.ok(!a.footprintIds.includes(neighbor.footprintIds[0]));
 }
});
