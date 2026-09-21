import bpy,json,math
from pathlib import Path
from mathutils import Vector
OUT=Path('/Users/hyemini/Documents/Codex/2026-09-08/seoul-elevation-local/data/model-source/bespoke/maple-height-corrected');D=json.loads((OUT/'authored-input.json').read_text());results=[]
for A in D['assets']:
 objs=[o for o in bpy.data.objects if o.type=='MESH' and o.get('dong')==A['dong']];locations={o.name:o.location.copy() for o in objs}
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.location=Vector((0,0,0));o.select_set(True);o['limits']=A['heightStatus']
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.export_scene.gltf(filepath=str(OUT/(A['id']+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_apply=True)
 for o in objs:o.location=locations[o.name]
 results.append({'id':A['id'],'objects':len(objs),'file':A['id']+'.glb'})
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-height-corrected.blend'));print('FINAL_IDS_EXPORTED',results)
