from pathlib import Path
import bpy,json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
O=Path(__file__).resolve().parent;dg=bpy.context.evaluated_depsgraph_get()
solids=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(k in o.name for k in ('actual_outline','_terrace','_glazed_roof_cap')) and 'coping' not in o.name];bvh=[(o.name,BVHTree.FromObject(o,dg)) for o in solids];rows=[]
for o in bpy.context.scene.objects:
 if o.type!='MESH' or not o.name.endswith('_canopy_stone_supports'):continue
 pts=[o.matrix_world@v.co for v in o.data.vertices]
 for k in range(0,len(pts),8):
  vs=pts[k:k+8];x=sum(v.x for v in vs)/8;y=sum(v.y for v in vs)/8;lo=min(v.z for v in vs);hits=[]
  for name,b in bvh:
   loc,n,fi,dist=b.ray_cast(Vector((x,y,160)),Vector((0,0,-1)),200)
   if loc is not None:hits.append((loc.z,name))
  best=max(hits,default=(None,None));rows.append({'support':o.name,'index':k//8,'xy':[x,y],'supportBase':lo,'highestSupportingSolid':best,'seatedOrEmbedded':best[0] is not None and best[0]>=lo-.08})
(O/'roof-support-validation.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'supports':len(rows),'seated':sum(r['seatedOrEmbedded'] for r in rows),'unseated':[r for r in rows if not r['seatedOrEmbedded']]},indent=2))

voids=[]
for o in bpy.context.scene.objects:
 if o.type!='MESH' or not o.name.endswith('_open_louver_beams'):continue
 pts=[o.matrix_world@v.co for v in o.data.vertices];centres=[sum(pts[i:i+8],Vector())/8 for i in range(0,len(pts),8)];b=BVHTree.FromObject(o,dg);a=centres[4];gap=(centres[4]+centres[5])/2
 on=b.ray_cast(a+Vector((0,0,1)),Vector((0,0,-1)),2)[0];off=b.ray_cast(gap+Vector((0,0,1)),Vector((0,0,-1)),2)[0]
 voids.append({'object':o.name,'onBeamHit':on is not None,'betweenBeamsOpen':off is None})
(O/'roof-opening-validation.json').write_text(json.dumps(voids,indent=2));assert all(v['onBeamHit'] and v['betweenBeamsOpen'] for v in voids);assert all(r['seatedOrEmbedded'] for r in rows);print(json.dumps({'openCanopies':len(voids),'allOpenAndSeated':True}))
