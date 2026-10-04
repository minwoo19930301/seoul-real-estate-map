import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { referenceManifest } from '../src/reference-models.ts';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const manifest=read('public/models/bespoke-manifest.json');
const all=referenceManifest(manifest,[...read('public/models/manifest.json').assets,...read('public/models/reference-manifest.json').assets]).assets;
const proof=read('docs/model-audit/published-bespoke.json');
for(const [site,count,representative,assetSite=site] of [['songpa-helio-city',33,416],['jamsil-parkrio',59,207],['jamsil-trizium',44,344],['daechi-eunma',27,21],['godeok-gracium',21,101],['raemian-la-classy',4,102],['godeok-arteon',24,323],['godeok-central-ipark',17,512],['godeok-raemian-hillstate',27,126],['geumho-park-hills',15,101],['raemian-oksu-riverzen',14,101],['dmc-parkview-xi',5,301],['seocho-grand-xi',8,109],['gaepo-raemian-forest',26,102],['raemian-blesstige',20,209],['dh-honor-hills',20,310],['dmc-parkview-xi-extension',33,301,'dmc-parkview-xi'],['mapo-raemian-prugio',33,404],['mapo-grang-xi',14,110],['banpo-xi-final',1,101,'banpo-xi'],['dmc-parkview-xi-completion',22,301,'dmc-parkview-xi'],['godeok-raemian-hillstate-completion',18,126,'godeok-raemian-hillstate'],['mapo-raemian-prugio-completion',10,404,'mapo-raemian-prugio'],['gaepo-raemian-forest-completion',3,102,'gaepo-raemian-forest'],['raemian-blesstige-completion',2,209,'raemian-blesstige'],['dh-honor-hills-completion',2,310,'dh-honor-hills'],['godeok-arteon-completion',16,323,'godeok-arteon'],['godeok-central-ipark-completion',1,512,'godeok-central-ipark'],['raemian-la-classy-completion',2,102,'raemian-la-classy']]){
  test(`${site} copies retain individual ownership and one shared file`,()=>{
    const copies=all.filter(a=>a.sourceRecord.siteId===site+'-shared');assert.equal(copies.length,count);
    const source=all.find(a=>a.id===`bespoke-${assetSite}-${representative}`);
    const identity=read(`docs/model-audit/${site}-source-identity.json`),bindings=read(`docs/model-audit/${site}-fallback-bindings.json`).bindings;
    for(const a of copies){
      const n=Number(a.id.split('-').at(-1)),row=identity.towers.find(r=>r.number===n),binding=bindings.find(b=>b.number===n);
      assert.equal(a.model,source.model);assert.equal(a.sha256,source.sha256);assert.equal(a.sourceRecord.blendSource,source.sourceRecord.blendSource);
      assert.deepEqual(a.footprintIds,[row.sourceId]);assert.deepEqual(a.supersedes,binding.supersedes);
      assert.equal(a.modelInstance.sourceAssetId,source.id);assert.equal(a.modelInstance.hiddenNodes.length, ['godeok-gracium','raemian-la-classy','godeok-arteon','godeok-central-ipark','godeok-raemian-hillstate','geumho-park-hills','raemian-oksu-riverzen','dmc-parkview-xi','seocho-grand-xi','gaepo-raemian-forest','raemian-blesstige','dh-honor-hills','dmc-parkview-xi-extension','mapo-raemian-prugio','mapo-grang-xi','banpo-xi-final','dmc-parkview-xi-completion','godeok-raemian-hillstate-completion','mapo-raemian-prugio-completion','gaepo-raemian-forest-completion','raemian-blesstige-completion','dh-honor-hills-completion','godeok-arteon-completion','godeok-central-ipark-completion','raemian-la-classy-completion'].includes(site)?0:1);
      const registered=Number(row.register.height), policy=a.sourceRecord.heightPolicy, expected=policy?.heightM ?? (registered>0?registered:Number(row.register.floors)*3.05);
      if(policy){assert.equal(policy.policy,'preserve-existing-visible-fallback-height');assert.equal(a.heightEstimated,true);assert.equal(a.sourceRecord.buildingFacts.heightUnresolved,true);assert.equal(registered,57.7);assert.ok(expected>82 && expected<83);assert.match(a.sourceRecord.buildingFacts.heightBasis,/not measured/);}
      assert.ok(Math.abs(a.dimensions[1]-expected)<.001);
      if(!registered){assert.equal(a.sourceRecord.buildingFacts.registeredHeightM,0);assert.match(a.sourceRecord.buildingFacts.heightBasis,/not measured/);}
      assert.equal(a.sourceRecord.delivery,'shared-instance');assert.match(a.sourceRecord.inferenceScope,/floor pattern/);
    }
    assert.equal(new Set(copies.flatMap(a=>a.footprintIds)).size,count);
    assert.equal(proof.sites[site+'-shared'].newGlbFiles,0);assert.equal(proof.sites[site+'-shared'].newBlendFiles,0);
  });
}
