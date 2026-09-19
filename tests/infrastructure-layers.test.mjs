import assert from 'node:assert/strict';
import test from 'node:test';
import { TransitLayer } from '../src/transit.ts';
import { Avenues } from '../src/avenues.ts';

function mapMock() {
  const calls=[]; return { calls, addSource(...x){calls.push(['addSource',...x])}, addLayer(...x){calls.push(['addLayer',...x])}, setLayoutProperty(...x){calls.push(['layout',...x])}, setFilter(...x){calls.push(['filter',...x])}, getLayer(){return undefined}, on(...x){calls.push(['on',...x])} };
}
test('transit and avenues validate input, fail cleanly and toggle idempotently', async () => {
const oldFetch=globalThis.fetch;
const point=(id,kind='rail_station')=>({type:'Feature',id,geometry:{type:'Point',coordinates:[126.9,37.5]},properties:{kind,nameKo:'테스트',sourceUrl:'x',locationMethod:'osm'}});
try {
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[point('r'),point('b','bus_stop'),point('bike','bike_station')]})});
  const m=mapMock(), t=new TransitLayer(m); await t.init(); assert.equal(m.calls.filter(x=>x[0]==='addSource').length,1); assert.equal(m.calls.filter(x=>x[0]==='addLayer').length,6);
  const n=m.calls.length; t.setVisible(true); t.setKinds(true,true); assert.equal(m.calls.length,n);
  t.setKinds(false,true,false); assert.ok(m.calls.some(x=>x[0]==='layout'&&x[1]==='transit-labels'&&x[3]==='none')); assert.ok(m.calls.some(x=>x[0]==='layout'&&x[1]==='transit-bike-labels'&&x[3]==='none')); assert.ok(m.calls.some(x=>x[0]==='layout'&&x[1]==='transit-bus-labels'&&x[3]==='visible'));
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[point('x'),point('x')]})}); await assert.rejects(()=>new TransitLayer(mapMock()).init());
  globalThis.fetch=async()=>({ok:true,json:async()=>({type:'FeatureCollection',features:[{...point('x'),geometry:{type:'Point',coordinates:[NaN,37.5]}}]})}); await assert.rejects(()=>new TransitLayer(mapMock()).init());
  globalThis.fetch=async()=>({ok:false,status:503}); const failed=mapMock(); await assert.rejects(()=>new TransitLayer(failed).init()); assert.equal(failed.calls.length,0);
  globalThis.fetch=async url=>({ok:true,json:async()=>({type:'FeatureCollection',features:[]})}); const aMap=mapMock(), a=new Avenues(aMap); await a.init(); const ac=aMap.calls.length; a.setVisible(true); assert.equal(aMap.calls.length,ac); a.setVisible(false); assert.equal(aMap.calls.filter(x=>x[0]==='layout').length,6);
  globalThis.fetch=async()=>({ok:false}); await assert.rejects(()=>new Avenues(mapMock()).init());
} finally { globalThis.fetch=oldFetch; }

});

test('official bus and Ttareungi records have stable source IDs and are not mixed with OSM fallback points', async () => {
  const { readFileSync } = await import('node:fs');
  const data = JSON.parse(readFileSync('public/transit.json', 'utf8'));
  const points = data.features;
  assert.equal(new Set(points.map(f => f.id)).size, points.length);
  for (const [kind, expected] of [['bus_stop', 11218], ['bike_station', 2786]]) {
    const group = points.filter(f => f.properties.kind === kind);
    assert.equal(group.length, expected);
    for (const f of group) {
      assert.ok(f.id.startsWith('seoul-' + kind + '-'));
      assert.equal(f.properties.locationMethod, 'seoul_official_xlsx');
      assert.ok(f.properties.sourceRow > 1);
      assert.ok(f.properties.ref);
      assert.ok(f.geometry.coordinates[0] > 126.7 && f.geometry.coordinates[0] < 127.3);
      assert.ok(f.geometry.coordinates[1] > 37.4 && f.geometry.coordinates[1] < 37.75);
    }
  }
  assert.equal(points.filter(f => f.properties.kind === 'rail_station').length, 311);
});
