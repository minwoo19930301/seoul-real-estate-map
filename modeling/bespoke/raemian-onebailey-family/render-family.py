import bpy,json
from pathlib import Path
P=Path(__file__).resolve().parent
scene=bpy.context.scene
records=[]
for name in ['river-source','101-102-inner-low','123-122-inner-low','courtyard','roof-plan','east-diagonal']:
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(P/f'review-family-{name}.png');bpy.ops.render.render(write_still=True)
 records.append({'camera':name,'filepath':scene.render.filepath,'position':list(scene.camera.location),'projection':scene.camera.data.type})
(P/'render-family-records.json').write_text(json.dumps(records,indent=2))
print('Rendered six comparison views.')
