import bpy,json,pathlib,math,hashlib
P=pathlib.Path(__file__).parent
old=bpy.context.scene
before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
reports=[]
for t in ['101','102','104']:
 p=P/t;d=json.loads((p/'source-data.json').read_text());source=pathlib.Path(d['source_blend']);assert hashlib.sha256(source.read_bytes()).hexdigest()==d['source_blend_sha256']
 with bpy.data.libraries.load(str(source),link=False) as (a,b):
  assert len(a.scenes)==1;b.scenes=a.scenes
 s=b.scenes[0];s.name='Banpo Xi '+t+' register corrected';bpy.context.window.scene=s
 obs=[o for o in s.objects if o.type=='MESH'];assert len(obs)==7
 prior=[o.matrix_world@v.co for o in obs for v in o.data.vertices];zmin=min(v.z for v in prior);zmax=max(v.z for v in prior);assert abs(zmin)<1e-5 and abs(zmax-81)<1e-5
 xy_before=[(v.x,v.y) for v in prior]
 for o in obs:
  assert o.matrix_world.is_identity
  o.data=o.data.copy()
  for v in o.data.vertices:v.co.z*=81.3/81
  o.data.update()
 current=[o.matrix_world@v.co for o in obs for v in o.data.vertices];assert [(v.x,v.y) for v in current]==xy_before
 s['height_basis']='Numbered register field81.3m; modeled upper envelope81.3m; roof/ornament legal measurement datum unconfirmed'
 s['register_id']=d['register_row']['id'];s['register_row_number']=d['register_row']['row_number'];s['register_height_m']=81.3;s['model_upper_envelope_m']=81.3;s['osm_height_m']=81.;s['floors']=29
 s['reference_scope']='KB complex-level photo inference; numbered tower photo identity/orientation unconfirmed; reviewed facade and24-floor lower wing retained'
 for o in bpy.context.selected_objects:o.select_set(False)
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 bpy.ops.export_scene.gltf(filepath=str(p/('banpo-xi-'+t+'.glb')),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
 for n in ['front','opposite','side','roof']:
  cams=[o for o in s.objects if o.type=='CAMERA' and n in o.name];assert len(cams)==1;s.camera=cams[0];s.render.filepath=str(p/(n+'.png'));bpy.ops.render.render(write_still=True)
 bpy.data.libraries.write(str(p/('banpo-xi-'+t+'-authored.blend')),{s},fake_user=True,compress=True)
 result={'tower':t,'source_blend_sha256':d['source_blend_sha256'],'xy_vertices_exactly_preserved':True,'vertical_scale':81.3/81,'base_z':min(v.z for v in current),'max_z':max(v.z for v in current),'register_height_m':81.3,'roof_datum_uncertain':True,'floors':29,'households':int(d['register_row']['households']),'mesh_objects':len(obs),'image_nodes':sum(n.type=='TEX_IMAGE' for o in obs for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes),'prior_scene_preserved':old.name}
 assert abs(result['base_z'])<1e-5 and abs(result['max_z']-81.3)<1e-4 and result['image_nodes']==0
 (p/'validation.json').write_text(json.dumps(result,indent=2));reports.append(result)
 bpy.context.window.scene=old;bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after
(P/'scene-preservation.json').write_text(json.dumps({'same_scene_object_lists':True,'before':before,'after':after,'active_scene':old.name},indent=2));print(json.dumps(reports))
