import bpy
from pathlib import Path
O=Path(__file__).parent;bpy.data.objects['Roof_support'].data.ortho_scale=110;bpy.ops.wm.save_as_mainfile(filepath=str(O/'maple-205.blend'));REVIEW_VIEWS=['Roof_support'];exec(compile((O/'render.py').read_text(),str(O/'render.py'),'exec'))
