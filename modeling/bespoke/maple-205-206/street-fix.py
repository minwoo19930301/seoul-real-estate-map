import bpy
from mathutils import Vector
from pathlib import Path
O=Path(__file__).parent;c=bpy.data.objects['NE_street'];c.location=(210,180,6);c.rotation_euler=(Vector((0,0,107.8*.48))-c.location).to_track_quat('-Z','Y').to_euler();bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-206.blend'));REVIEW_VIEWS=['NE_street'];exec(compile((O/'render.py').read_text(),str(O/'render.py'),'exec'))
