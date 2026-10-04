import bpy,json,math
bpy.ops.wm.open_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-athletes-village-228-representative/olympic-athletes-village-228-authored.blend',load_ui=False,use_scripts=False)
assert len(bpy.data.scenes)==1
s=bpy.data.scenes[0];meshes=[o for o in s.objects if o.type=='MESH'];vs=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
s['supersedesAssetIds']='["fallback-olympic-athletes-village-228"]'
s['current_owner_asset_ids']='["fallback-olympic-athletes-village-228"]'
s['binding_status']='root verified fallback owner'
s['reference_scope']='Corrected actual AthletesVillage photograph directly viewed: pale grey end/service strips, narrow vertical windows and horizontal floor seams; warm cream long facade with small square apertures and dark recessed verticalbank; sharp endwalls extending slightly above flat roof. No228number visible, complexappearance inference only; compass and hidden faces unknown. Neighbor connected height steps NOT used to invent228multiheightfootprint. Roof fin dimensions and positions inferred; source photo remains private.'
bpy.ops.wm.save_as_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-athletes-village-228-representative/olympic-athletes-village-228-authored.blend',compress=True)
r={'scenes':len(bpy.data.scenes),'source_id':s['source_id'],'register_id':s['register_id'],'floors':s['floors'],'height':s['model_upper_envelope_m'],'mesh_count':len(meshes),'camera_count':sum(o.type=='CAMERA' for o in s.objects),'image_nodes':sum(n.type=='TEX_IMAGE' for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes),'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]]}
assert r['source_id']=='955c73da-50bf-42bb-a94c-a456fc48bd4f' and r['register_id']=='102512802' and r['floors']==10 and r['height']==30.5 and r['camera_count']==4 and r['image_nodes']==0
assert abs(r['bounds_xyz'][0][2])<1e-5 and abs(r['bounds_xyz'][1][2]-30.5)<1e-4
print('ARTIFACT:standalone-validation.json:'+json.dumps(r))
bpy.ops.wm.open_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-athletes-village-228-representative/headless-initial.blend',load_ui=False,use_scripts=False)
print('ARTIFACT:standalone-restore.json:'+json.dumps({'restored_scene':bpy.context.scene.name,'scenes':len(bpy.data.scenes)}))
