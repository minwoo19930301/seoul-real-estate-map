import bpy,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
scene=bpy.context.scene
for name in ['SE-GS-photo','101-crown-detail','roof-plan','north-103','SW-street','roof-elevated']:
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/('review-v2-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('Mecenatpolis six comparison views rendered')
