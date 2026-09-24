from pathlib import Path
import bpy,json,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
P=Path(__file__).resolve().parent;out=[]
for n,specs in {'105':[(-61,-11,112.85)],'106':[(-1,-9,112.85)]}.items():
 obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset_id')=='bespoke-raemian-onepentas-'+n and '_roof_slab'in o.name];verts=[];faces=[]
 for o in obs:
  offset=len(verts);verts += [o.matrix_world@v.co for v in o.data.vertices];faces += [tuple(offset+i for i in f.vertices)for f in o.data.polygons]
 bvh=BVHTree.FromPolygons(verts,faces)
 for x,y,z in specs:
  hit,normal,idx,dist=bvh.ray_cast(Vector((x,y,z+.5)),Vector((0,0,-1)),2);ok=hit is not None and abs(hit.z-(z+.12))<.03
  out.append({'tower':n,'test':'serviceheadseatedonindividualroof','probe':[x,y,z+.5],'hit':list(hit)if hit else None,'pass':ok});assert ok
# Openpiloti center-free void between sparsecolumns/core:geometricalstate,
# sourcephotodimensions remainapproximate;noarbitrarygroundrectangle.
assert not any(o.type=='MESH' and 'groundplane'in o.name.lower()for o in bpy.context.scene.objects)
(P/'roof-support-validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
