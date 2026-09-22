import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { referenceManifest } from '../src/reference-models.ts';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const manifest=read('public/models/bespoke-manifest.json');
const all=referenceManifest(manifest,[...read('public/models/manifest.json').assets,...read('public/models/reference-manifest.json').assets]).assets;
const proof=read('docs/model-audit/published-bespoke.json');
for(const [site,count,representative] of [['songpa-helio-city',33,416],['jamsil-parkrio',59,207],['jamsil-trizium',44,344],['daechi-eunma',27,21],['godeok-gracium',21,101],['raemian-la-classy',4,102],['godeok-arteon',24,323],['godeok-central-ipark',17,512],['godeok-raemian-hillstate',27,126],['geumho-park-hills',15,101],['raemian-oksu-riverzen',14,101],['dmc-parkview-xi',5,301]]){
  test(`${site} copies retain individual ownership and one shared file`,()=>{
    const copies=all.filter(a=>a.sourceRecord.siteId===site+'-shared');assert.equal(copies.length,count);
    const source=all.find(a=>a.id===`bespoke-${site}-${representative}`);
    const identity=read(`docs/model-audit/${site}-source-identity.json`),bindings=read(`docs/model-audit/${site}-fallback-bindings.json`).bindings;
    for(const a of copies){
      const n=Number(a.id.split('-').at(-1)),row=identity.towers.find(r=>r.number===n),binding=bindings.find(b=>b.number===n);
      assert.equal(a.model,source.model);assert.equal(a.sha256,source.sha256);assert.equal(a.sourceRecord.blendSource,source.sourceRecord.blendSource);
      assert.deepEqual(a.footprintIds,[row.sourceId]);assert.deepEqual(a.supersedes,binding.supersedes);
      assert.equal(a.modelInstance.sourceAssetId,source.id);assert.equal(a.modelInstance.hiddenNodes.length, ['godeok-gracium','raemian-la-classy','godeok-arteon','godeok-central-ipark','godeok-raemian-hillstate','geumho-park-hills','raemian-oksu-riverzen','dmc-parkview-xi'].includes(site)?0:1);
      const registered=Number(row.register.height), expected=registered>0?registered:Number(row.register.floors)*3.05;
      assert.ok(Math.abs(a.dimensions[1]-expected)<.001);
      if(!registered){assert.equal(a.sourceRecord.buildingFacts.registeredHeightM,0);assert.match(a.sourceRecord.buildingFacts.heightBasis,/not measured/);}
      assert.equal(a.sourceRecord.delivery,'shared-instance');assert.match(a.sourceRecord.inferenceScope,/floor pattern/);
    }
    assert.equal(new Set(copies.flatMap(a=>a.footprintIds)).size,count);
    assert.equal(proof.sites[site+'-shared'].newGlbFiles,0);assert.equal(proof.sites[site+'-shared'].newBlendFiles,0);
  });
}
