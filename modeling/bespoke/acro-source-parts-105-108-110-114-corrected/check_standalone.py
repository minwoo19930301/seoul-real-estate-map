import bpy,json,pathlib,hashlib
P=pathlib.Path(__file__).parent;reports=[];old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
for t in ['105','106','107','108','110','111','112','113','114']:
 p=P/t;source=json.loads((p/'source-data.json').read_text())
 with bpy.data.libraries.load(str(p/('bespoke-acro-riverpark-'+t+'-authored.blend')),link=False) as (a,b):names=list(a.scenes);b.scenes=a.scenes
 assert len(names)==1;s=b.scenes[0];obs=[o for o in s.objects if o.type=='MESH'];images=sum(n.type=='TEX_IMAGE' for o in obs for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes);assert images==0
 regions=[]
 for r in source['regions']:
  vs=[v.co for o in obs if o.get('region_id')==r['region_id'] for v in o.data.vertices];assert vs and min(v.z for v in vs)==0 and abs(max(v.z for v in vs)-r['height_m'])<1e-4
  regions.append({'region_id':r['region_id'],'base':min(v.z for v in vs),'max':max(v.z for v in vs)})
 report={'tower':t,'scene_count':1,'scene_names':names,'mesh_count':len(obs),'images':images,'regions':regions,'blend_sha256':hashlib.sha256((p/('bespoke-acro-riverpark-'+t+'-authored.blend')).read_bytes()).hexdigest()};(p/'standalone-validation.json').write_text(json.dumps(report,indent=2));reports.append(report)
 bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
assert before=={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes} and bpy.context.scene==old
print(json.dumps(reports))
