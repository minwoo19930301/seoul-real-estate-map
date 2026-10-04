import pathlib,json,sys
R=pathlib.Path.cwd();P=pathlib.Path(__file__).parent;sys.path.insert(0,str(R/'scripts/bespoke'));from validate_neighbor_intrusions import neighbor_intrusions
from validate_height_regions import read_triangles
out=[]
for t,n in [(138,139),(139,138),(153,158),(158,153)]:
 p=P/str(t)
 if not (p/'standalone-validation.json').exists():continue
 d=json.loads((p/'source-data.json').read_text());nd=json.loads((P/str(n)/'source-data.json').read_text());hits=neighbor_intrusions(read_triangles(p/f'jamsil-els-{t}.glb'),d['anchor_lonlat'],nd['geometry'],nd['register_height_m']);out.append({'tower':t,'neighbor':n,'crossing_triangles':len(hits),'first_indices':hits[:10],'checker':'scripts/bespoke/validate_neighbor_intrusions.py; clips each triangle at neighborHeight-1mm before projected hull intersection'});assert not hits,(t,len(hits))
(P/'author-neighbor-intrusions-final.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
