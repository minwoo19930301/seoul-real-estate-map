"""Render the existing individually authored scene through Blender MCP; no rebuild."""
import bpy, json
from pathlib import Path
out=Path(__file__).resolve().parents[2]/'data/model-source/bespoke/express-terminal'
scene=bpy.context.scene
scene.cycles.samples=24
for name in ['View_Courtyard','View_Main_South_End','View_Street','View_Main_East']:
    scene.camera=bpy.data.objects[name]
    scene.render.filepath=str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['View_Courtyard']
bpy.ops.wm.save_as_mainfile(filepath=str(out/'express-terminal.blend'))
print(json.dumps({'rendered':[str(out/(n+'.png')) for n in ['View_Courtyard','View_Main_South_End','View_Street','View_Main_East']]}))
