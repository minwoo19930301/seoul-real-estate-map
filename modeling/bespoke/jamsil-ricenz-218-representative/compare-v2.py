import pathlib,json,sys,struct,collections,hashlib,numpy as np
from PIL import Image
P=pathlib.Path(__file__).parent;sys.path.insert(0,str(pathlib.Path.cwd()/'scripts/bespoke'));from validate_height_regions import read_triangles
old=P/'archive-v1/jamsil-ricenz-218.glb';new=P/'jamsil-ricenz-218.glb';a=read_triangles(old);b=read_triangles(new)
def ct(x):return collections.Counter(tuple(sorted(tuple(round(float(c),6) for c in v) for v in t)) for t in x)
ca,cb=ct(a),ct(b);added=cb-ca;removed=ca-cb;assert not added;proof=json.loads((P/'optimization-proof.json').read_text());assert sum(removed.values())==proof['removed_triangles'];assert len(a)-len(b)==proof['removed_triangles']
def attrs(p):
 raw=p.read_bytes();n=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+n]);blob=raw[28+n:];pairs=set();types=[];counts=[]
 def ar(i):
  ac=g['accessors'][i];bv=g['bufferViews'][ac['bufferView']];dt={5126:'<f4',5123:'<u2',5125:'<u4'}[ac['componentType']];k={'VEC3':3,'SCALAR':1}[ac['type']];off=bv.get('byteOffset',0)+ac.get('byteOffset',0);return np.frombuffer(blob,dtype=dt,count=ac['count']*k,offset=off).reshape(-1,k)
 for m in g['meshes']:
  for pr in m['primitives']:
   assert set(pr['attributes'])=={'POSITION','NORMAL'};pos=ar(pr['attributes']['POSITION']);nor=ar(pr['attributes']['NORMAL']);pairs.update(tuple(round(float(v),6) for v in row) for row in np.concatenate([pos,nor],axis=1));types.append(g['accessors'][pr['indices']]['componentType']);counts.append(len(pos))
 return pairs,types,counts
pa,ta,na=attrs(old);pb,tb,nb=attrs(new);assert not pb-pa;assert all(t==5123 for t in tb)
views=[]
for v in ['front','opposite','side','roof']:
 x=np.asarray(Image.open(P/'archive-v1'/(v+'.png')).convert('RGB'),dtype=np.float32);y=np.asarray(Image.open(P/(v+'.png')).convert('RGB'),dtype=np.float32);z=np.abs(x-y);views.append({'view':v,'mean_abs_8bit_difference':float(z.mean()),'percent_pixels_diff_gt8':float(np.any(z>8,axis=2).mean()*100),'max_difference':float(z.max())})
r={'v1_bytes':old.stat().st_size,'v2_bytes':new.stat().st_size,'reduction_fraction':1-new.stat().st_size/old.stat().st_size,'v1_triangles':len(a),'v2_triangles':len(b),'removed_triangles':sum(removed.values()),'added_or_changed_triangles':sum(added.values()),'all_remaining_position_normal_pairs_identical_to_v1_rounded_1e6':not bool(pb-pa),'old_index_component_types':ta,'new_index_component_types':tb,'old_exported_vertices':sum(na),'new_exported_vertices':sum(nb),'rail_bars_unchanged':proof['vertical_rail_bars_unchanged'],'render_comparison':views,'glb_sha256':hashlib.sha256(new.read_bytes()).hexdigest()};(P/'optimization-comparison.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
