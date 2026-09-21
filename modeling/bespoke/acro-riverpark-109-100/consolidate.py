import bpy,pathlib,json,collections
P=pathlib.Path(__file__).parent
src=bpy.context.scene
assert src.name.startswith('Acro109')
groups=collections.defaultdict(list)
for o in src.objects:
 if o.type=='MESH':groups[o.data.materials[0]].append(o)
es=bpy.data.scenes.new('Acro109_export_only');bpy.context.window.scene=es
counts={}
for mat,os in groups.items():
 vs=[];fs=[]
 for o in os:
  off=len(vs);vs.extend([tuple(o.matrix_world@v.co) for v in o.data.vertices]);fs.extend([tuple(i+off for i in p.vertices) for p in o.data.polygons])
 me=bpy.data.meshes.new('109 '+mat.name);me.from_pydata(vs,[],fs);me.materials.append(mat);me.update();ob=bpy.data.objects.new(me.name,me);es.collection.objects.link(ob);ob.select_set(True);ob['source_semantic_objects']=len(os);counts[mat.name]=len(os)
bpy.ops.export_scene.gltf(filepath=str(P/'acro-riverpark-109.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_yup=True)
bpy.context.window.scene=src
for o in list(es.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.data.scenes.remove(es)
print(json.dumps({'consolidated_material_meshes':len(groups),'semantic_authoring_objects':counts,'authored_scene_untouched':src.name}))
