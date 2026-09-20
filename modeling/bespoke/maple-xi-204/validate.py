import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;D=json.loads((O/'authored-input.json').read_text());objs=[o for o in bpy.data.objects if o.type=='MESH' and o.get('asset_id')==D['id']];out=[]
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);v=bm.calc_volume(signed=True);nm=sum(not e.is_manifold for e in bm.edges);finite=all(math.isfinite(c) for p in bm.verts for c in p.co);bm.free();out.append({'component':o.name,'volume':v,'nonManifoldEdges':nm,'finite':finite})
assert all(x['volume']>0 and x['nonManifoldEdges']==0 and x['finite'] for x in out)
bounds={'min':[min((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)],'max':[max((o.matrix_world@v.co)[i] for o in objs for v in o.data.vertices) for i in range(3)]};assert abs(bounds['min'][2])<1e-6;assert bounds['max'][2]<86.851
# Visual correctness guard: opaque facade backs must not hide sampled actualglass.
V=[Vector(p) for p in D['ringEN']];rays=[]
for e,t,label in [(4,.38,'SE wide bank'),(5,1-.606,'SW gray living bay'),(5,1-.42,'SW deep central slot'),(5,1-.09,'SW left living window'),(0,.23,'provisionalrear e0'),(1,.18,'provisionalrear e1'),(2,.39,'provisionalrear e2'),(3,.28,'provisionalrear e3')]:
 a,b=V[e],V[(e+1)%6];n=Vector((-(b-a).y,(b-a).x)).normalized();c=a+(b-a)*t;start=Vector((c.x+n.x*4,c.y+n.y*4,4.3+10*3+1.4));direction=Vector((-n.x,-n.y,0));hit=bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),start,direction,distance=9);assert hit[0] and ('window_glass' in hit[4].name or 'glazed_windows' in hit[4].name or 'provisional_openings' in hit[4].name),(label,str(hit));rays.append({'sample':label,'firstHit':hit[4].name})
(O/'opening-visibility.json').write_text(json.dumps({'status':'PASS','rays':rays},indent=2))
(O/'geometry-validation.json').write_text(json.dumps({'status':'PASS','scope':'Finite closed positive-volume components; ground0; legalheight envelope;8glassvisibilityrays. These checks do not prove photographic likeness.','boundsBlenderENU':bounds,'components':out},indent=2))
s=bpy.context.scene;s.camera=bpy.data.objects['C_SW_completed_match']
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-204.blend'));print('VALIDATION204_PASS',len(out),bounds,rays)
