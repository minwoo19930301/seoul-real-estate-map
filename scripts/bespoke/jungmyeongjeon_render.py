"""Photo-comparison renders of the currently open Jungmyeongjeon MCP scene."""
import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parents[2]/'data/model-source/bespoke/jungmyeongjeon'
scene=bpy.context.scene
for name,loc,target in [('Photo_Southwest_Ground',(-22,-40,2.0),(0,0,6.0)),('Photo_Rear_Ground',(-25,31,2.2),(-1,2,5.7))]:
    if name not in bpy.data.objects:
        d=bpy.data.cameras.new(name);d.type='PERSP';d.lens=43
        ob=bpy.data.objects.new(name,d);bpy.data.collections['QA'].objects.link(ob)
        ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
names=['Front_Southwest','Front_Southeast','Rear_Northwest','Measured_Roof','Front_Elevation','Photo_Southwest_Ground','Photo_Rear_Ground']
for name in names:
    scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Front_Southwest']
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jungmyeongjeon.blend'))
print(json.dumps({'rendered':names}))
