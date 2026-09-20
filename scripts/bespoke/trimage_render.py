"""Render the isolated saved Trimage scene through Blender MCP without changing assets."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/trimage'
scene=bpy.context.scene
# Timer keeps the MCP response prompt; real Blender performs these queued renders.
views=['river-source-match','courtyard-opposite','east-oblique','roof-plan','101-ribbons','103-stone-crown']
def render_next():
 if not views:return None
 name=views.pop(0)
 for col in bpy.data.collections:
  if col.name.endswith('_TRIMAGE_EDITABLE_COMPONENTS'):col.hide_render=(name=='101-ribbons' and not col.name.startswith('101')) or (name=='103-stone-crown' and not col.name.startswith('103'))
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/('review-'+name+'.png'));bpy.ops.render.render(write_still=True)
 return 0.5 if views else None
bpy.app.timers.register(render_next,first_interval=.5)
print('Queued6source-comparison renders in actual Blender scene.')
