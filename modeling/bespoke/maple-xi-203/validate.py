import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());objs=[o for o in bpy.data.objects if o.type=='MESH'and o.get('asset_id')==D['id']];checks=[]
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);checks.append({'component':o.name,'signedVolume':bm.calc_volume(signed=True),'nonManifoldEdges':sum(not e.is_manifold for e in bm.edges),'finite':all(math.isfinite(c)for v in bm.verts for c in v.co)});bm.free()
assert len(objs)>50 and all(x['signedVolume']>0 and x['nonManifoldEdges']==0 and x['finite']for x in checks)
bounds={'min':[min((o.matrix_world@v.co)[i]for o in objs for v in o.data.vertices)for i in range(3)],'max':[max((o.matrix_world@v.co)[i]for o in objs for v in o.data.vertices)for i in range(3)]};assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<62.451
V=[Vector(p)for p in D['ringEN']];rays=[]
for e,t,z,label in [(3, 0.32, 30.0, 'NEbedroom'), (3, 0.86, 30.0, 'NEmetalwide'), (4, 0.94, 30.0, 'SEwhitewide'), (4, 0.635, 30.0, 'SEdeepshaft'), (4, 0.15600000000000003, 30.0, 'SEmetalwrap'), (5, 0.87, 30.0, 'SWwide'), (2, 0.40, 30.0, 'NWcore'), (4, 0.76, 2.2, 'groundportal')]:
 a,b=V[e],V[(e+1)%6];n=Vector((-(b-a).y,(b-a).x)).normalized();p=a+(b-a)*t;start=Vector((p.x+n.x*4,p.y+n.y*4,z));direction=Vector((-n.x,-n.y,0));hit=bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),start,direction,distance=10);assert hit[0]and hit[4].active_material.name.startswith('Maple203_glass'),(label,str(hit));rays.append({'sample':label,'firstHit':hit[4].name,'material':hit[4].active_material.name})
(O/'geometry-validation.json').write_text(json.dumps({'status':'PASS','scope':'Closed positive-volume finite solids,0mground,within62.45mconservativeenvelope. Not proof ofphotographicaccuracy.','boundsBlenderENU':bounds,'components':checks},indent=2));(O/'opening-visibility.json').write_text(json.dumps({'status':'PASS','rays':rays},indent=2));bpy.context.scene.camera=bpy.data.objects['B_south_primary_match']
for sc in bpy.data.screens:
 for area in sc.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL';area.spaces.active.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-203.blend'));print('VALIDATION203_PASS',len(checks),bounds,rays)
