import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/lg-art-center';rows=[]
for o in bpy.data.objects:
 if o.type!='MESH' or not o.get('site'):continue
 o.data.calc_loop_triangles();volume=0
 for v in o.data.vertices:assert all(math.isfinite(c) for c in v.co)
 for t in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in t.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 rows.append({'name':o.name,'triangles':len(o.data.loop_triangles),'signedVolume':volume,'minZ':min(v.co.z for v in o.data.vertices)})
assert min(x['minZ'] for x in rows)==0
D=json.loads((OUT/'authored-input.json').read_text());a,b=[Vector((x,y,5.3)) for x,y in D['tube']['endpoints']];axis=(b-a).normalized();origin=(a+b)/2-axis*35;deps=bpy.context.evaluated_depsgraph_get()
# The Tube shell must not fill its longitudinal centre; ray-test the shell itself.
shell=next(o for o in bpy.data.objects if o.name.startswith('LG_rolled_elliptical_Tube_shell'));hit=shell.ray_cast(shell.matrix_world.inverted()@origin,axis,distance=70)[0];assert not hit,'Tube shell centre is blocked'
(OUT/'geometry-validation.json').write_text(json.dumps({'blender':bpy.app.version_string,'finiteVertices':True,'positiveMeshVolumes':True,'groundMinZ':0,'TubeShellLongitudinalVoid':True,'components':rows},indent=2)+'\n');bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'lg-art-center-seoul.blend'));print('LG_VALIDATED',len(rows),sum(r['triangles'] for r in rows),'triangles')
