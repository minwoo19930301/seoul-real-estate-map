"""Review the saved Culture Station scene through Blender MCP."""
import bpy,json
from pathlib import Path
out=Path(__file__).resolve().parents[2]/'data/model-source/bespoke/culture-station-seoul284'
scene=bpy.context.scene
bpy.data.objects['View_Plan'].data.ortho_scale=240
names=['View_East_Front','View_South_East','View_North_East','View_Plan']
for name in names:
    scene.camera=bpy.data.objects[name];scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['View_South_East'];bpy.ops.wm.save_as_mainfile(filepath=str(out/'culture-station-seoul284.blend'))
print(json.dumps({'rendered':[str(out/(n+'.png')) for n in names]}))
