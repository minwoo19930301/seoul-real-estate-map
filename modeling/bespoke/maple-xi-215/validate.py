import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());objs=[o for o in bpy.data.objects if o.type=='MESH' and o.get('asset_id')==D['id']];checks=[]
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);checks.append({'component':o.name,'signedVolume':bm.calc_volume(signed=True),'nonManifoldEdges':sum(not e.is_manifold for e in bm.edges),'finite':all(math.isfinite(c) for v in bm.verts for c in v.co)});bm.free()
assert all(x['signedVolume']>0 and x['nonManifoldEdges']==0 and x['finite'] for x in checks)
bounds={'min':[min((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)],'max':[max((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)]};assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<80.601
V=[Vector(p) for p in D['ringEN']];rays=[]
for e,t,h,label in [(4,1-.49,1.4,'SE broadwhite'),(4,.07,1.4,'SE metalwide'),(3,.87,1.4,'NE metalwide'),(3,.52,1.6,'NE smallwindow'),(3,.30,1.4,'NE coplanarwhitepair'),(0,.24,1.4,'provisional e0'),(1,.36,1.4,'provisional e1'),(5,.2,1.4,'provisional e5')]:
 a,b=V[e],V[(e+1)%6];n=Vector((-(b-a).y,(b-a).x)).normalized();c=a+(b-a)*t;start=Vector((c.x+n.x*4,c.y+n.y*4,4.6+10*3+h));direction=Vector((-n.x,-n.y,0));hit=bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),start,direction,distance=9);assert hit[0] and hit[4].active_material.name.startswith('Maple215_glass'),(label,str(hit));rays.append({'sample':label,'firstHit':hit[4].name})
(O/'opening-visibility.json').write_text(json.dumps({'status':'PASS','rays':rays},indent=2));(O/'geometry-validation.json').write_text(json.dumps({'status':'PASS','scope':'Finite closed positive-volume solids,0mground,within80.6mconservativeenvelope,8glassvisibilitysamples. Doesnotestablishphotoaccuracy.','boundsBlenderENU':bounds,'components':checks},indent=2));bpy.context.scene.camera=bpy.data.objects['A_SE_primary_match']
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL';area.spaces.active.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-215.blend'));print('VALIDATION215_PASS',len(checks),bounds,rays)
