import bpy,json,pathlib,hashlib
P=pathlib.Path(__file__).parent;reports=[]
for name in ['101','102','104']:
 p=P/name
 with bpy.data.libraries.load(str(p/('banpo-xi-'+name+'-authored.blend')),link=False) as (a,b):
  names=list(a.scenes);b.scenes=a.scenes
 loaded=b.scenes
 r={'tower':name,'standalone_scene_names':names,'scene_count':len(names),'mesh_objects':sum(o.type=='MESH' for s in loaded for o in s.objects),'image_nodes':sum(n.type=='TEX_IMAGE' for s in loaded for o in s.objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes),'source_sha256':hashlib.sha256((p/'source-data.json').read_bytes()).hexdigest(),'blend_sha256':hashlib.sha256((p/('banpo-xi-'+name+'-authored.blend')).read_bytes()).hexdigest()}
 assert r['scene_count']==1 and r['mesh_objects']==7 and r['image_nodes']==0
 for s in loaded:
  bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
 (p/'standalone-validation.json').write_text(json.dumps(r,indent=2));reports.append(r)
print(json.dumps(reports))
