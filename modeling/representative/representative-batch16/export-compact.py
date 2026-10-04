import bpy,json

def export_compact(S,objects,OUT):
 tmp=bpy.data.collections.new('TEMP_EXPORT');bpy.context.scene.collection.children.link(tmp)
 materials={}
 for ob in objects:
  if ob.type!='MESH':continue
  for face in ob.data.polygons:
   mat=ob.data.materials[face.material_index];key=mat.name
   if key not in materials:materials[key]=[mat,[],[],{}]
   _,verts,faces,mapping=materials[key];indices=[]
   for vi in face.vertices:
    keyv=(ob.name,vi)
    if keyv not in mapping:mapping[keyv]=len(verts);verts.append(tuple(ob.matrix_world@ob.data.vertices[vi].co))
    indices.append(mapping[keyv])
   faces.append(indices)
 exported=[]
 for name,(mat,verts,faces,_) in materials.items():
  mesh=bpy.data.meshes.new(name+' export');mesh.from_pydata(verts,[],faces);mesh.materials.append(mat);mesh.update();ob=bpy.data.objects.new(name,mesh);tmp.objects.link(ob);exported.append(ob)
 for ob in bpy.context.selected_objects:ob.select_set(False)
 for ob in exported:ob.select_set(True)
 bpy.context.view_layer.objects.active=exported[0]
 exported[0]['wgs84_anchor']=json.dumps(S['anchor']);exported[0]['source_footprint_ids']=json.dumps([t['id'] for t in S['towers']]);exported[0]['constructionMethod']='representative-photo-informed'
 bpy.ops.export_scene.gltf(filepath=str(OUT/(S['code']+'.glb')),export_format='GLB',use_selection=True,export_extras=True)
 for ob in exported:
  mesh=ob.data;bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
 bpy.data.collections.remove(tmp)
 return len(exported)
