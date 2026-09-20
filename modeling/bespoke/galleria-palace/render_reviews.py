from pathlib import Path
import bpy,json
from mathutils import Vector
O=Path(__file__).resolve().parent;s=bpy.context.scene;c=s.camera;s.cycles.samples=16
views=[('Architect_SW',(-220,-235,16),(-10,-5,73),48,1200,1500),('Courtyard_A',(-34,-9,7),(-34,36,95),22,1600,1150),('Olympic_North',(18,330,19),(-9,25,75),42,1500,1450),('South_C',(36,-335,17),(6,-47,73),45,1400,1500),('East_B',(330,80,22),(12,-5,75),42,1500,1450),('Roof_Context',(-180,-190,280),(-7,-4,65),40,1500,1400)]
for name,pos,target,lens,w,h in views:
 c.data.type='PERSP';c.data.lens=lens;c.location=pos;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler();s.render.resolution_x=w;s.render.resolution_y=h;s.render.resolution_percentage=100;s.render.filepath=str(O/f'review-{name}.png');bpy.ops.render.render(write_still=True)
print(json.dumps({'renders':[v[0] for v in views]}))
