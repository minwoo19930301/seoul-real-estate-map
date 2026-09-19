import assert from 'node:assert/strict';
import test from 'node:test';
import { TransitLayer } from '../src/transit.ts';
import { Avenues } from '../src/avenues.ts';

function mapMock() {
  const calls=[]; return { calls, addSource(...x){calls.push(['addSource',...x])}, addLayer(...x){calls.push(['addLayer',...x])}, setLayoutProperty(...x){calls.push(['layout',...x])}, setFilter(...x){calls.push(['filter',...x])}, getLayer(){return undefined} };
}
test('transit and avenues validate input, fail cleanly and toggle idempotently', async () => {
const oldFetch=globalThis.fetch;
const point=(id,kind='rail_station')=>({type:'Feature',id,geometry:{type:'Point',coordinates:[126.9,37.5]},properties:{kind,nameKo:'테스트',sourceUrl:'x',locationMethod:'osm'}});
try {
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[point('r'),point('b','bus_stop')]})});
  const m=mapMock(), t=new TransitLayer(m); await t.init(); assert.equal(m.calls.filter(x=>x[0]==='addSource').length,1); assert.equal(m.calls.filter(x=>x[0]==='addLayer').length,3);
  const n=m.calls.length; t.setVisible(true); t.setKinds(true,true); assert.equal(m.calls.length,n);
  t.setKinds(false,true); assert.ok(m.calls.some(x=>x[0]==='layout'&&x[3]==='none')); assert.ok(m.calls.some(x=>x[0]==='filter'));
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[point('x'),point('x')]})}); await assert.rejects(()=>new TransitLayer(mapMock()).init());
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[{...point('x'),geometry:{type:'Point',coordinates:[NaN,37.5]}}]})}); await assert.rejects(()=>new TransitLayer(mapMock()).init());
  globalThis.fetch=async()=>({ok:false,status:503}); const failed=mapMock(); await assert.rejects(()=>new TransitLayer(failed).init()); assert.equal(failed.calls.length,0);
  globalThis.fetch=async url=>({ok:true,json:async()=>({type:'FeatureCollection',features:[]})}); const aMap=mapMock(), a=new Avenues(aMap); await a.init(); const ac=aMap.calls.length; a.setVisible(true); assert.equal(aMap.calls.length,ac); a.setVisible(false); assert.equal(aMap.calls.filter(x=>x[0]==='layout').length,6);
  globalThis.fetch=async()=>({ok:false}); await assert.rejects(()=>new Avenues(mapMock()).init());
} finally { globalThis.fetch=oldFetch; }

});
