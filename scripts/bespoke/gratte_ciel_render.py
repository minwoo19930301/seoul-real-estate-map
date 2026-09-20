import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/gratte-ciel'
scene=bpy.context.scene
for name in ['southwest','northeast','plan','crown']:
    scene.camera=bpy.data.objects['review-'+name]
    scene.render.filepath=str(OUT/('review-'+name+'.png'))
    bpy.ops.render.render(write_still=True)
print('GRATTE_CIEL_REVIEW_RENDERS_COMPLETE')
