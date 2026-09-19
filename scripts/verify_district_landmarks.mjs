import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const folder=path.join(root,'public/models');
const manifest=JSON.parse(await fs.readFile(path.join(folder,'manifest.json'),'utf8'));
const matches=JSON.parse(await fs.readFile(path.join(folder,'footprint-matches.json'),'utf8'));
const rows=[];const loader=new GLTFLoader();
for(const asset of manifest.assets){
 const bytes=await fs.readFile(path.join(folder,asset.model));
 assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),asset.sha256,asset.id+' sha256');
 const jsonLength=bytes.readUInt32LE(12);const document=JSON.parse(bytes.subarray(20,20+jsonLength).toString('utf8').trim());assert.ok(!(document.buffers??[]).some(b=>b.uri),asset.id+' external buffer');assert.ok(!(document.images??[]).some(i=>i.uri),asset.id+' external image');
 const gltf=await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
 const box=new THREE.Box3().setFromObject(gltf.scene),size=box.getSize(new THREE.Vector3()).toArray();
 assert.ok(Math.abs(box.min.y)<.01,asset.id+' floor');
 assert.ok(size.every((v,i)=>Math.abs(v-asset.dimensions[i])<.01),asset.id+' dimensions');
 let triangles=0,drawCalls=0,vertices=0;
 gltf.scene.traverse(node=>{if(!node.isMesh)return;const g=node.geometry,p=g.attributes.position,n=g.attributes.normal;
   drawCalls+=Array.isArray(node.material)?node.material.length:1;triangles+=(g.index?.count??p.count)/3;vertices+=p.count;
   for(let i=0;i<p.count;i++){assert.ok([p.getX(i),p.getY(i),p.getZ(i)].every(Number.isFinite));const len=Math.hypot(n.getX(i),n.getY(i),n.getZ(i));assert.ok(Math.abs(len-1)<.01,asset.id+' normal');}
   if(g.index)for(let i=0;i<g.index.count;i++)assert.ok(g.index.getX(i)<p.count,asset.id+' index');
   g.dispose();for(const material of Array.isArray(node.material)?node.material:[node.material])material.dispose();
 });
 assert.equal(triangles,asset.triangles,asset.id+' triangles');if(asset.category==='bridge')assert.deepEqual(matches[asset.id],[],asset.id+' must not replace building footprints');else assert.ok(matches[asset.id]?.length,asset.id+' footprint membership');
 rows.push({id:asset.id,bytes:bytes.length,triangles,drawCalls,vertices,bounds:{min:box.min.toArray(),max:box.max.toArray()},sha256:asset.sha256});
}
const result={validator:`Three.js GLTFLoader; all ${rows.length} binary files parsed`,assetCount:rows.length,totalBytes:rows.reduce((s,a)=>s+a.bytes,0),totalTriangles:rows.reduce((s,a)=>s+a.triangles,0),maxAssetBytes:Math.max(...rows.map(r=>r.bytes)),checks:['SHA256','float32metreBounds','floorOrigin','finitePositions','unitNormals','indicesInRange','triangleCount','nonemptyFootprintMembership','noExternalResources'],assets:rows};
await fs.writeFile(path.join(root,'docs/LANDMARK_ASSET_VALIDATION.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({...result,assets:undefined},null,2));
