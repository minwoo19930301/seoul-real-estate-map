import bpy,pathlib,json
P=pathlib.Path(__file__).parent
reports=[]
for tower,H in [('109',132),('100',74)]:
 s=sorted([s for s in bpy.data.scenes if s.name.startswith('Acro'+tower+'_representative')],key=lambda s:s.name)[-1];bpy.context.window.scene=s
 meshes=[o for o in s.objects if o.type=='MESH']
 for o in meshes:
  for v in o.data.vertices:
   if (o.matrix_world@v.co).z<0:v.co.z=-o.location.z
 bpy.context.view_layer.update()
 zs=[(o.matrix_world@v.co).z for o in meshes for v in o.data.vertices]
 assert abs(min(zs))<.001 and abs(max(zs)-H)<.001
 bpy.data.libraries.write(str(P/('acro-riverpark-'+tower+'-authored.blend')),{s},fake_user=True,compress=True)
 exec(compile((P/('consolidate.py' if tower=='109' else 'consolidate100.py')).read_text(),'<consolidate>','exec'))
 with bpy.data.libraries.load(str(P/('acro-riverpark-'+tower+'-authored.blend')),link=False) as (data,to):
  scenes=data.scenes;assert len(scenes)==1 and scenes[0].startswith('Acro'+tower)
 reports.append({'tower':tower,'min_z':min(zs),'max_z':max(zs),'height_source':'OpenStreetMap estimate, not registered legal height','authored_meshes':len(meshes),'standalone_scenes':scenes,'reference_scope':'Complex photo only; individual tower facing assignment unresolved'})
(P/'final-geometry-validation.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports))
