import bpy
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud'
scene=bpy.context.scene;o=bpy.data.objects['Source2_east'];o.location=(165,-60,130);o.rotation_euler=(Vector((25,14,80))-o.location).to_track_quat('-Z','Y').to_euler();o.data.lens=52
scene.camera=o;scene.render.filepath=str(OUT/'source2_east.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'maple-club-cloud.blend'))
