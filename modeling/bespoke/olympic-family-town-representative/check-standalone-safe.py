import bpy,json,math
bpy.ops.wm.open_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-family-town-109-representative/olympic-family-town-109-authored.blend',load_ui=False,use_scripts=False)
assert len(bpy.data.scenes)==1
s=bpy.data.scenes[0];meshes=[o for o in s.objects if o.type=='MESH'];vs=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
s['supersedesAssetIds']='["residential-a97e1b84-a819-4847-9fc6-3254b5fcdae8"]'
s['current_owner_asset_ids']='["residential-a97e1b84-a819-4847-9fc6-3254b5fcdae8"]'
s['binding_status']='root verified current residential fallback'
s['source_sha256']='68de5e58becd1067c0c79b88f2bbe8a2a873ee6b03aeec20d289159ad4ea705c'
s['regions_json']='[{"id": "uniform-parent-assumption", "height_m": 45.0, "floors": 15, "basis": "Estimated45m=15registered floors x3m; uniform envelope; unmeasured roof.", "triangles": [[[-43.20385480056332, -9.771112999692377], [43.199438357707656, 9.77667900015291], [-39.42337949143159, -20.190664999645946]], [[43.199438357707656, 9.77667900015291], [-43.20385480056332, -9.771112999692377], [39.42779593428725, 20.18509899997639]]]}]'
bpy.ops.wm.save_as_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-family-town-109-representative/olympic-family-town-109-authored.blend',compress=True)
r={'scenes':len(bpy.data.scenes),'source_id':s['source_id'],'register_id':s['register_id'],'floors':s['floors'],'height':s['model_upper_envelope_m'],'mesh_count':len(meshes),'camera_count':sum(o.type=='CAMERA' for o in s.objects),'image_nodes':sum(n.type=='TEX_IMAGE' for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes),'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]]}
assert r['source_id']=='a97e1b84-a819-4847-9fc6-3254b5fcdae8' and r['register_id']=='102513122' and r['floors']==15 and r['height']==45 and r['camera_count']==4 and r['image_nodes']==0
assert abs(r['bounds_xyz'][0][2])<1e-5 and abs(r['bounds_xyz'][1][2]-45)<1e-4
print('ARTIFACT:standalone-validation.json:'+json.dumps(r))
bpy.ops.wm.open_mainfile(filepath='/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/olympic-family-town-109-representative/headless-initial.blend',load_ui=False,use_scripts=False)
print('ARTIFACT:standalone-restore.json:'+json.dumps({'restored_scene':bpy.context.scene.name,'scenes':len(bpy.data.scenes)}))
