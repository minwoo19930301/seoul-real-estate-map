import bpy,json,pathlib,math,hashlib
P=pathlib.Path(__file__).parent;D=json.loads((P/'source-data.json').read_text());regions=json.loads((P/'regions.json').read_text());old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
source=pathlib.Path(D['source_blend_roof_correction']);assert hashlib.sha256(source.read_bytes()).hexdigest()==D['source_blend_roof_correction_sha256']
with bpy.data.libraries.load(str(source),link=False) as (a,b):
 assert len(a.scenes)==1;b.scenes=a.scenes
s=b.scenes[0];s.name='Banpo Xi 101 roof contained';bpy.context.window.scene=s;objs=[o for o in s.objects if o.type=='MESH'];proof=[];theta=D['facade_axis_rad_inferred'];co,si=math.cos(theta),math.sin(theta)
def xy(u,v):return u*co-v*si,u*si+v*co
for o in objs:
 oldv=[tuple(v.co) for v in o.data.vertices];oldf=[tuple(p.vertices) for p in o.data.polygons];name=o.data.materials[0].name;roofkind='white' if 'ivory course bands' in name else ('cap' if 'dark coping' in name else None)
 if not roofkind:
  proof.append({'material':name,'all_vertices_faces_unchanged':True,'vertex_count':len(oldv)});continue
 cutoff=len(oldv)-72;assert cutoff>0;keepf=[f for f in oldf if max(f)<cutoff];removef=[f for f in oldf if min(f)>=cutoff];assert len(removef)==54 and len(keepf)+54==len(oldf);assert min(v[2] for v in oldv[cutoff:])>=regions[0]['body_height_m']-.001
 verts=oldv[:cutoff].copy();faces=keepf.copy();removed_bounds=[[min(v[i] for v in oldv[cutoff:]) for i in range(3)],[max(v[i] for v in oldv[cutoff:]) for i in range(3)]]
 def box(u,v,z,w,d,h):
  x,y=xy(u,v);off=len(verts);verts.extend([(x+a*co-b*si,y+a*si+b*co,z+c) for c in [-h/2,h/2] for a,b in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]);faces.extend([tuple(off+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
 scale=81.3/81
 for region in regions:
  u,v,w,d=region['roof_frame_uv'];z=region['body_height_m']
  if roofkind=='white':
   for a in [-w/2,w/2]:
    for b in [-d/2,d/2]:box(u+a,v+b,z+1.35*scale,.45,.45,2.7*scale)
   if region==regions[1]:box(u,v,z+1.05*scale,w*.65,d*.5,2.1*scale)
  else:
   for b in [-d/2,d/2]:box(u,v+b,z+2.8*scale,w+.6,.6,.4*scale)
   for a in [-w/2,w/2]:box(u+a,v,z+2.8*scale,.6,d+.6,.4*scale)
   if region==regions[1]:box(u,v,z+2.25*scale,w*.75,d*.65,.4*scale)
 mat=o.data.materials[0];me=bpy.data.meshes.new(o.name+' roof corrected');me.from_pydata(verts,[],faces);me.materials.append(mat);me.update();o.data=me
 assert [tuple(v.co) for v in me.vertices[:cutoff]]==oldv[:cutoff] and [tuple(p.vertices) for p in me.polygons[:len(keepf)]]==keepf
 proof.append({'material':name,'retained_facade_vertices':cutoff,'retained_facade_faces':len(keepf),'retained_vertices_faces_exact':True,'removed_roof_box_count':9,'removed_bounds':removed_bounds,'new_roof_boxes':(len(verts)-cutoff)//8})
s['supersedesAssetIds']=json.dumps(D['supersedesAssetIds']);s['binding_status']=D['binding_status'];s['roof_correction']=D['roof_correction'];s['reference_scope']='Complex photo inference; numbered photograph/orientation and 24F lower region unverified';s['regions_json']=json.dumps(regions)
for o in bpy.context.selected_objects:o.select_set(False)
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(P/'banpo-xi-101.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
for view in ['front','opposite','side','roof']:
 s.camera=next(o for o in s.objects if o.type=='CAMERA' and view in o.name);s.render.filepath=str(P/(view+'.png'));bpy.ops.render.render(write_still=True)
bpy.data.libraries.write(str(P/'banpo-xi-101-authored.blend'),{s},fake_user=True,compress=True);(P/'facade-preservation.json').write_text(json.dumps(proof,indent=2));bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s);after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after;(P/'scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name},indent=2));print(json.dumps(proof))
