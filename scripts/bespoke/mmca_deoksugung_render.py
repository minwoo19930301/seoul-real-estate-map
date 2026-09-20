"""Render the saved live MCP model without changing export geometry."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/mmca-deoksugung'
scene=bpy.context.scene
views=['front-whole','front-portico','elevated-official-worksheet','source-roof-plan','rear-limit']
for name in views:
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['front-whole']
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='MATERIAL'
print(json.dumps({'rendered':views}))
