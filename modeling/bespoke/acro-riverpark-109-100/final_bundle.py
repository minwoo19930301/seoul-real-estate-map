import bpy,pathlib,json,math
P=pathlib.Path(__file__).parent
reports=[]
for tower,H in [('109',132),('100',74)]:
 candidates=[s for s in bpy.data.scenes if s.name.startswith('Acro'+tower+'_representative')]
 s=sorted(candidates,key=lambda s:s.name)[-1];bpy.context.window.scene=s
 for o in s.objects:
  if o.type=='MESH' and ('compact roof plant cap' in o.name or 'pale roof cap coping' in o.name):o.location.z-=1.05
 meshes=[o for o in s.objects if o.type=='MESH'];zs=[(o.matrix_world@v.co).z for o in meshes for v in o.data.vertices]
 # update matrices before exact height validation
 bpy.context.view_layer.update();zs=[(o.matrix_world@v.co).z for o in meshes for v in o.data.vertices]
 assert abs(max(zs)-H)<.002,(tower,max(zs))
 for o in s.objects:
  if o.type=='CAMERA':
   s.camera=o;label=o.name.split()[1].split('.')[0];s.render.filepath=str(P/(tower+'-'+label+'.png'));bpy.ops.render.render(write_still=True)
 bpy.data.libraries.write(str(P/('acro-riverpark-'+tower+'-authored.blend')),{s},fake_user=True,compress=True)
 exec(compile((P/('consolidate.py' if tower=='109' else 'consolidate100.py')).read_text(),'<consolidate>','exec'))
 reports.append({'tower':tower,'height_max_m':max(zs),'height_min_m':min(zs),'meshes_in_authored_scene':len(meshes),'scene':s.name,'source_height_m':H,'height_source':'OpenStreetMap; not legal register'})
(P/'final-geometry-validation.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports))
