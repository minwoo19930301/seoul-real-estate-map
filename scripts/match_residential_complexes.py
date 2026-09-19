"""Reproduce the 179-record residential complex match on the 3,088-asset baseline.

This wrapper never edits a manifest or database. It invokes the existing bounded
matcher in a temporary directory, then applies the final geometry/district and
ownership audit before writing the two requested docs.
"""
import argparse,json,sqlite3,subprocess,tempfile
from pathlib import Path
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pool',type=Path,default=ROOT/'docs/residential-expansion-apartment-pool.json'); ap.add_argument('--manifest',type=Path,required=True); ap.add_argument('--footprints',type=Path,required=True); ap.add_argument('--output',type=Path,default=ROOT/'docs/residential-expansion-complex-matched.json'); ap.add_argument('--rejections-output',type=Path,default=ROOT/'docs/residential-expansion-complex-rejections.json'); args=ap.parse_args()
 manifest=json.loads(args.manifest.read_text()); assets=manifest['assets']
 if len(assets)!=3088: raise SystemExit(f'refusing to run against {len(assets)} assets; expected baseline 3088')
 pool=json.loads(args.pool.read_text()); fm=json.loads(args.footprints.read_text()); owned={str(b) for ids in fm.values() if isinstance(ids,list) for b in ids}
 districts={f['properties']['names']['primary']:shape(f['geometry']) for f in json.loads((ROOT/'data/building-source/districts.geojson').read_text())['features']}
 with tempfile.TemporaryDirectory() as td:
  out=Path(td)/'matched.json'; rej=Path(td)/'rejected.json'
  subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/match_district_landmarks.py'),'--additional-pool',str(args.pool),'--baseline-matches',str(args.footprints),'--per-district','99999','--allow-shortfall','--output',str(out),'--rejections-output',str(rej)],check=True)
  matched=json.loads(out.read_text()); rejected=json.loads(rej.read_text())
 db=sqlite3.connect('file:'+str(ROOT/'data/buildings.sqlite')+'?mode=ro',uri=True); cur=db.cursor(); claimed=set(); clean=[]
 for c in matched:
  good=[]; bad=[]
  for bid in c.get('buildingIds',[]):
   if bid in owned or bid in claimed: bad.append('existing or duplicate footprint ownership'); continue
   row=cur.execute('select geometry,kind from buildings where id=?',(bid,)).fetchone()
   if not row or not row[0] or row[1]!='building': bad.append('missing geometry or non-building kind'); continue
   if c['district'] not in districts or not districts[c['district']].covers(shape(json.loads(row[0])).representative_point()): bad.append('building representative point outside district'); continue
   good.append(bid)
  if good: c['buildingIds']=good; c.setdefault('membership',{})['postprocess']='read-only geometry/kind/district/ownership audit'; claimed.update(good); clean.append(c)
  else: rejected.append({'id':c['id'],'name':c['nameKo'],'district':c['district'],'reason':'; '.join(sorted(set(bad))) or 'no valid building footprint after audit'})
 ids={x['id'] for x in clean}|{x['id'] for x in rejected}; poolids={x['id'] for x in pool}
 if ids!=poolids: raise AssertionError(f'pool accounting mismatch: pool={len(poolids)} output={len(ids)}')
 args.output.write_text(json.dumps(clean,ensure_ascii=False,indent=2)+'\n'); args.rejections_output.write_text(json.dumps(rejected,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'pool':len(pool),'matched':len(clean),'rejected':len(rejected),'uniqueBuildings':len(claimed)},ensure_ascii=False))
if __name__=='__main__': main()
