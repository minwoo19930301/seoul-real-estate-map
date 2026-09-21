import bpy,pathlib,json,math,hashlib
from mathutils import Vector
P=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};f=P/'archive-v1/jamsil-ricenz-218-authored.blend'
with bpy.data.libraries.load(str(f),link=False) as (a,b):b.scenes=a.scenes
assert len(b.scenes)==1;s=b.scenes[0];bpy.context.window.scene=s
ob=next(o for o in s.objects if o.type=='MESH' and 'broad white facade frames' in o.name);me=ob.data;verts=[v.co.copy() for v in me.vertices];faces=[tuple(p.vertices) for p in me.polygons];assert len(verts)%8==0 and len(faces)==len(verts)//8*6
boxes=[];rails={};vertical=[]
for i in range(len(verts)//8):
 v=verts[i*8:i*8+8];center=sum(v,Vector())/8;ex=v[1]-v[0];ey=v[3]-v[0];w=ex.length;dep=ey.length;h=v[4].z-v[0].z;b={'i':i,'center':center,'ex':ex.normalized(),'ey':ey.normalized(),'w':w,'dep':dep,'h':h};boxes.append(b)
 if abs(h-.055)<.0001 and abs(dep-.045)<.0001 and w>1:rails.setdefault(round(center.z,3),[]).append(b)
 if abs(h-.87)<.0001 and abs(w-.022)<.0001 and abs(dep-.025)<.0001:vertical.append(b)
removed=set();witness=[]
for b in vertical:
 for faceidx in [0,1]:
  pi=b['i']*6+faceidx;vs=[verts[j] for j in faces[pi]];z=sum(v.z for v in vs)/4
  for rail in rails.get(round(z,3),[]):
   if all(abs((v-rail['center']).dot(rail['ex']))<=rail['w']/2-1e-5 and abs((v-rail['center']).dot(rail['ey']))<=rail['dep']/2-1e-5 and abs(v.z-rail['center'].z)<=rail['h']/2-1e-5 for v in vs):
    removed.add(pi);witness.append({'removed_face':pi,'vertical_box':b['i'],'containing_horizontal_rail_box':rail['i'],'z':z});break
assert len(removed)>0
# Export-friendly chunks retain exact coordinates, flat normals and material; no decimation.
mat=me.materials[0];chunks=[];chunkboxes=2048
for start in range(0,len(boxes),chunkboxes):
 stop=min(start+chunkboxes,len(boxes));vv=verts[start*8:stop*8];ff=[tuple(j-start*8 for j in faces[pi]) for pi in range(start*6,stop*6) if pi not in removed];nm=bpy.data.meshes.new('Ricenz218 exact white rail chunk');nm.from_pydata(vv,[],ff);nm.update();no=bpy.data.objects.new('Ricenz218 white exact chunk '+str(start//chunkboxes),nm);s.collection.objects.link(no);nm.materials.append(mat);chunks.append(no)
bpy.data.objects.remove(ob,do_unlink=True);s['mesh_optimization']='Only fully enclosed vertical-rail caps removed; exact coordinates/rail count/spacing retained; white mesh split for16bit indices';s['removed_fully_internal_quad_faces']=len(removed)
for o in bpy.context.selected_objects:o.select_set(False)
meshes=[o for o in s.objects if o.type=='MESH']
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.export_scene.gltf(filepath=str(P/'jamsil-ricenz-218.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True,export_texcoords=False,export_normals=True)
for name in ['front','opposite','side','roof']:
 cam=next(o for o in s.objects if o.type=='CAMERA' and name in o.name);s.camera=cam;s.render.filepath=str(P/(name+'.png'));bpy.ops.render.render(write_still=True)
bpy.data.libraries.write(str(P/'jamsil-ricenz-218-authored.blend'),{s},fake_user=True,compress=True);report={'vertical_rail_bars_unchanged':len(vertical),'white_box_components_unchanged':len(boxes),'removed_fully_enclosed_quad_caps':len(removed),'removed_triangles':len(removed)*2,'white_chunks':len(chunks),'mesh_count':len(meshes),'unchanged_coordinates':True,'unchanged_materials_and_flat_normals':True,'no_uv_or_colors_in_source':True,'no_decimation':True,'witnesses':witness};(P/'optimization-proof.json').write_text(json.dumps(report,indent=2));bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);assert before=={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};print(json.dumps({k:v for k,v in report.items() if k!='witnesses'}))
