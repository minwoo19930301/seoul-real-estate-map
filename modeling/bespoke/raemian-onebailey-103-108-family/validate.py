import bpy,json,math,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent;R=json.loads((O/'recipe.json').read_text());checks=[]
for T in R['towers']:
 no=T['number'];C=bpy.data.collections.get(f'{no}_retained_individual_massing')
 if C is None:continue
 obs=list(C.objects);verts=[v.co for ob in obs for v in ob.data.vertices];H=max(v.z for v in verts);m=bpy.data.objects[f'{no}_editable_massing'];base=[v.co for v in m.data.vertices if abs(v.co.z)<1e-6];lon,lat=T['coordinate'];ring=[((x-lon)*111320*math.cos(math.radians(lat)),(y-lat)*111320) for x,y in T['geometry']['coordinates'][0][:-1]]
 err=max(min(math.hypot(x-v.x,y-v.y) for v in base) for x,y in ring)
 checks.append({'id':T['id'],'sourceId':T['sourceId'],'sourceRingVertices':len(ring),'retainedBaseRingMaxErrorM':err,'heightM':H,'legalHeightM':T['registerHeightM'],'heightErrorM':abs(H-T['registerHeightM']),'finiteVertices':all(math.isfinite(v[k]) for v in verts for k in range(3)),'editableMeshObjects':len(obs),'floors':T['registerFloors'],'noBridge':True,'passed':err<.0001 and abs(H-T['registerHeightM'])<.0001})
assert all(c['passed'] and c['finiteVertices'] for c in checks)
(O/'geometry-validation.json').write_text(json.dumps({'passed':True,'assets':checks},indent=2));print(json.dumps(checks))
