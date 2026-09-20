import bpy,json
from pathlib import Path
O=Path(__file__).parent;(O/'renders').mkdir(exist_ok=True)
views=['C_SW_completed_match','A_SE_aerial_match','Roof_two_plants','White_face_detail','Dark_face_detail','Base_completed_match','NW_unverified_back']
for name in views:
 s=bpy.context.scene;s.camera=bpy.data.objects[name];s.render.filepath=str(O/'renders'/f'{name}.png');bpy.ops.render.render(write_still=True);print('RENDERED',name,flush=True)
print('ALL204_RENDERED')
