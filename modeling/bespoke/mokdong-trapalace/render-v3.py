import bpy
from pathlib import Path
OUT=Path(__file__).resolve().parent
s=bpy.context.scene
for name in ['SW-full','elevated-source','western-crown','north-reverse','SE-full','roof-plan','helipad-low-angle']:
 s.camera=bpy.data.objects[name];s.render.filepath=str(OUT/('review-v3-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('SIX_VIEWS_COMPLETE')
