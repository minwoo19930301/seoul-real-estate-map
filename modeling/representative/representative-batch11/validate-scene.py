import bpy,json,math
from pathlib import Path
P=Path(__file__).parent
sites=json.loads((P/'selected-input.json').read_text())['sites'];report=[]
for S in sites:
 cs=sorted([c for c in bpy.data.collections if c.name.startswith(S['code'])],key=lambda c:c.name)
 keep=cs[-1]
 for c in cs[:-1]:
  for ob in list(c.objects):bpy.data.objects.remove(ob,do_unlink=True)
  bpy.data.collections.remove(c)
 keep.name=S['code']+' '+S['name']
 obs=[ob for ob in keep.objects if ob.type=='MESH'];shells=[ob for ob in obs if 'retained_footprint_shell' in ob.name]
 assert len(shells)==len(S['towers'])
 for T in S['towers']:
  ob=next(ob for ob in shells if ob.get('source_building_id')==T['id'])
  source={tuple(p) for p in T['ringEastNorthM']};actual={(v.co.x,v.co.y) for v in ob.data.vertices if v.co.z>5}
  assert all(min(math.dist(a,b) for b in actual)<.001 for a in source) and all(min(math.dist(a,b) for b in source)<.001 for a in actual),(S['code'],T['id'],'footprint changed')
  height=T.get('height_m') or T['num_floors']*3
  assert abs(max(v.co.z for v in ob.data.vertices)-height)<.01
 report.append({'code':S['code'],'sourcePolygons':len(shells),'editableMeshObjects':len(obs),'footprintsPreserved':True,'heightsPreserved':True})
bpy.ops.wm.save_as_mainfile(filepath=str(P/'outputs/representative-batch11.blend'))
(P/'scene-validation.json').write_text(json.dumps(report,indent=2));print(report)
