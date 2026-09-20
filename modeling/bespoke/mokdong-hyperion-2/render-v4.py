import bpy
from pathlib import Path
P=Path(__file__).resolve().parent
s=bpy.context.scene
s.cycles.samples=16
s.render.resolution_x=1500;s.render.resolution_y=1400
for name in ['202-crown','NE-roof-consultant','SE-source','north-courtyard','NW-ground-photo','roof-plan']:
 s.camera=bpy.data.objects[name];s.render.filepath=str(P/f'review-v4-{name}.png');bpy.ops.render.render(write_still=True)
