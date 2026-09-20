import bpy
from pathlib import Path
O=Path(__file__).parent;(O/'renders').mkdir(exist_ok=True)
for name in globals().get('REVIEW_VIEWS', ['A_SE_primary_match','W06_North_end','W07_East_corner','Roof_individual_layout','Ground_NE_stone','SW_unverified_return','SE_white_detail','W06_NE_detail']):
 s=bpy.context.scene;s.camera=bpy.data.objects[name];s.render.filepath=str(O/'renders'/f'{name}.png');bpy.ops.render.render(write_still=True);print('RENDERED',name,flush=True)
print('ALL215_RENDERED')
