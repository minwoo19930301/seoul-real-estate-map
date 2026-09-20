import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/raemian-caelitus';scene=bpy.context.scene
batch=OUT/'render-batch.json';names=json.loads(batch.read_text()) if batch.exists() else ['southwest_completed_photo','northwest_rear_steps','east_completed_photo','roof_and_bridges','bridge_and_piloti','podium_canopy_ovals']
for name in names:
 scene.camera=bpy.data.objects[name];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['southwest_completed_photo'];bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'raemian-caelitus.blend'));print('CAELITUS_RENDERED',names)
