import bpy,pathlib,json,math
P=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};reports=[]
for t in map(str,range(105,115)):
 p=P/t;D=json.loads((p/'source-data.json').read_text())
 with bpy.data.libraries.load(str(p/('banpo-xi-'+t+'-authored.blend')),link=False) as (a,b):
  names=list(a.scenes);b.scenes=a.scenes
 assert len(names)==1;s=b.scenes[0];meshes=[o for o in s.objects if o.type=='MESH'];vs=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
 r={'tower':t,'scene_names':names,'mesh_objects':len(meshes),'cameras':[o.name for o in s.objects if o.type=='CAMERA'],'bounds_xyz':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'image_nodes':sum(n.type=='TEX_IMAGE' for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes),'source_id':s['source_id'],'register_id':s['register_id'],'floors':s['floors'],'reference_scope':s['reference_scope'],'supersedesAssetIds':s['supersedesAssetIds'],'binding_status':s['binding_status'],'finite':all(math.isfinite(c) for v in vs for c in v)}
 assert r['source_id']==D['id'] and r['register_id']==D['register_row']['id'] and r['floors']==D['floors'] and r['image_nodes']==0 and len(r['cameras'])==4 and r['finite'] and abs(r['bounds_xyz'][0][2])<1e-5 and abs(r['bounds_xyz'][1][2]-D['register_height_m'])<1e-4
 (p/'standalone-validation.json').write_text(json.dumps(r,indent=2));reports.append(r);bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after and old==bpy.context.scene;(P/'standalone-scene-preservation.json').write_text(json.dumps({'equal':before==after,'initial_scene':old.name},indent=2));print(json.dumps(reports))
