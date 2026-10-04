import bpy,json,pathlib,math
P=pathlib.Path(__file__).parent;old=bpy.context.scene
for n in ['100','101','103','104','109']:
 p=P/n;d=json.loads((p/'source-data.json').read_text())
 with bpy.data.libraries.load(str(p/(d['assetId']+'-authored.blend')),link=False) as (a,b):
  assert len(a.scenes)==1;b.scenes=a.scenes
 s=b.scenes[0];meshes=[o for o in s.objects if o.type=='MESH'];regions=[]
 for r in d['regions']:
  os=[o for o in meshes if o.get('region_id')==r['id']];z=[v.co.z for o in os for v in o.data.vertices];assert os and abs(max(z)-r['height_m'])<1e-4 and abs(min(z))<1e-5
  regions.append({'id':r['id'],'mesh_objects':len(os),'min_z':min(z),'max_z':max(z)})
 images=sum(1 for o in meshes for m in o.data.materials for node in m.node_tree.nodes if node.type=='TEX_IMAGE');assert images==0
 report={'tower':n,'scene_count_in_blend':1,'mesh_objects':len(meshes),'objects':len(s.objects),'regions':regions,'image_nodes':images,'previous_scene':old.name,'active_scene_preserved':bpy.context.scene==old,'passed':True};(p/'standalone-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));bpy.data.scenes.remove(s)
assert bpy.context.scene==old
